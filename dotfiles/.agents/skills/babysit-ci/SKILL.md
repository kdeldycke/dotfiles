---
name: babysit-ci
description: Monitor CI tests, lint, autofix, docs, and Nuitka binary-build workflows, diagnose failures, fix code, commit, and loop until all stable jobs pass. Ignores unstable failures.
compatibility: 'Designed for Claude Code. Recommended model: Sonnet.'
---

# Babysit CI: monitor and fix tests.yaml + lint.yaml + autofix.yaml + docs.yaml + release.yaml binaries

Monitor the `tests.yaml`, `lint.yaml`, `autofix.yaml`, `docs.yaml`, and `release.yaml` (Nuitka binary matrix, on projects that enable it) workflows in a fix-verify loop until all stable matrix variations pass and type-checking is clean.

## Invocation

This skill involves repeated `gh`, `git`, `uv run pytest`, `git commit`, and `git push` calls. Run with `--dangerously-skip-permissions` to avoid manual approval on each step. Sonnet is recommended: the task is mechanical (fetch logs, match patterns, edit code, commit) and doesn't need deep reasoning:

```shell-session
$ claude --dangerously-skip-permissions --model sonnet /babysit-ci
```

> [!WARNING]
> `--dangerously-skip-permissions` bypasses every permission prompt for the whole session: only use it in an environment you trust, ideally a sandbox or disposable checkout, never against an unfamiliar repository or untrusted input.

Because this loop runs autonomously without human review, **every commit carries a `Co-Authored-By: Claude <noreply@anthropic.com>` trailer by default** so unattended changes stay traceable, including where a project `CLAUDE.md` or a global `~/.claude/CLAUDE.md` has not synced that convention. The default yields to one thing: an explicit standing rule from the repository's maintainer against AI attribution, which outranks it because the trailer lands in their permanent history. A parent skill (like `/repomatic-ship`) spawning this loop does not by itself relax the requirement, but an exemption that skill passes down does, and it binds every commit made from that point on.

Keep the message itself short, per `claude.md` § Commit messages: an imperative subject naming the fix, under 72 characters, and **no body at all** unless the why is not evident from the diff. A CI fix rarely needs one — `` Fix Windows path assertion in `test_cache_paths` `` is a complete commit message. The exception worth taking: when the red traces to an upstream bug, a dependency release or a linked discussion, put that link in the body, since it is the only place the next reader will find why the fix looks the way it does.

### Yield to the orchestrator that spawned you

When `/repomatic-ship` or another orchestrator spawns this loop as a sub-agent, it may reach in to claim a specific fix, usually one touching a deliberately-kept structure that needs its own judgment. Honor that at once: a message telling you to **hold, stop, or stand down** on a fix (or on the whole loop) means stop editing the working tree immediately, reply to acknowledge, and neither commit nor push that fix. Mailbox messages are delivered between tool calls, so read yours before every edit and before every commit: a HOLD that landed while you were mid-edit still binds the moment you see it, and you must not race the orchestrator by finishing the edit first. Unless told to stand down entirely, keep polling and reporting the jobs it did not claim, and let it tell you which HEAD to resume on once its fix lands.

## Timeline

Three feedback channels run in parallel after every push, each at a different latency. Fix as soon as the **fastest** channel reports a failure: do not wait for slower channels.

```
 time   LOCAL (free)              REMOTE (CI minutes)
 ────   ────────────              ───────────────────
 0:00   push
        ├─ pytest ─┐              ├─ lint.yaml ─────────────────────┐
        ├─ mypy ───┤              │   (mypy on all files, YAML,     │
        └─ ruff ───┘              │    secrets, zizmor)             │
                                  │                                 │
                                  └─ tests.yaml ─────────────────┐  │
                                      (12 stable + 6 unstable)   │  │
                                                                 │  │
 0:30   GATE 1: local done                                       │  │
        fail? ─── yes ──► step 5 (fix now, skip CI)              │  │
                   no ──► poll CI                                │  │
                                                                 │  │
 3:30                     GATE 2: lint.yaml done ◄───────────────│──┘
                          mypy fail? ─── yes ──► step 4-5        │
                                          no ──► continue        │
                                                                 │
 5:00                     GATE 3: tests.yaml fast jobs done ◄────┘
                          stable fail? ── yes ──► step 4-5
                                           no ──► early exit if only macOS left (human runs; orchestrator waits)

 8:00                     tests.yaml macOS done (often skippable)

                          all green? ──► DONE
```

After fixing (step 5-7), the loop restarts from the top: push, run all three channels again.

## Loop

