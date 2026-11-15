# Merging duplicate books

Two Readwise books for one source (e.g. a Reader copy and a CSV entry of the same video) produce two export files. Keep the book the user names. Copy the other book's highlights into it with `readwise_create_highlights`, then delete the originals with `readwise_delete_highlight`.

**Matching.** A new highlight lands in an existing book only when title, author, `source_url` and `source_type` match that book's *original import*. The overridden values the dashboard shows don't count.
- For CSV imports from readwise-video-highlights, the original values are the CSV row: the video note's filename (e.g. "Wir haben nichts aus der Nazi-Zeit gelernt (Oliver Ruppel)"), the channel name at import time, the URL, and `source_type: manual`.
- PDF uploads don't expose their original title, so you usually can't merge into them. Tell the user and offer to leave both books.

**Test with one highlight.** Check the book `id` in the response.
- If it's a new id, the values didn't match. Delete that highlight and stop guessing: every wrong guess leaves an empty book.

**After merging:**
- Creating highlights resets the book's author and title overrides. Re-apply them.
- Copies get today's `highlighted_at` and lose their link back to the original location (e.g. a video timestamp). Tell the user before you merge.
- Deleting a Reader-sourced highlight in Readwise leaves it in Reader, and it can sync back. The user deletes it in Reader; give them the `https://read.readwise.io/read/<doc id>` link.
- List any empty books left over, including failed test books, and offer to delete them through the API (SKILL.md, step 4).
