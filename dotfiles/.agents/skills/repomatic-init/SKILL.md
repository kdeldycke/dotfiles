---
name: repomatic-init
description: Bootstrap a repository with reusable workflows from kdeldycke/repomatic.
compatibility: 'Designed for Claude Code. Recommended model: Haiku.'
allowed-tools: Bash Read Grep Glob
argument-hint: '[component ...]'
---

## Context

!`[ -f pyproject.toml ] && echo "pyproject.toml exists" || echo "No pyproject.toml"`

!`ls .github/workflows/ 2>/dev/null || echo "No .github/workflows/ directory"`

!`[ -f repomatic/__init__.py ] && echo "CANONICAL_REPO" || echo "DOWNSTREAM"`

## Instructions

You help users bootstrap a repository to use the reusable GitHub Actions workflows from `kdeldycke/repomatic`.

### Determine invocation method

- If the context above shows `CANONICAL_REPO`, use `uv run repomatic init`.
- Otherwise, use `uvx -- repomatic init`.
- Gate the `uvx` form with the supply-chain cooldown: `uvx --exclude-newer '{window}' --exclude-newer-package repomatic=P0D -- repomatic`. Read `{window}` from the `UV_EXCLUDE_NEWER` value of any `.github/workflows/*.yaml`, which `repomatic init` renders from `[tool.repomatic] minimum-release-age`. With no workflow yet, read that key from `pyproject.toml`, and ask the user when it is unset. `--exclude-newer-package` exempts repomatic itself, so a fresh release stays installable while its dependency tree stays gated.

### Argument handling

- If `$ARGUMENTS` is empty, first analyze the project (check `pyproject.toml`, existing workflows, project language) and recommend which components to initialize. Then ask the user to confirm before running.
- If `$ARGUMENTS` is provided, pass it through: `<cmd> init $ARGUMENTS`.

### After running

- Show the generated files and explain what each workflow does.
- Highlight required next steps: GitHub PAT setup for workflows that need it, GitHub Pages configuration for docs workflows, and any `pyproject.toml` `[tool.repomatic]` configuration options.
- If existing workflow files were detected, warn about potential conflicts.

### Next steps

Suggest the user run:

- `/repomatic-audit` to check the generated files against upstream conventions.
