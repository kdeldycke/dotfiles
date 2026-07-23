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

Period documents that cover a date range (statement exports, period reports) may extend the prefix to `YYYY-MM-DD--YYYY-MM-DD - Title.ext` — preserve that convention where a folder already uses it.

## Supported file types

- **PDFs**: Read the first few pages (and last page if needed) to find dates and understand content. The Read tool rejects PDFs over 20MB: render their pages to images with `pdftoppm -png -r 30` and view those instead
- **Images / Screenshots** (PNG, JPG, etc.): View the image to understand its content, then summarize it into a clear descriptive title. For screenshots, the date is often embedded in the filename (e.g., `Screenshot 2026-01-12 at 11.07.33.png` → date is 2026-01-12)
- **Office documents**: for `.xlsx`, read `docProps/core.xml` inside the zip (`unzip -p file.xlsx docProps/core.xml`) for `dcterms:created`; for Apple `.numbers`, the package often embeds a readable `preview.jpg` or `preview.pdf`. A stray `.~lock.*#` file next to a document is a LibreOffice lock: the document may be open somewhere (possibly on another synced machine); stale locks are trash candidates
- **Emails exported/printed to PDF**: use the email's sent date from its header, never the print/export date; derive the title from the subject and outcome of the thread
- **Photo archives**: a folder full of personal photos (`IMG_1234.jpeg` dumps) is an archive, not a document set — propose skipping it wholesale instead of dating each file. Rename a photo only when it acts as a document (appliance rating plate, meter photo, signed-form snapshot), dating it from EXIF `DateTimeOriginal` via `exiftool`
- **Other documents**: Read content where possible to extract dates and meaning

## Workflow

1. **List files** in the target directory (default: current working directory, or `$ARGUMENTS` if provided)
2. **Skip** files that already follow the `YYYY-MM-DD - Title.ext` pattern (but offer to clean up their titles if needed). A bare date with no title (like `2023-08-17.pdf`) is not compliant — read the file and add the missing title (often just `Invoice` or `Receipt` inside a provider folder, where the folder name already gives context)
3. **Read each file** to find the effective date and understand the content:
   - **For PDFs**:
     - Look for explicit "Effective from..." or "Effective date" statements — prefer these
     - Look for version dates in footers (e.g., "08/2025", "v. August 14, 2023")
     - Beware date-lookalike version codes: a code like `V160701.1` reads as YYMMDD but may be template artwork — if the same code appears on documents with different effective dates, it is not a date. Reference codes (like CRN `FRM021121`) often embed a MMDDYY date and corroborate other evidence at month precision
     - Filenames that are bare reference codes or portal export IDs (like `LICDSO202600109568.pdf` or `bill-3733181.pdf`) are almost always invoices or receipts — open them; the code itself rarely matters to the user
     - When two files resolve to the same date and the same title, re-inspect before renaming: one is usually a different document type (like an annual statement of accounts issued the same day as the monthly invoice)
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
   - When two documents of the same type share the same effective date but cover different product segments, disambiguate in the title (like `KFS - Credit cards (Skywards, Cash+ and Live+)` vs `KFS - Credit cards (Private Bank, Premier and Advance)`)
   - Manuals and spec sheets: title as `Brand Model - Doc type` (like `Gorenje WHT923E5XUK - Cooker hood manual`); vendor doc codes often embed the publication date (Grohe `…/02.19` = February 2019)
