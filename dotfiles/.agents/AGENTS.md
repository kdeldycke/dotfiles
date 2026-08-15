@~/.claude/tropes.md

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

Never write `#N` (a literal `#` followed by a number) in commit messages, PR titles, or PR bodies unless N is the actual number of a GitHub issue or pull request in the target repository. GitHub auto-links every `#N` token to issue/PR N, so positional references like `test #1` or `tests #14 and #15` render as misleading cross-references to unrelated tickets. Use plain numbers (`test 1`, `tests 14 and 15`), backtick-quote the identifier when it names a slot in a test plan or list (`` test `1` ``, `` item `14` ``), or rephrase (`the first test`, `the fourteenth case`).

## Shell commands

Never use `$()` command substitutions inside `gh` (or any other) Bash calls. The sandbox flags `$()` as a separate security check that fires regardless of permission allow rules — it can't statically verify what executes inside a substitution. Instead, run compound commands as separate sequential Bash calls: capture the inner result first, then use it in the next call. Both commands then match the allow rules individually and auto-approve.

Never `cd` in Bash calls: pass absolute paths to the tool instead. Claude Code creates a `.claude/.cc-writes/` atomic-write staging directory in the session's tracked working directory, and that directory follows every `cd`. So a single `cd` into a source tree, a `.venv`, or a document folder leaves a permanent empty `.claude/` behind. No setting disables this. For the same reason, launch `claude` from a repo root rather than from a deep subdirectory or a data folder. Run `claude-sweep` to clear the strays.

## Local environment

Non-obvious facts about this machine that have caused hard-to-diagnose failures:

- **Dotfiles are symlinked into `$HOME`, never hardlinked or copied.** `install.sh` links them with `ln -sf`, so `~/{path}` is a symlink to `~/code/dotfiles/dotfiles/{path}`. An audit of every tracked dotfile found zero hardlinks: most reach `$HOME` through a symlinked *parent directory* rather than their own link, so `~/.config/nvim` is a single link covering the whole folder and a file created in the repo shows up in `$HOME` immediately, with no `install.sh` re-run (only a brand-new top-level dotfile needs `./install.sh links`). Always edit the repo path and the `$HOME` symlink follows it: comparing inodes proves nothing, since a symlink resolves to the same inode a hardlink would. The real hazard is writing to the `$HOME` path with a replace-then-rename (what most editors and BSD/macOS `sed -i` do), which swaps the symlink for a regular file and silently forks the two copies. `~/.path-env-cache` is already forked exactly this way, because `.zshrc` writes to `${HOME}/.path-env-cache` directly.
- **`packages.toml` never picks up newly installed packages on its own.** `install.sh`'s snapshot stage runs `mpm snapshot --update-version ./packages.toml`, and `--update-version` only refreshes the version of entries *already* in the file. Adding entries is `--merge`, which that stage does not use. So anything installed with a bare `brew install` stays out of the manifest permanently and is skipped by a fresh-machine `mpm restore`: the `tree-sitter` library sat installed but unlisted for weeks this way. After installing a tool worth keeping, add its line by hand (alphabetically, bare version, no `v` prefix); `--update-version` tracks its version from then on. Never assume a later snapshot will notice it.
- **Pushing to `gitlab.alpinelinux.org` uses `~/.ssh/id_ed25519`, not the Secretive key.** The Secure Enclave key (Secretive) is registered there as a *Signing* key, which cannot authenticate a push: it connects as "Anonymous" and the push is rejected. The *Authentication* key is `~/.ssh/id_ed25519`. A `Host gitlab.alpinelinux.org` block in `~/.ssh/config` (before `Host *`) pins `IdentityAgent none` + `IdentityFile ~/.ssh/id_ed25519` + `IdentitiesOnly yes` to force it: leave that block in place. More generally, when a GitLab push fails as "Anonymous", check the key's usage type on the server, the `IdentityAgent` override, and `ControlMaster` multiplexing (a cached bad session masks key changes).

## Code generation preferences