1. **Detect the repo and branch** from the current working directory:

   ```shell-session
   $ gh repo view --json nameWithOwner --jq '.nameWithOwner'
   $ git branch --show-current
   ```

   Use the detected branch for all `--branch=` flags below.

2. **Get the latest runs** for the current branch:

   ```shell-session
   $ gh run list --workflow=tests.yaml --branch=<BRANCH> --limit=1
   $ gh run list --workflow=lint.yaml --branch=<BRANCH> --limit=1
   $ gh run list --workflow=autofix.yaml --branch=<BRANCH> --limit=1
   $ gh run list --workflow=docs.yaml --branch=<BRANCH> --limit=1
   $ gh run list --workflow=release.yaml --branch=<BRANCH> --limit=1
   ```

   Track all five run IDs (`docs.yaml` may have none: its `paths:` filter skips pushes touching nothing docs-relevant). An empty run list for the *other* workflows is not paths-filtering: GitHub can sit on a push event for hours before materializing any run (a 4-hour lag has been observed), so when a freshly pushed SHA shows no runs, keep re-polling instead of concluding the push was filtered, and measure the wait from run creation, not from the push. The `tests.yaml` run exercises the full test matrix; `lint.yaml` runs mypy on every tracked Python file and lints YAML; `autofix.yaml` runs the mechanical fix jobs (`format-*`, `sync-*`, `fix-typos`, `fix-vulnerable-deps`) and turns red when one *crashes* instead of committing a fix; `docs.yaml` builds and deploys the Sphinx site and runs the broken-links check (an externally cancelled or link-flaky run re-runs cleanly via `gh workflow run docs.yaml --ref <BRANCH>`, no commit needed); `release.yaml` runs the Nuitka binary matrix (dev binaries: an ordinary push rebuilds only the `[tool.repomatic] nuitka.dev-targets` canary subset, while release commits, the weekly `schedule` and `workflow_dispatch` build the full target fleet) — but only on projects with `[tool.repomatic] nuitka.enabled` and a CLI entry point; with Nuitka disabled the per-platform jobs skip on every push, release commits included, and a green `release.yaml` means package build plus dev pre-release sync only. Even with Nuitka enabled, a single push can still skip the matrix: `Metadata.skip_binary_build` (`repomatic/metadata.py`) is the authoritative signal, true when the head commit is on a non-code branch, is a user-initiated version-bump commit, or (the common case) its changed files fall entirely outside `Metadata.binary_affecting_paths` — a docs-only or workflow-only commit, say. Don't infer the reason from the commit message or assume an unrendered/skipped matrix job name means `nuitka_matrix` itself was empty: the matrix data can be fully populated for that exact commit (verify via the `release / 🧬 Project metadata` job's logged `metadata=` JSON output) while the workflow still elects not to build it. Check `skip_binary_build`'s three conditions before asserting why a matrix skipped. All must pass — see § Autofix job failures and § Nuitka binary build failures below for how to triage them without stalling the loop.

