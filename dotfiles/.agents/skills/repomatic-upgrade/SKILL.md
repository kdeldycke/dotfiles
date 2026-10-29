---
name: repomatic-upgrade
description: Apply what a newer `repomatic` release lets this repository adopt, reuse or drop, then audit its alignment with the tag it now pins. Use after `repomatic init` moved the upstream pin, or to check a repository against upstream conventions.
compatibility: 'Designed for Claude Code. Recommended model: Opus.'
allowed-tools: Bash Read Grep Glob Edit Write WebFetch Agent
argument-hint: '[vOLD vNEW] [all|workflows|configs|upstream]'
---

## Context

!`grep -rhoE 'kdeldycke/repomatic/[^@]+@.*v[0-9]+\.[0-9]+\.[0-9]+' .github 2>/dev/null | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+$' | sort -uV | tail -1 | sed 's/^/ADOPTED_PIN /'`

!`git diff HEAD -- .github 2>/dev/null | grep -E '^-.*kdeldycke/repomatic/.*v[0-9]+\.[0-9]+\.[0-9]+' | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+$' | sort -uV | head -1 | sed 's/^/PREVIOUS_PIN_UNCOMMITTED /'`

!`git log -1 --format='LAST_WORKFLOW_COMMIT %h %ad %s' --date=short -- .github/workflows 2>/dev/null`

!`[ -d ../repomatic/.git ] && echo "SIBLING_CHECKOUT ../repomatic" || echo "NO_SIBLING_CHECKOUT"`

!`[ -f repomatic/__init__.py ] && echo "CANONICAL_REPO" || echo "DOWNSTREAM"`

!`ls .github/workflows/*.yaml 2>/dev/null`

!`grep -h 'uses:.*kdeldycke/repomatic' .github/workflows/*.yaml 2>/dev/null | head -5`

!`grep -A5 '\[tool.repomatic\]' pyproject.toml 2>/dev/null || echo "No [tool.repomatic] section"`

!`grep -E '^(subagents|skills|gitignore)\.location' pyproject.toml 2>/dev/null`

## Instructions

You bring a downstream repository in line with `kdeldycke/repomatic`, and you do it in two passes in one session. The first pass works the delta of a newer release. The second audits how far the repository has drifted from the tag it now pins. `/repomatic-audit` used to be the second pass as a skill of its own: the pin bump is the moment to look at the integration as a whole, so both passes now share one report.

`repomatic init` prints the command launching this skill as its last next step when it moves the upstream pin. The `sync-repomatic` upgrade pull request invites the maintainer to run it, and so does the `sync-workflow-pins` one when a bump moves `repomatic`.

**This skill is for downstream repos only.** If the context shows `CANONICAL_REPO`, tell the user this skill is not applicable.

### Determine invocation method

Use `uvx --exclude-newer '{window}' --exclude-newer-package repomatic=P0D --from 'repomatic==X.Y.Z' -- repomatic`, with `X.Y.Z` the `ADOPTED_PIN` the context shows. Read `{window}` from the `UV_EXCLUDE_NEWER` value of any `.github/workflows/*.yaml`, which `repomatic init` renders from `[tool.repomatic] minimum-release-age`. The pin keeps the tool registry (`ruff`, `typos`, `mypy` versions) identical to what CI runs, and the cooldown gates the dependency tree while keeping a fresh release installable. References to `<cmd>` below resolve to it.

### Read the scope and the version pair

Both values come from `$ARGUMENTS`, in any order, and neither constrains the other.

- **The version pair** drives the first pass, which runs whenever a previous pin is known. Take it from the first source that carries it:
  1. A `vOLD vNEW` pair in `$ARGUMENTS`.
  2. The uncommitted diff: the removed `uses:` lines carry the previous pin, the added ones the adopted pin. The context prints it as `PREVIOUS_PIN_UNCOMMITTED`.
  3. The last upgrade commit: `git log -p -1 -- .github/workflows`, reading the previous pin off its removed `uses:` lines.
  4. Nowhere: the first pass has no delta to review. Skip it and audit alone.
