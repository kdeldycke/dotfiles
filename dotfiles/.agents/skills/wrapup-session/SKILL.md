---
name: wrapup-session
description: Close out a coding session. List what is left to do, then persist any lesson worth keeping into agent instructions, skills, memory, or code comments. Use when the user ends a session, asks to wrap up, or runs /bye.
argument-hint: '[focus]'
---

# Session wrap-up

This is the last turn of the session: the harness may quit as soon as it settles. Do not ask questions. State assumptions and finish. When arguments are passed, treat them as the focus of the pass.

## 1. Repeat invocation

Check the conversation for a closing report from an earlier invocation of this skill: the labelled to-do list (`Commit:` …, `Push:` …) is its signature. If one is there, this is a repeat call, and the session must end clean this time instead of deferring again.

On a repeat call, do not re-list the leftovers. Finish them:

- Execute every remaining item in the working tree: apply the deferred fix, write the code or the docs entry, draft the upstream report, delete the scratch files, run the verifications. Re-verify each item first, per § 2: work finished by hand since the last report is done, not to do.
- The repeat invocation is the user's go-ahead to commit: stage and commit the finished work locally, one commit per strand, following the commit-message rules. A first invocation never commits; a repeat one does.
- Pushing to a remote and posting to an external service still need the user's own hand. If only such items remain, say the tree is clean and name them.
- Then run the lessons pass (§ 3) and close with the same two lists (§ 4), near-empty by design.

## 2. Loose ends

Collect what this session leaves behind:

- Promises made in the conversation but not delivered: deferred fixes, "later" items, questions parked with a workaround.
- Working-tree changes this session created or touched, still uncommitted. Check `git status` and name only what this session produced. Never push or post anywhere; committing is reserved for the repeat invocation (§ 1).
- Background jobs or processes started here and still running.

**Verify every candidate against the current state before listing it.** The user often fixes, commits, or cleans items by hand between the last prompt and this wrap-up, and a stale item tells them to redo work already done. For each candidate, re-check the evidence: re-run `git status` and `git log` rather than trusting an earlier snapshot, read the file a fix would touch, check whether a deferred report or upstream comment already exists. Drop every item that is already resolved. When an item is only partially done, list only the remainder.

## 3. Lessons worth persisting

A candidate lesson is a correction the user gave, a surprise that cost time, or a rule stated nowhere. Skip anything the code, git history, or existing docs already record.

Route each keeper to its one home:

- A cross-project habit or correction: the global agent instructions file (the `CLAUDE.md` or `AGENTS.md` loaded from the home directory). Resolve symlinks and edit the target file inside its repository, never through the `$HOME` path: a replace-then-rename write forks the symlink.
- A rule specific to this project: the project's own `CLAUDE.md` or `AGENTS.md`.
- A repeatable procedure: a new or updated skill. This wrap-up skill is itself a valid target: an improvement here compounds across every later session.
- A fact about this machine or the user: persistent memory, when the harness provides one.
- A decision tied to one spot in the code: a comment or docstring at that spot.
- A rule a machine can check: propose a test or lint. Mechanical enforcement beats prose.

Guards:

- An empty result is the normal outcome. Most sessions teach nothing new: report "nothing to persist" and never invent a lesson to fill the section.
- Read the target file first and dedupe: update an existing rule in place instead of appending a near-duplicate.
- Apply small, safe edits directly, in the working tree only. Anything larger becomes a one-line proposal, reported as a `Review:` item in the closing report (§ 4).

## 4. Closing report

End with two short lists, a few words per item: **Done** first, then **Left to do**. Write "none" where a list is empty. Keep the whole report under about 15 lines.

**Done** holds what this session finished: lessons persisted and where, plus any tree work completed this turn. A lesson deliberately capped at a suggestion is not done: it moves to **Left to do** as a `Review:` item instead, so every decision the user owes lives in one list. A lesson examined and skipped because the code, history, or docs already record it appears here as one line: `Skipped: …`, naming where it already lives. The report is exactly these two lists and nothing else.

**Left to do** holds every remaining action. Order it so it can be executed top to bottom: create-and-fix work first, then documentation, then `Commit:`, then `Push:`/`Report:`. Name each item's target in full: the path, the SHA, the checkout, the upstream project. Prefix each item with an action label naming the verb it needs, so the list is scannable at a glance. Pick the narrowest label that fits:

- `Commit:` — uncommitted changes to stage and commit in this repository.
- `Push:` — commits already made but not on the remote.
- `Implement:` — new code or a feature to write, in this repo or a sibling checkout (name the checkout).
- `Report:` — an issue or comment to file upstream (name the project).
- `Review:` — something the user must read or decide on: a draft awaiting approval, a proposal from the lessons pass.

These five are the whole vocabulary: do not coin new labels. An item that fits none of them is a plain bullet whose first word is the verb, e.g. "Fix the …", "Clean /private/tmp/…".
