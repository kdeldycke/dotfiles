# Surfaces: where agent configuration lives

Detect which harnesses are present on the machine (`~/.claude` for Claude Code, `~/.pi` for pi) and audit only those. Within each harness, layers load in this order (later wins):

## Claude Code

| Scope                     | File                                    | Purpose                                    |
| ------------------------- | --------------------------------------- | ------------------------------------------ |
| Global user               | `~/.claude/settings.json`               | Permissions, hooks, env vars, plugins      |
| Global user local         | `~/.claude/settings.local.json`         | Machine-specific overrides (not committed) |
| Global instructions       | `~/.claude/CLAUDE.md`                   | User-wide behavioral instructions          |
| Project                   | `<project>/.claude/settings.json`       | Project-level permissions and hooks        |
| Project local             | `<project>/.claude/settings.local.json` | Machine-specific project overrides         |
| Project instructions      | `<project>/CLAUDE.md`                   | Project-level behavioral instructions      |
| Subdirectory instructions | `<project>/<subdir>/CLAUDE.md`          | Scoped instructions for a subtree          |

## pi

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

## Shared by both

| Path                                             | Purpose                                                                            |
| ------------------------------------------------ | ---------------------------------------------------------------------------------- |
| `~/.agents/skills/`, `<project>/.agents/skills/` | Harness-neutral skill locations (pi reads them; any Agent Skills spec harness may) |
| `<project>/.agents/AGENTS.md`                    | Harness-neutral project instructions                                               |
| `@<path>` imports inside any instruction file    | Include chains that load extra directives                                          |

## Discovery

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

## Agent-facing markdown

A candidate is a markdown file a model reads cold:

- Instruction files: `AGENTS.md`, `CLAUDE.md`, `claude.md` at any level.
- Agent definitions: `.claude/agents/*.md` and equivalent directories.
- Skill bodies: `**/skills/**/SKILL.md`.
- Bundled copies a sync pushes downstream: `*/data/agent-*.md`, `*/data/skills/**`, and peers.

Exclude what is not agent-facing: the `docs/` tree, readmes, changelogs, PR and issue templates, contributor docs (`contributing`, `code-of-conduct`), and generated artifacts. The audience decides: a file a human reads and a model never does is skipped; when unsure, audit it.

Enumerate the tracked set first, then verify each candidate by audience:

```shell-session
$ git ls-files '*.md' | grep -E '(AGENTS|CLAUDE|claude)\.md|agents/|SKILL\.md'
```

## Cross-harness checks

- **Duplicate loading**: the same skill reachable through more than one location (a harness-local copy beside the shared `.agents/skills/` original): one canonical copy wins, flag the rest.
- **Coverage drift**: a skill, agent, or prompt template available in one harness but not the other, when the two are meant to share it.
