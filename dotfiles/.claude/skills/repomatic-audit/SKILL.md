---
name: repomatic-audit
description: Audit downstream repo alignment with upstream repomatic reference, covering workflows, configs, and conventions.
model: opus
allowed-tools: Bash, Read, Grep, Glob, WebFetch, Agent
argument-hint: '[all|workflows|configs|claude]'
---

## Context

!`ls .github/workflows/*.yaml 2>/dev/null`
!`grep -h 'uses:.*kdeldycke/repomatic' .github/workflows/*.yaml 2>/dev/null | head -5`
!`grep -A5 '\[tool.repomatic\]' pyproject.toml 2>/dev/null || echo "No [tool.repomatic] section"`
!`grep -E '^(agents|skills|gitignore)\.location' pyproject.toml 2>/dev/null`
!`[ -f repomatic/__init__.py ] && echo "CANONICAL_REPO" || echo "DOWNSTREAM"`

## Instructions

You perform a comprehensive audit of a downstream repository against the upstream `kdeldycke/repomatic` reference. This goes **beyond** what `repomatic workflow sync` handles — it catches stale action versions in custom job content, missing workarounds, outdated configs, and conventions that can be borrowed from upstream.

**This skill is for downstream repos only.** If the context shows `CANONICAL_REPO`, tell the user this skill is not applicable.

### Distinguishing real drift from intended absence

Before flagging an issue, verify that the gap isn't **deliberate** or covered by a runtime mechanism. Common false positives:

- **`[tool.repomatic] exclude` is authoritative.** Files listed there (e.g., `renovate`, `workflows/changelog.yaml`, `labels`) are intentionally absent on disk. Do **not** report them as MISSING.
- **Bundled defaults applied at runtime.** Several workflows materialize their own config from the bundled template at runtime when the file is absent. Examples: the `renovate.yaml` workflow runs `repomatic init renovate` to materialize `renovate.json5` ephemerally; `[tool.ruff]`/`[tool.typos]` defaults from the tool registry are applied without requiring an on-disk copy. **Absence of these files is not a problem** — it is the intended state when the user is happy with the bundled policy. Only flag DRIFT if the user wants to deviate from the bundled policy.
- **Generator artifacts vs user error.** When local thin-callers diverge from upstream (e.g., extra `workflow_dispatch:`, missing `paths:`), the cause may be the **upstream generator**, not downstream tampering. Inspect `repomatic/github/workflow_sync.py` (`generate_thin_caller`, `_adapt_trigger_paths`, `generate_workflow_header`) before recommending the user re-run `repomatic init` to "fix" something `init` itself produced.
- **Project-level `claude.md` may live under a sub-directory.** `[tool.repomatic] agents.location` and `skills.location` indicate a project where `.claude/` is not at the root (e.g., dotfiles repos with `dotfiles/.claude/CLAUDE.md`). Search the configured location, not just `./CLAUDE.md`.

When in doubt, search the upstream codebase to confirm whether a behavior is intentional. Read `[tool.repomatic]` in the local `pyproject.toml` carefully before declaring anything missing.

### Scope selection

- `all` (default when `$ARGUMENTS` is empty): Run all audits below.
- `workflows`: Audit workflow files only.
- `configs`: Audit non-workflow config files only.
- `claude`: Audit `claude.md` alignment only.
- `upstream`: Identify downstream innovations that could be contributed back to repomatic.

### Fetching reference files

Use `gh api repos/kdeldycke/repomatic/contents/{path} --jq '.content' | base64 -d` to fetch upstream reference files.

### 1. Workflow audit (`workflows`)

#### Thin-caller workflows

Compare each local thin-caller workflow against its reference. These should be identical (except for files listed in `exclude`). Flag:

- Extra triggers (e.g., spurious `workflow_dispatch`).
- Missing triggers.
- Version pin drift (different `@vX.Y.Z` tag).

#### Header-only workflows (e.g., `tests.yaml`)

The header (name, `on:`, `concurrency:`) is synced automatically, but custom job content is not. Compare the job content against the reference for:

