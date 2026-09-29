# What makes a comment critical

Two tests. A comment stays if it passes either; everything else goes.

**Underivable.** A competent reader with the code in front of them, and the code it calls,
cannot arrive at what the comment says. Decisions made by people outside the code, incidents,
platform behaviour that leaves no trace in the source, pointers to records.

**Revert protection.** Without the comment, a reasonable engineer would make a natural-looking
change that reintroduces a bug. To apply this test, name the change and name the bug. If you
cannot, the comment fails.

The tests are deliberately narrow. Most comments a branch adds are useful in the sense that
they save the reader a few seconds; that is not enough, because they also cost every future
reader those seconds and they drift the moment the code changes. Only what the code cannot
carry gets to stay.

## Keep

**A decision that came from outside the code.** The code cannot argue with a future reader;
the pointer can. Underivable.

```ts
// Any user may set any Status: the customer's answer was "everyone". See ADR 0002.
```

**An ordering or guard that looks removable.** The change: reorder, or drop the guard. The
bug: the one the comment names. Revert protection.

```ts
// Prune before checking, not after: a client that was over the limit an hour ago must not
// stay blocked once their old hits have aged out of the window.
```

**A value or shape that looks wrong on purpose.** The change: replace it with the obvious
value. The bug: the drift, the quirk, the incident. Revert protection.

```prisma
/// The default is written in the form MySQL reports back, or every migrate shows drift.
kommentarOnkoSek String @default(dbgenerated("(_utf8mb4\\'\\')")) @db.Text
```

**A platform or library behaviour with no trace in the code.** Underivable: nothing in the
source says Firefox behaves this way.

```ts
// Firefox and Safari fire no blur or change when a focused input is removed from the DOM.
```

**A directive.** `eslint-disable`, `@ts-expect-error`, `svelte-ignore`, `noqa`,
`prettier-ignore`, a Prisma `/// [TypeName]` annotation, a shebang, a license header. Tools
read these; the script flags them. Never remove one, even when the prose around it goes.

**A comment a tool generated.** Translation sync source lines, code generators' headers,
"do not edit" banners. Exclude their files up front.

## Remove

**Narration.** The comment tells the story of the next lines.

```ts
// Loop over the rows and build a map from id to row.
```

**Restatement.** The comment repeats the name in words.

```ts
/** Returns the user's full name. */
function fullName(user: User): string
```

**A design that is visible in the shape of the code.** This one catches most of what survives
a first pass. The comment explains an intent that the code already demonstrates by how it is
laid out, so the explanation is a copy.

```ts
// The dashboard and the Vollbild render the same toolbar and list; the props are declared
// once so the two cannot drift.
$: listProps = { ... }
```

One object spread into two places says all of that. Remove.

**A contract the types or a one-screen body already state.** Doc comments on exports are not
exempt: if the signature and the body give the reader the same information in the same
time, the doc comment is a restatement.

```ts
/** Undefined leaves the table unselectable; an empty array means "selectable, none ticked". */
export let selectedIds: readonly string[] | undefined = undefined
$: selectable = selectedIds !== undefined
```

The second line is the contract. Remove.

**A module or class header that summarises what the exports show.** "Pure view model behind
the list; every decision about order and columns lives here." The export list says so.
Remove, unless the header holds a decision that passes a test, in which case shorten to it.

**A description of the change instead of the code.** "Now uses X instead of Y", "moved from
Z". The commit message has it; in the code it is stale on the next change.

**Section banners.** `// ── Helpers ──`, `<!-- Edit dialog -->`. Scaffolding. Remove unless
the project's own files use them as a convention.

**Reassurance and hedging.** "This is safe because …" when the because is on screen; "should
never happen" on a branch that plainly can.

**The why behind a choice that is the obvious choice.** Only a choice that looks wrong needs
its reason recorded. If the alternative would not occur to anyone, the reason is noise.

## Shorten

A block often wraps one sentence that passes a test in several that do not. This:

```ts
// We compute each row's key once up front and then sort by the precomputed keys. This is
// because computing the key inside the comparator would recompute it for every comparison,
// and the text projection of a column can format dates, which is slow. So the map, then the
// sort, then the map back.
```

is one line, and it stays only because someone would plausibly inline the key back into the
comparator to shorten the code:

```ts
// Keys are computed once, not per comparison: a text projection can format dates.
```

## Signs you are about to make the wrong call

- You are keeping a comment because it is well written, or because it "documents the API".
  Neither is a test.
- You have not named the change and the bug for a comment you kept under revert protection.
- You are keeping a module header because it reads like good documentation. Read the
  exports instead and ask what the header adds.
- You have not read the code the comment sits on. Judge nothing from the JSON alone.
- The comment contradicts the code. That is a bug, not a comment problem. Keep it and name it
  in the report.
- The project's own rules require doc comments on exports or forbid something here. The
  project wins; say so in the report.
