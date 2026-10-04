@~/.claude/tropes.md

## Consuming repomatic

### Upstream conventions

This repository takes its reusable workflows and much of its `pyproject.toml` configuration from [`kdeldycke/repomatic`](https://github.com/kdeldycke/repomatic), and follows the conventions established there. The generic sections of this file were seeded from that same upstream and are now maintained here: repomatic no longer syncs instructions into consuming repos, so an edit to one of them belongs in this file, not upstream.

**Contributing upstream:** propose a gap or improvement in the reusable workflows, the `repomatic` CLI, or a shared convention at [`kdeldycke/repomatic`](https://github.com/kdeldycke/repomatic/issues). Landing it upstream is what carries it to every other repository consuming it, instead of fixing it once here.

### Managed versus downstream-owned workflow content

A generated workflow file has two parts. The first job is the **managed thin caller**, delegating to a reusable upstream workflow through a SHA-pinned `uses:`. It is rebuilt from scratch on every sync, so a hand edit to it is lost. Everything declared *after* it is **downstream-owned**: the sync slices the file at the end of the managed job body and carries the remaining text through verbatim, comments and blank lines included.

Position alone does not settle ownership: a multi-job caller declares canonical jobs after its first one, and those are regenerated too. Write a comment above your first downstream job saying so. The sync preserves it like any other extra content but never writes one itself, so its absence means the file has nothing in it that is yours to edit.

A fragment that is only comments and blank lines is still carried over, and deliberately does not count as a downstream job for the rule below.

A workflow with no thin caller (`tests.yaml`) still has a managed part: the sync rewrites its header, everything above `jobs:`, triggers and `paths:` filters included. Change a filter through `[tool.repomatic]` instead: `workflow.extra-paths` appends to the `paths:` of every workflow, and `workflow.paths` replaces one workflow's list whole.

### The permissions contract is generated, not hand-written

When a workflow file carries downstream-owned jobs, the sync emits a top-level `permissions: {}` **and** the scopes the reusable workflow needs on the managed caller job. Both halves ship together, and neither is written by hand: a top-level `{}` on its own starves the managed call, which GitHub aborts at startup the moment a nested job asks for a scope the caller never granted.

So a `lint-repo` complaint about a missing top-level `permissions` key is a signal to re-run the sync, not to add the key yourself. Declare least privilege per job on the downstream-owned jobs instead, which is the half no sync rewrites.

### Bumping the repomatic pin

The `sync-repomatic` job bumps the pin: once a newer release clears `minimum-release-age`, it opens an `Upgrade repomatic to vX.Y.Z` pull request. That pull request moves the pin and every managed file together, and lists the breaking changes it crosses. After the merge, run the `/repomatic-upgrade` command it gives, to apply what the release lets the repository adopt, reuse or drop.

To adopt a release before it clears the cooldown, bump by hand. Regenerate rather than search-and-replace, so codegen changes (new job permissions, reshaped triggers) arrive with the version bump instead of a release behind it:

```shell-session
$ uvx --no-progress 'repomatic==X.Y.Z' init --no-cooldown workflows/autofix.yaml workflows/lint.yaml
```

`--no-cooldown` moves the pin. Without it, `init` holds the pin back while the release is inside the window, and leaves the workflows as they are. `init --upgrade` cannot do this job: it skips a release inside the window, and it takes no components.

Name the components explicitly. A bare `repomatic init` also materializes whatever else is in scope for the repository (labels config, a changelog), and an unqualified `workflows` selector bypasses scope gating.

Then run `/repomatic-upgrade`, which `init` prints as its last next step. A renamed autofix job is the recurring manual follow-up: its old PR branch stays open, attached to a job that no longer exists.

### Tools called from workflows are version-pinned

Every external tool a workflow invokes carries an exact version literal, in one of the shapes `sync-workflow-pins` recognizes: an action `uses:` ref, `uvx '{pkg}=={X.Y.Z}'` and the `--with` form for PyPI, `npm install {pkg}@{X.Y.Z}` for npm, and the `version:` input on `astral-sh/setup-uv`. That job resolves each to the newest release past `minimum-release-age` and opens a pull request. A tool invoked unpinned floats to the newest release on every run, outside the window entirely: see [§ Live registries with no cooldown knob](#live-registries-with-no-cooldown-knob).

A tool the runner image happens to provide is worse than an unpinned install, because it carries no version anywhere in the repository for anything to bump. Reach for a pinned dependency that already does the job instead of finding a way to pin the tool.

A version literal outside those shapes is worse still, because it *looks* maintained and nothing walks it. `gh release download vX.Y.Z` is the one to watch: it pins honestly, `sync-workflow-pins` does not recognize it, and no job ever proposes a bump. One sat three months past the release fixing a CVE in the tool it installs. Where a pin cannot take a recognized shape, say so in a comment beside it naming who is expected to bump it. A permanently-red gating job hides such a pin twice over, since a cell that can only fail teaches readers to ignore that workflow's red runs.

### PAT-gated checks degrade, they do not fail

Several `lint-repo` checks read GitHub API endpoints needing a scope on `REPOMATIC_PAT`. When the token lacks one, or the call fails for any other reason, the check returns an *indeterminate* result and is reported as skipped: it never fails the job. A missing scope costs coverage, not a red run, which is [§ Defensive workflow design](#defensive-workflow-design) applied to the audit lane.

Do not read a skipped check as a passing one. The setup-guide issue carries the pre-filled link for regenerating the token with the scopes a repository's own checks want.

### Configuration repomatic reads

`[tool.repomatic]` in `pyproject.toml` belongs to the repository and is authoritative for every feature flag. The tool sections synced from repomatic's bundled templates are not: a local edit to a key the template owns is re-applied on the next sync, so put a deviation behind a `[tool.repomatic]` setting rather than editing the synced value and expecting it to hold.

The sync grafts rather than overwrites. A key the template does not define survives verbatim, a table present in both is merged so local sub-keys are kept, and an array gains its local-only items after the template's. Only a scalar the template also defines is overwritten, which is the point of an ongoing sync. Comments on a grafted node carry over; a comment beside a key the template owns does not, so record why a local entry exists somewhere the merge cannot reach.

## Cooldown on every install

**Every command that resolves a package from a live registry carries a cooldown, except where this section names otherwise.** A cooldown refuses any version published more recently than a fixed window, so a compromised release has to survive that window before it can enter a build. Most malicious releases (stolen publishing credentials, dependency confusion, account takeover) are [caught and pulled within days of publication](https://blog.yossarian.net/2025/11/21/We-should-all-be-using-dependency-cooldowns), which is what makes a window of days worth the delay it costs.

The rule has **no scratch exemption**. It binds reusable workflows, one-off CI steps, test scripts, local reproduction commands, and throwaway experiments equally: an uncooled `uvx` in a five-minute debugging step resolves the same tree from the same registry onto the same runner as a production job. If you type an install command, it carries the cooldown. The exceptions are the [documented exemptions](#documented-exemptions) below, and nothing else.

### A cooldown is not a hash

A cooldown proves a version has been public long enough for a compromise to surface; a pin proves everyone resolves the same version; a checksum proves the bytes are the bytes that version shipped. A `uvx`-resolved tree has the cooldown but no checksum, because a `uvx` environment has no lockfile: `uv.lock` is the only place a Python dependency is hash-pinned. Know which guarantee you rely on before you call something verified.

### Where the window comes from

`[tool.repomatic] minimum-release-age` (default `1 week`) is the single source of truth. Never hard-code a duration next to an install command: read it from config, or from the `npm_min_release_age_days` output `repomatic show-metadata` derives from it. Every workflow carries the value as a workflow-level `UV_EXCLUDE_NEWER` and `NPM_CONFIG_MIN_RELEASE_AGE` env block, and `[tool.uv] exclude-newer` must equal it.

### Per-ecosystem knobs

| Ecosystem                                                                             | Cooldown                                                           | Per-package exemption                                   |
| :------------------------------------------------------------------------------------ | :----------------------------------------------------------------- | :------------------------------------------------------ |
| uv: `uvx`, `uv pip install`, `uv run --with`, `uv tool install`, `uv lock`, `uv sync` | `--exclude-newer`, or `UV_EXCLUDE_NEWER`                           | `--exclude-newer-package pkg=YYYY-MM-DD`, CLI flag only |
| npm, `npx`                                                                            | `--min-release-age` in whole days, or `NPM_CONFIG_MIN_RELEASE_AGE` | `--min-release-age-exclude` taking a name or glob       |
| A tool in the `repomatic run` registry                                                | applied by the runner                                              | n/a                                                     |

uv accepts a friendly duration (`1 week`), an ISO 8601 span (`P7D`), or an absolute date; npm counts whole days and needs 11.10.0 or newer. Both knobs gate the whole resolved tree, transitive dependencies included, which is the point: the compromised package is rarely the one named on the command line. An *exemption* does not inherit that reach: exempting a package leaves its own dependencies gated, so a bypass reaching a fresh release usually has to name the transitive closure that release pulled in, one round-trip at a time.

A cooldown-filtered resolution is not a dependency conflict: before you diagnose a uv "No solution found" as one, read its `hint:` line, which names the filtered package, the cutoff it hit and the version it would otherwise have picked. No exit code tells the two apart.

For any other package manager, [meta-package-manager's cooldown inventory](https://kdeldycke.github.io/meta-package-manager/cooldown.html#supported-managers) lists which ones enforce a cooldown natively, which have support proposed upstream, and which have none. Read its N/A verdict as a different threat model, not a gap: see [§ Distro archives are out of scope](#distro-archives-are-out-of-scope-not-an-exception).

### Live registries with no cooldown knob

Fail closed. When a *live registry* client has no cooldown knob, do not hand it a floating version range. Either pin an exact version that a cooldown-gated updater already vetted (`sync-action-pins`, `sync-tool-versions` and `sync-workflow-pins` all apply `minimum-release-age` before proposing a bump), or route the install through a client that has one. An unpinned install against a self-service registry is the exact thing this rule exists to prevent.

Check the [inventory](https://kdeldycke.github.io/meta-package-manager/cooldown.html#supported-managers) before concluding a client is knob-less, because they keep gaining one: `pip` grew `--uploaded-prior-to` / `PIP_UPLOADED_PRIOR_TO` in `26.1`, and `pipx` inherits it from the pip inside each venv it manages. A knob with a version floor also fails *open* on older releases, quietly ignoring the flag rather than erroring, so pair it with a floor check the way `repomatic run` does for npm (`NPM_MIN_VERSION_FOR_COOLDOWN`).

### Distro archives are out of scope, not an exception

`apt` and its peers are **not** live registries. A stable archive moves only through the distro's own staging, which is a cooldown one layer down, and nobody self-publishes into it. A distro version string also names the maintainer's package build, not an upstream publish date, so a publish-date filter has nothing to filter on.

**The exception is a repository you add yourself.** A PPA or a vendor's `.repo` file is a live, single-publisher registry with none of the distro staging behind it: pin the version there, or fetch a checksummed artifact instead.

Prefer the tool registry over `apt-get` when both can supply a binary: the registry version is pinned, checksum-verified, and identical on every runner and every developer machine. For a tool a *plugin* shells out to, declare it in the plugin host's `path_tools` (`mdformat` does this for `shfmt`). Write the `apt-get` calls you keep with `apt-get`, never `apt` (the `apt(8)` man page prefers `apt-get` in scripts), and with `--no-install-recommends`, then name any package the dropped Recommends were providing.

### Documented exemptions

An exemption is an install that deliberately bypasses the window, declared in the open rather than smuggled in.

Any other exemption is a bug until proven otherwise. Anything claiming one carries a comment naming what breaks without it, and the narrowest scope that still works: a package, not a job; a job, not a workflow.

A consuming repo runs the same rule against its own, which is usually empty. One category recurs and is worth naming, because it reads like a violation and is not: a dependency the same maintainer publishes. The window guards against a compromised upstream, and here the publisher and the consumer are the same person, so it buys nothing while holding each release back a week from the only repository that consumes it. Exempt it per-package, with a zero span, and put the reasoning beside it:

```toml
[tool.uv]
# apricot is published by this repository's own maintainer: the cooldown guards
# against a compromised upstream, which does not apply here, and it otherwise
# holds each release back a week from the one repository that consumes it.
exclude-newer-package = { apricot = "0 days" }
```

The entry admits one release only: `sync-uv-lock` rewrites the zero span as a fixed date that holds the locked release, then removes the entry once that release clears the window. Add it again for the next release that must not wait. A git or path source has no release date to freeze, so it alone keeps its span.

Declaring it in `pyproject.toml` rather than in a machine's `~/.config/uv/uv.toml` is what makes a fresh clone resolve the same way, and keeps the exemption reviewable in a diff. It stays a bypass and not a hole: the transitive tree that release pulls in is still gated, and that tree is the part the maintainer did not publish.

## A release ships only released dependencies

Consuming a dependency from a git branch, a fork, a local path or a private index is the right move mid-cycle, and `[tool.uv.sources]` exists for it. Releasing while one is in place is not: source overrides never reach the published metadata, so the wheel builds and uploads exactly as it would have, and only the *install* fails.

`repomatic lint-deps` is the gate, and it blocks everything off-index, `[dependency-groups]` included. Do not weaken a finding to a warning to get a release out; the two legitimate moves are to land the swap (`sync-dep-sources` automates the git-branch-plus-`.dev`-floor idiom on its own) or to name the package in `[tool.repomatic] lint-deps.allow` with the reason it is safe.

## A floor comment justifies one version

Every version floor carries a comment above it saying what breaks below that version and where the project would notice. That comment documents **the floor as it stands**, in one short paragraph. It is not a log of how the floor got there.

The failure mode is additive and slow. A floor bump arrives, whoever writes it appends a paragraph about the new version, and nobody deletes the paragraph about the old one, since deleting text that reads as informative feels like losing something. Repeat over a few years and the comment is a private changelog of the dependency, with the declared version buried under the floors it replaced.

So when you raise a floor, **rewrite the comment, don't extend it**:

- **Keep** what the newly required version buys, named concretely enough to check: the API, the fix, the `requires-python` alignment, plus the call site or module that consumes it. A CVE identifier or upstream issue reference is part of that claim, not history.
- **Delete** every superseded floor. A version no longer declared cannot break anything for a reader running the declared one, and `git log -- pyproject.toml` and `git blame` hold that story for whoever wants it.
- **Move out** anything that is not about *this* floor: how the dependency is used across the codebase belongs in the module that uses it, and a comparison against an alternative package belongs in `docs/` or an `XXX` pointer to the upstream ticket.

`lint-deps` warns (without failing) on any floor comment over `[tool.repomatic] lint-deps.comment-word-threshold` words, 40 by default: the same ceiling as a changelog bullet, for the same reason. Both are read by someone who came for one fact. A comment past that ceiling is either narrating history (cut it) or documenting two things (one of them belongs elsewhere).

## Documentation requirements

### Keeping `claude.md` lean

`claude.md` must contain only conventions, policies, rationale, and non-obvious rules Claude cannot discover by reading the codebase. Actively remove:

- **Structural inventories**: project trees, module tables, workflow lists. Discoverable via `Glob`/`Read`.
- **Code examples that duplicate source files**: YAML snippets copied from workflows, patterns visible in every module. Reference the source instead.
- **General programming knowledge**: standard idioms, well-known library usage, tool descriptions derivable from imports.
- **Implementation details readable from code**: what a function does. Only the *rationale* for non-obvious choices belongs here.
- **Anecdotes naming content published elsewhere**: the upstream thread, pull request, comment or release post where a lesson happened. The rule stands without it, and the reference rots as its target changes. Keep an external link only when it does a job: a ticket to revisit once it lands, or the source a claim depends on.
- **Incident narratives**: how a lesson was learned, with its dates, durations, measured counts and the tool version that misbehaved. Keep the rule and its fix, in two sentences at most, and a version stamp only on a claim about Claude Code or pi; the story belongs in the commit message.

### Changelog and docs updates

Always update documentation when making changes:

- **`changelog.md`**: One bullet per user-facing change, describing **what** changed (features, fixes, behavior changes), not **how** it was built or **why**. See [§ Changelog entry length](#changelog-entry-length); rationale belongs in `docs/`, code comments, the commit message, or the PR body, never the changelog.
- **`docs/`**: When this repo has a `docs/` tree, update the relevant page when adding or modifying workflow jobs, CLI commands, or configuration options.

**Never ship an empty release section.** When a cycle's net diff since the last tag is entirely mechanical — a dependency-pin bump, a generated-file regen, a docs-only or CI-only fix — and nothing qualifies as user-facing, add one bullet naming what actually moved rather than leaving the section blank under a heading that still gets tagged and published. A blank section reads as unexplained or broken to anyone scanning release notes for that version. Assert the absence of functional impact only when it is verified (a green, behavior-preserving cycle); otherwise just name the mechanical change: "Sync CI tooling, workflow pins and dependency floors with the latest repomatic release."

**Order within a release section:** `**Breaking:**` entries first, then `**Deprecated:**` entries, then new features, other changes, bug fixes and docs (a reader scans for breaking changes first).

Use `**Breaking:**` when a surface the reader actually consumes is gone and their code, invocation, config or workflow must change to keep working. Use `**Deprecated:**` when the old surface still resolves but emits a `DeprecationWarning` and is scheduled for removal in a named future release: name that release in the entry, so the reader knows their deadline.

**Who consumes the project decides what counts as breaking.** A project consumed as a library breaks real code when a Python symbol is renamed, moved or dropped, so that symbol earns a bullet. A project that is invoked rather than imported does not: its importable surface is an implementation detail, and a bullet announcing a dropped enum or a regrouped module only alarms readers who could never have called it.

To back a `**Deprecated:**` change in code, keep the old name importable for one cycle instead of deleting it: resolve it through an alias registry in a PEP 562 module `__getattr__` hook that emits the `DeprecationWarning` and redirects to the replacement, then remove it in the release the entry named. Reserve a hard `**Breaking:**` removal for a surface that genuinely cannot keep working. The `_deprecated.py` modules in `click-extra` and `extra-platforms` are reference implementations.

#### Changelog entry length

A changelog entry is a **release note**, not a commit message or PR description. The reader scans to decide: does this affect me, and must I do anything? Write the shortest bullet that answers both.

- **One sentence by default**, ~10-25 words. Add a second sentence only to flag a breaking change or migration step. A bullet past ~40 words is a smell: it smuggles in implementation detail (cut it) or covers two changes (split it).
- **Keep the user-facing surface:** the public name (CLI command, option, config key, or exported function/class where the project is imported), what it does for the user, plus the migration when it breaks something. Lead with the change, not the mechanism.
- **Cut what the user cannot see or act on**, and move it: *mechanism* (the module/function/job implementing it) to the commit, PR, or code comment; *rationale* (why this approach, which edge case) to a code/docstring comment or `docs/`; *archaeology* (dependency floors chased mid-cycle, root cause, CI trivia) to the commit or PR.
- **Name, don't narrate.** "Add `--cooldown` to skip packages newer than a given age" beats three sentences naming the environment variable each backend uses.

`lint-changelog` warns (without failing) on any unreleased bullet over `[tool.repomatic] changelog.bullet-word-threshold` words. Released sections are immutable.

**Do not mention in the changelog:**

- **Internal refactors behind an unchanged user surface**, in a project nobody imports. A module regrouped, a helper moved between modules, an enum merged or dropped, a signature reworked: none of it reaches a user whose CLI commands, config keys, workflow inputs and metadata keys all still resolve. Omit the bullet rather than demoting it out of `**Breaking:**`; the commit and PR already record the move.
- **Test work of any kind.** Fixtures, snapshots, parametrize cases and assertions adjusted to match a change, and equally the structural work: a new harness or fixture mechanism, switching `unittest.TestCase` to functions, parametrizing a whole module. None of it reaches a user, and `git log` already records it for contributors.
- **Short-shelf-life workarounds.** `tool.uv.exclude-newer-package` cooldown bypasses, dev pins for transient upstream bugs, `xfail` markers, commented-out lines: reverted within days. Drop unless load-bearing beyond a release cycle.
- **Upstream issue commentary.** Prose about a ticket's state (open/closed/not planned, "mirrors the upstream fix in…"). It rots in days and duplicates what `git blame` and the linked thread show. A bare upstream link is fine for a direct backport (`fix … from upstream PR x/y#NNN`); anything longer belongs in a code comment, docstring, or PR. Strip the prose during `consolidate`.

### Knowledge placement

Each piece of knowledge has one canonical home, chosen by audience; other locations get a brief pointer ("See `module.py`.").

| Audience              | Home                      | Content                                                                 |
| :-------------------- | :------------------------ | :---------------------------------------------------------------------- |
| GitHub visitors       | `readme.md`               | Landing page: pitch, quick start, links to docs.                        |
| End users             | `docs/`                   | Installation, configuration, dependencies, workflows, security, skills. |
| Setup walkthroughs    | `setup-guide.md` issue    | Step-by-step setup with deep links to repo settings pages.              |
| Developers            | Python docstrings         | Design decisions, trade-offs, "why" explanations.                       |
| Workflow maintainers  | YAML comments             | Brief "what" + pointer to Python code for "why."                        |
| Bug reporters         | `.github/ISSUE_TEMPLATE/` | Reproduction steps, version commands.                                   |
| Contributors / Claude | `claude.md`               | Conventions, policies, non-obvious rules.                               |

**YAML → Python distillation:** migrate lengthy "why" explanations from workflow YAML to Python module/class/constant docstrings (MyST admonitions like ```` ```{note} ````). Trim the YAML comment to a one-line "what" plus a pointer: `# See {package}/{module}.py for rationale.`

### Documenting code decisions

Document design decisions, trade-offs, and non-obvious choices in the code: MyST docstring admonitions (```` ```{warning} ````, ```` ```{note} ````, ```` ```{caution} ````), inline comments, and module-level docstrings for constants that need context.

### Pending work goes in a `todo` admonition

A statement about work not done yet (a shim waiting on an upstream release, a swap deferred until a library grows an API, an idea worth evaluating) belongs in a ```` ```{todo} ```` admonition, never a bare `# TODO` or `XXX` comment and never a loose sentence trailing a paragraph. `sphinx.ext.todo` collects every one of them onto a single `todolist` page, which is the difference between a project that knows what it owes and one where the answer is whatever a grep for four different spellings turns up.

- **Say the action and its trigger.** "Delete this module once [owner/repo#N](url) ships" tells a reader whether it is actionable today; "this could be simplified eventually" does not. Link the upstream ticket, since that ticket is usually what closes the item.
- **Split it out of the note describing current behavior**, rather than appending the plan to it. The `{note}` stays true for as long as the code does; the `{todo}` is the part that expires, and a reader deleting the shim should not have to unpick one paragraph into two.
- **Only what Sphinx renders reaches the page:** `docs/*.md` and any docstring `autodoc` covers. A `#` comment, a YAML comment and a TOML comment are invisible to it, and so is the docstring of a private member, which autodoc skips by default: a `{todo}` written in one reaches neither the page nor the todolist, so put it in the nearest docstring that renders (the public method or the module), and confirm on the built `todolist` page rather than trusting the inline render. Move the plan into the docstring that owns the concern and leave the config file a one-line `XXX` plus the ticket link. That split is also what the floor-comment rule wants (see [§ A floor comment justifies one version](#a-floor-comment-justifies-one-version)).
- **Retire it in the same change that retires the shim.** A todo outliving its trigger is worse than none: the page is published, so it advertises work already done.
- **File upstream, then record it in the same pass.** A report filed against a dependency belongs beside the workaround it explains, before the session moves on. Write what the fix would let the code drop, and say so accurately: a shim kept for two reasons loses only one of them, so the entry reads "re-scope" rather than "delete" unless the whole thing goes.

Enable the extension where it is missing (`sphinx.ext.todo` plus `todo_include_todos = True`), and give `docs/todolist.md` a toctree entry, or the items render nowhere. An incremental build does not re-read that page when a todo is added elsewhere, so a local `todolist` runs stale: touch `docs/todolist.md` or build with `--fresh-env` to re-collect. CI is immune, building from scratch.

### Example data

Example data everywhere (docs, docstrings, comments, workflows, fixtures) must be domain-neutral: cities, weather, fruits, animals, recipes. Do not reference the project, software engineering concepts, or package metadata. The reader should understand the example without knowing what the project is.

## File naming conventions

### Extensions: prefer long form

Use the longest, most explicit file extension. For YAML, `.yaml` (not `.yml`); likewise `.html` not `.htm`, `.jpeg` not `.jpg`.

### Filenames: lowercase

Use lowercase filenames everywhere. Avoid shouting-case names like `FUNDING.YML` or `README.MD`.

### GitHub exceptions

GitHub silently ignores certain files unless they use the exact name it expects. These are the known hard constraints where you **cannot** use `.yaml` or lowercase:

| File                     | Required name                       |
| ------------------------ | ----------------------------------- |
| Issue form templates     | `.github/ISSUE_TEMPLATE/*.yml`      |
| Issue template config    | `.github/ISSUE_TEMPLATE/config.yml` |
| Funding config           | `.github/funding.yml`               |
| Release notes config     | `.github/release.yml`               |
| Issue template directory | `.github/ISSUE_TEMPLATE/`           |
| Code owners              | `CODEOWNERS`                        |

Workflows (`.github/workflows/*.yaml`) and action metadata (`action.yaml`) support both `.yml` and `.yaml`: use `.yaml`.

## Code style

### Terminology and spelling

Use correct capitalization for proper nouns and trademarked names:

<!-- typos:off -->

- **PyPI** (not ~~PyPi~~): the Python Package Index, capitalized "I" for "Index". See [PyPI trademark guidelines](https://pypi.org/trademarks/).
- **GitHub** (not ~~Github~~)
- **GitHub Actions** (not ~~Github Actions~~ or ~~GitHub actions~~)
- **JavaScript** (not ~~Javascript~~)
- **TypeScript** (not ~~Typescript~~)
- **macOS** (not ~~MacOS~~ or ~~macos~~)
- **iOS** (not ~~IOS~~ or ~~ios~~)

<!-- typos:on -->

### Version formatting

The version string is always bare (`1.2.3`). The `v` prefix is a **tag namespace**: it only appears when the reference is to a git tag or something derived from one (action ref, comparison URL, commit message). This aligns with PEP 440, PyPI, and semver.

**Rules:**

1. **No `v` prefix on package versions.** Where the version identifies the *package* (PyPI, changelog heading, CLI output, `pyproject.toml`), use the bare version: `1.2.3`.
2. **`v` prefix on tag references.** Where the version identifies a *git tag* (comparison URLs, action refs, commit messages, PR titles), use `v1.2.3`.
3. **Always backtick-escape versions in prose.** Both `v1.2.3` and `1.2.3` are identifiers: wrap them in single backticks.
4. **Development versions** follow PEP 440: `1.2.3.dev0` with optional `+{short_sha}` local identifier.

### Commit messages

**Default to a subject line and nothing else.** Most hand-written commits carry no body at all: 93%, measured across `kdeldycke/repomatic`'s history. A commit message is a log entry, not a design document. It gives a quick summary of what the commit holds, and points at context that lives elsewhere.

- **Subject.** One line under 72 characters, imperative mood, capitalized, no trailing period, every identifier backticked. Name what you changed, not the category it falls in: `` Sync `uv.lock` ``, `Fix vulnerable dependencies`, `` Fix `sync-mailmap` crash on a missing file ``. This is the shape the automation already emits, since no PR template sets a `commit_message:` and each one's `title:` becomes the commit subject.
- **Avoid the bare one-word subject.** `Typo`, `Lint`, `Fix` and friends are common in the older history and are the habit to break, not a pattern to copy: they cost the next reader a `git show` to learn anything. Say what the typo was in, what the lint fixed.
- **No decorative prefixes.** This is not [Conventional Commits](https://www.conventionalcommits.org): no `feat:`, `chore:`, `fix:`. **A `[bracketed]` prefix is reserved for a load-bearing mechanism that parses it back**, never for decoration or categorization: before writing one, name the code that reads it. Never write a GitHub skip token (`[skip ci]` and its four aliases) in any message, including a body: they match anywhere and leave the required check "Pending" rather than failing. [`docs/commit-messages.md`](https://repomatic.net/commit-messages) inventories which tools read and write commit messages.
- **Body: three cases, and nothing else.** Omit the body by default, even when the *why* is not obvious from the diff. A body is not the place to explain the change, defend the approach, or restate what the diff already shows. Write one only when the commit meets one of these cases, and write no more than the case needs:
  - **It bundles orthogonal work.** The commit carries several unrelated tasks, or spans different domains, and one subject cannot name them all. Give one short line per strand.
  - **A public record holds the context.** Link it: the upstream issue or pull request, a review comment, a commit in another repository, the specification or documentation page that forced the behavior, the discussion thread. Point at the commit this reverts or follows up on the same way. Forges render commit messages as HTML, so the link is the cheapest route from `git log` to the full story. The body is that link plus at most one clause naming what it holds. Never summarize what the link says.
  - **It resolves or references a tracked item.** Use `Closes #N` when merging the commit into the default branch must close the issue, and `Related to #N` when it must not. Format every reference per [§ GitHub cross-references in commit messages and PRs](#github-cross-references-in-commit-messages-and-prs).
- **Hard cap: two lines, 25 words.** Cut to this ceiling rather than writing up to it: a body over it gets shortened, never reworded, per [§ Cut before rewriting](#cut-before-rewriting). A blank line never appears inside a body, so a two-paragraph body is always wrong. The bundled-work case is the one exception to the line count: it takes one line per strand, each line under 25 words. A body wanting more is holding something that belongs in the code, a docstring, `docs/`, or the pull request.

Never narrate the work in sequence, enumerate the files touched, or summarize the diff in prose: `git log --stat` lists the files and the diff shows the rest. A finding never goes in a commit body either: a version a probe reported, what a tool did when driven, a constant that turned out to be a comment rather than a variable. Those are content, and they belong in the file the commit writes, in a docstring, or in `docs/`. A finding that reaches only the git log is lost to every reader who never runs `git log`. Rationale goes to the same places, or to the pull request body.

### Pull request and issue bodies

**Hard cap: 150 words of prose.** The ceiling counts what you write. It does not count generated content or evidence, so a `pr-body` table, a checklist, a quoted log line, a reproducer, a code block and a list of links all sit outside it. A body wanting more prose belongs in a docs page or a file: write it there, and link it.

Everything the commit-body rules forbid is forbidden here too: no narration in sequence, no file inventory, no closing summary that restates the body above it, no "Testing" section repeating what the diff and CI already show. A reviewer opens a pull request to read the diff, and prose in front of it delays that. Evidence stays exempt because it is what the reader verifies: see [§ Upstream reports and comments](#upstream-reports-and-comments) for how to present it.

### GitHub cross-references in commit messages and PRs

Never write `#N` (a literal `#` followed by a number) in commit messages, PR titles, or PR bodies unless N is an actual issue/PR number in the target repo. GitHub auto-links every `#N`, so positional refs like `test #1` render as misleading cross-references. Use plain numbers (`test 1`, `tests 14 and 15`), backtick-quote a slot identifier (`` test `1` ``), or rephrase (`the first test`).

### Linking to external repositories in Markdown

In Markdown (changelog, `readme.md`, `docs/`, issue and PR bodies), link to another repository using GitHub's reference slug as the link text, not the raw URL:

- Issue or PR: `[owner/repo#N](https://github.com/owner/repo/issues/N)`. Issues and PRs share one number space; pick `/issues/N` or `/pull/N` to match the real type (GitHub redirects either way).
- Commit: `[owner/repo@shortsha](https://github.com/owner/repo/commit/fullsha)`.
- Repository homepage: `[owner/repo](https://github.com/owner/repo)`.

GitHub autolinks the bare `owner/repo#N` form only inside conversations (issues, PRs, commit messages), never in committed files, so the explicit link is what renders the compact slug in a Markdown file. Same-repo references drop the slug: `[#N](…/issues/N)`.

### Comments and docstrings

- All comments in Python files must end with a period.
- **A comment describes how the code works now, not how it used to work.** A refactor replaces the old behavior. The story of why it changed belongs in the commit message, not in a comment beside the new code.
- **A comment stands alone.** The reader never saw the session that wrote it: no phase numbers, no design-doc section references, no narration of the path taken ("first we tried X"), no note about what the code is not ("this is the deployment manual, not the README"). That context belongs in the commit message or the ticket.
- **A comment explains what the code does not say.** The code shows what it does; a comment earns its place by saying why. Do not justify every change: a block narrating the diff belongs in the commit message.
- Docstrings use MyST markdown (single-backtick inline code, `[text](url)` links, `` {role}`target` `` cross-references, ```` ```{directive} ```` admonitions); `click_extra.sphinx.myst_docstrings` converts to reST at build time. For Sphinx operational detail (fence style, `click-extra convert-to-myst`, page rosters, `conf.py` hygiene), see `.claude/agents/sphinx-docs.md`.
- **No Google-style docstring sections** (`Args:`, `Returns:`, `Raises:`, …; no `sphinx.ext.napoleon`). Use reST field lists: `:param name:`, `:return:` (not `:returns:`), `:raises ExceptionType:`. Markers pass through unchanged; their content is MyST-converted, and continuation lines indent to align with the description above.
- **Dataclass field docs:** attribute docstrings (a string literal immediately after the field), not `:param:` entries; the class docstring is for the class purpose only.
- **CLI help text:** Click renders docstrings as plain text in `--help`, so avoid MyST markup in Click command docstrings.
- Documentation in `./docs/` uses MyST markdown where possible.
- Keep Python lines within 88 characters (ruff default). Markdown has no line-length limit: do not hard-wrap prose.
- Titles in markdown use sentence case.
- **Heading anchors:** use the natural auto-generated anchor for cross-references; add explicit MyST anchors (`(my-anchor)=`) only when the natural one is unavailable (duplicate headings, non-heading targets).

### `__init__.py` files

Keep `__init__.py` minimal (easy to overlook): no logic, constants, or re-exports. Acceptable: license headers, package docstrings, `from __future__ import annotations`, `__version__`. Anything else belongs in a named module.

### Imports

- Import from the root package (`from {package} import cli`), not submodules, when possible.
- Imports go at the top of the file unless avoiding circular imports. **Never use local imports inside functions**: they hide dependencies and bypass ruff's import sorting.
- **Version-dependent imports** (like a `tomllib` fallback for Python 3.10) go after all normal imports but before the `TYPE_CHECKING` block, so ruff can sort the normal imports above.

### `TYPE_CHECKING` block

Place a module-level `TYPE_CHECKING` block after all imports (including version-dependent ones). Use `TYPE_CHECKING = False` (not `from typing import TYPE_CHECKING`) to avoid importing `typing` at runtime. **Only add it when there is a corresponding `if TYPE_CHECKING:` block**: a bare assignment with no consumer is dead code, so if all type-checking imports are removed, remove the assignment too.

### Modern `typing` practices

Use `collections.abc` and built-in types instead of `typing` imports; `X | Y` not `Union`, `X | None` not `Optional`. New modules include `from __future__ import annotations` ([PEP 563](https://peps.python.org/pep-0563/)).

### Minimal inline type annotations

Omit annotations on locals, loop variables, and assignments when mypy can infer from the right-hand side. Add one only when mypy errors (empty collections needing an element type like `items: list[Package] = []`, ambiguous `None` init, unions mypy can't narrow). Always annotate function parameters and return types.

### Python 3.10 compatibility

Project supports Python 3.10+. Unavailable syntax: multi-line f-string expressions (3.12+; split into concatenated strings), exception groups / `except*` (3.11+), `Self` type hint (3.11+; use `from typing_extensions import Self`).

### YAML workflows

Single-line commands: plain inline `run:`. Multi-line: the folded block scalar (`>`), which joins lines with spaces (no backslash continuations); use the literal scalar (`|`) only when preserved newlines are required (multi-statement scripts, heredocs).

YAML lines may run to 120 characters (`yamllint.yaml` sets `line-length: max: 120`): don't carry over Python's 88-char limit. The same limit governs generated downstream workflows, so codegen-source comments (like `release.yaml`'s `publish-pypi` job) should fill to 120 too.

Jobs run on a test-matrix runner (`ubuntu-26.04` for the x86 default), and downstream workflows inherit it. Never reach for a `-latest` alias: GitHub repoints those without a commit to review, and `lint-repo` warns about them.

### Ordering conventions

Keep definitions sorted for readability and to minimize merge conflicts:

- **Workflow jobs**: by execution dependency (upstream jobs first), then alphabetically within the same level.
- **Python module-level constants**: alphabetically, unless a logical or dependency order applies. Place hard-coded domain constants (like `NOT_ON_PYPI_ADMONITION`, `SKIP_BRANCHES`) at the top, right after imports: they encode domain assertions, so surfacing them early shows the module's assumptions.
- **YAML configuration keys**: alphabetically within each mapping level.
- **Documentation lists and tables**: alphabetically, unless a logical order (like chronological in changelog) takes precedence.

### Named constants

Do not inline named constants during refactors: a named, documented constant exists for readability and grep-ability. When moving code between modules, carry the constant with it, don't replace it with a literal.

### Single source of truth for defaults

Every configurable default lives in exactly one place: the canonical config dataclass field default. All code derives it from the source (class-level default for static contexts, instance value at runtime) rather than repeating the literal across registry entries, CLI option fallbacks, parameter defaults, or module-level paths. When adding a default, grep for the literal and point any other occurrence at the source.

## Testing guidelines

- Use `@pytest.mark.parametrize` for the same logic over multiple inputs, rather than copy-pasted test functions differing only in data.
- Keep test logic simple with straightforward asserts.
- Sort tests logically and alphabetically where applicable.
- No classes for grouping tests; write top-level functions. Use a class only for shared fixtures, setup/teardown, or class-level state.
- **`@pytest.mark.once` for run-once tests.** A custom `once` marker (in `[tool.pytest].markers`) tags tests that run once, not across the full matrix (CLI invocability, plugin registration, metadata checks). The main matrix filters with `pytest -m "not once"`; a dedicated `once-tests` job runs them on one runner. The admission test is coverage, not just OS-independence: the floor-holding matrix run filters `once` out, so a test moved there takes its package coverage with it — verify `report.fail_under` still clears, and keep a test on the matrix when it meaningfully covers package code.
- **CI-only pytest flags belong in workflow steps, not `[tool.pytest].addopts`.** `--cov-report=xml` produces a CI-only artifact and pollutes local runs if in `addopts`. Keep `addopts` for everywhere-flags (`--cov`, `--cov-report=term`, `--durations`, `--numprocesses`); pass CI-specific flags in the workflow `run:` step.
- **Coverage configuration belongs in `[tool.coverage]`** (`run.branch`, `run.source`, `report.precision`, `report.fail_under`), not `--cov-branch` in `addopts`. `addopts` carries only `--cov` and `--cov-report=term`. This holds for the coverage floor too, even though it is the one setting a workflow could plausibly carry: `--cov-fail-under` on the command line **outranks** `report.fail_under`, so passing it from CI would silently shadow the native knob a project sets. Never add a `[tool.repomatic]` key for it either, for the same reason. The floor is written for the full suite, so the two runs that do not clear it opt out explicitly with `--cov-fail-under=0`: the `once-tests` job (~22% on its own), and a focused local run, better served by `--no-cov`.
- **Write conformance tests when fixing a class of bugs.** For a bug that is a *category* (not a one-off), add a generic test locking in the invariant: iterate over every member of the set (registry entries, generators, exported symbols, data files) and assert the property uniformly via `@pytest.mark.parametrize` or a loop. Applies when the bug stems from a shared convention checkable from the codebase alone (no fixtures or mocks). Model: `tests/test_readme.py::test_docs_generator_matches_in_tree_state`. Shape: enumerate the population, assert on each, fail naming the violator. **Then prove it fails on the pre-fix state**, by running it against the old content rather than assuming: a conformance test written from the corrected text often only matches the corrected phrasing, so it passes on the very bug that motivated it and locks in nothing. When the invariant is genuinely narrower than the bug class (a rule keyed on one phrasing among several that state the same claim), keep the test and say so plainly, since a narrow guard is still worth having: what must not happen is reporting it as retroactive coverage it does not provide. **Revert one side only when the invariant is an agreement**, like a documented command against the argv the code builds: restoring the old code *and* the old documentation makes the two agree again, so the test passes and reads as a guard that catches nothing. Put back the code alone, which is the shape a real regression takes.
- **When a bug ships past a suite, open the test that claims to cover it.** A test can assert an outcome that two paths reach, and then it passes either way. One in `click-extra` prepended a subcommand from the configuration and also named that subcommand on the command line, so the assertion held whether or not the injection ran, and the feature stayed broken for every group class but one. Pick an expected output that the code path under test is the only way to reach: prepend `debug` and invoke `backup`, never prepend `backup` and invoke `backup`.
- **Pass `encoding="UTF-8"` to `subprocess.run(..., text=True)` when output may contain non-ASCII bytes** (emoji in workflow `name:`, accented names). `text=True` alone uses the platform default (`cp1252` on Windows), raising `UnicodeDecodeError` only in Windows CI. Test helpers shelling out to `git show`/`git cat-file` are the usual offenders; production `read_text`/`write_text` already set it.
- **Pass `encoding="UTF-8"` to every text-mode `open()`, `read_text()`, and `write_text()` in tests, same as production.** The same Windows cp1252 default applies to file I/O, and the failure hides until content grows a non-ASCII character. Ruff's `PLW1514` (in the shared config) flags `open()` and receivers its inference can type, but misses unannotated `Path` locals (`doc = tmp_path / "page.md"`); when a change touches file I/O, run the suite once with `PYTHONWARNDEFAULTENCODING=1` (PEP 597) to surface every bare call at runtime, on any platform.
- **Spell it `UTF-8`, never `utf-8`, in both of the above.** Python normalizes either, so the difference carries no meaning and a mixed codebase only makes a reader stop to work that out. `tests/test_suite_hygiene.py::test_encoding_argument_spelling_is_uniform` pins the suite to the one spelling; production holds it by convention, with no exception at present.
- **Never probe the environment at collection time.** A parametrize expectation computed at import — one that shells out, walks `PATH`, or stats the filesystem — is evaluated independently by every xdist worker, so a probe that can answer differently twice (a slow binary, a tool whose availability shifts mid-run, a file another test writes) leaves the workers holding different test lists and aborts the whole session with `Different tests were collected between gw0 and gw1`, naming no culprit. Wrap such an expectation in a callable the test resolves in its own body, and put any environment warm-up in a session-scoped fixture, which runs once collection has settled.
- **Seed environment-dependent global caches before the first test, from a session fixture.** click-extra's `runner` fixture pins `HOME` and its platform equivalents to an empty directory around each CLI invocation, so a module-global cache filled lazily *from inside* a test records what a home-less environment answered and serves that for the rest of the worker's session. `meta-package-manager` hit this the hard way: its manager pool cached a tool as unavailable because the probe that happened to run first went through a `$HOME`-dependent shim, and every later test on that worker saw the tool missing. An autouse session fixture touching the cache first, outside any runner, keeps that state honest — and is worth writing down where the cache lives, since the invariant is invisible at every call site.

## Agent conventions

### Source of truth hierarchy

`CLAUDE.md` defines the rules; the codebase and GitHub (issues, PRs, CI logs) are what you measure against them. When they disagree, fix the code to match; if the rules are wrong, fix `CLAUDE.md`.

### Common maintenance pitfalls

Patterns that recur across sessions, to watch for proactively:

- **Documentation drift** is the most frequent issue: version references and workflow job descriptions in `docs/` go stale after every release or refactor, so verify docs against actual output.
- **CI debugging starts from the URL.** When a workflow fails, fetch the run logs first (`gh run view --log-failed`), don't guess; when the user points to a specific failure, diagnose that exact one.
- **A green run can be stale rather than clean.** The newest conclusive run can sit behind cancelled runs that held the newest commits: diff the gap (`git log --oneline {headSha}..HEAD`) before you trust it. This direction costs more than a false red, because a false green ships the break.
- **A local green is not the CI result.** Once `git log origin/<branch>..HEAD` shows a session commit reached the remote, read its runs by SHA before the next report: a signal-timing test, another OS or a dependency-branch cell fails only there.
- **A test that flips with no code change is an environment diff, not a code one.** Compare what is installed against what the lockfile pins before you read the diff. A lock bump still waiting in an open sync pull request marks when CI inherits the same break. `uv sync --group X` sets the group list rather than adding to it, and a plain `uv sync --frozen` afterwards removes the rest: restore with `uv sync --frozen --all-groups`, or overlay one missing tool with `uv run --frozen --with '{pkg}=={X.Y.Z}'`. A tool in no group resolves from `PATH`, so check which binary answered.
- **A proof against old code needs the old code on `sys.path`.** `python -m {package}` puts the current directory first, so a child started from the main checkout imports the fixed package even under `uv run --project {worktree}`: add `--directory {worktree}`, or give the child a neutral `cwd`.
- **A slow job is not a hung one, and elapsed time alone cannot tell them apart.** For CI, compare against the workflow's recent successful runs and their per-job `completedAt` times: a flat count of in-progress jobs is no evidence of a stall. For a local process, walk to the leaf of the process tree (`ps -axo pid,ppid,stat,wchan,etime,command`), name what it waits on, read its consumed CPU twice (`utime+stime`, fields 14 and 15 of `/proc/<pid>/stat`), and list its open descriptors to see which file it is working on. A steady PID, a rising highest PID or a non-zero load average proves nothing, since any work on the machine produces them.
- **Probe the probe once by hand before you trust a watch built on it.** `kill -0` returns EPERM across a privilege boundary, so watch a root process with `ps -p`. A sandbox that denies `ps` makes it print nothing, which a watch reads as "finished". A count of findings needs a pattern that matches the command's real output: the shell's `diff` alias prints `-` and `+` lines, `command diff` prints `<` and `>`. Never poll a package manager's own query for progress: it blocks on the lock the transaction holds.
- **An exit code of 0 is not proof of effect.** Read the target back after any edit that matters: `sudo` over a non-interactive SSH session, `chpasswd` inside a `chroot`, and a pipeline that a broken heredoc never ran can all report success and change nothing. `$?` after a pipeline reports its last stage, so capture `${PIPESTATUS[0]}` in bash or `${pipestatus[1]}` in zsh. A background job's completion notice can report exit code 0 for a script that crashed: read its output file. Print what a probe said rather than a pass/fail verdict, and space out probes that a remote service may rate-limit.
- **Confirm the machine before debugging its behaviour.** A moved DHCP lease or a stale ARP entry can put another guest on the expected address: check the SSH host key or the version banner first. Disabling `StrictHostKeyChecking` removes exactly this check, so re-enable it for a host that misbehaves.
- **A regex that stops at whitespace mis-parses paths on macOS.** `Mobile Documents`, `Application Support` and most Library paths contain spaces, so a pattern like `file\.filename=([^ ,]+)` truncates mid-path and its match then fails.
- **Take a literal from the file, never from the screen.** Tool output can show one character as another (a `/` read as `-`), so do an exact replacement in Python against text read from disk, or anchor the match on text with no ambiguous character. Where one character must be checked, print a control beside it.
- **An escape typed into an edit tool arrives decoded.** Tool parameters are JSON, so `\u00a0` written into Python source through the Edit tool arrives as a literal non-breaking space, invisible in any diff. Spell its backslash as `\u005c`, since a doubled backslash arrives doubled, or insert the escape from a script, then scan the file for the raw character before committing. Literal blank look-alikes flatten the same way: an nbsp, braille blank or figure space typed into a `write` or `bash` parameter arrived as U+0020. Build such characters with `chr()` and prove the bytes with `hexdump` before trusting the artifact.
- **Type-checking divergence.** Code that passes `mypy` locally may fail in CI under `--python-version 3.10`; always check the minimum supported version.
- **Trace to root cause before coding a fix.** Audit a bug's scope before writing the patch. If the same pattern appears in multiple places, fix it at the shared layer; if only one call site is affected, check whether the data is on the wrong code path before handling it where it lands.
- **Three failed fix attempts end the loop.** After three turns of "still broken", stop editing code: name the assumption the diagnosis rests on, ask one diagnostic question, and wait. Patching a wrong diagnosis repeatedly is the failure mode, not slowness.
- **Simplify before adding.** Check whether existing code or a tool already covers the case, and remove dead code and unused abstractions before you add new ones. Look first in the dependency that owns the domain: `extra-platforms` for any platform, architecture, shell or terminal fact, `click-extra` for any CLI plumbing. A primitive the consumer lacks belongs upstream, as edits in the sibling checkout, not in the consumer.
- **A recorded decision is evidence, not a stop sign.** A note saying something was "assessed and rejected" describes the code as it stood when someone wrote it. Before you decline a change on its strength, check its scope against today's code, split the verdict where the two drifted, and rewrite the note to the rule the code now follows. A verdict from earlier in the same session gets no more trust: name the extension point you looked for and what it lacked.
- **Date a behavior by the commit that added it, never by the release note that announced it.** `git tag --contains {sha} | sort -V | head -1` names the first release that carried it, which decides whether a version floor has to move.
- **Angle-bracket placeholders in bash code blocks.** `mdformat-shfmt` runs `shfmt` on fenced ```` ```bash ``` ```` blocks, and `shfmt` parses `<foo>`/`>foo` as redirection and reorders the command. Use curly braces (`{foo}`) for placeholders in bash examples.
- **`pyproject-fmt` and `mdformat` write the same TOML two ways.** `pyproject-fmt` spaces and sorts an inline array in `pyproject.toml`; `mdformat` writes it unspaced in a fenced ```` ```toml ```` block. Let each formatter settle its own file, and never reconcile the difference by hand.
- **Route through existing infrastructure, don't bypass it.** Before writing a new helper or merge function, check whether the codebase already handles the operation. A bug from data on the wrong code path is better fixed by routing it correctly than by duplicating logic at the wrong site: move a misrouted file to the right registry rather than special-casing it at the call site.
- **A generator that writes a checked-in Markdown or JSON file competes with its formatter.** After you touch one, run the generator, the formatter, then the generator again, and confirm `git diff` stays empty across all three states. For JSON, read the indent from the target repository's Biome config: a hardcoded one fights `format-json` forever.
- **Verify formatting by running `repomatic run {tool}` in write mode, then reading `git diff`.** `--check` skips the Python post-process that some tools get (like `mdformat`), write mode prints nothing even when it fixed a file, and a hand-built `uvx` call misses the bundled config in `repomatic/data/`.
- **A generated artifact's prose has one owner layer: find it before rewriting.** A PR body, issue or docs page mixes code-generated parts (tables, computed rows) with static template text. Hand-editing a code-generated part is lost on the next run, and rewording prose by changing code edits the wrong layer. Find the template or string constant that owns the words first, and leave the rest alone.
- **Anchor a scripted edit on its target member, never on the first match in the file.** The same docstring prefix recurs across members: locate the `def {name}` line, search forward from there, and assert something unique to the target block before writing.
- **Grep for pinned phrases before rewriting text that has tests.** A suite may assert exact strings from the file being edited: a heading, an opening word, a checklist step. A rewrite that keeps the meaning can still fail it. Grep the tests and callers for distinctive phrases before editing; keep what they pin, or update the assertions in the same change.
- **A grep context window is not evidence of drift.** `-A`/`-B` can cut the governing clause mid-sentence, and the cut text then reads as a stale claim. Read the full block before you report text as outdated, and again before you edit it.
- **Claude Code behavior claims rot between releases.** Record the version and date a claim was verified against, and re-check it before you trust it: grep the installed binary (under `~/.local/share/claude/versions/` here), then run a live probe. The docs and the binary disagree regularly; the binary and the probe win.
- **Give a best-effort handler a log before debugging it.** An exit hook or shutdown callback that swallows its failures cannot tell "never fired" from "fired and gave up at step N". Add a small capped log line at every silent exit point, then run one cheap probe per fact.
- **`pi --help` cannot validate an extension edit** (pi `0.99.1`, 2026-10-01): it exits 0 on a file that does not parse. Probe the compile with `node --experimental-strip-types -e "import('{absolute path}.ts')"`, safe only when the extension's side effects all sit inside its default-exported factory, and only when it imports nothing but types from a pi package: those resolve inside pi's loader alone. That checks syntax and load, not types: read the option and context shapes off the `.d.ts` files under the pi install. Exercise a handler that fires on one exit path only, like `session_shutdown` with reason `quit`, once, and read its log. Exercise a tool handler with no model and no network: a probe extension that registers `fauxProvider()` from `@earendil-works/pi-ai` replays scripted tool calls, with `PI_CODING_AGENT_DIR` on a scratch directory, `PI_OFFLINE=1` and `--mode json` to read each `tool_execution_end`. A built-in extension is named `builtin:{name}`, and `--no-extensions` disables the built-ins too: a probe that needs one adds `--extension builtin:{name}`.

### Agent behavior policy

- **Never post to the web without explicit approval.** Do not create or comment on GitHub issues, PRs, or discussions, or post to any external service, without the user's explicit go-ahead. If approval is blocking, draft the content in a temporary markdown file for review.
- **A draft opens in the local editor, always.** Every issue body, pull request body, review reply and upstream comment written for approval is opened in the running VS Code instance as soon as it is written, never handed over as a path in a message: prose read in a terminal transcript is exactly what drafting to a file exists to avoid. The launch command is in [§ Local environment](#local-environment), because the `code` CLI reports success without opening anything under the sandbox.
- **Never use a browser Claude hosts.** The built-in browser pane is out, in this agent and in every agent I run. That covers every task: opening a page, reading a document, checking a link, filling a form. It is handy, and it carries none of the configuration I depend on. It has no content blocking, no cookie policy, no fingerprinting protection, no proxy or exit choice, and no separation between the identities I keep apart. Drive a browser installed on the system instead, listed in [§ Local environment](#local-environment). An extension driving an installed browser is a different case, because that profile and its settings are mine. Where a task needs a browser and no installed one can do it, say so and stop.
- Agents make fixes in the working tree only: never commit, push, or create PRs. Exception: skills that run autonomously (`/babysit-ci`, `/repomatic-ship`) may commit and push, and include a `Co-Authored-By` trailer by default; a maintainer's explicit standing rule against AI attribution overrides that default, since the trailer lands in their repository's permanent history. Follow the skill's instructions when they override this rule.
- **Land an upstream proposal as working-tree edits in the sibling checkout, not as prose.** When work in a downstream repo surfaces a bug or rough edge that belongs to `repomatic`, and a sibling checkout exists at `../repomatic`, implement the change there directly: edit the code, update the tests it breaks, and verify it. Then stop, leaving every change uncommitted and unpushed. A described fix costs the maintainer the whole implementation; a diff sitting in the tree costs them a review, which is the step they were always going to do themselves. This does not relax the rule above: no commit, no push, no PR, no issue. Confine the edits to what the finding justifies, and say plainly which files were touched and what verification was run.
- Prefer mechanical enforcement (tests, autofix jobs, lint checks) over prose rules. If a rule can be checked by code, it should be.

### Skills

A skill is a plain folder of static files, copied verbatim to wherever it runs, with optional `scripts/`, `references/` and `assets/` subdirectories: nothing renders it or varies it per destination. Its frontmatter carries [Agent Skills spec](https://agentskills.io/specification) fields plus `argument-hint`, and no other Claude Code extension: no `model:` (a recommended model goes in the spec's `compatibility` field) and no `disable-model-invocation:`, so every skill stays model-invocable and the permission layer decides what it may do. Keep a skill self-contained: its domain knowledge sits inline or in its own `references/`, never behind a `docs/` page or a web fetch. A cross-reference to another skill must degrade to a no-op when the target is missing, and a programmatic `Skill` call falls back to a subagent or inline work.

## Design principles

### Philosophy

1. Create something that works (to provide business value).
2. Create something that's beautiful (to lower maintenance costs).
3. Work on performance.

### Linting and formatting

[Linting](https://repomatic.net/workflows#github-workflows-lint-yaml-jobs) and [formatting](https://repomatic.net/workflows#github-workflows-autofix-yaml-jobs) are automated via GitHub workflows.

### Keep logic in Python, not workflow YAML

Push anything beyond trivial wiring out of workflow YAML into the CLI/library. Rather than duplicating `if:` conditions across steps, compute them once in `repomatic show-metadata` and reference the result. Rather than hand-maintaining workflow content, generate it in Python (see `repomatic.github.workflow_sync` for the rationale and the `publish-pypi` example): a tested generator that fails loudly beats a static artifact that can silently drift.

### Defensive workflow design

GitHub Actions workflows face race conditions, eventual consistency, and partial failures. Prefer **belt-and-suspenders**: multiple independent correctness mechanisms over a single guarantee. If a job depends on external state (tags, published packages, API availability), add a fallback or graceful default and make operations [idempotent](#idempotency-by-default) so re-runs are safe.

**Non-interactive third-party tooling.** When a tool prompts interactively (path selection, asset selection), pre-create its config files and resolve inputs via `gh` or another CLI rather than piping stdin: stdin redirection is fragile across platforms and fails outright on Windows ("Incorrect function"). Where a tool has no non-interactive mode at all, fetch the artifact it would install and verify that directly.

**Advisory findings never fail a scheduled audit job.** A scheduled audit separates advisory findings from gating checks: opportunities and upstream changes are reported into `$GITHUB_STEP_SUMMARY` while the job stays green, and only drift against pinned or committed state fails it — a red run for an advisory finding teaches people to ignore that workflow's red runs, which then hides real failures. A batch job accumulates a per-item row in the summary and exits non-zero once at the end, rather than aborting on the first failure.

**A degraded publish still ends red.** When a job drops part of its output so the rest can publish (a file over a host's size limit, a page that fails to render), publish first, then fail the job: a green run with a warning hides a dead link in production.

### Idempotency by default

Workflows and CLI commands must be safe to re-run: the same command twice with the same inputs produces the same result, with no errant side effects (duplicate tags or PR comments, redundant file writes). Use `--skip-existing` or equivalent guards when creating resources; check for existing state before writing (skip an admonition already present, skip a PR that already exists for the branch); prefer upsert over create-only; make file-modifying operations convergent (re-applying is a no-op).

**When idempotency is not achievable**, document in a comment or docstring what side effects occur on re-runs and why they are acceptable.

### Skip and move forward, don't rewrite history

When a release goes wrong (squash merge, broken artifact, bad metadata), prefer **skipping the version and releasing the next one** over reverting, force-pushing, or rewriting `main`: a burned version number is cheap, a botched automated recovery is not (this mirrors PyPI's [yank](https://peps.python.org/pep-0592/) model). When designing new safeguards, default to **detection + notification** over **detection + automated fix**: the blast radius of a missed notification is zero; that of a bad automated fix can be catastrophic.

A release that published without some of its binaries is the same case, because publishing locks the asset list: never hold a release or sit on a draft waiting for a red build cell. Fix the cause and let the next version carry it; the `repomatic-ship` skill (§ Repairing a short ship) repairs the notes that still advertise the missing binaries.

### Command-line options

Always prefer long-form options over short-form for readability in workflow files and scripts (`--output` not `-o`, `--verbose` not `-v`). The same rule applies to every argv the program builds at runtime (subprocess invocations included): long forms make logged command disclosures self-documenting.

### CLI commands that accept a `--lockfile` or similar path

A CLI command taking a project-file path (`--lockfile path/to/uv.lock`) must run any context-needing subprocess (`uv lock`, `uv audit`) with `cwd=path.parent`, else it resolves against the caller's directory, not the target project.

### CLI output conventions

CLI commands that produce structured output should separate terminal display from file output:

- **Terminal:** use `ctx.find_root().print_table(rows, headers)`, which respects the global `--table-format` option (github, json, csv, etc.).
- **File output (`--output`):** write markdown for PR bodies and CI; use `--output-format` for transport encoding (like `github-actions`, which spills the report to a file and emits `<key>_file=<path>` for `$GITHUB_OUTPUT`), not implicit env-var detection. A report has no ceiling of its own, so it travels as a path rather than inline: only bounded values still get the heredoc form.
- **Boolean feature flags** (like `--release-notes`) should use the `--flag/--no-flag` pattern so both directions are explicitly invocable from workflows.

### Prefer `uv` over `pip` in documentation

Documentation and install pages must use `uv` as the default installer (`uv tool install` for CLI tools, `uv pip install` for libraries/extras). Other installers may appear as secondary options, but `uv` must be primary.

### uv flags in CI workflows

When invoking `uv` and `uvx` commands in GitHub Actions workflows:

- **`--no-progress`** on all CI commands (uv-level flag, before the subcommand): progress bars render poorly in CI logs.
- **`--frozen`** on `uv run` commands (run-level flag, after `run`): the lockfile should be immutable in CI.
- **Flag placement:** `uv --no-progress run --frozen -- command` (not `uv run --no-progress`).
- **Exceptions:** omit `--frozen` for `uvx` with pinned versions, `uv tool install`, CLI invocability tests, and local examples.
- **Prefer explicit flags over environment variables** (`UV_NO_PROGRESS`, `UV_FROZEN`): self-documenting, visible in logs, and free of conflicts (like `UV_FROZEN` vs `--locked`). The cooldown is the deliberate exception, and only the cooldown: `UV_EXCLUDE_NEWER` is set workflow-wide so it reaches commands nobody flagged, per [§ Cooldown on every install](#cooldown-on-every-install).
- **Per-group `requires-python` in `[tool.uv]`:** a group needing newer Python can be restricted with `dependency-groups.docs = { requires-python = ">= 3.14" }`, so uv won't install incompatible dependencies on older Python.

### Pin uv with `required-version`

Downstream Python repos floor uv in `[tool.uv]` with a lower-bound `required-version` (like `required-version = ">=0.11.15"`), not an upper-capped range, so contributors and downstream repos are never capped and local development moves forward without a manual ceiling bump each minor.

**CI pins the exact uv separately.** `required-version` is a floor for everyone; what a runner downloads is a different question, and left to `setup-uv` the answer is "the newest release satisfying the floor", installed seconds after it lands. That makes the tool enforcing every cooldown the one tool without one. So every `astral-sh/setup-uv` step carries `with: version: "X.Y.Z"`, and `sync-workflow-pins` walks it forward once a uv release clears [`minimum-release-age`](#cooldown-on-every-install), like any other pinned literal. The pin is not a cap: it never co-resolves with anything, and CI still moves forward on its own, just a window behind. Skip a hard upper cap (`<0.13`): uv self-updates on many machines, so a cap breaks every contributor and runner the day the next minor lands, and `required-version` is a self-gate that never co-resolves with the project's dependencies (the usual reason to cap a dependency does not apply).

## Scope and precedence

These are my personal rules and my generic coding conventions, loaded on every project I open from this machine. A repository's own instructions file carries only what is specific to that project, and wins for that project where the two disagree; this file speaks for me everywhere else. The generic conventions used to sync from `kdeldycke/repomatic` into every consuming repo; since 2026-08-20 they live here instead, because this file loads machine-wide and the per-repo copies only ever duplicated them.

The boundary is one-way. Nothing personal here belongs in a project's instructions file: "push to `main` rather than a scratch branch" assumes admin rights on the remote, "use first-person singular" assumes a solo author, and the commit-authorization rule describes my review habits rather than a project's contribution policy.

The conventions for building `repomatic` itself live in that repository, beside what they govern: `~/code/repomatic/claude.md` holds operation naming and contracts and the rules for bundled agents and skills, and each module, test and workflow states its own rules in its docstring or comments. Read them before adding a job, a CLI command or a bundled asset to any repository.

## Writing: ASD-STE100 Simplified Technical English

Write all human-readable prose in ASD-STE100 Simplified Technical English (STE). This binds every text artifact an agent produces: documentation, readme files, code comments and docstrings, changelog entries, commit messages, PR titles and bodies, issue reports and comments, error and exception messages, log messages, and the answers rendered to the user within a session.

Core rules:

- **One idea per sentence.** Keep sentences short: 20 words maximum for descriptions, 25 for instructions. Split long sentences rather than chaining clauses.
- **Use approved words, in one meaning each.** Prefer the plain word from the STE dictionary over a synonym: "use" not "utilize", "help" not "facilitate", "start" not "initiate", "also" not "additionally". When several words fit, pick the most common one. A word keeps one meaning per text: do not reuse "run" for both executing code and a CI run in one passage if it can confuse.
- **Active voice, present tense.** Say who does what: "the job writes the file", not "the file is written by the job". Use past tense only for events that already happened.
- **No nominalizations.** Use the verb: "decide" not "make a decision", "configure" not "perform the configuration".
- **Short, simple noun phrases.** Break "the version of the package published to the registry" into steps or a list if it grows.
- **Use vertical lists for procedures and multi-item rules**, one step or item per line, starting with a verb for procedures.
- **Put form values in a table.** When the reader fills in a form, list its fields in a two-column table: one row per field, named with the form's own label.
- **Number only what runs in order.** A condition that replaces a step goes first, inside the step it replaces.
- **Check each claim against what it describes.** Read the command, the API or the form before stating its scope or effect.
- **Be explicit, not clever.** Cut idioms, metaphors, humor, rhetorical flourishes and rhetorical questions. State the fact, the reason, and the action directly.
- **Caveats are inline, not closing footers.** State a caveat where it is relevant, without preamble, and do not save it for the end of the message.
- **Use "you" only for instructions.** Statements of fact need no actor; the "I/my" voice rule below still applies to prose written on behalf of the user.

Exempt from STE, verbatim only: error messages and log lines quoted from an existing source, code identifiers, command examples, file paths, third-party names and titles. Do not paraphrase them into STE.

Where STE conflicts with another rule, the other rule wins for its own concerns (sentence-case headings, the colon-instead-of-em-dash rule, changelog length limits): STE governs word choice and sentence structure, not formatting. A quoted phrase or a proper name may keep its non-STE spelling.

### Cut before rewriting

A request to make text shorter or simpler asks for deletion first and paraphrase second. Cut the ideas a nearby structure already carries: a table, a linked page, a column of the same report. Then simplify what remains. A rewrite-only pass keeps every idea and changes only the words, so the text stays as long as before.

## Answer shape

The first line is the answer or the next action. A command, a path, or a snippet comes before any prose that explains it.

When work stays open, end with one concrete next step: "Next: run `uv run pytest tests/test_x.py` and paste the first failing line." A question the reader must answer counts as a next step.

One issue per answer. A second finding waits until the first is closed, then surfaces as a separate offer: "Separately: X. Want me to handle that next?" A question that arises mid-work is not a tangent: answer it in place and fold the result in.

State errors as cause and fix, with no alarm: "Test fails at `tests/test_x.py:42`: expected 200, got 401. Cause: missing auth header. Fix: add the header."

Restate position, not history: "Step 3 of 5 done, next is the backfill" carries where we are without recapping what was done.

Before sending, check: a reader who sees only the first line and the last line knows what to do next and what just happened. Delete a first sentence that announces the work, a last sentence that offers more, and any "by the way" sidebar. Keep a hedge only when it carries real uncertainty: deleting one manufactures confidence.

## Voice and punctuation

Use first-person singular ("I", "my") in all prose written on behalf of the user: issue descriptions, PR bodies, feature requests, comments, documentation. Never use first-person plural ("we", "our") unless the text genuinely refers to a group.

Use ":" instead of em dashes for inline elaboration or appositive clauses. That substitutes for the dash. It does not license joining clauses: when the second half is a full thought, a full stop beats a colon and two sentences beat one compound. Reference prose in `docs/` needs this most, and a parenthetical list reads better promoted behind a colon than left in brackets. Keep bold for a whole labelled item, never for emphasis mid-sentence.

## Name every file and URL by its full address

Every file and every URL named in a message carries its complete address: `/Users/kde/code/repomatic/changelog.md`, never `changelog.md` or `scratchpad/draft.md`; `https://github.com/kdeldycke/repomatic/issues/42`, never "the issue above". A bare or relative path is not clickable, and a scratchpad path is unreachable without the session directory in front of it. This binds every message an agent emits, not the final answer alone: a clarifying question, a plan step, a finding, the reason given for a tool call, a draft offered for review. The `file_path:line_number` reference form keeps its line suffix, with the path spelled in full. Put the address in parentheses when it would otherwise break the sentence: "the changelog (`/Users/kde/code/repomatic/changelog.md`) gained one bullet".

### Copying an address off the screen

I select these by hand in a terminal:

- Put an address I am expected to paste alone on its own line: a triple-click takes the whole line in any terminal, where a double-click stops at `/` or `:`.
- Keep the `:line` suffix on a path: it costs the copy nothing.
- Never let punctuation touch the last character: end the sentence on the address, or leave a space before the mark.
- Write the bare URL, never `[label](url)`, when the point is to paste it: Claude Code (`2.1.236`) renders a markdown link as a terminal hyperlink that can leave only `label` on screen.
- Escape for one destination: single-quote a path holding a space or a shell character for a shell, and percent-encode a URL. Never apply both, never quote a path I am meant to read rather than run, and never hide a zero-width or other invisible character in either.

## Code organization

Do not make autonomous decisions about module boundaries, file placement, or architectural structure. When intent is ambiguous, ask before reorganizing. The user has strong opinions about where code lives and how modules are scoped.

A documentation outline is a structure too: before moving sections across a page, propose the target skeleton and get it approved first.

## Commits and PRs

Never run `git commit`, `git push`, `gh pr create`, or any other command that creates a commit, pushes to a remote, or opens a pull request unless I have explicitly authorized that specific action in the current conversation. Staging changes, drafting commit messages, and showing diffs are fine; the actual commit, push, or PR creation requires my explicit go-ahead each time. A prior authorization does not carry over to later actions.

**Check `git log origin/<branch>..HEAD` before rewriting any commit, and rewrite only what it lists.** A commit already on the remote is mine to rewrite, not yours, whatever the improvement on offer: re-signing an unsigned one, correcting a message, splitting a bundle. Report it and let me decide. I push mid-session without announcing it, so a commit you made minutes ago may already be upstream, and "I only just wrote it" is not evidence that it is local. The recovery, when you have already rewritten one, is `git reset --mixed origin/<branch>`, which restores my history and keeps your later work in the tree; never force-push to make the remote match instead.

`git commit --amend` rewrites `HEAD` and nothing else. Name the commit you mean and confirm `HEAD` is it, since an amend aimed at an older commit silently folds the current staged diff into the wrong message.

**A shared working tree holds another session's work: stage your own paths, never `git commit -a`.** I run sessions in parallel in one checkout, and a second one may commit or rewrite a file mid-task, so re-read `HEAD` before staging instead of trusting an earlier `git status`. Where its edits interleave with yours in one file, build the content you mean outside the tree and stage it as a blob (`git hash-object -w`, then `git update-index --cacheinfo 100644,<sha>,<path>`), which never rewrites a file the other session is still writing. Reconstruct "HEAD plus mine" by inverting its edits where they are mechanically identifiable, and prove the result by diffing against `HEAD` for text you never touched. To regenerate a derived artifact from that reconstruction, export `git archive HEAD` to a scratch directory and run the generator under `uv run --project <scratch>`; swapping files in the shared tree instead races the other session. Its pending copy of a file you both edit can still revert your line after you commit, so re-read your own hunks in the working tree once the commit lands. To push your work while its commits sit unpushed on the branch, build yours on `origin/<branch>` with a temporary index (`GIT_INDEX_FILE=<scratch> git read-tree origin/<branch>`, then `update-index` and `write-tree`), create it with `git commit-tree -S`, and push `<sha>:refs/heads/<branch>`. Without `-S`, `commit-tree` ignores `commit.gpgsign` and writes an unsigned commit. Keep a file meant only for such a commit outside the tree: an untracked copy of a path the remote now tracks blocks the other session's next pull. A session can also commit work it did not write: twice here an uncommitted edit of mine rode into the other session's commit and reached the remote under its message, so an uncommitted strand in this checkout is a strand offered to whoever commits next; commit promptly, or rebuild yours as a blob once the absorption surfaces. Never `git stash` here to compare an older commit. The push removes your paths from the tree the other session reads, and a `git status` after the pop can show its commit instead of your pop, which reads as lost work. Add a throwaway `git worktree` at the SHA instead, and run the tool with `uv run --project <worktree>`: your tree never changes.

Never include AI attribution in commits or PRs. No `Co-Authored-By` lines, no "Generated with Claude Code", no mention of being an AI or which model produced the code. Do not reference model names, versions, or codenames in commit messages, PR titles, or PR bodies.

Two instruction sources mandate such a trailer, and neither one overrides this rule. The Claude Code harness prompt asks every commit message to end with a `Claude-Session:` link to the session URL. The `/repomatic-ship` skill asks its commits to carry `Co-Authored-By: Claude <noreply@anthropic.com>`, and states that the mandate beats any no-AI-attribution rule in a project or global instructions file. Drop both trailers, and do not ask me each time. A session URL is attribution too, even where the instruction reads as a formatting step, which is how it gets through. Tell an agent you spawn to skip the trailer, because a spawned agent only reads the prompt you give it. Never amend or force-push to remove a trailer from a commit already pushed: report it and let me decide.

Write commit messages as a human developer would — describe what the code change does and why, not how it was produced. Keep internal tooling references (specific tools, Slack channels, internal links) out of public-facing text.

When a change needs a live CI run to validate it, push to `main` rather than to a scratch branch. My workflows key their concurrency group on `${{ github.workflow }}-${{ github.ref }}` with `cancel-in-progress`, so each push to the same ref cancels the previous run and hands its runners straight back. A side branch is a different ref: its run queues alongside `main`'s instead of superseding it, and both then crawl through a runner pool that is capped, most tightly on macOS.

The `#N` autolink hazard applies here in full: see [§ GitHub cross-references in commit messages and PRs](#github-cross-references-in-commit-messages-and-prs).

## Upstream reports and comments

When drafting a bug report, a reproducer write-up, or a reply on an upstream issue, the maintainer of that code is the authority on it. The job is to hand over observations they can verify in one click, not conclusions to agree with. Load the `file-bug-report` skill for any upstream report or reply: it carries the evidence rules, among them SHA-pinned permalinks, log-line anchors and a control beside every reproducer.

Never shop for a proxy submitter. Several distributions refuse a package submitted by the software's own author: where that rule applies, accept it, publish the verified templates, and say a distribution user is welcome to submit them as their own. Never ask a named contributor to re-file the work, and never offer to take maintainership back once it is merged.

## Shell commands

Permission rules deny `cd`, `rm`, `curl`, `wget`, `chmod`, `chown` and `sudo`. Claude Code enforces them itself, and pi through `~/.pi/agent/extensions/shell-deny.ts`, which reads the same list. A call that holds one of them fails whole, a compound command included, so never write one. Use `git -C` or an absolute path in place of `cd`. Use `git rm` or `git clean -f -- {path}` in place of `rm`, and `/usr/bin/trash` for a path outside a repository, which keeps it recoverable. Use WebFetch, `gh api` or a Python script in place of `curl`. Use `uv run --script` in place of `chmod +x`.

Never use `$()` command substitutions inside `gh` (or any other) Bash calls: the sandbox flags `$()` as a separate security check that fires regardless of permission allow rules. Run the inner command as its own Bash call first, then use its result in the next one, so both match the allow rules and auto-approve.

Never hand `git clean` a directory: name each path to delete. `git clean -f -- {dir}/` removes every untracked file there, including ones about to be committed, and bypasses the Trash.

Verify each path in a hand-built `rm` list before running it: the list comes from memory, and one mistyped absolute path destroys something recoverable. Print each candidate's identity (its content) first.

Never `cd` in Bash calls: pass absolute paths to the tool instead. Claude Code's `.claude/.cc-writes/` staging directory follows every `cd` and leaves an empty `.claude/` behind, and no setting disables it. For the same reason, launch `claude` from a repo root. Run `claude-sweep` to clear the strays.

`git mv` stages the rename only: read an `RM` status as "rename staged, content not", and `git add` the file before committing.

`git show {rev}:{path}` resolves `{path}` from the repository root, even under `git -C {subdir}`, where `git log -- {path}` resolves from the subdirectory. Its error, `fatal: path '{full path}' exists, but not '{path}'` with exit `128`, goes to stderr alone, so discarding stderr turns a wrong path into a silent no-match.

`sed -i ''` misbehaves in this harness: it applies the edits, then exits `2` with `can't read :`. Use Python for in-place multi-file rewrites.

The tool shell is zsh with `nomatch` on: quote every glob meant for the program (`--include='*.swift'`), every argument that starts with `=`, and every `gh api` path that holds a `?`. Otherwise zsh aborts the command before it runs: an unmatched glob dies with `no matches found`, and `echo ======` dies with `===== not found`, because zsh expands `=name` to the path of a command.

`ruff` falls back to the current directory's configuration when the target project defines none. Pass `--no-fix` to read findings without changing files, and compare before and after in one invocation: `git show HEAD:{path} | ruff check --no-fix --stdin-filename {path} -`, then the same command fed the working copy. A repository consuming repomatic with no `[tool.ruff]` of its own takes its CI baseline from `--config ~/code/repomatic/repomatic/data/ruff.toml`, run with the pinned `ruff`, not a system one.

Never run `ruff --fix --select RUF100` outside the project's full rule set: with only RUF100 selected, ruff judges every `# noqa` unused and strips the ones the code needs. Autofix it only under the project's own configuration, and diff the result before staging.

Read one file through the API with `gh api 'repos/{owner}/{repo}/contents/{path}?ref={tag}' -H "Accept: application/vnd.github.raw"`. To search an unfamiliar repository, fetch `gh api repos/{owner}/{repo}/tarball/{ref}` once and grep the extracted tree.

Read what ran on a commit with `gh api 'repos/{owner}/{repo}/actions/runs?head_sha={sha}'` and the full 40-character SHA, never with `gh run list`, which lists weeks-old runs first. The `babysit-ci` skill carries the details.

`gh search prs` and `gh search issues` truncate silently at `--limit`. Put every exclusion in the query after the `--` separator (`gh search prs --author {user} -- -user:{user}`) and every flag before it, raise `--limit` toward its 1000 ceiling, and treat a result count equal to the limit as truncated.

## Local environment

Non-obvious facts about this machine that have caused hard-to-diagnose failures:

- **Dotfiles are symlinked into `$HOME`, never hardlinked or copied.** `~/{path}` links to `~/code/dotfiles/dotfiles/{path}`, often through a linked parent directory, so a file created in the repository appears in `$HOME` at once: only a new top-level dotfile needs `./install.sh links`. Always edit the repository path: a replace-then-rename write through the `$HOME` path swaps the link for a regular file and forks the two copies.
- **`.zprofile` caches its `PATH` list for 7 days.** New shells read `~/.path-env-cache`, not `PATH_LIST`, so a new entry reaches them only at the next refresh. To apply one now, append the resolved path to the cache, or delete the cache and let a new shell rebuild it slowly. Edit the list in the repository's `.zprofile`, then seed the cache, never the other way. The list lives in `.zprofile` so that login shells that never read `.zshrc` (SwiftBar plugins, pnpm) get it too.
- **`packages.toml` never picks up newly installed packages on its own.** `install.sh` runs `mpm snapshot --update-version`, which refreshes only the entries already listed. After installing a tool worth keeping, add its line by hand, alphabetically, with a bare version.
- **A scratch project under `/tmp` fails every path-relative test.** The editable install records `/tmp/{dir}` while Python resolves the symlink to `/private/tmp/{dir}`, so `Path.relative_to` raises `ValueError: '/private/tmp/…' is not in the subpath of '/tmp/…'`. Spell the path `/private/tmp/{dir}` everywhere, and delete `.venv` before re-running: its finder keeps the old spelling, and `PYTHONPATH` cannot override an editable install.
- **Push to `gitlab.alpinelinux.org` with `~/.ssh/id_ed25519`, not the Secretive key.** The Secretive key is registered there as a signing key only, so a push with it connects as "Anonymous" and fails. The `Host gitlab.alpinelinux.org` block in `~/.ssh/config` forces the right key: leave it in place. For any GitLab push rejected as "Anonymous", check the key's usage type, the `IdentityAgent` override and `ControlMaster` multiplexing.
- **`git config diff.noprefix` is `true` here, and it leaks into generated artifacts.** A generated artifact that runs `git diff` must pass `--no-prefix` or `--default-prefix` instead of inheriting the config: verify by rebuilding with `GIT_CONFIG_GLOBAL` and `GIT_CONFIG_SYSTEM` pointed at an empty file. A patch from this machine's `git diff` needs `git apply -p0`: without it the apply fails with `does not exist in index`, which never mentions the prefix.
- **Claude Code transcript paths use the realpath'd cwd.** A session run from `/tmp/x` writes to `~/.claude/projects/-private-tmp-x/`, and print-mode sessions write a transcript too.
- **File discovery must use `-iname` on this machine.** APFS resolves paths case-insensitively, but `find -name` matches case-sensitively, and these repos store `claude.md` in lowercase. `ls`, `stat` and `readlink` run through shims that reject BSD flags, print nothing for a regular file, or draw a glyph before every entry: use Python for timestamps and link targets, and never grep `ls` output.
- **The `code` CLI reports success without opening anything.** Under the sandbox, `code {file}` exits 0 and the running VS Code never receives the file. Open editors with `open -a "Visual Studio Code" {file}` and the sandbox off, then confirm the app's PID.
- **Three browsers are installed, and Firefox is not.** Launch `open -a Chromium {url}` (the ungoogled-chromium build), `open -a "Tor Browser" {url}` or `open -a Safari {url}`, each with the sandbox off.
- **Never retry a signed commit that hangs.** Secretive `4.0.0` shows the Touch ID modal only while one request waits. A second request retracts the modal and moves both into the agent's Pending Requests window. That window opens behind the others or on another display, and no setting turns it off: [maxgoedjen/secretive#842](https://github.com/maxgoedjen/secretive/issues/842) tracks it. A client that gives up leaves its request in the queue. A retry then sends the next request to that window too. A Fork fetch queues there as well: hours-old `git-upload-pack` processes show it. Stop the hung commit with SIGTERM, which lets git remove `.git/index.lock`, then ask me to clear that window. After that, send one signed commit at a time and wait for each. For a batch, ask me to pick a duration in Secretive's "signed" notification: it keeps the key unlocked for 1 minute to 24 hours. An error ends its request, so one retry is safe after `Couldn't sign message (signer): agent refused operation?` or `communication with agent failed?`. Signing and `%G?` both work inside the sandbox (Claude Code `2.1.284`), which allows the Secretive socket and `~/.ssh/allowed_signers`: keep it on for `git commit`. Its network proxy still breaks an SSH `git push` (`ssh_dispatch_run_fatal: Connection to UNKNOWN port 65535: Broken pipe`): push with it off.
- **A Fork fetch autostashes the working tree, which reads as lost work.** It does not always pop the stash back: look in `git stash list` for `Fork autostash <date>` before redoing the work, and compare each stashed file against `HEAD` before dropping it.
- **A scratch git repo inherits the global `commit.gpgsign`.** Pass `-c commit.gpgsign=false` to every commit in a repo nothing will push, or each one waits on the Secretive prompt.
- **`uv lock` copies this machine's `repomatic` cooldown exemption into the lockfile.** It lands as `[options.exclude-newer-package]` in `uv.lock`, which no CI run produces: relock with `XDG_CONFIG_HOME` pointed at an empty directory.

## Code generation preferences

For any non-trivial workflow, data processing, or multi-step logic: write Python, not Bash. The user is an advanced Python developer and can quickly read, inspect, and validate Python code. Short one-liners and simple Bash scripts are fine for convenience and performance, but anything with branching logic, string manipulation, data transformation, or error handling should be Python.

**Every Python script is a uv standalone script.** Give the file a `#!/usr/bin/env -S uv run --script` shebang and a PEP 723 inline metadata block that declares its dependencies, as the [click-extra tutorial](https://kdeldycke.github.io/click-extra/tutorial.html#standalone-script) shows. The file then carries its own environment. uv installs the declared dependencies into an isolated environment before the first run. No project boilerplate, lockfile, or install step sits in between. That resolution is a live-registry install, so [§ Cooldown on every install](#cooldown-on-every-install) binds it. The user-wide `exclude-newer` in `~/.config/uv/uv.toml` covers this machine, and the workflow-level `UV_EXCLUDE_NEWER` covers a workflow that calls the script elsewhere.

Run one with `uv run --script {absolute path}`, not through its shebang. A file written by a tool call is not executable, so invoking it by path fails with `permission denied`, and the `chmod +x … && …` that would fix it is a compound command the harness denies, the same way it denies a leading `cd`. The shebang stays for a human running the file from a shell.

## Data visualization

When producing matplotlib figures, follow the design system at https://github.com/temataro/better-graphs for readable, presentation-ready plots: it codifies Tufte-style design rules, a chart-selection guide, and a `house_style.py` styling module (`apply_theme()`, `polish()`, `takeaway_title()`) that replaces matplotlib defaults with accent-led palettes, trimmed spines, unit-aware ticks, and takeaway-focused titles.

## Markdown and documentation

The markdown no-hard-wrap rule above is not merely a ceiling to stay under: each sentence or logical clause flows as a single long line and the renderer handles wrapping. Never reflow a paragraph to a column width, in any markdown file.

Sentence-case titles, natural heading anchors and the `[owner/repo#N]` link form are stated above and need no restating here: see [§ Comments and docstrings](#comments-and-docstrings) and [§ Linking to external repositories in Markdown](#linking-to-external-repositories-in-markdown). One case those do not reach: in plain GFM, where MyST's `(my-anchor)=` is unavailable, the explicit anchor form is `<a id="…"></a>`.

GitHub renders an alert (`> [!NOTE]`, `> [!WARNING]`) only at the top level: nested in `<details>`, a list item or a blockquote, it shows its marker as plain text. There, write an emoji-labelled quote instead, like `> ⚠️ **Warning**: …`.
