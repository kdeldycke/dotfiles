---
name: pr-triage
description: Audit open PRs across multiple repos for duplicates, stale drafts, Renovate noise, and conflicts. Produces a unified priority report.
allowed-tools: Bash, Read, Grep, Glob, Agent
argument-hint: "[owner/repo1 owner/repo2 ...] or blank for current repo"
---

# PR triage across repositories

Audit open PRs across one or more GitHub repositories and produce a single prioritized report.

## Argument handling

`$ARGUMENTS` is a space-separated list of `owner/repo` identifiers. If empty, use the current repo (from `gh repo view --json nameWithOwner --jq .nameWithOwner`).

## Workflow

### Phase 1: Gather PR data

For each repo, spawn a parallel Agent that runs:

```bash
gh pr list -R {repo} --state open --json number,title,author,createdAt,isDraft,labels,headRefName,baseRefName,mergeable,reviewDecision,updatedAt
```

### Phase 2: Per-PR analysis

For each open PR, the agent evaluates:

#### Stale drafts

Flag drafts where `updatedAt` is more than 7 days ago. Include age in days.

#### Duplicate detection

Compare PR titles and branch names within the same repo. Flag pairs where:
- Titles share 3+ significant words (ignoring "fix", "update", "bump", "chore").
- Branch names share the same `verb-noun` prefix (e.g., two `fix-typos-*` branches).

#### Renovate PR analysis

For PRs authored by `renovate[bot]` or `app/renovate`:

1. Fetch the diff: `gh pr diff -R {repo} {number}`.
2. Classify:
   - **Version bump**: changelog entries show actual version changes. Mark as merge-ready.
   - **SHA-only**: diff changes only pinned commit SHAs with no version change (e.g., annotated tag re-point). Flag as cosmetic.
   - **Major update**: major version bump. Flag for manual review.
3. Check for Renovate PRs that update the same package — these are superseded duplicates.

#### Conflict detection

Compare `headRefName` across open PRs. Flag PRs that modify the same files (fetch file lists with `gh pr view -R {repo} {number} --json files --jq '.files[].path'`). Two PRs touching the same file are potential conflicts.

### Phase 3: Unified report

Merge results from all agents into one table, sorted by priority:

```
| Repo | PR | Title | Author | Age | Status | Action |
```

Status values:
- `merge` — Tests pass, approved, no conflicts. Merge-ready.
- `review` — Needs review (non-draft, no review decision yet).
- `stale` — Draft or non-draft with no activity for 7+ days.
- `cosmetic` — Renovate SHA-only update, low priority.
- `conflict` — Touches files that overlap with another open PR.
- `duplicate` — Likely duplicate of another open PR.
- `major` — Major dependency bump, needs manual assessment.

After the table, list:
1. **Merge-ready PRs** that can be merged immediately.
2. **Duplicates** with a recommendation on which to keep (prefer the older or more complete one).
3. **Stale drafts** with a recommendation to close or revive.
4. **Conflicts** with the specific files that overlap.

## Important rules

- Use `gh` CLI for all GitHub API interactions.
- Spawn one Agent per repo to parallelize data gathering.
- Do not merge, close, or comment on PRs. Report only.
- Keep the output scannable. Tables over prose.
- If a repo has more than 50 open PRs, focus on the 50 most recently updated.
