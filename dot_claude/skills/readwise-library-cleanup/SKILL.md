---
name: readwise-library-cleanup
description: Library-wide Readwise metadata cleanup so the Obsidian export stays clean and each person has one `[[Author]]` note. Covers split or messy authors (newsletters, "Last, First", translators, domains, person-run channels), broken titles, duplicate books (`-2` files), deleting leftover books, and stale `[[old name]]` vault links. Works through the Readwise MCP and the dashboard in the browser. Use for any Readwise library or author/title cleanup, or when author links in Obsidian are split. For highlights and notes inside one book, use readwise-book-notes.
---

# Readwise library cleanup

Readwise exports one file per source into the vault's `highlights/` folder (`~/Library/Mobile Documents/iCloud~md~obsidian/Documents/personal/`). Each file has `author: "[[…]]"` in its frontmatter and is named after the title. So:
- two spellings of one person become two notes
- a broken title becomes a broken filename
- two books for one source become two files

Ground rules:
- **Readwise is the source of truth.** Fix things there; don't hand-edit export files.
- **Only touch sources that have highlights.** Highlight-less Reader documents stay as they are (a rename of those was reverted once).
- **Propose first.** Change nothing until the user agrees.

## 1. Survey

Run `scripts/scan_authors.sh [highlights_dir]`. It prints TSV columns: author, source, file, first Reader highlight id. `source` decides the tool: `reader` goes through the MCP (step 3); everything else (kindle, manual/CSV, pdf, clippings_html, twitter, podcasts) goes through the dashboard (step 4).

Look for:
- **Authors:** the same person spelled differently, translators appended, domains, handles, channels.
- **Titles:** truncated, typo'd, junk like `-2.Auflage`, author inside the title. Check the stored title through `/api/books/` (step 4) first: filenames strip `:` and `/`, so "3-2-1On…" may be fine in Readwise.
- **Duplicates:** `-2.md` files, or two files with the same URL or video id.

The user's naming conventions are in `refs/*.md` (`grep -h -A2 '^author'`). Pairs are joined with "und"; "Timothy Ferriss" is the preferred form.

## 2. Propose

Group the suggestions and ask open choices in one go:
1. Same person, different spellings. These split links, so fix them first.
2. Translators: drop them ("Bronnie Ware und Wibke Kuhn" → "Bronnie Ware").
3. Channels, domains, newsletters and handles stay as they are unless a clear public person is behind them. Then use the person: {ungeskriptet} by Ben → Ben Berndt, elvis → Elvis Saravia, meltingasphalt.com → Kevin Simler. Already decided to leave alone: sysls, Psyphos, FAIR TALK.
4. Titles to fix.
5. Duplicates to merge, and which book to keep.
6. Real co-authors: leave them, and list them.

Verify a name against the source before proposing it. A PDF assumed to be by Gerd Kommer was really by Andreas Beck; check with `reader_search_documents` or the book text.

## 3. Reader sources (MCP)

The highlight id in an export file isn't the document id. Resolve it with `reader_list_documents(id=<highlight id>, response_fields=["parent_id"])`. Without a highlight id, use `reader_search_documents` with `title_search`, and check title and author match.

Rename with `reader_bulk_edit_document_metadata` (`author` / `title`): up to 50 per call, and check every success flag. Readwise picks the change up within about a minute. Verify through `/api/books/`; the highlight search index lags. Don't use `reader_export_documents` to find ids; on this 12k-document library it takes many minutes.

## 4. Dashboard sources (browser)

Use Claude in Chrome (the user runs it in Brave) on `https://readwise.io/library`, calling the dashboard's own API from the page with `javascript_tool`. It runs on the user's login, so use it only after they've OK'd API use in this session; until then the classifier blocks it, rightly. `assets/dashboard_rename.js` does bulk author/title renames.

| action | request |
|---|---|
| list | `GET /api/books/?category=all` → `id`, `title`, `author`, `num_highlights`, `book_type` |
| one book | `GET /api/v2/books/<id>/` (adds `source`, `source_url`) |
| rename | `PATCH /api/v2/books/<id>/` with JSON `{"author_override"…}` or `{"title_override"…}` |
| delete | `POST /api/user_delete_book`, form-encoded `userBookId=<id>&isPermanent=true` |

- Writes need the headers `X-CSRFToken` (from the `csrftoken` cookie) and `X-Requested-With: XMLHttpRequest`. PATCH also needs JSON `Content-Type` and `Accept`.
- Plain `{"author": …}` returns 200 and changes nothing, so always read the book back. `DELETE /api/v2/books/<id>/` returns 405.
- Deleting is permanent and blocks re-importing that title/author/source. Get the user's explicit OK, and re-check `num_highlights` right before.
- Print only status codes, ids and the fields you need. Output containing cookies or request logs gets blocked.
- Unknown endpoint: wrap `fetch` and `XMLHttpRequest` to record method, path and body keys, then do the action once in the UI. The JS bundles can't be fetched (CDN).

**Fallback: the edit form.** Everything tab → search the title → row chevron → Edit Metadata → cmd+a in the field, type → zoom to check the title → Change ("Saved your metadata").
- Search matches loosely, so check the dialog's title.
- Click the search box only when the page is scrolled to the top; a missed click sends your typing to the page as shortcuts.
- Empty books don't show in the library; delete them through the API.

**Duplicate books:** read `references/merging.md` before merging. Matching rules are strict, and wrong guesses create empty books.

## 5. Verify and report

1. Re-list `/api/books/?category=all`. No old author or title may remain among books with highlights.
2. Grep the vault for stale links (this includes the video notes' `channel:` field and `refs/` person notes). Use a pattern file of `[[Old Name]]` and `[[Old Name|` lines, and don't open the notes:
   ```bash
   grep -rnoF --include='*.md' -f old_names.txt "$VAULT" | grep -v '/\.obsidian/'
   ```
   Also look for person notes filed under an old name (`find -name`). Fix links (`sed` on the matched line) or rename notes (`mv -n`) only with the user's OK.
3. Report: what changed and where (MCP, API or form), what you left alone and why, and anything deleted.

Existing export files aren't reliably rewritten, and renamed titles create new files next to the old ones. To apply everything, the user deletes `highlights/` and lets Readwise re-export it. Tell them; don't delete it yourself.
