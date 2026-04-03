---
name: fill-web-form
description: Fill a web form using data extracted from local documents (PDFs, images, spreadsheets). Uses Claude Desktop (Cowork) with Chrome integration to read source documents and navigate/fill browser forms. Use when the user wants to automate filling an online form from document data.
argument-hint: "[URL of the form] [path to source documents]"
---

# Fill Web Form from Document Data

Read local documents (PDFs, images, spreadsheets), extract structured data, then navigate to a web form in Chrome and fill it in. Claude Desktop reads the documents; Claude in Chrome interacts with the form.

## Prerequisites

This skill requires **Claude Desktop (Cowork mode)** with Chrome integration. It cannot run from Claude Code in a terminal. If invoked from Claude Code, print the setup instructions below and stop.

## Setup (one-time)

### 1. Install Claude Desktop

Download from https://claude.ai/download if not already installed.

### 2. Install Claude in Chrome

Install the "Claude" extension in Chrome or Chromium:
- Chrome Web Store: search "Claude" by Anthropic
- Extension ID: `fcoeoabgfenejglbffodgkkbkcdhcgfn`

### 3. Enable browser actions in Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "preferences": {
    "allowAllBrowserActions": true
  }
}
```

### 4. Log into the target website

Open Chrome/Chromium, navigate to the target form URL, and log in manually. Claude cannot handle login/2FA flows: the session must already be authenticated before starting.

## Launching a form-filling session

### From Claude Desktop UI

1. Open Claude Desktop
2. Start a new Cowork session (the agent mode, not a regular chat)
3. Upload the source documents (PDFs, images) to the conversation
4. Enable Chrome integration: click the Chrome icon in the session toolbar, or ensure the session has `chromePermissionMode: "skip_all_permission_checks"` in its config
5. Paste the form URL and describe what needs to be filled

### From the command line (launch helper)

There is no single CLI command that bootstraps everything. The closest workflow:

```bash
# 1. Ensure Chromium is running with the target site logged in
open -a Chromium "https://example.com/form"

# 2. Open Claude Desktop (it will connect to the running Chrome via the extension)
open -a Claude

# 3. In the Claude Desktop Cowork session:
#    - Upload source documents
#    - Enable Chrome integration
#    - Type: "Read the uploaded documents and fill the form at https://example.com/form"
```

To open Claude Desktop to a specific conversation via URL scheme:
```bash
open "claude://conversation/SESSION_UUID"
```

## Architecture

```
Source documents (uploaded to Claude Desktop)
  -> Claude Desktop extracts structured data
  -> Claude in Chrome navigates to form URL
  -> Form fields filled using read_page + form_input / computer actions
  -> User reviews and submits
```

Claude Desktop and Claude in Chrome share the same conversation context within a Cowork session. When Chrome integration is enabled, Claude gains access to browser tools: `read_page`, `form_input`, `computer` (click, type, scroll), `navigate`, and `screenshot`.

## Workflow

### Phase 1: Extract data from documents

1. Read all uploaded documents
2. Build a structured data dictionary mapping document fields to form fields
3. Present the extracted data to the user for review before filling anything

### Phase 2: Navigate to the form

1. Use `navigate` or instruct the user to open the form URL in Chrome
2. Use `read_page` to understand the form structure
3. Map extracted data fields to form input elements

### Phase 3: Fill the form

For each form field:

1. `read_page(filter="interactive")` to get element refs
2. `form_input(ref="ref_XXXX", value="...")` for text inputs, selects, and textareas
3. `computer(action="left_click", ref="ref_XXXX")` for radio buttons, checkboxes, and custom widgets
4. `computer(action="key", text="Tab")` after each field to trigger any reactive validation
5. `screenshot` to verify the field was filled correctly

### Phase 4: Review and hand off

1. Screenshot the completed form
2. Present a summary of all filled values
3. **Stop before submitting.** Always leave the final Submit/Confirm action to the user.

## Browser interaction patterns

### Reading form structure

```python
read_page(filter="interactive")  # Returns ref_XXXX for each input/button
read_page(filter="all")          # Returns full page content with refs
```

### Filling text inputs

```python
form_input(ref="ref_1251", value="John Doe")
```

### Clicking buttons, radios, checkboxes

```python
computer(action="left_click", ref="ref_XXXX")
```

### Typing into fields that don't accept form_input

```python
computer(action="left_click", ref="ref_XXXX")  # Focus the field
computer(action="key", text="some text")         # Type into it
```

### Handling dropdowns/selects

```python
form_input(ref="ref_XXXX", value="Option Text")  # For standard <select>
# For custom dropdowns (common in SPA frameworks):
computer(action="left_click", ref="ref_XXXX")     # Open dropdown
wait(duration=1)
read_page(filter="interactive")                     # Find the option
computer(action="left_click", ref="ref_YYYY")      # Click the option
```

### Waiting for page updates

```python
wait(duration=2)    # After navigation or AJAX calls
screenshot          # Verify the page state
```

### Multi-step / wizard forms

After completing each step:
1. Find the "Next" / "Continue" button via `read_page`
2. Click it: `computer(action="left_click", ref="ref_XXXX")`
3. `wait(duration=3)` for the next step to load
4. `screenshot` to confirm advancement
5. Repeat

## Handling common SPA frameworks

### SAP UI5 (e.g., government portals)

- `form_input` works for text fields but not radio buttons
- Radio buttons require `computer(action="left_click", ref=...)`
- Fields may reject decimals: use integers
- Tab after each field to trigger reactive recalculation
- For bulk-filling empty fields with a default value, use JavaScript injection:

```javascript
let filled = 0;
document.querySelectorAll('input[type="text"]').forEach((el) => {
  if (el.value.trim() === '') {
    const setter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype, 'value'
    ).set;
    setter.call(el, '0');
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    filled++;
  }
});
`Filled ${filled} fields`;
```

### React / Angular / Vue SPAs

- Standard `form_input` usually works
- For custom components (date pickers, autocompletes), click to open, then select from the popup
- Wait for debounced validation after filling fields

### Static HTML forms

- `form_input` works reliably for all standard inputs
- File upload fields may need `computer(action="left_click")` to open the file picker

## Common problems

| Problem | Solution |
|---|---|
| Form field not accepting input | Try `computer(left_click)` to focus first, then `form_input` |
| Radio/checkbox not responding to form_input | Use `computer(left_click, ref=...)` instead |
| Dropdown options not visible | Click the dropdown trigger, `wait(1)`, then `read_page` to find options |
| Page navigation returns 404 | SPA context may need to be established first: navigate to the app root, then click through to the form |
| Validation error after filling | Check for red error indicators, use `read_page` to find error messages |
| Field shows wrong value after fill | Tab out of the field to trigger formatting, then `screenshot` to verify |
| Multi-page form loses progress | Use "Save as Draft" if available after each step |

## Important rules

1. **Never submit the form.** Always stop before the final Submit/Confirm button and hand off to the user.
2. **Present extracted data before filling.** Let the user verify the document-to-form mapping.
3. **Screenshot after each step.** Visual confirmation prevents silent errors.
4. **Log in manually first.** Claude cannot handle login/2FA. The browser session must be authenticated before starting.
5. **Integer rounding.** If the source document has decimals but the form expects integers, round to nearest and flag the difference to the user.
6. **Sensitive data.** If source documents contain data that should not be entered (passwords, SSNs in wrong fields), flag it and ask before proceeding.
