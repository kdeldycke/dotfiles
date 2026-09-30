# Common failure patterns

Failure shapes the `babysit-ci` loop meets, and what each one needs. `SKILL.md` holds the loop itself.

<a id="mypy-ruff-fix-oscillation"></a>

## mypy/ruff fix oscillation

mypy and ruff can enter a fix loop where each tool's fix breaks the other. Common triggers:

- **Unused import**: ruff removes an import (`F401`), mypy then complains about a missing name; re-adding triggers ruff again.
- **Type annotation style**: mypy requires an explicit annotation, ruff considers it redundant or wants a different form.
- **`noqa` vs `type: ignore`**: `# noqa` silences ruff but not mypy; `# type: ignore` silences mypy but ruff flags the unused directive.

When the same lines toggle between fixes across iterations, stop and apply a combined resolution: a `# type: ignore[code]` with a matching `# noqa: XXXX` on the same line, or a restructuring that satisfies both at once.

## mypy scope mismatch (local vs CI)

The classic false green: mypy passes locally over a subset of directories while CI checks **every tracked Python file** (`tests/` and `docs/` included). Run it as a bare `repomatic run mypy` and the runner resolves that same list, so an error in a test or docs file surfaces before the push rather than after it. A directory list is what reintroduces the gap.

## Platform-specific test skips

Some tests are skipped on certain platforms (`windows-11-arm` has no Python 3.10 ARM64 build). Before investigating missing results, check the matrix `exclude` section in `tests.yaml` and the `skip_platforms` entries in the binary self-test plan (`tests/cli-test-suite.toml`): individual cases can opt out of platforms without affecting the CI matrix.

## Cross-platform divergence

When a test passes locally but fails in CI, check platform differences before changing logic:

- **Path lengths**: `~/.config/...` is shorter on Linux than macOS/Windows equivalents, affecting text-wrapping assertions.
- **Terminal width**: CI runners may default differently than local dev machines.
- **Encoding**: Windows defaults to `cp1252`, not `utf-8`.
- **Line endings**: `\r\n` vs `\n` breaks exact-match assertions.
- **Untracked files**: tests that enumerate files (`python_files`, `doc_files` metadata) see untracked local files that CI's clean checkout lacks. When updating expected file lists, include only tracked files; run `git status` to spot the divergence.

## Workflow and infrastructure failures

Not all CI failures are code bugs:

