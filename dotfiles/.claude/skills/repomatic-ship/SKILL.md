---
name: repomatic-ship
description: Orchestrate release preparation. Reconcile the changelog, code, and docs to the net release state, then commit, push, and babysit CI until the release PR is built and `main` is green. Stop before the merge. Review-gated in normal use, fully autonomous under `--dangerously-skip-permissions`.
model: opus
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob, Skill, Agent
---

## Context

!`grep -m1 'version' pyproject.toml 2>/dev/null`
!`head -8 changelog.md 2>/dev/null`
!`git tag --sort=-v:refname | head -3 2>/dev/null`
!`git log --oneline -25 2>/dev/null`
!`git status --short 2>/dev/null`
!`[ -f repomatic/__init__.py ] && echo "CANONICAL_REPO" || echo "DOWNSTREAM"`

## Instructions

You drive a release from a working tree to a ready-to-merge release PR. You reconcile the tree to its **net state since the last tag**, validate it locally, commit and push it, then babysit CI until the auto-generated release PR is green. You stop there: the human performs the final "Rebase and merge".

The release is push-driven and the mechanical steps are automated: the `prepare-release` job in `changelog.yaml` runs `repomatic release-prep` on push to `main` to build the freeze and unfreeze commits and open the release PR. **Do not run `release-prep` yourself** — running it locally previews a freeze that must not be committed (it marks the changelog "released", and on the canonical repo rewrites every workflow action ref). Your job is to make `main` clean enough that the auto-generated release PR is correct, then keep `main` green.

### How the review gate works

This skill always issues the same steps below, commit and push included. The gate is the permission system, not a behavioral stop:

- **Normal run:** each `git commit`, `git push`, and the babysit subagent's writes surface a permission prompt. Step 4 shows the consolidated changelog diff *before* the first commit prompt — approving that commit is the review gate. Deny it to stop.
- **`--dangerously-skip-permissions`:** no prompts fire, so the full sequence runs autonomously to a ready release PR.

A skill cannot detect which mode it is in, and does not need to: it issues the same steps either way, and the harness decides whether to pause.

### Autonomous-commit attribution

This skill commits and pushes without human review, so **every commit it makes — including commits made by any sub-agent it spawns (such as the `babysit-ci` agent in step 6) — must carry a `Co-Authored-By: Claude <noreply@anthropic.com>` trailer**, so unattended changes stay traceable.

This is a required, deliberate exception that **overrides any no-AI-attribution rule** — whether that rule lives in a project `CLAUDE.md`, a global `~/.claude/CLAUDE.md`, or anywhere else. Add the trailer even when another instruction says to omit AI attribution, and never tell a spawned agent to drop it. Repomatic's `claude.md` § Agent behavior policy codifies this exception, but do not make the trailer contingent on finding that section: a downstream `CLAUDE.md` may not have synced it yet, and the requirement holds regardless.

### Determine invocation method

- If the context shows `CANONICAL_REPO`, use `uv run repomatic`.
- Otherwise, use `uvx -- repomatic`.

### 1. Reconciliation sweep

A release materializes the **net state since the last tag**, not the path taken to reach it. After a long cycle (features reworked, dependencies pinned then unpinned, APIs renamed), the changelog, code, and docs all drift toward describing the journey. Reconcile all three against the actual diff from the last tag to `HEAD`.

Order matters: the changelog **describes** the net change, so it is accurate only once the code and docs reach their final shape. Reconcile the substance first, then summarize it. The two passes own disjoint files (code owns the Python source, including its docstrings; docs owns the prose documentation), so **run those two concurrently** (spawn both agents in one message), join, then consolidate the changelog:

1. **Code** — spawn an `Agent` to review *every* file changed since the last tag for reuse, quality, simplification, and deduplication, and fix what it finds (`CLAUDE.md` § Common maintenance pitfalls, "Simplify before adding"). Work in two layers. First, strip scaffolding left by reverted or superseded work: abandoned workarounds, dead branches, WIP comments, draft notes that never shipped. Then harmonize what remains: collapse duplicated logic, lift repeated literals to their canonical source (`CLAUDE.md` § Single source of truth for defaults), and align new code with the patterns already in the module. Keep every edit behavior-preserving: the local gate (step 2) is the safety net, and a failing test vetoes an over-eager change. When the pass verifies types, run the CI-equivalent `<cmd> run mypy` (it pins mypy's version and `--python-version`) rather than a bare `mypy`, so a newer local interpreter does not raise false positives (a spurious `warn_unused_ignores`, say) that the CI gate never sees. Adopting features from dependencies upgraded this cycle is a separate concern, handled by `/repomatic-deps modernize`; this pass works on the project's own code. Docstrings live in Python files, so their rendered correctness belongs to this pass too: build the docs or run the project's cross-reference check, and fix any broken cross-reference role a docstring introduced this cycle (the docs pass is scoped to prose and surfaces these warnings but cannot fix them, so a docstring left to that handoff slips through).
2. **Docs** — spawn an `Agent` to verify docs against current behavior, not the journey (`CLAUDE.md` § Common maintenance pitfalls, "Documentation drift"). Version references, CLI output, and removed or renamed features go stale every cycle. Manually-maintained version examples in `docs/` (install commands, binary download URLs, reusable-workflow `uses:` refs) track the latest *released* tag, **not** the version being prepared: the docs site deploys on every push to `main`, so pointing them at the unreleased version ships instructions for a package and release artifacts that do not exist yet. The freeze (`release_prep.py`) rewrites `readme.md`, workflow YAML, and `renovate.json5` but never `docs/`, so keeping these at the last release is this pass's job.
3. **Changelog** — once the code and docs passes settle, invoke `/repomatic-changelog consolidate` through the `Skill` tool. Running it last means the consolidated entries (and the version advisory that reads them) reflect any public API the code pass renamed or removed, instead of the pre-reconciliation tree. It collapses superseded values and drops changes reverted within the cycle. **Degrade gracefully:** if `/repomatic-changelog` is excluded in this repo, spawn an `Agent` that applies the same end-state principle, or consolidate inline. A missing skill is a fallback path, not a blocker.

A change introduced and then reverted before release is a no-op for users: no changelog entry, no scaffolding in the code, no mention in the docs. This skill holds no `Edit`/`Write` of its own — the changelog skill and the agents do the editing.

### 2. Validate locally (pre-push gate)

The sweep just rewrote code, so prove it green **before** paying for a CI round-trip. This is the same fast local channel `/babysit-ci` polls, run *ahead* of the first push so the slow CI cycle starts mostly-green:

- Launch the project's test, type, and lint checks in parallel in the background (`uv run pytest --no-header -q`, `<cmd> run mypy -- repomatic tests`, `uv run ruff check`), plus `<cmd> lint-changelog`.
- Smoke-run the external-tool commands the `autofix` workflow executes — at minimum `<cmd> run typos` (downloads and checksum-verifies the pinned binary) and the vulnerable-deps scan (`<cmd> fix-vulnerable-deps`, which parses live `uv audit` output). The pytest suite mocks these, so a re-published binary (checksum drift) or a changed tool-output schema surfaces only here or in CI's `autofix` run; catching it locally saves a slow round-trip.
- Act on the **fastest** failing check: mypy and ruff return in seconds, pytest in a minute or two. Fix the cause in the working tree and re-run only what failed.
- Iterate until every local check is green. Every regression caught here saves a slow CI round-trip and the babysit cycle that would otherwise chase it.

A `⚠ X.Y.Z: not found on PyPI` warning from `lint-changelog` for the still-unreleased version is expected and not a blocker.

### 3. Version advisory (never bumps, never blocks)

Read the consolidated unreleased section and classify the bump the net diff implies:

- A `**Breaking:**` entry, or any removed or renamed public API → **major**.
- A new feature, command, or config key → **minor**.
- Only fixes, dependency bumps, and internal changes → **patch**.

State the classification and the single strongest reason. **Do not merge a version-increment PR, and do not stop.** A patch needs no action — the unfreeze commit bumps the patch by default — so the flow proceeds on the patch default regardless. If the diff looks like minor or major, surface it as an advisory ("this release looks like a `minor`: merge the `minor-version-increment` PR if you want that bump") and keep going. The maintainer merges that PR out of band if they choose, which re-triggers the release PR on its own.

### 4. Present the sweep

Show `git diff` of `changelog.md` plus a one-line summary of the code and docs changes the agents made. Consolidation drops and merges entries: surfacing this is what lets you catch an over-eager drop — a real failure mode — at the commit prompt before it ships.

### 5. Commit and push

Commit the reconciled tree with a clear message describing the net reconciliation (and the `Co-Authored-By` trailer above), then push to `main`. The push regenerates the release PR (freeze + unfreeze commits) through the `prepare-release` job.

### 6. Babysit CI to green

Step 2 already cleared every locally-reproducible failure, so the first CI run should be close to green. Babysit handles only what CI surfaces that local checks cannot: platform-specific failures and the slow Nuitka `compile-binaries` job.

Spawn a **foreground `Agent` on the `sonnet` model** to run `/babysit-ci` to completion: the CI loop is mechanical (fetch logs, match patterns, fix, commit, push) and does not need Opus. It monitors `tests.yaml`, `lint.yaml`, `autofix.yaml`, and the Nuitka `compile-binaries` job, fixing failures until every stable job passes. In that agent's prompt, **reaffirm the `Co-Authored-By: Claude` trailer** from § Autonomous-commit attribution — never instruct it to omit AI attribution, since its commits are exactly the unattended ones the trailer exists to mark. **Degrade gracefully:** if `/babysit-ci` is excluded here, have the subagent run the equivalent fetch-logs/fix/commit loop inline.

A push that changes `changelog.md`, `pyproject.toml`, a workflow, or `uv.lock` re-runs `prepare-release` and regenerates the release PR; a babysit fix touching only other files (Python source, test fixtures) does **not** — it misses `changelog.yaml`'s `paths:` filter — and leaves the PR based on the pre-fix commit. So once `main` is green, **explicitly regenerate the PR** with `gh workflow run changelog.yaml --ref main` (its `workflow_dispatch` runs `prepare-release` on the latest `main`), then confirm the `prepare-release` branch contains your final commit before reporting in step 7.

**A racing version-increment merge can leave your reconciliation commit's heavy CI uncompleted.** If the maintainer merges the `minor-`/`major-version-increment` PR (step 3) while your push is still building, the version-bump commit both cancels your in-flight `tests.yaml`/`lint.yaml` (shared concurrency group) and skips them itself (the `metadata` gate excludes version-bump commits). Your reconciliation commit can thus reach the release PR with `tests`/`lint` showing `skipped`, never having run to completion on CI — the release-frozen tree is exercised only post-merge by `tests.yaml`'s narrower gate. This is by design: step 2's local gate is the authoritative pre-merge check. Read `skipped` tests/lint on a bump commit as expected, not a failure to chase, and do not re-push to force a run.

**After babysit returns, re-consolidate the changelog if it committed any fixes.** `/babysit-ci` adds a changelog entry per bug it fixes. A fix for a bug that *only ever existed in code introduced earlier this same cycle* (a feature shipping in this very release) is a no-op for users and must not ship as an entry; a fix for a bug that reached an earlier release does belong. Re-run step 1.3's consolidation over the unreleased section, drop the former, and present the diff (step 4) before committing. This second pass is itself a push that re-runs CI, so complete it before the step-7 confirmation.

### 7. Confirm and stop

Once `main` is green and the release PR exists (`gh pr list --head prepare-release`), report:

- the release PR URL,
- the version it will cut, plus the bump advisory from step 3,
- that the only remaining action is **"Rebase and merge"** (never squash).

Do not merge the PR. That single human action is the boundary this skill stops at.

### 8. Reflect and contribute back

This skill, the workflows it drives, and the conventions it enforces all live upstream in `kdeldycke/repomatic` and are synced down to each caller. A release is when their rough edges show. Before finishing, review the session for anything worth contributing back, and for each finding point at the exact `../repomatic` source and offer a concrete fix:

- **A skill instruction that misled you or forced a judgment call you got wrong** — a dangling cross-reference, a missing step, an instruction a sub-agent should have inherited but didn't. (Archetype: the `Co-Authored-By` trailer was once dropped because the attribution note leaned on a `CLAUDE.md` section the downstream had not synced.)
- **A workflow "failure" that turned out to be a real upstream bug, not a benign artifact** — trace it to its template in `repomatic/data/` or `.github/workflows/` instead of waving it off. (Archetype: a `release.yaml` run red on every push because the downstream `publish-pypi` job's `strategy.matrix` evaluated `fromJSON('')`.)
- **A reconciliation the skill should have anticipated** — e.g. the step-6 babysit fixes landed changelog entries for bugs in features shipping this same release, which then needed a second consolidation pass.

Surfacing these is how the skill improves release-over-release instead of re-hitting the same friction. **Propose only:** do not commit, push, or open anything upstream without explicit approval.

### Why "Rebase and merge", never squash

The release PR carries exactly **two commits**: a **freeze commit** (`[changelog] Release vX.Y.Z`) that finalizes the changelog date and comparison URL, removes the unreleased warning, and pins workflow action refs and CLI invocations to the release version; and an **unfreeze commit** (`[changelog] Post-release bump`) that reverts those to `@main` and local source, adds a fresh unreleased section, and bumps the patch version. The auto-tagging job tags only the freeze commit, located by its message — squashing collapses both into one and breaks tagging. A `detect-squash-merge` safeguard opens an issue and fails the workflow when a squash is detected.

### What a complete release looks like

After the merge, the pipeline produces all of the following; if any is missing, the release is incomplete:

- **Git tag** (`vX.Y.Z`) on the freeze commit.
- **GitHub release** with notes matching the `changelog.md` entry.
- **Binaries** for all 6 platform/architecture combinations (linux-arm64, linux-x64, macos-arm64, macos-x64, windows-arm64, windows-x64), when the project builds them.
- **PyPI package** at the matching version.
- **`changelog.md`** entry with the release date and comparison URL finalized.