- **The scope** drives the second pass, and defaults to `all`:
  - `all`: run every audit area below.
  - `workflows`: audit workflow files only.
  - `configs`: audit non-workflow config files only.
  - `upstream`: identify downstream innovations that could be contributed back to `repomatic`.

### Sort a finding into drift or an upgrade note

Keep the two axes apart in the report, because only one of them is actionable:

- **Drift** is a difference against the adopted tag. Report it.
- **Available in a newer release** is a difference between the adopted tag and a later published one. That is an upgrade note, never a DRIFT row. Confirm the version actually exists with `gh api repos/kdeldycke/repomatic/releases --jq '.[].tag_name'`.
- **Only on `main`** is unreleased and belongs in neither list. The changelog's top section is headed with a `.devN` version and a "not released yet" warning; anything described there is not yet available to any downstream repo.

### Fetching reference files

Fetch every reference file at **the version the downstream repo has actually adopted**, never at the tip of `main`. The Context block above prints the `uses:` pins; take the tag from there and pass it as `ref` on every call:

```shell-session
$ gh api "repos/kdeldycke/repomatic/contents/{path}?ref=vX.Y.Z" --jq '.content' | base64 -d
```

An unpinned fetch resolves to `main`, which carries unreleased work. Audited against it, every change waiting for the next release reads as downstream drift, and the "fix" that follows can be worse than the phantom problem: a `[tool.X]` section matching its adopted bundled template exactly gets reported as stale, because `main` has since grown entries no release has shipped yet.

### Distinguishing real drift from intended absence

Before flagging an issue, verify that the gap isn't **deliberate** or covered by a runtime mechanism. Common false positives:

- **`[tool.repomatic] exclude` is authoritative.** Files listed there (like `workflows/changelog.yaml` or `labels`) are intentionally absent on disk. Do **not** report them as MISSING.
- **`[tool.repomatic] lint-repo.declined` records a decision.** Each entry names one bundled template entry that a `[tool.X]` section leaves out, with the reason. Do **not** report that entry as DRIFT. Report the record itself when `lint-repo` says it declines nothing.
- **Bundled defaults applied at runtime.** Some config is materialized from the bundled template at runtime when the file is absent, so no on-disk copy is needed. **Absence of these files is not a problem**: it is the intended state when the user is happy with the bundled policy. Only flag DRIFT if the user wants to deviate from it. Exactly five tools carry such a fallback, the ones whose `ToolSpec` sets `default_config` in `repomatic/tooling/registry.py`: `actionlint`, `mdformat`, `ruff`, `yamllint` and `zizmor`.
- **A `[tool.X]` section is never a candidate for deletion.** The inverse of the rule above, and the more expensive mistake. Every other tool has no `default_config`, so its resolution chain has no level 3 to fall back on: `lychee`, `typos`, `mypy`, `pytest`, `coverage`, `bumpversion` and `uv` are *deployed* into `pyproject.toml` by `repomatic init`, and that section is the only config the tool will ever see. Deleting it does not restore inheritance from a bundled default, it drops the tool to level 4 and runs it bare, silently discarding every rule the section held. Read the tool's `default_config` before proposing a section be dropped "to inherit upstream updates". Re-running `repomatic init` fixes a stale section only for the components marked `SyncMode.ONGOING` in `repomatic/components.py` (`lychee`, `typos`, `bumpversion`, `uv`). It never revisits a `mypy`, `pytest` or `coverage` section after the first write: `lint-repo` warns on each bundled template entry such a section lacks, to copy by hand or to decline with a reason under `[tool.repomatic] lint-repo.declined`.
- **Generator artifacts vs user error.** When local thin-callers diverge from upstream (e.g., extra `workflow_dispatch:`, missing `paths:`), the cause may be the **upstream generator**, not downstream tampering. Inspect `repomatic/github/workflow_sync.py` (`generate_thin_caller`, `_adapt_trigger_paths`, `generate_workflow_header`) before recommending the user re-run `repomatic init` to "fix" something `init` itself produced.
- **Project-level `claude.md` may live under a sub-directory.** `[tool.repomatic] subagents.location` and `skills.location` indicate a project where `.claude/` is not at the root (e.g., dotfiles repos with `dotfiles/.claude/CLAUDE.md`). Search the configured location, not just `./CLAUDE.md`.

