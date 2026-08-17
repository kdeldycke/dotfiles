---
name: repomatic-audit
description: Audit downstream repo alignment with upstream repomatic reference, covering workflows, configs, and conventions.
compatibility: 'Designed for Claude Code. Recommended model: Opus.'
allowed-tools: Bash Read Grep Glob WebFetch Agent
argument-hint: '[all|workflows|configs|agent]'
---

## Context

!`ls .github/workflows/*.yaml 2>/dev/null`
!`grep -h 'uses:.*kdeldycke/repomatic' .github/workflows/*.yaml 2>/dev/null | head -5`
!`grep -A5 '\[tool.repomatic\]' pyproject.toml 2>/dev/null || echo "No [tool.repomatic] section"`
!`grep -E '^(agent|subagents|skills|gitignore)\.location' pyproject.toml 2>/dev/null`
!`[ -f repomatic/__init__.py ] && echo "CANONICAL_REPO" || echo "DOWNSTREAM"`

## Instructions

You perform a comprehensive audit of a downstream repository against the upstream `kdeldycke/repomatic` reference. This goes **beyond** what `repomatic init workflows` handles: it catches stale action versions in custom job content, missing workarounds, outdated configs, and conventions that can be borrowed from upstream.

**This skill is for downstream repos only.** If the context shows `CANONICAL_REPO`, tell the user this skill is not applicable.

### Distinguishing real drift from intended absence

Before flagging an issue, verify that the gap isn't **deliberate** or covered by a runtime mechanism. Common false positives:

- **`[tool.repomatic] exclude` is authoritative.** Files listed there (like `workflows/changelog.yaml` or `labels`) are intentionally absent on disk. Do **not** report them as MISSING.
- **Bundled defaults applied at runtime.** Some config is materialized from the bundled template at runtime when the file is absent, so no on-disk copy is needed. **Absence of these files is not a problem**: it is the intended state when the user is happy with the bundled policy. Only flag DRIFT if the user wants to deviate from it. Exactly five tools carry such a fallback, the ones whose `ToolSpec` sets `default_config` in `repomatic/tool_registry.py`: `actionlint`, `mdformat`, `ruff`, `yamllint` and `zizmor`.
- **A `[tool.X]` section is never a candidate for deletion.** The inverse of the rule above, and the more expensive mistake. Every other tool has no `default_config`, so its resolution chain has no level 3 to fall back on: `lychee`, `typos`, `mypy`, `pytest`, `coverage`, `bumpversion` and `uv` are *deployed* into `pyproject.toml` by `repomatic init`, and that section is the only config the tool will ever see. Deleting it does not restore inheritance from a bundled default, it drops the tool to level 4 and runs it bare, silently discarding every rule the section held. Read the tool's `default_config` before proposing a section be dropped "to inherit upstream updates". A deployed section that has gone stale is fixed by re-running `repomatic init`, which resyncs the components marked `SyncMode.ONGOING` in `repomatic/registry.py`.
- **Generator artifacts vs user error.** When local thin-callers diverge from upstream (e.g., extra `workflow_dispatch:`, missing `paths:`), the cause may be the **upstream generator**, not downstream tampering. Inspect `repomatic/github/workflow_sync.py` (`generate_thin_caller`, `_adapt_trigger_paths`, `generate_workflow_header`) before recommending the user re-run `repomatic init` to "fix" something `init` itself produced.
- **Project-level `claude.md` may live under a sub-directory.** `[tool.repomatic] subagents.location` and `skills.location` indicate a project where `.claude/` is not at the root (e.g., dotfiles repos with `dotfiles/.claude/CLAUDE.md`). Search the configured location, not just `./CLAUDE.md`.

When in doubt, search the upstream codebase to confirm whether a behavior is intentional. Read `[tool.repomatic]` in the local `pyproject.toml` carefully before declaring anything missing.

### Scope selection

- `all` (default when `$ARGUMENTS` is empty): Run all audits below.
- `workflows`: Audit workflow files only.
- `configs`: Audit non-workflow config files only.
- `agent`: Audit the agent instructions file alignment only.
- `upstream`: Identify downstream innovations that could be contributed back to repomatic.

### Fetching reference files

Fetch every reference file at **the version the downstream repo has actually adopted**, never at the tip of `main`. The Context block above prints the `uses:` pins; take the tag from there and pass it as `ref` on every call:

```shell-session
$ gh api "repos/kdeldycke/repomatic/contents/{path}?ref=vX.Y.Z" --jq '.content' | base64 -d
```

An unpinned fetch resolves to `main`, which carries unreleased work. Audited against it, every change waiting for the next release reads as downstream drift, and the "fix" that follows can be worse than the phantom problem: a `[tool.X]` section matching its adopted bundled template exactly gets reported as stale, because `main` has since grown entries no release has shipped yet.

Keep the two axes apart in the report, because only one of them is actionable:

