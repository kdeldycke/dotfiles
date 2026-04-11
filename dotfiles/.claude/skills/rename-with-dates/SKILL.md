---
name: rename-with-dates
description: Rename documents and files (PDFs, images, screenshots, etc.) by reading their content to extract the effective/publication date, then renaming them with a "YYYY-MM-DD - Clear descriptive title.ext" format. Use when the user wants to organize files with date prefixes based on document content.
argument-hint: '[directory or files]'
---

# Rename Documents with Date Prefixes

Rename files in a folder by extracting the **effective date** from their content and giving them a clean, human-readable title.

## Target format

```
YYYY-MM-DD - Clear descriptive title.ext
```

Title casing: capitalize only the first word and proper nouns (title case), like a sentence.

Examples:

- `2023-11-01 - General terms and conditions.pdf`
- `2025-08-01 - Credit card fees and charges.pdf`
- `2025-12-01 - Key facts statement - Term deposits.pdf`
- `2024-06-15 - Rewards program earning structure.png`
- `2024-03-01 - Schedule of charges.pdf`

## Supported file types

- **PDFs**: Read the first few pages (and last page if needed) to find dates and understand content
- **Images / Screenshots** (PNG, JPG, etc.): View the image to understand its content, then summarize it into a clear descriptive title. For screenshots, the date is often embedded in the filename (e.g., `Screenshot 2026-01-12 at 11.07.33.png` → date is 2026-01-12)
- **Other documents**: Read content where possible to extract dates and meaning

## Workflow

1. **List files** in the target directory (default: current working directory, or `$ARGUMENTS` if provided)
2. **Skip** files that already follow the `YYYY-MM-DD - Title.ext` pattern (but offer to clean up their titles if needed)
3. **Read each file** to find the effective date and understand the content:
   - **For PDFs**:
     - Look for explicit "Effective from..." or "Effective date" statements — prefer these
     - Look for version dates in footers (e.g., "08/2025", "v. August 14, 2023")
     - Look for dated headers, cover pages, or document stamps
     - Use the **effective/applicability date**, not the publication or copyright date
   - **For images/screenshots**:
     - View the image to understand what it shows
     - Extract date from the original filename if it contains one (e.g., `Screenshot 2026-01-12 at ...`)
     - If the image contains visible dates in its content, prefer those
     - If no date can be found, ask the user
   - Match the date precision to what the document provides: use `YYYY-MM-DD` for exact dates, `YYYY-MM` for month-only, `YYYY` for year-only
4. **Choose a clear title**:
   - Use sentence case: capitalize only the first word and proper nouns
   - Be descriptive but concise (e.g., "Credit card fees and charges", not "popularbankname_credit_card_fees_charges")
   - For screenshots: summarize what the image shows (e.g., "Rewards program earning structure", "Account balance overview")
   - Keep well-known abbreviations uppercase: KFS, FAQ, T&C
   - Remove redundant institution names if the folder context already makes it clear
5. **Present a summary table** showing current name, detected date, and proposed new name
6. **Rename all files** after presenting the plan
7. **Post-rename analysis** — after renaming, scan the folder for cleanup opportunities and present a report with three sections:
   - **Duplicates**: Compare files with similar titles using MD5 checksums (`md5 -r`). Files with identical hashes are exact duplicates. Propose keeping one and trashing the others.
   - **Superseded documents**: Identify files that are older versions of the same document type (e.g., "Personal banking general T&C" from 2023 vs 2025). The newer version supersedes the older. Propose trashing the older version.
   - **Expired documents**: For time-bound documents (campaigns, offers, promotions) that specify a validity period (e.g., "1 November 2025 – 31 December 2025"), check if the end date has passed relative to today. Propose trashing expired ones. Do **not** flag standing T&Cs, KFS documents, or privacy policies — only documents with explicit campaign/offer end dates.
8. **Verify** by listing the final result

## Multi-language PDF stripping

Many legal/banking documents repeat the same content translated across several languages, organized as consecutive blocks of pages (e.g., pages 1-10 in English, 11-20 in Arabic, 21-30 in Bulgarian). When detected, propose stripping to keep only **English and French** pages.

### Detection

1. While reading a PDF, sample pages throughout the document (not just the beginning) to detect language blocks
2. A document qualifies for stripping **only if**:
   - The content is repeated in blocks of pages, each block being a full translation of the same content
   - Each page is in a **single language** — if a page mixes multiple languages (e.g., English and Arabic side by side, or bilingual tables), do **NOT** propose stripping that document
   - The granularity is the **page**: each page belongs to exactly one language
3. Identify the page ranges for each language block (e.g., "Pages 1-25: English, Pages 26-50: Arabic, Pages 51-75: French")

### Proposal

- Present findings clearly: list each language detected and its page range
- Propose which pages to **keep** (English and French) and which to **remove**
- Ask the user for confirmation before modifying the PDF
- Use a tool like `qpdf` or `pdftk` to extract only the desired pages into a new file
- Replace the original file with the stripped version (or keep a backup if the user prefers)

### When NOT to strip

- Pages contain multiple languages (bilingual layouts, side-by-side translations)
- The translations are not full-document blocks (e.g., just a translated summary at the end)
- The document has only one language
- You are not confident about the language boundaries

## Required tools

This skill depends on third-party CLI tools. At the start of execution, check if each is available and propose to install any that are missing via `brew install`.

| Tool        | Brew package | Used for                                                      |
| ----------- | ------------ | ------------------------------------------------------------- |
| `qpdf`      | `qpdf`       | Extracting page ranges from PDFs (multi-language stripping)   |
| `pdftotext` | `poppler`    | Extracting text per page for language detection in large PDFs |
| `exiftool`  | `exiftool`   | Reading PDF metadata (CreationDate, ModDate) as date fallback |

`mdls` (macOS built-in) can also be used for metadata and does not need installation.

If a missing tool is needed for the current run, propose the install command and ask the user before proceeding. If the tool is not needed (e.g., no multi-language PDFs detected, so `qpdf` is not required), skip silently.

## Important rules

- Always extract dates from **file content** (or filename for screenshots), never from file system metadata
- For PDFs, read the first few pages (and last page if needed) to find the date
- For images, always view the image to produce a meaningful title — never just use the original filename
- If a document has both a publication date and an "Effective from" date, use the effective date
- If no date can be found in the content or filename, fall back to PDF metadata (CreationDate, ModDate) using `mdls` or `exiftool`. Only use file system dates (modification date) as a last resort
- If no date can be found at all, flag it to the user and ask what to do
- Use `mv` for renaming — never copy-and-delete
