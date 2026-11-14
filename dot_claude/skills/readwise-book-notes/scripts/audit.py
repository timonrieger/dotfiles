#!/usr/bin/env python3
"""Audit one Readwise book's highlights after a Kindle import.

Input is the JSON from the Readwise MCP `readwise_list_highlights` (book_id filter,
page_size 1000) or a snapshot written by snapshot.py. The script only reads and
reports; it never talks to Readwise. Fixes are applied afterwards with the MCP tools.

Usage:
  audit.py HIGHLIGHTS.json [--book BOOK.md] [--start-line N] [--chapter-prefix "# "]
                           [--prev SNAPSHOT.json] [--fixes FIXES.json]

  --book            full book text (markdown); enables text verification and chapter checks
  --start-line      1-based line where the body starts (skips the table of contents,
                    whose titles would otherwise match short heading-like highlights)
  --chapter-prefix  line prefix marking a chapter heading in the book file
  --prev            earlier snapshot; reports what was added/removed/changed since
  --fixes           write machine-readable fix proposals (deduped merge texts etc.)
  --accept-cross    comma-separated highlight IDs whose chapter-spanning merge the user
                    has approved; they are listed as accepted instead of flagged
"""
import argparse, json, re, sys
from collections import defaultdict

SEP = ' ... '  # Readwise joins concatenated highlights with this
COLOR_NAMES = {'yellow', 'blue', 'pink', 'orange', 'green', 'purple', 'amarillo', 'azul',
               'rosa', 'naranja', 'verde', 'morado', 'gelb', 'blau', 'grün', 'jaune', 'bleu'}
MERGE_RE = re.compile(r'^\s*\.c\d+\b|\bmerge\b|\bconcat', re.I)


def load(path):
    d = json.load(open(path, encoding='utf-8'))
    return d.get('highlights') or d.get('results') or d


def tags(h):
    return [t['name'] if isinstance(t, dict) else t for t in (h.get('tags') or [])]


def norm(s):
    return re.sub(r'[^a-z]', '', s.lower())


def segs(h):
    return (h.get('text') or '').split(SEP)


def dedupe(parts):
    out = []
    for p in parts:
        if p not in out:
            out.append(p)
    return out


def short(s, n=70):
    s = (s or '').replace('\n', ' ')
    return s if len(s) <= n else s[:n] + '…'


