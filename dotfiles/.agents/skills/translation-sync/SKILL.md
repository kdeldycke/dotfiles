---
name: translation-sync
description: Detect stale translations in readme.*.md and contributing.*.md files by comparing structure and content against the English source, then draft updated translations for changed sections.
model: sonnet
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob, Agent
argument-hint: '[lang-code]'
---

## Context

!`ls readme.*.md 2>/dev/null || echo "No readme translations"`
!`ls .github/contributing.*.md 2>/dev/null || echo "No contributing translations"`
!`[ -f repomatic/__init__.py ] && echo "CANONICAL_REPO" || echo "DOWNSTREAM"`
!`[ -d repomatic/data/awesome_template ] && echo "HAS_AWESOME_TEMPLATE" || echo "NO_AWESOME_TEMPLATE"`

## Instructions

You synchronize translated markdown files with their English sources. The translation workflow in these repositories is documented in `contributing.md` § Pull-requests and issues: contributors propagate changes to all `readme.*.md` files using automatic translation tools, and bilingual contributors refine the result later.

This skill automates the detection side: find what drifted, show the delta, and draft updated translations for the stale sections.

### Scope

**In downstream `awesome-*` repos:** Sync `readme.*.md` files against `readme.md`.

**In the repomatic canonical repo:** Sync `contributing.*.md` against `contributing.md` inside `repomatic/data/awesome_template/.github/`. The awesome-template is the source of truth for contributing guides synced to all downstream repos, so keeping its translations current benefits every downstream project.

### Argument handling

- `$ARGUMENTS` can be a language code (e.g., `zh`, `fr`, `ja`) to limit the sync to one language. If empty, process all `*.{lang}.md` translation files found.

### Step 1: Discover translation pairs

Find all files matching the `*.{lang}.md` pattern (e.g., `readme.zh.md`, `contributing.fr.md`). For each, identify the English source by stripping the language suffix (e.g., `readme.zh.md` pairs with `readme.md`).

If context shows `CANONICAL_REPO` and `HAS_AWESOME_TEMPLATE`, look inside `repomatic/data/awesome_template/.github/` instead of the repo root.

Report the discovered pairs as a table:

| English source | Translation    | Language |
| :------------- | :------------- | :------- |
| `readme.md`    | `readme.zh.md` | zh       |

If no translation files are found, tell the user and suggest creating one.

### Step 2: Structural comparison

For each pair, compare the heading structure (all `#`, `##`, `###`, `####` headings). Report:

1. **Heading count match** — same number of headings at each level.
2. **Missing sections** — headings present in English but absent from the translation.
3. **Extra sections** — headings in the translation with no English counterpart (may indicate stale removed sections).
4. **Order alignment** — whether sections appear in the same order.

### Step 3: Content drift detection

For each section (delimited by headings), compare the English and translated versions:

1. **Link inventory** — extract all URLs from both. Flag URLs present in English but missing from the translation, or vice versa. URLs should be identical (not translated).
2. **List item count** — count bullet points and numbered items per section. A mismatch signals added or removed entries.
3. **Code block count** — code blocks should match 1:1.
4. **Badge/image parity** — compare `![` image references and shield.io badge URLs.
5. **HTML block parity** — compare `<p>`, `<table>`, and other HTML blocks that should be structurally identical.

### Step 4: Staleness report

Present findings grouped by severity:

**Structure breaks** (sections added/removed in English but not reflected):

| Section          | Issue                    | English | Translation |
| :--------------- | :----------------------- | :------ | :---------- |
| `## New Section` | Missing from translation | line 45 | —           |

**Content drift** (section exists in both but content diverged):

| Section      | Signal                   | Details                                           |
| :----------- | :----------------------- | :------------------------------------------------ |
| `## Billing` | 3 links added in English | `example.com/a`, `example.com/b`, `example.com/c` |
| `## IAM`     | 2 list items removed     | English has 12, translation has 14                |

**Cosmetic** (non-blocking but worth fixing):

| Issue                              | Location   |
| :--------------------------------- | :--------- |
| Language badge links inconsistent  | line 20-21 |
| Trailing whitespace in translation | line 134   |

### Step 5: Draft translations for stale sections

For each section flagged as drifted or missing, draft an updated translation:

1. Show the current English section content.
2. Show the current translation (if it exists).
3. Draft the updated translation, preserving:
   - All URLs, code blocks, and HTML exactly as in the English source.
   - The translation style and terminology already established in the file (read the existing translation to learn the voice).
   - Markdown formatting and indentation.
4. Present the draft as a diff the user can review and apply.

Do not auto-apply changes. Present all drafts for user review first.

### Step 6: Validate language badges

Check that both the English source and translation include matching language switcher badges. The expected pattern (from existing repos):

```markdown
<p align="center">
  <a href="..." hreflang="en"><img src="https://img.shields.io/badge/lang-English-blue?style=flat-square" lang="en" alt="English"></a>
  <a href="..." hreflang="zh"><img src="https://img.shields.io/badge/lang-中文-blue?style=flat-square" lang="zh" alt="中文"></a>
</p>
```

Flag files missing the badge block or with mismatched language entries.

### Guidelines

- URLs, code blocks, and HTML tags are never translated. They must be identical in source and translation.
- Section ordering in the translation must match the English source.
- When drafting translations, match the register and terminology of the existing translated content. Do not impose a different style.
- For `awesome-falsehood`, sections are in alphabetical order (per `contributing.md`). Verify the translation preserves this.
- The PR template checklist item "I applied the changes to all translatations in `readme.*.md` files" is the contributor-facing enforcement. This skill is the maintainer-facing verification.

### Next steps

Suggest the user run:

- `/awesome-triage` to check if any open PRs need translation updates before merging.
- `/repomatic-audit` to verify broader upstream/downstream alignment.
