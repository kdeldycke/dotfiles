---
name: session-wrapup
description: Close out a coding session. List what is left to do, then persist any lesson worth keeping into agent instructions, skills, memory, or code comments. Use when the user ends a session, asks to wrap up, or runs /bye.
argument-hint: "[focus]"
---

# Session wrap-up

This is the last turn of the session: the harness may quit as soon as it settles. Do not ask questions. State assumptions and finish. When arguments are passed, treat them as the focus of the pass.

## 1. Loose ends

Collect what this session leaves behind:

- Promises made in the conversation but not delivered: deferred fixes, "later" items, questions parked with a workaround.
- Working-tree changes this session created or touched, still uncommitted. Check `git status` and name only what this session produced. Never commit, push, or post anywhere.
- Background jobs or processes started here and still running.

## 2. Lessons worth persisting

A candidate lesson is a correction the user gave, a surprise that cost time, or a rule stated nowhere. Skip anything the code, git history, or existing docs already record.

Route each keeper to its one home:

- A cross-project habit or correction: the global agent instructions file (the `CLAUDE.md` or `AGENTS.md` loaded from the home directory). Resolve symlinks and edit the target file inside its repository, never through the `$HOME` path: a replace-then-rename write forks the symlink.
- A rule specific to this project: the project's own `CLAUDE.md` or `AGENTS.md`.
- A repeatable procedure: a new or updated skill.
- A fact about this machine or the user: persistent memory, when the harness provides one.
- A decision tied to one spot in the code: a comment or docstring at that spot.
- A rule a machine can check: propose a test or lint. Mechanical enforcement beats prose.

Guards:

- An empty result is the normal outcome. Most sessions teach nothing new: report "nothing to persist" and never invent a lesson to fill the section.
- Read the target file first and dedupe: update an existing rule in place instead of appending a near-duplicate.
- Apply small, safe edits directly, in the working tree only. Anything larger becomes a one-line proposal in the report.

## 3. Closing report

End with two short lists, a few words per item: left to do, and persisted or proposed. Write "none" where a list is empty. Keep the whole report under about 15 lines.
