---
name: sphinx-docs-sync
description: Two-way comparison and synchronization of Sphinx documentation across sibling projects. Discovers discrepancies in conf.py, install.md, index.md toctree, pyproject.toml docs dependencies, extra-deps sections, readme badges, and static assets. Use when you want to align documentation structure, catch stale dependencies, or push improvements across your Sphinx-enabled repositories.
model: sonnet
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob, Agent
argument-hint: '[path-or-github-url ...]'
---

## Context

!`[ -d docs ] && echo "docs/ exists" || echo "No docs/ directory"`
!`[ -f docs/conf.py ] && head -5 docs/conf.py || echo "No docs/conf.py"`
!`ls ../*/docs/conf.py 2>/dev/null | head -20 || echo "No sibling projects with docs/conf.py"`

## Instructions

You audit Sphinx documentation consistency across sibling projects. Find discrepancies in both directions: improvements this project can borrow from siblings, and improvements this project can push to siblings.

**This skill is the procedure layer; the rule layer is `.claude/agents/sphinx-docs.md`.** It carries the canonical conventions: `{click:run}` directives, recipes for `configuration.md`/`cli.md`/`install.md`, the standard page roster, `conf.py` hygiene, MyST/admonition rules, high-frequency lapses. When a discrepancy maps to a rule, cite the agent section so the user reads the rationale alongside the proposed change. When you find a pattern not yet codified, propose adding it to the agent rather than fixing it in each repo independently.

### Discover projects

If `$ARGUMENTS` are provided, each argument is a local directory path or a GitHub repository URL (`https://github.com/owner/repo` or `owner/repo`). For GitHub URLs, clone into a tmpdir with `gh repo clone`. Otherwise, scan the parent directory of the cwd for projects with a `docs/conf.py`.

Filter out forks: check `git remote get-url origin` and skip projects whose upstream repo name doesn't match the directory name (a local `click/` pointing to a fork of `pallets/click`). Focus on the user's own projects.

List the discovered projects and confirm with the user before proceeding.

### Collect documentation inventory

For each project, collect (parallelize with sub-Agents when possible). For each artifact, the agent section in parentheses is where the convention lives — diff the project against that section, not against your own preferences.

