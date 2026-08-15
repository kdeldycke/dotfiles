---
name: github-housekeeping
description: Backfill and curate labels and milestones across a repository's full issue and PR history, with taxonomy design, bulk classification, AI-slop detection, and release archaeology.
compatibility: 'Designed for Claude Code. Recommended model: Sonnet.'
allowed-tools: Bash Read Write Edit Grep Glob WebFetch Agent
argument-hint: '[audit|labels|milestones|slop]'
---

## Context

!`gh label list --limit 50 2>/dev/null || echo "NO_GH_ACCESS"`
!`gh api "repos/{owner}/{repo}/milestones?state=all&per_page=100" --jq 'length' 2>/dev/null`

## Instructions

You bring a repository's issue-tracker metadata up to date: a small label taxonomy applied to every issue and PR (open and closed), and one milestone per published release with every shipped PR assigned to the release it landed in. The method scales to thousands of historical items because classification runs against a local cache, mutations are paced and resumable, and every decision carries provenance a human can review.

### Argument handling

- `audit` (default when `$ARGUMENTS` is empty): measure coverage gaps (unlabeled items, milestone-less items, missing milestones), report counts, and propose a plan. No mutations.
- `labels`: design or load the taxonomy, classify the backlog, review, then apply.
- `milestones`: create/repair milestones from release history, then assign every shipped PR and resolved issue.
- `slop`: sweep for AI-generated junk using the closed-without-comment signal, review, then label.

### Ground rules for mass mutations

- **Plan first, mutate second.** Build the full plan offline, dump it to a reviewable markdown file, and get explicit approval before touching the repository. Reputational labels always go through a human.
- **Pace writes.** One `gh` edit every 2 seconds, sequential, never parallel. Split long runs into time-budgeted chunks (stay under shell timeouts) that mark each item done in the local cache as they go, so an interrupted run resumes exactly where it stopped.
- **Verify live after applying.** Re-query with the search API (`no:milestone`, `-label:"x"` filters) rather than trusting the local cache. Items created mid-run will not be in your plan: sweep for stragglers at the end.
- **Sync the cache after every manual intervention.** When the maintainer applies or corrects something by hand, fold it back into the cache and plan before continuing.

### Label taxonomy design

**Always propose repomatic's bundled defaults as the starting point**, whatever the repository already carries. Render them before discussing anything else:

```shell-session
$ repomatic init labels --output-dir {scratch_dir}
```

The `labels.toml` it writes holds the whole shipped set: a `default` profile every repository gets, plus an `awesome` profile applied only to `awesome-*` repos. Nothing committed to the repository is authoritative: that file is ephemeral, regenerated into a scratch directory right before `sync-labels` reads it, and a repo's own `labels.extra` / `labels.extra-files` entries are folded in only at sync time, so read `pyproject.toml` too for the effective taxonomy.

Present the design as a diff between that effective set and the live `gh label list` above:

- **Live label matching a default**: map it. The defaults carry `rename-from` lists migrating GitHub's stock names (`bug`, `documentation`, `invalid`, `wontfix`, …) to their emoji equivalents in place, preserving issue and PR associations. Never delete-and-recreate to rename.
- **Live label with no default**: propose it as a `[[tool.repomatic.labels.extra]]` entry in `pyproject.toml` (with `rename-from` when it is a spelling variant of a default), or propose retiring it. A label kept outside the config is not what `sync-labels` applies, so it drifts back on the next run.
- **Default with no live label**: it lands on the next sync, so classify the backlog against it now instead of waiting.

Depart from the defaults only for a domain axis they cannot express, and land the departure in the config (`labels.extra`, or `labels.extra-files` for a multi-profile set) so it survives. Designing a taxonomy from scratch is the last resort, for maintainers who explicitly want off the shared set.

The sections below name labels by their default (`🪫 AI slop`, `🚫 wont do/fix`, `🐛 bug`, …): substitute the repository's own names wherever it has departed.