When in doubt, search the upstream codebase to confirm whether a behavior is intentional. Read `[tool.repomatic]` in the local `pyproject.toml` carefully before declaring anything missing.

### Pass 1: work the release delta

#### Read the delta

- **Fetch the changelog at the adopted tag, never at `main`.** `gh api "repos/kdeldycke/repomatic/contents/changelog.md?ref=vNEW" -H "Accept: application/vnd.github.raw"`. Read every section from `vNEW` down to, and excluding, `vOLD`. A section the changelog no longer holds sits in `docs/changelog-archive.md` at the same ref. `main` carries unreleased work under a `.devN` heading, and none of it is available to this repository yet.
- **Sort every bullet into one of five bins.** Breaking: a renamed job, workflow input, config key or command the repository uses, which must be acted on. Adopt: a new config key, job, skill, CLI option or template this repository would use. Drop: a fix that makes a local workaround, pin or custom step obsolete. Simplify: a hand-maintained piece that `repomatic init` or a workflow now produces. Skip: docs, internals, test work, and jobs marked upstream-only.
- **Read the GitHub release notes only when a changelog bullet is unclear.** `gh api repos/kdeldycke/repomatic/releases --jq '.[] | select(.tag_name == "vNEW") | .body'` repeats the changelog section, so it adds nothing on its own.

#### Map the delta to this repository

For each bullet outside the skip bin, find what it touches here. Grep the source tree, `.github/`, `pyproject.toml` and `docs/`:

- **A new `[tool.repomatic]` key or workflow input.** Look in `pyproject.toml` and the header-only workflows for a hand-rolled equivalent the key now replaces, like a custom `paths:` list or a local step.
- **A new job, skill or subagent.** Check `[tool.repomatic] exclude` before proposing it: an excluded component is a decision, not a gap.
- **A dropped or renamed surface.** Grep `tests.yaml`, any other header-only workflow, and local scripts for the old name.
- **An upstream fix.** Search comments and workflow steps for the workaround it retires: `work around`, `XXX`, `TODO`, version-guarded branches, and inline pins of the tool it fixed.
- **A generator change**, like a thin caller gaining a trigger or a header gaining `paths:`. Read `git diff HEAD -- .github/workflows` against the changelog, so a diff the release explains is never reported as drift. When the upgrade is already committed, that diff is empty: clone `HEAD` into a scratch directory, point its `origin` at the GitHub URL, run `<cmd> init --no-cooldown` there and read `git status`. A clean tree proves the commit regenerated every managed file instead of moving the pins by hand.
- **A changed job.** Before you report it as adopted, call the released code on this repository's real inputs. An open pull request from that job shows only what its last run did, and that run can predate the adopted pin. A job that reads a file from another project also stops working when that file moves. A change to the binary build shows only in the self-test of the binaries `Build & release` compiles, which the Tests workflow never runs: read that run on the push that adopts the pin.
- **A synced skill or subagent.** `repomatic init` rewrites every bundled copy verbatim, so the upgrade also reverts each local commit made to one since the last sync. Take every copy under `skills.location` and `subagents.location` as it stood before the upgrade. That is `HEAD` while the upgrade is uncommitted, and the upgrade commit's parent once it landed. Compare it with upstream's `.claude/skills/{name}/SKILL.md` or `.claude/agents/{name}.md` at `vOLD`. Read those paths, not `repomatic/data/skills/`: its entries are symlinks, and `git show` returns their target path. A copy that matches neither `vOLD` nor any upstream commit between the two tags carries local edits. Upstream holds them already when they were ported before the release. To know, write the three states to files and run `git merge-file -p {vNEW copy} {vOLD copy} {local copy}`. An output equal to the `vNEW` copy means the upgrade drops nothing. Any other output holds edits that the upgrade drops, so report them as a `breaking` row.
- **A new `lint-repo` check.** Run `<cmd> lint-repo --repo {owner}/{repo}` and read its line: a check that passes here offers nothing. Without `--repo`, a local run has no `$GITHUB_REPOSITORY`, so every API-backed check drops out of the output.
- **A seeded tool config that lacks a bundled template entry.** `init` writes `[tool.ruff]`, `[tool.pytest]`, `[tool.coverage]`, `[tool.mypy]` and `[tool.mdformat]` once, and `lint-repo` names each entry such a section lacks. Copy the entry when it applies here. Record one that the repository leaves out on purpose under `[tool.repomatic] lint-repo.declined`, with the reason its instructions or comments give. The key is the tool, then the path of the entry in its section, like `mypy.warn_unreachable = "{reason}"`. For one member of a list, add the member as `lint-repo` prints it, like `pytest.addopts."--numprocesses=logical" = "{reason}"`. Ask the user when no reason is stated. Never copy an entry only to silence the warning.
- **A tool the registry bumped.** The changelog often leaves a tool version bump out. Run `<cmd> run mypy` and `<cmd> run ruff -- check --no-fix` once on the untouched tree, then the same two commands at `vOLD`. A finding that only the new pin reports is a row. When the release adds the gating job itself, every finding it fails on is a row, old ones included. A new `mypy` error is a `breaking` row: the `lint-types` job fails on it. So is a new `ruff` finding that no safe fix clears, which fails `lint-python`.

