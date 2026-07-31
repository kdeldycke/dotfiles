---
name: repomatic-ship
description: Orchestrate release preparation. Reconcile the changelog, code, and docs to the net release state, then commit, push, and babysit CI until the release PR is built and `main` is green. Stop before the merge. Review-gated in normal use, fully autonomous under `--dangerously-skip-permissions`.
model: opus
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob, Skill, Agent
---

## Context

!`grep -m1 'version' pyproject.toml 2>/dev/null`
!`awk '/^## \[/{n++} n==2{exit} {print}' changelog.md 2>/dev/null`
!`git tag --sort=-v:refname | head -3 2>/dev/null`
!`git log --oneline -25 2>/dev/null`
!`git status --short 2>/dev/null`
!`[ -f repomatic/__init__.py ] && echo "CANONICAL_REPO" || echo "DOWNSTREAM"`

## Instructions

You drive a release from a working tree to a ready-to-merge release PR: reconcile the tree to its **net state since the last tag**, validate it locally, commit and push, then babysit CI until the auto-generated release PR is green. You stop there: the human marks the draft release PR ready for review and performs the final "Rebase and merge".

The release is push-driven: the `prepare-release` job in `changelog.yaml` runs `repomatic prepare-release` on push to `main` to build the freeze and unfreeze commits and open the release PR. **Do not run `prepare-release` yourself**: a local run previews a freeze that must not be committed (it marks the changelog "released", and on the canonical repo rewrites every workflow action ref). Your job is to make `main` clean enough that the auto-generated release PR is correct, then keep `main` green.

### How this skill runs

- **The review gate is the permission system, not a behavioral stop.** Normal runs prompt on each `git commit`, `git push`, and subagent write; step 4 shows the consolidated changelog diff *before* the first commit prompt, so approving that commit is the review gate and denying it stops the run. `--dangerously-skip-permissions` mutes the prompts so the full sequence runs autonomously; the skill cannot detect the mode and does not need to.
- **Invocation method.** When the context shows `CANONICAL_REPO`, use `uv run repomatic`. Otherwise use `uvx -- repomatic`. References to `<cmd>` below resolve to one or the other.
- **You hold no `Edit`/`Write` of your own**: the changelog skill and the spawned agents do the editing.

### Sub-agent rules

The sweep agents (step 1) and the babysitter (step 6) all follow these rules. Restate them in every spawn prompt: a spawned agent only sees what the prompt carries.

- **Commit attribution.** Every commit this skill or any spawned agent makes carries a `Co-Authored-By: Claude <noreply@anthropic.com>` trailer so unattended changes stay traceable. This is a required exception that **overrides any no-AI-attribution rule** wherever it lives (project or global `CLAUDE.md`); never instruct an agent to drop it. Repomatic's `claude.md` § Agent behavior policy codifies the exception, but the rule holds even where a downstream `CLAUDE.md` has not synced that section yet.
- **Reports are sent, not written.** A background agent's end-of-turn text is never delivered, so every spawn prompt must require the final report as a `SendMessage` to the orchestrator: a "return a report" instruction yields a silent idle even when the report was composed. On an idle notification without a report, chase once; the tree (`git diff`) stays the authoritative record either way.
- **Trust the tree, not the report.** A mid-run message to a busy agent is delivery without receipt: it can land after the agent composed its final report and be silently dropped. After tasking a running agent, confirm the tree reflects the request (`git diff` the target file) before moving on.
- **Never revert the shared working tree.** The agents share one tree, so disjoint lanes do not make them race-free: no agent may run a working-tree-reverting git command (`checkout`, `restore`, `stash`, `reset`, `clean`), which silently discards the *other* agents' uncommitted edits. For full isolation instead, spawn with `isolation: "worktree"` and merge on join: disjoint files won't conflict.
- **Fix commits stage narrowly** (`git commit <path>`, never `-a`). Uncommitted files an agent did not create are the maintainer's in-progress work: never revert them and never sweep them into a commit.
- **Degrade gracefully.** A cross-referenced skill excluded from this repo is a fallback path, not a blocker: apply its principle via an `Agent` or inline. When an `Agent` spawn itself fails (a terminal API error), do the work in the main thread.

