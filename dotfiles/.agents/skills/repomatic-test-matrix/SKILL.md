---
name: repomatic-test-matrix
description: Choose what a repository's CI test matrix covers. Decides which Python versions, operating systems and runner images earn a cell, which axes stay unstable probes, and which runner a one-off job should sit on. Use when adding or dropping a Python version or OS, pinning a dependency floor, or picking where a new job runs.
compatibility: 'Designed for Claude Code. Recommended model: Sonnet.'
allowed-tools: Bash Read Grep Glob Edit
argument-hint: '[review|add <axis>|drop <axis>]'
---

## Context

!`grep -A20 '^\[tool.repomatic.test-matrix' pyproject.toml 2>/dev/null || echo "NO_TEST_MATRIX_CONFIG"`
!`grep -E '^\s*requires-python' pyproject.toml 2>/dev/null || echo "NO_REQUIRES_PYTHON"`

## Instructions

`repomatic metadata` builds the full and PR test matrices from `[tool.repomatic.test-matrix.*]`. Read the effective matrices before proposing anything:

```shell-session
$ repomatic metadata --format json test_matrix test_matrix_pr
```

A matrix cell costs a runner on every push, so each one has to earn its place. These are the selection conventions.

### Cover the shipped config broadly; probe unreleased axes narrowly; smoke-test released flavors

Released dependencies on stable Python get a broad spread, but *broad* means broad on the axis the product actually varies along, not on both at once. A tool whose behaviour changes per platform (it drives different system binaries, resolves different paths, ships a different feature set) earns a cell for every OS and architecture, because that spread **is** the product. Interpreter compatibility is OS-independent by construction, so the floor, the prerelease and the free-threaded build each need one runner rather than one per OS. Crossing the two axes multiplies cells to buy their *interaction*, which is worth paying for only where the failure history shows an interaction exists: measure it (see below) instead of assuming it, and put the floor on whichever OS its users actually run, which for a Python tool is usually Linux, where distribution packagers build against whatever interpreter their channel ships.

Unreleased dependency branches and prerelease Python run on one runner as `continue-on-error` probes (`test-matrix.unstable`), never across platforms: a probe that fails is information, and paying for it six times over buys none.

A *released* free-threaded build (`3.14t`) is a different case and runs **stable** on a single runner, as a `python-version` variation pinned with `exclude` and left out of `unstable`. It is shipped software, so a failure there is a real failure.

### Ask what a cell has caught, not what it might

A cell justifies itself by having failed while its siblings passed. Anything less is a hypothesis, and the repository already holds the evidence to test it: walk recent runs of the workflow and, for every failing cell, check whether the *same OS* passed at its other Python version in that same run. A cell that never fails alone has never repaid its cost.

```shell-session
$ gh run list --workflow tests.yaml --branch main --limit 40 --json databaseId
$ gh run view {run-id} --json jobs \
    --jq '.jobs[] | select(.name | test("py")) | "\(.name): \(.conclusion)"'
```

Count cancelled runs too. A busy default branch cancels most of its runs through `cancel-in-progress`, and the cells that had already reported a verdict inside them are where most of the failure history lives; filtering to conclusive runs alone can shrink a real sample to nothing.

Two readings make the decision. A failure hitting **every** cell of an OS is an OS-level or universal bug, which one cell per OS would have caught. A failure hitting **one** cell while its twin passed is the only kind a per-OS version pair can catch, and if that count is zero across a real sample, the pairs are redundant. Expect the second reading to also surface environment artifacts rather than code bugs (one runner of a label carrying a different tool layout than another), and do not count those as a cell earning its keep.

State the sample size and both counts when proposing the change, and record in the config comment what would justify restoring what you cut, so the next reader inherits the measurement rather than the conclusion alone.

### Pin the dependency floor, and any release a workaround targets

Add the floor of a supported range as an explicit matrix value: the floor is what an install actually resolves for someone on an old environment, and nothing else in CI exercises it.

Add any mid-range release a shim works around, too. That version is the one that catches the shim regressing, and it is invisible to a matrix that only spans the endpoints.

### Select runners by measured speed and workload, not architecture

Measure, do not reason from the chip:

```shell-session
$ repomatic job-timings --workflow tests.yaml --limit 5
```

That reports median whole-job wall-clock per runner image from recent successful runs. Read it before proposing any runner change: the parallel `pytest --numprocesses=auto` suite favours `ubuntu-26.04-arm`, which is why that is the test PR Linux slot, but the ratio is workload-dependent and yours may differ.

Where one fast runner suffices, `ubuntu-26.04-arm` is the default: fastest and cheapest tier, against hosted macOS billing roughly ten times Linux. Reserve `macos-26` and Windows for the OS coverage only they add, and drop the slower twin of an OS pair with `test-matrix.remove.os`.

### Time whole jobs, not the tool pass

A measurement that times only tool execution misses checkout and install, which is where most of the difference between runner images lives. The lean `ubuntu-slim` image survived for a long time on exactly that mistake: measured end to end, the full image ran 27-32% *faster*.

`job-timings` reads the jobs API's start and end timestamps, so what it reports is whole-job by construction and this mistake is not expressible through it.

### Watch what is arriving and retiring

You are not the first to know an image is changing. `repomatic sync-runner-images` runs weekly from the `autofix.yaml` workflow, looks up every label this repository runs in GitHub's *Available Images* table, and proposes the mechanical half as a pull request: rewriting a deprecated image's literal `runs-on:` onto its successor, or adding a strictly newer *version* of an image already in use to the full matrix as a `continue-on-error` probe. It opens one only when something here is exposed, so its existence is the signal.

Deciding whether to merge is this skill's job, and the CI run that pull request triggers is the evidence for it. Closing the pull request alone brings the proposal back on the next run; declining one for good means naming the label in `[tool.repomatic.sync-runner-images] ignore`.

That table is the only source read, and it badges an image `deprecated` when deprecation *begins* rather than when it is announced, so a retirement surfaces here months after an announcement feed would have shown it. The runway is still ample, since the badge lands well before the image stops working. What the table cannot show at all is a change to the *contents* of an image already in use, like a default toolchain moving: the suite is what catches those.

### An image is stable once validated here, not once GitHub relabels it

The Ubuntu 26.04 axes shipped as stable cells while still marked *preview* upstream. That label chiefly gates `-latest` alias eligibility, and no workflow here uses a floating alias, so it says nothing about whether the image runs the suite green.

Never introduce a `-latest` alias to sidestep the question: GitHub repoints those with no commit to review, and `lint-repo` rejects them.

### Every job runs on a test axis

The images a job may run on are exactly those the test matrices use, and `lint-repo` rejects any other `runs-on:`. Read the effective set from `repomatic metadata` rather than from the package source, which a repository consuming repomatic does not have checked out. That keeps "where is the suite exercised" and "what may a job run on" a single question, because each extra image is one more to track, pin and migrate.

A job that genuinely needs something else widens the axes rather than naming a one-off image. This covers the Linux Nuitka hosts (a published binary is built on the image the suite is validated against, and its toolchain comes from a digest-pinned manylinux container regardless) and the light mechanical jobs.

### Reporting

Propose changes as a `[tool.repomatic.test-matrix.*]` diff, and for each added or removed cell say what it buys or costs: a version nothing else exercises, an OS-specific failure mode, a runner-minute saving. A cell nobody can justify in one sentence is a cell to drop.

Verify with `repomatic metadata` after editing, since the config is an input to a computed matrix rather than the matrix itself.
