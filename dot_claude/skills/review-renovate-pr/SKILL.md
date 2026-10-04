---
name: review-renovate-pr
description: Assess whether a Renovate dependency-bump PR is safe to merge — what actually changed between the pinned and target version, what it breaks in our code, and whether a security claim is real. Use whenever asked to review, assess, or judge the mergeability of a dependency update, a Renovate/Dependabot PR, a `fix(deps)`/`chore(deps)` PR, or a version bump, including "can we merge N" and "is this safe". Report findings in chat and name which outcome the PR belongs to; never merge, migrate, close, or post to GitHub yourself.
---

# Review a Renovate PR

Most dependency bumps are fine and deserve minutes, not hours. The job is to spend effort in proportion to risk, and to be honest at the end about what the upgrade actually buys.

## The three outcomes

Every Renovate PR ends in one of three places. Work the questions in this order and stop at the first one that answers `yes` — the order matters, because it is also the order of increasing cost.

1. **Is this a trivial change?** → **Merge.** Patch or minor inside a stable major, a surface we barely touch, green CI, nothing interesting in the changelog. Most PRs end here and should not consume more than a few minutes. Note that "trivial" is about the migration, not the version number: a major of a small stable library like `nodemailer` is usually still trivial.
2. **If it is not trivial, do the CVEs actually apply to us?** → **Migrate.** Our pinned version is in the vulnerable range *and* the vulnerable code path is reachable from how we use the package. This is the case that earns real time: read the upstream changes, diff the shipped package, fix our call sites, test it.
3. **Non-trivial with no CVE that applies to us** → **the user's call, not yours.** Do not default to closing. Present the trade-off (below) with a recommendation and let the user decide between migrating now and deferring.

The rest of this skill is how to answer those three questions honestly.

**You never carry out the outcome.** Do not merge, do not close, do not push migration commits, do not post reviews or comments to GitHub. Name the outcome, give the reasoning, and let the user act.

### Question 3 — the deferral trade-off

With no CVE forcing the issue, the upgrade buys currency, and whether that is worth the hours depends on two things you should report explicitly:

- **Migration effort** — how many of our call sites move, and how mechanical the change is. A rename across three files is not the same as a config format we have to relearn.
- **Ecosystem stability** — how fast the package churns. A build tool or framework in an active major cycle will bump again next month, so the work recurs and deferring costs little; `vite` and `svelte` are the local examples, and deferring them is usually right. A mature library with a slow release cadence is the opposite: the bump is a one-off, and putting it off just makes the eventual jump bigger.

Weigh those two and say which way you would go, but the decision stays with the user. Closing the PR is one legitimate outcome here — it tells Renovate to stop reopening it — and so is leaving it open to revisit. Say which you mean.

## Question 1 — is this trivial?

Answer these before reading any changelog. Most PRs exit here as a merge.

```bash
gh pr view <N> --json title,state,mergeable,mergeStateStatus,files,statusCheckRollup
gh pr diff <N> -- package.json            # the declared range
```

1. **What version are we actually going to?** The PR body is unreliable — Renovate's table shows the advisory's minimum patched version, which is often not what it wrote. Read the `package.json` range *and* the resolved version in the lockfile. They differ more often than you would expect.
2. **How big is the jump?** Patch/minor within a stable major is usually a skim. A major is where the work is.
3. **How much of our code touches it?** `grep -rn "<pkg>" packages --include=*.ts --include=*.svelte | grep -v node_modules`. Two files is a different review from forty.
4. **Does CI pass?** A red type-check usually names the breaking change for you — read the log before guessing.

It is **not** trivial — go to question 2 — for: any major bump, anything in the render/parse path for user-supplied files, anything with a security claim, or anything where CI is red.

## Question 2 — does the CVE actually apply to us?

Renovate opens vulnerability PRs based on the declared *range*, not the pinned version, so "security" in the title does not mean we are exposed.

