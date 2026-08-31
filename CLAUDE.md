# CasaZebra (repo: borgovero) — project instructions

The product was renamed **CasaZebra** (casazebra.it) in S007. The repo,
paths and remote keep the borgovero name deliberately — renaming them
buys nothing and breaks every session note that cites a path.

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

**The remote is `origin` over SSH:** `git@github.com:CGW/borgovero.git`,
a private GitHub repo. SSH keys are set up and working — push with plain
`git push`, never an HTTPS URL. GitHub dropped password auth for git in
2021, so an HTTPS remote prompts for a username and password and then
rejects whatever is typed; if that prompt ever appears, the remote has been
switched to HTTPS and the fix is:

```bash
cd ~/borgovero
git remote set-url origin git@github.com:CGW/borgovero.git
```

Use `set-url`, not `add` — origin already exists, and `add` fails with
*"remote origin already exists"*.

**`gh` is not installed on this machine** (`zsh: command not found: gh`), so
never hand over a `gh repo create` line. Creating a repo is a browser step at
github.com/new — private, and no README, .gitignore or licence, which would
otherwise create a divergent history to reconcile.

Never run `git add --dry-run` against this repo from the sandbox — the mount
cannot clean up `.git/index.lock` afterwards and it blocks the next commit.
If a commit fails on a stale lock, `rm -f .git/index.lock` first.

A `git commit` that reports *"nothing to commit, working tree clean"* right
after a successful one is a duplicate run, not a failure. Check `git log`
before re-staging anything.

## Deploying (recorded S008 — it had never been written down)

Production is the Vercel project **`dist-site`**
(`prj_kzhgio7otE8l2Ec75on36d6bWIrj`, team `cgw-2712s-projects`), served
at casazebra.it. It is **not** git-connected: every deploy is the CLI run
from the built tree, which is why the project is named after the folder.

```bash
cd ~/borgovero/bv-site/dist-site
vercel link --yes --project dist-site
vercel --prod
```

**The `vercel link` line is not optional, and this is the trap:**
`build.py` installs by calling `shutil.rmtree()` on its output directory,
so **every build deletes `dist-site/.vercel`**. A bare `vercel --prod`
then finds no project link and offers to create one — accept the default
and the site deploys to a NEW project that no domain points at, looking
like a successful deploy that changed nothing. Re-linking explicitly
costs a second and removes the guess.

Deploy AFTER `build.py` reports both gates (twice byte-identical, lint
clean) — it installs nothing if either fails, so a failed build leaves
the previous tree in place and `vercel --prod` would silently redeploy
the OLD site.

## Session hygiene

Write or update `docs/SOT.md` **before** the session runs out of room, not
after. S001 ended mid-run without a wrap and the missing SOT cost the first
half of S002.

Every session ends with: SOT updated in place (drift fixes plus one
changelog row), then the git block above.

## What is precious and what is disposable

Gitignored and regenerable in under a minute: `cache/`, `*.sqlite`,
`phase0_results.csv`. A missing database is not lost work.

**`phase0/data/id_anchors.json` is the exception, and it IS tracked.**
It represents hours of Wayback harvesting that cannot be reconstructed if
access to the archive changes, so `.gitignore` ignores `**/data/*` and then
un-ignores this one file with `!**/data/id_anchors.json`. It is committed
(`dda2cab`), in HEAD, and pushed — verify with `git ls-files | grep anchor`
rather than assuming either way.

This paragraph used to say the opposite: gitignored, on this machine only,
not backed up by a push. That was stale for months, and it was repeated as a
standing warning at the end of session after session without anyone running
the one command that checks it. **A caution that is never re-tested becomes
folklore.** The second Wayback harvest nobody needed to do was the cheap
outcome; the expensive version is a claim about the data itself surviving the
same way. `phase0/verified_clusters.json` is the other human-measured,
non-regenerable file — same reasoning, and it is tracked too.

## Standing cautions

- Numbers from placeholder OMI bands are provisional. Say so every time one
  is quoted.
- Publish both surface bases (net and commerciale) or neither. Picking one
  silently is the failure mode the project exists to expose.
- DOM figures below the earliest ID anchor are bounds, not estimates —
  bucketable, never rankable.
