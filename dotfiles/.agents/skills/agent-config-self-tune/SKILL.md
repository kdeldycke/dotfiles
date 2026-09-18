---
name: agent-config-self-tune
description: Audit and tune coding agent configuration across Claude Code and pi. Browse all global and local settings files (settings.json, settings.local.json) and instruction files (CLAUDE.md, AGENTS.md), audit them for issues, percolate recurring local patterns into the global config, compress verbose instruction files to cut per-session token cost, and review past session transcripts for tool calls denied by the sandbox or allow/deny rules to propose allowlist refinements.
compatibility: 'Designed for Claude Code and pi. Recommended model: Opus.'
allowed-tools: Bash Read Grep Glob Edit Agent
argument-hint: '[~/code or parent directory to scan]'
---

# Audit and consolidate coding agent configuration

Scan all configuration files of the supported harnesses (Claude Code, pi) across projects, audit them for issues, promote recurring local patterns into the global config, and cut the token cost of instruction files.

## Supported harnesses and config layers

Detect which harnesses are present on the machine (`~/.claude` for Claude Code, `~/.pi` for pi) and audit only those. Within each harness, layers load in this order (later wins):

### Claude Code

| Scope                     | File                                    | Purpose                                    |
| ------------------------- | --------------------------------------- | ------------------------------------------ |
| Global user               | `~/.claude/settings.json`               | Permissions, hooks, env vars, plugins      |
| Global user local         | `~/.claude/settings.local.json`         | Machine-specific overrides (not committed) |
| Global instructions       | `~/.claude/CLAUDE.md`                   | User-wide behavioral instructions          |
| Project                   | `<project>/.claude/settings.json`       | Project-level permissions and hooks        |
| Project local             | `<project>/.claude/settings.local.json` | Machine-specific project overrides         |
| Project instructions      | `<project>/CLAUDE.md`                   | Project-level behavioral instructions      |
| Subdirectory instructions | `<project>/<subdir>/CLAUDE.md`          | Scoped instructions for a subtree          |

### pi

| Scope                | Path                                                   | Purpose                                               |
| -------------------- | ------------------------------------------------------ | ----------------------------------------------------- |
| Global user          | `~/.pi/agent/settings.json`                            | Model defaults, tools, compaction, installed packages |
| Project              | `<project>/.pi/settings.json`                          | Project overrides, loaded only for trusted folders    |
| Trust decisions      | `~/.pi/agent/trust.json`                               | Per-folder project-trust record                       |
| Global instructions  | `~/.pi/agent/AGENTS.md`                                | Machine-wide behavioral instructions                  |
| Project instructions | `<project>/AGENTS.md`                                  | Project-level behavioral instructions                 |
| Extensions           | `~/.pi/agent/extensions/`, `<project>/.pi/extensions/` | TypeScript loaded at startup                          |
| Skills               | `~/.pi/agent/skills/`, `<project>/.pi/skills/`         | On-demand capabilities                                |
| Prompt templates     | `~/.pi/agent/prompts/`, `<project>/.pi/prompts/`       | `/name` command templates                             |

### Shared by both

| Path                                             | Purpose                                                                            |
| ------------------------------------------------ | ---------------------------------------------------------------------------------- |
| `~/.agents/skills/`, `<project>/.agents/skills/` | Harness-neutral skill locations (pi reads them; any Agent Skills spec harness may) |
| `<project>/.agents/AGENTS.md`                    | Harness-neutral project instructions                                               |
| `@<path>` imports inside any instruction file    | Include chains that load extra directives                                          |

## Argument handling

`$ARGUMENTS` is an optional parent directory to scan for projects. Defaults to `~/code`.

## Workflow

### Phase 1: Discovery

1. Detect which harnesses are present (`~/.claude`, `~/.pi`). Skip absent harnesses without flagging them.

