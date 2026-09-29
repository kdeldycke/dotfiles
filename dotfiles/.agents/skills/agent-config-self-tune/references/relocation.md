# Relocation

An instruction file loads into every session of its project. Most sessions read a rule about one function, one test or one page for nothing. That rule also goes stale when the code moves without it. Relocation gives each rule one home, beside what it governs, and leaves the file with conventions and pointers.

Measured on one project file: 11,801 words became 848, and most of the removed text already existed in docstrings.

## Procedure

1. **Find the consumers of the file.** Search the tree for its name, in both letter cases. Look for a docs page that includes it, a test that reads it and a packaging manifest that ships it. Look also for the comments and docstrings that cite its sections. Each consumer constrains the edit: see § Traps.
2. **Compare each claim with its home.** For each identifier a claim names (function, constant, test, workflow, configuration key, page), open that home and read it. The table below gives the verdict.
3. **Write the missing part at the home.** Rewrite it for that home: a comment says how the code works now and why, with no history of the change. Keep exact strings, test names and thresholds.
4. **Rewrite the file.** Keep what § What stays lists. Add a pointer table: one row per area, with the path of its home. State the rule for later edits: a new rule goes to its home, and the file gets one row at most.
5. **Repoint the citations.** Each comment or docstring that cited the instruction file now cites the new home.
6. **Verify**, per § Verification.

To speed up step 2, list every identifier the file writes in backticks, and search the tree for each one. An identifier found in no other file marks a claim with no home yet, or a stale one.

| The comparison finds                  | Verdict of `SKILL.md`                               |
| :------------------------------------ | :-------------------------------------------------- |
| The home already says it.             | Drop                                                |
| The home lacks it.                    | Relocate                                            |
| The home and the file disagree.       | Resolve: read the code, then correct the wrong side |
| No code, test or page is its subject. | Keep, or Extract when it is a procedure             |

Expect stale claims: a file that restates code drifts from it, and no test notices. Read the behavior of the code before choosing a side. The docstring is sometimes the stale one.

## Homes

Pick the narrowest home that owns the knowledge.

| Knowledge                                  | Home                                                     |
| :----------------------------------------- | :------------------------------------------------------- |
| Why one function or constant is as it is   | Its docstring                                            |
| A rule common to a family of functions     | The module docstring                                     |
| A rule that a test enforces                | The docstring of that test                               |
| Guidance for the whole test suite          | The package docstring of the tests                       |
| Why a setting has its value                | A comment beside the setting                             |
| The rules of a workflow or of its jobs     | A comment in the workflow, in a part the repository owns |
| How to edit one hand-maintained docs page  | A comment at the top of that page                        |
| A procedure with steps                     | The skill that does it                                   |
| Setup and commands for a human contributor | The contributing page of the documentation               |
| A policy for the users of the project      | A documentation page                                     |

Prefer a test to a sentence. A rule that code can check becomes a test, and its docstring carries the reason.

## What stays

- A convention with no code to sit beside: vocabulary, example data, commit prefixes, the name of a new file.
- A distinction between two subjects that share a name.
- A roster of deliberate exemptions from a wider rule.
- The pointer table.

## Traps

- **A docs page includes the file.** What stays in the file is then published. Give the page its own copy of what human contributors need, and keep each heading of the file different from the headings of that page.
- **A test or a packaging manifest reads the file.** The file must keep its name and its place.
- **Generated content cites the file.** A workflow header or a configuration comment that a sync writes comes back at the next sync. Read the template first. Fix the generator in its own repository, and leave the copy alone.
- **A program reads the home.** A module docstring given to `argparse` prints in `--help`. A Click command docstring is help text, which takes no markup.
- **A parser reads the page.** Put the comment outside each table and each generated region that a test or a generator reads back. Never realign such a table.
- **A base class holds the docstring.** Documentation tools render an inherited docstring on each subclass, so a cross-reference in it needs its fully qualified target.

## Verification

1. Run the tests that scan prose: docstring checks, glyph scans, link checks. Then run the suite.
2. Compare the lint findings of each edited file between `HEAD` and the working tree. Equal counts prove the edit added nothing.
3. Build the documentation twice, from an export of `HEAD` and from the working tree, and compare the two warning lists. Build both in a fresh environment that holds the same dependency groups: a module that fails to import turns each reference to it into a false warning.
4. Measure the file again.