- **`docs/conf.py`** (agent § `docs/conf.py` hygiene, § Standard extension set). Read the full file. Surface settings present in some projects but missing from others; deprecated/renamed settings; conditional imports for Python versions below the project's floor; `read_text()` calls without `encoding=`. Cross-check the extension list against the canonical set; flag projects missing `sphinx_issues`, `sphinxext.opengraph`, or `sphinxcontrib.mermaid` that would benefit from them. Confirm `myst_enable_extensions` matches the canonical alphabetized list. Verify `repomatic.myst_docstrings` ordering (must precede `sphinx_autodoc_typehints`) and corresponding `repomatic` entry in `[dependency-groups] docs`.
- **`conf.py` warning/strictness governance** (agent § `suppress_warnings` governance, § `nitpick_ignore` governance, § Linkcheck and intersphinx). Audit each `suppress_warnings`, `nitpick_ignore`, and `linkcheck_ignore` entry: does it carry a comment naming the failing case and the reason for suppression? Flag uncommented entries. Re-test linkcheck-ignored hosts on each audit pass; remove entries that have started working again. Suggest migrating per-anchor `linkcheck_anchors_ignore` patterns to per-host `linkcheck_anchors_ignore_for_url` when the entire host is JS-rendered.
- **`docs/index.md`** (agent § Standard page roster). Diff toctree shape, page ordering, octicon icons (cross-check against the canonical octicon registry), and presence/absence of standard pages.
- **`docs/install.md`** (agent § Recipes › `install.md`). Diff section roster, install-method tab order, executables table format, Repology badge, Python compatibility matrix structure, gh attestation verify section.
- **`docs/cli.md` and `docs/configuration.md`** (agent § Recipes). Diff the auto-region between markers and confirm the regenerator script (`docs/docs_update.py`) follows the same shape across projects.
- **Auto-region marker naming** (agent § Auto-generated reference tables, marker naming convention). Grep all `docs/*.md` for `<!-- start -->`/`<!-- end -->` pairs; flag any bare markers, recommend renaming to `<!-- {feature}-{kind}-start -->`. Confirm that named markers across siblings use consistent `{kind}` slugs (`table`, `sankey`, `mindmap`, `autodata`, `automodule`, `autodoc`, `reference`).
- **Theme assets** (agent § `conf.py` hygiene › Theme assets and OpenGraph). Confirm `html_logo = "assets/logo-square.svg"`, `html_favicon = "assets/favicon.svg"`, and `ogp_image = "assets/banner-social-light.png"` when banner assets exist. Flag projects with `sphinxext.opengraph` enabled but no `ogp_image` set. Suggest the user run `/brand-assets` on flagged projects to regenerate or backfill the asset set in one pass.
- **`sphinx_issues` migration** (agent § Migrating off `sphinx_issues`). Grep each project for `{issue}` `/`{pr}` ` / `{user}` `/`{commit}` ` (MyST) and `:issue:` `/`:pr:` ` / `:user:` `/`:commit:` ` (reST) across `*.md`, `*.rst`, `*.py`. Flag every occurrence and offer to apply the migration recipe in one pass per repo. After replacement, drop `"sphinx_issues"` from `extensions` in `conf.py`, `"sphinx-issues>=…"` from `[dependency-groups] docs`, and any `issues_github_path` setting unused by other extensions.
- **`pyproject.toml` docs dependency group**. Compare against what `conf.py` actually imports — flag undeclared imports and declared-but-unimported deps. Don't change version pins unless provably stale (a conditional dep on a Python version below the project's floor; a transitively-constrained loose pin held by a meta-extra like `click-extra[sphinx]`).
- **`readme.md`**. Compare badge sets and section structure. Flag a `## Development` section when `claude.md` exists in the same repo (per agent § High-frequency lapses).
- **Sphinx tests** (agent § Sphinx tests). Look for `tests/sphinx/`, `tests/test_sphinx_*.py`, or `test_sphinx_crossrefs.py`. Note which projects have render-tests and which don't; suggest adopting cross-reference render tests where the docs surface complex `{role}` cross-refs.
- **Static assets and auto-generated files**. Compare `docs/_static/`, `docs/assets/`, `.rst` files, `docs_update.py`. Hunt for stale `.rst` orphans from past package renames.

### Compare and report

Present findings as tables organized by category:

```
### Category name

| Issue | Severity | Direction | Projects |
|:------|:---------|:----------|:---------|
| description (cite agent § X) | bug/align/enhance | borrow/push | list |
```

Group, in this order:

1. Bug fixes (stale deps, missing declared deps, broken links).
2. Structural alignment (toctree, page naming, `conf.py` settings).
3. Content improvements (install.md sections, extra-deps tables, badges).

For each row, name the agent section that authorizes the change (e.g., "agent § Standard page roster: docs/agents toctree entry missing"). If a discrepancy doesn't map to any agent section, flag it as a candidate for new agent content rather than a fix to push.

### Implement

After presenting the report, ask the user which items to apply. When they confirm, group edits by project to minimize context switches.

### Procedural guards

These are about *how* you run the audit, not what counts as a violation:

- Always verify file existence before recommending changes based on cross-project patterns. A "missing" file may not apply (e.g., shell completion only matters for CLI projects; binaries only for projects with `nuitka.enabled` in `[tool.repomatic]`).
- When a dependency appears in multiple groups (main, extras, docs), the version may be intentionally loose in one group because it's transitively constrained. Verify before flagging.
- Respect project-specific opt-outs: `[tool.repomatic] exclude` and `include` lists are authoritative. A page or component listed in `exclude` is intentionally absent.
- Never silently bump a version pin. Loose pins are sometimes intentional; tight pins always have a reason. Flag, don't fix.

### Next steps

Suggest the user run:

- `/repomatic-audit` for broader workflow and config alignment across the same projects.
- `/repomatic-deps` to analyze dependency graphs for projects with stale or divergent docs deps.
- Opting into the `sphinx-docs` agent (`repomatic init agents/sphinx-docs`) on any project that drifted significantly — Claude will then auto-load the conventions when working in that repo.
