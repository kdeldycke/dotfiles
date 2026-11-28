# Deep pass

**Run the deep pass before step 1 when the invocation passes `--deep`.** It covers the whole repository, not only the cycle diff, and it may break the public surface. Step 1 then reconciles the changelog, the docs and the bundled assets against the refactored tree, and the step-2 gate, CI and babysit check the result like any other cycle work. The pass runs first so that everything after it also checks the refactor. It runs only on request: ship often runs more than once in a cycle, and each run of the pass reads the whole repository again.

**Never move the version line.** The maintainer sets the version, whatever the pass breaks: a refactor that breaks the public surface still ships under the version `pyproject.toml` already carries. Step 3's advisory names the bump the breaks imply, and the maintainer merges the increment pull request or ignores it.

**The release is a new major when the major of the `pyproject.toml` version in the context is above that of the last tag.** The rules marked "on a new major" apply only then. A maintainer who wants them merges the `major-version-increment` pull request before the pass.

The pass covers the code, its tests and the workflows the repository owns. Prose under `docs/` and the bundled assets follow in step 1. Before the first spawn, capture the unstaged diff as step 1 describes, and give every agent of the pass the same guard. Every agent follows the sub-agent rules of the skill.

**Spawn every agent of the pass on the strongest model that the `Agent` tool offers: `fable` in Claude Code `2.1.284`.** A harness with no model choice runs them on the session model. Ask each agent to reason as thoroughly as the task warrants: in that version, this request is what the `ultrathink` keyword adds to a turn.

**Keep the findings, the plan and each brief in files under the scratchpad.** The pass outlasts a context window on a large repository, and a continued session resumes from those files, not from its summary.

## Survey

**Split the repository into slices of related modules, and give each slice one survey agent.** Each agent reads every line of its modules, their tests and the docs pages that name them: whole files, never excerpts. It reports bugs, duplication inside and across its slice, dead code, shims whose trigger fired, history in comments, hot paths and the generic helpers its modules define or re-implement. Condense the reports into one findings file.

**Tell each survey agent to write nothing.** An agent with no `Edit` tool still holds `Bash`, and one ran `git add`, `sed -i` and `git checkout` on the shared tree during a read-only audit. Name the forbidden commands in the brief: no `git add`, `checkout`, `stash` or `restore`, no `sed -i`, no redirect into a tracked file.

**Write the plan from the findings: the target layout, the removals and the work packages.** Group modules by domain in subpackages, and leave at the root the shared leaves that everything imports: burying those lengthens every import and buys nothing. Give each work package the modules it owns and the tests that target them, so no two packages share a file. Name every removal the plan makes by default: a command alias, an option, a config key, a public name.

**Show the plan before the fan-out: the layout, the removals and the work packages.** In normal use, that is where the maintainer stops a move or a removal they refuse. Then apply all of it. The `--deep` flag is the maintainer's go-ahead for module boundaries, which the code-organization rule otherwise reserves to them.

## Moves first

**Make every module move with a script before any lane starts, and commit it alone.** The script runs `git mv`, rewrites the imports with an AST pass, and rewrites dotted and path references elsewhere with a regex: the `automodule` entries and page stubs under `docs/`, the test inventories, the instruction files, the workflow YAML and the packaging includes. A lane that starts after the moves edits the final paths, and the findings file names the old ones, so tell each lane to search by symbol.

**Push the move commit once its gate is green, and start the lanes while CI runs it.** A move that breaks one platform shows there in minutes, before any lane builds on it.

**Read the packaging includes and the symlinks after a move.** A binary build lost its templates when a data directory moved and `[tool.nuitka] include-data-dir` still named the old path: read `include-data-dir`, `include-package-data`, `build-backend.source-exclude` and their peers. A relative symlink that targets a moved file dangles: list them with `git ls-files -s` (mode `120000`) and retarget each one in the same commit.

## Lanes

**Give each work package its own agent, in its own worktree, all in one tool-call block.** Spawn with `isolation: "worktree"`: a lane then never sees a sibling's half-done edit, and a crash leaves the shared tree intact. Seed the worktrees from the committed moves. A lane runs its focused tests with `--no-cov`, then the full suite once at the end.

