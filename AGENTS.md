# Development guide

This file holds only the rules specific to this repository. The generic conventions load from `dotfiles/.agents/global-instruction.md`, which every session on this machine reads.

## Shell startup and packages

- **`.zprofile` caches its `PATH` list for 7 days.** New shells read `~/.path-env-cache`, not `PATH_LIST`, so a new entry reaches them only at the next refresh. To apply one now, append the resolved path to the cache, or delete the cache and let a new shell rebuild it slowly. Edit the list in the repository's `.zprofile`, then seed the cache, never the other way. The list lives in `.zprofile` so that login shells that never read `.zshrc` (SwiftBar plugins, pnpm) get it too.
- **`packages.toml` never picks up newly installed packages on its own.** `install.sh` runs `mpm snapshot --update-version`, which refreshes only the entries already listed. After installing a tool worth keeping, add its line by hand, alphabetically, with a bare version.

## pi extensions

- **`pi --help` cannot validate an extension edit** (pi `1.3.0`): it exits 0 on a file that does not parse. Probe the compile with `node --experimental-strip-types -e "import('{absolute path}.ts')"`, safe only when the extension's side effects all sit inside its default-exported factory. A value import from a pi package resolves inside pi's loader alone: load a copy beside `node_modules/@earendil-works/{package}`, a symlink to the same path under the pi install. To exercise a widget, call the default export with a fake `pi.on` and render the component a fake `ctx.ui.setWidget` receives. That checks syntax and load, not types: read the option and context shapes off the `.d.ts` files under the pi install. Exercise a handler that fires on one exit path only, like `session_shutdown` with reason `quit`, once, and read its log. Exercise a tool handler with no model and no network: a probe extension that registers `fauxProvider()` from `@earendil-works/pi-ai` replays scripted tool calls, with `PI_CODING_AGENT_DIR` on a scratch directory, `PI_OFFLINE=1` and `--mode json` to read each `tool_execution_end`. A built-in extension is named `builtin:{name}`, and `--no-extensions` disables the built-ins too: a probe that needs one adds `--extension builtin:{name}`.
- **Exercising a TUI exit-path handler needs a real session under a pty.** `{ sleep {seconds}; printf '\004'; } | script -q {log} pi --model {fast-model} '{one-word prompt}'` leaves the exit output in the log. A `/quit` fed while a turn runs queues as a user message and never quits: wait for the turn to settle, then send Ctrl+D.

## pi models

- **Nativ's Configure for Pi drops two hand-added `compat` keys from `dotfiles/.pi/agent/models.json`: `supportsFinishReason` and `thinkingFormat`.** After a Configure, read `git diff -- dotfiles/.pi/agent/models.json`, keep the new model list and restore each key the diff shows as removed.

## pi upgrades

- **The first interactive start of a new pi release rewrites `lastChangelogVersion` in `dotfiles/.pi/agent/settings.json`, so the previous version is the one at `HEAD`.** Read the newer `CHANGELOG.md` sections in `/opt/homebrew/opt/pi-coding-agent/libexec/lib/node_modules/@earendil-works/pi-coding-agent/`, validate the pi config files against the `schemas/` there, and re-check each claim that `git grep -n -E 'pi .?[0-9]+\.[0-9]+\.[0-9]+'` finds stamped with an older version. Keep each stamp on one line, or that grep misses it.

## pi auth

- **A running pi session overwrites hand edits to `auth.json`.** It persists its refreshed credential when the token expires and replaces the whole entry, so a credential swap applied mid-session reverts. Quit pi sessions first, or re-apply and confirm with `pi auth check --provider {id}` plus one live probe.

## Instruction files

