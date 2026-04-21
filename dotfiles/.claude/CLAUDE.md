@~/.claude/tropes.md

Also avoid patterns described at https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing

## Voice and punctuation

Use first-person singular ("I", "my") in all prose written on behalf of the user: issue descriptions, PR bodies, feature requests, comments, documentation. Never use first-person plural ("we", "our") unless the text genuinely refers to a group.

Use ":" instead of em dashes for inline elaboration or appositive clauses.

## Code organization

Do not make autonomous decisions about module boundaries, file placement, or architectural structure. When intent is ambiguous, ask before reorganizing. The user has strong opinions about where code lives and how modules are scoped.

## Commits and PRs

Never include AI attribution in commits or PRs. No `Co-Authored-By` lines, no "Generated with Claude Code", no mention of being an AI or which model produced the code. Do not reference model names, versions, or codenames in commit messages, PR titles, or PR bodies.

Write commit messages as a human developer would — describe what the code change does and why, not how it was produced. Keep internal tooling references (specific tools, Slack channels, internal links) out of public-facing text.

## Shell commands

Never use `$()` command substitutions inside `gh` (or any other) Bash calls. The sandbox flags `$()` as a separate security check that fires regardless of permission allow rules — it can't statically verify what executes inside a substitution. Instead, run compound commands as separate sequential Bash calls: capture the inner result first, then use it in the next call. Both commands then match the allow rules individually and auto-approve.

## Code generation preferences

For any non-trivial workflow, data processing, or multi-step logic: write Python, not Bash. The user is an advanced Python developer and can quickly read, inspect, and validate Python code. Short one-liners and simple Bash scripts are fine for convenience and performance, but anything with branching logic, string manipulation, data transformation, or error handling should be Python.

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

## File naming conventions

Use the longest, most explicit file extension available. For YAML, that means `.yaml` (not `.yml`). Apply the same principle to all extensions (like `.html` not `.htm`, `.jpeg` not `.jpg`).

Use lowercase filenames everywhere.

## Markdown and documentation

Markdown files have no line-length limit: do not hard-wrap prose in markdown. Each sentence or logical clause should flow as a single long line; let the renderer handle wrapping.

Titles in markdown use sentence case.

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