### 1. Reconciliation sweep

A release materializes the **net state since the last tag**, not the path taken to reach it: after a long cycle, the changelog, code, and docs all drift toward describing the journey. Reconcile all three against `git diff v<last>..HEAD`. Order matters: the changelog *describes* the net change, so reconcile the substance first (code and docs in parallel), then summarize it (changelog). A change introduced and then reverted before release is a no-op for users: no changelog entry, no scaffolding, no docs mention.

**Before spawning, capture the unstaged diff** (`git diff` against `HEAD`): those lines are the maintainer's in-progress drafts, not cycle work. Pass both diffs to each agent with the rule: preserve every line present only in the unstaged set (a curated TODO, a scratch note in a docstring) unless the maintainer explicitly asked for cleanup. Without the guard an agent strips unstaged scratch as "cycle scaffolding" and the draft silently vanishes. When in doubt, leave it.

The two substance passes own disjoint lanes (code owns Python including docstrings, docs owns prose), so spawn them as **two `Agent` calls in a single tool-call block**: sequential spawns waste the wall-clock of whichever finishes first.

1. **Code**: an `Agent` that reviews every file changed since the last tag for reuse, quality, simplification, and deduplication, and fixes what it finds (`CLAUDE.md` § Common maintenance pitfalls, "Simplify before adding"). Two layers: first strip scaffolding from reverted or superseded work within the cycle diff (abandoned workarounds, dead branches, WIP notes that never shipped); then harmonize what remains (collapse duplication, lift repeated literals to their canonical source, align new code with module patterns). Its constraints:

   - Every edit stays behavior-preserving: step 2 is the safety net, a failing test vetoes.
   - Type checks use the CI-equivalent `<cmd> run mypy` (pinned version and `--python-version`), never a bare `mypy` whose newer interpreter raises false positives CI never sees.
   - Failures the pass believes pre-existing get *reported*, not silently scoped out: that verdict belongs to step 2's CI check.
   - Adopting features from upgraded dependencies stays in `/repomatic-deps modernize`.
   - On the canonical repo, workflow invocations reading `uvx --from . repomatic` are the intended unfrozen state (the freeze commit rewrites them to a `'repomatic=={version}'` PyPI pin at release): never flag `--from .` as a pin regression or downstream breakage. The invariant to check instead is that every `uv`-invoking job provisions `setup-uv` in its own steps.
   - Docstring rendering belongs to this pass: build the docs and fix any broken cross-reference role a docstring introduced (the docs pass can surface but not fix them). Build only into the gitignored `docs/_build`, never an ad-hoc path: a stray build tree pollutes `git status` and trips tool scans like `run typos`.
   - Shortening an over-long workflow line to satisfy yamllint's 120-char limit must not lift `hashFiles(...)` (or any `runner.*`) into a workflow-level `env:` var: that context exposes only `github`/`secrets`/`inputs`/`vars`, so the expression resolves to empty at run-init before checkout and silently breaks the value — a cache `key:` shortened this way ships a broken key to every downstream repo. Shorten the literal itself instead (trim a shared key prefix, say).