For any non-trivial workflow, data processing, or multi-step logic: write Python, not Bash. The user is an advanced Python developer and can quickly read, inspect, and validate Python code. Short one-liners and simple Bash scripts are fine for convenience and performance, but anything with branching logic, string manipulation, data transformation, or error handling should be Python.

## Data visualization

When producing matplotlib figures, follow the design system at https://github.com/temataro/better-graphs for readable, presentation-ready plots: it codifies Tufte-style design rules, a chart-selection guide, and a `house_style.py` styling module (`apply_theme()`, `polish()`, `takeaway_title()`) that replaces matplotlib defaults with accent-led palettes, trimmed spines, unit-aware ticks, and takeaway-focused titles.

## Terminology and spelling

Use correct capitalization for proper nouns and trademarked names:

<!-- typos:off -->

- **PyPI** (not ~~PyPi~~): the Python Package Index. The "I" is capitalized because it stands for "Index". See [PyPI trademark guidelines](https://pypi.org/trademarks/).
- **GitHub** (not ~~Github~~)
- **GitHub Actions** (not ~~Github Actions~~ or ~~GitHub actions~~)
- **JavaScript** (not ~~Javascript~~)
- **TypeScript** (not ~~Typescript~~)
- **macOS** (not ~~MacOS~~ or ~~macos~~)
- **iOS** (not ~~IOS~~ or ~~ios~~)

<!-- typos:on -->

## Version formatting

The version string is always bare (like `1.2.3`). The `v` prefix is a **tag namespace**: it only appears when the reference is to a git tag or something derived from a tag (action ref, comparison URL, commit message). This aligns with PEP 440, PyPI, and semver conventions.

Rules:

1. **No `v` prefix on package versions.** Anywhere the version identifies the *package* (PyPI, changelog heading, CLI output, `pyproject.toml`), use the bare version: `1.2.3`.
2. **`v` prefix on tag references.** Anywhere the version identifies a *git tag* (comparison URLs, action refs, commit messages, PR titles), use `v1.2.3`.
3. **Always backtick-escape versions in prose.** Both `v1.2.3` (tag) and `1.2.3` (package) are identifiers, not natural language. Wrap them in single backticks: `` `v1.2.3` ``, `` `1.2.3` ``.
4. **Development versions** follow PEP 440: `1.2.3.dev0` with optional `+{short_sha}` local identifier.

## File naming conventions

Use the longest, most explicit file extension available. For YAML, that means `.yaml` (not `.yml`). Apply the same principle to all extensions (like `.html` not `.htm`, `.jpeg` not `.jpg`).

Use lowercase filenames everywhere.

### GitHub exceptions

GitHub silently ignores certain files unless they use the exact name it expects. These are the known hard constraints where the long-form / lowercase rule does **not** apply:

| File                     | Required name                       |
| ------------------------ | ----------------------------------- |
| Issue form templates     | `.github/ISSUE_TEMPLATE/*.yml`      |
| Issue template config    | `.github/ISSUE_TEMPLATE/config.yml` |
| Funding config           | `.github/funding.yml`               |
| Release notes config     | `.github/release.yml`               |
| Issue template directory | `.github/ISSUE_TEMPLATE/`           |
| Code owners              | `CODEOWNERS`                        |

Workflows (`.github/workflows/*.yaml`) and action metadata (`action.yaml`) accept both `.yml` and `.yaml`: use `.yaml`.

## Markdown and documentation

Markdown files have no line-length limit: do not hard-wrap prose in markdown. Each sentence or logical clause should flow as a single long line; let the renderer handle wrapping.

Titles in markdown use sentence case.

Use the natural auto-generated heading anchor for cross-references. Add an explicit anchor (`(my-anchor)=` in MyST, `<a id="…"></a>` in plain GFM) only when the natural one is unavailable: duplicate headings, non-heading targets.

In markdown (changelogs, `readme.md`, `docs/`, issue and PR bodies), link to another repository using GitHub's reference slug as the link text, not the raw URL:

- Issue or PR: `[owner/repo#N](https://github.com/owner/repo/issues/N)`. Issues and PRs share one number space; pick `/issues/N` or `/pull/N` to match the real type (GitHub redirects either way).
- Commit: `[owner/repo@shortsha](https://github.com/owner/repo/commit/fullsha)`.
- Repository homepage: `[owner/repo](https://github.com/owner/repo)`.

GitHub autolinks the bare `owner/repo#N` form only inside conversations (issues, PRs, commit messages), never in committed files, so the explicit link is what renders the compact slug in a markdown file. Same-repo references drop the slug: `[#N](…/issues/N)`.

## YAML workflows

For single-line commands, use plain inline `run:`. For multi-line, use the folded block scalar (`>`) which joins lines with spaces: no backslash continuations needed. Use the literal block scalar (`|`) only when preserved newlines are required (multi-statement scripts, heredocs).

YAML lines may run to 120 characters: repomatic's bundled `yamllint.yaml` sets `line-length: max: 120`. Do not carry Python's 88-character limit over into workflow files.

Never use a `-latest` runner alias (`ubuntu-latest`, `macos-latest`). GitHub repoints those without a commit to review, and `repomatic lint-repo` rejects them. Pin the explicit image instead: `macos-26` or `ubuntu-26.04`.

## Modern `typing` practices

Use modern equivalents from `collections.abc` and built-in types instead of `typing` imports. Use `X | Y` instead of `Union` and `X | None` instead of `Optional`. New modules should include `from __future__ import annotations` ([PEP 563](https://peps.python.org/pep-0563/)).

Omit type annotations on local variables, loop variables, and assignments when the type is obvious from the right-hand side. Add an explicit annotation only when the type checker cannot infer it (empty collections needing a specific element type, `None` initializations where the intended type is ambiguous). Function signatures are unaffected: always annotate parameters and return types.

## Testing guidelines

- Use `@pytest.mark.parametrize` when testing the same logic for multiple inputs. Prefer parametrize over copy-pasted test functions that differ only in their data.
- Keep test logic simple with straightforward asserts.
- Do not use classes for grouping tests. Write test functions as top-level module functions. Only use test classes when they provide shared fixtures, setup/teardown methods, or class-level state.

## Ordering conventions

Keep definitions sorted for readability and to minimize merge conflicts:

- **YAML configuration keys**: alphabetically within each mapping level.
- **Documentation lists and tables**: alphabetically, unless a logical order (like chronological in changelog) takes precedence.

## Command-line options

Always prefer long-form options over short-form for readability in workflow files and scripts (like `--output` not `-o`, `--verbose` not `-v`).

## Common maintenance pitfalls

- **CI debugging starts from the URL.** When a workflow fails, fetch the run logs first (`gh run view --log-failed`). Do not guess at the cause.
- **Trace to root cause before coding a fix.** When a bug surfaces, audit its scope across the codebase before writing the patch. If the same pattern appears in multiple places, the fix belongs at the shared layer.
- **Simplify before adding.** When asked to improve something, first ask whether existing code or tools already cover the case. Remove dead code and unused abstractions before introducing new ones.
- **Documentation drift.** Version references, command output, and workflow descriptions in docs go stale after every release or refactor. Verify docs against actual behavior after changes, not against your assumption of what the code does.
- **Type-checking divergence across Python versions.** Code that passes `mypy` locally on Python 3.14 may fail in CI under `--python-version 3.10`. Always check against the minimum supported version when modifying type-sensitive code.
- **Angle-bracket placeholders in bash code blocks.** `mdformat-shfmt` runs `shfmt` on ```` ```bash ``` ```` fences. `shfmt` parses `<foo>` as input redirection and `>foo` as output redirection, then reorders the command. Use curly braces (`{foo}`) for placeholders in bash examples instead.
- **Route through existing infrastructure, don't bypass it.** Before writing a new helper, check whether the codebase already has a mechanism for the same operation. A bug caused by data taking the wrong code path is better fixed by routing data to the right path than by duplicating logic at the wrong one.
