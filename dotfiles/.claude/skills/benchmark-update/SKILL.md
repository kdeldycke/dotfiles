---
name: benchmark-update
description: Create or update a competitive benchmark page (docs/benchmark.md) comparing the current project against alternatives in the same space. Checks maintenance status, feature accuracy, new candidates, and badge health.
model: opus
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob, WebFetch, WebSearch, Agent
argument-hint: '[audit|init|add <project>|refresh-badges]'
---

## Context

!`[ -f pyproject.toml ] && grep '^name' pyproject.toml | head -1 || echo "No pyproject.toml"`
!`[ -f docs/benchmark.md ] && head -15 docs/benchmark.md || echo "No docs/benchmark.md yet"`
!`[ -f docs/benchmark.md ] && grep -c '^|' docs/benchmark.md || echo 0`
!`[ -f CLAUDE.md ] && grep -i 'ordering\|benchmark\|comparison' CLAUDE.md | head -5 || echo "No ordering conventions found"`

## Instructions

You create and maintain `docs/benchmark.md`, a competitive benchmark page comparing the current project against alternatives in the same space. The page follows a standard template with feature tables, GitHub activity badges, popularity charts, distribution info, and metadata.

### Reference examples

Fetch these files as reference when building or auditing a benchmark page:

- [`kdeldycke/meta-package-manager/docs/benchmark.md`](https://github.com/kdeldycke/meta-package-manager/blob/main/docs/benchmark.md): package manager comparison with features, operations, OS support, distribution, activity, popularity, and metadata tables.
- [`kdeldycke/click-extra/docs/benchmark.md`](https://github.com/kdeldycke/click-extra/blob/main/docs/benchmark.md): CLI framework comparison with DX/UX feature tables, parser flag scoping, unique strengths, gaps with upstream issue references, and an "Excluded frameworks" section.

### Scope selection

- `audit` (default): Run all checks on an existing benchmark page and report findings. Do not edit unless the user confirms.
- `init`: Create a benchmark page from scratch. Research competitors, build feature tables, and populate all sections.
- `add <project>`: Research a specific project and add it to all tables in the correct position.
- `refresh-badges`: Verify all badge URLs resolve. Fix broken ones (repos that moved, renamed packages).

### Column ordering convention

If `CLAUDE.md` defines a benchmark ordering convention, follow it. Otherwise, place the current project first, its direct dependencies/foundation second, then remaining projects sorted by GitHub stars (descending).

### Creating a benchmark from scratch (`init`)

#### 1. Identify the project and its domain

Read `pyproject.toml` for the project name, description, and keywords. Determine what category of software this project is (CLI framework, package manager, static site generator, linter, etc.).

#### 2. Discover competitors

Search for alternatives in the same space:

- Search GitHub: `gh search repos "<domain keywords>" --sort stars --limit 30`
- Search PyPI and other registries for similar tools.
- Check "awesome" lists on GitHub.
- Look at the project's own README or docs for mentions of alternatives.

For each candidate, collect: name, GitHub `owner/repo`, approximate star count, one-line description, and language/ecosystem.

Present the candidates and ask the user which to include.

#### 3. Research features

For each included project, research its feature set by reading its documentation, README, and changelog. Build comparison tables relevant to the domain. Common table categories:

- **Features**: core capabilities, grouped by audience (developer experience vs. end-user experience) when applicable.
- **Activity**: GitHub badges (watchers, contributors, commit activity, commits since latest release, last release date, last commit, open issues, open PRs, forks, dependencies freshness).
- **Popularity**: star history chart + badges (stars, SourceRank, dependent repos).
- **Distribution**: package registry badges (PyPI, crates.io, npm, Homebrew, etc.) as applicable.
- **Metadata**: license, main language, latest version, benchmark date.

Use `✓` for supported features, `~` for basic/partial support, empty for unsupported, `N/A` where not applicable.

#### 4. Gap analysis

After building the feature tables, analyze them to identify:

- **Unique strengths**: features where this project leads or is the only one offering the capability. Summarize each with a brief explanation of why it matters.
- **Gaps and opportunities**: features where competitors lead and this project could improve. For each gap:
  - Search the project's primary upstream dependency (if any) for related open issues and PRs using `gh issue list --repo <upstream> --search "<feature>" --state open`.
  - Link to specific upstream issues with their number, title, and demand signals (thumbs-up count, comment count).
  - Note whether upstream has declined the feature, has a pending PR, or has never been asked.
  - Describe what this project could do to close the gap (override, extend, integrate a third-party package, etc.).

This analysis turns the benchmark from a static comparison into an actionable roadmap.

#### 5. Build the page

Follow this template structure:

```markdown
# {octicon}`trophy` Benchmark

<intro paragraph about why this comparison exists>

## <Feature category 1>

<legend if needed>

| Feature | `this-project` | `competitor-1`[^1] | ... |
| ... | :---: | :---: | ... |

<brief prose highlighting key differences>

## <Feature category 2>

...

## Unique strengths

<bullet list of features where this project leads, with brief explanations>

## Gaps and opportunities

### <Gap title>

<description of the gap, with links to upstream issues like `[owner/repo#N](url)` including demand signals>

<what this project could do to close the gap>

### <Gap title>

...

## Activity

| Metrics | `this-project` | `competitor-1`[^1] | ... |
(GitHub badge rows: watchers, contributors, commit activity, etc.)

## Popularity

[![Star History Chart](<star-history-url>)](<star-history-link>)

| Metrics | `this-project` | `competitor-1`[^1] | ... |
(Stars, SourceRank, Dependent repos)

## Distribution

| Registry | `this-project` | `competitor-1`[^1] | ... |
(PyPI, crates.io, npm, Homebrew downloads)

## Metadata

| Metadata | `this-project` | `competitor-1`[^1] | ... |
(License, main language, latest version, benchmark date)

## Excluded projects

~~~{note}
<Project name> is not included because <reason>.
~~~

## Project URLs

[^1]: [<url>](<url>)
```

Badge format follows shields.io conventions: `![GitHub](https://img.shields.io/github/<metric>/<owner>/<repo>?label=%20&style=flat-square)` for compact badges with no label text.

Star history chart: `[![Star History Chart](https://api.star-history.com/svg?repos=<comma-separated>&type=Date)](https://star-history.com/#<ampersand-separated>&Date)`

### Auditing an existing benchmark (`audit`)

#### 1. Maintenance status check

For each project in the benchmark, check via `gh api`:

- Last commit date on the default branch.
- Last GitHub release date.
- Whether the repo is archived.
- Any deprecation or sunsetting announcements in recent issues.

Classify each as: **active**, **slow but maintained**, **stale** (no activity in 12+ months), or **abandoned/archived**.

Stale or abandoned projects should be moved to the "Excluded projects" section with a `{note}` admonition explaining why.

#### 2. Feature matrix accuracy

For each feature row, spot-check 2-3 projects against their current documentation or changelog. Flag cells that look wrong (features added or removed since the benchmark was written).

#### 3. Gap analysis freshness

For each item in "Gaps and opportunities", check whether the linked upstream issues have changed status:

- Closed issues: the gap may have been addressed upstream or in this project. Verify and update.
- New upstream PRs: a fix may be in progress.
- Features this project has since implemented: the gap should be removed and the feature moved to "Unique strengths" or the feature table updated.

Also check whether new gaps have appeared (competitors added features this project lacks).

#### 4. New candidates

Search for projects in the same space with significant GitHub stars not already in the benchmark. Report candidates with: name, GitHub repo, stars, one-line description, and maintenance status.

#### 5. Badge health

Verify the GitHub `owner/repo` in badge URLs matches the current canonical location. Repos get transferred. Check via `gh api repos/{owner}/{repo} --jq '.full_name'`.

#### 6. Star history chart

Verify the star-history.com URL includes all current projects and no excluded ones.

### Adding a project (`add`)

1. Research its features against every row in the existing feature tables.
2. Determine the correct column position per the ordering convention.
3. Add it to **every** table (features, activity, popularity, distribution, metadata).
4. Add a footnote with the project URL.
5. Add it to the star history chart URL.

### Output format

For `audit`, produce a summary table:

| Project | Status               | Issues found                         |
| ------- | -------------------- | ------------------------------------ |
| ...     | active / stale / ... | badge broken / feature changed / ... |

Then list recommended actions. Do not edit the file until the user confirms.

### Cross-referencing with `docs/upstream.md`

The gap analysis surfaces upstream issues and PRs that overlap with what `docs/upstream.md` tracks. When the benchmark discovers new upstream issues (reported, workaround in place, declined, or fixed), check whether they belong in `docs/upstream.md` too. Suggest running `/upstream-audit sync-git` afterward if new references were added to the benchmark.