- **The global file is `dotfiles/.agents/global-instruction.md`, reached by two symlinks: `~/.claude/CLAUDE.md` and `~/.pi/agent/AGENTS.md`.** `./install.sh links` creates and checks both, and refuses to replace a regular file. Claude Code `2.1.284` reads a project's `AGENTS.md` only when no `CLAUDE.md` stands on the walk from the root down to the working directory. It files what it finds as project instructions, never as user scope, so the user-scope link keeps the name `CLAUDE.md`. A repository file named `CLAUDE.md` turns the fallback off for that project.
- **Do not name the global file `AGENTS.md`.** The fallback reads an `AGENTS.md` under `dotfiles/.agents/` as a nested project file, so a Read there can attach the whole global file a second time. This comes from the built-in plugin's source in Claude Code `2.1.284`, not from a live probe.
- **Check which instruction file a project loads without the API:** run `claude --print --debug-file {log}` from the project directory and read the `[agents-md]` lines, like `no CLAUDE.md found; AGENTS.md loaded: {path}`. The lines appear before the first API call, so a blocked network does not hide them. They cover the project fallback only: the `SessionStart` and `InstructionsLoaded` hooks stay silent in `--print` before the API call (Claude Code `2.1.284`), so nothing offline shows whether the user-scope file loads.
- **`Instructions no longer present: /Users/kde/.claude/CLAUDE.md` at a session start means the symlink is gone, and every global rule with it.** Recreate it outside the sandbox with `ln -sfn ../code/dotfiles/dotfiles/.agents/global-instruction.md /Users/kde/.claude/CLAUDE.md`.
- **Cowork in Claude Desktop reads neither link, so the account-wide Settings > Your Claude > Instructions field points its sessions to the copy in the `dotfiles` plugin.** Cowork never loads `~/.claude/CLAUDE.md` (Claude Desktop `5.11492.5`), and the plugin carries this whole repository. The field reaches every chat on the account, so its pointer addresses sessions with file tools only, and its first paragraph is the only rule that plain chats get. No documented API writes the field: when you change the text below, or rename a file it names, paste the text into the field again. The field holds the text below.

```text
I code in advanced Python. Always produce Markdown files. For rich non-text only document, produce editable OpenOffice documents, and PDF to freeze content.

In a session with file tools, read and follow my global rules before your first action: dotfiles/.agents/global-instruction.md and dotfiles/.claude/tropes.md, under the root of the "dotfiles" plugin (search for the file names if needed). They take precedence over harness defaults, like commit trailers. If you cannot read them, say so in your first reply.
```

## Skills

- **Each `repomatic init` and `sync-repomatic` run rewrites every skill under `dotfiles/.agents/skills/` that `.claude-plugin/plugin.json` does not list.** Port a lesson written into one of them to `../repomatic/.claude/skills/{name}/SKILL.md` in the same pass.
- **A skill owned here has two rosters.** Add its path to `.claude-plugin/plugin.json`, then its name and the new counts to the plugin paragraphs of `readme.md`.
- **The Bash sandbox denies writes under `dotfiles/.agents/skills/` and `dotfiles/.claude/`, and to the global file, `dotfiles/.agents/global-instruction.md`.** Change those files with the Write and Edit tools; Bash can still read them, so lint and test a skill in place. The Write tool keeps a regex escape like `\b` or `\n` as typed (Claude Code `2.1.284`). The auto-mode classifier refuses a copy into the skills folder with the sandbox off, so hand the user a `!` line that sets an executable bit there.
- **`dotfiles/.agents/skills/synced/` and `.trash/` come from the Claude app sync.** `synced/{id}/manifest.json` names each skill's `source` (`anthropic`, `anthropic-example`), and a skill in `.trash/` came from there. The claude.ai Skills page does not list them: hide one with `skillOverrides` in `.claude/settings.json` and a `!` glob in the pi `skills` setting. `pi config` is a TUI only: count the skills pi loads with a node script that calls `DefaultResourceLoader` (from pi's `dist/index.js`) `reload()` then `getSkills()`.
- **A private skill lives in `~/code/private-skills`, a local repository with no remote.** Link each skill folder into `dotfiles/.agents/skills/{name}` and ignore the link in `.git/info/exclude`, which keeps its name out of this public repository. Claude Code (`2.1.284`) finds no skill nested one level deeper, so one `private/` link for the whole folder does not work.

## Public repository

- **Keep home-network data out of this public repository.** Subnets, VLANs, the gateway, static routes, device addresses, SSIDs and DNS configuration IDs live in the local-only knowledge base in `~/ProtonDrive/Network & machines/`. A private SSH host goes in `~/.ssh/config.d/`, which `dotfiles/.ssh/config` includes after a `Match all` line.

## Assets

- **The dated desktop screenshots in `assets/` are kept on purpose.** An audit for unreferenced files must leave them, and may still report the configuration of a tool that is no longer installed.