### Pass 2: audit the repository

Run the areas the scope names, and apply the rules in § Distinguishing real drift from intended absence to every finding.

#### Ask the generator first

Before you compare a managed file by hand, run the adopted release's generator on a throwaway copy of `HEAD`:

```shell-session
$ git worktree add --detach {scratch}/audit HEAD
$ uvx --no-progress --exclude-newer '{window}' --exclude-newer-package repomatic=P0D --directory {scratch}/audit 'repomatic==X.Y.Z' init
$ git -C {scratch}/audit diff
$ git worktree remove --force {scratch}/audit
```

Read `{window}` from the `UV_EXCLUDE_NEWER` value of any `.github/workflows/*.yaml`, which `repomatic init` renders from `[tool.repomatic] minimum-release-age`.

An empty diff means every thin caller, each header-only workflow header and each ongoing-sync `[tool.X]` section equals what that release generates. Any hunk is DRIFT that the sync would rewrite. Keep `--directory`: `--output-dir` alone writes into the copy but reads `[tool.repomatic]` from the directory the command started in.

The generator does not read hand-owned jobs, the comment beside a synced key, or an entry only the local file carries. Compare those yourself, in the sections below.

#### 1. Workflow audit

Compare each local thin-caller workflow against its reference. These should be identical (except for files listed in `exclude`). Flag:

- Extra triggers (e.g., spurious `workflow_dispatch`).
- Missing triggers.
- Version pin drift (different `@vX.Y.Z` tag).

The header (name, `on:`, `concurrency:`) is synced automatically, but custom job content is not. Compare the job content against the reference for:

