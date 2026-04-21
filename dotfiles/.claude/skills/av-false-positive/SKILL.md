---
name: av-false-positive
description: Scan a release on VirusTotal and generate false positive submission instructions for flagged AV vendors.
model: opus
disable-model-invocation: true
allowed-tools: Bash, Read, Write, Grep, Glob, Agent
argument-hint: '[version]'
---

## Context

!`gh repo view --json nameWithOwner --jq '.nameWithOwner' 2>/dev/null`
!`gh release view --json tagName --jq '.tagName' 2>/dev/null`
!`grep -m1 'license' pyproject.toml 2>/dev/null`
!`grep -m1 'name' pyproject.toml 2>/dev/null`
!`grep -A1 '\[project.urls\]' pyproject.toml 2>/dev/null | head -5`

## Instructions

Scan release binaries on VirusTotal and generate per-vendor false-positive submission files for any flagged artifacts.

### Step 1: resolve version and artifacts

If `$ARGUMENTS` is empty, use the latest release tag from the context above. Otherwise treat `$ARGUMENTS` as the version (accept both `6.2.1` and `v6.2.1`; normalize to bare version for filenames, `v`-prefixed for tags per CLAUDE.md § Version formatting).

Detect the repository from the context (`nameWithOwner`). Extract the project name, license, and homepage URL from `pyproject.toml`.

List all release assets:

```shell-session
$ gh release view v{VERSION} --json assets --jq '.assets[].name'
```

### Step 2: upload to VirusTotal (or retrieve existing results)

Use the `scan-virustotal` CLI command for the upload. But to get per-engine detection details (which the CLI does not expose), also query the VT API directly via Python with the `vt` library.

The VT API key comes from: `$VIRUSTOTAL_API_KEY` env var, or ask the user.

For each binary artifact (`.bin`, `.exe`):

1. Download via `gh release download`.
2. Compute SHA256 locally.
3. Check `GET /api/v3/files/{sha256}` to see if VT already has results.
4. If not found or results are stale (older than 7 days), upload via `POST /api/v3/files`.
5. Poll `GET /api/v3/analyses/{id}` until `status == "completed"`.
6. Handle rate limits (HTTP 429) by waiting 60 seconds and retrying.

### Step 3: collect results

For each artifact, record:

- Filename, file size in bytes
- SHA256
- VT report URL: `https://www.virustotal.com/gui/file/{sha256}`
- Total engines scanned
- Number of malicious detections
- For each engine that flagged it: engine name and detection name

Also record the VT report URLs for the clean `.whl` and `.tar.gz` source distributions (used as evidence in every submission).

### Step 4: print summary table

Print a markdown table:

| Artifact   | Detections | VT report | Verdict              |
| ---------- | ---------- | --------- | -------------------- |
| `filename` | N/M        | [link]    | Clean / FP (engines) |

### Step 5: generate per-vendor submission files

For each vendor in § Vendor definitions, check if any artifacts were flagged by that vendor's engine(s). If so, generate `fp-submission-{vendor}.md` at the project root.

Only generate a file for a vendor if at least one artifact was flagged by that vendor.

#### Output format: fully self-contained, zero cross-references

Each submission file must be optimized for copy-paste. The maintainer should be able to work through each submission without scrolling back or cross-referencing. Concretely:

- Never write "copy from above" or "see the file section above". Every field value must be spelled out inline at the point of use.
- For vendors requiring one submission per file: repeat the full form walkthrough for each binary as a separate `## Submission N` section with `---` separators.
- For vendors accepting a single submission covering multiple files: one section is fine, but list every binary with its full details (SHA256, VT link, detection name, download URL) inline in the text.
- Every pre-written text block must include the specific binary's VT scan link, the clean source distribution VT links, and the GitHub release link. No placeholders: use the actual URLs.

#### Dynamic project metadata

All submission text blocks must derive project details from `pyproject.toml` and git metadata:

- **Project name**: from `[project] name`.
- **License**: from `[project] license`.
- **Homepage/PyPI URL**: from `[project.urls]`.
- **Maintainer name**: from `git config user.name` or `[project] authors`.
- **Previous FP reference**: search the repo's GitHub issues for "false positive" or "VirusTotal" to find a prior reference issue. If none exists, omit the reference.

#### Vendor definitions