- **Stale action versions**: e.g., `actions/checkout`, `astral-sh/setup-uv`, `codecov/*` — compare pinned versions.
- **Missing workarounds**: e.g., the "Force native ARM64 Python on Windows ARM64" step that sets `UV_PYTHON`.
- **Missing matrix exclusions**: e.g., `windows-11-arm` + Python 3.10 (no native ARM64 build).
- **Outdated integration patterns**: e.g., using `codecov-action` when upstream migrated to `codecov-cli` via `uvx`.
- **Missing pytest output flags**: e.g., `--cov-report=xml`, `--junitxml=junit.xml` needed for codecov-cli.
- **YAML scalar style issues**: e.g., `run: |` where `run: >` is needed for multi-line single commands.

#### `paths:` filters that don't fit the downstream project

Header-only sync inherits the canonical `paths:` filter verbatim (after `repomatic/**` substitution). When the project's filesystem layout doesn't match, two outcomes are possible:

- **Inherited entries that don't exist locally** (e.g., `tests/**`, `uv.lock` in a non-Python repo): the trigger never fires for them. Coverage is missing, not noisy. Recommend `[tool.repomatic.workflow.ignore_paths]` to drop them.
- **Locally relevant paths not in the canonical filter** (e.g., `install.sh`, `dotfiles/**` in a config repo): the trigger silently skips PRs that should run CI. Recommend `[tool.repomatic.workflow.extra_paths]` to append them globally, or `[tool.repomatic.workflow.paths]` keyed by filename for a per-workflow wholesale replacement.

The relevant config schema lives in `WorkflowConfig` (`repomatic/config.py`): `source_paths`, `extra_paths`, `ignore_paths`, and `paths` (per-workflow override dict, keyed by workflow filename). Per-workflow override is authoritative — it replaces the entire `paths:` list and ignores the other knobs.

#### Excluded workflows

Respect `exclude` entries from `[tool.repomatic]` in `pyproject.toml`. Report excluded files but do not flag them as drift.

### 2. Config file audit (`configs`)

Compare these files against the upstream reference. **Before flagging absence as DRIFT**, verify the file is not deliberately omitted (see "Distinguishing real drift" above):

| File                                  | What to check                                                                                                     | Absence is OK when                                                                    |
| ------------------------------------- | ----------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| `renovate.json5`                      | Divergence from bundled policy (labels, assignees, stabilization windows, custom managers)                        | Always: the `renovate.yaml` workflow materializes the bundled default at runtime.     |
| `pyproject.toml` `[tool.typos]`       | Missing `default.extend-identifiers` for common capitalizations (GitHub, macOS, PyPI, iOS, etc.)                  | Tool registry applies bundled defaults; only flag when the local file overrides them. |
| `pyproject.toml` `[tool.bumpversion]` | Missing `ignore_missing_files`                                                                                    | Project is not Python-versioned (no `[project]` table).                               |
| `pyproject.toml` `[tool.ruff]`        | Missing or divergent lint rules, preview settings                                                                 | Project has no `*.py` files (only flag if Python files exist that ruff would scan).   |
| `pyproject.toml` `[tool.mypy]`        | Missing settings compared to reference                                                                            | No Python source.                                                                     |
| `.github/ISSUE_TEMPLATE/`             | Filename conventions (hyphens, not underscores), missing labels                                                   | Personal/internal repo without external bug reporters.                                |
| `.github/code-of-conduct.md`          | Title-case headings vs upstream sentence case, plaintext email vs anti-scrape obfuscation, stale attribution URLs | Replace verbatim with upstream when divergence is detected.                           |
| `.github/funding.yml`                 | Compare with reference                                                                                            | —                                                                                     |
| `.gitignore`                          | Symlink target (often `dotfiles/.gitignore_global` or similar) vs upstream                                        | Auto-generated by repomatic; drift means the user should re-run sync.                 |
| `lychee.toml`                         | Note differences (usually project-specific, just flag for review)                                                 | Project doesn't run lychee.                                                           |

**Skip** files that are intentionally excluded via `exclude` in `[tool.repomatic]`. Cross-check `[tool.ruff] extend-exclude` and similar before flagging "missing" entries.

### 3. `claude.md` audit (`claude`)

**Locate the local file first.** It may not be at the repo root:

- Check `[tool.repomatic] agents.location` and `skills.location` for a sub-directory (e.g., `dotfiles/.claude/`); if those are set, look for `{location_parent}/CLAUDE.md`.
- Try common alternates: `claude.md`, `CLAUDE.md`, `.claude/CLAUDE.md`, `dotfiles/.claude/CLAUDE.md`.