**Write each lane brief with these parts, in this order.** The maintainer's intent in two sentences; the floors to assume; the owned files and the files nobody may touch; the rules below; the commands, with absolute paths and the exact test invocation; the report format of the sub-agent rules, with its parts named. Add the traps the survey found in that slice: a lane copies the patterns it sees, so an unlisted trap propagates.

**A lane never edits `pyproject.toml`, `uv.lock`, `changelog.md` or a generated asset.** It drafts its changelog bullets in its report, and names the floor or the lock change it needs. The orchestrator writes the changelog section once per phase, from the drafts, and step 1 consolidates it.

**A lane reports a failure in a test file it does not own, and never chases it.** The owner fixes it, or the orchestrator does after the join.

**Ask each lane to report its proposals and its helpers inventory, then act on both after the join.** The proposals are the moves, the cross-lane duplicates and the public API changes that ownership blocked. The inventory lists the generic helpers its modules define or re-implement inline: ANSI stripping, width measurement, write-if-changed, subprocess launch, env var parsing. Two inventories naming the same helper are one cross-lane duplicate.

## Instructions lane

**Give the repository's own instruction files a lane of their own: `AGENTS.md`, `.claude/agents/**` and `.claude/skills/**`.** Downstream, the lane covers only what the repository authors, as step 1's bundled-asset lane says: a synced copy is overwritten at the next sync, so a finding there goes to the step-8 report. The global instruction file of the maintainer's machine is out of scope: another tool of theirs tunes it. The lane runs after the code lanes join, since the code decides which rules still hold.

**Mechanize first, then refactor what remains.** A rule that code can check becomes a conformance test, a `lint-repo` check or an autofix rule, and the prose shrinks to a pointer. Only then relocate and compress what stays: a compression pass keeps a duplicate that a mechanization deletes.

**Mechanize each directive a machine can check, and keep the judgment calls as prose.** Checkable: a spelling, a placement, an ordering, a word ceiling, a required comment, a flag on a command, a file that must exist. Judgment: a verdict, a trade-off, a design choice, a harness quirk. The test for a candidate is whether a false failure costs an afternoon: a check that is under-inclusive by construction is still worth having.

**Prefer a `lint-repo` check to a test for a generic rule.** A test in this repository runs here alone; a `lint-repo` check reaches every repository that pins the release. Downstream, a `lint-repo` check is upstream work: the lane writes the test it can land, and reports the check for step 8.

**Give each `gh api` recipe in a skill a CLI option, and delete the pitfall prose with it.** A recipe with pitfalls attached, like the full SHA, `--allow-escape-sequences` or the stale `gh run list`, is a missing CLI option, and the option carries the pitfall once.

**Then give each surviving rule one verdict: drop, relocate, extract, compress or keep.** Drop a rule another layer states word for word, or whose target is gone. Relocate a rule about one function, test, workflow or page beside it: a docstring, a test docstring, a comment in the workflow, a comment at the top of the page. Extract a procedure with steps into a skill, or into the `references/` folder of the skill that runs it. Compress only what stays, and measure in tokens: a text saving under 10% keeps its original, and a corpus written under a word ceiling clears the bar nowhere, so keep is the common verdict.

**Never compress a `description`.** It is the retrieval surface the router matches against the user's own words: keep its redundant trigger phrases.

**Read the code before you settle a disagreement between a rule and its mechanism.** A rule that restates code drifts from it, and no test notices. Where the prose and the test disagree, the mechanism won, and the prose is the side to fix.

**Keep each deleted rule only where it is scar tissue.** A line that exists because someone made that mistake reads as redundant exactly because it now prevents the error: `git log -S` on it before you cut it.

**Repoint every consumer of a moved rule in the same edit.** A docs page that includes the file publishes what stays in it. A test or a packaging manifest reads the file by name. A sync writes generated content back over a comment that cites it: fix the generator instead. A base-class docstring renders on each subclass, so a cross-reference in it needs its full path.

**Gate the lane with the asset tests, the docs build and the suite.** `tests/test_claude_assets.py` and `tests/test_skills.py` hold the bundled assets to their contract: the directive word ceiling, the module paths, the config keys, the workflow files and the skill names each asset cites. A relocated rule that lands in a docstring needs the docs build, which is the only check on a cross-reference role. Measure each file before and after, and report both sizes.

## Join and cross-lane wave