- **Drift** is a difference against the adopted tag. Report it.
- **Available in a newer release** is a difference between the adopted tag and a later published one. That is an upgrade note, never a DRIFT row. Confirm the version actually exists with `gh api repos/kdeldycke/repomatic/releases --jq '.[].tag_name'`.
- **Only on `main`** is unreleased and belongs in neither list. The changelog's top section is headed with a `.devN` version and a "not released yet" warning; anything described there is not yet available to any downstream repo.

### 1. Workflow audit (`workflows`)

#### Thin-caller workflows

Compare each local thin-caller workflow against its reference. These should be identical (except for files listed in `exclude`). Flag:

- Extra triggers (e.g., spurious `workflow_dispatch`).
- Missing triggers.
- Version pin drift (different `@vX.Y.Z` tag).

#### Header-only workflows (e.g., `tests.yaml`)

The header (name, `on:`, `concurrency:`) is synced automatically, but custom job content is not. Compare the job content against the reference for:

- **Stale action versions**: e.g., `actions/checkout`, `astral-sh/setup-uv` — compare pinned versions. `setup-uv` carries a second, independent pin: a `with: version: "X.Y.Z"` input naming the uv it downloads. Absent, the runner installs whatever uv is newest, leaving the tool that enforces every cooldown without one; split across two values, the fleet silently tests two resolvers. `lint-repo`'s `setup-uv-version-pin` check reports both, non-fatally.
- **Inline upstream pin with no cooldown exemption**: a `run:` command pinning the toolkit (`uvx 'repomatic==X.Y.Z' …`) under a workflow that sets `UV_EXCLUDE_NEWER` must carry `--exclude-newer-package repomatic=P0D` on the same command line, since `uvx` reads no project configuration and the pin routinely names a release published hours ago. Without it the command cannot resolve, and every `needs: metadata` job dies with it. `lint-repo`'s `self-pin-cooldown-exemption` check is fatal on this.
- **Missing workarounds**: e.g., the "Force native ARM64 Python on Windows ARM64" step that sets `UV_PYTHON`.
- **Missing matrix exclusions**: e.g., `windows-11-arm` + Python 3.10 (no native ARM64 build).
- **Outdated integration patterns**: e.g., a third-party action still in use where upstream replaced it with a `repomatic run` tool.
- **Missing coverage floor**: e.g., no `report.fail_under` under `[tool.coverage]`, so a coverage regression never fails the suite.
- **YAML scalar style issues**: e.g., `run: |` where `run: >` is needed for multi-line single commands.

#### `paths:` filters that don't fit the downstream project

Header-only sync inherits the canonical `paths:` filter verbatim (after `repomatic/**` substitution). When the project's filesystem layout doesn't match, two outcomes are possible:

- **Inherited entries that don't exist locally** (e.g., `tests/**`, `uv.lock` in a non-Python repo): the trigger never fires for them. Coverage is missing, not noisy. Recommend `[tool.repomatic.workflow.ignore-paths]` to drop them.
- **Locally relevant paths not in the canonical filter** (e.g., `install.sh`, `dotfiles/**` in a config repo): the trigger silently skips PRs that should run CI. Recommend `[tool.repomatic.workflow.extra-paths]` to append them globally, or `[tool.repomatic.workflow.paths]` keyed by filename for a per-workflow wholesale replacement.

The relevant config schema lives in `WorkflowConfig` (`repomatic/config.py`): `source_paths`, `extra_paths`, `ignore_paths`, and `paths` (per-workflow override dict, keyed by workflow filename). Per-workflow override is authoritative — it replaces the entire `paths:` list and ignores the other knobs.

#### Excluded workflows

Respect `exclude` entries from `[tool.repomatic]` in `pyproject.toml`. Report excluded files but do not flag them as drift.

### 2. Config file audit (`configs`)

Compare these files against the upstream reference. **Before flagging absence as DRIFT**, verify the file is not deliberately omitted (see "Distinguishing real drift" above):

| File                                  | What to check                                                                                                     | Absence is OK when                                                                                                                                       |
| ------------------------------------- | ----------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `pyproject.toml` `[tool.typos]`       | Missing `default.extend-identifiers` for common capitalizations (GitHub, macOS, PyPI, iOS, etc.)                  | Never: typos carries no bundled fallback, so an absent section means the canonical proper-noun map is simply inactive. Recommend `repomatic init typos`. |
| `pyproject.toml` `[tool.bumpversion]` | Missing `ignore_missing_files`                                                                                    | Project is not Python-versioned (no `[project]` table).                                                                                                  |
| `pyproject.toml` `[tool.ruff]`        | Missing or divergent lint rules, preview settings                                                                 | Always: ruff falls back to the bundled `ruff.toml` at runtime. Only flag when a local section overrides it and diverges.                                 |
| `pyproject.toml` `[tool.mypy]`        | Missing settings compared to reference                                                                            | No Python source.                                                                                                                                        |
| `.github/ISSUE_TEMPLATE/`             | Filename conventions (hyphens, not underscores), missing labels                                                   | Personal/internal repo without external bug reporters.                                                                                                   |
| `.github/code-of-conduct.md`          | Title-case headings vs upstream sentence case, plaintext email vs anti-scrape obfuscation, stale attribution URLs | Replace verbatim with upstream when divergence is detected.                                                                                              |
| `.github/funding.yml`                 | Compare with reference                                                                                            | —                                                                                                                                                        |
| `.gitignore`                          | Must be a real file: git skips an in-tree `.gitignore` reached via symlink; otherwise content vs upstream         | Auto-generated by repomatic; drift means the user should re-run sync.                                                                                    |
| `lychee.toml`                         | Note differences (usually project-specific, just flag for review)                                                 | Project doesn't run lychee.                                                                                                                              |

