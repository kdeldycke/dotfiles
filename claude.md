# Development guide

This file holds only the rules specific to this repository. The generic conventions load from `dotfiles/.agents/AGENTS.md`, which every session on this machine reads.

## Shell startup and packages

- **`.zprofile` caches its `PATH` list for 7 days.** New shells read `~/.path-env-cache`, not `PATH_LIST`, so a new entry reaches them only at the next refresh. To apply one now, append the resolved path to the cache, or delete the cache and let a new shell rebuild it slowly. Edit the list in the repository's `.zprofile`, then seed the cache, never the other way. The list lives in `.zprofile` so that login shells that never read `.zshrc` (SwiftBar plugins, pnpm) get it too.
- **`packages.toml` never picks up newly installed packages on its own.** `install.sh` runs `mpm snapshot --update-version`, which refreshes only the entries already listed. After installing a tool worth keeping, add its line by hand, alphabetically, with a bare version.

## pi extensions

- **`pi --help` cannot validate an extension edit** (pi `0.99.1`, 2026-10-01): it exits 0 on a file that does not parse. Probe the compile with `node --experimental-strip-types -e "import('{absolute path}.ts')"`, safe only when the extension's side effects all sit inside its default-exported factory, and only when it imports nothing but types from a pi package: those resolve inside pi's loader alone. That checks syntax and load, not types: read the option and context shapes off the `.d.ts` files under the pi install. Exercise a handler that fires on one exit path only, like `session_shutdown` with reason `quit`, once, and read its log. Exercise a tool handler with no model and no network: a probe extension that registers `fauxProvider()` from `@earendil-works/pi-ai` replays scripted tool calls, with `PI_CODING_AGENT_DIR` on a scratch directory, `PI_OFFLINE=1` and `--mode json` to read each `tool_execution_end`. A built-in extension is named `builtin:{name}`, and `--no-extensions` disables the built-ins too: a probe that needs one adds `--extension builtin:{name}`.

## pi models

- **Native's Configure for Pi drops three hand-added `compat` keys from `dotfiles/.pi/agent/models.json`: `supportsFinishReason`, `maxTokensField` and `thinkingFormat`.** After a Configure, read `git diff -- dotfiles/.pi/agent/models.json`, keep the new model list and restore each key the diff shows as removed.

## Skills

- **Each `repomatic init` and `sync-repomatic` run rewrites every skill under `dotfiles/.agents/skills/` that `.claude-plugin/plugin.json` does not list.** Port a lesson written into one of them to `../repomatic/.claude/skills/{name}/SKILL.md` in the same pass.

## Assets

- **The dated desktop screenshots in `assets/` are kept on purpose.** An audit for unreferenced files must leave them, and may still report the configuration of a tool that is no longer installed.
