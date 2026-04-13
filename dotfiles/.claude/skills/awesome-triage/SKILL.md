---
name: awesome-triage
description: Triage new issues and PRs on awesome-list repos by applying curation criteria distilled from past decisions.
model: opus
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob, WebFetch, WebSearch
argument-hint: <issue-or-pr-url>
---

## Context

!`gh api repos/{owner}/{repo} --jq '.description' 2>/dev/null`
!`cat .github/contributing.md 2>/dev/null | head -20`

## Instructions

You help the maintainer triage incoming issues and PRs on awesome-list repositories (awesome-billing, awesome-iam, awesome-falsehood, awesome-engineering-team-management) by applying curation criteria distilled from historical accept/reject decisions across all four lists.

### Prerequisites

Read `.github/contributing.md` in the current repo before triaging. It is the canonical source of truth for formatting rules, editorial line, section ordering, content candidates, and rejection reasons. This skill does not restate those rules — it adds the analytical layer on top: structured evaluation, signals the guide does not codify, and comment/label recommendations.

### Argument handling

`$ARGUMENTS` should be a GitHub issue or PR URL (e.g., `https://github.com/kdeldycke/awesome-billing/issues/42` or `#42`). If empty, list the 10 most recent open issues and PRs and ask the user which to triage.

### Fetch the submission

1. Use `gh issue view` or `gh pr view` to get the title, body, labels, and author.
2. For PRs, also fetch the diff with `gh pr diff`.
3. Fetch all comments with `gh issue view --comments` or `gh pr view --comments`.
4. If the submission proposes a URL, fetch that URL to inspect the linked resource.

### Triage checklist

Evaluate the submission against each criterion below. For each, state PASS, FAIL, or NEEDS REVIEW with a one-line explanation.

#### 1. Template compliance

- **Issues**: Must use the new-link issue template (URL field filled, motivation provided, affiliation disclosed, self-checks completed).
- **PRs**: Must fill the PR template (motivation section explaining what the link adds, affiliation checkboxes, self-checks completed).
- PRs that skip the template entirely or leave placeholder text ("This new link is special because...") fail this check.

#### 2. Duplicate detection

- Search existing list entries (`readme.md` and all `readme.*.md`) for the proposed URL or domain.
- Search closed issues and PRs for the same URL: `gh issue list --state closed --search "<url>"` and `gh pr list --state closed --search "<url>"`.
- **Domain cap**: Two links to the same commercial domain is the soft maximum (see `contributing.md` FAQ "Why my link was rejected?"). A second link to the same domain *in the same section* already looks like content stuffing.
- The same URL must not appear in multiple sections (awesome-list guidelines prohibit duplicate links across sections).

#### 3. AI slop detection

This is not covered by `contributing.md`. Look for these signals (any two together warrant the `AI slop` label):

