---
name: shared-tree-commit
description: Load before you stage, commit, push or undo edits in a git checkout where another agent session also works, when its edits sit in a file you changed, when its commits sit unpushed on the branch, or when it committed work of yours. Gives the git recipes that commit only the hunks of this session and never rewrite a file the other session is editing.
compatibility: Designed for Claude Code and pi. Needs git, and uv for the Python steps.
---

# Commit in a shared working tree

The user runs agent sessions in parallel in one checkout. A second session may commit, stage or rewrite a file while this one works. Each recipe below commits, pushes or undoes the work of this session alone.

## Rules for every case

- Read `HEAD` again before you stage. Do not trust an earlier `git status`.
- Take the list of your paths from what this session wrote, never from `git status`: it lists the other session's files too.
- Never run `git commit -a`. A plain `git commit` also takes the files the other session staged. Commit with `git commit -- <your paths>`, which leaves its index as it was.
- Ask the user before you commit or push the work of the other session with yours.

## Interleaved edits in one file

`git commit -- <path>` takes that path from the working tree, the other session's hunks included. Stage a blob in its place:

1. Build the content you mean outside the tree. Reconstruct "HEAD plus mine": invert its edits where they are mechanically identifiable.
2. Prove the result: diff it against `HEAD` for text you never touched.
3. Stage it as a blob: `git hash-object -w`, then `git update-index --cacheinfo 100644,<sha>,<path>`. This never rewrites a file the other session is still writing.
4. Commit with a plain `git commit` once `git diff --cached --name-only` lists only your paths.

## Edits built on its uncommitted work

1. Ask the user.
2. Commit its work first, rebuilt without your hunks. A rebuilt file is proven when its `git hash-object` matches the blob on the `index` line of a `git diff` taken before your first edit.
3. Commit yours on top.

For each commit, run a plain `git commit` once `git diff --cached --name-only` lists only that path. `git commit -- <path>` takes that path from the working tree, the other session's hunks included.

## Derived artifacts

To regenerate a derived artifact from that reconstruction, export `git archive HEAD` to a scratch directory and run the generator under `uv run --project <scratch>`. A swap of files in the shared tree races the other session.

## After your commit

The other session's pending copy of a file you both edit still lacks your line, so its next commit of that file reverts it. Once yours is in, add your lines to its working copy with an exact-match edit.

## Unpushed commits of the other session

To push your work while its commits sit unpushed on the branch:

1. Build your commit on `origin/<branch>` with a temporary index: `GIT_INDEX_FILE=<scratch> git read-tree origin/<branch>`, then `update-index` and `write-tree`.
2. Create the commit with `git commit-tree -S`. Without `-S`, `commit-tree` ignores `commit.gpgsign` and writes an unsigned commit.
3. Push `<sha>:refs/heads/<branch>`.

When your work builds on those commits, ask the user before you push them with it.

Work not written yet is simpler in a `git worktree add --detach` at `origin/<branch>`: run `uv sync --frozen --all-groups` there, commit, and push `HEAD:refs/heads/<branch>`.

Keep a file meant only for such a commit outside the tree: an untracked copy of a path the remote now tracks blocks the other session's next pull.

## Commit authorized, push not authorized

Still end with the commit on local `<branch>`, never on a side branch. Fast-forward with `git merge --ff-only`, or move the ref:

1. Run `git update-ref refs/heads/<branch> <new> <old>`.
2. Run `git reset --quiet -- <your paths>`. A full reset drops what the other session staged.

When it staged a hunk in one of your paths, skip the reset for that path: point its entry at the blob of the new commit plus that hunk, with `git update-index --cacheinfo`.

## Work that another session committed

A session can also commit work it did not write. An uncommitted strand in this checkout is a strand offered to whoever commits next. Commit promptly, or rebuild yours as a blob once the absorption shows.

## Undo and compare

- To undo your own edits, reverse your hunks. `git checkout -- {path}` also drops the other session's edits to that file.
- A pi session's edits survive as `edit` calls in its `~/.pi/agent/sessions/` transcript, to replay.
- Never `git stash` to compare an older commit. The push removes your paths from the tree the other session reads. A `git status` after the pop can show its commit instead of your pop, which reads as lost work. Add a throwaway `git worktree` at the SHA, and run the tool with `uv run --project <worktree>`: your tree never changes.