```bash
gh api /advisories/<GHSA-id> -q '.vulnerabilities[] | {range: .vulnerable_version_range, patched: .first_patched_version}'
```

Two separate questions, both must hold for the answer to be yes:

- **Is the pinned version in the vulnerable range?** Often it predates the vulnerability entirely.
- **Is the vulnerable code path reachable from our usage?** Check whether the risky option is part of the API we call or only of a viewer/bundled UI we never instantiate. Grep the shipped build for the option name and see which entry point it belongs to.

If neither holds, say so plainly rather than repeating the CVE framing — that is a close, not a migration.

Separately, check whether `renovate.json` enables `lockFileMaintenance`. If it does, the declared range matters as much as today's pin, because a monthly re-resolve moves within it. That is an argument about advisory alerts and audit noise, not necessarily about exploitability — keep the two distinct, and do not let it silently promote a close into a migration.

## Doing the work when the answer is migrate

Only once question 2 came back yes is the rest of this worth the hours.

### What changed upstream

List the releases between our pinned version and the target, then read them:

```bash
gh api repos/<owner>/<repo>/releases --paginate -q '.[] | "\(.tag_name)\t\(.published_at)"'
gh api repos/<owner>/<repo>/releases/tags/<tag> -q '.body'
```

Grep the bodies for `api-major`, `api-minor`, `breaking`, `removed`, `renamed`. Then check each hit against the surface we actually use — most will be irrelevant, and saying so explicitly is part of the review.

**Do not trust the severity label.** Maintainers categorise by API-shape change, not by blast radius. A line marked `[api-minor]` can silently make a runtime asset required. If a changelog entry mentions decoders, codecs, wasm, fonts, workers, or "replace X with Y", treat it as suspect regardless of its label.

### Diff the shipped package, not just the changelog

For anything that ships more than JavaScript — wasm, fonts, native binaries, workers, CMaps, ICC profiles — compare the actual tarballs. This catches what changelogs omit:

```bash
npm pack <pkg>@<old> && npm pack <pkg>@<new>   # or curl the registry tarball
# then diff the directory listings, and package.json engines / optionalDependencies
```

A file that appears in the new version and not the old one is usually a new required asset, which usually means a new configuration option we do not set. The runtime symptom is a fetch for a path with the literal string `null`, `undefined` or `[object Object]` in it — the library concatenated an unset option into a URL.

Also compare `engines` (does CI's Node still satisfy it?) and any change to minimum browser versions, which nothing in the build will catch if there is no browserslist config.

### Prove it at runtime when static review cannot

For parsers, renderers, codecs and anything handling untrusted user files, reading the diff is not enough — the failure mode is a blank page, not an exception. Get fixture files from the upstream project's own regression corpus (`test/` in its repo), which are the exact cases the maintainers test, and drive them through our real UI path.

**Compare against the deployed environment, not just against expectations.** Running the same fixtures on production and on the branch is the only cheap way to tell a regression this PR introduced from a bug that was already there. Both are worth reporting, and conflating them wastes everyone's time.

## Reporting

Report in chat. Do not post a review or comment to GitHub unless asked.

**Lead with which of the three outcomes this PR belongs to — merge, migrate, or a deferral decision — and the one reason it lands there.** Then: what breaks and where (`file:line`), what changed but does not affect us, what is pre-existing rather than caused by this PR, and what still needs testing.

For outcomes 1 and 2 the answer is a recommendation the user carries out: say what acting on it involves — the merge button, or the migration work and roughly what it costs.

For outcome 3 the report exists to let the user decide. Give both axes concretely — the call sites that move and how mechanical the change is, and the package's release cadence and whether another major is already in flight — then your recommendation and what each path costs. Do not collapse it into a single verdict, and do not present two options as equal when they are not.

Include an honest answer to "what does this buy us". If the security rationale did not survive question 2 and the upgrade mostly buys currency, say exactly that rather than repeating the CVE framing. A bump whose main value is avoiding a larger bump later is a legitimate but different argument, and the reviewer deserves to judge it as what it is.
