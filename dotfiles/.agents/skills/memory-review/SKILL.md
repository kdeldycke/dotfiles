---
name: memory-review
description: Review, prune and repair the persistent memory of Claude Code (~/.claude/projects/*/memory). Verify every memory against the code, the docs, the skills and the upstream state, fix or delete the stale ones, merge duplicates, and keep each MEMORY.md index in step with its folder. Use when a memory misled a session, when memories look stale or bloated, when asked to clean up, prune, audit or consolidate memories, or every few months.
compatibility: 'Designed for Claude Code. Recommended model: Opus for the lead and the review agents, Sonnet for the fix-up agent.'
allowed-tools: Bash Read Grep Glob Edit Write Agent SendMessage
argument-hint: '[project directory | all] [--no-agents]'
---

# Memory review

Claude Code keeps one memory per fact under `~/.claude/projects/{project}/memory/`, with a `MEMORY.md` index per project that loads into every session of that project. A memory is a point-in-time observation, and nothing tests it: the code moves, the follow-up ships, the tool gains the feature the memory worked around. A stale memory then steers a session wrong with full confidence. One described a hand-written CI watcher, and a later session rebuilt it, while `repomatic ci-status --wait` already did the job.

This skill verifies every memory against the current state, fixes or removes the stale ones, merges duplicates, and leaves each index in step with its folder. The mechanics live in `scripts/memory_review.py`, a uv standalone script, and the brief of a review agent in `references/agent-brief.md`. Read the brief when step 3 starts, not before.

## Scope

`$ARGUMENTS` names the scope: a project directory, for its memory folder alone, or `all`, for every memory folder, which is the default. With `--no-agents` the lead reviews inline, which fits a scope under about 40 files.

The instruction files, skills and docstrings are out of scope: they are the subject of the `agent-config-self-tune` skill, when it is installed. The two meet at one verdict. A memory that restates one of those files is deleted, and a memory that is a procedure becomes a skill, or a `references/` file of one.

## Verdicts

Every memory gets one verdict, with the evidence the report must carry: a path and line, a command, or a URL.

| Verdict | Test                                            | Action                                                                   |
| :------ | :---------------------------------------------- | :----------------------------------------------------------------------- |
| KEEP    | Still true, still useful, recorded nowhere else | None                                                                     |
| UPDATE  | Partly stale, or bloated with narrative         | Edit in place: correct the fact, cut the story, keep exact error strings |
| DELETE  | One of the four tests below                     | Report it; the lead moves it to the Trash                                |
| MERGE   | A duplicate of another memory                   | Write the merged text into the survivor; report the other one as DELETE  |

A memory is deleted when:

- another file states it: the global instruction file, the project's `AGENTS.md` or `CLAUDE.md`, a skill, a docstring, a docs page. Name the file and the line;
- its follow-up is over: the pull request merged, the issue closed, the deadline passed, the release shipped. Name the commit, the state or the version;
- a tool now does what it worked around. Name the flag or the subcommand;
- it is wrong, and a reading of the current code or a probe shows it.

The survivor of a merge is the file with more inbound `[[links]]`. A claim nobody can test keeps its file and gets an UNSURE flag in the report: a virtual machine, a live service, anything that needs a write or an install, a forge behind a bot wall.

## Procedure

1. Inventory. Run `uv run --script {skill}/scripts/memory_review.py inventory`. It prints one row per memory folder: file count, size, and the mechanical issues (an index line with no file, a file with no index line, a missing frontmatter). Fix those first with the Edit tool: they are cheap, and they confuse the agents.
2. Batches. Run `... batches {scratch}/memreview --size 45`. It writes one file list per batch: one project per batch where it fits, a large project split, the small projects pooled. Each batch is one agent's property, and no two batches share a file.
3. Review agents. Start one agent per batch, all in the same turn, with the brief from `references/agent-brief.md` filled in. The agents edit UPDATE and MERGE files in place, delete nothing, never touch a `MEMORY.md`, and report each DELETE with its evidence. They send the report with SendMessage to `main`, in parts of at most 3000 characters, and end on a one-line final message: see § Traps.
4. Collect. As each report arrives, write `{scratch}/memreview/apply-{batch}.json` with its deletions and its new index lines, in the schema the script's docstring gives. Write it on arrival: a report read later is a report forgotten. A verdict whose evidence names no file, line, command or URL goes back to its agent. Keep the UNSURE flags and the findings outside the memories in the same file, for the final report.
5. Apply. Run `... apply {scratch}/memreview` for the plan, then with `--apply`. The script moves the deleted files to the Trash, backs each index up under `{scratch}/memreview/backup/`, drops the index lines of the deleted files and replaces the lines of the updated ones. It refuses to apply while any reference fails to resolve. The Trash step needs the sandbox off.
6. Fix-up. Run `... check`. It lists the `[[links]]` that resolve to no memory, the lines that call someone "he", and the empty folders. Hand the first two lists to one agent on Sonnet, with a table that maps each dead link to its new home: the merge survivor, or the home the DELETE evidence named. Run `check` again when it returns.
7. Report. Give the counts (reviewed, kept, updated, deleted), where the Trash and the index backups are, the UNSURE flags grouped by file, and the findings outside the memories as a list the user decides on: an edit to the global instruction file, a bug in a repository, a dated docs page, a memory folder that no session loads any more. Act on none of them without a word from the user.

## Verification sources

- The repository at its current HEAD: `git log`, `rg`, Read. Each file, function, flag, configuration key and version a memory names must still exist and behave as described.
- The rules recorded elsewhere: the global instruction file, the project's `AGENTS.md` or `CLAUDE.md`, the skills of the user and of the repository.
- The tools: `--help` of the CLI the memory works around, and its changelog since the memory's date.
- The upstream state: `gh api 'repos/{owner}/{repo}/issues/{n}' --jq '.state, .state_reason, .pull_request.merged_at'`, GET only. A non-GitHub forge gets a plain GET, or an UNSURE flag.
- A deadline or an "until" date before today: the follow-up is due or done, and the agent finds out which.

## Traps

- The harness refuses a report file from a subagent, with `Subagents should return findings as text, not write report files`, and it cuts a long final message at about 5000 characters with `[result truncated — ask the agent for the rest via SendMessage]` (Claude Code `2.1.284`). Put the delivery rule in the brief: without it, every agent needs a second round, and the second round arrives as duplicates of the first.
- The Bash sandbox denies writes under `~/.claude/projects/`. The agents edit with the Edit and Write tools, and the lead runs the Trash step with the sandbox off.
- A `[[link]]` resolves by the `name` of a frontmatter, not by the file name, and the two spellings differ: underscores in the file, hyphens in the name. The `check` subcommand resolves both.
- Memories about the user accumulate "he" and "his". The rule is they/them, or the name or the role. The fix-up agent rewrites every match of `\b(he|him|his|himself)\b` outside a verbatim quote, index hooks included.
- A memory folder follows the working directory of the session that wrote it. A folder renamed or moved on disk leaves its memories orphaned, and a memory written from a parent folder never loads in a child. Report such a folder; moving memories between folders is the user's call.
- The agents may read the sibling batches of their project to find duplicates, but they edit their own files only. A duplicate across batches is reported as KEEP with the other file named, and the lead decides.
- The index hook of an updated memory is rewritten when its meaning changed, under 150 characters. The script replaces a line by its file name, so the agent reports the whole line.
- The lessons of the review go into this skill, not into a new memory.
- Expect about a third of the files deleted and half of the rest updated on a folder a few months old: the first full pass went from 490 files to 325, with 237 rewritten. The ratio is not a target: a verdict needs its evidence.