2. **Docs**: an `Agent` that verifies prose docs against current behavior, not the journey (version references, CLI output, removed or renamed features go stale every cycle). Its constraints:

   - Manually-maintained version examples (install commands, binary download URLs, `uses:` refs) track the latest *released* tag, never the version being prepared: the docs site deploys on every push to `main`, and the freeze never touches `docs/`. The tracking runs both ways: advance a sample that *lags* the released tag (still at N-1 after release N published) up to it, applying the bump directly rather than deferring it as a version advisory; only bumping a sample forward to the not-yet-released version is off-limits. A stale sample hides in plain sight, so grep every version string in `docs/` and `readme.md` rather than trusting a sub-agent's list.
   - What the freeze rewrites varies by repo (the canonical repo pins workflow refs and CLI invocations; a downstream freeze may touch only `changelog.md`, `citation.cff`, `__init__.py`, and `pyproject.toml`). Read the last freeze commit's file list (`git show <last-freeze-sha> --stat`) and treat every version sample outside it, `readme.md` quick-start output included, as hand-maintained tracking the released tag: samples presumed freeze-managed have shipped stale through a release. On a cycle that migrated the release tooling itself, the historical freeze under-predicts the new one (a pre-repomatic freeze touching only `changelog.md` says nothing about the repomatic freeze, which also rewrites `citation.cff`, `__init__.py`, and `pyproject.toml`): treat every version sample as hand-maintained until the regenerated release PR's diff shows the new freeze's actual scope.
   - Executable doc blocks fail open: a `{click:run}` invocation that no longer parses renders the usage error into the published page instead of failing the build (`docs.yaml` stayed green while a stale option printed `No such option`; only `click:tree` and `click:config` hard-error). Verify each `{click:run}` invocation against the current CLI, or grep the built HTML for `Error: No such option`-class output.
   - Correcting one description of a convention means correcting *every* description of it in the same pass: a rule restated in more than one place (an overview line and its worked example, two docs pages) drifts as a set, so grep for the sibling statements and align them together — fixing one in isolation leaves the others contradicting the fix (a freeze-cutoff overview still said "the day after" while its worked example had been corrected to "the second day after", reconciled only on a second pass).
   - The docs build has a single owner, the code agent (which already builds for docstring cross-references): verify prose against that build instead of launching a second `sphinx-build` into the same output dir.
   - Any docs-pass edit touching a `.py` file (typically `docs/conf.py`) is re-verified with `<cmd> run mypy -- docs/` before the agent returns: `docs/conf.py` may import from the docs group's higher Python floor while mypy checks the project minimum, and the break otherwise surfaces only in CI's lint job.
   - Changelog *released* sections (`## [X.Y.Z]` blocks) are immutable history: a command, option, or config key named there was correct for that release, so never flag or rewrite a since-renamed name in one. When the changelog seeds the checklist for a rename, reconcile only the unreleased section (the docs pass once flagged `update-deps-graph` in three released sections that a `7.4.0` rename had superseded).

3. **Changelog**: once both passes settle, invoke `/repomatic-changelog consolidate` through the `Skill` tool, so the consolidated entries (and the version advisory reading them) reflect the reconciled tree, renames included. It collapses superseded values and drops intra-cycle reverts. Consolidation assumes the entries already exist, though: when the unreleased section under-represents the net cycle (a maintainer left one stub bullet for a multi-feature cycle), run `add` first, or the bare `/repomatic-changelog` default that runs `add` then `consolidate`, so the shipped changes are drafted before they are collapsed. If the skill is excluded here, degrade gracefully (sub-agent rules).

### If the sweep made no edits

A clean cycle, where every change since the last tag is already at its net end-state, is a normal outcome. With **no working-tree edits**, the commit-and-push spine collapses and three steps change shape:

- **Step 2** becomes redundant: CI already ran on this exact commit (it is `HEAD` of `main`), so verify that run's conclusion (`gh run list --branch main`) instead of paying for a fresh gate. Still quick-run the time-dependent external smoke checks (`<cmd> run typos`, `<cmd> audit --fix`): re-published binaries and new CVEs drift independently of code.
- **Step 5** is a no-op: never force an empty commit.
- **Step 6** reduces to verifying the existing run. When `gh pr list --head prepare-release` shows a PR whose freeze commit sits on the current `HEAD`, confirm every stable job on `HEAD` is green and go to step 7, spawning `/babysit-ci` only on a real failure. When no current PR exists (the last push missed `changelog.yaml`'s `paths:` filter), trigger one with `gh workflow run changelog.yaml --ref main`, still with no commit.

Steps 3, 4, and 7 are unchanged: the version advisory and the (empty) changelog diff still inform the maintainer.

### 2. Validate locally (pre-push gate)

When the sweep rewrote code, prove it green **before** paying for a CI round-trip (no edits: see above). This is the same fast local channel `/babysit-ci` polls, run ahead of the first push. Launch the slow checks (tests, types, changelog lint) in parallel in the background, act on the fastest failure first (mypy and ruff in seconds, pytest in minutes), fix in the working tree, re-run only what failed, and iterate until every check is green.

**First read CI's conclusions on `HEAD`** (`gh run list --branch main`): every red job there is cycle work this release must fix, and no "pre-existing failure" claim from the sweep is valid until checked against it. An in-cycle lockfile bump can invalidate `type: ignore` comments and override signatures with zero source changes, so "the source did not change" never proves "the check still passes" (a dependency re-lock once widened a parent method, and CI Lint was red with exactly the 7 mypy errors the sweep had rationalized as pre-existing).

The checks:

- **Tests**: `uv run pytest --no-header -q`. Exception: an integration-heavy suite driving real external tooling can outrun a local background timeout and need tools not installed locally, so it is not a fast gate. Skip it, keep the rest of the gate, and treat the CI matrix on the exact commit as the authoritative test signal (step 6 covers dispatching one).
- **Types**: `<cmd> run mypy -- repomatic tests docs`, scoped to **every directory holding tracked Python**, `docs/` included: CI's lint job type-checks all tracked `*.py`, so a narrower gate stays green on a `docs/` error that reddens Lint post-push.
- **Changelog**: `<cmd> lint-changelog`. A `⚠ X.Y.Z: not found on PyPI` warning for the still-unreleased version is expected and not a blocker.
- **Formatting**, reproduced with the **pinned** tools, never the dev-env `uv run ruff` (a newer local ruff once silently disagreed on a `PERF401` fix): `<cmd> run autopep8 --` over the cycle's changed Python files (it wraps long-line comments ruff leaves), then `<cmd> run ruff -- check` and `<cmd> run ruff -- format` (all write in place; the runner injects `--fix`), then read `git diff`: write-mode output is the reliable signal, `--check` is not. An empty diff past your reconciliation edits is green; fold a legitimate style fix into the reconciliation. For any Markdown the reconciliation touched (`changelog.md`, `docs/`), verify with the pinned `<cmd> run mdformat -- <file>`, never a bare `mdformat`/`mdformat --with mdformat-myst`: the bare form rewrites MyST directive colon-options (a `{list-table}`'s `:header-rows:`/`:widths:`) to `---` frontmatter form, diverging from CI's autofix and injecting a spurious reflow you would then have to revert.
  - Landmine: autopep8 relocates a trailing `# type: ignore[...]` off a >88-char line onto its own line, voiding the suppression (Lint red under `warn_unused_ignores`); ruff format usually reverts the relocation, so only wraps that survive the full pinned sequence are real formatting debt. Never commit the relocation: fix the line length at the source so the comment rides the opening line.
