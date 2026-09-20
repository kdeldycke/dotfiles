---
name: repomatic-upgrade
description: Review what a newer repomatic release lets a downstream repository adopt, reuse or drop, then apply it. Use right after `repomatic init` moved the upstream pin, or after an upgrade commit landed.
compatibility: 'Designed for Claude Code. Recommended model: Opus.'
allowed-tools: Bash Read Grep Glob Edit Write WebFetch Agent
argument-hint: '[vOLD vNEW]'
---

## Context

!`grep -rhoE 'kdeldycke/repomatic/[^@]+@.*v[0-9]+\.[0-9]+\.[0-9]+' .github 2>/dev/null | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+$' | sort -uV | tail -1 | sed 's/^/ADOPTED_PIN /'`
!`git diff HEAD -- .github 2>/dev/null | grep -E '^-.*kdeldycke/repomatic/.*v[0-9]+\.[0-9]+\.[0-9]+' | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+$' | sort -uV | head -1 | sed 's/^/PREVIOUS_PIN_UNCOMMITTED /'`
!`git log -1 --format='LAST_WORKFLOW_COMMIT %h %ad %s' --date=short -- .github/workflows 2>/dev/null`
!`[ -d ../repomatic/.git ] && echo "SIBLING_CHECKOUT ../repomatic" || echo "NO_SIBLING_CHECKOUT"`
!`[ -f repomatic/__init__.py ] && echo "CANONICAL_REPO" || echo "DOWNSTREAM"`

## Instructions

You review what a newer `repomatic` release brings to a downstream repository once its upstream pin moved, and you apply what is worth taking. `/repomatic-audit` compares the repository against the release it already pins and files anything newer as an upgrade note: this skill is that note, worked through. `/repomatic-deps modernize` does the same job for Python dependencies.

`repomatic init` prints the command launching this skill as its last next step when it moves the upstream pin. The `sync-repomatic` upgrade pull request invites the maintainer to run it, and so does the `sync-workflow-pins` one when a bump moves `repomatic`.

**This skill is for downstream repos only.** If the context shows `CANONICAL_REPO`, tell the user this skill is not applicable.

### Determine invocation method

Use `uvx --exclude-newer '1 week' --exclude-newer-package repomatic=P0D --from 'repomatic==X.Y.Z' -- repomatic`, with `X.Y.Z` the `ADOPTED_PIN` the context shows. The pin keeps the tool registry (`ruff`, `typos`, `mypy` versions) identical to what CI runs, and the cooldown gates the dependency tree while keeping a fresh release installable. References to `<cmd>` below resolve to it.

### Find the version pair

The context block prints, in order: the pin now on disk, the previous pin when `repomatic init` ran but nothing is committed yet, and the last commit touching the workflows. Take the pair from the first source that carries it:

1. `$ARGUMENTS`, as `vOLD vNEW`.
2. The uncommitted diff: the removed `uses:` lines carry the previous pin, the added ones the adopted pin.
3. The last upgrade commit: `git log -p -1 -- .github/workflows`, reading the previous pin off its removed `uses:` lines.
4. Ask the user when none of these carries a previous pin. A first adoption has no delta to review.

### Read the delta

- **Fetch the changelog at the adopted tag, never at `main`.** `gh api "repos/kdeldycke/repomatic/contents/changelog.md?ref=vNEW" -H "Accept: application/vnd.github.raw"`. Read every section from `vNEW` down to, and excluding, `vOLD`. A section the changelog no longer holds sits in `docs/changelog-archive.md` at the same ref. `main` carries unreleased work under a `.devN` heading, and none of it is available to this repository yet.
- **Sort every bullet into one of five bins.** Breaking: a renamed job, workflow input, config key or command the repository uses, which must be acted on. Adopt: a new config key, job, skill, CLI option or template this repository would use. Drop: a fix that makes a local workaround, pin or custom step obsolete. Simplify: a hand-maintained piece that `repomatic init` or a workflow now produces. Skip: docs, internals, test work, and jobs marked upstream-only.
- **Read the GitHub release notes only when a changelog bullet is unclear.** `gh api repos/kdeldycke/repomatic/releases --jq '.[] | select(.tag_name == "vNEW") | .body'` repeats the changelog section, so it adds nothing on its own.

### Map the delta to this repository

For each bullet outside the skip bin, find what it touches here. Grep the source tree, `.github/`, `pyproject.toml` and `docs/`:

- **A new `[tool.repomatic]` key or workflow input.** Look in `pyproject.toml` and the header-only workflows for a hand-rolled equivalent the key now replaces, like a custom `paths:` list or a local step.
- **A new job, skill or subagent.** Check `[tool.repomatic] exclude` before proposing it: an excluded component is a decision, not a gap.
- **A dropped or renamed surface.** Grep `tests.yaml`, any other header-only workflow, and local scripts for the old name.
- **An upstream fix.** Search comments and workflow steps for the workaround it retires: `work around`, `XXX`, `TODO`, version-guarded branches, and inline pins of the tool it fixed.
- **A generator change**, like a thin caller gaining a trigger or a header gaining `paths:`. Read `git diff HEAD -- .github/workflows` against the changelog, so a diff the release explains is never reported as drift. When the upgrade is already committed, that diff is empty: clone `HEAD` into a scratch directory, point its `origin` at the GitHub URL, run `<cmd> init --no-cooldown` there and read `git status`. A clean tree proves the commit regenerated every managed file instead of moving the pins by hand.
- **A changed job.** Before you report it as adopted, call the released code on this repository's real inputs. An open pull request from that job shows only what its last run did, and that run can predate the adopted pin. A job that reads a file from another project also stops working when that file moves.
- **A synced skill or subagent.** `repomatic init` rewrites every bundled copy verbatim, so the upgrade also reverts each local commit made to one since the last sync. Take every copy under `skills.location` and `subagents.location` as it stood before the upgrade. That is `HEAD` while the upgrade is uncommitted, and the upgrade commit's parent once it landed. Compare it with upstream's `.claude/skills/{name}/SKILL.md` or `.claude/agents/{name}.md` at `vOLD`. Read those paths, not `repomatic/data/skills/`: its entries are symlinks, and `git show` returns their target path. A copy that matches neither `vOLD` nor any upstream commit between the two tags carries local edits. The upgrade drops them, so report them as a `breaking` row.
- **A new `lint-repo` check.** Run `<cmd> lint-repo --repo {owner}/{repo}` and read its line: a check that passes here offers nothing. Without `--repo`, a local run has no `$GITHUB_REPOSITORY`, so every API-backed check drops out of the output.

Keep the two axes apart, as `/repomatic-audit` does: what the release offers is this skill, what the repository drifted from is that one. A local deviation the release does not touch belongs to the audit, not here.

### Report

Produce one table: changelog entry, bin (`breaking`, `adopt`, `drop`, `simplify`), where it lands in this repository, and the action. Order the rows breaking first, then by rising effort. Close with the entries that offer nothing for this repository, in one line, so the user knows they were read.

### Apply

1. **Apply one row at a time, breaking rows first.** Keep each change readable on its own in `git diff`.
2. **Keep the local edits a synced copy carries.** Restore the file as it stood before the upgrade when upstream left it unchanged between the two tags. Otherwise re-apply the local commits onto the new copy: `git apply -C1` gets past a context line upstream reworded. Then port the edits upstream, as step 4 describes, or the next sync reverts them again.
3. **Run the local checks after each row.** The project's tests, `mypy` and `ruff`, plus `<cmd> lint-repo --repo {owner}/{repo}` when the row touched `.github/` or `pyproject.toml`. A failing check vetoes the row: revert it and note it in the report. Never loosen a test to pass.
4. **Send generator problems upstream, as edits in the sibling checkout.** When a row needs a change in `repomatic` itself (a generator writing something unwanted, a missing knob, a docs gap, a lesson a synced copy carries) and the context shows `SIBLING_CHECKOUT`, implement it in `../repomatic`: the code, the tests it breaks, and a changelog bullet. Verify it there. `repomatic run typos` and `mdformat` rewrite files in place and print no findings, so judge them by `git diff`. Another session may share that checkout: edit only the files the row needs, and name them in the report so they can be committed by pathspec. Leave every change uncommitted. Without a sibling checkout, describe the change in the report instead.
5. **Never commit, push, or open an issue or pull request.** The user reviews the working tree and decides, so the skill needs no report-only mode.
6. **Report.** What was applied, per row. What sits uncommitted in `../repomatic`. What was skipped, and why.

### What not to touch

- **An adoption that needs a token, a service or a new external setup.** List it with a recommendation and leave it to the user. Apply the `adopt` rows that need only configuration.
- **A deviation `[tool.repomatic] exclude` or `include` records.** Those are decisions.
- **A major-version migration that needs broad rework.** Report it and stop.

### Next steps

Suggest the user run:

- `/repomatic-audit` in a fresh session, to check the repository against the release it now pins.
- `/repomatic-deps modernize` when the upgrade also moved `uv.lock`.
- `/repomatic-changelog add` for the downstream changelog bullet, when the repository keeps one.
