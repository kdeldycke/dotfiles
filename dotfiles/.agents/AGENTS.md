@~/.claude/tropes.md

## Consuming repomatic

<!-- audience: downstream -->

### Upstream conventions

<!-- audience: downstream -->

This repository takes its reusable workflows and much of its `pyproject.toml` configuration from [`kdeldycke/repomatic`](https://github.com/kdeldycke/repomatic), and follows the conventions established there. Every tagged section in this file is pushed from upstream and is the canonical form of a shared rule: edit it there, not here, or the next sync overwrites the edit. A section this repository wrote for itself carries no tag and survives every sync untouched.

**Contributing upstream:** propose a gap or improvement in the reusable workflows, the `repomatic` CLI, or a shared convention at [`kdeldycke/repomatic`](https://github.com/kdeldycke/repomatic/issues). Landing it upstream is what carries it to every other repository consuming it, instead of fixing it once here.

### Managed versus downstream-owned workflow content

<!-- audience: downstream -->

A generated workflow file has two parts. The first job is the **managed thin caller**, delegating to a reusable upstream workflow through a SHA-pinned `uses:`. It is rebuilt from scratch on every sync, so a hand edit to it is lost. Everything declared *after* it is **downstream-owned**: the sync slices the file at the end of the managed job body and carries the remaining text through verbatim, comments and blank lines included.

Position alone does not settle ownership: a multi-job caller declares canonical jobs after its first one, and those are regenerated too. Write a comment above your first downstream job saying so. The sync preserves it like any other extra content but never writes one itself, so its absence means the file has nothing in it that is yours to edit.

A fragment that is only comments and blank lines is still carried over, and deliberately does not count as a downstream job for the rule below.

### The permissions contract is generated, not hand-written

<!-- audience: downstream -->

<!-- supersedes: Known lint warning: top-level workflow permissions -->

When a workflow file carries downstream-owned jobs, the sync emits a top-level `permissions: {}` **and** the scopes the reusable workflow needs on the managed caller job. Both halves ship together, and neither is written by hand: a top-level `{}` on its own starves the managed call, which GitHub aborts at startup the moment a nested job asks for a scope the caller never granted.

So a `lint-repo` complaint about a missing top-level `permissions` key is a signal to re-run the sync, not to add the key yourself. Declare least privilege per job on the downstream-owned jobs instead, which is the half no sync rewrites.

### Bumping the repomatic pin

<!-- audience: downstream -->

Regenerate rather than search-and-replace, so codegen changes (new job permissions, reshaped triggers) arrive with the version bump instead of a release behind it:

```shell-session
$ uvx --no-progress 'repomatic==X.Y.Z' init workflows/autofix.yaml workflows/lint.yaml
```

Name the components explicitly. A bare `repomatic init` also materializes whatever else is in scope for the repository (labels config, a changelog), and an unqualified `workflows` selector bypasses scope gating.

Read the release notes for breaking changes needing a manual follow-up. A renamed autofix job is the recurring one: its old PR branch stays open, attached to a job that no longer exists.

### Tools called from workflows are version-pinned

<!-- audience: downstream -->

Every external tool a workflow invokes carries an exact version literal, in one of the shapes `sync-workflow-pins` recognizes: an action `uses:` ref, `uvx '{pkg}=={X.Y.Z}'` and the `--with` form for PyPI, `npm install {pkg}@{X.Y.Z}` for npm, and the `version:` input on `astral-sh/setup-uv`. That job resolves each to the newest release past `minimum-release-age` and opens a pull request. A tool invoked unpinned floats to the newest release on every run, outside the window entirely: see [§ Live registries with no cooldown knob](#live-registries-with-no-cooldown-knob).

A tool the runner image happens to provide is worse than an unpinned install, because it carries no version anywhere in the repository for anything to bump. Reach for a pinned dependency that already does the job instead of finding a way to pin the tool.

### PAT-gated checks degrade, they do not fail

<!-- audience: downstream -->

<!-- supersedes: `REPOMATIC_PAT` needs `Administration: Read-only` -->

Several `lint-repo` checks read GitHub API endpoints needing a scope on `REPOMATIC_PAT`. When the token lacks one, or the call fails for any other reason, the check returns an *indeterminate* result and is reported as skipped: it never fails the job. A missing scope costs coverage, not a red run, which is [§ Defensive workflow design](#defensive-workflow-design) applied to the audit lane.

Do not read a skipped check as a passing one. The setup-guide issue carries the pre-filled link for regenerating the token with the scopes a repository's own checks want.

### Configuration repomatic reads

<!-- audience: downstream -->

`[tool.repomatic]` in `pyproject.toml` belongs to the repository and is authoritative for every feature flag. The tool sections synced from repomatic's bundled templates are not: a local edit to a key the template owns is re-applied on the next sync, so put a deviation behind a `[tool.repomatic]` setting rather than editing the synced value and expecting it to hold.

The sync grafts rather than overwrites. A key the template does not define survives verbatim, a table present in both is merged so local sub-keys are kept, and an array gains its local-only items after the template's. Only a scalar the template also defines is overwritten, which is the point of an ongoing sync. Comments on a grafted node carry over; a comment beside a key the template owns does not, so record why a local entry exists somewhere the merge cannot reach.

## Cooldown on every install

<!-- audience: all -->

**Every command that resolves a package from a live registry carries a cooldown, except where this section names otherwise.** A cooldown refuses any version published more recently than a fixed window, so a compromised release has to survive that window before it can enter a build. Most malicious releases (stolen publishing credentials, dependency confusion, account takeover) are [caught and pulled within days of publication](https://blog.yossarian.net/2025/11/21/We-should-all-be-using-dependency-cooldowns), which is what makes a window of days worth the delay it costs.

The rule has **no scratch exemption**. It binds reusable workflows, one-off CI steps, test scripts, local reproduction commands, and throwaway experiments equally: an uncooled `uvx` in a five-minute debugging step resolves the same tree from the same registry onto the same runner as a production job. If you type an install command, it carries the cooldown. The exceptions are the three [documented exemptions](#documented-exemptions) below, and nothing else.

### A cooldown is not a hash

<!-- audience: all -->

The two guarantees are independent, and most of what CI installs has only one of them. Know which you are relying on before calling something verified.

| Guarantee    | What it proves                                                      | Where this repo has it                                                   |
| :----------- | :------------------------------------------------------------------ | :----------------------------------------------------------------------- |
| **Cooldown** | The version has been public long enough for a compromise to surface | Every `uvx`, `uv pip`, `uv tool`, `npm` and `npx` invocation, whole tree |
| **Pin**      | Everyone resolves the same version                                  | Action SHAs, workflow version literals, `repomatic run` tools, `uv.lock` |
| **Checksum** | The bytes are the bytes that version shipped                        | `repomatic run` binary tools, `uv.lock` hashes, digest-pinned containers |

The gap worth naming: a `uvx`-resolved tree is gated by publication age but **never checked against a known digest**, because a `uvx` environment has no lockfile. That covers every uvx-backed `repomatic run` tool, and every `uvx 'repomatic==X.Y.Z' …` call a downstream repo inherits from a frozen workflow. `uv.lock` is the only place a Python dependency is hash-pinned, so anything resolved outside it trades hash verification for the cooldown alone.

This is why workflows on `main` run the CLI as `uv --no-progress run --frozen -- repomatic`, from the lockfile, rather than resolving it fresh: see {data}`repomatic.prepare_release.LOCAL_CLI_INVOCATION`. Beyond the stronger guarantee, an index resolution can be made *unsatisfiable* by the cooldown while a lockfile cannot: raising a dependency floor onto a release younger than the window leaves `uvx` with no version to pick and nowhere to record an exemption, since it reads neither `uv.lock` nor *any* project configuration: neither `[tool.uv] exclude-newer-package` in `pyproject.toml` nor a `uv.toml` sitting beside it, and uv exposes no environment variable for a per-package bypass. See [§ Per-ecosystem knobs](#per-ecosystem-knobs) for what that leaves reachable.

Running from the lockfile insulates this repository from that, which creates its own hazard: **a floor inside the window is now invisible here and breaks only the people installing the release** (downstream repos running a frozen workflow's `uvx 'repomatic==X.Y.Z'`, and `uvx repomatic` users). `tests/test_dep_sources.py` is what catches it, so treat that test failing as "this release is not shippable yet", not as a local annoyance to wait out.

Prefer a binary from the tool registry when one exists: it is the only path that carries all three at once. When adding a tool that repomatic shells out to, register it and reach it through {func}`repomatic.tool_runner.ensure_binary` rather than `$PATH`, which carries none of the three.

### Where the window comes from

<!-- audience: all -->

`[tool.repomatic] minimum-release-age` (default `1 week`) is the single source of truth. Never hard-code a duration next to an install command: read it from config, or from the `npm_min_release_age_days` output `repomatic metadata` derives from it.

Two files carry the duration as a literal instead, and both are pinned back to that source by a conformance test rather than trusted:

- **Every workflow**, because YAML cannot read Python: each sets `UV_EXCLUDE_NEWER` and `NPM_CONFIG_MIN_RELEASE_AGE` in a **workflow-level `env:` block**, rendered by `cooldown_env_block()` and asserted verbatim by `tests/test_workflows.py`. Job-level `env:` would let the value come from the `metadata` job, but it cannot cover the bootstrap: `metadata` resolves packages before any other job's output exists, and a workflow-level `env:` block cannot reference `needs`. The literal covers every job, including that bootstrap and any step added later by someone who never read this section.
- **`[tool.uv] exclude-newer`**, in this repo's `pyproject.toml` and in the bundled `repomatic/data/uv.toml`, because uv reads its own config and knows nothing of `[tool.repomatic]`. `tests/test_uv.py` asserts both equal `minimum-release-age`. They must not merely be *close*: a lock window wider than the install window resolves versions those installs then refuse, leaving a package pinned in `uv.lock` that CI cannot install.

That makes the cooldown the one place an environment variable beats an explicit flag, inverting [§ uv flags in CI workflows](#uv-flags-in-ci-workflows): a flag only protects the command someone remembered to write it on, and the commands that most need protecting are the ones nobody thought about.

A command that resolves against a checked-in lockfile is the exception that needs the flag *back*. `uv lock` and `uv sync` are governed by the project's own `[tool.uv] exclude-newer`, and an ambient `UV_EXCLUDE_NEWER` silently overrides it, so CI would lock to a different window than a developer running the same command. `sync-uv-lock` therefore passes `--exclude-newer` explicitly, sourced from `[tool.uv]`: a CLI flag outranks the environment.

### Per-ecosystem knobs

<!-- audience: all -->

| Ecosystem                                                                             | Cooldown                                                           | Per-package exemption                                   |
| :------------------------------------------------------------------------------------ | :----------------------------------------------------------------- | :------------------------------------------------------ |
| uv: `uvx`, `uv pip install`, `uv run --with`, `uv tool install`, `uv lock`, `uv sync` | `--exclude-newer`, or `UV_EXCLUDE_NEWER`                           | `--exclude-newer-package pkg=YYYY-MM-DD`, CLI flag only |
| npm, `npx`                                                                            | `--min-release-age` in whole days, or `NPM_CONFIG_MIN_RELEASE_AGE` | `--min-release-age-exclude` taking a name or glob       |
| A tool in the `repomatic run` registry                                                | applied by the runner                                              | n/a                                                     |

uv accepts a friendly duration (`1 week`), an ISO 8601 span (`P7D`), or an absolute date; npm counts whole days and needs 11.10.0 or newer. Both knobs gate the whole resolved tree, transitive dependencies included, which is the point: the compromised package is rarely the one named on the command line. An *exemption* does not inherit that reach: exempting a package leaves its own dependencies gated, so a bypass reaching a fresh release usually has to name the transitive closure that release pulled in, one round-trip at a time.

"CLI flag only" in that table is literal, and it is what forces every per-package bypass in this repository onto a command line ({data}`repomatic.prepare_release.SELF_PIN_COOLDOWN_EXEMPTION`) rather than into one central declaration. Verified against uv `0.12.3`: under an ambient `UV_EXCLUDE_NEWER`, a `uvx` resolution fails byte-identically whether the exemption sits in `[tool.uv]`, in an adjacent `uv.toml`, or nowhere at all. The one knob that does reach it is `--config-file` / `UV_CONFIG_FILE`, rejected here because it **replaces** discovered configuration instead of merging with it: setting it for a whole CI environment silently drops `required-version`, `exclude-newer`, `dependency-groups` and `build-backend` from every *other* uv command in that environment, so making it safe means maintaining a complete mirror of `[tool.uv]` where a newly added key nobody remembers to mirror fails silently. Upstream: the `UV_EXCLUDE_NEWER_PACKAGE` ask is [astral-sh/uv#20995](https://github.com/astral-sh/uv/issues/20995), glob exemptions are [astral-sh/uv#20788](https://github.com/astral-sh/uv/issues/20788), and pin-based bypasses are [astral-sh/uv#19864](https://github.com/astral-sh/uv/issues/19864) with [astral-sh/uv#18921](https://github.com/astral-sh/uv/pull/18921). Revisit this paragraph when one of them lands.

A cooldown-filtered resolution is not a dependency conflict, and uv now says so: [astral-sh/uv#5878](https://github.com/astral-sh/uv/issues/5878) shipped a `hint:` naming the filtered package, the cutoff it hit, and the version it would otherwise have picked. Read that hint before diagnosing a "No solution found" as a real conflict. There is still no distinct exit code or error kind, so nothing automated can tell the two apart.

For any other package manager, consult [meta-package-manager's cooldown inventory](https://kdeldycke.github.io/meta-package-manager/cooldown.html#supported-managers) for which of them enforce a cooldown natively, which have support proposed upstream, which have none, and which are marked N/A because their archive already stages releases on its own. It tracks the capability across every manager mpm drives and stays fresher than a table copied into this file. Read the N/A verdict as "different threat model", not "gap": see [§ Distro archives are out of scope](#distro-archives-are-out-of-scope-not-an-exception).

### Live registries with no cooldown knob

<!-- audience: all -->

Fail closed. When a *live registry* client has no cooldown knob, do not hand it a floating version range. Either pin an exact version that a cooldown-gated updater already vetted (`sync-action-pins`, `sync-tool-versions` and `sync-workflow-pins` all apply `minimum-release-age` before proposing a bump), or route the install through a client that has one. An unpinned install against a self-service registry is the exact thing this rule exists to prevent.

Check the [inventory](https://kdeldycke.github.io/meta-package-manager/cooldown.html#supported-managers) before concluding a client is knob-less, because they keep gaining one: `pip` grew `--uploaded-prior-to` / `PIP_UPLOADED_PRIOR_TO` in `26.1`, and `pipx` inherits it from the pip inside each venv it manages. A knob with a version floor also fails *open* on older releases, quietly ignoring the flag rather than erroring, so pair it with a floor check the way `repomatic run` does for npm (`NPM_MIN_VERSION_FOR_COOLDOWN`).

### Distro archives are out of scope, not an exception

<!-- audience: all -->

`apt` and its peers are **not** live registries, and this rule was never about them. A stable archive is frozen at release and moves only through the distro's own staging: Debian's migration windows are a cooldown, implemented one layer down and measured in weeks rather than days. Nobody self-publishes into it, which is the property the window exists to compensate for everywhere else.

A second reason the knob could not exist even if someone wanted it: a distro version string is *the maintainer's package build*, not an upstream publish date, so a publish-date filter has nothing to filter on. mpm's inventory files these managers as **N/A** rather than unsupported for exactly this reason: the ecosystem solves the problem differently, it is not missing a solution.

**The exception is a repository you add yourself.** A PPA or a vendor's `.repo` file is a live, single-publisher registry wearing apt's clothes, with none of the distro staging behind it. Pin the version there, or fetch a checksummed artifact instead. `_release-engine.yaml` used to add the `cli.github.com` RPM repo to reach `gh` inside the build container; now that `gh` ships from the tool registry, no such hand-added repository remains in this codebase, which is the better fix whenever a registry binary exists.

Still prefer the tool registry over `apt-get` when both can supply a binary (`shfmt`, `actionlint`, `biome`, `gitleaks`, `lychee`, `typos`), for reasons that have nothing to do with cooldowns: the registry version is pinned, checksum verified, and identical on every runner and every developer machine, where the archive gives each distro release whatever it happens to hold. For a tool a *plugin* shells out to rather than imports, declare it in the plugin host's `path_tools` (`mdformat` does this for `shfmt`) instead of installing it beside the job.

Write the `apt-get` calls you do keep so they pull as little as possible:

- **`apt-get`, never `apt`.** The `apt(8)` man page says to prefer `apt-get` and `apt-cache` in scripts, as they keep backward compatibility; `apt` is an end-user tool whose behavior may change between versions.
- **`--no-install-recommends` always.** Recommends are extra packages nobody asked for, and every one widens what a step installs beyond what it names.
- **Name what the Recommends were providing.** Dropping them can quietly remove something real (graphviz recommends `fonts-liberation`, which a base image may not ship on its own), so add it to the install list explicitly. An explicit dependency you can read beats an implicit one you inherit.

### Documented exemptions

<!-- audience: all -->

Three installs deliberately bypass the window. The first two are per-package and never widen to the rest of the tree; the third is a whole job, and says why it has to be.

- **The upstream toolkit's own pin.** `repomatic` runs from a pin that moves in lockstep with the `uses:` refs pointing at it, so a release must be installable the minute it is published or every downstream repo breaks until the window elapses. The release freeze emits an `--exclude-newer-package` escape hatch beside the pin it writes.
- **A security fix still inside the window.** `audit --fix` reaches a CVE fix through an `exclude-newer-package` entry rather than lifting `exclude-newer` for everything.
- **The `test-package-install` job.** Its subject *is* the freshly published artifact, so a cooldown would make the question it exists to answer unanswerable. Scoping the opt-out to one job is what keeps it honest: it holds no secrets, inherits `permissions: {}`, and only runs `--version` on a throwaway runner.

A fourth exemption is a bug until proven otherwise. Anything claiming one carries a comment naming what breaks without it, and the narrowest scope that still works: a package, not a job; a job, not a workflow.

That inventory is this repository's own. A downstream repo runs the same rule against its own, which is usually empty. One category recurs and is worth naming, because it reads like a violation and is not: a dependency the same maintainer publishes. The window guards against a compromised upstream, and here the publisher and the consumer are the same person, so it buys nothing while holding each release back a week from the only repository that consumes it. Exempt it per-package, with a zero span rather than a fixed date so the next release is picked up without editing the file, and put the reasoning beside it:

```toml
[tool.uv]
# apricot is published by this repository's own maintainer: the cooldown guards
# against a compromised upstream, which does not apply here, and it otherwise
# holds each release back a week from the one repository that consumes it.
exclude-newer-package = { apricot = "0 days" }
```

Declaring it in `pyproject.toml` rather than in a machine's `~/.config/uv/uv.toml` is what makes a fresh clone resolve the same way, and keeps the exemption reviewable in a diff. It stays a bypass and not a hole: the transitive tree that release pulls in is still gated, and that tree is the part the maintainer did not publish.

## A floor comment justifies one version

<!-- audience: all -->

Every version floor carries a comment above it saying what breaks below that version and where the project would notice. That comment documents **the floor as it stands**, in one short paragraph. It is not a log of how the floor got there.

The failure mode is additive and slow. A floor bump arrives, whoever writes it appends a paragraph about the new version, and nobody deletes the paragraph about the old one, since deleting text that reads as informative feels like losing something. Repeat over a few years and the comment is a private changelog of the dependency, with the declared version buried under the floors it replaced. `meta-package-manager`'s `click-extra` entry reached 676 words that way, walking back through eight superseded floors before reaching the dependency itself.

So when you raise a floor, **rewrite the comment, don't extend it**:

- **Keep** what the newly required version buys, named concretely enough to check: the API, the fix, the `requires-python` alignment, plus the call site or module that consumes it. A CVE identifier or upstream issue reference is part of that claim, not history.
- **Delete** every superseded floor. A version no longer declared cannot break anything for a reader running the declared one, and `git log -- pyproject.toml` and `git blame` hold that story for whoever wants it.
- **Move out** anything that is not about *this* floor: how the dependency is used across the codebase belongs in the module that uses it, and a comparison against an alternative package belongs in `docs/` or an `XXX` pointer to the upstream ticket.

`lint-deps` warns (without failing) on any floor comment over `[tool.repomatic] lint-deps.comment-word-threshold` words, 40 by default: the same ceiling as a changelog bullet, for the same reason. Both are read by someone who came for one fact. A comment past that ceiling is either narrating history (cut it) or documenting two things (one of them belongs elsewhere).

## Documentation requirements

<!-- audience: all -->

### Section audience tags

<!-- audience: all -->

Every heading below carries an HTML comment declaring who the section is written for. The tag is what lets `repomatic init` push the right subset into each repo, `lint-repo` report drift on what it pushed, and `repomatic-audit` tell a managed section from a repo-owned one without fetching upstream.

| Tag                             | Reaches                                                               |
| :------------------------------ | :-------------------------------------------------------------------- |
| `<!-- audience: all -->`        | This repository and every downstream repo.                            |
| `<!-- audience: upstream -->`   | `kdeldycke/repomatic` only. Never deployed.                           |
| `<!-- audience: downstream -->` | Repos consuming repomatic; not repomatic itself, which consumes none. |

A `; scope:` qualifier narrows an audience to a repository type, mirroring {class}`~repomatic.registry.RepoScope`. Only `package` is defined so far (`<!-- audience: all; scope: package -->`), covering the release lane: it skips a uv virtual project, which locks and tests like any Python repo but has nothing to publish, tag or write release notes for. A `python` scope is deliberately absent while every repo in the set is Python, since it would ship with no members distinct from the default.

Two rules hold the tags together, both enforced by `tests/test_agent_md.py`:

- **Every section is tagged.** An untagged heading has no declared reach, so a sync cannot place it and a reader cannot tell whether it binds them.
- **A subsection never reaches wider than its parent.** An `all` section under an `upstream` heading would deploy with no heading above it, arriving as an orphan under whatever section precedes it.

A section a downstream repo wrote for itself carries no tag and is never touched: the sync owns the tagged sections and nothing else.

**Renaming a managed section is a migration, not an edit.** The merge keys on the heading title, so a rename strands the old section downstream, where it sits beside its own replacement contradicting it. Declare the old title on the section that replaces it, one comment per title:

```markdown
### PAT-gated checks degrade, they do not fail

<!-- audience: downstream -->

<!-- supersedes: `REPOMATIC_PAT` needs `Administration: Read-only` -->
```

The same reasoning that makes a label rename beat a delete-and-recreate, and the same one-way direction: a superseded title is claimed and dropped wherever it is found, so it must not also name a section that is still live. Adding a `supersedes:` for a title that never shipped is harmless, and cheaper than discovering the orphan in six repositories a year later.

### Keeping `claude.md` lean

<!-- audience: all -->

`claude.md` must contain only conventions, policies, rationale, and non-obvious rules Claude cannot discover by reading the codebase. Actively remove:

- **Structural inventories**: project trees, module tables, workflow lists. Discoverable via `Glob`/`Read`.
- **Code examples that duplicate source files**: YAML snippets copied from workflows, patterns visible in every module. Reference the source instead.
- **General programming knowledge**: standard idioms, well-known library usage, tool descriptions derivable from imports.
- **Implementation details readable from code**: what a function does. Only the *rationale* for non-obvious choices belongs here.

### Knowledge placement

<!-- audience: all -->

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

<!-- audience: all -->

Document design decisions, trade-offs, and non-obvious choices in the code: MyST docstring admonitions (```` ```{warning} ````, ```` ```{note} ````, ```` ```{caution} ````), inline comments, and module-level docstrings for constants that need context.

### Example data

<!-- audience: all -->

Example data everywhere (docs, docstrings, comments, workflows, fixtures) must be domain-neutral: cities, weather, fruits, animals, recipes. Do not reference the project, software engineering concepts, or package metadata. The reader should understand the example without knowing what the project is.

## File naming conventions

<!-- audience: all -->

### Extensions: prefer long form

<!-- audience: all -->

Use the longest, most explicit file extension. For YAML, `.yaml` (not `.yml`); likewise `.html` not `.htm`, `.jpeg` not `.jpg`.

### Filenames: lowercase

<!-- audience: all -->

Use lowercase filenames everywhere. Avoid shouting-case names like `FUNDING.YML` or `README.MD`.

### GitHub exceptions

<!-- audience: all -->

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

<!-- audience: all -->

### Terminology and spelling

<!-- audience: all -->

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

<!-- audience: all -->

The version string is always bare (`1.2.3`). The `v` prefix is a **tag namespace**: it only appears when the reference is to a git tag or something derived from one (action ref, comparison URL, commit message). This aligns with PEP 440, PyPI, and semver.

**Rules:**

1. **No `v` prefix on package versions.** Where the version identifies the *package* (PyPI, changelog heading, CLI output, `pyproject.toml`), use the bare version: `1.2.3`.
2. **`v` prefix on tag references.** Where the version identifies a *git tag* (comparison URLs, action refs, commit messages, PR titles), use `v1.2.3`.
3. **Always backtick-escape versions in prose.** Both `v1.2.3` and `1.2.3` are identifiers: wrap them in single backticks.
4. **Development versions** follow PEP 440: `1.2.3.dev0` with optional `+{short_sha}` local identifier.

### Commit messages

<!-- audience: all -->

**Default to a subject line and nothing else, when there is no context to link.** Measured across this repository's history, 93% of hand-written commits are subject-only, and of the few carrying a body, 77% hold it to one paragraph. A commit message is a log entry, not a design document.

- **Subject.** One line under 72 characters, imperative mood, capitalized, no trailing period, every identifier backticked. Name what you changed, not the category it falls in: `` Sync `uv.lock` ``, `Fix vulnerable dependencies`, `` Fix `sync-mailmap` crash on a missing file ``. This is the shape the automation already emits, since no PR template sets a `commit_message:` and each one's `title:` becomes the commit subject.
- **Avoid the bare one-word subject.** `Typo`, `Lint`, `Fix` and friends are common in the older history and are the habit to break, not a pattern to copy: they cost the next reader a `git show` to learn anything. Say what the typo was in, what the lint fixed.
- **No decorative prefixes.** This is not [Conventional Commits](https://www.conventionalcommits.org): no `feat:`, `chore:`, `fix:`. **A `[bracketed]` prefix is reserved for a load-bearing mechanism that parses it back**, never for decoration or categorization: before writing one, name the code that reads it. Only `[changelog] …` qualifies here, and it is an invariant, not a convention: every machine-authored version-machinery commit (release freeze, post-release bump, manual major/minor bumps) starts with {data}`repomatic.git_ops.CHANGELOG_COMMIT_PREFIX`, which lets workflow gates skip machinery pushes on that single prefix instead of enumerating message shapes. `tests/test_workflows.py::test_changelog_prefix_is_the_machinery_invariant` holds the prefix set, the gates, and the emitting template together; the auto-tagging job matches {data}`repomatic.git_ops.RELEASE_COMMIT_PATTERN` within the same family. Never write a GitHub skip token (`[skip ci]` and its four aliases) in any message, including a body: they match anywhere and leave the required check "Pending" rather than failing. [`docs/commit-messages.md`](https://repomatic.net/commit-messages) inventories which tools read and write commit messages; `tests/test_pr_body.py` enforces both rules over every template.
- **Body: link the context.** Omit it when the subject says everything. Write one short paragraph when the *why* is not evident from the diff, and especially when there is a **public place where the decision was made**: the upstream issue or PR, a commit in another repository, the spec or documentation page that forced the behavior, the discussion thread. Point at the commit this reverts or follows up on, and cross-reference internal issues and PRs the same way. Forges render commit messages as HTML, so a link is the cheapest route from `git log` to the full story: this is where accountability and traceability actually live. Format every reference per [§ GitHub cross-references in commit messages and PRs](#github-cross-references-in-commit-messages-and-prs).

Never narrate the work in sequence or enumerate the files touched: `git log --stat` lists the files and the diff shows the order. Rationale needing more room than a paragraph belongs somewhere durable instead: a code comment, a docstring, `docs/`, or the PR body.

### GitHub cross-references in commit messages and PRs

<!-- audience: all -->

Never write `#N` (a literal `#` followed by a number) in commit messages, PR titles, or PR bodies unless N is an actual issue/PR number in the target repo. GitHub auto-links every `#N`, so positional refs like `test #1` render as misleading cross-references. Use plain numbers (`test 1`, `tests 14 and 15`), backtick-quote a slot identifier (`` test `1` ``), or rephrase (`the first test`).

### Linking to external repositories in Markdown

<!-- audience: all -->

In Markdown (changelog, `readme.md`, `docs/`, issue and PR bodies), link to another repository using GitHub's reference slug as the link text, not the raw URL:

- Issue or PR: `[owner/repo#N](https://github.com/owner/repo/issues/N)`. Issues and PRs share one number space; pick `/issues/N` or `/pull/N` to match the real type (GitHub redirects either way).
- Commit: `[owner/repo@shortsha](https://github.com/owner/repo/commit/fullsha)`.
- Repository homepage: `[owner/repo](https://github.com/owner/repo)`.

GitHub autolinks the bare `owner/repo#N` form only inside conversations (issues, PRs, commit messages), never in committed files, so the explicit link is what renders the compact slug in a Markdown file. Same-repo references drop the slug: `[#N](…/issues/N)`.

### Comments and docstrings

<!-- audience: all -->

- All comments in Python files must end with a period.
- Docstrings use MyST markdown (single-backtick inline code, `[text](url)` links, `` {role}`target` `` cross-references, ```` ```{directive} ```` admonitions); `click_extra.sphinx.myst_docstrings` converts to reST at build time. For Sphinx operational detail (fence style, `click-extra convert-to-myst`, page rosters, `conf.py` hygiene), see `.claude/agents/sphinx-docs.md`.
- **No Google-style docstring sections** (`Args:`, `Returns:`, `Raises:`, …; no `sphinx.ext.napoleon`). Use reST field lists: `:param name:`, `:return:` (not `:returns:`), `:raises ExceptionType:`. Markers pass through unchanged; their content is MyST-converted, and continuation lines indent to align with the description above.
- **Dataclass field docs:** attribute docstrings (a string literal immediately after the field), not `:param:` entries; the class docstring is for the class purpose only.
- **CLI help text:** Click renders docstrings as plain text in `--help`, so avoid MyST markup in Click command docstrings.
- Documentation in `./docs/` uses MyST markdown where possible.
- Keep Python lines within 88 characters (ruff default). Markdown has no line-length limit: do not hard-wrap prose.
- Titles in markdown use sentence case.
- **Heading anchors:** use the natural auto-generated anchor for cross-references; add explicit MyST anchors (`(my-anchor)=`) only when the natural one is unavailable (duplicate headings, non-heading targets).

### `__init__.py` files

<!-- audience: all -->

Keep `__init__.py` minimal (easy to overlook): no logic, constants, or re-exports. Acceptable: license headers, package docstrings, `from __future__ import annotations`, `__version__`. Anything else belongs in a named module.

### Imports

<!-- audience: all -->

- Import from the root package (`from {package} import cli`), not submodules, when possible.
- Imports go at the top of the file unless avoiding circular imports. **Never use local imports inside functions**: they hide dependencies and bypass ruff's import sorting.
- **Version-dependent imports** (like a `tomllib` fallback for Python 3.10) go after all normal imports but before the `TYPE_CHECKING` block, so ruff can sort the normal imports above.

### `TYPE_CHECKING` block

<!-- audience: all -->

Place a module-level `TYPE_CHECKING` block after all imports (including version-dependent ones). Use `TYPE_CHECKING = False` (not `from typing import TYPE_CHECKING`) to avoid importing `typing` at runtime. **Only add it when there is a corresponding `if TYPE_CHECKING:` block**: a bare assignment with no consumer is dead code, so if all type-checking imports are removed, remove the assignment too.

### Modern `typing` practices

<!-- audience: all -->

Use `collections.abc` and built-in types instead of `typing` imports; `X | Y` not `Union`, `X | None` not `Optional`. New modules include `from __future__ import annotations` ([PEP 563](https://peps.python.org/pep-0563/)).

### Minimal inline type annotations

<!-- audience: all -->

Omit annotations on locals, loop variables, and assignments when mypy can infer from the right-hand side. Add one only when mypy errors (empty collections needing an element type like `items: list[Package] = []`, ambiguous `None` init, unions mypy can't narrow). Always annotate function parameters and return types.

### Python 3.10 compatibility

<!-- audience: all -->

Project supports Python 3.10+. Unavailable syntax: multi-line f-string expressions (3.12+; split into concatenated strings), exception groups / `except*` (3.11+), `Self` type hint (3.11+; use `from typing_extensions import Self`).

### YAML workflows

<!-- audience: all -->

Single-line commands: plain inline `run:`. Multi-line: the folded block scalar (`>`), which joins lines with spaces (no backslash continuations); use the literal scalar (`|`) only when preserved newlines are required (multi-statement scripts, heredocs).

YAML lines may run to 120 characters (`yamllint.yaml` sets `line-length: max: 120`): don't carry over Python's 88-char limit. The same limit governs generated downstream workflows, so codegen-source comments (like `release.yaml`'s `publish-pypi` job) should fill to 120 too.

Jobs run on a test-matrix runner (`ubuntu-26.04` for the x86 default), and downstream workflows inherit it. Never reach for a `-latest` alias: GitHub repoints those without a commit to review, and `lint-repo` rejects them.

### Naming conventions for automated operations

<!-- audience: all -->

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
3. **All four dimensions must agree.** A file-modifying operation uses one `verb-noun` for CLI command, workflow job ID, PR branch, and PR body template (`sync-gitignore` everywhere). Operations that write no repository file use only the CLI command and job ID: `lint-*`, which reads, `pack-*`, which emits a build artifact, and the bare-noun issue trackers of rule 9. Two exceptions: release-lane recording (`scan-virustotal` and the `sync-binaries` catalog it commits) has no PR branch or template because it pushes directly to the default branch, disableable via `[tool.repomatic] binaries.sync`, see [§ Release-lane direct commits](https://repomatic.net/operation-contracts#release-lane-direct-commits); and `fix-awesome-toc` runs as a step of `format-markdown` because it corrects what that job just wrote and the two would otherwise fight across separate PRs, see [§ Fix steps inside another job](https://repomatic.net/operation-contracts#fix-steps-inside-another-job). A job local to this repository (one with no upstream template to name on `pr-body --template`) keeps the same identity: its template is `.github/pr-templates/{job-id}.md`, passed with `--template-file`, and `repomatic lint-repo` flags one placed elsewhere. See [§ Repository-local templates](https://repomatic.net/operation-contracts#repository-local-templates).
4. **Function names follow the CLI name** (`sync_gitignore` for `sync-gitignore`). On collision with an imported module, use the Click `name=` parameter (`@repomatic.command(name="update-dep-graph")` on `dep_graph`) or append `_cmd` (`sync_uv_lock_cmd`).
5. **A read-only command may expose mutation via `--fix`.** When a query command (like `audit`) gains a `--fix` autofix mode, the autofix operation keeps its own `fix-X` job ID, PR branch, and template and invokes `<command> --fix` (`fix-vulnerable-deps` runs `audit --fix`). That command name is then exempt from rule 3: it is a general-purpose query command (like `metadata`), not the operation's namesake.
6. **`dep` when attributive, `deps` when the object.** A "dep" prefix modifying another noun stays singular, following English compound-noun convention (`dep-graph`, `dep-sources`, `dep_report.py`); "deps" appears only where the dependencies are themselves the object of the verb (`sync-deps`, `vulnerable-deps`).
7. **A sample accrues where a sync converges.** `sync-X` regenerates a file the external source could rebuild from scratch, so losing it costs a re-run. `sample-X` records a reading the source will not remember: the store is the only place that history exists, and a lost one is gone. That is what settles the two properties the table cannot state. Idempotency holds *within* a period only, since re-running on the same day overwrites its own point while tomorrow's run adds one nothing upstream could reproduce. And the recording commits straight to the default branch rather than opening a pull request, for the reason a post-release recording does: the diff is not reviewable, since rejecting it cannot change what the API answered, only lose it. See [§ Sample job contract](https://repomatic.net/operation-contracts#sample-job-contract). Rule 3's PR-branch and PR-template dimensions therefore do not apply.
8. **A dataset the repository commits is CSV, not JSON.** Every one of them is a flat table, and CSV wins on all four counts that matter for a file under version control: a record is one line rather than seven, so a scheduled append is a readable diff; the file is about half the size; MyST's `csv-table` renders it directly and GitHub serves it through a searchable grid viewer; and nothing in the autofix lane touches CSV, where a committed JSON file has to be serialized in Biome's exact style or `format-json` rewrites it right back. Reach for JSON only when a record genuinely nests. {mod}`repomatic.tabular` is the one place that reads and writes them.
9. **An operation whose output is a GitHub issue takes a bare noun, no verb prefix** (`setup-guide`). It writes no repository file: it upserts one issue through {func}`~repomatic.github.issue.manage_issue_lifecycle`, which opens, updates, closes and reopens it, matched on the exact title. Every such command shares that one mechanism, so a verb would name the mechanism rather than the subject and they would all collapse onto the same prefix; the noun instead names what the issue tracks, keeping the command and the issue title the same phrase. Body fragments live in `repomatic/templates/{name}[-{fragment}].md` and render through {func}`~repomatic.github.pr_body.render_template`: that renderer is shared with PR bodies, but these are issue bodies, so `pr-body --template` never names one and rule 3's PR-branch and PR-template dimensions do not apply. Every issue carries {data}`~repomatic.github.issue.BOT_ISSUE_LABEL`. `broken-links` predates this convention and sits outside its population: its job is `check-broken-links` rather than the bare noun, and its issue carries a topical label (`📚 documentation`, or `🩹 fix link` on an awesome list) instead of the bot one. That last sentence is therefore a claim about the rule-9 family, not about every issue the CLI opens.

### Automated operation contracts

<!-- audience: all -->

Every automated operation follows the [naming conventions](#naming-conventions-for-automated-operations) and is [idempotent](#idempotency-by-default). For the detailed checklists of required properties, invariants, and optional elements for each operation type (sync, update, format/fix, lint, pack, scan, PR body templates), see [`docs/operation-contracts.md`](https://repomatic.net/operation-contracts).

### Ordering conventions

<!-- audience: all -->

Keep definitions sorted for readability and to minimize merge conflicts:

- **Workflow jobs**: by execution dependency (upstream jobs first), then alphabetically within the same level.
- **Python module-level constants**: alphabetically, unless a logical or dependency order applies. Place hard-coded domain constants (like `NOT_ON_PYPI_ADMONITION`, `SKIP_BRANCHES`) at the top, right after imports: they encode domain assertions, so surfacing them early shows the module's assumptions.
- **YAML configuration keys**: alphabetically within each mapping level.
- **Documentation lists and tables**: alphabetically, unless a logical order (like chronological in changelog) takes precedence.

### Named constants

<!-- audience: all -->

Do not inline named constants during refactors: a named, documented constant exists for readability and grep-ability. When moving code between modules, carry the constant with it, don't replace it with a literal.

### Single source of truth for defaults

<!-- audience: all -->

Every configurable default lives in exactly one place: the canonical config dataclass field default (the `Config` dataclass in `repomatic/config.py`). All code derives it from the source (class-level default for static contexts, instance value at runtime) rather than repeating the literal across registry entries, CLI option fallbacks, parameter defaults, or module-level paths. When adding a default, grep for the literal and point any other occurrence at the source.

A config field also surfaces in serialized command output (a non-string default needs format-safe encoding) and in test fixtures enumerating the config surface: run the full test suite after adding or removing a field, not just the module's own tests.

## Testing guidelines

<!-- audience: all -->

- Use `@pytest.mark.parametrize` for the same logic over multiple inputs, rather than copy-pasted test functions differing only in data.
- Keep test logic simple with straightforward asserts.
- Sort tests logically and alphabetically where applicable.
- No classes for grouping tests; write top-level functions. Use a class only for shared fixtures, setup/teardown, or class-level state.
- **`@pytest.mark.once` for run-once tests.** A custom `once` marker (in `[tool.pytest].markers`) tags tests that run once, not across the full matrix (CLI invocability, plugin registration, metadata checks). The main matrix filters with `pytest -m "not once"`; a dedicated `once-tests` job runs them on one runner. The admission test is coverage, not just OS-independence: the floor-holding matrix run filters `once` out, so a test moved there takes its package coverage with it — verify `report.fail_under` still clears, and keep a test on the matrix when it meaningfully covers package code.
- **CI-only pytest flags belong in workflow steps, not `[tool.pytest].addopts`.** `--cov-report=xml` produces a CI-only artifact and pollutes local runs if in `addopts`. Keep `addopts` for everywhere-flags (`--cov`, `--cov-report=term`, `--durations`, `--numprocesses`); pass CI-specific flags in the workflow `run:` step.
- **Coverage configuration belongs in `[tool.coverage]`** (`run.branch`, `run.source`, `report.precision`, `report.fail_under`), not `--cov-branch` in `addopts`. `addopts` carries only `--cov` and `--cov-report=term`. This holds for the coverage floor too, even though it is the one setting a workflow could plausibly carry: `--cov-fail-under` on the command line **outranks** `report.fail_under`, so passing it from CI would silently shadow the native knob a project sets. Never add a `[tool.repomatic]` key for it either, for the same reason. The floor is written for the full suite, so the two runs that do not clear it opt out explicitly with `--cov-fail-under=0`: the `once-tests` job (~22% on its own), and a focused local run, better served by `--no-cov`.
- **Write conformance tests when fixing a class of bugs.** For a bug that is a *category* (not a one-off), add a generic test locking in the invariant: iterate over every member of the set (registry entries, generators, exported symbols, data files) and assert the property uniformly via `@pytest.mark.parametrize` or a loop. Applies when the bug stems from a shared convention checkable from the codebase alone (no fixtures or mocks). Model: `tests/test_readme.py::test_docs_generator_matches_in_tree_state`. Shape: enumerate the population, assert on each, fail naming the violator. **Then prove it fails on the pre-fix state**, by running it against the old content rather than assuming: a conformance test written from the corrected text often only matches the corrected phrasing, so it passes on the very bug that motivated it and locks in nothing. When the invariant is genuinely narrower than the bug class (a rule keyed on one phrasing among several that state the same claim), keep the test and say so plainly, since a narrow guard is still worth having: what must not happen is reporting it as retroactive coverage it does not provide.
- **The suite is hermetic against the host's own `repomatic` configuration.** The default config search derives from `click.get_app_dir`, so any config file in the developer's app folder is discovered by every in-process `CliRunner().invoke(repomatic, ...)`: a local setting can fail a test CI cannot reproduce. The `_isolate_user_config` autouse fixture in `tests/conftest.py` (aliasing click-extra's `isolated_app_dir`) repoints discovery at an empty per-test directory; tests exercising config loading pass an explicit path instead.
- **It is *not* hermetic against this repository's own `[tool.repomatic]`, and nothing makes it so.** Discovery is CWD-first, walking up to the VCS root, so a call that resolves config itself (`run_init(config=None)`, anything reaching `load_repomatic_config()` with no argument) reads the checkout's `pyproject.toml` under pytest exactly as it would in a shell. The autouse fixture above covers the app dir only. This turns *enabling a feature here* into a test failure elsewhere: switching on a component's config gate made `test_init_only_workflows` see a workflow it asserted absent. Pass an explicit `Config()` in any test asserting on default behaviour, and treat a test that breaks when you flip a `[tool.repomatic]` key as coupled rather than as a real regression.
- **Pass `encoding="UTF-8"` to `subprocess.run(..., text=True)` when output may contain non-ASCII bytes** (emoji in workflow `name:`, accented names). `text=True` alone uses the platform default (`cp1252` on Windows), raising `UnicodeDecodeError` only in Windows CI. Test helpers shelling out to `git show`/`git cat-file` are the usual offenders; production `read_text`/`write_text` already set it.
- **Pass `encoding="UTF-8"` to every text-mode `open()`, `read_text()`, and `write_text()` in tests, same as production.** The same Windows cp1252 default applies to file I/O, and the failure hides until content grows a non-ASCII character. Ruff's `PLW1514` (in the shared config) flags `open()` and receivers its inference can type, but misses unannotated `Path` locals (`doc = tmp_path / "page.md"`); when a change touches file I/O, run the suite once with `PYTHONWARNDEFAULTENCODING=1` (PEP 597) to surface every bare call at runtime, on any platform.
- **Spell it `UTF-8`, never `utf-8`, in both of the above.** Python normalizes either, so the difference carries no meaning and a mixed codebase only makes a reader stop to work that out. `tests/test_suite_hygiene.py::test_encoding_argument_spelling_is_uniform` pins the suite to the one spelling; production holds it by convention, with no exception at present.
- **Never probe the environment at collection time.** A parametrize expectation computed at import — one that shells out, walks `PATH`, or stats the filesystem — is evaluated independently by every xdist worker, so a probe that can answer differently twice (a slow binary, a tool whose availability shifts mid-run, a file another test writes) leaves the workers holding different test lists and aborts the whole session with `Different tests were collected between gw0 and gw1`, naming no culprit. Wrap such an expectation in a callable the test resolves in its own body, and put any environment warm-up in a session-scoped fixture, which runs once collection has settled.
- **Seed environment-dependent global caches before the first test, from a session fixture.** click-extra's `runner` fixture pins `HOME` and its platform equivalents to an empty directory around each CLI invocation, so a module-global cache filled lazily *from inside* a test records what a home-less environment answered and serves that for the rest of the worker's session. `meta-package-manager` hit this the hard way: its manager pool cached a tool as unavailable because the probe that happened to run first went through a `$HOME`-dependent shim, and every later test on that worker saw the tool missing. An autouse session fixture touching the cache first, outside any runner, keeps that state honest — and is worth writing down where the cache lives, since the invariant is invisible at every call site.

## Agent conventions

<!-- audience: all -->

This repository uses three Claude Code agents in `.claude/agents/`. Definitions stay lean: if a rule belongs in `CLAUDE.md`, put it there and reference it. Do not duplicate.

**Agents must be self-contained for downstream portability.** Agents deploy downstream via `repomatic init subagents` as standalone files; Claude auto-invokes them from their `description:` frontmatter. All knowledge must be inline or reference `claude.md` sections, not upstream `docs/` URLs or upstream-only paths. When mining session history, default to local `claude.md` updates; file an upstream proposal only when the pattern is generic across repos.

### Source of truth hierarchy

<!-- audience: all -->

`CLAUDE.md` defines the rules; the codebase and GitHub (issues, PRs, CI logs) are what you measure against them. When they disagree, fix the code to match; if the rules are wrong, fix `CLAUDE.md`.

### Common maintenance pitfalls

<!-- audience: all -->

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
- **Generator/formatter ping-pong is recurrent.** Any code that writes a checked-in Markdown file competes with `format-markdown` for the canonical layout. After touching such code, run the generator, then `repomatic run mdformat -- {file}`, then the generator again, confirming `git diff` stays empty across all three states; if not, align the generator with mdformat. Grep for the pattern in sibling generators and mirror the check in `tests/`. Checked-in JSON has the same trap with `format-json`: Biome indents JSON with tabs, so generators must serialize with `json.dumps(..., indent="\t", sort_keys=True)` (see `upsert_scan_records` in `repomatic/virustotal.py`).
- **`repomatic run {tool} --check` is unreliable for tools with a post-process fixup.** A few tools (currently `mdformat`) get a Python post-processing pass that only runs in write mode, so `--check` can report drift the write path would reconcile (false positive) or pass on files it would still rewrite (false negative). To verify or gate formatting, run the write path and inspect `git diff`, never `--check`.
- **Removing a bundled asset leaves downstream orphans.** Dropping a skill, agent, or workflow from `COMPONENTS` stops shipping it, but copies already in downstream repos are invisible to stale-file detection. Add a `RemovedAsset` tombstone to `REMOVED_ASSETS` in `repomatic/registry.py` so `repomatic init` prunes the orphan (the `RemovedAsset` docstring has the content- vs fingerprint-gating recipe); a CI test fails otherwise. A rename is a drop plus an add: tombstone the old name.

### Agent behavior policy

<!-- audience: all -->

- **Never post to the web without explicit approval.** Do not create or comment on GitHub issues, PRs, or discussions, or post to any external service, without the user's explicit go-ahead. If approval is blocking, draft the content in a temporary markdown file for review.
- Agents make fixes in the working tree only: never commit, push, or create PRs. Exception: skills that run autonomously (`/babysit-ci`, `/repomatic-ship`) may commit and push, and include a `Co-Authored-By` trailer by default; a maintainer's explicit standing rule against AI attribution overrides that default, since the trailer lands in their repository's permanent history. Follow the skill's instructions when they override this rule.
- **Land an upstream proposal as working-tree edits in the sibling checkout, not as prose.** When work in a downstream repo surfaces a bug or rough edge that belongs to `repomatic`, and a sibling checkout exists at `../repomatic`, implement the change there directly: edit the code, update the tests it breaks, and verify it. Then stop, leaving every change uncommitted and unpushed. A described fix costs the maintainer the whole implementation; a diff sitting in the tree costs them a review, which is the step they were always going to do themselves. This does not relax the rule above: no commit, no push, no PR, no issue. Confine the edits to what the finding justifies, and say plainly which files were touched and what verification was run.
- **When the repository *is* `repomatic`, land the finding here and ship it.** The rule above is written for a downstream repo with a sibling checkout; inside `kdeldycke/repomatic` there is no `../repomatic`, so "propose it upstream" collapses into "fix it here" and stopping before the commit only defers the fix to a later cycle while the diff collects conflicts against whatever the machinery rewrites meanwhile. Implement it, verify it with whichever checks the change touches, and commit it like any other work. A release is when this pays off rather than a reason to hold it back: `prepare-release` regenerates the release pull request on every push to the default branch, replaying the freeze onto the new head, so a fix landed before the merge ships in *that* release instead of the next. Keep the pass bounded to what the session actually surfaced, though: anything needing more than a contained edit, or touching code the release itself depends on, stays an uncommitted diff plus a note, exactly as it would downstream.
- Prefer mechanical enforcement (tests, autofix jobs, lint checks) over prose rules. If a rule can be checked by code, it should be.
- Agent definitions reference `CLAUDE.md` sections, not restate them.
- qa-engineer is the gatekeeper for agent definition changes.

### Skills

<!-- audience: all -->

Skills in `.claude/skills/` follow agent conventions: lean, no duplication with `CLAUDE.md`, reference sections instead of restating rules. Run `repomatic list-skills` to list them.

**A skill is a plain folder of static files, copied verbatim.** `repomatic init skills` places the folder at its destination and does nothing else: no rendering, no per-target variants, no flavor flags. Optional `scripts/`, `references/` and `assets/` subdirectories travel with it. Anything that would otherwise vary per destination belongs in the skill body as prose, never in a code path.

**Frontmatter carries [Agent Skills spec](https://agentskills.io/specification) fields, plus `argument-hint`.** That single deviation is settled; every other Claude Code extension stays out. Notably there is no `model:` (the recommended model rides in the spec's `compatibility` field) and no `disable-model-invocation:`, so **every skill is model-invocable by design**: skills exist to augment the parent agent, and what they may actually do is gated by the permission layer, not by frontmatter. `tests/test_skills.py` enforces this, so argue a new field there before adding it to a skill.

**Skills must be self-contained for downstream portability.** Skills deploy downstream via `repomatic init skills` as standalone folders; downstream repos have no `docs/` and skills typically lack `WebFetch`, so all domain knowledge must be inline or in the skill's own `references/`. Duplication between a skill and a docs page is intentional: `docs/` serves humans, the skill serves Claude at runtime.

**Cross-references between skills and agents must degrade gracefully.** A "Next steps" line suggesting `/other-skill` is informational; a *programmatic* call is the same: a skill invoking another through the `Skill` tool must fall back to a subagent or inline work when the target is excluded (via `[tool.repomatic] exclude` or scope filtering), never letting a missing skill abort the caller. Write prose so a missing cross-reference is a no-op, not a blocker.

### Mechanical vs analytical work

<!-- audience: all -->

The `repomatic` ecosystem has a **mechanical layer** (CLI commands and CI workflows that deterministically sync, lint, format, and fix files on every push to `main`) and an **analytical layer** (judgment-based tasks needing context comparison and trade-offs). Skills focus on the analytical gaps (custom job content analysis, cross-repo pattern comparison, judgment on intentional vs stale divergence); don't duplicate what CI handles mechanically: see [§ Automated operation contracts](#automated-operation-contracts).

## Design principles

<!-- audience: all -->

### Philosophy

<!-- audience: all -->

1. Create something that works (to provide business value).
2. Create something that's beautiful (to lower maintenance costs).
3. Work on performance.

### Labeller rules are precision-first conveniences

<!-- audience: all -->

The issue and PR labeller (content keyword rules, file glob rules) pre-labels a freshly filed issue or PR to save the maintainer a first pass. It never replaces their review and classification, and nothing downstream treats its labels as complete or authoritative. Tune it for **precision, not recall**: a missing label costs one manual click; a wrong label is noise on every item that trips it. Encode a rule only when the signal is unambiguous, and none when it is not.

- **Content rules** match issue/PR prose: key them off terms that unambiguously name the subject (a distro, language, ecosystem or brand) and that the tool never prints in its own output. Never key off a token the tool emits for *every* item it handles, like an ID, sub-command or status-table entry a CLI lists for all its back-ends: a user who pastes such a trace makes every one of those labels fire at once.
- **File rules** match a PR's changed paths: key them off a path owned by exactly one label. A glob broad enough to catch unrelated changes is worse than none.

Both rule families match in-process (`repomatic/labels.py`) rather than through the retired `github/issue-labeler` and `actions/labeler` actions, and a label's pattern list is **OR-joined**: any one pattern matching earns the label. A bare content pattern is a keyword, matched case-insensitively and anchored on each edge that is itself a word character, so `fix` does not fire inside `prefix`. Wrap a pattern in slashes (`/body/flags`) to pass a regex through verbatim instead, case-sensitive unless a flag says otherwise. A label's file globs are evaluated as one set, so a `!`-negated entry subtracts from its siblings the way a `.gitignore` line would (`["docs/**", "!docs/generated/**"]`), with no separate exclude rule to write.

### Linting and formatting

<!-- audience: all -->

[Linting](https://repomatic.net/workflows#github-workflows-lint-yaml-jobs) and [formatting](https://repomatic.net/workflows#github-workflows-autofix-yaml-jobs) are automated via GitHub workflows. Developers needn't run them manually; pushing triggers the workflows, which catch issues and handle the nitpicking.

### Registry types own their query logic

<!-- audience: all -->

Enums and dataclasses that carry metadata should also carry the methods that interpret it. When callers decide based on a field (scope, format, config key), the logic belongs on the type, not scattered across call sites (`RepoScope.matches(...)`, `NativeFormat.serialize(...)`, `Component.is_enabled(config)`). When adding a field, ask: will callers branch on this value? If yes, add a method. When fixing duplicated conditionals that interpret the same field, the fix is a method, not a helper elsewhere.

### Keep logic in Python, not workflow YAML

<!-- audience: all -->

Push anything beyond trivial wiring out of workflow YAML into the CLI/library. Rather than duplicating `if:` conditions across steps, compute them once in `repomatic metadata` and reference the result. Rather than hand-maintaining workflow content, generate it in Python (see `repomatic.github.workflow_sync` for the rationale and the `publish-pypi` example): a tested generator that fails loudly beats a static artifact that can silently drift.

### Defensive workflow design

<!-- audience: all -->

GitHub Actions workflows face race conditions, eventual consistency, and partial failures. Prefer **belt-and-suspenders**: multiple independent correctness mechanisms over a single guarantee. If a job depends on external state (tags, published packages, API availability), add a fallback or graceful default and make operations [idempotent](#idempotency-by-default) so re-runs are safe.

**Non-interactive third-party tooling.** When a tool prompts interactively (path selection, asset selection), pre-create its config files and resolve inputs via `gh` or another CLI rather than piping stdin: stdin redirection is fragile across platforms and fails outright on Windows ("Incorrect function"). Where a tool has no non-interactive mode at all, fetch the artifact it would install and verify that directly.

**Advisory findings never fail a scheduled audit job.** A scheduled audit separates advisory findings from gating checks: opportunities and upstream changes are reported into `$GITHUB_STEP_SUMMARY` while the job stays green, and only drift against pinned or committed state fails it — a red run for an advisory finding teaches people to ignore that workflow's red runs, which then hides real failures. A batch job accumulates a per-item row in the summary and exits non-zero once at the end, rather than aborting on the first failure.

```{note}
Release-specific design rationale for `kdeldycke/repomatic` (the `workflow_run` checkout pitfall, immutable releases, concurrency, freeze/unfreeze structure) lives in `docs/upstream-development.md` § Release checklist. Downstream repos with their own release flow can borrow it but aren't bound by it.
```

### Idempotency by default

<!-- audience: all -->

Workflows and CLI commands must be safe to re-run: the same command twice with the same inputs produces the same result, with no errant side effects (duplicate tags or PR comments, redundant file writes). Use `--skip-existing` or equivalent guards when creating resources; check for existing state before writing (skip an admonition already present, skip a PR that already exists for the branch); prefer upsert over create-only; make file-modifying operations convergent (re-applying is a no-op).

**When idempotency is not achievable**, document in a comment or docstring what side effects occur on re-runs and why they are acceptable.

### Command-line options

<!-- audience: all -->

Always prefer long-form options over short-form for readability in workflow files and scripts (`--output` not `-o`, `--verbose` not `-v`). The same rule applies to every argv the program builds at runtime (subprocess invocations included): long forms make logged command disclosures self-documenting.

### CLI commands that accept a `--lockfile` or similar path

<!-- audience: all -->

A CLI command taking a project-file path (`--lockfile path/to/uv.lock`) must run any context-needing subprocess (`uv lock`, `uv audit`) with `cwd=path.parent`, else it resolves against the caller's directory, not the target project.

### CLI output conventions

<!-- audience: all -->

CLI commands that produce structured output should separate terminal display from file output:

- **Terminal:** use `ctx.find_root().print_table(rows, headers)`, which respects the global `--table-format` option (github, json, csv, etc.).
- **File output (`--output`):** write markdown for PR bodies and CI; use `--output-format` for transport encoding (like `github-actions`, which spills the report to a file and emits `<key>_file=<path>` for `$GITHUB_OUTPUT`), not implicit env-var detection. A report has no ceiling of its own, so it travels as a path rather than inline: only bounded values still get the heredoc form.
- **Boolean feature flags** (like `--release-notes`) should use the `--flag/--no-flag` pattern so both directions are explicitly invocable from workflows.

### Prefer `uv` over `pip` in documentation

<!-- audience: all -->

Documentation and install pages must use `uv` as the default installer (`uv tool install` for CLI tools, `uv pip install` for libraries/extras). Other installers may appear as secondary options, but `uv` must be primary.

### uv flags in CI workflows

<!-- audience: all -->

When invoking `uv` and `uvx` commands in GitHub Actions workflows:

- **`--no-progress`** on all CI commands (uv-level flag, before the subcommand): progress bars render poorly in CI logs.
- **`--frozen`** on `uv run` commands (run-level flag, after `run`): the lockfile should be immutable in CI.
- **Flag placement:** `uv --no-progress run --frozen -- command` (not `uv run --no-progress`).
- **Exceptions:** omit `--frozen` for `uvx` with pinned versions, `uv tool install`, CLI invocability tests, and local examples.
- **Prefer explicit flags over environment variables** (`UV_NO_PROGRESS`, `UV_FROZEN`): self-documenting, visible in logs, and free of conflicts (like `UV_FROZEN` vs `--locked`). The cooldown is the deliberate exception, and only the cooldown: `UV_EXCLUDE_NEWER` is set workflow-wide so it reaches commands nobody flagged, per [§ Cooldown on every install](#cooldown-on-every-install).
- **Per-group `requires-python` in `[tool.uv]`:** a group needing newer Python can be restricted with `dependency-groups.docs = { requires-python = ">= 3.14" }`, so uv won't install incompatible dependencies on older Python.

### Pin uv with `required-version`

<!-- audience: all -->

Downstream Python repos floor uv in `[tool.uv]` with a lower-bound `required-version` (like `required-version = ">=0.11.15"`), not an upper-capped range, so contributors and downstream repos are never capped and local development moves forward without a manual ceiling bump each minor.

**CI pins the exact uv separately.** `required-version` is a floor for everyone; what a runner downloads is a different question, and left to `setup-uv` the answer is "the newest release satisfying the floor", installed seconds after it lands. That makes the tool enforcing every cooldown the one tool without one. So every `astral-sh/setup-uv` step carries `with: version: "X.Y.Z"`, and `sync-workflow-pins` walks it forward once a uv release clears [`minimum-release-age`](#cooldown-on-every-install), like any other pinned literal. The pin is not a cap: it never co-resolves with anything, and CI still moves forward on its own, just a window behind. `tests/test_workflows.py` fails on a `setup-uv` step without the input, or on two steps naming different versions. Skip a hard upper cap (`<0.13`): uv self-updates on many machines, so a cap breaks every contributor and runner the day the next minor lands, and `required-version` is a self-gate that never co-resolves with the project's dependencies (the usual reason to cap a dependency does not apply). `uv.lock` stays stable across minors because `sync-uv-lock` discards a re-lock that only re-spells equivalent environment markers (see `sync_uv_lock` in `repomatic/uv.py`). repomatic manages this: `repomatic init uv` writes both policy pins (`required-version`, `exclude-newer`) from the bundled `uv.toml`, and `sync-uv-lock` re-applies them while leaving every other `[tool.uv]` key untouched.

## Scope and precedence

These are my personal rules, loaded on every project I open from this machine. A repository's own `claude.md` speaks for that project; this file speaks for me. **Where the two conflict, this file wins**: the repo file is written for every contributor, this one is written for how I work.

The boundary is one-way. Nothing here belongs in a project's `claude.md`, least of all `kdeldycke/repomatic`'s, which ships its conventions to repos with outside contributors. Several rules below would be actively wrong advice there: "push to `main` rather than a scratch branch" assumes admin rights on the remote, "use first-person singular" assumes a solo author, and the commit-authorization rule describes my review habits rather than the project's contribution policy. Project conventions travel the other way, from `repomatic/claude.md` down into each repo, tagged by audience at the section level.

## Voice and punctuation

Use first-person singular ("I", "my") in all prose written on behalf of the user: issue descriptions, PR bodies, feature requests, comments, documentation. Never use first-person plural ("we", "our") unless the text genuinely refers to a group.

Use ":" instead of em dashes for inline elaboration or appositive clauses.

## Code organization

Do not make autonomous decisions about module boundaries, file placement, or architectural structure. When intent is ambiguous, ask before reorganizing. The user has strong opinions about where code lives and how modules are scoped.

## Commits and PRs

Never run `git commit`, `git push`, `gh pr create`, or any other command that creates a commit, pushes to a remote, or opens a pull request unless I have explicitly authorized that specific action in the current conversation. Staging changes, drafting commit messages, and showing diffs are fine; the actual commit, push, or PR creation requires my explicit go-ahead each time. A prior authorization does not carry over to later actions.

Never include AI attribution in commits or PRs. No `Co-Authored-By` lines, no "Generated with Claude Code", no mention of being an AI or which model produced the code. Do not reference model names, versions, or codenames in commit messages, PR titles, or PR bodies.

Write commit messages as a human developer would — describe what the code change does and why, not how it was produced. Keep internal tooling references (specific tools, Slack channels, internal links) out of public-facing text.

When a change needs a live CI run to validate it, push to `main` rather than to a scratch branch. My workflows key their concurrency group on `${{ github.workflow }}-${{ github.ref }}` with `cancel-in-progress`, so each push to the same ref cancels the previous run and hands its runners straight back. A side branch is a different ref: its run queues alongside `main`'s instead of superseding it, and both then crawl through a runner pool that is capped, most tightly on macOS.

The `#N` autolink hazard applies here in full: see [§ GitHub cross-references in commit messages and PRs](#github-cross-references-in-commit-messages-and-prs).

## Shell commands

Never use `$()` command substitutions inside `gh` (or any other) Bash calls. The sandbox flags `$()` as a separate security check that fires regardless of permission allow rules — it can't statically verify what executes inside a substitution. Instead, run compound commands as separate sequential Bash calls: capture the inner result first, then use it in the next call. Both commands then match the allow rules individually and auto-approve.

Never `cd` in Bash calls: pass absolute paths to the tool instead. Claude Code creates a `.claude/.cc-writes/` atomic-write staging directory in the session's tracked working directory, and that directory follows every `cd`. So a single `cd` into a source tree, a `.venv`, or a document folder leaves a permanent empty `.claude/` behind. No setting disables this. For the same reason, launch `claude` from a repo root rather than from a deep subdirectory or a data folder. Run `claude-sweep` to clear the strays.

## Local environment

Non-obvious facts about this machine that have caused hard-to-diagnose failures:

- **Dotfiles are symlinked into `$HOME`, never hardlinked or copied.** `install.sh` links them with `ln -sf`, so `~/{path}` is a symlink to `~/code/dotfiles/dotfiles/{path}`. An audit of every tracked dotfile found zero hardlinks: most reach `$HOME` through a symlinked *parent directory* rather than their own link, so `~/.config/nvim` is a single link covering the whole folder and a file created in the repo shows up in `$HOME` immediately, with no `install.sh` re-run (only a brand-new top-level dotfile needs `./install.sh links`). Always edit the repo path and the `$HOME` symlink follows it: comparing inodes proves nothing, since a symlink resolves to the same inode a hardlink would. The real hazard is writing to the `$HOME` path with a replace-then-rename (what most editors and BSD/macOS `sed -i` do), which swaps the symlink for a regular file and silently forks the two copies. `~/.path-env-cache` is already forked exactly this way, because `.zshrc` writes to `${HOME}/.path-env-cache` directly.
- **The `PATH` list of `.zshrc` is cached with a 7-day TTL.** `.zshrc` rebuilds `~/.path-env-cache` only when the file is missing or older than 7 days, and new shells read the cache, not `PATH_LIST` directly: an entry added to `PATH_LIST` reaches new terminals only at the next refresh. To apply one immediately, append the resolved path to the cache (or delete the cache and let a new shell regenerate it, at the cost of a slow round of `brew --prefix` calls). The cache is the already-forked file from the dotfiles bullet above by design, so edit the repo's `.zshrc` and seed the `$HOME` cache; never the reverse.
- **`packages.toml` never picks up newly installed packages on its own.** `install.sh`'s snapshot stage runs `mpm snapshot --update-version ./packages.toml`, and `--update-version` only refreshes the version of entries *already* in the file. Adding entries is `--merge`, which that stage does not use. So anything installed with a bare `brew install` stays out of the manifest permanently and is skipped by a fresh-machine `mpm restore`: the `tree-sitter` library sat installed but unlisted for weeks this way. After installing a tool worth keeping, add its line by hand (alphabetically, bare version, no `v` prefix); `--update-version` tracks its version from then on. Never assume a later snapshot will notice it.
- **Pushing to `gitlab.alpinelinux.org` uses `~/.ssh/id_ed25519`, not the Secretive key.** The Secure Enclave key (Secretive) is registered there as a *Signing* key, which cannot authenticate a push: it connects as "Anonymous" and the push is rejected. The *Authentication* key is `~/.ssh/id_ed25519`. A `Host gitlab.alpinelinux.org` block in `~/.ssh/config` (before `Host *`) pins `IdentityAgent none` + `IdentityFile ~/.ssh/id_ed25519` + `IdentitiesOnly yes` to force it: leave that block in place. More generally, when a GitLab push fails as "Anonymous", check the key's usage type on the server, the `IdentityAgent` override, and `ControlMaster` multiplexing (a cached bad session masks key changes).

## Code generation preferences

For any non-trivial workflow, data processing, or multi-step logic: write Python, not Bash. The user is an advanced Python developer and can quickly read, inspect, and validate Python code. Short one-liners and simple Bash scripts are fine for convenience and performance, but anything with branching logic, string manipulation, data transformation, or error handling should be Python.

## Data visualization

When producing matplotlib figures, follow the design system at https://github.com/temataro/better-graphs for readable, presentation-ready plots: it codifies Tufte-style design rules, a chart-selection guide, and a `house_style.py` styling module (`apply_theme()`, `polish()`, `takeaway_title()`) that replaces matplotlib defaults with accent-led palettes, trimmed spines, unit-aware ticks, and takeaway-focused titles.

## Markdown and documentation

The markdown no-hard-wrap rule above is not merely a ceiling to stay under: each sentence or logical clause flows as a single long line and the renderer handles wrapping. Never reflow a paragraph to a column width, in any markdown file.

Sentence-case titles, natural heading anchors and the `[owner/repo#N]` link form are stated above and need no restating here: see [§ Comments and docstrings](#comments-and-docstrings) and [§ Linking to external repositories in Markdown](#linking-to-external-repositories-in-markdown). One case those do not reach: in plain GFM, where MyST's `(my-anchor)=` is unavailable, the explicit anchor form is `<a id="…"></a>`.
