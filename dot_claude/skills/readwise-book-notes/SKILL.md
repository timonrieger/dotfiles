---
name: readwise-book-notes
description: Maintain one book's highlights in Readwise through the Readwise MCP. Clean up after a Kindle import (duplicates, broken `.c1/.c2` concatenations, "merge with previous" notes, colour tags), check highlights against the book's full text, and write or edit notes on highlights without going back through Kindle. Use whenever the user says a Readwise or Kindle import is in, asks to tidy, merge, split or check their highlights for a book, or wants practice notes, summaries or annotations added to highlights. Also use when a folder holds a `*-handoff.md` that names a Readwise book_id, even if the user only says "next techniques" or "import is in".
---

# Readwise book notes

The user reads on Kindle, highlights, and imports into Readwise. Readwise then feeds their notes app. Kindle is a poor place to write notes and Readwise's import is lossy. So the user just highlights, and you do the rest in Readwise:
- clean up what each import breaks
- carry out merge requests
- write the notes the user wants on highlights

Edits made in Readwise stick, because later imports add new copies instead of overwriting old ones.

## Book handoff

Every book has a handoff file in its working folder, usually `<book>-handoff.md`. Read it first. It holds everything specific to that book:
- Readwise `book_id`
- path to the book text
- `--start-line` (where the body starts, after the contents)
- chapter-heading prefix
- note format and numbering rules
- accepted exceptions, such as merges approved to span chapters
- status and open threads

This skill covers the workflow that stays the same from book to book.

For a new book, create the handoff from `assets/handoff-template.md`. Ask the user only for what you can't find yourself: the note format they want, and where the book text lives. Search Readwise to get the `book_id`. Keep the handoff short and book-specific; the general workflow lives here.

## Readwise MCP

- The official server is `https://mcp2.readwise.io/mcp`. If tools named `mcp__readwise__*` are missing, add it with `claude mcp add --transport http readwise https://mcp2.readwise.io/mcp`, then have the user run `/mcp`, choose **readwise** and then **Authenticate**. The sign-in is OAuth, so only the user can complete it.
- **Listing:** use `readwise_list_highlights` with `book_id` and `page_size: 1000`.
  - A whole book is too big to return inline, so the tool saves the result to a file and prints its path. Hand that path to the scripts below, or to `jq`; don't read the file into context.
  - Pass `response_fields` to make the result smaller.
- **Editing:** `readwise_update_highlight` takes `text`, `note`, `add_tags` and `remove_tags`. `readwise_delete_highlight` deletes, and there is no undo.
  - Independent edits can run as parallel calls, about 20–25 per message.
  - Every update returns the updated highlight. Check it, don't assume it worked.
- `readwise_search_highlights` with a `document_title` full-text query is the quickest way to find an unknown book's `book_id`.

## After an import ("import is in")

1. **List** the book's highlights. Run the audit against the book text and the latest snapshot:
   ```bash
   python3 -I <skill>/scripts/audit.py <listing.json> --book <book.md> --start-line <N> \
     --prev <snapshots/latest.json> --accept-cross <ids from handoff> --fixes <scratch>/fixes.json
   ```
   It only reads; it never writes to Readwise. The report's sections line up with the steps below. `fixes.json` contains the deduplicated merge texts, ready to paste.

2. **Exact duplicates.** Re-imports add a fresh copy of highlights that already exist.
   - Keep the copy that has a note or extra tags, otherwise the newest one.
   - Before deleting, move across anything only the other copy has (a `favorite` tag, a note). The audit lists these with `!`.
   - Deleting duplicates the audit has confirmed is routine cleanup. Do it, then report.

3. **Broken concatenations.** Readwise's `.c1`/`.c2` merging tends to go wrong in three ways:
   - (a) it repeats the later parts several times inside the merged highlight
   - (b) it leaves the short `.c1` copy as a separate highlight
   - (c) it attaches one chain's parts to a different chain

   Fix (a) by writing the deduplicated text (from `fixes.json`) onto the long highlight. Fix (b) by deleting the short copy once its text is the first part of the long one; its `.c1` note is no longer needed.

   The audit cannot tell (c) from a merge the user meant, so ask about anything flagged as spanning chapters. Some cross-chapter merges are deliberate. One example: a Q&A chapter answers a question about the previous chapter's technique, and the user wants the answer joined to it. Once the user approves one, add its ID to the handoff's accepted list.

   To split a wrong merge: trim the host to its own parts. Then put the other parts into the highlight where that chain really starts, in book order. Delete any standalone highlight whose text is now part of a merged one.

4. **Merge instructions.** The user writes plain notes in Kindle, like "merge with previous" or "merge with next" (or older `.cN` tags).
   - Build the merged text in book order, joined with ` ... ` (the separator Readwise uses).
   - Put it on the earliest highlight. Move across any real notes or tags from the others, then delete them.
   - Remove the instruction note, since it has done its job.
   - If "previous" or "next" is unclear (several candidates, or a gap in the book text between them), ask.

5. **Variant pairs** are a highlight that is the start of another one, with neither being a merge. Show both with `https://readwise.io/open/<id>` links and let the user choose. Whether a longer capture is intended is their call.

6. **Colour tags.** Kindle colours turn into tags like `Amarillo` that just repeat the `color` field. Remove them when the handoff says to.

7. **Notes the user wrote in Kindle that aren't merge instructions** are their own annotations, such as section summaries. Leave them alone, even if they don't match the note format.

8. **Report** briefly: what was fixed, what needs a decision (with links), and which new items now need notes. List what was deleted in one line. A careful user who keeps backups still wants to know.

9. **Snapshot** the clean state, so the next import can be compared against it:
   ```bash
   python3 -I <skill>/scripts/snapshot.py <fresh-listing.json> <book-folder>/snapshots --book-id <id>
   ```
   Take the listing *after* your edits. Refresh the snapshot whenever notes change later in the session, so it never lags behind Readwise.

## Writing notes on highlights

- **Work from the book text.** Draft from the passage in the book file, not from memory. Read the section for each item, plus the chapter introduction, which often quotes the source text or gives the instructions.
- **Use the handoff's format exactly**: prefix, length, what goes first, what to leave out. Unless the user has said otherwise, each note stands on its own, with no "same as X". Notes get read one at a time in review apps, so a cross-reference points nowhere.
- **Draft first, then write.** Show each draft in its own code block so the user can change any one of them. When they approve ("write them"), set each `note` with `readwise_update_highlight`. If they've said "write directly", skip the draft round.
- **Readwise holds the current text.** The user edits notes there, so read the current note before changing it. Never restore an older version from the handoff or the chat.
- When the user asks for format fixes or rewording, change only that and keep the rest of the note as it was.

## Keeping the handoff current

Once the work is done, update the handoff's status: how far the user has read, which items have notes, what's next, and any newly accepted exceptions. Leave out workflow details; those belong in this skill.
