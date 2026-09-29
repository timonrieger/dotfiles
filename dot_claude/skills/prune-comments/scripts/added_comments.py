#!/usr/bin/env python3
"""
List the comments a branch added, compared with a target ref.

Reads `git diff` between the merge base of the target and HEAD and the working tree (so
committed and uncommitted work both count), keeps only added lines, and groups the ones that
are comments into blocks. Each block comes with a few lines of the surrounding code, because
whether a comment earns its place can only be judged next to the code it sits on.

Usage:
    added_comments.py <target> [--committed-only] [--exclude GLOB ...] [--summary] [--cwd DIR]

Output: a JSON array on stdout, one object per comment block:
    file            path relative to the repository root
    start, end      1-based line numbers in the current file (inclusive)
    kind            line | doc-line | block | doc | html | hash | dash | docstring
    inline          true when the comment trails code on the same line
    partial         true when the block continues into lines the branch did not add
                    (never delete those blindly; the rest of the comment predates the branch)
    directive       true when the text looks like something a tool reads rather than a person
                    (eslint-disable, @ts-expect-error, noqa, prisma-json annotations, shebangs …)
    text            the comment text, with the comment markers stripped
    before, after   up to three lines of code on either side, for context
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

C_LIKE = {
    '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.mts', '.cts', '.java', '.kt', '.kts', '.go',
    '.rs', '.c', '.h', '.cc', '.cpp', '.hpp', '.cs', '.swift', '.scala', '.dart', '.php',
    '.scss', '.less', '.prisma', '.groovy', '.proto', '.gradle',
}
BLOCK_ONLY = {'.css'}
HASH = {
    '.py', '.rb', '.sh', '.bash', '.zsh', '.yaml', '.yml', '.toml', '.pl', '.r', '.ps1', '.tf',
    '.hcl', '.mk', '.cfg', '.ini', '.env', '.gitignore', '.dockerignore', '.editorconfig',
}
HASH_NAMES = {'Dockerfile', 'Makefile', 'Justfile', 'Rakefile', 'Gemfile'}
DASH = {'.sql', '.lua', '.hs', '.elm'}
HTML = {'.html', '.htm', '.xml', '.svg', '.md', '.mdx'}
TEMPLATE = {'.svelte', '.vue', '.astro'}

DIRECTIVE = re.compile(
    r'(eslint-|@ts-(ignore|expect-error|nocheck|check)|prettier-ignore|svelte-ignore|biome-ignore|'
    r'\bnoqa\b|\btype:\s|pylint:|pyright:|mypy:|flake8:|ruff:|\bnolint\b|#!/|/// ?\[|<reference\s|'
    r'sourceMappingURL|SPDX-|Copyright|c8 ignore|istanbul ignore|v8 ignore|@__PURE__|'
    r'\bfmt:\s*(off|on)\b|clippy::|#\[|@generated|AUTO-GENERATED|DO NOT EDIT|webpack|vite-ignore|'
    r'cspell:|spell-checker:|region\b|endregion\b)',
    re.IGNORECASE,
)


def styles_for(path: str):
    name = os.path.basename(path)
    ext = os.path.splitext(name)[1].lower()
    out = set()
    if ext in C_LIKE or ext in TEMPLATE:
        out |= {'line', 'block'}
    if ext in BLOCK_ONLY:
        out.add('block')
    if ext in HASH or name in HASH_NAMES:
        out.add('hash')
    if ext in DASH:
        out |= {'dash', 'block'}
    if ext in HTML or ext in TEMPLATE:
        out.add('html')
    if ext == '.py':
        out.add('docstring')
    return out


def run_git(args, cwd):
    return subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def added_lines(target: str, cwd: str, committed_only: bool):
    """Map file -> {new line number: text} for every added line in the diff."""
    base = run_git(['merge-base', target, 'HEAD'], cwd).strip()
    diff_args = ['diff', '-U0', '--no-color', '--no-ext-diff']
    diff_args += [f'{base}..HEAD'] if committed_only else [base]
    diff = run_git(diff_args, cwd)
    files, current, new_line = {}, None, 0
    for raw in diff.splitlines():
        if raw.startswith('+++ '):
            path = raw[4:]
            current = None if path == '/dev/null' else path[2:] if path.startswith('b/') else path
            if current is not None:
                files.setdefault(current, {})
        elif raw.startswith('@@'):
            m = re.match(r'@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@', raw)
            new_line = int(m.group(1)) if m else 0
        elif current is not None and raw.startswith('+') and not raw.startswith('+++'):
            files[current][new_line] = raw[1:]
            new_line += 1
    return files


def strip_markers(kind: str, lines):
    out = []
    for text in lines:
        t = text.strip()
        if kind in ('line', 'doc-line'):
            t = re.sub(r'^///?\s?', '', t)
        elif kind in ('block', 'doc'):
            t = re.sub(r'^/\*\*?\s?', '', t)
            t = re.sub(r'\s?\*/\s*$', '', t)
            t = re.sub(r'^\*\s?', '', t)
        elif kind == 'html':
            t = re.sub(r'^<!--\s?', '', t)
            t = re.sub(r'\s?-->\s*$', '', t)
        elif kind == 'hash':
            t = re.sub(r'^#\s?', '', t)
        elif kind == 'dash':
            t = re.sub(r'^--\s?', '', t)
        elif kind == 'docstring':
            t = re.sub(r'^[rRbBuU]?("""|\'\'\')', '', t)
            t = re.sub(r'("""|\'\'\')\s*$', '', t)
        out.append(t)
    return '\n'.join(out).strip()


