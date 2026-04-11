---
name: audit-config
description: Browse all global and local Claude Code config files (settings.json, settings.local.json, CLAUDE.md), audit them for issues, and percolate recurring local patterns into the global config.
allowed-tools: Bash, Read, Grep, Glob, Edit, Agent
argument-hint: '[~/code or parent directory to scan]'
---

# Audit and consolidate Claude Code configuration

Scan all Claude Code configuration files across projects, audit them for issues, and promote recurring local patterns into the global config.

## Config file types

Claude Code configuration lives in several layers, loaded in this order (later wins):

| Scope                     | File                                    | Purpose                                    |
| ------------------------- | --------------------------------------- | ------------------------------------------ |
| Global user               | `~/.claude/settings.json`               | Permissions, hooks, env vars, plugins      |
| Global user local         | `~/.claude/settings.local.json`         | Machine-specific overrides (not committed) |
| Global instructions       | `~/.claude/CLAUDE.md`                   | User-wide behavioral instructions          |
| Project                   | `<project>/.claude/settings.json`       | Project-level permissions and hooks        |
| Project local             | `<project>/.claude/settings.local.json` | Machine-specific project overrides         |
| Project instructions      | `<project>/CLAUDE.md`                   | Project-level behavioral instructions      |
| Subdirectory instructions | `<project>/<subdir>/CLAUDE.md`          | Scoped instructions for a subtree          |

## Argument handling

`$ARGUMENTS` is an optional parent directory to scan for projects. Defaults to `~/code`.

## Workflow

### Phase 1: Discovery

1. Read the global config files:

   - `~/.claude/settings.json`
   - `~/.claude/settings.local.json`
   - `~/.claude/CLAUDE.md`

2. Find all projects under the scan directory. Use `/usr/bin/find` (not the shell alias) to locate:

   - `*/.claude/settings.json`
   - `*/.claude/settings.local.json`
   - `*/CLAUDE.md`
   - `*/**/CLAUDE.md` (subdirectory instructions)

   Search up to 4 levels deep. Exclude `node_modules`, `.git`, `__pycache__`, and `venv` directories.

3. Build an inventory table of every config file found, grouped by project.

### Phase 2: Audit

Read every config file discovered. For each, check:

#### Settings files (settings.json, settings.local.json)

- **Redundant permissions**: local `allow` entries that are already covered by a global `allow` rule (exact match or glob superset).
- **Conflicting permissions**: local `allow` entries that contradict a global `deny` rule, or vice versa.
- **Overly broad permissions**: `Bash(*)` or similar wildcards that bypass the deny list.
- **Duplicate entries**: the same permission string appearing twice in the same file.
- **Orphaned local settings**: `settings.local.json` files for projects that no longer exist or haven't been opened recently.
- **Missing deny rules**: projects that override permissions without inheriting the global deny list.
- **Hook inconsistencies**: hooks defined locally that duplicate or conflict with global hooks.
- **Env var conflicts**: environment variables set locally that contradict global values.

#### CLAUDE.md files

- **Redundant instructions**: local CLAUDE.md content that duplicates what's already in `~/.claude/CLAUDE.md`.
- **Contradictory instructions**: local rules that conflict with global rules.
- **Stale references**: `@` includes pointing to files that don't exist.
- **Generic instructions**: local instructions that aren't project-specific and could be promoted to global.

### Phase 3: Promotion candidates

Identify patterns that appear across multiple projects and would benefit from promotion to the global config:

#### Permission promotion

- Count how many projects share each local `allow` entry.
- If a permission appears in 3+ project configs (or in more than half of all projects), flag it as a promotion candidate for `~/.claude/settings.json`.

#### Instruction promotion

- Look for similar phrasing or rules in multiple project CLAUDE.md files.
- Flag instructions that are project-agnostic (not referencing specific files, tools, or frameworks unique to one project).

#### Deny rule gaps

- If local configs add deny rules not in the global config, consider whether they should be global.

### Phase 4: Report

Present a structured report:

#### Inventory

Table of all config files found:

```
| Project | settings.json | settings.local.json | CLAUDE.md | Subdirectory CLAUDE.md |
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

### Phase 5: Apply changes

After presenting the report, ask the user which actions to apply. Then:

1. Edit `~/.claude/settings.json` to add promoted permissions.
2. Edit local config files to remove entries that are now redundant.
3. Edit CLAUDE.md files to remove duplicated instructions.
4. Do NOT delete any files without explicit user confirmation.
5. Do NOT modify `settings.local.json` files without explicit user confirmation (they may contain machine-specific overrides).

## Important rules

- Use `/usr/bin/find` for file discovery — the shell may alias `find` to `gfind`.
- Read every config file before making any recommendations.
- Never remove a permission that isn't provably redundant (covered by a broader global rule).
- When comparing permissions, account for glob patterns: `Bash(git *)` covers `Bash(git status *)`.
- Present the full report before making any changes.
- Do not touch files outside the Claude config directories.
- Spawn parallel Agents to read project configs when there are more than 5 projects.
- If `settings.json` is a symlink (common in dotfiles repos), follow it and report the real path.