- **Runner timeouts or OOM kills**: the log ends abruptly or shows `The runner has received a shutdown signal`. Re-run; do not change code.
- **A runner that died mid-step**: the step runs far past its baseline, and a cancel does not stop it. A live runner kills a cancelled step within ten seconds and keeps its partial log. A cancel does not apply to a job whose `if:` holds `always()`, so read that condition first. Any other job still `in_progress` a minute after the cancel has lost its runner: the server closes it at the five-minute [cancellation timeout](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-cancellation), and no log survives, neither at the job's log endpoint (`BlobNotFound`) nor in the run's log archive. A 404 from a job that is still running proves nothing, since every running job returns one. Re-run with `--failed`: there is nothing to diagnose.
- **Action version mismatches**: `Unable to resolve action`, deprecated-runtime errors. Fix the workflow YAML, not the Python.
- **Network/registry flakiness**: `uv`/`pip` timeouts, PyPI 503s, `ConnectionResetError`. Re-run.
- **A wall-clock budget assertion** (`assert elapsed_ms < N`) failing on a shared runner: infrastructure is the *trigger*, but the defect is the test, which took one sample and so measured that runner's worst moment rather than the code. A re-run only re-rolls the dice, and the tell that it has been re-rolled before is a budget already ratcheted upward in an earlier cycle for the same runner class. Assert on the fastest of several samples instead: a real regression slows every sample, a scheduling stall slows one. Raising the budget again is the fix that stops working.
- **Permission errors**: `Resource not accessible by integration`, 403s. Check `gh api rate_limit` first ([§ GitHub API rate-limit exhaustion](#github-api-rate-limit-exhaustion)), then token permissions; never code.
- **A whole workflow red with nothing executed**, every job reporting failure and the `metadata` job unable to resolve its own toolkit pin: the inline `uvx 'repomatic==X.Y.Z'` command is missing `--exclude-newer-package repomatic=P0D`, so the workflow-wide `UV_EXCLUDE_NEWER` refuses a pin naming a release younger than the window, and each `needs: metadata` job dies with it. Splice the flag onto that command line — `uvx` reads no project configuration, so there is nowhere else the bypass can live — or merge the `sync-workflow-pins` PR that backfills it. `lint-repo`'s fatal `self-pin-cooldown-exemption` check names the offending files. Re-running changes nothing.

For infrastructure, re-run the failed jobs (`gh run rerun <RUN_ID> --failed`) and continue polling; never modify code to work around transient infra. **A release run is the exception**: when an orchestrator like `/repomatic-ship` spawned this loop, a flake surfaced here is debt owed under that skill's genuinely-green goal, so a red whose defect lives in the repository (the wall-clock budget above, a tolerated-exit set that needs widening) gets fixed at the source instead. "Transient infra" then names the trigger, not the remedy. A red with no repo-side defect at all, like a runner OOM or a PyPI 503, is still a re-run.

**`--failed` also re-runs the jobs skipped behind a failure.** Each failed or cancelled job re-runs with every job that `needs:` it, skipped ones included. So one rerun restores the whole chain: never re-run the whole workflow to reach a skipped dependent.

<a id="github-api-rate-limit-exhaustion"></a>

## GitHub API rate-limit exhaustion

Heavy polling from this loop spends the same REST quota (5,000 requests/hour) as every workflow authenticating as the same user (`REPOMATIC_PAT`). Exhaustion produces two failure shapes that look unrelated to quotas:

- Local `gh` calls fail with `HTTP 403: API rate limit exceeded`.
- Workflows fail with *permission-shaped* errors: `lint-repo` reports the PAT lacks `Contents`/`Dependabot`/`Workflows` scopes, or a `Sync pull request` step (`repomatic pr-sync`) stalls on the GitHub API until its `timeout-minutes` or the concurrency group kills the run.

Diagnose with `gh api rate_limit` **before** touching token settings: `remaining: 0` on the `core` bucket confirms it. Recovery: wait for the printed `reset` epoch, then re-run the failed workflows unchanged (`gh run rerun <RUN_ID> --failed`); they go green with no commit. While waiting, degrade to the channels that stay live: the GraphQL bucket is metered separately (`gh api graphql` for a commit's check suites, refs, and releases; `gh pr list` / `gh pr view`), and `git fetch` over SSH covers branch and commit verification.

<a id="pr-merge-permission-wall"></a>

## PR-merge permission wall

`gh pr merge` — and other write-heavy verbs (force-push, `reset --hard`, repo or release delete) — is commonly hard-denied in the operator's own Claude Code `settings.json` as a standing guard against irreversible actions, independent of any conversation. This deny is structural, not a per-call prompt: it fires identically whether or not a maintainer just authorized the exact command in chat, because it blocks the tool call itself rather than asking. Signs you have hit it, not a normal prompt: the denial is immediate with nothing to answer, and it recurs identically after a fresh, explicit, real-time go-ahead. Do not retry it, and do not read a maintainer's chat-level "yes, merge it" as actionable — a deny rule cannot be cleared from inside the session. Report the wall once and ask the maintainer to run the merge themselves, fully outside this session (their terminal, or the GitHub web UI): that is the only path this deny shape leaves open. The same holds when a hardware-key signing refusal blocks a direct commit (step 7 of `SKILL.md`): with both remedies walled, the release advances only by a human acting outside the tool.

## Nuitka binary build failures (release.yaml)

This section only applies to projects that build binaries (`[tool.repomatic] nuitka.enabled` with a CLI entry point); on a Nuitka-disabled project the per-platform jobs skip on every push and there is no matrix to fail. When enabled, the engine runs Nuitka across a 6-way OS/arch matrix on release commits, on the weekly `schedule` and on `workflow_dispatch`, narrowing an ordinary push to the `[tool.repomatic] nuitka.dev-targets` canary subset (job names are templated per platform, like `✅ {os}, {sha} build`); catching a break while the version is still `.dev0` avoids shipping a release with missing or broken binaries, which the immutable-release wall makes unrecoverable. Triage by category:

- **Infrastructure** (runner OOM, shutdown signal, macOS runner crash, registry timeout): re-run the failed job (`gh run rerun <RELEASE_RUN_ID> --failed`); binary builds are resource-heavy and macOS runners crash more than most.
- **Nuitka configuration** (`Error, unsupported ...`, an unknown `--flag`, a missing data file): fix `[tool.nuitka]` in `pyproject.toml`, not the Python source; verify each key maps to a current Nuitka option.
- **Real compile or runtime errors** (the binary builds but its smoke test fails, a `ModuleNotFoundError` at runtime): fix the code or the `include-package`/`include-data-files` configuration, then push and re-monitor.

The matrix is slow: let `tests.yaml` and `lint.yaml` set the loop cadence, but act on a red build cell the moment it lands, like any stable failure (every faster channel has already reported by then): fix, push, supersede. Never idle out the rest of a matrix you already know is doomed.

**A *cancelled* canary cell is a coverage gap, not a failure, and `--failed` closes it cheaply.** Supersession routinely kills the canary mid-build (an automation PR merges, the concurrency group cancels it), and the pushes behind it often skip the matrix outright, so the binary signal for the last code-affecting tree is simply missing with nothing in flight to supply it. Reach for `gh run rerun <cancelled-run-id> --failed` rather than `gh workflow run release.yaml`: the rerun rebuilds only the cancelled cell and its dependents, leaving every skipped job skipped, where a dispatch compiles the whole platform fleet. The precondition is that the cancelled run's binary-affecting tree still matches `HEAD`, since the rerun rebuilds that run's commit and not the current one: check with `git diff --name-only <that run's headSha>..HEAD` and confirm nothing in it touches `Metadata.binary_affecting_paths`.

**On a release run, a red build cell means that version ships short, permanently.** When the run's head commit is a `[changelog] Release vX.Y.Z` push, `publish-release` sits at the end of that same run and flips the draft to published once the asset jobs settle, locking the asset list. Whatever the matrix failed to produce by then is missing from that version forever: no re-run, no later upload.

**This is by design, so do not try to stop it.** Publishing a release short beats holding it, and the recovery is the next version, not a draft the maintainer has to babysit. Keep doing exactly what you do for any stable red: fix the cause, push, and let the fix ride the next release. The one addition is reporting: name the platforms that version lost, so the maintainer knows the gap exists and can note it in the release. A short ship also leaves the changelog section, the release body and `docs/install.md` still advertising binaries that are not there (the `repomatic-ship` skill's § Repairing a short ship covers the cleanup); flag it rather than fixing it silently mid-loop.

## Autofix job failures (autofix.yaml)

`autofix.yaml`'s jobs normally commit their fixes; a job that *crashes* turns the workflow red without producing one. Fetch the failed log (`gh run view <AUTOFIX_RUN_ID> --log-failed`) and triage:

- **Tool-runner checksum mismatch** (`ValueError: SHA-256 mismatch for https://...`): the pinned binary's hash no longer matches the published artifact, usually an upstream re-publish. Regenerate with `repomatic update-checksums`, then confirm with `repomatic run <tool>`.
- **External-tool output parse error** (a `RuntimeError`/`KeyError` in a parser, like `fix-vulnerable-deps` reading `uv audit` JSON): the tool's output schema drifted. Fix the parser and update the test fixture encoding the old shape.
- **Dependency fails to build on the runner** (`Failed to build <pkg>`, a `maturin`/`cargo`/native-compiler error during install): usually self-inflicted, not upstream: a `runs-on` change *this cycle* moved the job to an architecture with no published wheel, forcing a doomed source build. Check `git log <last-tag>..HEAD` for the runner swap and revert it; a genuinely broken upstream artifact (failing on *every* platform) is the rarer case.
- **Genuine content the job fixes** (real typos, an actual vulnerability): the job commits the fix and goes green on its own; nothing to do.
