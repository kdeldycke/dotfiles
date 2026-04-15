---
name: upstream-audit
description: Create or update an upstream contributions page (docs/upstream.md) tracking the project's relationship with its dependencies. Discovers merged PRs, reported issues, workarounds, and declined features.
model: opus
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob, Agent
argument-hint: '[audit|init|refresh|sync-git]'
---

## Context

!`[ -f pyproject.toml ] && grep '^name' pyproject.toml | head -1 || echo "No pyproject.toml"`
!`git config user.name 2>/dev/null || echo "No git user"`
!`gh api /user --jq '.login' 2>/dev/null || echo "No gh auth"`
!`[ -f docs/upstream.md ] && grep '^## ' docs/upstream.md || echo "No docs/upstream.md yet"`
!`[ -f docs/upstream.md ] && grep -c 'github.com/' docs/upstream.md || echo 0`

## Instructions

You create and maintain `docs/upstream.md`, which tracks the project's relationship with its upstream dependencies: code contributed back, workarounds provided, issues reported, and features declined.

### Reference example

Fetch this file as reference when building or auditing an upstream page:

- [`kdeldycke/click-extra/docs/upstream.md`](https://github.com/kdeldycke/click-extra/blob/main/docs/upstream.md): tracks ~35 merged PRs across Click, python-tabulate, Pygments, Furo, Cloup, and click-contrib projects, plus upstreamed workarounds, feature-area-grouped workarounds still in place, declined PRs, and open upstream issues.

### Document structure

The page uses five sections:

1. **Code contributed upstream** - PRs authored by the maintainer and merged into upstream projects. Organized by project, optionally grouped by theme within large projects.
2. **Upstreamed from this project** - Issues the project solved with local workarounds first, then the fix was contributed upstream and the workaround removed locally.
3. **Addressed by this project** - Issues that remain open or unfixed upstream; this project provides the solution. Grouped by feature area.
4. **Declined by upstream** - PRs or issues rejected by upstream maintainers; this project provides the functionality regardless.
5. **Open upstream** - PRs and issues still pending upstream.

Items are listed as markdown links: `` - [`#N` - Title](url) ``

### Scope selection

- `audit` (default): Check status of all linked issues/PRs in an existing page and report items that need to move between sections.
- `init`: Create `docs/upstream.md` from scratch by discovering all upstream contributions.
- `refresh`: Same as audit, but also apply the changes.
- `sync-git`: Scan the git log for upstream references not yet in the document.

### Creating from scratch (`init`)

#### 1. Identify the maintainer

Determine the GitHub username from `gh api /user --jq '.login'` or `git config user.name`. Confirm with the user.

#### 2. Identify upstream dependencies

Extract dependencies from `pyproject.toml` (both `[project.dependencies]` and `[project.optional-dependencies]`/`[dependency-groups]`). For each dependency, find its GitHub repository:

- Check PyPI metadata: `pip show <pkg>` or `https://pypi.org/pypi/<pkg>/json`
- Check `uv.lock` for source URLs

Also include significant build/test/docs dependencies (Sphinx themes, pytest plugins, linters) that the project interacts with.

#### 3. Discover contributions

For each upstream repo, search for the maintainer's participation:

```
gh api "repos/{owner}/{repo}/issues?creator={username}&state=all&per_page=100" \
  --jq '.[] | "#\(.number) \(.title) [\(.state)] \(.pull_request // empty | "PR") \(.html_url)"'
```

For repos with many results, also check PRs specifically:

```
gh search prs --author {username} --repo {owner}/{repo} --limit 50
```

#### 4. Check status of each item

For PRs: `gh pr view <url> --json state,mergedAt,title`
For issues: `gh issue view <url> --json state,stateReason,title`

#### 5. Scan git history

Search the git log for upstream references not yet found:

```
git log --all --oneline --grep="github.com/" | head -100
```

Search the codebase for inline issue references:

```
grep -rn 'github\.com/.*/\(issues\|pull\)/' src/ lib/ --include="*.py" | grep -v __pycache__
```

Also check `docs/` and any changelog for upstream references.

#### 6. Categorize each item

| Item type | Status                                                  | Section                      |
| --------- | ------------------------------------------------------- | ---------------------------- |
| PR        | merged                                                  | Code contributed upstream    |
| PR        | closed, not merged                                      | Declined by upstream         |
| PR        | open                                                    | Open upstream                |
| Issue     | closed, this project had workaround, workaround removed | Upstreamed from this project |
| Issue     | open or closed, this project provides workaround        | Addressed by this project    |
| Issue     | closed as not planned                                   | Declined by upstream         |
| Issue     | open, no local workaround                               | Open upstream                |

To determine whether the project has a workaround for an issue, search the codebase for references to that issue URL or number.

#### 7. Build the page

Write the document following the five-section structure. Within "Code contributed upstream", group PRs by upstream project and optionally by theme (for projects with many PRs). Within "Addressed by this project", group by feature area rather than by upstream project.

Use the `{octicon}` title format if sphinx-design is available (check `docs/conf.py` for the extension):

```markdown
# {octicon}`git-pull-request` Upstream
```

### Auditing an existing page (`audit`)

#### 1. Status check

For every GitHub URL in the document, check its current state via `gh`:

- For PRs: `gh pr view <url> --json state,mergedAt`
- For issues: `gh issue view <url> --json state,stateReason`

Flag items that need to move:

| Current section           | New state                 | Action                                                                              |
| ------------------------- | ------------------------- | ----------------------------------------------------------------------------------- |
| Open upstream             | PR merged                 | Move to "Code contributed upstream"                                                 |
| Open upstream             | Issue closed as completed | Move to "Upstreamed" or "Addressed" depending on whether a local workaround existed |
| Open upstream             | Closed as not planned     | Move to "Declined by upstream"                                                      |
| Addressed by this project | Fixed upstream            | Move to "Upstreamed from this project"                                              |

#### 2. Consistency checks

- All items in "Code contributed upstream" are actually merged (not just closed).
- All items in "Open upstream" are actually still open.
- No item appears in multiple sections.
- Items within each project subsection are sorted by issue number (newest first).

### Git log scan (`sync-git`)

Search for upstream references not yet tracked:

```
git log --all --oneline --grep="github.com/" | head -100
git log --all --oneline --grep="upstream" | head -50
git log --all --oneline --grep="workaround" | head -50
git log --all --oneline --grep="backport" | head -50
```

For each new reference, determine which section it belongs to and report it.

### Output format

For `audit`, produce a summary:

| Action                | Count |
| --------------------- | ----- |
| Items to move         | N     |
| New items to add      | N     |
| Stale items to remove | N     |

Then list each change with: URL, current section, recommended section, reason.

Do not edit the file until the user confirms (except with `refresh`).

### Cross-referencing with `docs/benchmark.md`

The upstream page and the benchmark page both track upstream issues and PRs. When items change status in `docs/upstream.md` (a gap gets fixed, a workaround gets upstreamed, a PR gets merged), check whether `docs/benchmark.md` has a corresponding entry in its "Gaps and opportunities" or feature tables that needs updating. Suggest running `/benchmark-update audit` afterward if upstream changes affect the competitive comparison.