class Book:
    def __init__(self, path, start_line, chapter_prefix):
        lines = open(path, encoding='utf-8').read().split('\n')
        self.text = []
        self.idx = []
        for i, l in enumerate(lines):
            n = norm(re.sub(r'\{[^}]*\}', '', l))  # drop pandoc attributes
            self.text.append(n)
            self.idx += [i] * len(n)
        self.text = ''.join(self.text)
        self.base = next((k for k, i in enumerate(self.idx) if i >= start_line - 1), 0)
        self.chapters = [(i, re.sub(r'\{[^}]*\}|\[|\]', '', l[len(chapter_prefix):]).strip())
                         for i, l in enumerate(lines) if l.startswith(chapter_prefix)]

    def locate(self, s):
        """Book line of a passage, or None. Tries the opening, then a later window."""
        n = norm(s)
        if not n:
            return None
        for probe in (n[:80], n[20:80], n[-60:]):
            if len(probe) >= min(15, len(n)):
                p = self.text.find(probe, self.base)
                if p >= 0:
                    return self.idx[p]
        return None

    def chapter(self, line):
        cur = None
        for i, title in self.chapters:
            if i <= line:
                cur = title
        return cur


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('highlights')
    ap.add_argument('--book')
    ap.add_argument('--start-line', type=int, default=1)
    ap.add_argument('--chapter-prefix', default='# ')
    ap.add_argument('--prev')
    ap.add_argument('--fixes')
    ap.add_argument('--accept-cross', default='')
    a = ap.parse_args()

    H = sorted(load(a.highlights), key=lambda h: (h.get('location') or 0, h['id']))
    fixes = {'delete_duplicates': [], 'dedupe_merges': [], 'variant_pairs': [],
             'merge_instructions': [], 'color_tags': [], 'cross_chapter': [], 'unmatched': []}
    out = []
    p = out.append

    p(f'# Audit: {len(H)} highlights')
    by_day = defaultdict(int)
    for h in H:
        by_day[(h.get('highlighted_at') or '?')[:10]] += 1
    p('Import dates: ' + ', '.join(f'{d} ({n})' for d, n in sorted(by_day.items())))

    # 1. exact duplicates: keep the copy carrying a note/extra tags, else the newest
    p('\n## 1. Exact duplicates (same text)')
    groups = defaultdict(list)
    for h in H:
        groups[h.get('text')].append(h)
    n_dup = 0
    for text, g in groups.items():
        if len(g) < 2:
            continue
        n_dup += 1
        keep = max(g, key=lambda h: (bool(h.get('note')), len(tags(h)), h.get('highlighted_at') or ''))
        drop = [h for h in g if h['id'] != keep['id']]
        lost = []
        for h in drop:
            if h.get('note') and h['note'] != keep.get('note'):
                lost.append(f"note {h['id']}: {short(h['note'], 40)!r}")
            extra = set(tags(h)) - set(tags(keep))
            if extra:
                lost.append(f"tags {h['id']}: {sorted(extra)}")
        p(f"- loc {keep.get('location')}: keep {keep['id']}, delete {[h['id'] for h in drop]} — {short(text, 50)!r}")
        if lost:
            p(f"  ! move before deleting: {'; '.join(lost)}")
        fixes['delete_duplicates'].append({'keep': keep['id'], 'delete': [h['id'] for h in drop], 'carry_over': lost})
    if not n_dup:
        p('- none')

    # 2. merges whose parts repeat (Readwise concatenation bug)
    p('\n## 2. Merged highlights with repeated parts')
    n = 0
    for h in H:
        s = segs(h)
        u = dedupe(s)
        if len(s) > 1 and len(u) < len(s):
            n += 1
            p(f"- {h['id']} loc {h.get('location')}: {len(s)} parts, {len(u)} unique → proposed text in fixes")
            fixes['dedupe_merges'].append({'id': h['id'], 'text': SEP.join(u)})
    if not n:
        p('- none')

    # 3. variant pairs: one highlight is the leading part of another (leftover .c1 copy,
    #    or a later import captured a longer/merged version)
    p('\n## 3. Variant pairs (one highlight is the start of another)')
    n = 0
    ids_dup = {d for f in fixes['delete_duplicates'] for d in f['delete']}
    for s in H:
        if s['id'] in ids_dup:
            continue
        for l in H:
            if l['id'] == s['id'] or l['id'] in ids_dup or l.get('text') == s.get('text'):
                continue
            first = segs(l)[0]
            if len(segs(l)) > 1 and first == s.get('text') or \
               len(s.get('text') or '') >= 40 and (l.get('text') or '').startswith(s['text']):
                n += 1
                p(f"- short {s['id']} (loc {s.get('location')}, note {short(s.get('note'), 30)!r}) "
                  f"⊂ long {l['id']} (loc {l.get('location')}, {len(segs(l))} parts) — {short(s.get('text'), 45)!r}")
                fixes['variant_pairs'].append({'short': s['id'], 'long': l['id'], 'short_note': s.get('note')})
    if not n:
        p('- none')

    # 4. merge instructions written as Kindle notes
    p('\n## 4. Notes that look like merge instructions')
    n = 0
    for h in H:
        if h.get('note') and MERGE_RE.search(h['note']):
            n += 1
            p(f"- {h['id']} loc {h.get('location')}: {h['note']!r} — {short(h.get('text'), 45)!r}")
            fixes['merge_instructions'].append({'id': h['id'], 'note': h['note'], 'location': h.get('location')})
    if not n:
        p('- none')

    # 5. tags that only mirror the highlight colour
    p('\n## 5. Colour-mirroring tags')
    col = defaultdict(list)
    for h in H:
        for t in tags(h):
            if t.lower() in COLOR_NAMES or t == h.get('color'):
                col[t].append(h['id'])
    for t, ids in col.items():
        p(f'- {t!r} on {len(ids)} highlights')
        fixes['color_tags'].append({'tag': t, 'ids': ids})
    if not col:
        p('- none')

    # 6. verification against the book text
    if a.book:
        bk = Book(a.book, a.start_line, a.chapter_prefix)
        p('\n## 6. Book check')
        unmatched, cross, order = [], [], []
        for h in H:
            lines = [bk.locate(s) for s in segs(h)]
            missing = [i + 1 for i, l in enumerate(lines) if l is None]
            if missing:
                unmatched.append(h)
                p(f"- NOT IN BOOK {h['id']} loc {h.get('location')} part(s) {missing}: {short(h.get('text'), 50)!r}")
                fixes['unmatched'].append({'id': h['id'], 'parts': missing})
            found = [l for l in lines if l is not None]
            if len(found) > 1:
                chs = [bk.chapter(l) for l in found]
                if len(set(chs)) > 1 and str(h['id']) in a.accept_cross.split(','):
                    p(f"- (accepted) chapter-spanning merge {h['id']} loc {h.get('location')}")
                elif len(set(chs)) > 1:
                    cross.append(h)
                    p(f"- CROSSES CHAPTERS {h['id']} loc {h.get('location')}: " +
                      ' | '.join(f'part {i + 1}: {short(c, 30)}' for i, c in enumerate(chs)))
                    fixes['cross_chapter'].append({'id': h['id'], 'chapters': chs})
                if found != sorted(found):
                    order.append(h)
                    p(f"- PARTS OUT OF BOOK ORDER {h['id']} loc {h.get('location')}")
        if not (unmatched or cross or order):
            p('- every highlight and every merged part matches the book, in order, within one chapter')

        p('\n## 7. Highlights per chapter')
        per = defaultdict(list)
        for h in H:
            l = bk.locate(segs(h)[0])
            per[bk.chapter(l) if l is not None else '?'].append(h)
        for i, title in bk.chapters:
            if title in per:
                hs = per[title]
                noted = sum(1 for h in hs if h.get('note'))
                p(f'- {short(title, 55)}: {len(hs)} highlights, {noted} with notes')
        if '?' in per:
            p(f"- (not located): {len(per['?'])}")

    # 8. diff against the previous snapshot
    if a.prev:
        P = {h['id']: h for h in load(a.prev)}
        C = {h['id']: h for h in H}
        p('\n## 8. Changes since previous snapshot')
        added = [C[i] for i in C if i not in P]
        removed = [P[i] for i in P if i not in C]
        p(f'- added: {len(added)}')
        for h in sorted(added, key=lambda h: h.get('location') or 0):
            p(f"  + {h['id']} loc {h.get('location')} note={short(h.get('note'), 30)!r}: {short(h.get('text'), 50)!r}")
        p(f'- removed: {len(removed)}')
        for h in removed:
            p(f"  - {h['id']} loc {h.get('location')}: {short(h.get('text'), 50)!r}")
        for i in sorted(set(P) & set(C)):
            for field in ('text', 'note'):
                if (P[i].get(field) or '') != (C[i].get(field) or ''):
                    p(f"  ~ {i} {field} changed: {short(P[i].get(field), 30)!r} → {short(C[i].get(field), 30)!r}")
            if sorted(tags(P[i])) != sorted(tags(C[i])):
                p(f'  ~ {i} tags: {tags(P[i])} → {tags(C[i])}')

    print('\n'.join(out))
    if a.fixes:
        json.dump(fixes, open(a.fixes, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    sys.exit(main())
