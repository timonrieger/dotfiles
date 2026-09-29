---
name: prune-comments
description: Prune the comments a branch added against a target ref (main, a commit, a tag) and report which ones are critical. Keeps only comments that carry what the code cannot say — a why, an invariant, a gotcha, a pointer — removes the ones that narrate or restate the code, never touches directives or generated comments, and reports both lists with reasons. Use this whenever someone asks to clean up, thin out, prune, review or de-noise the comments on a branch, PR or diff, says the code is over-commented or "reads like a tutorial", wants to know which comments are worth keeping, or is tidying AI-written changes before review — even if they do not say "comment" but talk about "docstrings", "JSDoc", "explanations in the code" or "the chatter".
---

# Prune comments

A branch, especially one written with an assistant, tends to arrive with far more comments
than it needs: every helper introduced by a sentence, every branch of an `if` narrated, every
decision explained twice. Most of that is noise a reader has to wade through to find the two
comments that matter. This skill removes the noise and keeps the comments that prevent a future
bug or carry understanding the code itself cannot, then reports both so the author can check
the calls.

Only comments the branch added are in scope. Comments that predate the branch belong to
someone else's judgement; leave them alone even when they are bad.

## Workflow

### 1. Establish the target and the boundaries

The target is whatever the user names: a branch, a commit, a tag. If they name none, use the
repository's main branch (`main`, else `master`, else ask). Confirm it resolves with
`git rev-parse`; in a fresh clone the branch often exists only as `origin/<name>`, so fall back
to that before asking.

Read the project's `CLAUDE.md` or `AGENTS.md` (and any comment-style rule they point at) before
judging anything: a project may require doc comments on exports, forbid them, or have a house
style for section markers. Its rules outrank the defaults below.

Find generated comments and exclude their files. A common case is a translation sync that
writes the source-language text as a comment above every key; deleting those breaks the
tooling. Anything a tool writes or reads is off limits. Pass such paths as `--exclude` globs.

### 2. List what the branch added

```bash
WORK=$(mktemp -d)
python3 <skill-dir>/scripts/added_comments.py <target> --exclude '<generated glob>' --summary > $WORK/comments.json
```

Use a fresh temp directory rather than a fixed path: two prunes running side by side on one
machine would otherwise overwrite each other's lists.

The script diffs the working tree against the merge base with the target (so committed and
uncommitted work both count; `--committed-only` restricts to commits), keeps the added lines,
groups the ones that are comments into blocks, and prints them as JSON with three lines of
code on either side. Each block says whether it is `inline` (trails code), `partial` (continues
into lines the branch did not add) or a `directive` (something a tool reads). Read the script's
docstring for the field list.

### 3. Judge every block next to its code

Read `references/classification.md` for the two tests and worked examples, then go through
the JSON. Judge from the code, not from the comment. The default is **remove**. A comment
survives only by passing one of two tests:

1. **Underivable.** It states something a competent reader cannot get from the code and the
   code it touches, however long they look: a customer's decision, an incident, a platform
   quirk that leaves no trace in the source, a pointer to a record outside the code.
2. **Revert protection.** Without it, a reasonable engineer would make a natural-looking
   change that reintroduces a bug: reorder two statements, drop an odd-looking guard, replace
   a deliberately strange value with the obvious one, "simplify" a workaround away.

"Useful", "well written", "documents the contract" and "explains the design" are not tests.
If the design is visible in the shape of the code, the comment describing it is a second copy
that will drift. If the contract is in the types or in a one-screen body, the doc comment is
a restatement. Prose that a reader would nod along to and then not need is exactly what this
skill removes.

Decide one of:

- **keep** — passes a test as it stands.
- **shorten** — one sentence passes a test, the rest is narration around it. Keep that
  sentence, drop the rest.
- **remove** — everything else, including doc comments on exports that only say what the
  signature and body already say.

Never remove a `directive` block, and never remove a `partial` block by line range; for a
partial block, edit the added lines by hand if they are noise.

When in doubt, remove. The cost of a missing comment that would have passed a test is a
future bug, so name that bug: if you cannot say which change a reader would make and what it
would break, the comment does not pass, and doubt is not a reason to keep it.

### 4. Apply

Write the blocks to remove to a JSON file (the same objects, filtered) and run:

```bash
python3 <skill-dir>/scripts/remove_comments.py $WORK/remove.json --cwd <repo>
```

It deletes bottom-up so line numbers stay valid, cuts inline comments off their code line, and
refuses partial blocks. Do the shortenings by hand with the file editor. Then run the project's
formatter on the touched files if it has one, and its typecheck or lint if that is cheap: a
removed comment can leave an empty line a formatter wants gone, and a `@ts-expect-error` you
misjudged shows up here.

Re-run `added_comments.py` and confirm the remaining blocks are exactly the kept ones.

### 5. Report

Use this shape. The user reads the report to check your calls, so every kept comment needs the
concrete reason it is critical, and every removed one needs the category it fell into. Quote
the comment text, not a paraphrase, and reference locations as `path:line` so they are
clickable.

```
# Comment pruning: <branch> against <target>

<one line: N blocks found in M files; K kept, R removed, S shortened; excluded: <globs>>

## Kept — critical
For each: `path:line` — "<comment text>" — which test it passes: what cannot be derived, or
which change it stops and what that change would break.

## Shortened
For each: `path:line` — what was cut, what stayed.

## Removed
Grouped by category (narration, restatement, change description, obvious contract …),
one line each: `path:line` — "<comment text>".

## Left alone
Directives, generated comments, partial blocks — with the reason.
```

End with one sentence on anything that looked like a bug rather than a comment problem (a
comment contradicting its code is the usual find), because the user will want to know.
