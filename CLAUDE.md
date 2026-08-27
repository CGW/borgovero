# Borgo Vero — project instructions

**Read `docs/SOT.md` first.** It is the authority on scope, architecture,
current state and open questions. Do not re-derive or re-explain what it
already covers.

## Handing over commands

**Always give git operations as a copy-pasteable bash block**, never as
prose describing what to run. Same for any other shell work — assume it is
going to be pasted straight into a terminal.

- Start from the repo root: `cd ~/borgovero`
- Real commit messages, not placeholders
- Multi-line messages in a single quoted heredoc-style block, as written
- Say plainly what the commit will and will not include, especially where
  `.gitignore` silently drops something that matters

**The remote is `origin`, a private GitHub repo created with `gh`.** Push
with plain `git push`. If a push ever fails with *"No configured push
destination"*, the remote is missing — recreate it rather than committing
and moving on:

```bash
cd ~/borgovero
gh repo create borgovero --private --source=. --remote=origin --push
```

Never run `git add --dry-run` against this repo from the sandbox — the mount
cannot clean up `.git/index.lock` afterwards and it blocks the next commit.
If a commit fails on a stale lock, `rm -f .git/index.lock` first.

A `git commit` that reports *"nothing to commit, working tree clean"* right
after a successful one is a duplicate run, not a failure. Check `git log`
before re-staging anything.

## Session hygiene

Write or update `docs/SOT.md` **before** the session runs out of room, not
after. S001 ended mid-run without a wrap and the missing SOT cost the first
half of S002.

Every session ends with: SOT updated in place (drift fixes plus one
changelog row), then the git block above.

## What is precious and what is disposable

Gitignored and regenerable in under a minute: `cache/`, `*.sqlite`,
`phase0_results.csv`. A missing database is not lost work.

**`phase0/data/id_anchors.json` is the exception.** It is gitignored, lives
only on this machine, and represents hours of Wayback harvesting that cannot
be reconstructed if access to the archive changes. Flag it whenever backups
or commits come up — a clean `git push` does **not** back it up.

## Standing cautions

- Numbers from placeholder OMI bands are provisional. Say so every time one
  is quoted.
- Publish both surface bases (net and commerciale) or neither. Picking one
  silently is the failure mode the project exists to expose.
- DOM figures below the earliest ID anchor are bounds, not estimates —
  bucketable, never rankable.
