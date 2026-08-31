@~/.claude/tropes.md

## Consuming repomatic

### Upstream conventions

This repository takes its reusable workflows and much of its `pyproject.toml` configuration from [`kdeldycke/repomatic`](https://github.com/kdeldycke/repomatic), and follows the conventions established there. The generic sections of this file were seeded from that same upstream and are now maintained here: repomatic no longer syncs instructions into consuming repos, so an edit to one of them belongs in this file, not upstream.

**Contributing upstream:** propose a gap or improvement in the reusable workflows, the `repomatic` CLI, or a shared convention at [`kdeldycke/repomatic`](https://github.com/kdeldycke/repomatic/issues). Landing it upstream is what carries it to every other repository consuming it, instead of fixing it once here.

### Managed versus downstream-owned workflow content

A generated workflow file has two parts. The first job is the **managed thin caller**, delegating to a reusable upstream workflow through a SHA-pinned `uses:`. It is rebuilt from scratch on every sync, so a hand edit to it is lost. Everything declared *after* it is **downstream-owned**: the sync slices the file at the end of the managed job body and carries the remaining text through verbatim, comments and blank lines included.

Position alone does not settle ownership: a multi-job caller declares canonical jobs after its first one, and those are regenerated too. Write a comment above your first downstream job saying so. The sync preserves it like any other extra content but never writes one itself, so its absence means the file has nothing in it that is yours to edit.

A fragment that is only comments and blank lines is still carried over, and deliberately does not count as a downstream job for the rule below.

### The permissions contract is generated, not hand-written

When a workflow file carries downstream-owned jobs, the sync emits a top-level `permissions: {}` **and** the scopes the reusable workflow needs on the managed caller job. Both halves ship together, and neither is written by hand: a top-level `{}` on its own starves the managed call, which GitHub aborts at startup the moment a nested job asks for a scope the caller never granted.

So a `lint-repo` complaint about a missing top-level `permissions` key is a signal to re-run the sync, not to add the key yourself. Declare least privilege per job on the downstream-owned jobs instead, which is the half no sync rewrites.

### Bumping the repomatic pin

Regenerate rather than search-and-replace, so codegen changes (new job permissions, reshaped triggers) arrive with the version bump instead of a release behind it:

```shell-session
$ uvx --no-progress 'repomatic==X.Y.Z' init workflows/autofix.yaml workflows/lint.yaml
```

Name the components explicitly. A bare `repomatic init` also materializes whatever else is in scope for the repository (labels config, a changelog), and an unqualified `workflows` selector bypasses scope gating.

Read the release notes for breaking changes needing a manual follow-up. A renamed autofix job is the recurring one: its old PR branch stays open, attached to a job that no longer exists.

### Tools called from workflows are version-pinned

Every external tool a workflow invokes carries an exact version literal, in one of the shapes `sync-workflow-pins` recognizes: an action `uses:` ref, `uvx '{pkg}=={X.Y.Z}'` and the `--with` form for PyPI, `npm install {pkg}@{X.Y.Z}` for npm, and the `version:` input on `astral-sh/setup-uv`. That job resolves each to the newest release past `minimum-release-age` and opens a pull request. A tool invoked unpinned floats to the newest release on every run, outside the window entirely: see [§ Live registries with no cooldown knob](#live-registries-with-no-cooldown-knob).

A tool the runner image happens to provide is worse than an unpinned install, because it carries no version anywhere in the repository for anything to bump. Reach for a pinned dependency that already does the job instead of finding a way to pin the tool.

### PAT-gated checks degrade, they do not fail

Several `lint-repo` checks read GitHub API endpoints needing a scope on `REPOMATIC_PAT`. When the token lacks one, or the call fails for any other reason, the check returns an *indeterminate* result and is reported as skipped: it never fails the job. A missing scope costs coverage, not a red run, which is [§ Defensive workflow design](#defensive-workflow-design) applied to the audit lane.

Do not read a skipped check as a passing one. The setup-guide issue carries the pre-filled link for regenerating the token with the scopes a repository's own checks want.

### Configuration repomatic reads

`[tool.repomatic]` in `pyproject.toml` belongs to the repository and is authoritative for every feature flag. The tool sections synced from repomatic's bundled templates are not: a local edit to a key the template owns is re-applied on the next sync, so put a deviation behind a `[tool.repomatic]` setting rather than editing the synced value and expecting it to hold.

The sync grafts rather than overwrites. A key the template does not define survives verbatim, a table present in both is merged so local sub-keys are kept, and an array gains its local-only items after the template's. Only a scalar the template also defines is overwritten, which is the point of an ongoing sync. Comments on a grafted node carry over; a comment beside a key the template owns does not, so record why a local entry exists somewhere the merge cannot reach.

## Cooldown on every install

**Every command that resolves a package from a live registry carries a cooldown, except where this section names otherwise.** A cooldown refuses any version published more recently than a fixed window, so a compromised release has to survive that window before it can enter a build. Most malicious releases (stolen publishing credentials, dependency confusion, account takeover) are [caught and pulled within days of publication](https://blog.yossarian.net/2025/11/21/We-should-all-be-using-dependency-cooldowns), which is what makes a window of days worth the delay it costs.

The rule has **no scratch exemption**. It binds reusable workflows, one-off CI steps, test scripts, local reproduction commands, and throwaway experiments equally: an uncooled `uvx` in a five-minute debugging step resolves the same tree from the same registry onto the same runner as a production job. If you type an install command, it carries the cooldown. The exceptions are the three [documented exemptions](#documented-exemptions) below, and nothing else.

### A cooldown is not a hash

The two guarantees are independent, and most of what CI installs has only one of them. Know which you are relying on before calling something verified.

| Guarantee    | What it proves                                                      | Where this repo has it                                                   |
| :----------- | :------------------------------------------------------------------ | :----------------------------------------------------------------------- |
| **Cooldown** | The version has been public long enough for a compromise to surface | Every `uvx`, `uv pip`, `uv tool`, `npm` and `npx` invocation, whole tree |
| **Pin**      | Everyone resolves the same version                                  | Action SHAs, workflow version literals, `repomatic run` tools, `uv.lock` |
| **Checksum** | The bytes are the bytes that version shipped                        | `repomatic run` binary tools, `uv.lock` hashes, digest-pinned containers |

The gap worth naming: a `uvx`-resolved tree is gated by publication age but **never checked against a known digest**, because a `uvx` environment has no lockfile. That covers every uvx-backed `repomatic run` tool, and every `uvx 'repomatic==X.Y.Z' …` call a downstream repo inherits from a frozen workflow. `uv.lock` is the only place a Python dependency is hash-pinned, so anything resolved outside it trades hash verification for the cooldown alone.

### Where the window comes from

`[tool.repomatic] minimum-release-age` (default `1 week`) is the single source of truth. Never hard-code a duration next to an install command: read it from config, or from the `npm_min_release_age_days` output `repomatic metadata` derives from it.

Two files carry the duration as a literal instead, and both are pinned back to that source by a conformance test rather than trusted:

- **Every workflow**, because YAML cannot read Python: each sets `UV_EXCLUDE_NEWER` and `NPM_CONFIG_MIN_RELEASE_AGE` in a **workflow-level `env:` block**, rendered by `cooldown_env_block()` and asserted verbatim by `tests/test_workflows.py`. Job-level `env:` would let the value come from the `metadata` job, but it cannot cover the bootstrap: `metadata` resolves packages before any other job's output exists, and a workflow-level `env:` block cannot reference `needs`. The literal covers every job, including that bootstrap and any step added later by someone who never read this section.
- **`[tool.uv] exclude-newer`**, in this repo's `pyproject.toml` and in the bundled `repomatic/data/uv.toml`, because uv reads its own config and knows nothing of `[tool.repomatic]`. `tests/test_uv.py` asserts both equal `minimum-release-age`. They must not merely be *close*: a lock window wider than the install window resolves versions those installs then refuse, leaving a package pinned in `uv.lock` that CI cannot install.

That makes the cooldown the one place an environment variable beats an explicit flag, inverting [§ uv flags in CI workflows](#uv-flags-in-ci-workflows): a flag only protects the command someone remembered to write it on, and the commands that most need protecting are the ones nobody thought about.

A command that resolves against a checked-in lockfile is the exception that needs the flag *back*. `uv lock` and `uv sync` are governed by the project's own `[tool.uv] exclude-newer`, and an ambient `UV_EXCLUDE_NEWER` silently overrides it, so CI would lock to a different window than a developer running the same command. `sync-uv-lock` therefore passes `--exclude-newer` explicitly, sourced from `[tool.uv]`: a CLI flag outranks the environment.

### Per-ecosystem knobs

| Ecosystem                                                                             | Cooldown                                                           | Per-package exemption                                   |
| :------------------------------------------------------------------------------------ | :----------------------------------------------------------------- | :------------------------------------------------------ |
| uv: `uvx`, `uv pip install`, `uv run --with`, `uv tool install`, `uv lock`, `uv sync` | `--exclude-newer`, or `UV_EXCLUDE_NEWER`                           | `--exclude-newer-package pkg=YYYY-MM-DD`, CLI flag only |
| npm, `npx`                                                                            | `--min-release-age` in whole days, or `NPM_CONFIG_MIN_RELEASE_AGE` | `--min-release-age-exclude` taking a name or glob       |
| A tool in the `repomatic run` registry                                                | applied by the runner                                              | n/a                                                     |

uv accepts a friendly duration (`1 week`), an ISO 8601 span (`P7D`), or an absolute date; npm counts whole days and needs 11.10.0 or newer. Both knobs gate the whole resolved tree, transitive dependencies included, which is the point: the compromised package is rarely the one named on the command line. An *exemption* does not inherit that reach: exempting a package leaves its own dependencies gated, so a bypass reaching a fresh release usually has to name the transitive closure that release pulled in, one round-trip at a time.

"CLI flag only" in that table is literal, and it is what forces every per-package bypass in this repository onto a command line ({data}`repomatic.release.prepare_release.SELF_PIN_COOLDOWN_EXEMPTION`) rather than into one central declaration. Verified against uv `0.12.3`: under an ambient `UV_EXCLUDE_NEWER`, a `uvx` resolution fails byte-identically whether the exemption sits in `[tool.uv]`, in an adjacent `uv.toml`, or nowhere at all. The one knob that does reach it is `--config-file` / `UV_CONFIG_FILE`, rejected here because it **replaces** discovered configuration instead of merging with it: setting it for a whole CI environment silently drops `required-version`, `exclude-newer`, `dependency-groups` and `build-backend` from every *other* uv command in that environment, so making it safe means maintaining a complete mirror of `[tool.uv]` where a newly added key nobody remembers to mirror fails silently. Upstream: the `UV_EXCLUDE_NEWER_PACKAGE` ask is [astral-sh/uv#20995](https://github.com/astral-sh/uv/issues/20995), glob exemptions are [astral-sh/uv#20788](https://github.com/astral-sh/uv/issues/20788), and pin-based bypasses are [astral-sh/uv#19864](https://github.com/astral-sh/uv/issues/19864) with [astral-sh/uv#18921](https://github.com/astral-sh/uv/pull/18921). Revisit this paragraph when one of them lands.

A cooldown-filtered resolution is not a dependency conflict, and uv now says so: [astral-sh/uv#5878](https://github.com/astral-sh/uv/issues/5878) shipped a `hint:` naming the filtered package, the cutoff it hit, and the version it would otherwise have picked. Read that hint before diagnosing a "No solution found" as a real conflict. There is still no distinct exit code or error kind, so nothing automated can tell the two apart.

For any other package manager, consult [meta-package-manager's cooldown inventory](https://kdeldycke.github.io/meta-package-manager/cooldown.html#supported-managers) for which of them enforce a cooldown natively, which have support proposed upstream, which have none, and which are marked N/A because their archive already stages releases on its own. It tracks the capability across every manager mpm drives and stays fresher than a table copied into this file. Read the N/A verdict as "different threat model", not "gap": see [§ Distro archives are out of scope](#distro-archives-are-out-of-scope-not-an-exception).

### Live registries with no cooldown knob

Fail closed. When a *live registry* client has no cooldown knob, do not hand it a floating version range. Either pin an exact version that a cooldown-gated updater already vetted (`sync-action-pins`, `sync-tool-versions` and `sync-workflow-pins` all apply `minimum-release-age` before proposing a bump), or route the install through a client that has one. An unpinned install against a self-service registry is the exact thing this rule exists to prevent.

Check the [inventory](https://kdeldycke.github.io/meta-package-manager/cooldown.html#supported-managers) before concluding a client is knob-less, because they keep gaining one: `pip` grew `--uploaded-prior-to` / `PIP_UPLOADED_PRIOR_TO` in `26.1`, and `pipx` inherits it from the pip inside each venv it manages. A knob with a version floor also fails *open* on older releases, quietly ignoring the flag rather than erroring, so pair it with a floor check the way `repomatic run` does for npm (`NPM_MIN_VERSION_FOR_COOLDOWN`).

### Distro archives are out of scope, not an exception

`apt` and its peers are **not** live registries, and this rule was never about them. A stable archive is frozen at release and moves only through the distro's own staging: Debian's migration windows are a cooldown, implemented one layer down and measured in weeks rather than days. Nobody self-publishes into it, which is the property the window exists to compensate for everywhere else.

A second reason the knob could not exist even if someone wanted it: a distro version string is *the maintainer's package build*, not an upstream publish date, so a publish-date filter has nothing to filter on. mpm's inventory files these managers as **N/A** rather than unsupported for exactly this reason: the ecosystem solves the problem differently, it is not missing a solution.

**The exception is a repository you add yourself.** A PPA or a vendor's `.repo` file is a live, single-publisher registry wearing apt's clothes, with none of the distro staging behind it. Pin the version there, or fetch a checksummed artifact instead. `_release-engine.yaml` used to add the `cli.github.com` RPM repo to reach `gh` inside the build container; now that `gh` ships from the tool registry, no such hand-added repository remains in this codebase, which is the better fix whenever a registry binary exists.

Still prefer the tool registry over `apt-get` when both can supply a binary (`shfmt`, `actionlint`, `biome`, `gitleaks`, `lychee`, `typos`), for reasons that have nothing to do with cooldowns: the registry version is pinned, checksum verified, and identical on every runner and every developer machine, where the archive gives each distro release whatever it happens to hold. For a tool a *plugin* shells out to rather than imports, declare it in the plugin host's `path_tools` (`mdformat` does this for `shfmt`) instead of installing it beside the job.

Write the `apt-get` calls you do keep so they pull as little as possible:

- **`apt-get`, never `apt`.** The `apt(8)` man page says to prefer `apt-get` and `apt-cache` in scripts, as they keep backward compatibility; `apt` is an end-user tool whose behavior may change between versions.
- **`--no-install-recommends` always.** Recommends are extra packages nobody asked for, and every one widens what a step installs beyond what it names.
- **Name what the Recommends were providing.** Dropping them can quietly remove something real (graphviz recommends `fonts-liberation`, which a base image may not ship on its own), so add it to the install list explicitly. An explicit dependency you can read beats an implicit one you inherit.

### Documented exemptions

An exemption is an install that deliberately bypasses the window, declared in the open rather than smuggled in.

Any other exemption is a bug until proven otherwise. Anything claiming one carries a comment naming what breaks without it, and the narrowest scope that still works: a package, not a job; a job, not a workflow.

A consuming repo runs the same rule against its own, which is usually empty. One category recurs and is worth naming, because it reads like a violation and is not: a dependency the same maintainer publishes. The window guards against a compromised upstream, and here the publisher and the consumer are the same person, so it buys nothing while holding each release back a week from the only repository that consumes it. Exempt it per-package, with a zero span rather than a fixed date so the next release is picked up without editing the file, and put the reasoning beside it:

```toml
[tool.uv]
# apricot is published by this repository's own maintainer: the cooldown guards
# against a compromised upstream, which does not apply here, and it otherwise
# holds each release back a week from the one repository that consumes it.
exclude-newer-package = { apricot = "0 days" }
```

Declaring it in `pyproject.toml` rather than in a machine's `~/.config/uv/uv.toml` is what makes a fresh clone resolve the same way, and keeps the exemption reviewable in a diff. It stays a bypass and not a hole: the transitive tree that release pulls in is still gated, and that tree is the part the maintainer did not publish.

## A release ships only released dependencies

Consuming a dependency from a git branch, a fork, a local path or a private index is the right move mid-cycle, and `[tool.uv.sources]` exists for it. Releasing while one is in place is not: source overrides never reach the published metadata, so the wheel builds and uploads exactly as it would have, and only the *install* fails. Nothing in this repository can feel it, because every workflow here installs from `uv.lock` and resolves straight through the override.

`repomatic lint-deps` is the gate, and it blocks everything off-index, `[dependency-groups]` included. Do not weaken a finding to a warning to get a release out; the two legitimate moves are to land the swap (`sync-dep-sources` automates the git-branch-plus-`.dev`-floor idiom on its own) or to name the package in `[tool.repomatic] lint-deps.allow` with the reason it is safe. Adding a rule here means adding it to {func}`repomatic.deps.dep_sources.scan_pyproject` or {func}`~repomatic.deps.dep_sources.scan_lock`, never to a call site.

The gate runs in four places, and the release lane's copy is the backstop, not the mechanism: by the time it fires the freeze commit is already on `main` and the recovery is to burn the version per [§ Skip and move forward](#skip-and-move-forward-dont-rewrite-history). The layer that prevents that is the `prepare-release` PR banner, which is regenerated on every push. See [`docs/dependencies.md` § Shippable sources](https://repomatic.net/dependencies#shippable-sources) for the rules and the failure classes.

## A floor comment justifies one version

Every version floor carries a comment above it saying what breaks below that version and where the project would notice. That comment documents **the floor as it stands**, in one short paragraph. It is not a log of how the floor got there.

The failure mode is additive and slow. A floor bump arrives, whoever writes it appends a paragraph about the new version, and nobody deletes the paragraph about the old one, since deleting text that reads as informative feels like losing something. Repeat over a few years and the comment is a private changelog of the dependency, with the declared version buried under the floors it replaced. `meta-package-manager`'s `click-extra` entry reached 676 words that way, walking back through eight superseded floors before reaching the dependency itself.

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

### Changelog and docs updates

Always update documentation when making changes:

- **`changelog.md`**: One bullet per user-facing change, describing **what** changed (features, fixes, behavior changes), not **how** it was built or **why**. See [§ Changelog entry length](#changelog-entry-length); rationale belongs in `docs/`, code comments, the commit message, or the PR body, never the changelog.
- **`docs/`**: When this repo has a `docs/` tree, update the relevant page when adding or modifying workflow jobs, CLI commands, or configuration options.

**Never ship an empty release section.** When a cycle's net diff since the last tag is entirely mechanical — a dependency-pin bump, a generated-file regen, a docs-only or CI-only fix — and nothing qualifies as user-facing, add one bullet naming what actually moved rather than leaving the section blank under a heading that still gets tagged and published. A blank section reads as unexplained or broken to anyone scanning release notes for that version. Assert the absence of functional impact only when it is verified (a green, behavior-preserving cycle); otherwise just name the mechanical change: "Sync CI tooling, workflow pins and dependency floors with the latest repomatic release."

**Order within a release section:** `**Breaking:**` entries first, then `**Deprecated:**` entries, then new features, other changes, bug fixes and docs (a reader scans for breaking changes first).

Use `**Breaking:**` when a surface the reader actually consumes is gone and their code, invocation, config or workflow must change to keep working. Use `**Deprecated:**` when the old surface still resolves but emits a `DeprecationWarning` and is scheduled for removal in a named future release: name that release in the entry, so the reader knows their deadline.

**Who consumes the project decides what counts as breaking.** A project consumed as a library breaks real code when a Python symbol is renamed, moved or dropped, so that symbol earns a bullet. A project that is invoked rather than imported does not: its importable surface is an implementation detail, and a bullet announcing a dropped enum or a regrouped module only alarms readers who could never have called it. `repomatic` is the second kind, so `**Breaking:**` here covers the surfaces a user touches: CLI commands and options, `[tool.repomatic]` config keys, reusable-workflow inputs and job names, `repomatic metadata` output keys, and bundled assets.

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
- **Only what Sphinx renders reaches the page:** `docs/*.md` and any docstring `autodoc` covers. A `#` comment, a YAML comment and a TOML comment are invisible to it, so move the plan into the docstring that owns the concern and leave the config file a one-line `XXX` plus the ticket link. That split is also what the floor-comment rule wants (see [§ A floor comment justifies one version](#a-floor-comment-justifies-one-version)).
- **Retire it in the same change that retires the shim.** A todo outliving its trigger is worse than none: the page is published, so it advertises work already done.

Enable the extension where it is missing (`sphinx.ext.todo` plus `todo_include_todos = True`), and give `docs/todolist.md` a toctree entry, or the items render nowhere.

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

Jobs run on a test-matrix runner (`ubuntu-26.04` for the x86 default), and downstream workflows inherit it. Never reach for a `-latest` alias: GitHub repoints those without a commit to review, and `lint-repo` rejects them.

### Naming conventions for automated operations

CLI commands, workflow job IDs, PR branch names, and PR body template names must share the same verb prefix, keeping the conventions learnable and grepable.

| Prefix     | Semantics                                          | Source of truth      | Idempotent? | Examples                                          |
| :--------- | :------------------------------------------------- | :------------------- | :---------- | :------------------------------------------------ |
| `sync-X`   | Regenerate from a canonical or external source.    | Template, API, repo  | Yes         | `sync-gitignore`, `sync-mailmap`, `sync-uv-lock`  |
| `update-X` | Compute from project state.                        | Lockfile, git log    | Yes         | `update-dep-graph`, `update-checksums`            |
| `format-X` | Rewrite to enforce canonical style.                | Formatter rules      | Yes         | `format-json`, `format-markdown`, `format-python` |
| `fix-X`    | Correct content (auto-fix).                        | Linter/checker rules | Yes         | `fix-typos`                                       |
| `lint-X`   | Check content without modifying it.                | Linter rules         | Yes         | `lint-changelog`                                  |
| `pack-X`   | Assemble a distributable artifact set for release. | Repository tree      | Yes         | `pack-binaries`, `pack-plugin`                    |
| `sample-X` | Record an external reading into a local history.   | External API         | Per period  | `sample-metrics`                                  |
| `scan-X`   | Submit artifacts to an external analysis service.  | External API         | Yes         | `scan-virustotal`                                 |
| `{noun}`   | Maintain a GitHub issue tracking a repo condition. | GitHub API, settings | Yes         | `setup-guide`                                     |

**Rules:**

1. **Pick the verb that matches the data source.** External template/API/canonical reference: `sync`. Local project state (lockfiles, git history, source): `update`. Reformatting: `format`.
2. **Name the specific tool or file, not a generic category** (`sync-zizmor`, not `sync-linter-configs`). A second tool in a category gets its own operation.
3. **All four dimensions must agree.** A file-modifying operation uses one `verb-noun` for CLI command, workflow job ID, PR branch, and PR body template (`sync-gitignore` everywhere). Operations that write no repository file use only the CLI command and job ID: `lint-*`, which reads, `pack-*`, which emits a build artifact, and the bare-noun issue trackers of rule 9. Two exceptions: `sync-binaries` has no PR branch or template of its own because it runs inside the `scan-virustotal` job and appends to that job's pull request, disableable via `[tool.repomatic] binaries.sync`, see [§ Scanning accumulates in one pull request](https://repomatic.net/operation-contracts#scanning-accumulates-in-one-pull-request); and `fix-awesome-toc` runs as a step of `format-markdown` because it corrects what that job just wrote and the two would otherwise fight across separate PRs, see [§ Fix steps inside another job](https://repomatic.net/operation-contracts#fix-steps-inside-another-job). A job local to this repository (one with no upstream template to name on `pr-body --template`) keeps the same identity: its template is `.github/pr-templates/{job-id}.md`, passed with `--template-file`, and `repomatic lint-repo` flags one placed elsewhere. See [§ Repository-local templates](https://repomatic.net/operation-contracts#repository-local-templates).
4. **Function names follow the CLI name** (`sync_gitignore` for `sync-gitignore`). On collision with an imported module, use the Click `name=` parameter (`@repomatic.command(name="update-dep-graph")` on `dep_graph`) or append `_cmd` (`sync_uv_lock_cmd`).
5. **A read-only command may expose mutation via `--fix`.** When a query command (like `audit`) gains a `--fix` autofix mode, the autofix operation keeps its own `fix-X` job ID, PR branch, and template and invokes `<command> --fix` (`fix-vulnerable-deps` runs `audit --fix`). That command name is then exempt from rule 3: it is a general-purpose query command (like `metadata`), not the operation's namesake.
6. **`dep` when attributive, `deps` when the object.** A "dep" prefix modifying another noun stays singular, following English compound-noun convention (`dep-graph`, `dep-sources`, `dep_report.py`); "deps" appears only where the dependencies are themselves the object of the verb (`sync-deps`, `vulnerable-deps`).
7. **A sample accrues where a sync converges.** `sync-X` regenerates a file the external source could rebuild from scratch, so losing it costs a re-run. `sample-X` records a reading the source will not remember: the store is the only place that history exists, and a lost one is gone. That is what settles the two properties the table cannot state. Idempotency holds *within* a period only, since re-running on the same day overwrites its own point while tomorrow's run adds one nothing upstream could reproduce. And the recording accumulates in one long-lived pull request that every run appends to, never a per-run one and never a direct push. A per-run pull request is unreviewable for the reason a post-release recording is: rejecting the diff cannot change what the API answered, only lose it, and one left unmerged would stall the accrual. One accumulating pull request escapes both, because each run restores the store from the branch before appending: leaving it open costs freshness and never a reading. See [§ Sample job contract](https://repomatic.net/operation-contracts#sample-job-contract). All four of rule 3's dimensions therefore apply, PR branch and template included.
8. **A dataset the repository commits is CSV, not JSON.** Every one of them is a flat table, and CSV wins on all four counts that matter for a file under version control: a record is one line rather than seven, so a scheduled append is a readable diff; the file is about half the size; MyST's `csv-table` renders it directly and GitHub serves it through a searchable grid viewer; and nothing in the autofix lane touches CSV, where a committed JSON file has to be serialized in Biome's exact style or `format-json` rewrites it right back. Reach for JSON only when a record genuinely nests. {mod}`repomatic.tabular` is the one place that reads and writes them.
9. **An operation whose output is a GitHub issue takes a bare noun, no verb prefix** (`setup-guide`). It writes no repository file: it upserts one issue through {func}`~repomatic.github.issue.manage_issue_lifecycle`, which opens, updates, closes and reopens it, matched on the exact title. Every such command shares that one mechanism, so a verb would name the mechanism rather than the subject and they would all collapse onto the same prefix; the noun instead names what the issue tracks, keeping the command and the issue title the same phrase. Body fragments live in `repomatic/templates/{name}[-{fragment}].md` and render through {func}`~repomatic.github.pr_body.render_template`: that renderer is shared with PR bodies, but these are issue bodies, so `pr-body --template` never names one and rule 3's PR-branch and PR-template dimensions do not apply. Every issue carries {data}`~repomatic.github.issue.BOT_ISSUE_LABEL`. `broken-links` predates this convention and sits outside its population: its job is `check-broken-links` rather than the bare noun, and its issue carries a topical label (`📚 documentation`, or `🩹 fix link` on an awesome list) instead of the bot one. That last sentence is therefore a claim about the rule-9 family, not about every issue the CLI opens.

### Automated operation contracts

Every automated operation follows the [naming conventions](#naming-conventions-for-automated-operations) and is [idempotent](#idempotency-by-default). For the detailed checklists of required properties, invariants, and optional elements for each operation type (sync, update, format/fix, lint, pack, scan, PR body templates), see [`docs/operation-contracts.md`](https://repomatic.net/operation-contracts).

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
- **Write conformance tests when fixing a class of bugs.** For a bug that is a *category* (not a one-off), add a generic test locking in the invariant: iterate over every member of the set (registry entries, generators, exported symbols, data files) and assert the property uniformly via `@pytest.mark.parametrize` or a loop. Applies when the bug stems from a shared convention checkable from the codebase alone (no fixtures or mocks). Model: `tests/test_readme.py::test_docs_generator_matches_in_tree_state`. Shape: enumerate the population, assert on each, fail naming the violator. **Then prove it fails on the pre-fix state**, by running it against the old content rather than assuming: a conformance test written from the corrected text often only matches the corrected phrasing, so it passes on the very bug that motivated it and locks in nothing. When the invariant is genuinely narrower than the bug class (a rule keyed on one phrasing among several that state the same claim), keep the test and say so plainly, since a narrow guard is still worth having: what must not happen is reporting it as retroactive coverage it does not provide.
- **Pass `encoding="UTF-8"` to `subprocess.run(..., text=True)` when output may contain non-ASCII bytes** (emoji in workflow `name:`, accented names). `text=True` alone uses the platform default (`cp1252` on Windows), raising `UnicodeDecodeError` only in Windows CI. Test helpers shelling out to `git show`/`git cat-file` are the usual offenders; production `read_text`/`write_text` already set it.
- **Pass `encoding="UTF-8"` to every text-mode `open()`, `read_text()`, and `write_text()` in tests, same as production.** The same Windows cp1252 default applies to file I/O, and the failure hides until content grows a non-ASCII character. Ruff's `PLW1514` (in the shared config) flags `open()` and receivers its inference can type, but misses unannotated `Path` locals (`doc = tmp_path / "page.md"`); when a change touches file I/O, run the suite once with `PYTHONWARNDEFAULTENCODING=1` (PEP 597) to surface every bare call at runtime, on any platform.
- **Spell it `UTF-8`, never `utf-8`, in both of the above.** Python normalizes either, so the difference carries no meaning and a mixed codebase only makes a reader stop to work that out. `tests/test_suite_hygiene.py::test_encoding_argument_spelling_is_uniform` pins the suite to the one spelling; production holds it by convention, with no exception at present.
- **Never probe the environment at collection time.** A parametrize expectation computed at import — one that shells out, walks `PATH`, or stats the filesystem — is evaluated independently by every xdist worker, so a probe that can answer differently twice (a slow binary, a tool whose availability shifts mid-run, a file another test writes) leaves the workers holding different test lists and aborts the whole session with `Different tests were collected between gw0 and gw1`, naming no culprit. Wrap such an expectation in a callable the test resolves in its own body, and put any environment warm-up in a session-scoped fixture, which runs once collection has settled.
- **Seed environment-dependent global caches before the first test, from a session fixture.** click-extra's `runner` fixture pins `HOME` and its platform equivalents to an empty directory around each CLI invocation, so a module-global cache filled lazily *from inside* a test records what a home-less environment answered and serves that for the rest of the worker's session. `meta-package-manager` hit this the hard way: its manager pool cached a tool as unavailable because the probe that happened to run first went through a `$HOME`-dependent shim, and every later test on that worker saw the tool missing. An autouse session fixture touching the cache first, outside any runner, keeps that state honest — and is worth writing down where the cache lives, since the invariant is invisible at every call site.

## Agent conventions

This repository uses three Claude Code agents in `.claude/agents/`. Definitions stay lean: if a rule belongs in `CLAUDE.md`, put it there and reference it. Do not duplicate.

**Agents must be self-contained for downstream portability.** Agents deploy downstream via `repomatic init subagents` as standalone files; Claude auto-invokes them from their `description:` frontmatter. All knowledge must be inline or reference `claude.md` sections, not upstream `docs/` URLs or upstream-only paths. When mining session history, default to local `claude.md` updates; file an upstream proposal only when the pattern is generic across repos.

### Source of truth hierarchy

`CLAUDE.md` defines the rules; the codebase and GitHub (issues, PRs, CI logs) are what you measure against them. When they disagree, fix the code to match; if the rules are wrong, fix `CLAUDE.md`.

### Common maintenance pitfalls

Patterns that recur across sessions, to watch for proactively:

- **Documentation drift** is the most frequent issue: version references and workflow job descriptions in `docs/` go stale after every release or refactor, so verify docs against actual output.
- **CI debugging starts from the URL.** When a workflow fails, fetch the run logs first (`gh run view --log-failed`), don't guess; when the user points to a specific failure, diagnose that exact one.
- **A green run can be stale rather than clean.** Reading the newest *conclusive* run walks back past the `cancelled` ones supersession piles up on a busy branch, and those are exactly where the newest commits were tested, so a `success` a few commits back can predate every line the cycle added. Diff the gap (`git log --oneline <that run's headSha>..HEAD`) before trusting it: when cycle commits sit inside, the workflow never ran on them. This direction costs more than its opposite, since a false red only wastes a round-trip while a false green ships the break.
- **A slow job is not a hung one, and elapsed time alone cannot tell them apart.** Before calling anything stuck, get a baseline from that workflow's recent *successful* runs (`gh run list --status success`) and read per-job `completedAt` timestamps. A flat count of in-progress jobs is not evidence of a stall: jobs finish and others start into the freed slots, holding the count steady. Diagnosing a hang wrongly is expensive when the proposed remedy is cancelling someone's work.
- **Type-checking divergence.** Code that passes `mypy` locally may fail in CI under `--python-version 3.10`; always check the minimum supported version.
- **Trace to root cause before coding a fix.** Audit a bug's scope before writing the patch. If the same pattern appears in multiple places, fix it at the shared layer; if only one call site is affected, check whether the data is on the wrong code path before handling it where it lands.
- **Simplify before adding.** When improving something, first check whether existing code or tools cover the case; remove dead code and unused abstractions before introducing new ones.
- **A recorded decision is evidence, not a stop sign.** A note in a rules file saying something was "assessed and rejected" or "kept by decision" describes the code as it stood when someone wrote it. Later edits can shrink what it covers while leaving the sentence intact, and a rationale written about a whole subsystem often only ever justified part of it. Before declining a change on the strength of such a note, restate what it actually decided, check that scope against the code today, and split the verdict when the two have drifted. Then rewrite the note to state the rule the code now follows, since a paragraph defending a subsystem uniformly is what preserves the half that stopped earning it.
- **Angle-bracket placeholders in bash code blocks.** `mdformat-shfmt` runs `shfmt` on fenced ```` ```bash ``` ```` blocks, and `shfmt` parses `<foo>`/`>foo` as redirection and reorders the command. Use curly braces (`{foo}`) for placeholders in bash examples.
- **The two TOML formatters disagree, so a config example has two canonical forms.** `pyproject-fmt` owns `pyproject.toml` and writes an inline array spaced and sorted (`keywords = [ "a", "b" ]`); `mdformat` owns fenced ```` ```toml ```` blocks and rewrites the same line unspaced (`keywords = ["a", "b"]`). Neither is wrong and neither yields: a snippet pasted from the file into a docs fence gets reformatted, and one pasted back gets reformatted again. Write the example however you like and let each formatter settle its own territory, but never treat the resulting difference as drift to reconcile by hand.
- **Route through existing infrastructure, don't bypass it.** Before writing a new helper or merge function, check whether the codebase already handles the operation. A bug from data on the wrong code path is better fixed by routing it correctly than by duplicating logic at the wrong site: move a misrouted file to the right registry rather than special-casing it at the call site.
- **Generator/formatter ping-pong is recurrent.** Any code that writes a checked-in Markdown file competes with `format-markdown` for the canonical layout. After touching such code, run the generator, then `repomatic run mdformat -- {file}`, then the generator again, confirming `git diff` stays empty across all three states; if not, align the generator with mdformat. Grep for the pattern in sibling generators and mirror the check in `tests/`. Checked-in JSON has the same trap with `format-json`, in a worse form. The indent is whatever the target repository's Biome config asks for, so a generator hardcoding one fights `format-json` forever wherever the repository is configured the other way. Read it from that repository instead: `_biome_json_indent` in `repomatic/plugin.py` resolves it, and `render_plugin_settings` writes with it.
- **`repomatic run {tool} --check` is unreliable for tools with a post-process fixup.** A few tools (currently `mdformat`) get a Python post-processing pass that only runs in write mode, so `--check` can report drift the write path would reconcile (false positive) or pass on files it would still rewrite (false negative). To verify or gate formatting, run the write path and inspect `git diff`, never `--check`.
- **A generated artifact's prose has one owner layer: find it before rewriting.** A PR body, issue or docs page mixes code-generated parts (tables, computed rows) with static template text. Hand-editing a code-generated part is lost on the next run, and rewording prose by changing code edits the wrong layer. Find the template or string constant that owns the words first, and leave the rest alone.
- **Grep for pinned phrases before rewriting text that has tests.** A suite may assert exact strings from the file being edited: a heading, an opening word, a checklist step. A rewrite that keeps the meaning can still fail it. Grep the tests and callers for distinctive phrases before editing; keep what they pin, or update the assertions in the same change.
- **Removing a bundled asset leaves downstream orphans.** Dropping a skill, agent, or workflow from `COMPONENTS` stops shipping it, but copies already in downstream repos are invisible to stale-file detection. Add a `RemovedAsset` tombstone to `REMOVED_ASSETS` in `repomatic/registry.py` so `repomatic init` prunes the orphan (the `RemovedAsset` docstring has the content- vs fingerprint-gating recipe); a CI test fails otherwise. A rename is a drop plus an add: tombstone the old name.
- **Claude Code behavior claims rot between releases.** The hook output schema and the title applier routing changed materially between the builds verified 2026-07 and 2026-08 (the session-title premise inverted), so any claim encoded about that runtime carries the version and date it was verified against, and gets re-checked before being trusted: strings-grep the installed bundle in the Caskroom, then run a live probe. Docs and bundle disagree regularly; the bundle and the probe win.
- **Give a best-effort handler a log before debugging it.** An exit hook or shutdown callback that swallows its failures is invisible when it breaks: nothing distinguishes "never fired" from "fired and gave up at step N". Before theorizing, add a small capped log line at every silent exit point, then run one cheap probe per fact. Both the Claude Code `SessionEnd` nudge and pi's exit-time title rename needed exactly this on 2026-08-29; each hid a multi-cause failure chain no single guess would have found.

### Agent behavior policy

- **Never post to the web without explicit approval.** Do not create or comment on GitHub issues, PRs, or discussions, or post to any external service, without the user's explicit go-ahead. If approval is blocking, draft the content in a temporary markdown file for review.
- Agents make fixes in the working tree only: never commit, push, or create PRs. Exception: skills that run autonomously (`/babysit-ci`, `/repomatic-ship`) may commit and push, and include a `Co-Authored-By` trailer by default; a maintainer's explicit standing rule against AI attribution overrides that default, since the trailer lands in their repository's permanent history. Follow the skill's instructions when they override this rule.
- **Land an upstream proposal as working-tree edits in the sibling checkout, not as prose.** When work in a downstream repo surfaces a bug or rough edge that belongs to `repomatic`, and a sibling checkout exists at `../repomatic`, implement the change there directly: edit the code, update the tests it breaks, and verify it. Then stop, leaving every change uncommitted and unpushed. A described fix costs the maintainer the whole implementation; a diff sitting in the tree costs them a review, which is the step they were always going to do themselves. This does not relax the rule above: no commit, no push, no PR, no issue. Confine the edits to what the finding justifies, and say plainly which files were touched and what verification was run.
- **When the repository *is* `repomatic`, land the finding here and ship it.** The rule above is written for a downstream repo with a sibling checkout; inside `kdeldycke/repomatic` there is no `../repomatic`, so "propose it upstream" collapses into "fix it here" and stopping before the commit only defers the fix to a later cycle while the diff collects conflicts against whatever the machinery rewrites meanwhile. Implement it, verify it with whichever checks the change touches, and commit it like any other work. A release is when this pays off rather than a reason to hold it back: `prepare-release` regenerates the release pull request on every push to the default branch, replaying the freeze onto the new head, so a fix landed before the merge ships in *that* release instead of the next. Keep the pass bounded to what the session actually surfaced, though: anything needing more than a contained edit, or touching code the release itself depends on, stays an uncommitted diff plus a note, exactly as it would downstream.
- Prefer mechanical enforcement (tests, autofix jobs, lint checks) over prose rules. If a rule can be checked by code, it should be.
- Agent definitions reference `CLAUDE.md` sections, not restate them.
- qa-engineer is the gatekeeper for agent definition changes.

### Skills

Skills in `.claude/skills/` follow agent conventions: lean, no duplication with `CLAUDE.md`, reference sections instead of restating rules. Run `repomatic list-skills` to list them.

**A skill is a plain folder of static files, copied verbatim.** `repomatic init skills` places the folder at its destination and does nothing else: no rendering, no per-target variants, no flavor flags. Optional `scripts/`, `references/` and `assets/` subdirectories travel with it. Anything that would otherwise vary per destination belongs in the skill body as prose, never in a code path.

**Frontmatter carries [Agent Skills spec](https://agentskills.io/specification) fields, plus `argument-hint`.** That single deviation is settled; every other Claude Code extension stays out. Notably there is no `model:` (the recommended model rides in the spec's `compatibility` field) and no `disable-model-invocation:`, so **every skill is model-invocable by design**: skills exist to augment the parent agent, and what they may actually do is gated by the permission layer, not by frontmatter. `tests/test_skills.py` enforces this, so argue a new field there before adding it to a skill.

**Skills must be self-contained for downstream portability.** Skills deploy downstream via `repomatic init skills` as standalone folders; downstream repos have no `docs/` and skills typically lack `WebFetch`, so all domain knowledge must be inline or in the skill's own `references/`. Duplication between a skill and a docs page is intentional: `docs/` serves humans, the skill serves Claude at runtime.

**Cross-references between skills and agents must degrade gracefully.** A "Next steps" line suggesting `/other-skill` is informational; a *programmatic* call is the same: a skill invoking another through the `Skill` tool must fall back to a subagent or inline work when the target is excluded (via `[tool.repomatic] exclude` or scope filtering), never letting a missing skill abort the caller. Write prose so a missing cross-reference is a no-op, not a blocker.

### Mechanical vs analytical work

The `repomatic` ecosystem has a **mechanical layer** (CLI commands and CI workflows that deterministically sync, lint, format, and fix files on every push to `main`) and an **analytical layer** (judgment-based tasks needing context comparison and trade-offs). Skills focus on the analytical gaps (custom job content analysis, cross-repo pattern comparison, judgment on intentional vs stale divergence); don't duplicate what CI handles mechanically: see [§ Automated operation contracts](#automated-operation-contracts).

## Design principles

### Philosophy

1. Create something that works (to provide business value).
2. Create something that's beautiful (to lower maintenance costs).
3. Work on performance.

### Labeller rules are precision-first conveniences

The issue and PR labeller (content keyword rules, file glob rules) pre-labels a freshly filed issue or PR to save the maintainer a first pass. It never replaces their review and classification, and nothing downstream treats its labels as complete or authoritative. Tune it for **precision, not recall**: a missing label costs one manual click; a wrong label is noise on every item that trips it. Encode a rule only when the signal is unambiguous, and none when it is not.

- **Content rules** match issue/PR prose: key them off terms that unambiguously name the subject (a distro, language, ecosystem or brand) and that the tool never prints in its own output. Never key off a token the tool emits for *every* item it handles, like an ID, sub-command or status-table entry a CLI lists for all its back-ends: a user who pastes such a trace makes every one of those labels fire at once.
- **File rules** match a PR's changed paths: key them off a path owned by exactly one label. A glob broad enough to catch unrelated changes is worse than none.

Both rule families match in-process (`repomatic/labels.py`) rather than through the retired `github/issue-labeler` and `actions/labeler` actions, and a label's pattern list is **OR-joined**: any one pattern matching earns the label. A bare content pattern is a keyword, matched case-insensitively and anchored on each edge that is itself a word character, so `fix` does not fire inside `prefix`. Wrap a pattern in slashes (`/body/flags`) to pass a regex through verbatim instead, case-sensitive unless a flag says otherwise. A label's file globs are evaluated as one set, so a `!`-negated entry subtracts from its siblings the way a `.gitignore` line would (`["docs/**", "!docs/generated/**"]`), with no separate exclude rule to write.

### Linting and formatting

[Linting](https://repomatic.net/workflows#github-workflows-lint-yaml-jobs) and [formatting](https://repomatic.net/workflows#github-workflows-autofix-yaml-jobs) are automated via GitHub workflows. Developers needn't run them manually; pushing triggers the workflows, which catch issues and handle the nitpicking.

### Keep logic in Python, not workflow YAML

Push anything beyond trivial wiring out of workflow YAML into the CLI/library. Rather than duplicating `if:` conditions across steps, compute them once in `repomatic metadata` and reference the result. Rather than hand-maintaining workflow content, generate it in Python (see `repomatic.github.workflow_sync` for the rationale and the `publish-pypi` example): a tested generator that fails loudly beats a static artifact that can silently drift.

### Defensive workflow design

GitHub Actions workflows face race conditions, eventual consistency, and partial failures. Prefer **belt-and-suspenders**: multiple independent correctness mechanisms over a single guarantee. If a job depends on external state (tags, published packages, API availability), add a fallback or graceful default and make operations [idempotent](#idempotency-by-default) so re-runs are safe.

**Non-interactive third-party tooling.** When a tool prompts interactively (path selection, asset selection), pre-create its config files and resolve inputs via `gh` or another CLI rather than piping stdin: stdin redirection is fragile across platforms and fails outright on Windows ("Incorrect function"). Where a tool has no non-interactive mode at all, fetch the artifact it would install and verify that directly.

**Advisory findings never fail a scheduled audit job.** A scheduled audit separates advisory findings from gating checks: opportunities and upstream changes are reported into `$GITHUB_STEP_SUMMARY` while the job stays green, and only drift against pinned or committed state fails it — a red run for an advisory finding teaches people to ignore that workflow's red runs, which then hides real failures. A batch job accumulates a per-item row in the summary and exits non-zero once at the end, rather than aborting on the first failure.

### Idempotency by default

Workflows and CLI commands must be safe to re-run: the same command twice with the same inputs produces the same result, with no errant side effects (duplicate tags or PR comments, redundant file writes). Use `--skip-existing` or equivalent guards when creating resources; check for existing state before writing (skip an admonition already present, skip a PR that already exists for the branch); prefer upsert over create-only; make file-modifying operations convergent (re-applying is a no-op).

**When idempotency is not achievable**, document in a comment or docstring what side effects occur on re-runs and why they are acceptable.

### Skip and move forward, don't rewrite history

When a release goes wrong (squash merge, broken artifact, bad metadata), prefer **skipping the version and releasing the next one** over reverting, force-pushing, or rewriting `main`: a burned version number is cheap, a botched automated recovery is not (this mirrors PyPI's [yank](https://peps.python.org/pep-0592/) model). When designing new safeguards, default to **detection + notification** over **detection + automated fix**: the blast radius of a missed notification is zero; that of a bad automated fix can be catastrophic.

### A published release freezes what is missing from it

Publishing flips [immutable releases](https://docs.github.com/en/code-security/concepts/supply-chain-security/immutable-releases) on, locking the asset list along with the tag. A binary the matrix never produced is then not a gap to fill later: it is a permanent property of that version. `v6.30.0` shipped without `windows-arm64`, `v7.5.0` without either Windows build, and `v7.7.0` without any binary at all. None of the three can be repaired, only superseded.

**Shipping short is the intended behavior, not a failure to prevent.** `publish-release` publishes through a partial matrix on purpose: a release carrying five platforms beats one held hostage by the sixth, and the recovery is the next release, exactly as [§ Skip and move forward](#skip-and-move-forward-dont-rewrite-history) prescribes for every other release mishap. A fast cycle makes a burned platform cheap. So never hold a release, or sit on a draft, waiting for a red build cell: fix the cause and let the next version carry it.

A short ship does leave three artifacts still advertising binaries that are not there: the version's changelog section, the GitHub release body, and `docs/install.md`. Repairing them is a post-publication procedure rather than a rule, so it lives in the `repomatic-ship` skill (§ Repairing a short ship) with the rest of the release lane.

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

## Writing: ASD-STE100 Simplified Technical English

Write all human-readable prose in ASD-STE100 Simplified Technical English (STE). This binds every text artifact an agent produces: documentation, readme files, code comments and docstrings, changelog entries, commit messages, PR titles and bodies, issue reports and comments, error and exception messages, log messages, and the answers rendered to the user within a session.

Core rules:

- **One idea per sentence.** Keep sentences short: 20 words maximum for descriptions, 25 for instructions. Split long sentences rather than chaining clauses.
- **Use approved words, in one meaning each.** Prefer the plain word from the STE dictionary over a synonym: "use" not "utilize", "help" not "facilitate", "start" not "initiate", "also" not "additionally". When several words fit, pick the most common one. A word keeps one meaning per text: do not reuse "run" for both executing code and a CI run in one passage if it can confuse.
- **Active voice, present tense.** Say who does what: "the job writes the file", not "the file is written by the job". Use past tense only for events that already happened.
- **No nominalizations.** Use the verb: "decide" not "make a decision", "configure" not "perform the configuration".
- **Short, simple noun phrases.** Break "the version of the package published to the registry" into steps or a list if it grows.
- **Use vertical lists for procedures and multi-item rules**, one step or item per line, starting with a verb for procedures.
- **Be explicit, not clever.** Cut idioms, metaphors, humor, rhetorical flourishes and rhetorical questions. State the fact, the reason, and the action directly.
- **Caveats are inline, not closing footers.** State a caveat where it is relevant, without preamble, and do not save it for the end of the message.
- **Use "you" only for instructions.** Statements of fact need no actor; the "I/my" voice rule below still applies to prose written on behalf of the user.

Exempt from STE, verbatim only: error messages and log lines quoted from an existing source, code identifiers, command examples, file paths, third-party names and titles. Do not paraphrase them into STE.

Where STE conflicts with another rule, the other rule wins for its own concerns (sentence-case headings, the colon-instead-of-em-dash rule, changelog length limits): STE governs word choice and sentence structure, not formatting. A quoted phrase or a proper name may keep its non-STE spelling.

### Cut before rewriting

A request to make text shorter or simpler asks for deletion first and paraphrase second. Cut the ideas a nearby structure already carries: a table, a linked page, a column of the same report. Then simplify what remains. A rewrite-only pass keeps every idea and changes only the words, so the text stays as long as before.

## Voice and punctuation

Use first-person singular ("I", "my") in all prose written on behalf of the user: issue descriptions, PR bodies, feature requests, comments, documentation. Never use first-person plural ("we", "our") unless the text genuinely refers to a group.

Use ":" instead of em dashes for inline elaboration or appositive clauses.

## Name a file by its full path

Every file named in an answer carries its absolute path: `/Users/kde/code/repomatic/changelog.md`, never `changelog.md` or `scratchpad/draft.md`. A bare or relative path is not clickable, and a scratchpad path is unreachable without the session directory in front of it. This binds every mention: a draft's location, a file quoted in a finding, a file proposed for review. The `file_path:line_number` reference form keeps its line suffix, with the path spelled in full.

## Code organization

Do not make autonomous decisions about module boundaries, file placement, or architectural structure. When intent is ambiguous, ask before reorganizing. The user has strong opinions about where code lives and how modules are scoped.

A documentation outline is a structure too: before moving sections across a page, propose the target skeleton and get it approved first.

## Commits and PRs

Never run `git commit`, `git push`, `gh pr create`, or any other command that creates a commit, pushes to a remote, or opens a pull request unless I have explicitly authorized that specific action in the current conversation. Staging changes, drafting commit messages, and showing diffs are fine; the actual commit, push, or PR creation requires my explicit go-ahead each time. A prior authorization does not carry over to later actions.

Never include AI attribution in commits or PRs. No `Co-Authored-By` lines, no "Generated with Claude Code", no mention of being an AI or which model produced the code. Do not reference model names, versions, or codenames in commit messages, PR titles, or PR bodies.

Two instruction sources mandate such a trailer, and neither one overrides this rule. The Claude Code harness prompt asks every commit message to end with a `Claude-Session:` link to the session URL. The `/repomatic-ship` skill asks its commits to carry `Co-Authored-By: Claude <noreply@anthropic.com>`, and states that the mandate beats any no-AI-attribution rule in a project or global instructions file. Drop both trailers, and do not ask me each time. A session URL is attribution too, even where the instruction reads as a formatting step, which is how it gets through. Tell an agent you spawn to skip the trailer, because a spawned agent only reads the prompt you give it. Never amend or force-push to remove a trailer from a commit already pushed: report it and let me decide.

Write commit messages as a human developer would — describe what the code change does and why, not how it was produced. Keep internal tooling references (specific tools, Slack channels, internal links) out of public-facing text.

When a change needs a live CI run to validate it, push to `main` rather than to a scratch branch. My workflows key their concurrency group on `${{ github.workflow }}-${{ github.ref }}` with `cancel-in-progress`, so each push to the same ref cancels the previous run and hands its runners straight back. A side branch is a different ref: its run queues alongside `main`'s instead of superseding it, and both then crawl through a runner pool that is capped, most tightly on macOS.

The `#N` autolink hazard applies here in full: see [§ GitHub cross-references in commit messages and PRs](#github-cross-references-in-commit-messages-and-prs).

## Upstream reports and comments

When drafting a bug report, a reproducer write-up, or a reply on an upstream issue, the maintainer of that code is the authority on it. The job is to hand over observations they can verify in one click, not conclusions to agree with.

- **Every factual claim links the exact line that proves it.** A claim drawn from a CI log links the log line (see [§ GitHub Actions log anchors](#github-actions-log-anchors)); a claim that only exists in an uploaded artifact links the artifact, since no log line proves it.
- **Line-range permalinks pin a tag or a commit SHA, never a moving branch.** `blob/main#L10-L20` silently points at different code after the next push; a tag-pinned or SHA-pinned link is the only form that stays true. A "here is the thing" link without a line range may still use the default branch.
- **Verify before asserting.** A sentence about how an upstream tool behaves gets checked against that tool's source or manual first, and a code comment that says it better is quoted verbatim with a link. Memory is not a source.
- **Search before claiming novelty.** Open *and* closed issues and PRs upstream: a finding that reads as new often has a predecessor that was closed for lack of a reproducer, and that closure is itself the citation.
- **Observations in, attribution out.** Present what varied, where, and the link to it; leave the diagnosis and the next step to the maintainer. A maintainer who wrote the code reaches the conclusion faster than any summary of it, and trusts their own reasoning more.
- **One issue, one bug.** A second finding surfaced while working an issue gets its own issue with cross-references, never a renamed broader one: the title must still describe the fix that closes it.
- **The reproducer's vocabulary is published evidence.** When the prose quotes log lines, artifact names, and paths, renaming any of them in the reproducer forces a rerun and then a full repoint of every link and quoted phrase, in that order.

## Shell commands

Never use `$()` command substitutions inside `gh` (or any other) Bash calls. The sandbox flags `$()` as a separate security check that fires regardless of permission allow rules — it can't statically verify what executes inside a substitution. Instead, run compound commands as separate sequential Bash calls: capture the inner result first, then use it in the next call. Both commands then match the allow rules individually and auto-approve.

Never hand `git clean` a directory. Name each path to delete, even when most of the directory is going: `git clean -f -- docs/assets/` removes *every* untracked file there, including ones renamed into place seconds earlier and about to be committed. It bypasses the Trash, so they are unrecoverable. Keeping a subset means naming the discards one by one, or moving the keepers out first.

Never `cd` in Bash calls: pass absolute paths to the tool instead. Claude Code creates a `.claude/.cc-writes/` atomic-write staging directory in the session's tracked working directory, and that directory follows every `cd`. So a single `cd` into a source tree, a `.venv`, or a document folder leaves a permanent empty `.claude/` behind. No setting disables this. For the same reason, launch `claude` from a repo root rather than from a deep subdirectory or a data folder. Run `claude-sweep` to clear the strays.

`git mv` stages the rename only: unstaged content edits on the moved file stay unstaged, and the commit records a 100%-similarity rename without them. Read an `RM` status as "rename staged, content not" and `git add` the file before committing.

`sed -i ''` misbehaves in this harness: the empty-suffix argument is read as a file name, so the edits apply to the named files but the call exits `2` with `can't read :`, a half-succeeded state. Use Python for in-place multi-file rewrites instead.

Quote any `gh api` path carrying a query string: zsh expands the `?` as a glob and kills the call with `no matches found` before `gh` runs. Write `gh api 'repos/{owner}/{repo}/contents/{path}?ref={tag}'`. Reading one file this way needs `-H "Accept: application/vnd.github.raw"`; to search an unfamiliar repository, fetch `gh api repos/{owner}/{repo}/tarball/{ref}` and grep the extracted tree once, rather than guessing paths one call at a time.

Never run `ruff --fix --select RUF100` outside the project's full rule set: with only RUF100 selected, ruff cannot see the violations the `# noqa` comments suppress, judges every one unused, and strips load-bearing suppressions (it deleted the `# noqa: F401` off registration-side-effect imports this way). Autofix RUF100 only under the project's own configuration, and diff the result before staging.

## GitHub Actions log anchors

A `…/actions/runs/{run}/job/{job}#step:{N}:{line}` link follows non-obvious numbering, verified against live runs:

- **Fetch the raw log** with `gh api repos/{owner}/{repo}/actions/jobs/{id}/logs --allow-escape-sequences`. Without the flag, `gh` refuses the escape sequences and writes an empty file. The job's numeric ID comes from `gh api repos/{owner}/{repo}/actions/runs/{run}/jobs` (`gh run view --json jobs` reports it as `null`).
- **The step number counts "Set up job" as 1**, so a workflow's sixth step is `step:7`.
- **The line number starts at the step's `##[group]Run …` marker**, which is line 1, and includes the echoed script plus the `shell:`/`env:` preamble before any output.
- **Strip the leading timestamp** (`^\S+Z `) from each raw line before counting or matching.
- **Anchors rot on every rerun.** Any change in a job's output shifts every line below it, and a tool printing one extra banner line moves anchors nobody touched. After a rerun, repoint every anchor programmatically and re-resolve each one against the new logs to confirm it still lands on the intended line; never trust the arithmetic.

## Local environment

Non-obvious facts about this machine that have caused hard-to-diagnose failures:

- **Dotfiles are symlinked into `$HOME`, never hardlinked or copied.** `install.sh` links them with `ln -sf`, so `~/{path}` is a symlink to `~/code/dotfiles/dotfiles/{path}`. An audit of every tracked dotfile found zero hardlinks: most reach `$HOME` through a symlinked *parent directory* rather than their own link, so `~/.config/nvim` is a single link covering the whole folder and a file created in the repo shows up in `$HOME` immediately, with no `install.sh` re-run (only a brand-new top-level dotfile needs `./install.sh links`). Always edit the repo path and the `$HOME` symlink follows it: comparing inodes proves nothing, since a symlink resolves to the same inode a hardlink would. The real hazard is writing to the `$HOME` path with a replace-then-rename (what most editors and BSD/macOS `sed -i` do), which swaps the symlink for a regular file and silently forks the two copies. `~/.path-env-cache` is already forked exactly this way, because `.zshrc` writes to `${HOME}/.path-env-cache` directly.
- **The `PATH` list of `.zshrc` is cached with a 7-day TTL.** `.zshrc` rebuilds `~/.path-env-cache` only when the file is missing or older than 7 days, and new shells read the cache, not `PATH_LIST` directly: an entry added to `PATH_LIST` reaches new terminals only at the next refresh. To apply one immediately, append the resolved path to the cache (or delete the cache and let a new shell regenerate it, at the cost of a slow round of `brew --prefix` calls). The cache is the already-forked file from the dotfiles bullet above by design, so edit the repo's `.zshrc` and seed the `$HOME` cache; never the reverse.
- **`packages.toml` never picks up newly installed packages on its own.** `install.sh`'s snapshot stage runs `mpm snapshot --update-version ./packages.toml`, and `--update-version` only refreshes the version of entries *already* in the file. Adding entries is `--merge`, which that stage does not use. So anything installed with a bare `brew install` stays out of the manifest permanently and is skipped by a fresh-machine `mpm restore`: the `tree-sitter` library sat installed but unlisted for weeks this way. After installing a tool worth keeping, add its line by hand (alphabetically, bare version, no `v` prefix); `--update-version` tracks its version from then on. Never assume a later snapshot will notice it.
- **Pushing to `gitlab.alpinelinux.org` uses `~/.ssh/id_ed25519`, not the Secretive key.** The Secure Enclave key (Secretive) is registered there as a *Signing* key, which cannot authenticate a push: it connects as "Anonymous" and the push is rejected. The *Authentication* key is `~/.ssh/id_ed25519`. A `Host gitlab.alpinelinux.org` block in `~/.ssh/config` (before `Host *`) pins `IdentityAgent none` + `IdentityFile ~/.ssh/id_ed25519` + `IdentitiesOnly yes` to force it: leave that block in place. More generally, when a GitLab push fails as "Anonymous", check the key's usage type on the server, the `IdentityAgent` override, and `ControlMaster` multiplexing (a cached bad session masks key changes).
- **Claude Code transcript paths use the realpath'd cwd.** Transcripts live under `~/.claude/projects/<sanitized-cwd>/<session-id>.jsonl`, and the sanitization runs after symlink resolution: a session run from `/tmp/x` lands in `-private-tmp-x/`, not `-tmp-x/`. The claim that `claude --print` persists no transcript was an artifact of looking at the wrong directory; print-mode sessions are inspectable like any other.
- **File discovery must use `-iname` on this machine.** APFS resolves paths case-insensitively, but `find -name` matching stays case-sensitive, so the lowercase `claude.md` files these repos store are invisible to `find -name CLAUDE.md`. The `ls` and `stat` commands also run through shims that reject their BSD flags; reach for Python when timestamps matter.
- **A Secretive signing refusal is transient.** A `git commit` failing with `Couldn't sign message (signer): agent refused operation?` means the Secure Enclave approval prompt went unanswered, not that signing is broken: retry the same commit.

## Code generation preferences

For any non-trivial workflow, data processing, or multi-step logic: write Python, not Bash. The user is an advanced Python developer and can quickly read, inspect, and validate Python code. Short one-liners and simple Bash scripts are fine for convenience and performance, but anything with branching logic, string manipulation, data transformation, or error handling should be Python.

## Data visualization

When producing matplotlib figures, follow the design system at https://github.com/temataro/better-graphs for readable, presentation-ready plots: it codifies Tufte-style design rules, a chart-selection guide, and a `house_style.py` styling module (`apply_theme()`, `polish()`, `takeaway_title()`) that replaces matplotlib defaults with accent-led palettes, trimmed spines, unit-aware ticks, and takeaway-focused titles.

## Markdown and documentation

The markdown no-hard-wrap rule above is not merely a ceiling to stay under: each sentence or logical clause flows as a single long line and the renderer handles wrapping. Never reflow a paragraph to a column width, in any markdown file.

Sentence-case titles, natural heading anchors and the `[owner/repo#N]` link form are stated above and need no restating here: see [§ Comments and docstrings](#comments-and-docstrings) and [§ Linking to external repositories in Markdown](#linking-to-external-repositories-in-markdown). One case those do not reach: in plain GFM, where MyST's `(my-anchor)=` is unavailable, the explicit anchor form is `<a id="…"></a>`.