**Merge each worktree per path, never with a working-tree checkout.** `git merge-file`, with the seed as the base, the main file as ours and the worktree file as theirs, touches no index: a parallel session's commit cannot sweep the merge in. `git apply -3` on an exported patch does the same job. Register each new file with `git add --intent-to-add` before the gate: an inventory test reads `git ls-files`, and an unregistered file fails it.

**Import every module in a fresh interpreter right after the join, before the suite.** A module one lane created imports a name another lane moved, and every lane's own suite was green. Derive the moved names from the code (names a new module defines that its old home no longer does), repoint the imports with an AST pass, then import each module once.

**Run one cross-lane agent after the join, on the shared tree, and give it every proposal and the merged inventory.** It applies the proposals, merges the duplicates the inventories exposed, and makes the moves the lanes could not. Never leave a proposal for the maintainer to decide: in every past pass, the answer to a parked list was "do all of them", one full round later. A lane that works on the shared tree follows the no-revert rule of the sub-agent rules.

**Grep the whole tree for each pattern the plan named, after the lanes join.** A survey misses files: a repository-wide sweep of placeholders once missed three test files that a later grep found.

## What the pass changes

- **Refactor for the reader who navigates the code.** Harmonize patterns, remove duplication, regroup related code, and give each module one concern. Simplify before you add.
- **Fix each bug the survey finds, with a test that fails on the pre-fix lines.** A bug that reached a release gets a changelog bullet; one introduced this cycle gets none. Never weaken a test to make it pass, and never pin a bug in one.
- **Break the public surface where a better foundation needs it, and record each break a consumer can reach.** A `**Breaking:**` bullet names each one. Who consumes the project decides what counts: a renamed Python symbol breaks a library's users, while a project that is invoked rather than imported owes a bullet only for a command, an option, a config key or an output.
- **Keep every name a sibling repository of the maintainer imports, private or not.** Grep the sibling checkouts beside this one for each removed or moved name before the move: a consumer there breaks on the next release, and its own tests cannot see it.
- **Use the Python features that `requires-python` provides, and leave that floor as it is.** The maintainer moves it: on their own, or on the proposal a new major allows below. Read the What's New page of each Python release up to the floor (`https://docs.python.org/3/whatsnew/3.{N}.html`), and adopt what reads better: `StrEnum`, `match` over a long `isinstance` chain, `itertools.pairwise`, `zip(strict=True)`, `str.removeprefix`, `contextlib.chdir`, `datetime.UTC`. `<cmd> run ruff -- check --select UP,FURB,PERF,SIM,C4 --no-fix` lists mechanical candidates that the shared rule set does not check: read each one before you apply it.
- **Delete code that no supported install runs.** A fallback for a Python below `requires-python`, a version guard, an `ImportError` fallback or a workaround for a dependency release below its floor is dead on every install. Keep a shim that waits on a release not out yet, with its `{todo}`.
- **Cut history from comments and docstrings.** A comment describes the code as it is now: delete "used to", "no longer", "since X.Y", "was renamed", the story of how a bug was found, and every mention of a removed feature. Keep the rule and its reason, in the present tense.
- **Lock each convention the pass applied in a conformance test.** A sweep that hoisted every function-local import, or put `encoding=` on every text I/O, earns a test that iterates the population and names the violator, or the next cycle undoes it.
- **Speed up a hot path only where a measurement shows the gain.** Compare against the old code in one interleaved run, with the median of 10 or more samples. Look first where past passes found the gains: the startup imports of the CLI (`python -X importtime -c "import {pkg}"`), one file parsed several times in one command, a log line formatted before its level is checked, a whole file read where a bounded slice does, a network call made twice for one answer, and a download that fetches every artifact to bump one.
- **Cache only a pure function of hashable arguments.** A cache that reads the environment, the working directory, the filesystem or the clock gives stale results to the next caller, and to the next test. A cache keyed on a file's path, size and mtime is the shape that holds for a parsed file. Never add work at import time, and never cache on a decoration-time singleton: a context-dependent value cached there made its own test flake.
- **Run `/repomatic-deps explore`, then apply each Adopt verdict that needs no higher floor, and each removal verdict.** Its § Removal candidates holds the rules of a replacement by stdlib code: rank by the packages freed per line written, keep what is public API or validates or writes user data, compare against the old package as the oracle, classify each mismatch and pin it with a test, one commit per dependency gated by the tests and mypy. Step 1's code lane runs `modernize --no-bump` after the pass.