3. **Run local tests while waiting for CI.** Don't idle while polling. Start the full test suite and linters locally in the background immediately:

   ```shell-session
   $ uv run pytest --no-header -q &
   $ uv run --group typing repomatic run mypy &
   $ uv run repomatic run ruff -- check repomatic tests docs &
   ```

   Give `run mypy` no arguments: the tool runner resolves the same file list CI's `lint.yaml` runs it on, so the two cannot diverge. Naming directories instead is what used to make mypy pass locally and fail in CI.

   **Gate 1 (local, ~30s):** if any local check fails, you already have the diagnosis: skip straight to step 5 without waiting for CI.

   If local passes, poll CI every 60 seconds with:

   ```shell-session
   $ uv run repomatic ci-status --branch=<BRANCH> --no-fatal
   ```

   It reads every workflow a push can start (derived from `.github/workflows/`, so its list is wider than the five above), reports each one's latest run, and names the failing jobs that actually gate a merge. Three traps it settles, so no hand-rolled `jq` has to: a run's own `status` lags its jobs (every monitored workflow can read `queued` while a dozen jobs have already finished, which is indistinguishable from the runner-cap saturation a busy account genuinely hits); a `continue-on-error` probe that crashed hides inside a `success` run conclusion; and a run whose `conclusion` is `failure` with *no* failed job is a workflow-level error (an invalid `strategy.matrix` expression, malformed YAML, a missing secret) with no job log to read, which the command flags rather than letting you write off a persistently-red workflow as a known artifact.

   The one thing run state *does* gate is log retrieval (step 4): job logs stay unreadable until the parent run itself reaches a terminal state.

   **A queue is not a hang, and elapsed time alone cannot tell them apart.** A long stall invites the theory that some run is stuck and that cancelling it would free the pool, which is a conclusion worth reaching only on evidence, because acting on it destroys work that was progressing fine. Two readings settle it, and neither is the elapsed clock. Get a **baseline** from that workflow's recent successful runs (`gh run list --workflow <wf> --repo <owner/repo> --status success --json createdAt,updatedAt`): a suite whose normal duration is two hours is not hung at ninety minutes. Then read **per-job `completedAt` timestamps** (`gh run view <id> --json jobs`) rather than an aggregate: a flat count of `in_progress` jobs is not evidence of a stall, since jobs finish and others start into the freed slots, holding the count steady while real progress continues. Watch for the self-contradiction that exposes the mistake, a report that the count "dropped from 11 to 9" *and* that nothing has changed. Two smaller traps live here too: `gh` reports a pending job's `conclusion` as `""`, not `null`, so a `select(.conclusion == null)` filter silently matches nothing and reads as "no pending jobs"; and jobs queue against the runner pool their `runs-on` names, so a stall confined to macOS cells says nothing about Linux capacity. **Never cancel another repository's run to free slots without the maintainer's explicit go-ahead**, and never ask for that go-ahead on a diagnosis you have not backed with a baseline and timestamps.

   **Gate 2 (lint.yaml, ~4 min):** `lint.yaml` finishes before `tests.yaml`. If "Lint types" (mypy) fails, proceed to step 4 immediately.

   **Gate 3 (tests.yaml, ~5-8 min):** once the first stable job fails, or all fast platforms (Linux, Windows) pass, proceed.

   **Poll in-process; never detach a monitor.** Block on `gh run watch <RUN_ID>` or loop the polls within your own turn. A detached background monitor (a standalone process, a `run_in_background: true` Bash poller that re-invokes you when it exits, or a `Monitor`-tool stream that returns control on each tick) makes a parent-resumed run spawn *another* monitor per tick instead of driving to a terminal state; worse, a spawned sub-agent that detaches this way orphans the poll from its caller the moment it returns. Hold the turn until the run completes: starting a poller and handing back "to be notified" is the early return this loop must never make.

   **Every wait between polls must be a `sleep`, never a busy-wait.** A poll loop with no delay (`until gh run view ...; do true; done`) fires thousands of requests per minute and exhausts the REST quota (5,000/hour) within minutes. The harness blocking a bare foreground `sleep` is not a reason to drop the delay: put the `sleep 60` *inside* the loop command itself, which runs fine in both foreground and background. Exhaustion does not just blind your own polling — workflows authenticating with the same PAT start failing server-side with misleading errors (see [§ GitHub API rate-limit exhaustion](#github-api-rate-limit-exhaustion)).

4. **On any CI failure**, cancel the branch's remaining runs to free runners:

   ```shell-session
   $ uv run repomatic cancel-runs --branch=<BRANCH>
   ```

   The command spares any run whose head commit carries `[changelog] Release`, mirroring the `cancel-in-progress` condition in every workflow's concurrency group. Cancelling a release run costs that version its binaries permanently, so never hand-roll the sweep with `gh run cancel`.

   Then download logs from **all** failed jobs across the workflows (logs are retained after cancellation):

   ```shell-session
   # Failed stable test jobs:
   $ gh run view <TESTS_RUN_ID> --json jobs --jq '[.jobs[] | select(.conclusion == "failure" and (.name | contains("⁉️") | not))] | .[].databaseId'

   # Failed lint jobs (especially "🛡️ Lint types" for mypy):
   $ gh run view <LINT_RUN_ID> --json jobs --jq '[.jobs[] | select(.conclusion == "failure")] | .[].databaseId'
   ```

   The first filter negates the unstable glyph rather than matching a `✅` prefix, mirroring `JobStatus.required`. `tests.yaml` runs four required jobs whose names carry no `✅` at all (`🧬 Project metadata`, `1️⃣ Run-once tests`, `📦 Package install`, `🖥️ Validate …`), and the release engine prefixes the workflow ahead of the glyph, so a prefix test silently drops a real failure from the batch.

   Fetch each failed job's log (`gh api repos/<OWNER>/<REPO>/actions/jobs/<JOB_ID>/logs`) and fix them as one batch: different sources surface different issues, and logs survive cancellation. Batch only what has *already failed*, never what might still fail. Once every harvested failure is root-caused and fixed, push immediately rather than waiting for undrained cells to surface more: the fresh run supersedes the stale one, and serially waiting out each full matrix is the slow path. Analyze following the [error triage discipline](#error-triage-discipline): stable-job `FAILED`/`AssertionError` lines only.

   `gh run view --log-failed` writes its log cache under `~/.cache/gh`, which the harness sandbox denies: the resulting `failed to get run log: creating cache entry ... operation not permitted` masquerades as a `gh` bug. Disable the sandbox for that read, exactly like the signing calls in step 7.

   **A completed job's log is readable while the rest of the run drains, but only with `--allow-escape-sequences`.** The run-scoped reads *are* gated on the whole run going terminal (`gh run view --log-failed` answers `run <id> is still in progress; logs will be available when it is complete`), while the job-scoped `gh api repos/<OWNER>/<REPO>/actions/jobs/<JOB_ID>/logs` answers a failed cell immediately, twenty minutes into its slowest sibling's build. What makes it look otherwise is a `gh` guard rather than the API: CI logs carry ANSI colour, so `gh` refuses to emit them and prints `the response contains terminal escape sequences; pass --allow-escape-sequences to output it anyway` — one line where a log was expected, indistinguishable from an empty body if the output went to a file. Pass the flag and strip the codes:

   ```shell-session
   $ gh api repos/<OWNER>/<REPO>/actions/jobs/<JOB_ID>/logs --allow-escape-sequences \
       | sed 's/\x1b\[[0-9;]*m//g' > job.log
   ```

   So the diagnosis is minutes away, not an hour: harvest every failed cell as it lands and keep the run alive for the cells still to report. Cancelling to read logs is never the reason — logs survive cancellation, but they never needed it. **Make the run terminal only when you have a fix**, per the batch-and-push rule above: the stale run has no verification value left once superseded.

5. **Fix the root cause** using the combined picture from CI logs and local results. Fix the codebase, not the tests, unless the tests are genuinely wrong. Address mypy and ruff failures together (see [§ mypy/ruff fix oscillation](#mypy-ruff-fix-oscillation)).

   If the root cause is in a third-party dependency, check whether a change *this cycle* exposed it before treating it as upstream: `git log <last-release-tag>..HEAD` for a runner/image swap, a dependency bump, or a config change that put the dependency in a context it cannot satisfy (a Rust-built package forced to compile from an sdist on an architecture with no published wheel, say). When a cycle change is the trigger, revert or adjust *that* change; only a failure independent of everything the cycle touched warrants `/file-bug-report` for an upstream report.

   After applying fixes, re-run the full local validation:

   ```shell-session
   $ uv run pytest --no-header -q
   $ uv run --group typing repomatic run mypy
   $ uv run repomatic run ruff -- check repomatic tests docs
   $ uv run repomatic run ruff -- format repomatic tests docs
   ```

   **Hard gate:** all four must come back clean before step 6. If a fix introduces new failures not in the original set, the fix is wrong: revert it and try a different approach rather than layering another fix on top.

   Both ruff commands write in place: read `git diff` after they run and fold any reformat into the fix. Skipping the `format` pass does not fail CI — instead the `format-python` autofix job pushes the reformat as its own commit, a new HEAD that cancels every in-flight run through the shared concurrency group and restarts the whole CI cycle (a wasted Tests + Nuitka round). A parent `/repomatic-ship` run's format gate only covered the pre-fix tree: this loop's commits are exactly the ones that would skip it.

6. **Check autofix status before pushing:**

   ```shell-session
   $ gh run list --workflow=autofix.yaml --branch=<BRANCH> --limit=1
   $ gh pr list --state=open --json number,title,headRefName,url
   ```

   If any open autofix PR already contains your fix — a `format-python` branch (ruff's own autofixes), a `sync-repomatic`/`sync-workflow-pins` branch (a bumped workflow pin, or a spliced-in `--exclude-newer-package` cooldown exemption carrying no version bump at all — that one is the whole fix when the `metadata` job cannot resolve its own pin), or another `sync-*`/`fix-*` branch — prefer merging it over authoring your own commit: GitHub signs the merge commit server-side, so this sidesteps a local hardware-key signing prompt entirely. If it resolves the failure, merge it (`gh pr merge <n> --squash --delete-branch`), pull, and rebase your fix before pushing — or skip your own commit if the merge is the whole fix. If `gh pr merge` is denied outright (a standing `permissions.deny` on the verb, not a retryable prompt), see [§ PR-merge permission wall](#pr-merge-permission-wall).

7. **Commit the fix** with a clear message describing what changed and why, then `git push`.

   When the fix corrects a *user-facing* bug, add a `changelog.md` entry **only when the bug reached a released version**. Blame the changed line against the last release tag (`git blame`, or `git log -S`): a bug introduced *and* fixed within the current unreleased cycle never shipped, so it gets no entry; a bug that predates the last tag is a real regression and does. Making this call here keeps a parent `/repomatic-ship` run from having to add or drop entries afterward.

   **Time each push by what its diff rebuilds.** A source-affecting fix (`repomatic/**`, `tests/**`, `pyproject.toml`, `uv.lock`: whatever the repo's test and binary `paths:` filters name) pushes the moment it clears step 5: the runs it supersedes were verifying an obsolete tree, and its own run rebuilds everything it cancels. A commit those filters skip (changelog-only, docs-only, cosmetic prose) is the opposite case on a binaries-enabled project: `release.yaml` runs on *every* push in a per-branch cancel-in-progress group, so pushed mid-drain such a commit cancels the in-flight binary matrix while its own run skips the rebuild (`Metadata.skip_binary_build`), and the lost verification costs a full re-dispatch. That cost scales with what is actually in flight: an ordinary push builds only the `[tool.repomatic] nuitka.dev-targets` canary subset, and no push cancels a full fleet at all, since release commits, `schedule` and `workflow_dispatch` runs each sit in their own concurrency group. Hold it until the heavy matrices on the current HEAD are terminal, or bundle it into the next source-affecting push; with binaries disabled, only a canary build in flight, or nothing heavy in flight, push freely.

   **If commit signing fails, do not loop on it.** The sandbox can block the SSH key or socket under `~/.ssh/*` (`Operation not permitted`): fix with `dangerouslyDisableSandbox: true` for the `git commit` and `git push` calls only. A hardware-backed key (Secretive, YubiKey, TPM) then prompts the maintainer per signature, and a refused or missed prompt surfaces as `agent refused operation?`, indistinguishable from a real failure. Retry once at most after disabling the sandbox; if it still refuses, hand off cleanly: stage the specific files you fixed (never `git add -A`), return the exact commit message and `git push` command verbatim, and exit the loop. The fix is done — only the signature is missing. If the block is instead a structural permission deny on `gh pr merge` (not a signing refusal), the escalation differs — a maintainer's in-chat approval cannot clear a deny rule: see [§ PR-merge permission wall](#pr-merge-permission-wall).

8. **Repeat from step 2** until the monitored workflows are green: `tests.yaml` with all stable (✅) jobs passing, `lint.yaml` with no mypy failures (test and docs files included). **Stop after 5 iterations without progress** (the set of distinct failing stable jobs did not shrink): report what was fixed and what remains, and ask for guidance rather than churning. Productive iterations never trip the cap: a release paying down a long test-debt tail legitimately takes more than five pushes.

### Early exit (human-invoked runs only)

**This shortcut applies only when a human invoked the loop directly.** Once all fast platforms (Linux, Windows) have completed with zero stable failures and only slow runners (macOS) remain queued or in progress, declare success and stop — macOS runners are resource-constrained, and platform-independent fixes gain no diagnostic value from waiting. **Announce this exit; never end on a silent idle.** Report that the fast channels are green and name what stays unverified (the `release.yaml` binary-matrix run ID, any still-queued macOS or congestion-delayed cells) so the human takes over that check instead of assuming the whole matrix passed.

**When an orchestrator spawned this loop (like `/repomatic-ship`), do not early-exit — drive every monitored workflow to terminal green before returning.** The orchestrator spawned you precisely to own the slow tail it would otherwise poll itself; returning at "fast platforms green" just hands the macOS cells and the `release.yaml` binary matrix back to a caller that must then detect your stall and re-drive them, and an idle sub-agent is indistinguishable from a dead one. Keep polling — with the step-3 `sleep` cadence, never a busy-wait — until macOS and the full `release.yaml` matrix have finished and every stable (✅) job is green, fixing and re-pushing on any stable failure (steps 4-7). Then send the orchestrator a final `SendMessage` naming each monitored workflow's conclusion. A harness idle/available signal is not that report: end the turn only with that explicit message, or on a blocker you cannot resolve (say which).

### When supersession never lets a run conclude

A busy default branch can cancel the same workflow indefinitely. Every push shares the `${{ github.workflow }}-${{ github.ref }}` concurrency group, so an unrelated commit landing mid-matrix cancels yours, and the next one cancels its replacement. Three consecutive heads leaving `tests.yaml` cancelled is an ordinary afternoon, not a fault. Dispatching a fresh run does not escape it: a `workflow_dispatch` run joins the same group and is cancelled by the next push like any other.

**A cancelled run is neither a failure nor a pass, and the run-level conclusion hides which.** Read the jobs:

```shell-session
$ gh run view {run-id} --json jobs \
    --jq '[.jobs[] | .conclusion] | group_by(.) | map({(.[0] // "running"): length}) | add'
{"cancelled":2,"success":25}
```

Twenty-five green and zero failures is a strong signal that the tree is fine; it is not a green run, and must never be reported as one.

**Establish coverage by union, then close the residue locally.** List the cells that never reached `success` on any head containing your change, across every cancelled run:

```shell-session
$ gh run view {run-id} --json jobs --jq '.jobs[] | select(.conclusion != "success") | "\(.conclusion): \(.name)"'
```

The residue is almost always macOS, which is the slowest tier and therefore last standing whenever a run is cut short. Discount any `⁉️` cell (it gates nothing) and run whatever stable cells remain on the matching interpreter locally:

```shell-session
$ uv --no-progress run --python 3.10 --all-extras --group test --frozen -- pytest -m "not once"
```

`--group test` is required: without it uv resolves an environment with no pytest in it and fails with `Failed to spawn: pytest`, which reads as a broken command rather than a missing dependency group. A cell whose OS differs from the machine you are on cannot be closed this way — name it as unverified instead of implying otherwise.

Report the union explicitly: which cells passed in CI, which you closed locally, and which remain open and why. "CI was cancelled" on its own tells the caller nothing they can act on.

## Stable vs. unstable

- **Stable jobs** (✅): must pass. So does every job carrying no stability glyph at all (`🛡️ Lint types`, `1️⃣ Run-once tests`, `📦 Package install`): the test is the *absence* of `⁉️` anywhere in the name, never the presence of a `✅` prefix.
- **Unstable jobs** (⁉️): allowed to fail (an in-development Python, currently 3.15). Their failures never gate the loop; a release context still fixes the repo-fixable ones (see [error triage discipline](#error-triage-discipline), rule 1).

The workflow uses `continue-on-error` for unstable jobs, so the run can succeed even when they fail.

`repomatic ci-status` does this classification, and doing it by hand is where it goes wrong: job-name shapes differ across workflows — `tests.yaml` names carry no workflow prefix (`✅ ubuntu-26.04 / py3.10`) while the release engine's arrive through the reusable call (`release / ✅ ubuntu-26.04, abc1234 build`) — so a test anchored at the start of the name misfiles one shape and a split on `" / "` misfiles the other, either way masking a real failure as green. Containment is the one test both shapes satisfy. Only `✅`/`⁉️` carry stability: a job whose name opens on some other emoji (`🛡️ Lint types`, `1️⃣ Run-once tests`) is required, so test for the absence of `⁉️` rather than for the presence of any glyph. If you reformat job names for display, keep the raw string for the test.

## Error triage discipline

Read the exact error messages before forming a hypothesis. The most common diagnostic mistake is latching onto a warning or unstable-job failure instead of the actual stable-job error.

1. **Filter first.** Gating and loop cadence read stable (✅) jobs only: an unstable (⁉️) failure never blocks the loop, never sets its tempo, and never queue-jumps a stable red. When an orchestrator like `/repomatic-ship` spawned this loop for a release, ⁉️ reds are still work owed under its genuinely-green goal: once no stable red is outstanding, read their logs and fix what is repo-fixable (a crash converted to a clean availability-gated skip, a flaky live install folded into a tolerated-exit set), leaving only genuine dev-interpreter breakage unfixed and named in the final report. Human-invoked runs keep the strict filter: discard ⁉️ logs entirely unless asked.
2. **Quote the error.** Before proposing a fix, quote the exact failing line(s) from the log. If you cannot quote a specific error, you have not diagnosed the problem.
3. **One cause at a time.** Multiple failing jobs often share a root cause: identify the common thread before treating each job as independent.
4. **Distinguish test failures from lint failures.** A pytest `AssertionError` and a mypy `error:` have different fixes, but always analyze mypy and ruff failures together before fixing either (see [§ mypy/ruff fix oscillation](#mypy-ruff-fix-oscillation)).
5. **Do not fix warnings.** Deprecation and informational messages are not failures; ignore them unless they cause a stable job to fail.

## Common failure patterns

<a id="mypy-ruff-fix-oscillation"></a>

### mypy/ruff fix oscillation

mypy and ruff can enter a fix loop where each tool's fix breaks the other. Common triggers:

- **Unused import**: ruff removes an import (`F401`), mypy then complains about a missing name; re-adding triggers ruff again.
- **Type annotation style**: mypy requires an explicit annotation, ruff considers it redundant or wants a different form.
- **`noqa` vs `type: ignore`**: `# noqa` silences ruff but not mypy; `# type: ignore` silences mypy but ruff flags the unused directive.

When the same lines toggle between fixes across iterations, stop and apply a combined resolution: a `# type: ignore[code]` with a matching `# noqa: XXXX` on the same line, or a restructuring that satisfies both at once.

### mypy scope mismatch (local vs CI)

The classic false green: mypy passes locally over a subset of directories while CI checks **every tracked Python file** (`tests/` and `docs/` included). Run it as a bare `repomatic run mypy` and the runner resolves that same list, so an error in a test or docs file surfaces before the push rather than after it. A directory list is what reintroduces the gap.

### Platform-specific test skips

Some tests are skipped on certain platforms (`windows-11-arm` has no Python 3.10 ARM64 build). Before investigating missing results, check the matrix `exclude` section in `tests.yaml` and the `skip_platforms` entries in the binary self-test plan (`tests/cli-test-suite.toml`): individual cases can opt out of platforms without affecting the CI matrix.

### Cross-platform divergence

When a test passes locally but fails in CI, check platform differences before changing logic:

- **Path lengths**: `~/.config/...` is shorter on Linux than macOS/Windows equivalents, affecting text-wrapping assertions.
- **Terminal width**: CI runners may default differently than local dev machines.
- **Encoding**: Windows defaults to `cp1252`, not `utf-8`.
- **Line endings**: `\r\n` vs `\n` breaks exact-match assertions.
- **Untracked files**: tests that enumerate files (`python_files`, `doc_files` metadata) see untracked local files that CI's clean checkout lacks. When updating expected file lists, include only tracked files; run `git status` to spot the divergence.

### Workflow and infrastructure failures

Not all CI failures are code bugs:

- **Runner timeouts or OOM kills**: the log ends abruptly or shows `The runner has received a shutdown signal`. Re-run; do not change code.
- **Action version mismatches**: `Unable to resolve action`, deprecated-runtime errors. Fix the workflow YAML, not the Python.
- **Network/registry flakiness**: `uv`/`pip` timeouts, PyPI 503s, `ConnectionResetError`. Re-run.
- **Permission errors**: `Resource not accessible by integration`, 403s. Check `gh api rate_limit` first ([§ GitHub API rate-limit exhaustion](#github-api-rate-limit-exhaustion)), then token permissions; never code.
- **A whole workflow red with nothing executed**, every job reporting failure and the `metadata` job unable to resolve its own toolkit pin: the inline `uvx 'repomatic==X.Y.Z'` command is missing `--exclude-newer-package repomatic=P0D`, so the workflow-wide `UV_EXCLUDE_NEWER` refuses a pin naming a release younger than the window, and each `needs: metadata` job dies with it. Splice the flag onto that command line — `uvx` reads no project configuration, so there is nowhere else the bypass can live — or merge the `sync-workflow-pins` PR that backfills it. `lint-repo`'s fatal `self-pin-cooldown-exemption` check names the offending files. Re-running changes nothing.

For infrastructure, re-run the failed jobs (`gh run rerun <RUN_ID> --failed`) and continue polling; never modify code to work around transient infra.

<a id="github-api-rate-limit-exhaustion"></a>

### GitHub API rate-limit exhaustion

Heavy polling from this loop spends the same REST quota (5,000 requests/hour) as every workflow authenticating as the same user (`REPOMATIC_PAT`). Exhaustion produces two failure shapes that look unrelated to quotas:

- Local `gh` calls fail with `HTTP 403: API rate limit exceeded`.
- Workflows fail with *permission-shaped* errors: `lint-repo` reports the PAT lacks `Contents`/`Dependabot`/`Workflows` scopes, or a `Sync pull request` step (`repomatic pr-sync`) stalls on the GitHub API until its `timeout-minutes` or the concurrency group kills the run.

Diagnose with `gh api rate_limit` **before** touching token settings: `remaining: 0` on the `core` bucket confirms it. Recovery: wait for the printed `reset` epoch, then re-run the failed workflows unchanged (`gh run rerun <RUN_ID> --failed`); they go green with no commit. While waiting, degrade to the channels that stay live: the GraphQL bucket is metered separately (`gh api graphql` for a commit's check suites, refs, and releases; `gh pr list` / `gh pr view`), and `git fetch` over SSH covers branch and commit verification.

<a id="pr-merge-permission-wall"></a>

### PR-merge permission wall

`gh pr merge` — and other write-heavy verbs (force-push, `reset --hard`, repo or release delete) — is commonly hard-denied in the operator's own Claude Code `settings.json` as a standing guard against irreversible actions, independent of any conversation. This deny is structural, not a per-call prompt: it fires identically whether or not a maintainer just authorized the exact command in chat, because it blocks the tool call itself rather than asking. Signs you have hit it, not a normal prompt: the denial is immediate with nothing to answer, and it recurs identically after a fresh, explicit, real-time go-ahead. Do not retry it, and do not read a maintainer's chat-level "yes, merge it" as actionable — a deny rule cannot be cleared from inside the session. Report the wall once and ask the maintainer to run the merge themselves, fully outside this session (their terminal, or the GitHub web UI): that is the only path this deny shape leaves open. The same holds when a hardware-key signing refusal blocks a direct commit (step 7): with both remedies walled, the release advances only by a human acting outside the tool.

### Nuitka binary build failures (release.yaml)

This section only applies to projects that build binaries (`[tool.repomatic] nuitka.enabled` with a CLI entry point); on a Nuitka-disabled project the per-platform jobs skip on every push and there is no matrix to fail. When enabled, the engine runs Nuitka across a 6-way OS/arch matrix on release commits, on the weekly `schedule` and on `workflow_dispatch`, narrowing an ordinary push to the `[tool.repomatic] nuitka.dev-targets` canary subset (job names are templated per platform, like `✅ {os}, {sha} build`); catching a break while the version is still `.dev0` avoids shipping a release with missing or broken binaries, which the immutable-release wall makes unrecoverable. Triage by category:

- **Infrastructure** (runner OOM, shutdown signal, macOS runner crash, registry timeout): re-run the failed job (`gh run rerun <RELEASE_RUN_ID> --failed`); binary builds are resource-heavy and macOS runners crash more than most.
- **Nuitka configuration** (`Error, unsupported ...`, an unknown `--flag`, a missing data file): fix `[tool.nuitka]` in `pyproject.toml`, not the Python source; verify each key maps to a current Nuitka option.
- **Real compile or runtime errors** (the binary builds but its smoke test fails, a `ModuleNotFoundError` at runtime): fix the code or the `include-package`/`include-data-files` configuration, then push and re-monitor.

The matrix is slow: let `tests.yaml` and `lint.yaml` set the loop cadence, but act on a red build cell the moment it lands, like any stable failure (every faster channel has already reported by then): fix, push, supersede. Never idle out the rest of a matrix you already know is doomed.

**On a release run, a red build cell means that version ships short, permanently.** When the run's head commit is a `[changelog] Release vX.Y.Z` push, `publish-release` sits at the end of that same run and flips the draft to published once the asset jobs settle, locking the asset list. Whatever the matrix failed to produce by then is missing from that version forever: no re-run, no later upload. `v6.30.0` shipped without `windows-arm64`, `v7.5.0` without either Windows build, and `v7.7.0` without any binary at all.

**This is by design, so do not try to stop it.** Publishing a release short beats holding it, and the recovery is the next version, not a draft the maintainer has to babysit. Keep doing exactly what you do for any stable red: fix the cause, push, and let the fix ride the next release. The one addition is reporting: name the platforms that version lost, so the maintainer knows the gap exists and can note it in the release. A short ship also leaves the changelog section, the release body and `docs/install.md` still advertising binaries that are not there (the `repomatic-ship` skill's § Repairing a short ship covers the cleanup); flag it rather than fixing it silently mid-loop.

### Autofix job failures (autofix.yaml)

`autofix.yaml`'s jobs normally commit their fixes; a job that *crashes* turns the workflow red without producing one. Fetch the failed log (`gh run view <AUTOFIX_RUN_ID> --log-failed`) and triage:

- **Tool-runner checksum mismatch** (`ValueError: SHA-256 mismatch for https://...`): the pinned binary's hash no longer matches the published artifact, usually an upstream re-publish. Regenerate with `repomatic update-checksums`, then confirm with `repomatic run <tool>`.
- **External-tool output parse error** (a `RuntimeError`/`KeyError` in a parser, like `fix-vulnerable-deps` reading `uv audit` JSON): the tool's output schema drifted. Fix the parser and update the test fixture encoding the old shape.
- **Dependency fails to build on the runner** (`Failed to build <pkg>`, a `maturin`/`cargo`/native-compiler error during install): usually self-inflicted, not upstream: a `runs-on` change *this cycle* moved the job to an architecture with no published wheel, forcing a doomed source build. Check `git log <last-tag>..HEAD` for the runner swap and revert it; a genuinely broken upstream artifact (failing on *every* platform) is the rarer case.
- **Genuine content the job fixes** (real typos, an actual vulnerability): the job commits the fix and goes green on its own; nothing to do.

### End-of-loop retrospective

After the loop converges (or hits the iteration cap), review whether any finding is worth feeding back: a failure pattern that recurred across iterations, or a diagnosis needing non-obvious knowledge, belongs in [§ Common failure patterns](#common-failure-patterns). Propose the addition; do not push it unreviewed.
