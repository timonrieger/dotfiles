#!/usr/bin/env bash
# List every Readwise export file in the Obsidian highlights folder as TSV:
#   author <TAB> source <TAB> file <TAB> first read.readwise.io highlight id (Reader sources only)
# Usage: scan_authors.sh [highlights_dir]   (default: the personal vault's highlights/)
set -euo pipefail
dir="${1:-$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/personal/highlights}"
cd "$dir"
for f in ./*.md; do
  author=$(grep -m1 '^author:' "$f" | sed 's/^author: *"\[\[//; s/\]\]" *$//')
  source=$(grep -m1 '^source:' "$f" | sed 's/^source: *//')
  hl=$(grep -m1 -o 'read\.readwise\.io/read/[a-z0-9]*' "$f" | sed 's#.*/##' || true)
  printf '%s\t%s\t%s\t%s\n' "$author" "$source" "${f#./}" "$hl"
done | sort -f
