---
name: session-title
description: Refresh the current Claude Code session's title (shown in /resume picker and terminal tab). Trigger on "rename session", "refresh session title", "update tab title", "set session title to ...".
compatibility: 'Designed for Claude Code. Recommended model: Sonnet.'
---

When the user asks to refresh or rename the current session's title:

1. **Compose the summary myself, from conversation context.**
   I already have the full conversation in context: pick a 3-7 word title (max 50 chars) that captures the current topic. Do not call any external generator: that would spawn a Haiku inference (slow), and a fresh summary I'd pass to it tends to drift away from what I already know.

   Use sentence case. Capitalize the first word and proper nouns only.

2. **Determine the session_id and transcript path.**

   - `session_id` is in the env var `CLAUDE_SESSION_ID` if set, otherwise: take the basename (without `.jsonl`) of the most recently modified `*.jsonl` file directly under `~/.claude/projects/<sanitized-cwd>/` where `<sanitized-cwd>` is the current working directory with `/` replaced by `-`.
   - The transcript path is `~/.claude/projects/<sanitized-cwd>/<session_id>.jsonl`.

3. **Apply via the helper.**
   The helper auto-prepends the timestamp prefix (`MM-DD@HH:MM`) extracted from the first `custom-title` line in the transcript, so I should pass only the summary part:

   ```bash
   /Users/kde/code/dotfiles/dotfiles/.claude/hooks/session-title.py set "$session_id" "$transcript" "Refactor API client error handling"
   ```

   The helper sanitizes (strips control chars, rejects path-shaped values, caps at 80 chars), writes the sidecar at `~/.claude/session-titles/<session_id>`, and writes OSC 0 to update the terminal tab immediately. The `UserPromptSubmit` hook applies the sidecar title at the next prompt through Claude Code's supported rename path (the same write `/rename` uses), which persists it in the transcript and re-applies it on every later start/resume: the new title lands one prompt after this step.

4. **Confirm in one short sentence**, e.g.:
   `Session title updated to: 04-29@10:14 Refactor API client error handling`
