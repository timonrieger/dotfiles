---
name: readwise-book-notes
description: Maintain one book's highlights in Readwise via the MCP. Use after a Kindle/Readwise import ("import is in"): fix duplicates, broken .c1/.c2 concatenations, "merge with previous/next" notes, colour tags. Also for tidying, merging, splitting or checking a book's highlights against its text, and for writing practice notes, summaries or annotations on highlights. Use when a folder has a `*-handoff.md` naming a book_id, even if the user only says "next techniques".
---

# Readwise book notes

The user highlights on Kindle and imports into Readwise, which feeds their notes app. The import is lossy and Kindle is bad for notes, so you do the rest in Readwise: clean up the import, carry out merge requests, write notes. Edits in Readwise stick, because later imports add new copies instead of overwriting.

This skill works inside one book. A book's author or title, duplicate books, and moving highlights between books belong to readwise-library-cleanup.

## Book handoff

Read the book's `<book>-handoff.md` first. It holds the book-specific details:
- `book_id`
- path to the book text and `--start-line`
- chapter-heading prefix
- note format and numbering rules
- accepted exceptions
- status

For a new book, create the handoff from `assets/handoff-template.md`. Ask only for what you can't find yourself (the note format, where the book text is). Find the `book_id` with `readwise_search_highlights` on `document_title`.

## Readwise MCP

- **Setup.** If the `mcp__readwise__*` tools are missing: `claude mcp add --transport http readwise https://mcp2.readwise.io/mcp`. Then the user runs `/mcp` → readwise → Authenticate (OAuth, so only they can do it).
- **Listing.** `readwise_list_highlights` with `book_id`, `page_size: 1000` and a small `response_fields`. A whole book gets saved to a file: pass that path to the scripts or `jq`, and don't read it into context.
- **Editing.** `readwise_update_highlight` takes `text`, `note`, `add_tags` and `remove_tags`. `readwise_delete_highlight` has no undo.
  - Run independent edits in parallel, about 20–25 per message.
  - Check each returned highlight; don't assume the edit worked.

## After an import

1. **Audit.** It's read-only. Its sections match the steps below, and `fixes.json` holds the deduplicated merge texts:
   ```bash
   python3 -I <skill>/scripts/audit.py <listing.json> --book <book.md> --start-line <N> \
     --prev <snapshots/latest.json> --accept-cross <ids from handoff> --fixes <scratch>/fixes.json
   ```
2. **Exact duplicates.** Keep the copy with a note or extra tags, otherwise the newest. First move across anything only the other copy has (the audit marks these `!`). Confirmed duplicates are routine: delete them, then report.
3. **Broken concatenations.** Readwise's `.c1`/`.c2` merging fails in three ways:
   - (a) It repeats the later parts inside the merged highlight. Write the text from `fixes.json` onto it.
   - (b) It leaves the short `.c1` copy behind as its own highlight. Delete it once its text opens the long one.
   - (c) It attaches one chain's parts to a different chain. The audit can't tell this from an intended merge, so ask about anything flagged as spanning chapters. Some cross-chapter merges are deliberate (e.g. a Q&A answer joined to the previous chapter's technique). Add approved ones to the handoff's accepted list.

   To split a wrong merge: trim the host to its own parts, put the other parts where their chain really starts (in book order), and delete any standalone highlight that is now contained in a merged one.
4. **Merge instructions** are Kindle notes like "merge with previous/next", or older `.cN` tags.
   - Join the texts in book order with ` ... ` and put the result on the earliest highlight.
   - Move across real notes and tags, delete the other highlights, and remove the instruction note.
   - If it's unclear which highlight is meant (several candidates, or a gap in the text), ask.
5. **Variant pairs** are a highlight that starts another one, without being a merge. Show both as `https://readwise.io/open/<id>` links; the user chooses.
6. **Colour tags** like `Amarillo` just repeat the `color` field. Remove them if the handoff says so.
7. **Other Kindle notes** are the user's own annotations. Leave them alone, even if they're off-format.
8. **Report** briefly: what you fixed, what needs a decision (with links), and which items now need notes. Put deletions on one line; the user still wants to know.
9. **Snapshot** the state after your edits. Refresh it whenever notes change later, so it never lags behind Readwise:
   ```bash
   python3 -I <skill>/scripts/snapshot.py <fresh-listing.json> <book-folder>/snapshots --book-id <id>
   ```

## Writing notes

- **Work from the book text,** not from memory. Read each item's section and the chapter introduction, which often gives the source text or the instructions.
- **Follow the handoff's format exactly.** Unless the user says otherwise, each note stands alone, with no "same as X": review apps show notes one at a time, so a cross-reference points nowhere.
- **Draft first,** each note in its own code block. Write them with `readwise_update_highlight` only after the user approves, unless they've said "write directly".
- **Readwise holds the current text.** Read the current note before changing it, and never restore an older version from the handoff or the chat. When asked for a fix, change only that.

## Handoff upkeep

When done, update the handoff's status: reading progress, which items have notes, what's next, newly accepted exceptions. Keep workflow details out of it; they live here.