- **Autofix externals**: smoke-run `<cmd> run typos`, **every formatter that downloads a checksum-pinned binary** (`<cmd> run biome` and peers), and the vulnerable-deps scan `<cmd> audit --fix` (parses live `uv audit` output). An upstream re-publish flips a pinned SHA-256 and kills the step; pytest mocks these, so the drift (or a changed output schema) surfaces only here or in CI's `autofix` run. A pin living upstream in `repomatic` breaks every downstream repo and cannot be patched here: surface it for the step-8 upstream report. Invocation rules:
  - Arg-needing tools take their CI-shaped args after the `--` separator (`<cmd> run biome -- check --write .`, `<cmd> run pyproject-fmt -- pyproject.toml`, `<cmd> run shfmt -- .`, `<cmd> run zizmor -- .`): a bare `<cmd> run biome` still downloads and checksum-verifies the binary, but then exits non-zero on its own usage error, indistinguishable from real drift in a scripted gate (a bare `<cmd> run shfmt` likewise errors on stdin).
  - When the repo has no files for a tool (no shell scripts for `shfmt`, say), smoke the pin alone with `<cmd> run <tool> -- --version`: it downloads and checksum-verifies the binary without touching the tree.
  - Never replay a workflow job's `xargs` pipe when the repo has no matching files: `xargs` still runs the tool once with zero path arguments, and a pathless formatter walks the **whole tree in write mode** (an empty JSON list once sent biome rewriting 3,000+ files).
  - These run in **write mode** (`run typos` defaults to `--write-changes`; `audit --fix` rewrites pins), and the args form over-formats relative to CI's `autofix` scope (`docs/_static/custom.css` gets retabbed): **revert any mutation that is not part of this release's net diff** before the step-5 commit; a fix that genuinely belongs to the cycle can be kept and folded into the reconciliation. Revert a formatter *move* as a move: it is a paired add-plus-delete, and reverting only the added copy silently deletes the block from the file (a `[tool.uv]` key nearly vanished this way). A mutated file carrying no reconciliation edit reverts whole with `git checkout -- <file>`: safe at this gate, where the sweep agents have already joined (their no-revert rule protects a *live* shared tree).
- **Binary self-test plan**, against the source build: `uv run -- click-extra test-suite --command <source-entrypoint> --jobs max`, the same engine `tests.yaml` (`--command`) and `release.yaml` (`--binary`) drive. It catches the two failures otherwise hidden until the ~90-minute matrix: a case assertion drifted from current CLI output (colors stripped by the piped harness, a moved string), and a plan that cannot *load* under the binary runner's stdlib-only base deps (a YAML or json5 plan raises "format support disabled" and silently falls back to a trivial suite: keep the plan TOML or JSON, and confirm a non-TOML plan parses under stdlib `tomllib`, since the full-venv source run has the format extras and hides the gap).
- **Fresh resolution**: `uvx --no-progress --from . <cmd-bare> --version`. A fresh isolated env resolves `[project.dependencies]` from scratch, surfacing transitive conflicts the already-synced venv hides; CI's `🧬 Project metadata` job runs exactly this on every workflow, and end users installing via `uvx` hit the same resolution, so a failure is **release-blocking**. Fix at the dependency level (drop, swap, or wait on upstream), never with environment-scoped overrides: `uvx --from .` does not read `[tool.uv] override-dependencies`.

**The local gate is single-OS**, so platform-specific failures surface only in CI. Shrink that window pre-push:

- The usual culprits: path resolution (`Path.resolve()` canonicalizes Windows 8.3 names and POSIX symlinks), home-directory expansion, env-var casing, filesystem case-sensitivity, text-I/O encoding (Windows defaults to cp1252, so a bare `open()`/`read_text()`/`write_text()` breaks on the first non-ASCII character, and only in Windows CI: pass `encoding="utf-8"`, and when the cycle touched file I/O, run the suite once with `PYTHONWARNDEFAULTENCODING=1` to surface calls ruff's inference-limited `PLW1514` cannot see), and direct execution of a generated script (Windows honors neither the executable bit nor the shebang, dispatching on file extension, so a `chmod +x`'d shebang script a test runs by bare path fails with `WinError 193`: emit a `.cmd` launcher beside a `.py` sidecar on Windows, or invoke the interpreter explicitly).
- The structural fix is to **mirror the production transformation, not reconstruct it**: a test asserting on a derived value should run the same pipeline the code runs, so the expectation matches by construction on every platform. Where expectations must diverge by platform, the CI matrix is authoritative: read every cell, not just your OS.
- **Name what the gate cannot run**: grep the cycle's changed test files for pytestmarks that exclude the local platform (`unless_*`, `skip_*`, `skipif`) and diff-review those tests' expectations by hand, since a green local run says nothing about them. Extend the review to the *inputs* those tests consume, not just the test files: new docs prose or docstrings can redden a platform-gated conformance test whose skip list never met that reference class (a reworded docstring a Sphinx test asserts on, a first-ever stdlib cross-reference missing from a skip list). The cycle's earlier pushes already ran those tests in CI, which is why the read of CI's conclusions on `HEAD` above is what actually catches them pre-push.
- **Reproducing a platform-specific failure churns the shared venv, and the wrong re-sync then reddens the rest of the gate with artifacts.** Confirming a free-threaded or version-specific break with `uv run --python <other>` (e.g. `3.14t` for a free-threading race) recreates and repoints `.venv` to that interpreter. Restore it with the CI-matching group set (`uv sync --frozen --all-extras --group test`, mirroring `tests.yaml`), never `--all-groups`: `--all-groups` pulls in the `typing`/`docs` groups whose imports perturb process-global-state-dependent tests (logging config, default theme) into spurious failures, while a default-only `uv sync` instead strips the `test` group (no `pytest`) and the `typing` group that holds mypy's third-party stubs — so a full-scope `<cmd> run mypy` then floods `import-untyped`/`import-not-found` in files the cycle never touched (even `pytest` reads as `import-not-found`). Both are venv-provisioning artifacts, not code regressions: re-sync to the CI-matching groups before re-running the gate, and trust CI's `lint.yaml`/`tests.yaml` over a local gate re-run against a churned venv (`lint.yaml` on the prior `HEAD` reporting exactly the real error set, and none of the stub noise, is the authoritative mypy signal).