User-facing documentation of vendor portals, submission priority, and common issues is in [`docs/security.md` § AV false-positive submissions](https://kdeldycke.github.io/repomatic/security.html#av-false-positive-submissions).

##### Microsoft (engines: `Microsoft`)

- Portal: https://www.microsoft.com/en-us/wdsi/filesubmission?persona=SoftwareDeveloper
- Requires Microsoft account login. Select "Software developer" on the persona page.
- **One file per form submission.** Generate a separate `## Submission N` section per flagged binary.
- Only include binaries where Microsoft's own engine returned `category == "malicious"`. Windows ARM64 binaries are typically not flagged by Microsoft (only by MaxSecure), so check before including.
- macOS binaries can be flagged by Microsoft too (with `Wacatac` variants): include them if detected.
- Form fields per binary:

| Field                                                                | Value                                                         |
| -------------------------------------------------------------------- | ------------------------------------------------------------- |
| **Microsoft security product used to scan the file**                 | `Microsoft Defender Antivirus (Windows 10)` or `(Windows 11)` |
| **Company Name**                                                     | Maintainer name from project metadata                         |
| **Do you have a Microsoft support case number?**                     | No                                                            |
| **Select the file**                                                  | Upload the exact filename                                     |
| **Should this file be removed from our database at a certain date?** | No                                                            |
| **What do you believe this file is?**                                | `Incorrectly detected as malware/malicious`                   |
| **Detection name**                                                   | Exact detection name for this binary                          |
| **Definition version**                                               | (leave blank)                                                 |
| **Additional information**                                           | Paste the text below                                          |

- Additional information: **1900 character limit.** Include: binary's VT scan link, clean `.whl` and `.tar.gz` VT links, GitHub release link, project URL, PyPI URL, license, previous FP reference if found.
- **Known portal issues:** the upload sometimes fails with CORS errors or stuck progress modals (auth session expiring mid-upload). Workaround: sign out, clear cookies for `microsoft.com` and `wdsiprod.westus.cloudapp.azure.com`, sign back in, submit immediately. Also check the URL doesn't have a duplicated `?persona=SoftwareDeveloper&persona=SoftwareDeveloper` parameter.

##### BitDefender (engines: `BitDefender`, `ALYac`, `Arcabit`, `Emsisoft`, `GData`, `MicroWorld-eScan`, `VIPRE`)

- Portal: https://www.bitdefender.com/submit/
- BitDefender's engine powers ~6 downstream vendors. Fixing BitDefender removes the most detections per submission.
- Only list artifacts flagged by the `BitDefender` engine itself (not downstream).
- **One file per submission.** Max 25 MB per file upload.
- The **"Sensitive files / Screenshot" field is mandatory**: instruct the user to take a screenshot of the VT report page showing the BitDefender detection row.
- Form fields per binary:

| Field                            | Value                                                              |
| -------------------------------- | ------------------------------------------------------------------ |
| **Select the category**          | `False Positive`                                                   |
| **Full Name**                    | Maintainer name from project metadata                              |
| **E-mail**                       | (user's email)                                                     |
| **Sample type**                  | `File`                                                             |
| **Attach a file**                | Upload the exact filename                                          |
| **Detection name**               | Exact detection name                                               |
| **Description**                  | Paste the pre-written text                                         |
| **Sensitive files / Screenshot** | Screenshot of the VT report page showing the BitDefender detection |

- Generate one complete `## Submission N` section per binary.
- **Known portal issues:** the form sometimes returns "Your request could not be registered!" with no details. This is a backend issue on BitDefender's side. Retry later.

##### ESET (engines: `ESET-NOD32`)

- Method: email to `samples@eset.com`
- Alternative portal: https://support.eset.com/en/kb141
- **Single email covering all flagged binaries.** Attach files in a password-protected ZIP (password: `infected`).
- **Email attachment limit: ~24 MB.** Nuitka binaries are ~23 MB each, so only one binary fits in the ZIP. Attach the first binary and reference all others by SHA256 and direct download URL in the email body so ESET can fetch them.
- Email subject format: `False positive: {detection_name} in {Project Name} {VERSION}`
- Email body must list per binary: filename, SHA256, detection name, VT report link, download URL. Also include clean source distribution VT links and GitHub release link.
- ESET is the most reliable submission channel since it doesn't depend on any web portal being up.

##### Symantec / Broadcom (engines: `Symantec`)

- Portal: https://symsubmit.symantec.com/false_positive
- Click "Clean software incorrectly detected" on the landing page.
- **The FP form does not accept `.exe` or `.bin` file uploads.** The file upload field only accepts images, logs, and text files (for supporting evidence). Use hash submission instead.
- **Hash submission accepts only one hash per form.** To cover multiple binaries: submit the hash of one binary in the form field, and list all other binaries with their SHA256 hashes and VT links in the Additional Information text.
- **Single submission covering all binaries** using the approach above.
- The Additional Information field has a 5000 character limit.
- **Formatting caveat:** the confirmation email renders the Additional Information as a single paragraph with no newlines. Use short, clearly separated lines and label each section (like `Binary 1:`, `Binary 2:`) so the text remains readable even when flattened.
- Form structure has three fieldsets:

**Product Details:**

| Field                             | Value                                                                                                                 |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| **Which product were you using?** | `Symantec Endpoint Protection 16.x` (avoid "Don't know": it maps to `UNKNOWN` in their tracking system)               |
| **When did the detection occur?** | `When downloading or uploading a file`                                                                                |
| **Which type of detection?**      | `Download/File Insight (Reputation Based Detection)` (best match for `ML.Attribute.*` detections; avoid "Don't know") |
| **Detection Name**                | Exact detection name                                                                                                  |

**Submission Details:**

| Field               | Value                                      |
| ------------------- | ------------------------------------------ |
| **Submission Type** | `Provide an MD5 or SHA-256 hash of a file` |
| **File Hash**       | SHA256 of first binary                     |

**Additional Information** (expand the collapsed section):

| Field                         | Value                     |
| ----------------------------- | ------------------------- |
| **Recurring False Positive?** | `Yes`                     |
| **Business Impact?**          | `Medium`                  |
| **Application Type?**         | `Third Party Application` |

Then paste the description text listing all binaries with SHA256, VT links, clean source VT links, and GitHub release link.

**Your Details:**

| Field              | Value                                 |
| ------------------ | ------------------------------------- |
| **Contact Name**   | Maintainer name from project metadata |
| **Email Address**  | (user's email)                        |
| **Site ID Number** | (leave blank)                         |

##### Avast/AVG (engines: `Avast`, `AVG`)

- Portal: https://www.avast.com/submit-a-sample
- Shared engine: one submission covers both Avast and AVG. Include artifacts flagged by either engine.
- **One file per submission.** Select "I want to report a false detection (false positive)".
- Generate one complete `## Submission N` section per binary with all details inline.
- **Known portal issues:** the form sometimes returns "An internal error occurred while sending the form." This is a backend issue. Retry later.

##### Sophos (engines: `Sophos`)

- Portal: https://support.sophos.com/support/s/filesubmission
- **Max 25 MB total per submission** (not per file). Nuitka binaries are ~23 MB each, so only one binary fits per submission.
- **One binary per form submission.**
- PUA detections require justification of the software's legitimate purpose. The description must explain what the project does and list its distribution channels.
- Form fields per binary:

| Field                                    | Value                      |
| ---------------------------------------- | -------------------------- |
| **First Name**                           | Maintainer first name      |
| **Last Name**                            | Maintainer last name       |
| **Country**                              | (user's country)           |
| **Email Address**                        | (user's email)             |
| **About You**                            | `Using a free product`     |
| **Operating System**                     | `Windows`                  |
| **Why do you want to send this sample?** | Paste the pre-written text |
| **File**                                 | Upload the exact filename  |

- Generate one complete `## Submission N` section per binary.

#### Common rules for all vendors

Every binary entry in every submission file must include:

- The binary's own VT report link (`https://www.virustotal.com/gui/file/{sha256}`)
- The VT report links for the clean `.whl` and `.tar.gz` (as comparison evidence)
- The GitHub release link (`https://github.com/{owner/repo}/releases/tag/v{VERSION}`)
- The download URL for the binary (`https://github.com/{owner/repo}/releases/download/v{VERSION}/{filename}`)

Pre-written text blocks must mention: Nuitka `--onefile` compilation, open-source project, GitHub and PyPI URLs, license from `pyproject.toml`, and the previous FP issue reference if one was found in the repo's GitHub issues.

#### Submission priority order

1. **Microsoft**: most influential engine. ML detections (`Sabsik`, `Wacatac`) are the most impactful to fix.
2. **BitDefender**: their engine powers ~6 downstream vendors. Highest detection-removal-per-submission ratio.
3. **ESET**: reliable email channel, no portal dependency.
4. **Symantec**: ML detections may take 3-7 business days.
5. **Avast/AVG**: shared engine, one submission covers both.
6. **Sophos**: PUA detections take up to 15 business days.

### Step 6: download flagged binaries

Download all artifacts that appear in any submission file to `$TMPDIR` using `gh release download` with `--pattern` flags. These are needed for manual upload to vendor portals.

### Step 7: report

Print a summary of what was generated:

- Which `fp-submission-*.md` files were created (and which vendors were skipped because they had no detections)
- Where the binaries were downloaded
- Submission priority order and expected turnaround times
- Note any vendor portals known to have intermittent issues (Microsoft, Avast, BitDefender)
