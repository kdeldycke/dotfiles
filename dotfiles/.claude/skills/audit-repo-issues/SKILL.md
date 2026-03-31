---
name: audit-repo-issues
description: Analyze a GitHub repository's issues and PRs to find unaddressed feature requests, dismissed ideas, maintenance signals, and opportunities relevant to the current project. Use when you want to scout a related or competing repo for gaps your project could fill.
argument-hint: "<owner/repo>"
---

# Audit repository issues and PRs

Analyze a GitHub repository's open and closed issues and PRs to identify opportunities for the **current project** (the one in the working directory). The target repo is provided as `$ARGUMENTS` (e.g., `python-distro/distro`).

## Goal

Produce a structured report covering:

1. **Popular unaddressed feature requests** — open issues with high engagement (reactions, comments) that have stalled or been explicitly deferred.
2. **Dismissed feature requests** — closed issues where maintainers rejected a popular idea, especially if it aligns with the current project's scope.
3. **Abandoned or rejected PRs** — unmerged PRs that proposed valuable features, scope expansions, or new platform/detection support.
4. **Merged PRs worth noting** — features that were added and could inform what the current project should also support.
5. **Maintenance and trust signals** — evidence of maintenance gaps (stale PRs, slow releases, unanswered issues) that position the current project as a healthier alternative.
6. **Detection techniques or data sources** — novel approaches proposed in issues/PRs that the current project could adopt.

## Workflow

### Phase 1: Understand the current project

1. Read the current project's `CLAUDE.md`, `readme.md`, or `pyproject.toml` to understand its scope, architecture, and what it already supports.
2. This context determines what counts as "relevant" when scanning the target repo.

### Phase 2: Gather data from the target repo

Use `gh` CLI exclusively. Run these searches in parallel where possible:

```bash
# Open issues sorted by reactions (most popular first).
gh issue list -R $ARGUMENTS --state open --limit 100 --json number,title,labels,reactionGroups,comments,createdAt

# Closed issues (look for rejected feature requests).
gh issue list -R $ARGUMENTS --state closed --limit 200 --json number,title,labels,reactionGroups,comments,createdAt,closedAt

# Open PRs (potentially stalled).
gh pr list -R $ARGUMENTS --state open --limit 50 --json number,title,createdAt,comments

# Closed PRs (look for unmerged/rejected).
gh pr list -R $ARGUMENTS --state closed --limit 100 --json number,title,mergedAt,closedAt,comments,createdAt
```

### Phase 3: Triage and deep-dive

1. **Rank issues by engagement**: sort by total reactions + comment count.
2. **Identify feature requests**: filter out pure bug reports — focus on enhancement requests, scope expansions, and architectural proposals.
3. **Deep-dive into top candidates**: for the ~20 most promising issues/PRs, fetch full details:
   ```bash
   gh issue view -R $ARGUMENTS <number> --json title,body,comments,reactionGroups,labels,state,closedAt
   gh pr view -R $ARGUMENTS <number> --json title,body,comments,state,mergedAt,closedAt
   ```
4. **Check for current-project mentions**: search for the current project's name in the target repo's issues to see if users have already referenced it as an alternative.

### Phase 4: Produce the report

Structure the output as follows:

#### High-value opportunities

For each opportunity (sorted by relevance to the current project):
- **Issue/PR reference**: number, title, link
- **Engagement**: reaction count, comment count, age
- **Status**: open/closed/rejected, and why
- **Relevance**: how it maps to the current project's scope
- **Action**: what the current project could do (already supports it, should add it, worth considering)

#### Platforms / features added to the target repo

List features that were merged into the target repo and that the current project might want to support too.

#### Detection techniques worth borrowing

Novel approaches or data sources proposed in issues/PRs.

#### Maintenance signals

Evidence table of maintenance health (stale PRs, release cadence, unanswered issues).

#### Bottom line

A concise summary of the biggest wins and positioning advantages.

## Important rules

- Use `gh` CLI for all GitHub API interactions — never scrape HTML.
- Use the Agent tool to parallelize research across open issues, closed issues, and PRs.
- When fetching issue/PR details, batch requests to avoid rate limiting.
- Focus on **relevance to the current project** — skip issues about internal bugs, CI config, or typo fixes.
- Include direct links to issues/PRs so the user can follow up.
- If the target repo has thousands of issues, focus on the top 100 by engagement rather than trying to read everything.
- Present findings with clear, scannable formatting (tables, headers, bullet points).
- Do not editorialize beyond factual observations — let the data speak.