### Local cache

Fetch the complete inventory once into SQLite (a `{repo}-github.sqlite` file at the repo root, gitignored) instead of hammering the API per item:

- Page through issues and PRs with GraphQL (100 per page): number, type, title, body, state, `stateReason`, timestamps, `mergedAt`, author, labels, url.
- A `label_plan` working table holds one row per (item, proposed label) with `confidence` (high/medium/low), `method` (how it was decided), and a one-line `rationale`. Every item must end with at least one row: full coverage is a hard invariant.
- Enrich lazily with extra tables as heuristics demand: who closed each item (`ClosedEvent.actor`), what closed it (`ClosedEvent.closer` PR), merge commit SHAs.

### Bulk label classification

Hybrid pipeline, cheapest signal first:

1. **Already labeled** items need nothing: record them as settled.
2. **Keyword heuristics** derived from each label's own description. Score title hits heavily (a title match with no rival label is high confidence) and cap body-match contributions so long bodies cannot fake a signal. This confidently resolves roughly half of a typical backlog for free.
3. **Agent batches** for the residual: parallel subagents, ~70 items each, given the taxonomy with calibration examples, item titles plus bodies truncated to ~500 chars, and the heuristic's best guess as a hint. Demand strict machine-parseable output (`number|label|confidence|rationale`, one line per item, every item exactly once) and validate on merge: unknown labels, missing items, and unparseable lines get retried or fall through.
4. **Fallback**: anything dropped by an agent gets classified by hand so coverage stays total.

Review gates before applying: all low-confidence calls, plus every proposed `🪫 AI slop`/`🚫 wont do/fix`, go in a "needs review first" section of the plan, open items sorted first. Offer to open candidate batches in the browser (`xargs open < urls.txt`) so the maintainer can eyeball them quickly.

### AI-slop detection

**Any two signals warrant `🪫 AI slop`**, the same bar `/awesome-triage` applies; one alone never does, because the label is reputational.

The first signal is behavioral rather than textual: **a maintainer closing an item with zero comments** is a drive-by rejection. It counts only past a date cutoff, calibrated against the earliest item this repository has already confirmed as AI junk. Absent one, start from late 2025 and move it earlier only on evidence.

The second comes from the content tells: the item "fixes" an API that does not exist in the codebase, near-identical PRs from different throwaway accounts claiming the same fabricated bug, raw coding-agent output pasted as the title, unfilled PR templates on non-trivial changes, generic "comprehensive analysis" boilerplate.

- Zero-comment close past the cutoff **and** at least one content tell: propose `🪫 AI slop`.
- Zero-comment close on its own, or anything created before the cutoff: propose `🚫 wont do/fix`. The close is documented; an AI attribution is not.
- Exemptions beat any signal count: items authored or closed as part of routine process (release checklists match the zero-comment close!), and anything from trusted co-maintainers.

When `/awesome-triage` is present (it ships to `awesome-*` repositories only), its catalog widens where a second signal may come from: surface tells in its §3, and contributor and repository provenance in its §9 (account age, profile completeness, commit cadence, AI bot co-authors, solo-contributor humanness), each with a `gh api` one-liner. Where that skill is absent, the tells above are the whole pool.

Hygiene for confirmed junk: `🪫 AI slop` and `🚫 wont do/fix` items carry **only** that label (strip component labels) and **no milestone** (nothing shipped).

### Milestones

One closed milestone per published release, named exactly like the GitHub release it collects: the tag, `v` prefix included (`v8.4.2`). Descriptions keep the bare version, which names the release rather than the tag.

