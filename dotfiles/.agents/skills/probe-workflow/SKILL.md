---
name: probe-workflow
description: Validate a claim about real-host behavior with a temporary GitHub Actions workflow. Measure the environment, iterate on hard assertion gates, then retire the workflow with its findings recorded in the retirement commit. Use when local tests and mocks cannot answer how a tool, platform, container or privilege boundary actually behaves.
compatibility: 'Designed for Claude Code. Recommended model: Opus.'
---

# Probe real-host behavior with a temporary workflow

A probe is a throwaway GitHub Actions workflow that answers one question about the real world: what a third-party CLI actually prints, how a privilege boundary actually behaves, what a container or another OS actually ships. It exists because a unit test asserts what you believe, while a probe measures what is true. The lifecycle is fixed: write, push, read, iterate, then **retire it in a commit whose body records what it proved**. A probe that lingers becomes CI cost with no question left to answer.

Reach for one when:

- Code must match a tool's real output or error wordings, and the tool does not run on the development machine (another OS, another distro, a musl container, a privileged path).
- A feature's flagship scenario has only ever run against mocks or a stand-in host.
- A CI failure depends on runner-image state that local reproduction cannot fake (preinstalled tools, filesystem ACLs, service accounts).

Do not reach for one when a local test, a container run on the development machine, or reading the tool's source answers the question faster.

## Invocation

The loop commits and pushes on every iteration. Get the user's explicit go-ahead for autonomous commit/push/run/cancel cycles before starting, or run under `--dangerously-skip-permissions` in a trusted checkout. Confirm which branch to push to: these repositories key workflow concurrency on the ref, so pushing to the default branch supersedes cleanly while a side branch queues alongside it.

## Ground rules

- **Mark it temporary in line one.** The workflow's first comment says `TEMPORARY probe workflow, to be deleted once <question> is answered`. Name the file `<subject>-probe.yaml`.
- **Trigger on `push` with a `paths:` filter covering the workflow file AND the code under test.** A probe validating `mymodule.py` must re-run when `mymodule.py` changes, or code iterations silently test nothing.
- **Cooldown rules apply.** Installs from live registries carry the repository's cooldown (`UV_EXCLUDE_NEWER`, `NPM_CONFIG_MIN_RELEASE_AGE` in the workflow `env:`); distro archives (`apt-get`, `apk`) are out of scope by design. Pin actions by SHA and tools by version, copied from an existing workflow.
- **Hard gates, not eyeballs.** Every claim becomes a `grep -q` (or `test -e`, exit-code check) against captured output: `command > out.txt 2>&1 || true` then grep. A step that only prints is a diagnostic, not a validation, and belongs in the run only while a question is open.
- **Negative gates too.** Assert the behavior does NOT fire where it must not (`if grep -q ...; then exit 1; fi`), or the probe proves half the contract.

## Measure before asserting

When an assertion fails and more than one theory explains it, do not fix the theory: add a measurement step and push again. Print the state the theories disagree about (`ls -la` the directory, run the raw command as each user, `cat` the config), read the numbers, then write the fix. Guessing costs a full runner round-trip per guess; measuring costs one round-trip total. Record each lesson as a comment beside the step that hit it, so the retirement commit can harvest them.

Two shell traps recur in measurement steps:

- GitHub's default shell is `bash -e`: a step written to *capture* a failure dies at the failing command instead. Set `shell: bash {0}` on diagnostic steps, or suffix `|| true` on every command whose non-zero exit is the datum.
- Steps run as root in container jobs. Behavior gated on privilege (escalation, ownership, per-user config) needs a created unprivileged user, with scripts handed over via `su <user> -s /bin/sh /path/script.sh` and `HOME` set explicitly inside the script.

## Runner facts that cost a round-trip each

Measured on hosted `ubuntu-26.04` runners and `alpine:edge` containers, 2026-08. Re-verify before relying on them: runner images churn.

- `/opt` carries setgid, sticky and a permissive ACL that children inherit: a `sudo mkdir` there is world-writable until `chmod 0755` plus `setfacl -b`.
- `sudo` resets `HOME`, so an escalated tool reads root's own configuration, not the invoking user's: a per-user config set before escalating silently does not apply.
- `uv sync` venvs ship no `pip`: the venv python shadowing `PATH` breaks anything probing `python -m pip`.
- JavaScript actions (`actions/checkout`, `astral-sh/setup-uv`) are glibc-linked and die in musl containers: inside Alpine, fetch the exact SHA with `git clone` + `git fetch origin "$GITHUB_SHA"` and install tooling with `apk add`.
- Container base images ship no package index: run the package manager's index refresh before any search or install can see the catalog.

## The iteration loop

1. Push. The `paths:` trigger starts the run.
2. Watch with a single-pipeline poll: `until gh api "repos/<OWNER>/<REPO>/actions/workflows/<file>/runs?head_sha=<FULL_SHA>" --jq '.workflow_runs[] | select(.status == "completed") | "DONE " + .conclusion' | grep DONE; do sleep 20; done`. Multi-step shell in background watchers (variables, `set --`, `paste`) fails silently; one pipeline per tick is the shape that survives. Read runs through the API, never `gh run list`: both its forms have put runs weeks old at the top of the list. Give `head_sha` the **full** 40-character SHA, since an abbreviated one matches nothing and returns an empty list that looks identical to "nothing ran", and quote the whole path, since zsh expands the `?` as a glob.
3. Read `gh run view <id> --log-failed` first, the full `--log` when the failed step's cause sits in an earlier step's output.
4. Diagnose from measurement, fix exactly one thing, commit with a subject naming the lesson, push again.
5. A failing gate can indict the probe's staging *or* the code under test. When raw commands succeed where the code fails, the probe has found a real bug: fix it in the codebase with its own tests and changelog entry, and let the probe re-validate.

## Retirement

Delete the workflow the moment every gate is green:

- The retirement commit's body states what the probe proved, in one sentence per claim. This is the durable record: the workflow file is gone, and `git log` on it is where the findings live.
- Route each finding to its lasting home before the delete: a real-output fixture into the test corpus, an environment quirk into a comment beside the code that works around it, a user-facing fix into the changelog. The probe itself must hold nothing that still matters.
- If a scenario deserves *permanent* coverage, that is a new decision with a cost: propose a schedule-only job to the user rather than quietly keeping the probe alive.