### 3. Version advisory (never bumps, never blocks)

Read the consolidated unreleased section and classify the bump the net diff implies:

- A `**Breaking:**` entry, or any removed or renamed public API: **major**.
- A new feature, command, or config key: **minor**.
- Only fixes, dependency bumps, and internal changes: **patch**.

State the classification and the single strongest reason, then keep going on the patch default (the unfreeze commit bumps the patch automatically). **Do not merge a version-increment PR, and do not stop**: for minor or major, surface an advisory ("this release looks like a `minor`: merge the `minor-version-increment` PR if you want that bump") and proceed. The maintainer merges that PR out of band, which re-triggers the release PR on its own.

### 4. Present the sweep

Show `git diff` of `changelog.md` plus a one-line summary of the code and docs changes the agents made. Consolidation drops and merges entries: surfacing this is what lets you catch an over-eager drop at the commit prompt before it ships.

### 5. Commit and push

Commit the reconciled tree with a message describing the net reconciliation (plus the attribution trailer), then push to `main`: the push regenerates the release PR through `prepare-release`.

**Signed commits: sandbox off, and a hardware key is not a retry loop.** With SSH signing (`gpg.format = ssh`), the harness sandbox blocks the key or socket under `~/.ssh/*` (`Operation not permitted`): disable the sandbox for the `git commit` and `git push` calls only. A hardware-backed key (Secretive, YubiKey, TPM) additionally prompts the maintainer per signature; a refused or missed prompt surfaces as `agent refused operation?` and looks like a real failure. Stop after one or two retries and ask the maintainer rather than burning prompts they may not be watching. The same applies to the babysitter in step 6: its skill carries the explicit hand-off contract.

### 6. Babysit CI to green

Step 2 cleared every locally-reproducible failure, so the first run should be close to green: babysit handles what only CI surfaces, platform-specific breaks and, when the project builds binaries, the slow Nuitka matrix.

Spawn a **foreground `Agent` on the `sonnet` model** to run `/babysit-ci` to completion (the loop is mechanical: fetch logs, match patterns, fix, commit, push). It monitors `tests.yaml`, `lint.yaml`, `autofix.yaml`, `docs.yaml`, and `release.yaml` (whose engine runs the per-platform Nuitka matrix when the project enables binaries; its job names are templated, like `✅ {os}, {sha} build`, so key the watch on the workflow, not a literal job id, and the leading `✅`/`⁉️` across the test and release matrices marks cell stability, not outcome: a red `✅` (required) cell is release-blocking, a red `⁉️` (an allowed-failure probe, like the newest dev Python) is noise, so triage a red matrix with `select(.conclusion!="success" and (.name|startswith("✅")))`, not by which Python version failed). If `/babysit-ci` is excluded here, the agent runs the same fetch-logs/fix/commit/push/re-poll loop inline (and the sub-agent rules cover a failed spawn). Its prompt restates the sub-agent rules (the trailer and narrow staging especially: its commits are exactly the unattended ones those rules exist for) and adds:

