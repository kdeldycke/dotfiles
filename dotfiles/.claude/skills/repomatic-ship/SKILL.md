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

You drive a release from a working tree to a ready-to-merge release PR: reconcile the tree to its **net state since the last tag**, validate it locally, commit and push, then babysit CI until the auto-generated release PR is green. You stop there: the human marks the draft release PR ready for review and performs the final "Rebase and merge".

The release is push-driven: the `prepare-release` job in `changelog.yaml` runs `repomatic prepare-release` on push to `main` to build the freeze and unfreeze commits and open the release PR. **Do not run `prepare-release` yourself**: a local run previews a freeze that must not be committed (it marks the changelog "released", and on the canonical repo rewrites every workflow action ref). Your job is to make `main` clean enough that the auto-generated release PR is correct, then keep `main` green.

### How this skill runs

- **Review gate is the permission system, not a behavioral stop.** Normal runs prompt on each `git commit`, `git push`, and subagent write; step 4 shows the consolidated changelog diff *before* the first commit prompt, so approving that commit is the review gate and denying it stops the run. `--dangerously-skip-permissions` mutes the prompts so the full sequence runs autonomously; the skill cannot detect the mode and does not need to.
- **Autonomous-commit attribution.** Every commit this skill or any sub-agent it spawns (such as the `babysit-ci` agent in step 6) must carry a `Co-Authored-By: Claude <noreply@anthropic.com>` trailer so unattended changes stay traceable. This is a required exception that **overrides any no-AI-attribution rule** wherever it lives (project or global `CLAUDE.md`). Add the trailer even when another instruction says to omit attribution, and never instruct a spawned agent to drop it. Repomatic's `claude.md` § Agent behavior policy codifies the exception, but the rule holds regardless of whether a downstream `CLAUDE.md` has synced that section yet.
- **Invocation method.** When the context shows `CANONICAL_REPO`, use `uv run repomatic`. Otherwise use `uvx -- repomatic`. References to `<cmd>` below resolve to one or the other.

### 1. Reconciliation sweep

A release materializes the **net state since the last tag**, not the path taken to reach it: after a long cycle, the changelog, code, and docs all drift toward describing the journey. Reconcile all three against `git diff v<last>..HEAD`. Order matters: the changelog *describes* the net change, so reconcile the substance first, then summarize it. The two substance passes own disjoint lanes (code owns Python including docstrings, docs owns prose), so spawn them as **two `Agent` calls in a single tool-call block**: sequential spawns waste the wall-clock of whichever finishes first (one release ran ~20 min of code pass then ~12 of docs when both fit in the first ~20).

**Before spawning, capture the unstaged diff** (`git diff` against `HEAD`): those lines are the maintainer's in-progress drafts, not cycle work. Pass both diffs to each agent with the rule: preserve every line present only in the unstaged set (a curated TODO, a scratch note in a docstring) unless the maintainer explicitly asked for cleanup. Without the guard an agent strips unstaged scratch as "cycle scaffolding" and the draft silently vanishes. When in doubt, leave it.