5. **Present a summary table** showing current name, detected date, and proposed new name
6. **Rename all files** after presenting the plan. On case-insensitive filesystems (macOS APFS), a case-only rename fails with "are the same file" — do it in two steps through a temporary name
7. **Post-rename analysis** — after renaming, scan the folder for cleanup opportunities and present a report with three sections:
   - **Duplicates**: Compare files with similar titles using MD5 checksums (`md5 -r`). Files with identical hashes are exact duplicates. Propose keeping one and trashing the others. If an undated file is an exact duplicate of an already-compliant one, do **not** rename it into a name collision — leave its name untouched and propose trashing it. Also compare content when hashes differ but titles match: re-downloads of the same document often differ only in PDF metadata. Printed document numbers (invoice number, receipt number, DocuSign envelope ID) are reliable fingerprints for catching these content-duplicates.
   - **Superseded documents**: Identify files that are older versions of the same document type (e.g., "Personal banking general T&C" from 2023 vs 2025). The newer version supersedes the older. Propose trashing the older version.
   - **Expired documents**: For time-bound documents (campaigns, offers, promotions) that specify a validity period (e.g., "1 November 2025 – 31 December 2025"), check if the end date has passed relative to today. Propose trashing expired ones. Do **not** flag standing T&Cs, KFS documents, or privacy policies — only documents with explicit campaign/offer end dates.

   - **Not applicable**: documents covering products or services the user does not hold (other product tiers' T&C, KFS for products never subscribed, forms for other customer segments). Ask the user to confirm their actual holdings, then propose trashing the rest — documents for held products stay, as they are the contractual record of the terms in force.

   When the user approves trashing, move the files into a dated subfolder like `~/.Trash/{folder} cleanup YYYY-MM-DD/` so the whole batch stays grouped and recoverable. Writing into `~/.Trash` is typically blocked by the command sandbox — run that step outside the sandbox.
8. **Verify** by listing the final result with plain binaries — `ls` may be aliased (eza, lsd) and print nothing when piped — and run a compliance sweep: `/usr/bin/find . -type f | sed 's|.*/||' | grep -Ev '^[0-9]{4}(-[0-9]{2})?(-[0-9]{2})?(--[0-9]{4}-[0-9]{2}-[0-9]{2})? - '` should return only intentionally held files

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
- Use `qpdf` to extract only the desired pages into a new file (`qpdf in.pdf --pages . 1-4 -- out.pdf`)
- Verify before replacing: the original's `qpdf --show-npages` must match the detected page total, and the stripped output must match the kept range length — skip the file on any mismatch
- Replace the original file with the stripped version, and stash the pre-strip originals in the Trash batch folder (like `~/.Trash/{folder} cleanup YYYY-MM-DD/pre-strip originals/`) as a safety net
- For more than a handful of files, drive the loop with a small Python script (manifest of filename + keep range + expected total) instead of ad-hoc shell commands

### When NOT to strip

- The document is **signed**: signed forms and agreements are legal records — never alter them, even when their languages are cleanly block-structured
- Pages contain multiple languages (bilingual layouts, side-by-side translations)
- The translations are not full-document blocks (e.g., just a translated summary at the end)
- The document has only one language
- You are not confident about the language boundaries

## Required tools

This skill depends on third-party CLI tools. At the start of execution, check if each is available and propose to install any that are missing via `brew install`.

| Tool        | Brew package | Used for                                                                             |
| ----------- | ------------ | ------------------------------------------------------------------------------------ |
| `qpdf`      | `qpdf`       | Extracting page ranges from PDFs (multi-language stripping), page counts (`--show-npages`) |
| `pdftoppm`  | `poppler`    | Rendering PDF pages — the Read tool depends on it to view PDFs at all                |
| `pdftotext` | `poppler`    | Extracting text per page for language detection in large PDFs                        |
| `exiftool`  | `exiftool`   | Reading PDF metadata (CreationDate, ModDate) as date fallback                        |

`mdls` (macOS built-in) can also be used for metadata and does not need installation.

If a missing tool is needed for the current run, propose the install command and ask the user before proceeding. If the tool is not needed (e.g., no multi-language PDFs detected, so `qpdf` is not required), skip silently.

If the target folder contains any PDFs, install `poppler` first thing: without `pdftoppm` the Read tool cannot render PDF pages, so no PDF can be inspected at all. Note that `brew install` writes to `/opt/homebrew` and usually needs to run outside the command sandbox.

## Important rules

- Always extract dates from **file content** (or filename for screenshots), never from file system metadata
- For PDFs, read the first few pages (and last page if needed) to find the date
- For images, always view the image to produce a meaningful title — never just use the original filename
- If a document has both a publication date and an "Effective from" date, use the effective date
- If no date can be found in the content or filename, fall back to PDF metadata (CreationDate, ModDate) using `mdls` or `exiftool`. Only use file system dates (modification date) as a last resort
- If no date can be found at all, flag it to the user and ask what to do
- Use `mv` for renaming — never copy-and-delete
- Folders can change while you work (the user may be acting in parallel, or cloud sync may intervene): re-check that files still exist before acting on them, and if files vanish mid-run, surface it to the user — never restore things from the Trash on your own initiative. Folders may also be renamed mid-run: if a move fails, re-resolve the path before assuming the file is gone
- Reading several look-alike files in one parallel batch (same provider, same visit date, same document family) risks cross-attributing the returned pages to the wrong filename — one run swapped a prescription and a tomography report scanned the same day, and only the user caught it. Read ambiguous siblings one at a time, and after renaming a batch of same-day scans, re-render a page of each renamed file to confirm its content matches the new title
- For large trees, fan out read-only subagents to extract dates and propose titles per folder, but review their proposals and execute all renames yourself so titles stay consistent across folders