- **The loop condition, verbatim**: "re-poll after each push; do not return after a push without re-polling". The turn ends only when every monitored workflow on the latest `main` HEAD has `conclusion: success` (or `skipped` for benign reasons), or on a real blocker it cannot resolve. Terser phrasings get misread as "report after first fix", and the agent returns while the slow jobs still build, doubling wall-clock when you re-spawn it.
- **The poll cadence**: every poll loop sleeps at least 45-60 seconds between iterations, with the `sleep` inside the loop command. Zero-delay spins exhaust the shared REST quota (5,000 requests/hour) in minutes, and the exhaustion resurfaces as PAT-permission-shaped workflow failures and `prepare-release` hangs (see babysit's § GitHub API rate-limit exhaustion).
- **Poll in-process; never detach a monitor**: the poll loop must block inside the agent's turn (a foreground loop or `gh run watch`), never a `run_in_background` Bash poller or a `Monitor`-tool stream the agent idles on awaiting notification. Name the `Monitor` tool in the prohibition: an agent told only "no background poller" does not classify `Monitor` as one, reaches for it, and idles mid-watch. Babysit itself forbids detached monitors, but a spawn prompt with an "as a background task" aside overrides that, and the agent follows the prompt: a failure landing in the idle window then goes unhandled.
- **Interim status pings**: a message at startup (local gate result, which runs it watches) and on every state change (fix pushed, workflow landed, re-run triggered), not only at the end. A silent babysitter is indistinguishable from a dead one.

**Treat its return as a claim, not proof.** Even with the verbatim prompt it can stop early (the long Nuitka wait is where it gives up). Re-poll `gh run list --branch main` yourself and read each monitored workflow's conclusion; anything still `queued`/`in_progress` or non-green means it stopped early: take over the loop inline rather than re-spawning it into the same idle. On takeover:

- **Inspect the tree before improvising a fix** (`git status`, `git diff --cached`): a stood-down or idled agent often leaves a correct fix **staged but uncommitted** (a hardware signing prompt it could not answer). Adopt and verify *that* fix instead of re-deriving a parallel one that then collides with it.
- **Poll at the job level** (`gh run view <run> --json jobs`), the way `/babysit-ci`'s own poll does, never the run's `conclusion` alone: a run holds at `queued`/`in_progress` until its whole matrix drains, so a fast stable job that already failed stays invisible to a run-level check for as long as the slowest cell runs (a failed `once-tests` job once hid for half an hour behind a 40-minute macOS cell that ultimately passed). Break the instant any stable (`✅`) job turns `conclusion == "failure"`.
- **Log fetches may need the sandbox off**: `gh run view --log-failed` caches under `~/.cache/gh`, which the sandbox denies; the `creating cache entry ... operation not permitted` failure masquerades as a `gh` bug.

**Verify the Nuitka run yourself, starting with whether the project builds binaries at all:**

- A project with `[tool.repomatic] nuitka.enabled = false` or no CLI entry point emits no `nuitka_matrix` (see `Metadata.nuitka_matrix` in `metadata.py`): the engine's per-platform build and test jobs skip by design on **every** push, release commits included, and past releases carry no binary assets (`gh release view <last-tag> --json assets` settles the regime in one call). There is no binary signal to verify and none appears on merge either (the `release_commits_matrix` gate drives the publish/tag lanes, not the binary matrix): wheel-plus-sdist is the complete release shape.
- When binaries are enabled, babysit's "every stable job passes" never covers them: its early exit declares success once the fast platforms are green, while macOS and the entire `release.yaml` matrix still build. Independently confirm the `release.yaml` run reached a terminal green state (`gh run watch <release-run-id>`, then read its `conclusion`); never infer the Nuitka result from babysit's summary. If a binary build fails, re-spawn babysit or fix inline.
- A green `conclusion` also proves nothing on a HEAD that touched no Python source: `release.yaml` skips the entire `compile-binaries` matrix on such pushes (workflow-only, docs-only). Read the run's *jobs* and confirm the per-platform build and test jobs ran rather than skipped; when they skipped, the authoritative binary signal is the last run that actually compiled, valid only while its source tree matches the release tree. When no compiled run matches the release tree (a binary-relevant commit's run cancelled by supersession, then the reconciliation HEAD content-skipped the matrix), dispatch one: `gh workflow run release.yaml --ref main`. A dispatch carries no push diff for the skip heuristic to read, so it compiles and self-tests the full per-platform matrix on the current tree, with no commit and no PR churn.

