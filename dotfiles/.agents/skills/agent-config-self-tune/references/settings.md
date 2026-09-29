# Settings, permissions and hooks

Read every settings file of the scope. For each, check:

## Claude Code settings files (settings.json, settings.local.json)

- **Redundant permissions**: local `allow` entries that are already covered by a global `allow` rule (exact match or glob superset).
- **Conflicting permissions**: local `allow` entries that contradict a global `deny` rule, or vice versa.
- **Overly broad permissions**: `Bash(*)` or similar wildcards that bypass the deny list.
- **Duplicate entries**: the same permission string appearing twice in the same file.
- **Orphaned local settings**: `settings.local.json` files for projects that no longer exist or haven't been opened recently.
- **Missing deny rules**: projects that override permissions without inheriting the global deny list.
- **Hook inconsistencies**: hooks defined locally that duplicate or conflict with global hooks.
- **Env var conflicts**: environment variables set locally that contradict global values.

## pi settings files (~/.pi/agent/settings.json, .pi/settings.json, trust.json)

- **Dead overrides**: project keys that repeat the global value verbatim.
- **Contradictory overrides**: project keys that change behavior in ways the user likely did not intend (a narrower `defaultTools` than the global set, a disabled feature the global enables).
- **Stale trust entries**: `trust.json` folders that no longer exist.
- **Stale packages**: packages listed in global settings but no longer installed (cross-check with `pi list`).
- **Orphaned resources**: a project-scope extension, skill, or prompt template duplicating a global one with different content, or left behind by a removed project.

## Promotion candidates

Identify patterns that appear across multiple projects and would benefit from promotion to the global config:

### Permission promotion (Claude Code only)

pi has no allow/deny rule surface; its gating is the harness permission layer and per-folder trust. This subsection applies to Claude Code settings alone.

- Count how many projects share each local `allow` entry.
- If a permission appears in 3+ project configs (or in more than half of all projects), flag it as a promotion candidate for `~/.claude/settings.json`.

### Deny rule gaps (Claude Code only)

- If local configs add deny rules not in the global config, consider whether they should be global.

## Rules

- Never remove a permission that isn't provably redundant (covered by a broader global rule).
- When comparing permissions, account for glob patterns: `Bash(git *)` covers `Bash(git status *)`.