2. Read the global config files of each present harness:

   - Claude Code: `~/.claude/settings.json`, `~/.claude/settings.local.json`, `~/.claude/CLAUDE.md`.
   - pi: `~/.pi/agent/settings.json`, `~/.pi/agent/trust.json`, `~/.pi/agent/AGENTS.md`, and list `~/.pi/agent/extensions/`, `~/.pi/agent/skills/`, `~/.pi/agent/prompts/`.

3. Find all projects under the scan directory. Use `/usr/bin/find` (not the shell alias) to locate:

   - `*/.claude/settings.json`, `*/.claude/settings.local.json`
   - `*/.pi/settings.json`
   - `*/CLAUDE.md`, `*/AGENTS.md`, `*/**/CLAUDE.md` (subdirectory instructions)
   - `*/.agents/AGENTS.md`

   Search up to 4 levels deep. Exclude `node_modules`, `.git`, `__pycache__`, and `venv` directories.

4. Resolve `@<path>` imports in instruction files and add their targets to the inventory: an imported file is part of the loaded surface even when nothing else references it.

5. Build an inventory table of every config file found, grouped by project.

### Phase 2: Audit

Read every config file discovered. For each, check:

#### Claude Code settings files (settings.json, settings.local.json)

- **Redundant permissions**: local `allow` entries that are already covered by a global `allow` rule (exact match or glob superset).
- **Conflicting permissions**: local `allow` entries that contradict a global `deny` rule, or vice versa.
- **Overly broad permissions**: `Bash(*)` or similar wildcards that bypass the deny list.
- **Duplicate entries**: the same permission string appearing twice in the same file.
- **Orphaned local settings**: `settings.local.json` files for projects that no longer exist or haven't been opened recently.
- **Missing deny rules**: projects that override permissions without inheriting the global deny list.
- **Hook inconsistencies**: hooks defined locally that duplicate or conflict with global hooks.
- **Env var conflicts**: environment variables set locally that contradict global values.

#### pi settings files (~/.pi/agent/settings.json, .pi/settings.json, trust.json)

- **Dead overrides**: project keys that repeat the global value verbatim.
- **Contradictory overrides**: project keys that change behavior in ways the user likely did not intend (a narrower `defaultTools` than the global set, a disabled feature the global enables).
- **Stale trust entries**: `trust.json` folders that no longer exist.
- **Stale packages**: packages listed in global settings but no longer installed (cross-check with `pi list`).
- **Orphaned resources**: a project-scope extension, skill, or prompt template duplicating a global one with different content, or left behind by a removed project.

#### Cross-harness

- **Duplicate loading**: the same skill reachable through more than one location (a harness-local copy beside the shared `.agents/skills/` original): one canonical copy wins, flag the rest.
- **Coverage drift**: a skill, agent, or prompt template available in one harness but not the other, when the two are meant to share it.

#### Instruction files (CLAUDE.md, AGENTS.md, @imports)

- **Redundant instructions**: local instruction content that duplicates what's already in the machine-wide instruction file.
- **Contradictory instructions**: local rules that conflict with global rules.
- **Stale references**: `@` includes pointing to files that don't exist.
- **Generic instructions**: local instructions that aren't project-specific and could be promoted to global.
- **Token bloat**: measure every instruction file with a tokenizer before judging its size. Word counts and filler rates do not predict token cost; cl100k or o200k sits within ~5-10% of Claude's tokenizer in aggregate. Flag a file for compression only when a measured pass would save ~10% or more. Below that, the remaining words are the payload and the edit is churn.
- **Compressibility**: for a flagged file, re-encode rather than delete. Keep every MUST/NEVER line, every default with its unit, every exact string, example, and failure condition, and declare every intended loss before rewriting. If the `semantic-compression` skill is available, follow its procedure; this bullet is the fallback minimum.

### Phase 3: Promotion candidates

Identify patterns that appear across multiple projects and would benefit from promotion to the global config:

#### Permission promotion (Claude Code only)