- **Stale action versions**: e.g., `actions/checkout`, `astral-sh/setup-uv` — compare pinned versions. `setup-uv` carries a second, independent pin: a `with: version: "X.Y.Z"` input naming the uv it downloads. Absent, the runner installs whatever uv is newest, leaving the tool that enforces every cooldown without one; split across two values, the fleet silently tests two resolvers. `lint-repo`'s `setup-uv-version-pin` check reports both, non-fatally.
- **Inline upstream pin with no cooldown exemption**: a `run:` command pinning the toolkit (`uvx 'repomatic==X.Y.Z' …`) under a workflow that sets `UV_EXCLUDE_NEWER` must carry `--exclude-newer-package repomatic=P0D` on the same command line, since `uvx` reads no project configuration and the pin routinely names a release published hours ago. Without it the command cannot resolve, and every `needs: metadata` job dies with it. `lint-repo`'s `self-pin-cooldown-exemption` check is fatal on this.
- **Missing workarounds**: e.g., the "Force UTF-8 encoding on Windows" step that sets `PYTHONIOENCODING`.
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

#### Read the CI state

A file can match its reference and still fail. Read the latest runs on the default branch, the open autofix pull requests and the open bot issues:

- A job that fails on every push is a finding, whatever its files look like.
- An autofix pull request that stays open across many pushes means a tool and the files it rewrites disagree.

#### 2. Config file audit

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
| `pyproject.toml` `[tool.lychee]`      | Note differences (usually project-specific, just flag for review); a root `lychee.toml` wins as native config     | Project doesn't run lychee.                                                                                                                              |
| `pyproject.toml` `[tool.gitleaks]`    | An allowlist alone replaces the built-in rules, so the scan finds nothing. It needs `extend.useDefault = true`    | No `[tool.gitleaks]` section: gitleaks keeps its built-in rules.                                                                                         |

**Skip** files that are intentionally excluded via `exclude` in `[tool.repomatic]`, and settings declined under `lint-repo.declined`. Cross-check `[tool.ruff] extend-exclude` and similar before flagging "missing" entries.

#### 3. Upstream contribution opportunities

Scan the downstream repo for patterns, workarounds, or configurations that are **better** than or **missing from** the upstream reference. These are candidates for contributing back to `kdeldycke/repomatic`. Look for:

- **Broader test matrices**: e.g., more OS variants, extra Python versions, additional architecture coverage that upstream could adopt as defaults.
- **Workarounds for known issues**: Steps or configs that fix CI failures or edge cases that upstream hasn't addressed yet.
- **Better tool configurations**: e.g., ruff `extend-include` patterns, pytest addopts, coverage settings that are more complete than upstream.
- **Useful `pyproject.toml` patterns**: e.g., dependency group definitions, build config, or tool settings that could be generalized.
- **Custom workflow steps**: Reusable patterns in header-only workflows (e.g., package install verification, environment variable passing) that could become part of the reference workflow.
- **Documentation improvements**: bundled skill or subagent guidance, issue templates, or repo metadata patterns that would benefit all downstream repos. Upstream no longer syncs instructions-file content into a consuming repo, so a convention worth spreading belongs in a skill or a subagent, never in a proposed `claude.md` section.

For each candidate, assess:

1. **Generalizability**: Would this benefit most downstream repos, or is it project-specific?
2. **Complexity**: Is it a simple config change or a significant workflow redesign?
3. **Action**: Suggest filing as a GitHub issue or PR at `kdeldycke/repomatic`, with a draft title and description.

### Report

One record per pass, then one hand-off for both.

**Pass 1 table.** Changelog entry, bin (`breaking`, `adopt`, `drop`, `simplify`), where it lands in this repository, and the action. Order the rows breaking first, then by rising effort. Close with the entries that offer nothing for this repository, in one line, so the user knows they were read. A first pass that did not run, because no previous pin was found, has no table.

**Pass 2 table.** Item, one status per finding (`MATCH`, `DRIFT`, `MISSING`, `N/A`), and a brief description. Group by severity, functional issues first, then consistency, then cosmetic. For each issue, state what the current state is, what the reference has, and the recommended fix.

**Status guide:** `MATCH` matches the reference, or differs only cosmetically. `DRIFT` exists and diverges in a way the user likely wants to fix. `MISSING` is expected but absent, and only where the absence is a genuine problem: an absence covered by `[tool.repomatic] exclude`, runtime materialization or a tool-registry default is `N/A` instead. `N/A` does not apply to this project. When unsure between `DRIFT` and `N/A`, lean `N/A` and explain in the description; over-flagging produces noisy reports the user has to refute.

