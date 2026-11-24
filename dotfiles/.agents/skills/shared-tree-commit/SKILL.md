---
name: shared-tree-commit
description: Load before you stage, commit, amend, push or undo edits in a git checkout where another agent session also works, when its edits sit in a file you changed, when its commits sit unpushed on the branch, or when it committed work of yours. Gives the git recipes that commit only the hunks of this session and never rewrite a file the other session is editing.
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

When `git diff` shows your edits and its edits in separate hunks, a filtered patch is shorter. It is the scripted form of `git add --patch`, and it writes the index only:

1. Save `git diff --no-prefix -- <path>` to a file outside the tree.
2. Delete each hunk of the other session from that file. A hunk runs from its `@@` line to the line before the next `@@` line. Keep the header lines above the first hunk.
3. Run `git apply --cached -p0 --check <patch>`, then the same command without `--check`.
4. Prove the result: `git diff --cached -- <path>` shows only your hunks, and `git diff -- <path>` shows only its hunks.
5. Commit with a plain `git commit` once `git diff --cached --name-only` lists only your paths.

Use the blob route when one hunk holds edits of both sessions.

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

## Amend an older unpushed commit

`git rebase` needs a clean tree, and its `--autostash` is the `git stash` that "Undo and compare" forbids. Rebuild the range with plumbing instead, after you check that `git log origin/<branch>..HEAD` lists each of its commits:

1. Take each commit from the target to `HEAD`, oldest first. Read its tree into a temporary index (`GIT_INDEX_FILE=<scratch> git read-tree <sha>`), set the entry of your path to your blob with `git update-index --cacheinfo`, then run `git write-tree`.
2. Create the new commit with `git commit-tree <tree> -p <new parent> -F -`. Give it the old message on standard input, and the old author in `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL` and `GIT_AUTHOR_DATE`.
3. Build the whole range once without `-S`. Check that `git diff --name-only <old head> <new head>` lists only your paths, and that each message and author is unchanged. A check that fails after the signed build wastes one signature for each commit.
4. Build the range again with `-S`, one commit at a time, then move the branch as "Commit authorized, push not authorized" says.

## Push rejected as non-fast-forward

`git pull` refuses the dirty tree for the same reason. Rebuild the unpushed range on `origin/<branch>` as "Amend an older unpushed commit" says, with two changes:

- Take each tree from `git merge-tree --write-tree --merge-base=<old parent> <new parent> <commit>`, which stops on a conflict, and compare each pair with `git patch-id --stable`.
- After the branch moves, point the index entry of each path the remote changed at its new blob with `git update-index --cacheinfo`. Then run `git checkout-index --force -- <path>`, unless the working copy already holds that blob: otherwise the path reads as reverted.

## Work that another session committed

A session can also commit work it did not write. An uncommitted strand in this checkout is a strand offered to whoever commits next. Commit promptly, or rebuild yours as a blob once the absorption shows.

## Undo and compare

- To undo your own edits, reverse your hunks. `git checkout -- {path}` also drops the other session's edits to that file.
- A pi session's edits survive as `edit` calls in its `~/.pi/agent/sessions/` transcript, to replay.
- Never `git stash` to compare an older commit. The push removes your paths from the tree the other session reads. A `git status` after the pop can show its commit instead of your pop, which reads as lost work. Add a throwaway `git worktree` at the SHA, and run the tool with `uv run --project <worktree>`: your tree never changes.