def trailing_comment(line: str, styles):
    """Return (index, kind) of a comment that trails code on this line, or None."""
    code = line
    # Crude but serviceable: ignore markers inside quotes by blanking string literals first.
    blanked = re.sub(r'(["\'`])(?:\\.|(?!\1).)*\1', lambda m: ' ' * len(m.group(0)), code)
    candidates = []
    if 'line' in styles:
        m = re.search(r'(?<=\S)\s+//(?!/)', blanked)
        if m and not re.search(r'https?:$', blanked[: m.start() + 1]):
            candidates.append((m.start(), 'line'))
    if 'block' in styles:
        m = re.search(r'(?<=\S)\s+/\*.*\*/\s*$', blanked)
        if m:
            candidates.append((m.start(), 'block'))
    if 'hash' in styles:
        m = re.search(r'(?<=\S)\s+#(?!\{)', blanked)
        if m:
            candidates.append((m.start(), 'hash'))
    if 'dash' in styles:
        m = re.search(r'(?<=\S)\s+--\s', blanked)
        if m:
            candidates.append((m.start(), 'dash'))
    if 'html' in styles:
        m = re.search(r'(?<=\S)\s+<!--.*-->\s*$', blanked)
        if m:
            candidates.append((m.start(), 'html'))
    if not candidates:
        return None
    return min(candidates)


def classify_line(stripped: str, styles):
    """Kind of a whole-line comment opener, or None. Returns (kind, closes_on_same_line)."""
    if 'line' in styles and stripped.startswith('//'):
        return ('doc-line' if stripped.startswith('///') else 'line'), True
    if 'block' in styles and stripped.startswith('/*'):
        kind = 'doc' if stripped.startswith('/**') and not stripped.startswith('/**/') else 'block'
        return kind, ('*/' in stripped[2:])
    if 'html' in styles and stripped.startswith('<!--'):
        return 'html', ('-->' in stripped[4:])
    if 'hash' in styles and stripped.startswith('#'):
        return 'hash', True
    if 'dash' in styles and stripped.startswith('--'):
        return 'dash', True
    if 'docstring' in styles and re.match(r'^[rRbBuU]?("""|\'\'\')', stripped):
        q = '"""' if '"""' in stripped[:4] else "'''"
        body = stripped[stripped.index(q) + 3:]
        return 'docstring', (q in body)
    return None, False


def is_continuation(stripped: str, kind: str):
    if kind in ('line', 'doc-line'):
        return stripped.startswith('///') if kind == 'doc-line' else (
            stripped.startswith('//') and not stripped.startswith('///'))
    if kind == 'hash':
        return stripped.startswith('#')
    if kind == 'dash':
        return stripped.startswith('--')
    return False


def closes(stripped: str, kind: str):
    if kind in ('block', 'doc'):
        return '*/' in stripped
    if kind == 'html':
        return '-->' in stripped
    if kind == 'docstring':
        return '"""' in stripped or "'''" in stripped
    return False