### Apply

1. **Apply one row at a time, breaking rows first.** Keep each change readable on its own in `git diff`. Pass 2 findings wait until every pass 1 row is settled.

2. **Keep the local edits a synced copy carries.** Restore the file as it stood before the upgrade when upstream left it unchanged between the two tags. Otherwise keep that `git merge-file` output as the new copy, once its conflicts are resolved. To re-apply one local commit instead, `git apply -C1` gets past a context line upstream reworded. Then port the edits upstream, as step 4 describes, or the next sync reverts them again.

3. **Run the local checks after each row.** The project's tests, `mypy` and `ruff`, plus `<cmd> lint-repo --repo {owner}/{repo}` when the row touched `.github/` or `pyproject.toml`. After a row that touched a workflow, also run `<cmd> run actionlint`, which parses its `${{ }}` expressions. A failing check vetoes the row: revert it and note it in the report. Never loosen a test to pass.

4. **Send generator problems upstream, as edits in the sibling checkout.** When a row needs a change in `repomatic` itself (a generator writing something unwanted, a missing knob, a docs gap, a lesson a synced copy carries) and the context shows `SIBLING_CHECKOUT`, implement it in `../repomatic`: the code, the tests it breaks, and a changelog bullet. Verify it there. `repomatic run typos` and `mdformat` rewrite files in place and print no findings, so judge them by `git diff`. Another session may share that checkout: edit only the files the row needs, and name them in the report so they can be committed by pathspec. Leave every change uncommitted. Without a sibling checkout, describe the change in the report instead.

5. **Never commit, push, or open an issue or pull request.** The user reviews the working tree and decides.

6. **Close with two short lists.** Keep the tables as the record, then end the answer with two lists, a few words per item, in place of prose about what was applied or skipped:

   - **Done**: each applied row, with the files it changed, from either pass. A `breaking` row carries the detail it needs as sub-bullets here, and a row that needed no local edit stays in its table's closing line.
   - **Left to do**: each remaining action, ordered so it can be executed top to bottom, prefixed with one of these five labels and nothing else. Put `Decide:` items first, since an answer can add work below them.
     - `Decide:` a change this pass proposed and the user has not approved, or a choice between options. End the item with the answer you recommend.
     - `Implement:` code or a docs entry to write, naming the checkout when it is not this one.
     - `Commit:` uncommitted changes, naming each repository and path.
     - `Push:` commits made but not on the remote.
     - `Report:` an issue or comment to file upstream, naming the project and the draft's path.

   An item that fits none of the five is a plain bullet whose first word is the verb. Write "none" for an empty list, and add no closing summary.

### What not to touch

- **An adoption that needs a token, a service or a new external setup.** List it with a recommendation and leave it to the user. Apply the `adopt` rows that need only configuration.
- **A deviation `[tool.repomatic] exclude`, `include` or `lint-repo.declined` records.** Those are decisions.
- **A major-version migration that needs broad rework.** Report it and stop.

### After running

Suggest the user run:

- `/repomatic-deps modernize` when the upgrade also moved `uv.lock`.
- `/repomatic-changelog add` for the downstream changelog bullet, when the repository keeps one.
- `/sphinx-docs-sync` to align `docs/` with the upstream `kdeldycke/repomatic` reference, when this repository has a Sphinx documentation tree. The `sphinx-docs` agent (`.claude/agents/sphinx-docs.md`, opt-in via `repomatic init subagents/sphinx-docs`) holds the canonical conventions for `configuration.md`, `cli.md`, `install.md`, `conf.py`, and the standard page roster.

Apply the mechanical fixes by pushing to `main`: the `sync-repomatic` autofix job reconciles thin-caller workflow drift, and `lint.yaml` flags remaining metadata issues.