**Skip** files that are intentionally excluded via `exclude` in `[tool.repomatic]`. Cross-check `[tool.ruff] extend-exclude` and similar before flagging "missing" entries.

### 3. Agent instructions audit (`agent`)

**Read `[tool.repomatic] agent.location` first.** That key is the answer, and it defaults through `[tool.repomatic.flavor] agent` to the selected runtime's own filename (`./claude.md` for Claude Code). Only when the repository sets neither, and nothing sits at the default, is guessing warranted:

- Check `subagents.location` and `skills.location` for a sub-directory (like `dotfiles/.claude/`); if those are set, look beside them.
- Try the common alternates: `claude.md`, `CLAUDE.md`, `AGENTS.md`, `.claude/CLAUDE.md`.

A file found by guessing is one `repomatic init agent` will not write to. Say so, and recommend setting `agent.location` to it: that is the whole fix, and it turns the push direction below from unreachable into a one-command sync.

**Read the audience tags before judging anything.** Upstream marks every section with an HTML comment right under its heading, and that comment answers the question this audit used to answer by eye:

```markdown
### Version formatting

<!-- audience: all -->
```

`audience: all` and `audience: downstream` sections belong to upstream and are pushed down by `repomatic init agent`. `audience: upstream` never leaves `kdeldycke/repomatic`. A `; scope: package` qualifier narrows a section to repos that build a distributable, so a uv virtual project skipping one is correct, not missing. A section with **no tag at all** is the repository's own.

That splits the work into two directions, and they are not symmetric:

**Push (mechanical, do not hand-edit).** For each tagged local section, compare its body against upstream's. Any difference is stale, whichever side looks better: the fix is to run `repomatic init agent`, never to hand-patch the section or to propose the local wording upstream. Report the count and name the sections, but do not draft the diff. A tagged section upstream no longer sends here (retagged `upstream`, or scoped away) is an orphan the same command prunes.

**Pull (analytical, this is your job).** Untagged local sections are where repo-specific knowledge lives and are correct by default. Read them for two things:

1. **Content that generalizes.** A section describing something every repomatic consumer faces (how a workflow is regenerated, what a sync owns, how a pinned tool moves) is an upstream proposal. Say which audience it would carry, and check that no tagged section already covers it under a different title.
2. **Content that upstream has since replaced.** A local section on a subject upstream now covers under a *different heading* is stale and will not be adopted, because the merge keys on the title. That is what upstream's `<!-- supersedes: {old title} -->` is for: propose adding one rather than asking the repo to delete its section.

**Degrade gracefully when the file carries no tags at all.** The `agent` component is opt-in, so a repository may never have run it. Say so once, treat the whole file as untagged repo-owned content, and audit only the pull direction. Do not hand-classify the file section by section against upstream: recommending `repomatic init agent` is both the smaller message and the durable fix.

**A downstream instructions file is not a copy of upstream, tags or no tags.** Personal or project conventions (voice, commit policy, shell patterns, language preferences) are deliberately absent upstream and must never be proposed for it, since upstream ships to repos with outside contributors where several such rules are wrong advice.

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

- Apply mechanical fixes by pushing to `main`: the `sync-repomatic` autofix job reconciles thin-caller workflow drift, and `lint.yaml` flags remaining metadata issues.
- Make manual edits for header-only workflow drift and config changes that sync cannot fix.
- `/sphinx-docs-sync` to audit `docs/` against the upstream `kdeldycke/repomatic` reference when this repo has a Sphinx documentation tree. The `sphinx-docs` agent (`.claude/agents/sphinx-docs.md`, opt-in via `repomatic init subagents/sphinx-docs`) holds the canonical conventions for `configuration.md`, `cli.md`, `install.md`, `conf.py`, and the standard page roster — recommend opting in when the repo has Sphinx docs that drift from upstream patterns.

If the audit surfaces a generator behavior that produces unwanted output (e.g., a thin-caller trigger the user wants gone, a header `paths:` filter that doesn't fit), fix it in the upstream tool (`repomatic/github/workflow_sync.py`, `repomatic/config.py`) rather than asking the user to hand-patch the generated file every time `repomatic init` runs.