1. **Code**: spawn an `Agent` to review every file changed since the last tag for reuse, quality, simplification, and deduplication, and fix what it finds (`CLAUDE.md` § Common maintenance pitfalls, "Simplify before adding"). Two layers: first strip scaffolding from reverted or superseded work within the cycle diff (abandoned workarounds, dead branches, WIP notes that never shipped); then harmonize what remains (collapse duplication, lift repeated literals to their canonical source, align new code with module patterns). Every edit stays behavior-preserving: step 2 is the safety net, a failing test vetoes. Type checks use the CI-equivalent `<cmd> run mypy` (pinned version and `--python-version`), never a bare `mypy` whose newer interpreter raises false positives CI never sees. Failures the pass believes pre-existing get *reported*, not silently scoped out: that verdict belongs to step 2's CI check. Adopting features from upgraded dependencies stays in `/repomatic-deps modernize`. On the canonical repo, workflow invocations reading `uvx --from . repomatic` are the intended unfrozen state (the freeze commit rewrites them to a `'repomatic=={version}'` PyPI pin at release): never flag `--from .` as a pin regression or downstream breakage; the invariant to check instead is that every `uv`-invoking job provisions `setup-uv` in its own steps. Docstring rendering belongs to this pass: build the docs and fix any broken cross-reference role a docstring introduced (the docs pass can surface but not fix them). Build only into the gitignored `docs/_build`, never an ad-hoc path: a stray build tree pollutes `git status` and trips tool scans like `run typos`.
2. **Docs**: spawn an `Agent` to verify prose docs against current behavior, not the journey (version references, CLI output, removed or renamed features go stale every cycle). Manually-maintained version examples in `docs/` (install commands, binary download URLs, `uses:` refs) track the latest *released* tag, never the version being prepared: the docs site deploys on every push to `main`, and the freeze rewrites `readme.md` and workflow YAML but never `docs/`. Any docs-pass edit touching a `.py` file (typically `docs/conf.py`) is re-verified with `<cmd> run mypy -- docs/` before the agent returns: `docs/conf.py` may import from the docs group's higher Python floor while mypy checks the project minimum, and the break otherwise surfaces only in CI's lint job.
3. **Changelog**: once both passes settle, invoke `/repomatic-changelog consolidate` through the `Skill` tool, so the consolidated entries (and the version advisory reading them) reflect the reconciled tree, renames included. It collapses superseded values and drops intra-cycle reverts. **Degrade gracefully:** if the skill is excluded here, apply the same end-state principle via an `Agent` or inline; a missing skill is a fallback path, not a blocker.

**The two agents share one working tree**, so disjoint lanes do not make them race-free. Neither may run a working-tree-reverting git command (`checkout`, `restore`, `stash`, `reset`, `clean`): it silently discards the *other* agent's uncommitted edits (one release lost docs fixes that way and re-applied them by hand). The docs build has a single owner, the code agent (which already builds for docstring cross-references); the docs pass verifies prose against that build instead of launching its own `sphinx-build` into the same output dir. For full isolation, spawn each agent with `isolation: "worktree"` and merge on join: their disjoint files won't conflict.

A change introduced and then reverted before release is a no-op for users: no changelog entry, no scaffolding, no docs mention. This skill holds no `Edit`/`Write` of its own: the changelog skill and the agents do the editing.

### If the sweep made no edits

A clean cycle, where every change since the last tag is already at its net end-state, is a normal outcome. With **no working-tree edits**, the commit-and-push spine collapses and three steps change shape:

- **Step 2** becomes redundant: CI already ran on this exact commit (it is `HEAD` of `main`), so verify that run's conclusion (`gh run list --branch main`) instead of paying for a fresh gate. Still quick-run the time-dependent external smoke checks (`<cmd> run typos`, `<cmd> audit --fix`): re-published binaries and new CVEs drift independently of code.
- **Step 5** is a no-op: never force an empty commit.
- **Step 6** reduces to verifying the existing run. When `gh pr list --head prepare-release` shows a PR whose freeze commit sits on the current `HEAD`, confirm every stable job on `HEAD` is green and go to step 7, spawning `/babysit-ci` only on a real failure. When no current PR exists (the last push missed `changelog.yaml`'s `paths:` filter), trigger one with `gh workflow run changelog.yaml --ref main`, still with no commit.

Steps 3, 4, and 7 are unchanged: the version advisory and the (empty) changelog diff still inform the maintainer.

### 2. Validate locally (pre-push gate)

When the sweep rewrote code, prove it green **before** paying for a CI round-trip (no edits: see above). This is the same fast local channel `/babysit-ci` polls, run ahead of the first push:

- Launch in parallel in the background: `uv run pytest --no-header -q`, `<cmd> run mypy -- repomatic tests docs`, and `<cmd> lint-changelog`. Scope mypy to **every directory holding tracked Python**, `docs/` included: CI's lint job type-checks all tracked `*.py`, so a `repomatic tests`-only gate stays green on a `docs/` error (surfaced by a same-cycle mypy bump, say) that reddens Lint post-push.
- Reproduce CI's `format-python` with the **pinned** tools, never the dev-env `uv run ruff` (version drift: a newer local ruff once silently disagreed on a `PERF401` fix): `<cmd> run autopep8 --` over the cycle's changed Python files (it wraps long-line comments ruff leaves), then `<cmd> run ruff -- check` and `<cmd> run ruff -- format` (all write in place; the runner injects `--fix`), then read `git diff`: write-mode output is the reliable signal, `--check` is not. An empty diff past your reconciliation edits is green; fold a legitimate style fix into the reconciliation. Landmine: autopep8 relocates a trailing `# type: ignore[...]` off a >88-char line onto its own line, voiding the suppression (Lint red under `warn_unused_ignores`); never commit the relocation, fix the length at the source so the comment rides the opening line. Run `ruff -- format` after autopep8 and read the diff only then: ruff format usually reverts the relocation on its own (one release saw it restore the line byte-for-byte), so only the wraps that survive the full pinned sequence — typically comment-free code lines — are real formatting debt.
- Smoke-run the `autofix` externals: `<cmd> run typos`, **every formatter that downloads a checksum-pinned binary** (`<cmd> run biome` and peers), and the vulnerable-deps scan `<cmd> audit --fix` (parses live `uv audit` output). An upstream re-publish flips a pinned SHA-256 and kills the step; pytest mocks these, so the drift (or a changed output schema) surfaces only here or in CI's `autofix` run. A pin living upstream in `repomatic` breaks every downstream on it and cannot be patched here: surface it for the step-8 upstream fix. A bare invocation (`<cmd> run biome`) fully exercises download and checksum; never replay a workflow job's `xargs` pipe when the repo has no matching files: `xargs` still runs the tool once with zero path arguments, and a pathless formatter walks the **whole tree in write mode** (an empty JSON list once sent biome rewriting 3,000+ files).
  - These run in **write mode** (`run typos` defaults to `--write-changes`; `audit --fix` rewrites pins), so they can mutate tracked files. Those edits are the `autofix` workflow's job: **revert any mutation that is not part of this release's net diff** before the step-5 commit; a fix that genuinely belongs to the cycle can be kept and folded into the reconciliation.
- Smoke-run the **binary self-test plan** against the source build: `uv run -- click-extra test-suite --command <source-entrypoint> --jobs max`, the same engine `tests.yaml` (`--command`) and `release.yaml` (`--binary`) drive. It catches the two failures otherwise hidden until the ~90-minute matrix: a case assertion drifted from current CLI output (colors stripped by the piped harness, a moved string), and a plan that cannot *load* under the binary runner's stdlib-only base deps (a YAML or json5 plan raises "format support disabled" and silently falls back to a trivial suite: keep the plan TOML or JSON, and confirm a non-TOML plan parses under stdlib `tomllib`, since the full-venv source run has the format extras and hides the gap).
- Smoke-run `uvx --no-progress --from . <cmd-bare> --version`: a fresh isolated env resolves `[project.dependencies]` from scratch, surfacing transitive conflicts the already-synced venv hides. CI's `🧬 Project metadata` job runs exactly this on every workflow, and end users installing via `uvx` hit the same resolution, so a failure is **release-blocking**: fix at the dependency level (drop, swap, or wait on upstream), never with environment-scoped overrides: `uvx --from .` does not read `[tool.uv] override-dependencies`.
- Act on the fastest failing check first (mypy and ruff in seconds, pytest in minutes); fix in the working tree, re-run only what failed, and iterate until every local check is green.

**Read CI's conclusions on `HEAD` before trusting any "pre-existing" claim.** The gate proves the tree against the *current* CI state: `gh run list --branch main`, and every red job there is cycle work this release must fix. An in-cycle lockfile bump can invalidate `type: ignore` comments and override signatures with zero source changes, so "the source did not change" never proves "the check still passes" (archetype: a Click patch re-lock widened a parent method, the code pass rationalized the 7 resulting mypy errors as pre-existing, and CI Lint was red with exactly those errors).

**Integration-heavy suites are the exception to the pytest bullet.** A suite driving real external tooling can outrun a local background timeout and need tools not installed locally, so it is not a fast gate: keep mypy, ruff, and `lint-changelog` as the local gate and treat the **CI matrix on the exact commit** as the authoritative test signal instead of blocking on a slow local pytest.

**The local pytest gate is single-OS**, so platform-specific failures surface only after the push. Usual culprits: path resolution (`Path.resolve()` canonicalizes Windows 8.3 names and POSIX symlinks), home-directory expansion, env-var casing, filesystem case-sensitivity, and text-I/O encoding (Windows defaults to cp1252, so a bare `open()`/`read_text()`/`write_text()` breaks on the first non-ASCII character, and only in Windows CI: pass `encoding="utf-8"`, and when the cycle touched file I/O, run the suite once with `PYTHONWARNDEFAULTENCODING=1` to catch bare calls ruff's inference-limited `PLW1514` cannot see). The structural fix is to **mirror the production transformation, not reconstruct it**: a test asserting on a derived value should run the same pipeline the code runs, so the expectation matches by construction on every platform. Where expectations must diverge by platform, the CI matrix is authoritative: read every cell, not just your OS. The gate can also name what it cannot run: grep the cycle's changed test files for pytestmarks that exclude the local platform (`unless_*`, `skip_*`, `skipif`) and diff-review those tests' expectations by hand, since a green local run says nothing about them (archetype: a rename cycle rewords docstrings asserted by `unless_linux`-marked Sphinx tests, the maintainer gates on macOS, and the stale fragments redden only in CI).

A `⚠ X.Y.Z: not found on PyPI` warning from `lint-changelog` for the still-unreleased version is expected and not a blocker.

### 3. Version advisory (never bumps, never blocks)

Read the consolidated unreleased section and classify the bump the net diff implies:

- A `**Breaking:**` entry, or any removed or renamed public API: **major**.
- A new feature, command, or config key: **minor**.
- Only fixes, dependency bumps, and internal changes: **patch**.

State the classification and the single strongest reason, then keep going on the patch default (the unfreeze commit bumps the patch automatically). **Do not merge a version-increment PR, and do not stop**: for minor or major, surface an advisory ("this release looks like a `minor`: merge the `minor-version-increment` PR if you want that bump") and proceed. The maintainer merges that PR out of band, which re-triggers the release PR on its own.

### 4. Present the sweep

Show `git diff` of `changelog.md` plus a one-line summary of the code and docs changes the agents made. Consolidation drops and merges entries: surfacing this is what lets you catch an over-eager drop at the commit prompt before it ships.

### 5. Commit and push

Commit the reconciled tree with a message describing the net reconciliation (plus the `Co-Authored-By` trailer above), then push to `main`: the push regenerates the release PR through `prepare-release`.

**Signed commits: sandbox off, and a hardware key is not a retry loop.** With SSH signing (`gpg.format = ssh`), the harness sandbox blocks the key or socket under `~/.ssh/*` (`Operation not permitted`): disable the sandbox for the `git commit` and `git push` calls only. A hardware-backed key (Secretive, YubiKey, TPM) additionally prompts the maintainer per signature; a refused or missed prompt surfaces as `agent refused operation?` and looks like a real failure. Stop after one or two retries and ask the maintainer rather than burning prompts they may not be watching. The same applies to the babysit subagent in step 6: its skill carries the explicit hand-off contract.

### 6. Babysit CI to green

Step 2 cleared every locally-reproducible failure, so the first run should be close to green: babysit handles what only CI surfaces, platform-specific breaks and the slow Nuitka `compile-binaries` job.

Spawn a **foreground `Agent` on the `sonnet` model** to run `/babysit-ci` to completion (the loop is mechanical: fetch logs, match patterns, fix, commit, push). It monitors `tests.yaml`, `lint.yaml`, `autofix.yaml`, `docs.yaml`, and the Nuitka `compile-binaries` job, fixing failures until every stable job passes. Its prompt must:

- **reaffirm the `Co-Authored-By: Claude` trailer**: its commits are exactly the unattended ones the trailer marks; never instruct it to omit attribution;
- **state the loop condition verbatim**: "re-poll after each push; do not return after a push without re-polling". Its turn ends only when every monitored workflow on the latest `main` HEAD has `conclusion: success` (or `skipped` for benign reasons), or on a real blocker it cannot resolve. Terser phrasings get misread as "report after first fix", and the agent returns while the slow jobs still build, doubling wall-clock when you re-spawn it;
- **set the poll cadence**: every poll loop sleeps at least 45-60 seconds between iterations, with the `sleep` inside the loop command; zero-delay spins exhaust the shared REST quota (5,000 requests/hour) in minutes, and the exhaustion resurfaces as PAT-permission-shaped workflow failures and `prepare-release` hangs (see babysit's § GitHub API rate-limit exhaustion);
- **relay babysit's "poll in-process; never detach a monitor" rule**: the poll loop must block inside the agent's turn (a foreground loop or `gh run watch`), never a `run_in_background` poller the agent idles on awaiting notification. The babysit skill already forbids detached monitors, but a spawn prompt composed from these bullets alone can override that with an "e.g. as a background task" aside, and the agent follows the prompt: one release's babysitter armed a background poll and went idle, the Tests failure landed in that idle window, and the main thread had to take over the loop;
- **mandate interim status pings**: it must message the orchestrator at startup (local gate result, which runs it watches) and on every state change (fix pushed, workflow landed, re-run triggered), not only at the end. Agents otherwise go silent-idle mid-loop — one release had to prompt both its sweep agents and the babysitter for reports they never sent — and a silent babysitter is indistinguishable from a dead one;
- **stage only the file a fix touches** (`git commit <path>`, never `-a`).

**Degrade gracefully:** if `/babysit-ci` is excluded here, have the subagent run the equivalent fetch-logs/fix/commit/push/re-poll loop inline; if the `Agent` itself fails to spawn (a terminal API error), run that loop yourself in the main thread until every stable job is green. **Treat its return as a claim, not proof**: even with the verbatim prompt it can stop early (the long Nuitka wait is where it gives up). Re-poll `gh run list --branch main` yourself and read each monitored workflow's conclusion; anything still `queued`/`in_progress` or non-green means it stopped early, so take over the loop inline rather than re-spawning it into the same idle.

**Verify the Nuitka run yourself.** Babysit's own early exit declares success once the fast platforms are green, leaving macOS and the entire `release.yaml` matrix still building: its "every stable job passes" never covers the binaries. Independently confirm the `release.yaml` run reached a terminal green state (`gh run watch <release-run-id>`, then read its `conclusion`); never infer the Nuitka result from babysit's summary. If a binary build fails, re-spawn babysit or fix inline. A green `conclusion` also proves nothing on a HEAD that touched no Python source: `release.yaml` skips the entire `compile-binaries` matrix on such pushes (workflow-only, docs-only), so read the run's *jobs* and confirm the per-platform build and test jobs ran rather than skipped. When they skipped, the authoritative binary signal is the last run that actually compiled, valid only while its source tree matches the release tree.

**Refresh the release PR after non-trigger pushes.** Whether a push re-runs `prepare-release` (and so refreshes the PR onto your new HEAD) depends on `changelog.yaml`'s `paths:` filter, which varies per repo: commonly `changelog.md`, `pyproject.toml`, workflows, and `uv.lock`, but many repos also list `docs/**` and `**/*.py`, so a docs-only or Python-only fix can refresh the PR on its own. Do not infer it from the path list. Once `main` is green, verify that `changelog.yaml` actually ran on your latest commit (`gh run list --workflow changelog.yaml --branch main` shows a green run titled with your commit). Only if it did not, run `gh workflow run changelog.yaml --ref main`; then confirm the `prepare-release` branch contains your final commit before step 7.

**A racing version-increment merge can leave your commit's heavy CI uncompleted.** Merging the `minor-`/`major-version-increment` PR mid-build cancels your in-flight `tests`/`lint` (shared concurrency group) while the bump commit is itself gated out of them, so the release PR can show them `skipped`. This is by design: step 2 is the authoritative pre-merge check, so read `skipped` tests/lint on a bump commit as expected and do not re-push to force a run.

**When no Tests run ever completed on the release tree, dispatch one.** Superseded-run cancellation, the version-bump gate, and `tests.yaml`'s `paths:` filter can leave every attempt on a busy cycle `cancelled` or `skipped`, and recent Tests *activity* is not a completed run on the current tree. If the local pytest was also skipped (the integration-heavy exception), no test signal exists anywhere: get one with `gh workflow run tests.yaml --ref main` (a `workflow_dispatch` adds no commit and does not regenerate the PR), then verify the stable jobs and ignore the `continue-on-error` probes. A docs-only HEAD shares its source tree with the prior commit, so the dispatched run validates the frozen tree. The same hole opens for every paths-filtered workflow, Docs included: a cancelled `docs.yaml` run followed by a workflow-only HEAD leaves the release tree with no completed docs build even though the cycle's docstring edits changed the rendered site. Close it the same way (`gh workflow run docs.yaml --ref main`) and confirm the dispatched run lands green.

**Reconcile the changelog against every fix babysit committed: entries it added *and* omitted.** Walk its commits and blame each fix against the last release tag: a bug that only ever existed in code introduced this same cycle is a user no-op (drop any entry babysit added for it); a bug that reached an earlier release deserves the entry babysit may have skipped. Re-run step 1.3's consolidation with both corrections and present the diff (step 4) before committing. This second pass is itself a push that re-runs CI: complete it before the step-7 confirmation.

**New uncommitted changes can appear during the babysit wait.** The 30+ minute CI wait gives the maintainer time to keep coding: those files are theirs, never revert them and never let a fix sweep them in (stage only what the fix touches). Surface them in the step-7 report so the maintainer decides whether each belongs in this release (commit and push before merge) or the next.

### 7. Confirm and stop

Once `main` is green and the release PR exists (`gh pr list --head prepare-release`), report:

- the release PR URL,
- the version it will cut, plus the bump advisory from step 3,
- that the PR is opened as a **draft** (`prepare-release` creates it with `draft: always-true`), so the remaining human actions are to mark it **"Ready for review"**, then **"Rebase and merge"** (never squash).

Do not merge the PR, and do not mark it ready yourself. That final human action is the boundary this skill stops at.

### 8. Reflect and contribute back

This skill, the workflows it drives, and the conventions it enforces live upstream in `kdeldycke/repomatic` and sync down to each caller; a release is when their rough edges show. Before finishing, review the session and for each finding point at the exact `../repomatic` source with a concrete fix:

- **A skill instruction that misled you or forced a judgment call you got wrong**: a dangling cross-reference, a missing step, an instruction a sub-agent should have inherited but didn't (archetype: the `Co-Authored-By` trailer dropped because the attribution note leaned on an unsynced `CLAUDE.md` section).
- **A workflow "failure" that turned out to be a real upstream bug**: trace it to its template in `repomatic/data/` or `.github/workflows/` instead of waving it off (archetype: `release.yaml` red on every push from a `strategy.matrix` evaluating `fromJSON('')`).
- **A reconciliation the skill should have anticipated** (archetype: the step-6 second consolidation pass, added after babysit fixes shipped spurious or missing entries).

Surfacing these is how the skill improves release-over-release. **Propose only:** do not commit, push, or open anything upstream without explicit approval.

### Why "Rebase and merge", never squash

The release PR carries exactly **two commits**: a **freeze commit** (`[changelog] Release vX.Y.Z`) that finalizes the changelog date and comparison URL and pins workflow refs and CLI invocations to the release version, and an **unfreeze commit** (`[changelog] Post-release bump`) that reverts those to `@main`, adds a fresh unreleased section, and bumps the patch version. The auto-tagging job locates the freeze commit **by its message**: squashing collapses both commits into one and breaks tagging. A `detect-squash-merge` safeguard opens an issue and fails the workflow when a squash is detected.

### What a complete release looks like

After the merge, the pipeline produces all of the following; if any is missing, the release is incomplete:

- **Git tag** (`vX.Y.Z`) on the freeze commit.
- **GitHub release** with notes matching the `changelog.md` entry.
- **Binaries** for all 6 platform/architecture combinations (linux-arm64, linux-x64, macos-arm64, macos-x64, windows-arm64, windows-x64), when the project builds them.
- **PyPI package** at the matching version.
- **`changelog.md`** entry with the release date and comparison URL finalized.