pi has no allow/deny rule surface; its gating is the harness permission layer and per-folder trust. This subsection applies to Claude Code settings alone.

- Count how many projects share each local `allow` entry.
- If a permission appears in 3+ project configs (or in more than half of all projects), flag it as a promotion candidate for `~/.claude/settings.json`.

#### Instruction promotion

- Look for similar phrasing or rules in multiple project instruction files.
- Flag instructions that are project-agnostic (not referencing specific files, tools, or frameworks unique to one project).

#### Deny rule gaps (Claude Code only)

- If local configs add deny rules not in the global config, consider whether they should be global.

### Phase 3.5: Session transcript review

Scan past session transcripts to find tool calls that were denied by the sandbox or by the permission allow/deny rules, then propose allowlist refinements. Denials are the primary signal, but also mine the corpus for recurring failures and retry loops that point at misconfiguration (see Beyond denials below).

Keep re-runs incremental: record the last-scanned `mtime` and size per session file in one state file per harness (`~/.claude/.self-tune-transcript-state.json`, `~/.pi/agent/.self-tune-transcript-state.json`), and parse only files that changed since the previous run. The corpus grows with every session, and a full re-scan each time costs the reading time the tuning is meant to save.

#### Where transcripts live

- Claude Code: `~/.claude/projects/<encoded-project-path>/<session-uuid>.jsonl`, one JSONL file per session, sibling to a directory of the same UUID containing tool results. The encoded project path replaces `/` with `-`, so `/Users/kde/code/dotfiles` becomes `-Users-kde-code-dotfiles`.
- pi: `~/.pi/agent/sessions/*.jsonl`, one JSONL file per session, organized by working directory.

#### Denial signals to grep for (Claude Code)

pi prompts interactively and keeps no allow/deny rules, so denial mining applies to Claude Code sessions only. Search transcripts for these markers in `message.content[*].content` and `toolUseResult` fields:

- `Permission to use <Tool> with command <X> has been denied.`: user pressed "deny" on a permission prompt.
- `requires approval`, `requires permission`: tool call paused on the allowlist gate.
- `Operation not permitted`, `sandbox`, `dangerouslyDisableSandbox`: sandbox filesystem or network denial.
- `EACCES`, `EPERM`: surfaced when a sandboxed command hits a denied path.

Use `Grep` with these patterns across `~/.claude/projects/**/*.jsonl`. Default to the last 30 days; allow the user to widen the window.

#### Extracting actionable patterns

For each denial, extract:

- The tool name (Bash, Edit, Read, WebFetch, ...).
- The exact argument that was denied (the bash command, the file path, the URL host).
- The matching permission rule shape: `Bash(rm:*)`, `Read(/Users/kde/.ssh/**)`, `WebFetch(domain:example.com)`.
- The session date and project, so I can tell recurring denials apart from one-offs.

Group denials by rule shape and count occurrences across sessions and projects.

#### Classifying denials

Each recurring denial falls into one of three buckets, and the proposed change differs by bucket:

1. **Should be allowed**: a benign command the user kept approving manually (high re-approval rate, no destructive intent). Propose adding a narrow `allow` rule, scoped to the smallest pattern that covers the observed calls (prefer `Bash(tool:*)` over `Bash(*)`).
2. **Should stay blocked, but noisy**: the denial is correct but the prompt fires often. Propose a `deny` rule so future calls fail fast without an interactive prompt, or propose a hook that rewrites the call.
3. **Sandbox-only**: the permission rule already allows the call, but the sandbox filesystem or network policy denied it. Propose adding the path to `permissions.additionalDirectories` or the host to the network allowlist, and never propose `dangerouslyDisableSandbox` as a fix.

Skip one-off denials (single occurrence, no project recurrence): they are noise.

#### Beyond denials: failure and loop signals

Two more corpus signals produce config findings, though both are noisier than denials. They apply to transcripts of both harnesses:

- **Retry loops**: the same tool call, with the same or near-identical arguments, repeated several times in one session. This is often a permission prompt the user kept answering, or a hook that keeps failing. Extract the repeated call, check it against the allow list and the hook definitions, and classify it as a permission gap, a broken hook, or agent noise.
- **Recurring command errors**: the same command shape failing with the same non-permission error across sessions. This usually points at a hook or environment misconfiguration, not an allowlist gap.

Classify a finding as config-related before proposing anything. Most tool errors in a transcript are ordinary coding failures, not configuration.

#### Output

Add a "Session denials" section to the Phase 4 report with:

- A table of recurring denials and config-related failures: rule shape, count, distinct projects, last seen date, classification.
- For each promoted allow/deny rule, the exact diff to apply to `~/.claude/settings.json` (or the project `settings.json` when the pattern is project-specific).
- For sandbox denials, the proposed `additionalDirectories` or network host entry, with the originating command for context.

### Phase 4: Report

Present a structured report:

#### Inventory

Table of all config files found:

```
| Project | settings.json | settings.local.json | CLAUDE.md / AGENTS.md | Subdirectory instructions |
```

Use checkmarks for present, dashes for absent.

#### Issues found

Group by severity:

- **Conflicts**: permissions or instructions that contradict between layers.
- **Redundancies**: entries that can be removed because they're already covered globally.
- **Stale**: references to missing files, orphaned configs, or outdated settings.

For each issue, show the file path, the problematic entry, and why it's flagged.

#### Promotion candidates

For each candidate:

- The permission or instruction text
- Which projects currently define it locally
- Proposed change to the global config (exact diff)

#### Recommended actions

A numbered list of concrete changes, ordered by impact:

1. Entries to add to the global config
2. Entries to remove from local configs (now redundant after promotion)
3. Conflicts to resolve (with a suggested resolution)
4. Stale entries to clean up
5. Allow/deny rules derived from recurring session denials (Phase 3.5)
6. Sandbox `additionalDirectories` or network host additions for recurring sandbox denials

For every proposed removal, state what the entry prevents and why removing it is still safe. A declared loss is a decision the user can audit; an undeclared one is a guess.

### Phase 5: Apply changes

After presenting the report, ask the user which actions to apply. Then:

1. Edit `~/.claude/settings.json` to add promoted permissions.
2. Edit local config files to remove entries that are now redundant.
3. Edit instruction files to remove duplicated instructions.
4. Do NOT delete any files without explicit user confirmation.
5. Do NOT modify machine-local overrides without explicit user confirmation: Claude Code `settings.local.json` files and pi project `.pi/settings.json` files may carry machine-specific state.
6. For session-derived rules: only apply allow/deny entries the user explicitly approves from the Phase 3.5 table. Never auto-approve sandbox-disabling escapes.

## Important rules

- Use `/usr/bin/find` for file discovery — the shell may alias `find` to `gfind`.
- Read every config file before making any recommendations.
- Never remove a permission that isn't provably redundant (covered by a broader global rule).
- When comparing permissions, account for glob patterns: `Bash(git *)` covers `Bash(git status *)`.
- Present the full report before making any changes.
- Do not touch files outside the audited harness config directories (`~/.claude`, `~/.pi`, and the scanned projects' harness folders).
- Spawn parallel Agents to read project configs when there are more than 5 projects.
- If a config file is a symlink (common in dotfiles repos), follow it and report the real path; write through the repository path, never through the `$HOME` symlink, or the replace-then-rename write forks the two copies.
- Before proposing the removal of a permission rule or an instruction line, `git blame` it when the file is version-controlled. A line that looks redundant is often scar tissue from a past incident, and only its history shows that.
- Measure size in tokens, never words or line counts, before flagging a file as bloated or a change as worthwhile.
- Skip marginal changes: a fix that saves nothing the user would notice is churn, not tuning.