On a new major, the pass also takes what a major release allows:

- **Propose a `requires-python` raise when the floor names a Python that upstream no longer maintains.** The oldest release that upstream still maintains, listed on https://devguide.python.org/versions/, is the floor to propose. State the proposal before the survey, and again in the step-7 report. Leave the floor as it is: the maintainer applies it with `/repomatic-test-matrix drop <version>`, or by hand where that skill is missing, since the test matrix and the ruff and mypy targets move with it. The next pass then uses what the new floor provides.
- **Delete every deprecated surface.** On another release, delete only the surfaces whose `**Deprecated:**` entry named this release or an earlier one. A plan that a docstring or an alias registry makes for the next major is not a trigger before that major: a pass once executed such a plan on a minor, and the maintainer reverted all of it.
- **Raise dependency floors only to releases older than `minimum-release-age`.** A `[project]` floor inside the cooldown blocks the release at `lint-deps`. Run `/repomatic-deps modernize` without `--no-bump`, and apply the Adopt verdicts of `explore` that need a higher floor. Then delete the compatibility code that each new floor makes dead, and rerun the removal audit of `explore`: a new floor turns a keep into a drop.

## Traps

- **Grep the tests for patch targets before you move a name.** A test patches a name where the caller looks it up, so `mock.patch("{old module}.{name}")` and `monkeypatch.setattr` keep working only while the caller imports from the old module. One rewire broke sixteen test seams for a one-line gain. Read each seam, then move the name and the patch target together.
- **Prove a symbol dead with `git grep`, never with `rg`.** A gitignored build tree, like `docs/_build`, names almost every symbol in stale HTML, so `rg` reports it alive. A symbol can also live through a CLI command name in workflow YAML, a bundled copy or a docs `automodule` page: grep those too. A hit in a released changelog section is history, not a caller.
- **Never rewrite the quote style of a string literal mechanically.** A test embeds a child script whose inner one-line strings use the other quote: one `encoding='utf-8'` to `encoding="UTF-8"` pass closed those strings early, and the child never printed its ready line.
- **Break an import cycle with a leaf module both sides import, never with a function-local import.** Move the shared name into a small module, and delete the lazy imports on both sides.
- **Resolve a default path from the module, never from the working directory.** A refactor that moved a default to `Path("docs/install.md")` let a test rewrite the real file. Give such a test an autouse fixture that points the default into `tmp_path`.
- **Seed a module-global cache from a session fixture, never from inside a test.** A CLI runner fixture pins `HOME` to an empty directory, so a cache filled inside a test records what that environment answered, for the rest of the worker's session.
- **Build the docs once, after the join, from the orchestrator.** A lane cannot build them, and the build is the only gate for an executable doc block: a `{click:run}` block fails open, and the build forces color, so an assertion on plain help layout fails there alone. Compare the warnings against a build of the last tag, as step 1 describes.
- **Restore a committed generated asset that the gate rewrote.** A docs build or a test can regenerate a checked-in capture from an environment-dependent input, like the program name a `python -m` launch reports. Stage by explicit path, as step 5 says.

## Gate, commit and hand over

- **Gate each phase with the tests, types and formatting checks of step 2, then commit it alone.** The phases are the moves, the lanes, the cross-lane wave and the workflow changes. When a floor moved, also run the shippable-deps and fresh-resolution checks. The step-1 lanes build on this tree, and a red tree sends each of them after failures it did not cause.
- **Push each phase once its gate is green, and watch its runs while the next phase works.** CI then checks the phase on every platform, and a Windows-only failure, like a fixture written in text mode, surfaces before the next phase builds on it. Read each run at the job level, as step 6 says.
- **Before each commit prompt, list every module move, public name removed, floor raised and measured speedup.** In normal use, that prompt is the review of the refactor, and a one-line summary hides the moves that the maintainer would refuse.
- **Give step 1 the list of moves and the list of deliberate removals.** The docs lane updates every page that names a moved module. The code lane gives each removal that users can reach a `**Breaking:**` bullet, and never brings it back.
- **Narrow the code lane after the pass.** It keeps its first layer and its constraints, and skips the second layer, which the pass did.