**Close the coverage holes a busy cycle opens:**

- **Refresh the release PR after non-trigger pushes.** Whether a push re-runs `prepare-release` (and so refreshes the PR onto your new HEAD) depends on `changelog.yaml`'s `paths:` filter, which varies per repo: do not infer it from the path list. Once `main` is green, verify `changelog.yaml` actually ran on your latest commit (`gh run list --workflow changelog.yaml --branch main` shows a green run titled with your commit). Only if it did not, run `gh workflow run changelog.yaml --ref main`; then confirm the `prepare-release` branch contains your final commit before step 7.
- **A racing version-increment merge can leave your commit's heavy CI uncompleted.** Merging the `minor-`/`major-version-increment` PR mid-build cancels your in-flight `tests`/`lint` (shared concurrency group) while the bump commit is itself gated out of them, so the release PR can show them `skipped`. This is by design: step 2 is the authoritative pre-merge check, so read `skipped` tests/lint on a bump commit as expected and do not re-push to force a run.
- **When no Tests run ever completed on the release tree, dispatch one.** Superseded-run cancellation, the version-bump gate, and `tests.yaml`'s `paths:` filter can leave every attempt on a busy cycle `cancelled` or `skipped`, and recent Tests *activity* is not a completed run on the current tree. If the local pytest was also skipped (the integration-heavy exception), no test signal exists anywhere: get one with `gh workflow run tests.yaml --ref main` (a `workflow_dispatch` adds no commit and does not regenerate the PR), then verify the stable jobs and ignore the `continue-on-error` probes. A docs-only HEAD shares its source tree with the prior commit, so the dispatched run validates the frozen tree. The same hole opens for every paths-filtered workflow, Docs included (a cancelled `docs.yaml` run followed by a workflow-only HEAD leaves the cycle's docstring edits unbuilt): close it the same way (`gh workflow run docs.yaml --ref main`) and confirm the dispatched run lands green.

**Reconcile the changelog against every fix babysit committed: entries it added *and* omitted.** Walk its commits and blame each fix against the last release tag: a bug that only ever existed in code introduced this same cycle is a user no-op (drop any entry babysit added for it); a bug that reached an earlier release deserves the entry babysit may have skipped. Re-run step 1.3's consolidation with both corrections and present the diff (step 4) before committing. This second pass is itself a push that re-runs CI: complete it before the step-7 confirmation.

**Surface maintainer work that appeared during the wait.** The 30+ minute CI wait gives the maintainer time to keep coding: those uncommitted files are theirs (sub-agent rules). List them in the step-7 report so the maintainer decides whether each belongs in this release (commit and push before merge) or the next.

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
- **Binaries** for all 6 platform/architecture combinations (linux-arm64, linux-x64, macos-arm64, macos-x64, windows-arm64, windows-x64), when the project builds them: it does only with `[tool.repomatic] nuitka.enabled` and a CLI entry point, and the previous release's assets show which regime applies.
- **PyPI package** at the matching version.
- **`changelog.md`** entry with the release date and comparison URL finalized.