- The PR body or issue text reads as LLM output (generic phrasing, no specific knowledge of the list's content, template-like structure beyond the actual template).
- The PR explicitly discloses AI generation (e.g., "Generated with Claude Code", "Created by Copilot").
- The linked resource's content appears auto-generated (generic copy, placeholder text, stock descriptions, no voice or editorial specificity).
- The product is not launched (coming soon pages, empty repos, placeholder domains on Vercel/Netlify).
- The proposed description is a rewrite of the resource's meta description or first paragraph without editorial judgment.

#### 4. Competitive context

- Identify the proposed resource's direct competitors or comparable tools (check the resource's own comparison page, "alternatives to" sections, or npm/PyPI "related packages").
- Check whether any of those comparables are already in the list.
- If none of the resource's peer group is featured, the resource likely falls outside the list's scope. This is a strong rejection signal. (Pattern from awesome-billing PRs #175, #176 and awesome-iam PR #158.)

#### 5. Section saturation

- Count the entries in the target section. Is it already well-served?
- The lists are in a **curation phase, not an accumulation phase** (contributing.md § Status). Overcrowded sections need curation (removing weaker entries), not more links. The maintainer has rejected well-written, relevant content purely because the section was full enough (awesome-iam PRs #131, #158; awesome-iam PR #76).
- If an existing link already "tells the story" of the concept, a second article on the same ground is rejected.

#### 6. Affiliation and commercial signals

- Check which affiliation box the contributor ticked: author, employee, or unaffiliated.
- Cross-reference with the contributor's GitHub profile, the resource's domain, and commit history.
- Self-promotion is allowed but must be disclosed. Undisclosed affiliation is a trust signal.
- Author submissions get more scrutiny on the "marketing vs. genuine content" axis but are not automatically penalized. Many accepted PRs across all four lists are author self-submissions.
- For commercial content, apply `contributing.md` FAQ "Why my commercial project is not in the list?": prefer open-source repository links over commercial landing pages.

#### 7. Formatting and editorial compliance

Check the diff (for PRs) against `contributing.md` §§ Formatting and Editorial line. Flag deviations but do not restate the rules here: read the guide.

#### 8. Resource quality

- **Launched and functional**: The product or article must exist and be accessible.
- **Maintained**: For GitHub repos, check if the project is archived, when the last commit was. Archived or abandoned projects are candidates for removal (contributing.md FAQ "Why removes inactive GitHub projects?"). Check for forks or reboots before recommending deletion.
- **Generic, not product-specific**: Articles applicable to only one product are not generic enough for inclusion (contributing.md "Why my link was rejected?" + awesome-falsehood PR #31).

### Verdict

After running all checks, provide one of:

- **ACCEPT**: All checks pass. Suggest merging (possibly with minor formatting fixes).
- **ACCEPT WITH CHANGES**: Value is there but formatting, description, or placement needs work. List the specific changes needed.
- **REJECT**: Fails one or more hard criteria (duplicate, AI slop, not launched, paywalled, no value-add, section saturation, competitive context mismatch). Draft a rejection comment.
- **NEEDS DISCUSSION**: Borderline case where maintainer judgment is required. Summarize the arguments for and against.

### Drafting comments

When drafting a rejection or request-for-changes comment:

- Be specific about which criteria were not met.
- Reference `contributing.md` sections where applicable.
- Stay polite and constructive. Contributors may improve and resubmit (e.g., awesome-iam PR #179 was rejected, contributor revised and PR #182 was merged).
- For AI slop: keep it brief. State the specific tells (e.g., "the site content appears auto-generated", "the product does not appear to be launched yet").
- When a section is saturated, suggest the contributor identify weaker existing entries that could be replaced, turning an addition into a curation improvement.

### Broken link triage

For issues reporting broken links (typically automated by the lychee link checker):

- **403 from Medium/Substack**: Bot-blocking responses, not genuine dead links. Ignore unless the content is confirmed gone.
- **404 confirmed dead**: Replace with archive.org/archive.ph/sci-hub.st per `contributing.md` § URL. Replacing a broken URL is maintenance; removing the entry is a curation decision.
- **Archived GitHub repos**: Check for forks or reboots. If none exist and the section has other entries covering the same ground, the entry can be removed. Leave the door open for re-inclusion if the project revives.

### Label recommendations

Suggest applying these labels based on findings:

| Label         | When to apply                                                   |
| ------------- | --------------------------------------------------------------- |
| `AI slop`     | Two or more AI slop signals detected.                           |
| `curation`    | Involves removing, replacing, or reorganizing existing entries. |
| `new link`    | Proposes adding a new resource to the list.                     |
| `duplicate`   | The resource or a near-equivalent is already in the list.       |
| `fix link`    | Reports or fixes a broken URL.                                  |
| `wont do/fix` | Maintainer decision to not act on the request.                  |

### Next steps

Suggest the user:

- Apply the recommended labels.
- Post the drafted comment if rejecting or requesting changes.
- For accepted PRs, check that translations in `readme.*.md` are updated before merging.
