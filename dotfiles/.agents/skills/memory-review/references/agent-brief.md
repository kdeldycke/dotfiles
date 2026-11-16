# Brief of a review agent

Fill the placeholders in braces, then pass the text as the prompt of one `general-purpose` agent per batch. Start every agent of a pass in the same turn. Give each a name like `mem-b01`, so a reply reaches it.

`{batch file list}` is the list the `batches` subcommand wrote, one absolute path per line. `{project context}` names the repository or folder the memories describe, where its rules live (its `AGENTS.md` or `CLAUDE.md`, its docs), and what the agent cannot test there: a virtual machine, a device, a live service. `{date of today}` is the date. `{incident sentence}` is one sentence on the stale memory that started this review, when one did.

---

You review persistent memory files of Claude Code: one batch of a parallel review. Nobody else touches your files.

Your batch: the files listed in {batch file list}, one absolute path per line. Read the list first, then each file.

Batch context: {project context}. The other batches of the same project sit in the same directory: you may read them to detect duplicates, but edit only your own files.

What a memory is: one file holding one fact, with a YAML frontmatter (`name`, `description`, `metadata.type` = user | feedback | project | reference). The body is the fact; a feedback or project memory adds **Why:** and **How to apply:** lines. A memory must not hold what the repository already records (code, docstrings, docs, `AGENTS.md` or `CLAUDE.md`, git history) or what mattered to one conversation only. Memories are point-in-time, and many are stale. Today is {date of today}. {incident sentence}

For each file, verify every claim against the current state, then give one verdict:

- KEEP: still true, still useful, recorded nowhere else.
- UPDATE: partly stale or bloated. Apply the fix yourself with the Edit tool, or Write for a full rewrite: correct the stale fact, cut the narrative down to the rule and its fix, keep exact error strings, write absolute dates. Keep `name` unchanged. Update `description` when the content changed.
- DELETE: wrong; resolved with no lasting lesson (a merged pull request, a passed deadline, a finished follow-up); a workaround for something a tool now does; or recorded elsewhere in full (name the file and the line). Do not delete it yourself: report it.
- MERGE: a duplicate of another file of your batch. Write the merged text into the file with more inbound `[[links]]` and report the other one as DELETE. For a duplicate outside your batch, give KEEP and name the other file in the reason.

How to verify, read-only:

- Code and docs: the repository at its current HEAD (`git -C {repo} log`, `rg`, Read). Check that each named file, function, flag, configuration key and version still exists and behaves as described.
- Rules already recorded: the global instruction file at `~/.claude/CLAUDE.md` and the files it includes, the repository's `AGENTS.md` or `CLAUDE.md`, the skills under `~/.claude/skills/` and under the repository. A memory that restates one of them is DELETE, with the file and line named, unless it holds a detail they lack: then UPDATE it down to that detail.
- Tool features: a memory describing a hand-made workaround for something a tool now does is DELETE, or UPDATE to point at the feature. Read the `--help` of the tool and its sources.
- Upstream issues and pull requests: `gh api 'repos/{owner}/{repo}/issues/{n}' --jq '.state, .state_reason, .pull_request.merged_at'`, GET only. A memory waiting on something already merged or closed is stale. For another forge, read what a plain GET returns, and flag UNSURE otherwise.
- A deadline or "until" date before today means the follow-up is due or done: find out which.
- When you cannot settle a claim, keep the file and flag it UNSURE with the reason. Never guess, and never invent a fact.

Hard rules:

- Never edit any `MEMORY.md`: report the new index line instead.
- Never write, commit, push or post anything outside the memory files of your batch. No `gh` writes, no git writes, no installs, no SSH, no access to a device or a virtual machine.
- The Bash sandbox blocks writes under `~/.claude/projects/`: use the Edit and Write tools for memory edits. The commands `rm`, `cd`, `curl`, `chmod` and `sudo` are denied: never use them.
- Quote zsh globs and any `gh api` path that holds a `?`. Never use `$()` substitutions.
- Write memory text in plain English: short sentences, active voice, ":" instead of em dashes, "like" instead of "e.g.", they/them for a person whose pronouns you do not know, no filler words ("crucial", "robust", "leverage", "load-bearing", "seamless").

Report delivery: the harness refuses a report file from you, and it cuts a long final message. So send the report with the SendMessage tool, to `main`, in parts of at most 3000 characters each, in this order:

1. The verdict table: file name | verdict | one-line reason with its evidence (path:line, command or URL). One row per file of the batch.
2. UNSURE flags: each claim you could not settle, and why.
3. Index lines: for each UPDATE or MERGE whose meaning changed, the new `MEMORY.md` line, in the form `- [Title](file.md) — hook`, under 150 characters, with the folder it goes to when your batch spans several.
4. Findings outside the memories: a repository bug, a dated docs page, a rule file that contradicts the code. Report them; change nothing there.

Your final message is then the single word "sent". Keep the whole report under 1500 words.
