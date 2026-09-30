# Session transcript review

Scan past session transcripts to find tool calls that were denied by the sandbox or by the permission allow/deny rules, then propose allowlist refinements. Denials are the primary signal, but also mine the corpus for recurring failures and retry loops that point at misconfiguration (see Beyond denials below).

Keep re-runs incremental: record the last-scanned `mtime` and size per session file in one state file per harness (`~/.claude/.self-tune-transcript-state.json`, `~/.pi/agent/.self-tune-transcript-state.json`), and parse only files that changed since the previous run. The corpus grows with every session, and a full re-scan each time costs the reading time the tuning is meant to save.

## Where transcripts live

- Claude Code: `~/.claude/projects/<encoded-project-path>/<session-uuid>.jsonl`, one JSONL file per session, sibling to a directory of the same UUID containing tool results. The encoded project path replaces `/` with `-`, so `/Users/kde/code/dotfiles` becomes `-Users-kde-code-dotfiles`.
- pi: `~/.pi/agent/sessions/*.jsonl`, one JSONL file per session, organized by working directory.

## Denial signals to grep for (Claude Code)

pi prompts interactively and keeps no allow/deny rules, so denial mining applies to Claude Code sessions only. Search transcripts for these markers in `message.content[*].content` and `toolUseResult` fields:

- `Permission to use <Tool> with command <X> has been denied.`: a `deny` rule matched the call.
- `Permission for this action was denied by the Claude Code auto mode classifier. Reason: <reason>`: the auto-mode classifier refused the call.
- `The user doesn't want to proceed with this tool use`: the user rejected a permission prompt.
- `requires approval`, `requires permission`: tool call paused on the allowlist gate.
- `Operation not permitted`, `sandbox`, `dangerouslyDisableSandbox`: sandbox filesystem or network denial.
- `EACCES`, `EPERM`: surfaced when a sandboxed command hits a denied path.

Use `Grep` with these patterns across `~/.claude/projects/**/*.jsonl`. Default to the last 30 days; allow the user to widen the window.

## Extracting actionable patterns

For each denial, extract:

- The tool name (Bash, Edit, Read, WebFetch, ...).
- The exact argument that was denied (the bash command, the file path, the URL host).
- The matching permission rule shape: `Bash(rm:*)`, `Read(/Users/kde/.ssh/**)`, `WebFetch(domain:example.com)`.
- The session date and project, so I can tell recurring denials apart from one-offs.

Group denials by rule shape and count occurrences across sessions and projects.

Count each call once. A resumed or forked session replays earlier entries into its own transcript, so key every call on its `tool_use` id across all files.

A denied command can sit anywhere in a compound command: search the whole command for the denied head, not its first word alone.

## Classifying denials

Each recurring denial falls into one of three buckets, and the proposed change differs by bucket:

1. **Should be allowed**: a benign command the user kept approving manually (high re-approval rate, no destructive intent). Propose adding a narrow `allow` rule, scoped to the smallest pattern that covers the observed calls (prefer `Bash(tool:*)` over `Bash(*)`).
2. **Should stay blocked, but noisy**: the denial is correct but the prompt fires often. Propose a `deny` rule so future calls fail fast without an interactive prompt, or propose a hook that rewrites the call.
3. **Sandbox-only**: the permission rule already allows the call, but the sandbox filesystem or network policy denied it. Propose adding the path to `permissions.additionalDirectories` or the host to the network allowlist, and never propose `dangerouslyDisableSandbox` as a fix.

Skip one-off denials (single occurrence, no project recurrence): they are noise.

## Beyond denials: failure and loop signals

Two more corpus signals produce config findings, though both are noisier than denials. They apply to transcripts of both harnesses:

- **Retry loops**: the same tool call, with the same or near-identical arguments, repeated several times in one session. This is often a permission prompt the user kept answering, or a hook that keeps failing. Extract the repeated call, check it against the allow list and the hook definitions, and classify it as a permission gap, a broken hook, or agent noise.
- **Recurring command errors**: the same command shape failing with the same non-permission error across sessions. This usually points at a hook or environment misconfiguration, not an allowlist gap.

Classify a finding as config-related before proposing anything. Most tool errors in a transcript are ordinary coding failures, not configuration.

## Output

Add a "Session denials" section to the report with:

- A table of recurring denials and config-related failures: rule shape, count, distinct projects, last seen date, classification.
- For each promoted allow/deny rule, the exact diff to apply to `~/.claude/settings.json` (or the project `settings.json` when the pattern is project-specific).
- For sandbox denials, the proposed `additionalDirectories` or network host entry, with the originating command for context.
