---
name: audit-repo-issues
description: Analyze a GitHub repository's issues and PRs to find unaddressed feature requests, dismissed ideas, maintenance signals, and opportunities relevant to the current project. Use when you want to scout a related or competing repo for gaps your project could fill.
argument-hint: '{owner/repo}'
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
7. **Commercial posture** — whether the target is fully open-source, open-core-light, open-core-heavy, or fully proprietary, and which essential features (if any) live behind a paid tier.
8. **Retirement and acquisition signals** — explicit notices that the project has been formally retired, superseded, or acquired with the roadmap shifted to a successor commercial product.

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
   gh issue view -R $ARGUMENTS {number} --json title,body,comments,reactionGroups,labels,state,closedAt
   gh pr view -R $ARGUMENTS {number} --json title,body,comments,state,mergedAt,closedAt
   ```
4. **Check for current-project mentions**: search for the current project's name in the target repo's issues to see if users have already referenced it as an alternative.

### Phase 3b: Commercial posture and retirement check

For repos that ship a product (tools, datasets, projects — not articles or curation lists), evaluate the commercial posture and retirement signals. These rarely surface in issues/PRs, so check the repo metadata, README, and external pages directly.

```bash
# Repo metadata: license, archive flag, latest push, latest release, homepage URL.
gh repo view $ARGUMENTS --json name,description,homepageUrl,licenseInfo,isArchived,pushedAt,latestRelease

# README contents (look for "premium features", "Enterprise", "Cloud", retirement notices).
gh api repos/$ARGUMENTS/readme --jq '.content' | base64 -d

# Top-level directory listing (look for ee/, enterprise/, pro/ folders that may carry a non-OSS license).
gh api repos/$ARGUMENTS/contents
```

Then assess each axis below. The first three define the commercial posture; the last two cover retirement.

| Axis                  | Signals to look for                                                                                                                                                                                               | Verdict                                                          |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| **License envelope**  | `licenseInfo` is permissive (MIT, Apache-2.0, BSD); no `ee/`/`enterprise/`/`pro/` folder under a different license                                                                                                | OSS-only                                                         |
| **Feature gating**    | README mentions "Enterprise tier", "Cloud only", "premium features", "protective barrier"; pricing page lists SSO/SAML/OIDC, SCIM, audit log retention, multi-tenancy, fine-grained permissions, admin UI as paid | Open-core (light or heavy depending on which features are gated) |
| **Vendor extraction** | Homepage URL is a vendor domain selling a hosted/Cloud/Enterprise version; pricing page exists; per-MAU or per-seat pricing on what looks like core features                                                      | Commercial-backed                                                |
| **Formal retirement** | README banner pointing to a successor project; statement that "new projects should no longer rely on this"; archive flag set on the repo                                                                          | Retired                                                          |
| **Acquisition drift** | Recent commits are Dependabot/copyright-only; no feature commits in 12+ months; `pushedAt` recent but `latestRelease` stale; vendor's roadmap mentions a successor commercial product                             | Maintained-but-not-developed                                     |

Classify the project as one of: **fully OSS**, **open-core-light** (some advanced compliance/integrations gated, core works in OSS), **open-core-heavy** (essential features gated), **fully proprietary** (no usable OSS), **retired**, or **acquisition-drifted**. Spell out which essential features (per the current project's domain) are gated, if any.

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

#### Commercial posture

State the verdict (fully OSS / open-core-light / open-core-heavy / fully proprietary / retired / acquisition-drifted). For open-core variants, list which essential features are gated and where (Enterprise tier, Cloud add-on, separate `ee/` folder, per-MAU pricing). Include the vendor's pricing-page URL when relevant.

For curation tasks (e.g., feeding an awesome-list selection), use this verdict to decide:

- **Fully OSS** → eligible, mark with the 🆓 marker if the awesome-list uses such markers.
- **Open-core-light** → eligible when covering a distinct niche; mark with the 💸 marker.
- **Open-core-heavy** → reject in overcrowded sections; the OSS shell is not genuinely usable in production.
- **Fully proprietary** → reject when an OSS alternative exists; otherwise borderline.
- **Retired or acquisition-drifted** → flag for removal even when the repo is not formally archived.

#### Retirement and acquisition signals

Quote any explicit retirement notice from the README, link the successor project if named, and call out acquisition-drift symptoms (Dependabot-only commits, stale `latestRelease` despite recent `pushedAt`, vendor roadmap shifted to a successor commercial product).

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
