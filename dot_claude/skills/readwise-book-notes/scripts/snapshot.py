#!/usr/bin/env python3
"""Save a Readwise highlight listing as a dated snapshot.

Usage: snapshot.py MCP_OUTPUT.json SNAPSHOT_DIR --book-id ID [--date YYYY-MM-DD]

MCP_OUTPUT.json is the `readwise_list_highlights` result (the tool saves large results
to a file and prints its path). Writes SNAPSHOT_DIR/<date>.json, sorted by location,
and prints a one-line summary. Compare snapshots with audit.py --prev.
"""
import argparse, datetime, json, os

ap = argparse.ArgumentParser()
ap.add_argument('src')
ap.add_argument('outdir')
ap.add_argument('--book-id', type=int, required=True)
ap.add_argument('--date', default=datetime.date.today().isoformat())
a = ap.parse_args()

d = json.load(open(a.src, encoding='utf-8'))
hs = sorted(d.get('results') or d.get('highlights') or [], key=lambda h: (h.get('location') or 0, h['id']))
os.makedirs(a.outdir, exist_ok=True)
path = os.path.join(a.outdir, f'{a.date}.json')
json.dump({'book_id': a.book_id, 'taken_at': a.date, 'count': len(hs), 'highlights': hs},
          open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
notes = sum(1 for h in hs if h.get('note'))
print(f'{path}: {len(hs)} highlights, {notes} with notes')