def collect(path: str, added: dict, cwd: str):
    styles = styles_for(path)
    if not styles:
        return []
    full = Path(cwd) / path
    if not full.is_file():
        return []
    file_lines = full.read_text(encoding='utf-8', errors='replace').splitlines()
    blocks = []
    n = len(file_lines)
    i = 1
    while i <= n:
        line = file_lines[i - 1]
        stripped = line.strip()
        if i not in added:
            i += 1
            continue
        kind, closed = classify_line(stripped, styles)
        if kind is None:
            tc = trailing_comment(line, styles)
            if tc is not None:
                idx, tkind = tc
                blocks.append(dict(file=path, start=i, end=i, kind=tkind, inline=True, partial=False,
                                   raw=[line[idx:].strip()], text=strip_markers(tkind, [line[idx:]])))
            i += 1
            continue
        start = i
        raw = [line]
        partial = False
        if kind in ('line', 'doc-line', 'hash', 'dash'):
            # A directive line (an annotation a tool reads) is its own block, so that pruning the
            # prose around it can never take the annotation with it.
            j = i + 1
            if not DIRECTIVE.search(stripped):
                while (j <= n and j in added and is_continuation(file_lines[j - 1].strip(), kind)
                       and not DIRECTIVE.search(file_lines[j - 1].strip())):
                    raw.append(file_lines[j - 1])
                    j += 1
            # A run that continues into lines the branch did not add is part of an older comment.
            if j <= n and j not in added and is_continuation(file_lines[j - 1].strip(), kind):
                partial = True
            if start > 1 and (start - 1) not in added and is_continuation(file_lines[start - 2].strip(), kind):
                partial = True
            end = j - 1
        else:
            j = i
            if not closed:
                j = i + 1
                while j <= n and not closes(file_lines[j - 1].strip(), kind):
                    if j not in added:
                        partial = True
                    raw.append(file_lines[j - 1])
                    j += 1
                if j <= n:
                    raw.append(file_lines[j - 1])
                    if j not in added:
                        partial = True
            end = min(j, n)
            # Code after the closing marker on the same line means the comment is not the whole line.
            tail = re.sub(r'.*(\*/|-->|"""|\'\'\')', '', file_lines[end - 1].strip(), count=1)
            if tail.strip():
                partial = True
        blocks.append(dict(file=path, start=start, end=end, kind=kind, inline=False, partial=partial,
                           raw=raw, text=strip_markers(kind, raw)))
        i = end + 1
    for b in blocks:
        b['directive'] = bool(DIRECTIVE.search('\n'.join(b['raw'])))
        b['before'] = file_lines[max(0, b['start'] - 4): b['start'] - 1]
        b['after'] = file_lines[b['end']: b['end'] + 3]
        del b['raw']
    return blocks


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('target', help='branch, tag or commit to compare against')
    ap.add_argument('--committed-only', action='store_true', help='ignore uncommitted changes')
    ap.add_argument('--exclude', action='append', default=[], metavar='GLOB',
                    help='skip files matching this glob (generated files, translations …); repeatable')
    ap.add_argument('--summary', action='store_true', help='print counts per file to stderr')
    ap.add_argument('--cwd', default='.', help='repository directory (default: current)')
    args = ap.parse_args()
    root = run_git(['rev-parse', '--show-toplevel'], args.cwd).strip()
    files = added_lines(args.target, root, args.committed_only)
    from fnmatch import fnmatch
    blocks = []
    for path, added in sorted(files.items()):
        if any(fnmatch(path, g) or fnmatch(os.path.basename(path), g) for g in args.exclude):
            continue
        blocks.extend(collect(path, added, root))
    if args.summary:
        per = {}
        for b in blocks:
            per[b['file']] = per.get(b['file'], 0) + 1
        for f, c in sorted(per.items()):
            print(f'{c:4d}  {f}', file=sys.stderr)
        print(f'{len(blocks)} comment blocks in {len(per)} files', file=sys.stderr)
    json.dump(blocks, sys.stdout, indent=1, ensure_ascii=False)
    print()


if __name__ == '__main__':
    main()
