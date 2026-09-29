#!/usr/bin/env python3
"""
Delete comment blocks by file and line range, as listed by added_comments.py.

Reads a JSON array of objects with at least `file`, `start`, `end` and `inline` (the shape
added_comments.py prints; extra keys are ignored) and removes those comments from the working
tree. Whole-line blocks are deleted outright. An inline comment is cut off its code line, which
keeps the code. Blocks marked `partial` are refused, because part of that comment predates the
branch and deleting by line range would eat text nobody asked to remove.

Deletions are applied bottom-up within each file, so the line numbers of the input stay valid
throughout. The input must describe the files as they are now; do not run it twice on the same
list.

Usage:
    remove_comments.py <blocks.json> [--dry-run] [--cwd DIR]
"""
import argparse
import json
import re
import sys
from pathlib import Path

INLINE_MARKERS = re.compile(r'\s+(//|/\*|#|--|<!--)')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('blocks', help='JSON file with the blocks to remove')
    ap.add_argument('--dry-run', action='store_true', help='report what would change, touch nothing')
    ap.add_argument('--cwd', default='.', help='repository root the paths are relative to')
    args = ap.parse_args()
    blocks = json.load(open(args.blocks, encoding='utf-8'))
    root = Path(args.cwd)

    by_file = {}
    for b in blocks:
        if b.get('partial'):
            print(f"refused (partial): {b['file']}:{b['start']}-{b['end']}", file=sys.stderr)
            continue
        by_file.setdefault(b['file'], []).append(b)

    removed = 0
    for path, items in by_file.items():
        full = root / path
        lines = full.read_text(encoding='utf-8').split('\n')
        for b in sorted(items, key=lambda x: (x['start'], x['end']), reverse=True):
            start, end = b['start'], b['end']
            if start < 1 or end > len(lines) or start > end:
                print(f"skipped (out of range): {path}:{start}-{end}", file=sys.stderr)
                continue
            if b.get('inline'):
                line = lines[start - 1]
                m = INLINE_MARKERS.search(line)
                if not m:
                    print(f"skipped (no inline comment found): {path}:{start}", file=sys.stderr)
                    continue
                lines[start - 1] = line[: m.start()].rstrip()
            else:
                del lines[start - 1: end]
                # A line left blank between two blank lines is a hole the comment used to fill.
                if (start - 2 >= 0 and start - 1 < len(lines)
                        and lines[start - 2].strip() == '' and lines[start - 1].strip() == ''):
                    del lines[start - 1]
            removed += 1
            print(f"{'would remove' if args.dry_run else 'removed'}: {path}:{start}-{end}", file=sys.stderr)
        if not args.dry_run:
            full.write_text('\n'.join(lines), encoding='utf-8')
    print(f"{removed} block(s) {'would be ' if args.dry_run else ''}removed in {len(by_file)} file(s)", file=sys.stderr)


if __name__ == '__main__':
    main()