Fetch the upstream `claude.md` and identify universally applicable sections that the local file is missing. Focus on:

- Terminology and spelling rules.
- Version formatting conventions.
- File naming conventions (long-form extensions, lowercase, GitHub exceptions table).
- Modern typing practices.
- YAML scalar style (`>` vs `|`).
- Markdown heading anchor rules.
- Python version compatibility caveats.
- Testing guidelines (e.g., "no test classes" rule, `@pytest.mark.once`).
- Common maintenance pitfalls (CI URL, root-cause tracing, doc drift, type-check divergence, angle-bracket placeholders, route-through-existing-infra).
- Command-line option conventions.

Do **not** flag upstream sections that are project-specific (e.g., CLI abstractions, knowledge placement table, workflow design rationale, release checklists, agent conventions, MyST docstring rules, `__init__.py` discipline, `TYPE_CHECKING` block patterns).

**Do not treat the local file as a downstream copy of upstream.** Many downstream `claude.md` files are personal-conventions documents with project-agnostic preferences (voice, commit policy, shell-command patterns, language preferences) that should not appear in upstream. Only flag missing content that is universally applicable.

### 4. Upstream contribution opportunities (`upstream`)

Scan the downstream repo for patterns, workarounds, or configurations that are **better** than or **missing from** the upstream reference. These are candidates for contributing back to `kdeldycke/repomatic`. Look for:

- **Broader test matrices**: e.g., more OS variants, extra Python versions, additional architecture coverage that upstream could adopt as defaults.
- **Workarounds for known issues**: Steps or configs that fix CI failures or edge cases that upstream hasn't addressed yet.
- **Better tool configurations**: e.g., ruff `extend-include` patterns, pytest addopts, coverage settings that are more complete than upstream.
- **Useful `pyproject.toml` patterns**: e.g., dependency group definitions, build config, or tool settings that could be generalized.
- **Custom workflow steps**: Reusable patterns in header-only workflows (e.g., package install verification, environment variable passing) that could become part of the reference workflow.
- **Documentation improvements**: `claude.md` sections, issue templates, or repo metadata patterns that would benefit all downstream repos.

For each candidate, assess:

1. **Generalizability**: Would this benefit most downstream repos, or is it project-specific?
2. **Complexity**: Is it a simple config change or a significant workflow redesign?
3. **Action**: Suggest filing as a GitHub issue or PR at `kdeldycke/repomatic`, with a draft title and description.

### Output format

For each audit area, produce:

1. A summary table: item, status (MATCH / DRIFT / MISSING / N/A), brief description.
2. For each issue: what the current state is, what the reference has, and the recommended fix.
3. Prioritize: group by severity (breaking/functional issues first, then consistency, then cosmetic).

**Status guide:**

- **MATCH** — local matches reference (or differs only cosmetically with no functional impact).
- **DRIFT** — local exists and diverges from reference in a way the user likely wants to fix.
- **MISSING** — file expected but absent. Reserve for cases where absence is genuinely a problem; if the absence is covered by `[tool.repomatic] exclude`, runtime materialization, or a tool-registry default, mark **N/A** instead.
- **N/A** — file does not apply to this project (excluded, opt-out, or outside the project's scope).

When unsure between DRIFT and N/A, lean N/A and explain in the description; over-flagging produces noisy reports the user has to refute.

### After running

Suggest the user run:

- `/repomatic-sync` to fix thin-caller workflow drift automatically.
- Manual edits for header-only workflow drift and config changes.
- `/repomatic-lint` to validate after fixes are applied.
- `/sphinx-docs-sync` to audit `docs/` against sibling projects when this repo has a Sphinx documentation tree. The `sphinx-docs` agent (`.claude/agents/sphinx-docs.md`, opt-in via `repomatic init agents/sphinx-docs`) holds the canonical conventions for `configuration.md`, `cli.md`, `install.md`, `conf.py`, and the standard page roster — recommend opting in when the repo has Sphinx docs that drift from upstream patterns.

If the audit surfaces a generator behavior that produces unwanted output (e.g., a thin-caller trigger the user wants gone, a header `paths:` filter that doesn't fit), fix it in the upstream tool (`repomatic/github/workflow_sync.py`, `repomatic/config.py`) rather than asking the user to hand-patch the generated file every time `repomatic init` runs.
