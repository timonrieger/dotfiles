---
name: video-note-highlight
description: Extract key insights from a video note .md file and append them as highlights to a CSV file. Use this skill whenever the user points to a video note file and wants to add it to the highlights CSV, or says things like "add this to highlights", "create highlights for this video", "highlight this video note", or simply shares a video .md filename. Also use when the user asks to process a video note they've been taking notes on. The file is in the Obsidian vault at ~/Library/Mobile Documents/iCloud~md~obsidian/Documents/personal/.
---

# Video Note → Highlights CSV

Turn a single video note markdown file into highlights and append them to `video-highlights.csv` in the project folder.

## Step 1: Read the file

Load the .md file the user pointed to. If only a title was given (no path), look in:
`~/Library/Mobile Documents/iCloud~md~obsidian/Documents/personal/<title>.md`

## Step 2: Extract metadata from YAML frontmatter

- **title**: the filename without `.md`
- **author**: the `channel` field — strip `[[` and `]]` (e.g. `[[{ungeskriptet} by Ben]]` → `{ungeskriptet} by Ben`). If missing, use `"YouTube Video"`.
- **url**: extract from frontmatter — use as the URL column value
- **date**: use the `watched` date if available, otherwise leave empty

## Step 3: Distill highlights

From the Key Takeaways and Notes sections, pick the 1–3 insights worth revisiting months later. A good highlight:
- Stands alone without needing the video for context (self-contained)
- Captures a concrete idea, fact, or actionable point — not a vague reaction
- Is paraphrased or merged if multiple notes say the same thing

**Language:** Write highlights in the same language as the notes in the file. If the notes are in German, write the highlights in German. Do not translate.

Skip highlights that are purely subjective ("great talk!") or too incomplete to be useful.

If the file has no meaningful content (empty notes), say so and stop.

## Step 4: Show highlights and ask for confirmation

Present the highlights you've selected, then ask: "Soll ich diese Highlights zur CSV hinzufügen?"

Only proceed to Step 5 after the user confirms.

## Step 5: Append to CSV

The CSV file is at:
`~/Library/Mobile Documents/iCloud~md~obsidian/Documents/personal/video-highlights.csv`

**CSV format** — one row per highlight, columns in this exact order:
```
Highlight,Title,Author,URL,Note,Location,Date
```

- **Highlight**: the highlight text
- **Title**: the video title (filename without `.md`)
- **Author**: channel name (stripped of `[[` `]]`)
- **URL**: the YouTube URL from frontmatter, or empty
- **Note**: leave empty
- **Location**: leave empty
- **Date**: ISO 8601 timestamp from the `watched` field in frontmatter, or empty

If the file doesn't exist yet, create it with the header row first.

If it exists, append rows only — never overwrite the file or modify existing rows.

All fields must be quoted. Use Python to append safely:

```python
import csv, os
path = os.path.expanduser("~/Library/Mobile Documents/iCloud~md~obsidian/Documents/personal/video-highlights.csv")
file_exists = os.path.exists(path)
with open(path, 'a', newline='', encoding='utf-8') as f:
    writer = csv.writer(f, quoting=csv.QUOTE_ALL)
    if not file_exists:
        writer.writerow(['Highlight', 'Title', 'Author', 'URL', 'Note', 'Location', 'Date'])
    for highlight in highlights:
        writer.writerow([highlight, title, author, url, '', '', date])
```

## Step 6: Confirm

Report back: video title, author, number of highlights appended, and the highlight texts.