- **Due date = actual release date**, sourced from the package index: `https://pypi.org/pypi/{pkg}/json`, min `upload_time_iso_8601` across that version's files. Where the repository publishes no package, or a version predates its index history, fall back to the GitHub release's own `publishedAt` (`gh release view v8.4.2 --json publishedAt`): publication stamps it once, and immutable releases keep a published release from being re-cut, so it stays a faithful record. GitHub floors `due_on` to the date. Backfill milestones for ancient releases the tracker predates.
- **Pre-releases fold into the final milestone**: no `v8.0.0a1`/`v8.0.0rc1` milestones; the `v8.0.0` description notes "Covers the whole `8.0.0` release cycle including the `8.0.0a1` and `8.0.0rc1` pre-releases."
- **Yanked releases keep their milestone**, with the description recording PyPI's own yank reason: "🛑 Yanked from PyPI: \{reason}." Same wording and same reason as the changelog's `[!CAUTION]` admonition for that release; the emoji stands in for the alert, which does not render in a milestone description.
- **Planned-but-never-released** milestones (a `v8.5` that never shipped) get deleted, not closed.
- Only unreleased milestones (`v9.0.0`, the next dev version) stay open and dateless.

### Release archaeology: which milestone does a PR belong to?

Waterfall for every merged PR, most authoritative source first:

1. **Changelog references**: parse `{pr}`N\`\` (or `#N`) mentions under each `## Version X` heading. The changelog is maintainer-curated truth.
2. **Git tag containment**: `git describe --tags --contains --exclude '*.x' {merge_commit}` on a full clone, stripping the `~N`/`^N` suffix. Fold prerelease tags into their final release.
3. **Date fallback** (no merge commit recorded, or tags too coarse for old history): first release published at or after `mergedAt`.
4. Merged after the latest release: the open dev milestone.

Systematic corrections the raw waterfall gets wrong:

- **`Release vX.Y.Z` PRs merge after their own tag ships**, so containment lands them one release late. Trust the version in the title.
- **Branch-sync PRs near release boundaries**: when a live milestone is already set, it usually encodes maintainer intent better than containment. Trust live.
- **Changelog-vs-live conflicts get individual review**: wording like "completing the partial fix from {pr}`N`" proves N shipped *earlier* than the section citing it.
- Closed-unmerged PRs get **no milestone**: nothing shipped.

Then propagate to issues:

- A closed issue whose `ClosedEvent.closer` is a merged PR inherits that PR's milestone (and, when it has none of its own, that PR's labels).
- Issues closed as `DUPLICATE` inherit the milestone of their canonical issue, so stumbling on the duplicate still tells you which release addressed it. GitHub's `MarkedAsDuplicateEvent` is rarely populated: fall back to reading the closing comments for "duplicate of #N".
- Issues closed by hand with no linkable PR are left alone: inventing a milestone would be guesswork.

### GitHub API techniques

- **Batch reads with GraphQL aliases**: 40-50 items per query via `i123: issue(number: 123) {...}`. `timelineItems(itemTypes: [CLOSED_EVENT], last: 1)` yields both `actor` (who closed) and `closer` (the PR/commit that closed it).
- **REST pagination**: put `?state=all&per_page=100` in the path; `--paginate` concatenates JSON arrays that break naive `json.load`.
- **`gh pr edit --milestone <name>` cannot resolve closed milestones.** Assign by number instead: `gh api -X PATCH repos/{owner}/{repo}/issues/{n} -F milestone={milestone_number}` (works for PRs too: they are issues in the REST API).
- Labels are fine by name: `gh issue|pr edit N --add-label "x" --remove-label "y"`, several flags per call to make one atomic edit per item.
- **Search API for verification**: `gh api -X GET search/issues -f q="repo:{owner}/{repo} is:pr no:milestone"` and `-label:"x"` negations give instant gap counts.

### Wrap-up

Report what changed with counts per label/milestone, what was left alone and why (closed-unmerged PRs, unlinkable issues), and flag the review file for anything applied at low confidence. Regenerate the plan markdown so it reflects the applied state, and keep the SQLite cache: the next housekeeping run starts from it.
