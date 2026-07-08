---
name: repomatic-changelog
description: Draft, validate, consolidate, and fix changelog entries.
model: sonnet
allowed-tools: Bash, Read, Grep, Glob, Edit, Write
argument-hint: '[add|check|fix|consolidate [VERSION]|VERSION]'
---

## Context

!`head -40 changelog.md 2>/dev/null || echo "No changelog.md found"`
!`git log --oneline -10 2>/dev/null`
!`[ -f repomatic/__init__.py ] && echo "CANONICAL_REPO" || echo "DOWNSTREAM"`

## Instructions

You help users manage their `changelog.md` file. Follow `CLAUDE.md` § Changelog and docs updates for style rules.

### Mechanical layer

The `lint.yaml` workflow runs `lint-changelog` in CI. The `check` and `fix` subcommands below invoke the same tool locally. The `add` subcommand is purely analytical — it reviews git history and drafts entries, which no CI job does.

### Determine invocation method

- If the context above shows `CANONICAL_REPO`, use `uv run repomatic`.
- Otherwise, use `uvx -- repomatic`.

### Argument handling

- (default when `$ARGUMENTS` is empty): Run `add` then `consolidate` on the unreleased section, sequentially.
- `add`: Review recent git commits and draft changelog entries. Place entries under the current unreleased section. Describe **what** changed, not **how** or **why**: one sentence per user-facing change (~10-25 words), per `CLAUDE.md` § Changelog entry length. Mechanism, internal names, and rationale go in the commit and PR, not the entry.
- `check`: Run `<cmd> lint-changelog` and report results. Explain each issue found.
- `fix`: Run `<cmd> lint-changelog --fix` and show what was changed.
- `consolidate [VERSION]`: Consolidate redundant entries in a changelog section. This is analytical work with no CLI equivalent — read the entries, compare against `git log` for the relevant range, and rewrite. See § Consolidation rules below. If `VERSION` is omitted, target the unreleased section. If `VERSION` is given (e.g., `consolidate 6.8.0`), target that released section instead — locate it in `changelog.md` by matching the heading, and use the git range between its tag and the previous tag (e.g., `v6.7.0..v6.8.0`).
- A bare version number (e.g., `6.8.0` or `v6.8.0`) is shorthand for `consolidate VERSION`. Strip the `v` prefix if present.

### Consolidation rules

Entries accumulate during development as features are built incrementally. Before release, they need consolidation. The goal is a changelog that reads as a release summary, not a development diary.

01. **Read the target section** and `git log` for its range. For the unreleased section, use `git log` since the last release tag. For a released version like `6.8.0`, use `git log v6.7.0..v6.8.0` (derive the previous tag from the next heading in `changelog.md`).
02. **Reconcile against the end state, not the commit trail.** The changelog records the net diff from the last tag to `HEAD`. `git log` includes work that was later undone or superseded, so verify every entry against the *current* code and docs (open `pyproject.toml`, the source, the docs) instead of trusting commit messages. Collapse a value that a later commit corrected into its final form: an entry bumping a dependency floor to one version, when a subsequent commit moved it higher, should state the higher version. Drop any change introduced and then reverted within the same cycle: a dependency pinned to a branch until a fix ships and unpinned once it did, or a temporary workaround added then deleted. It never reached a release, so it is a no-op for users.
03. **Merge entries that describe the same feature at different stages.** Multiple bullets about adding tools to a registry, then migrating workflows for those tools, then wiring up their version pins — that is one feature ("add unified tool runner with 13 managed tools"), not twelve.
04. **Merge entries that describe infrastructure and its usage together.** "Add binary download infrastructure" + "add 5 binary tools" + "migrate 5 workflow steps" = one bullet covering the feature end-to-end.
05. **Keep distinct user-facing changes as separate entries.** A breaking config key change and a new CLI command are separate features even if they landed in the same development cycle.
06. **Keep the names users need, shed the rest.** Tool names, config keys, CLI options, and breaking-change notes stay explicit. But consolidation cuts per-entry *length*, not just bullet count: a merged entry is one short sentence naming the feature, not a paragraph stacking every mechanism and rationale from the bullets it replaced. Target ~10-25 words (`CLAUDE.md` § Changelog entry length); push implementation detail and "why" to the commit, PR, code comment, or `docs/`.
07. **Remove implementation details** that don't affect users: internal refactors, helper functions, test additions.
    Also strip upstream issue commentary: trailing prose that links to upstream tickets and narrates their status ("Click does not ship an equivalent: the upstream conversation is in `pallets/click#NNNN` (open)…", "mirrors the upstream fix in PR `…#NNNN`"). The status rots within days and the prose duplicates what the linked thread already says. A bare upstream link is acceptable on a direct backport entry; longer rationale belongs in a code comment, docstring, or PR body.
08. **Order entries by category, breaking changes first:** lead with `**Breaking:**` entries, then new features, then broad/global changes, then bug fixes, then documentation and testing. Breaking changes are what a reader scans for before upgrading, so they go at the top of the block.
09. **Apply directly.** Write the consolidated section to `changelog.md` without asking for approval. Summarize what was merged, dropped, or reordered after writing.
10. **Validate after writing.** A bulk rewrite can introduce malformed markup, silently drop structure, or leave entries over-long. Before reporting, confirm: no doubled list markers (a stray `- -`); every rewritten bullet is within `changelog.bullet-word-threshold` (a delegated agent may under-compress, so gate on the measured count, not the agent's self-report); `mdformat` leaves the file unchanged (run it, expect a no-op); and the `## [...]` heading count and availability-admonition count match what they were before the edit. Breaking entries lead each section (rule 8).

### Style rules

Follow `CLAUDE.md` § Changelog and docs updates and § Changelog entry length (one short sentence per change, what-not-how-or-why) and § Version formatting (bare versions in changelog headings, no `v` prefix).

### Next steps

Suggest the user run:

- `/repomatic-ship` to reconcile the tree and drive the release to a ready-to-merge PR.
