---
name: readwise-video-highlights
description: Turn a video note .md from the Obsidian vault into 1–3 distilled highlights and append them to `video-highlights.csv` for import into Readwise. Use when the user shares or wants to process a (YouTube) video note or filename, says "add this to highlights", "create highlights for this video" or "highlight this video", or asks how to get video highlights into Readwise.
---

# Video note → Readwise highlights (CSV)

Vault: `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/personal/`. You append highlights to `video-highlights.csv` there. The user imports the CSV into Readwise (a "manual" source, category Podcasts), which exports one file per video, with `author: "[[…]]"`.

## 0. One route per video

The alternative route is Reader: the user saves the YouTube link and highlights the synced transcript, getting verbatim quotes with timestamps. Using both routes for one video creates two books and two files. So first check Reader: `reader_search_documents` with `url_search` set to the video id. If the video is there, ask which route the user wants.

## 1. Read the note

Use the path given, or `<vault>/<title>.md`.

## 2. Metadata (from frontmatter)

- **Title:** the filename without `.md`.
- **Author:** the `channel` value without `[[ ]]`; `"YouTube Video"` if missing.
  - Use the person's canonical Readwise name: a person-run channel gets the person's name ({ungeskriptet} by Ben → Ben Berndt), other channels keep the channel name.
  - The note's `channel:` link should carry the same name, so both files link to one person note.
- **URL:** from frontmatter.
- **Date:** the `watched` value as an ISO 8601 timestamp, or empty.

**The video is already in Readwise** (check `readwise_search_highlights` or the `highlights/` export): Readwise files new highlights by the *original import's* title, author and URL, not by the name the dashboard shows. The CSV isn't kept after importing, so take those values from what was imported:
- title: the note's filename at the time
- author: the channel name at the time, possibly an older spelling such as `{ungeskriptet} by Ben`

Anything different creates a second book; tell the user. If the import resets a renamed author, re-apply it with readwise-library-cleanup.

## 3. Distill

From Key Takeaways and Notes, pick the 1–3 insights worth revisiting months later. Each one should:
- stand on its own, without the video
- be concrete (an idea, a fact, an action), not a reaction like "great talk"
- merge or paraphrase notes that say the same thing

Write in the notes' language; don't translate. If the note has no real content, say so and stop.

## 4. Confirm

Show the highlights and ask "Soll ich diese Highlights zur CSV hinzufügen?". Continue only on yes.

## 5. Append

Columns: `Highlight,Title,Author,URL,Note,Location,Date`. Note and Location stay empty. Quote every field. Create the file with a header row if it doesn't exist. Otherwise only append; never rewrite existing rows.

```python
import csv, os
p = os.path.expanduser("~/Library/Mobile Documents/iCloud~md~obsidian/Documents/personal/video-highlights.csv")
new = not os.path.exists(p)
with open(p, 'a', newline='', encoding='utf-8') as f:
    w = csv.writer(f, quoting=csv.QUOTE_ALL)
    if new: w.writerow(['Highlight', 'Title', 'Author', 'URL', 'Note', 'Location', 'Date'])
    for h in highlights: w.writerow([h, title, author, url, '', '', date])
```

## 6. Report

Video title, author, the number of highlights appended, and their texts.
