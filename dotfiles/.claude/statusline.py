#!/usr/bin/env python3
"""Render the Claude Code status line with starship.

`starship statusline claude-code` reads the session JSON on stdin, but only feeds it to the
`claude_model`, `claude_context` and `claude_cost` modules. Two gaps follow, and this wrapper
closes both.

The `directory` module never sees the JSON: starship resolves the path from `--path` and
`--logical-path`, and falls back to the working directory of the status line process. That
fallback shows the directory Claude Code was launched from, and it does not follow a `cd` made
during the session. So the wrapper reads `workspace.current_dir` and passes it on both flags.
`--path` drives git and read-only detection; `--logical-path` drives what `directory` prints.

The rest of the JSON has no starship module at all. Rate limits, reasoning effort, the open
pull request, the session name and the worktree are all absent from the schema starship parses.
The wrapper exports each one as an environment variable, which an `env_var` module in
`~/.config/starship.toml` renders with the same styling as any native module. An absent field
leaves its variable unset, and `env_var` prints nothing for an unset variable, so every one of
these segments hides itself.

Native rate limit modules are proposed upstream in
[starship/starship#7442](https://github.com/starship/starship/pull/7442) and
[starship/starship#7684](https://github.com/starship/starship/pull/7684). Drop the
`CC_RATE_*` variables here, and their `env_var` blocks in `starship.toml`, once one of them
lands.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

STARSHIP_COMMAND = ["starship", "statusline", "claude-code"]

SESSION_NAME_MAX_LENGTH = 24
"""Longest session name to print before eliding the tail.

A name comes from `--name`, from `/rename`, or from the title `session-title.py` generates, so
nothing bounds its length. The status line shares one row with the directory and the git state.
"""

PR_REVIEW_GLYPHS = {
    "approved": "✓",
    "changes_requested": "✗",
    "pending": "·",
    "draft": "○",
}
"""Review state of the open pull request, as a single trailing glyph.

An `env_var` module carries one style, so it cannot colour by state the way `claude_context`
colours by threshold. A glyph inside the value says the same thing in one column.
"""

RATE_LIMIT_TIERS = ((80.0, "CRIT"), (50.0, "WARN"), (0.0, "OK"))
"""Severity tiers for rate limit usage, highest first.

Each tier has its own `CC_RATE_{tier}` variable and its own `env_var` block, and the wrapper
sets exactly one. That reproduces the threshold colouring `claude_context` gets natively.
"""

RATE_LIMIT_RESET_TIER = 50.0
"""Usage percentage above which the reset countdown is worth its width on the row.

Below it the window is not the constraint, and the countdown is noise.
"""

WIDTH_MARGIN = 5
"""Columns held back from `COLUMNS` before handing the width to `$fill`.

Claude Code reports the full terminal width but draws the status line in a narrower box, and
gives no way to ask how much narrower. A row padded to exactly `COLUMNS` overruns it and is
truncated with an ellipsis, which eats the cost at the far right.

The figure is calibrated against a real terminal, not derived: at `COLUMNS` the cost lost four
characters, and at `COLUMNS - 2` it still lost two. starship's own padding is not the culprit,
since measuring a rendered row confirms it lands exactly on the width it was given, emoji
counted as two columns. Raise this if a segment is still clipped; lower it if blank space opens
between the last block and the right edge.
"""

WIDTH_BUDGET = ((120, ("CC_PR", "CC_WORKTREE")), (100, ("CC_FLAGS",)))
"""Variables to drop below each terminal width, widest threshold first.

The blocks starship draws from its own modules cannot be dropped from here, so the row has a
floor of roughly 113 columns with a git branch, a python version and a dirty worktree in it.
Past that floor Claude Code wraps the row rather than truncating it, which costs a whole
terminal line to show the same information worse. Shedding the segments that keep longest is
the cheaper trade: an open pull request and a worktree name change on the order of days, while
the context gauge and the cost move every turn.
"""


def session_directory(session: dict) -> str | None:
    """Return the directory the session currently works in."""
    workspace = session.get("workspace") or {}
    return workspace.get("current_dir") or session.get("cwd")


def terminal_width() -> int | None:
    """Return the terminal width Claude Code reports, for the `fill` module to pad against.

    Claude Code captures the script's output rather than attaching it to the terminal, so the
    width arrives in `COLUMNS` and cannot be read from the file descriptor. Without it starship
    assumes 80 columns and `fill` pads to the wrong place.
    """
    columns = os.environ.get("COLUMNS", "")
    if not columns.isdigit():
        return None
    usable = int(columns) - WIDTH_MARGIN
    return usable if usable > 0 else None


def format_countdown(epoch: float) -> str | None:
    """Render seconds until `epoch` as a compact `1h05m` or `43m`."""
    remaining = int(epoch - time.time())
    if remaining <= 0:
        return None
    hours, minutes = divmod(remaining // 60, 60)
    return f"{hours}h{minutes:02d}m" if hours else f"{minutes}m"


def format_rate_limits(session: dict) -> tuple[str, str] | None:
    """Return the `CC_RATE_*` variable name and value for the session's rate limit usage.

    Only the busier of the two windows is reported. Both would cost about ten columns on a row
    that already competes for them, and the busier one is the one that stops the work first.
    The variable name carries its severity, which is what colours the segment.
    """
    limits = session.get("rate_limits") or {}
    windows = []
    for key, label in (("five_hour", "5h"), ("seven_day", "7d")):
        window = limits.get(key) or {}
        used = window.get("used_percentage")
        if isinstance(used, (int, float)):
            windows.append((used, label, window.get("resets_at")))
    if not windows:
        return None

    # Keyed on the percentage alone. Comparing the tuples would fall through to the label and
    # then to `resets_at`, where a present timestamp against a missing one raises TypeError.
    # `max` returns the first of equal values, so a tie reports the five-hour window: at the
    # same percentage it fills from the same usage over a shorter span, and so runs out first.
    used, label, resets_at = max(windows, key=lambda window: window[0])
    value = f"{label} {used:.0f}%"
    if used >= RATE_LIMIT_RESET_TIER and isinstance(resets_at, (int, float)):
        countdown = format_countdown(resets_at)
        if countdown:
            value += f"·{countdown}"
    tier = next(name for threshold, name in RATE_LIMIT_TIERS if used >= threshold)
    return f"CC_RATE_{tier}", value


def format_pull_request(session: dict) -> str | None:
    """Return the open pull request as `#1234 ✓`, or `!1234 ✓` for a GitLab merge request."""
    pull_request = session.get("pr") or {}
    number = pull_request.get("number")
    if number is None:
        return None
    prefix = "!" if pull_request.get("kind") == "mr" else "#"
    glyph = PR_REVIEW_GLYPHS.get(pull_request.get("review_state"))
    return f"{prefix}{number} {glyph}" if glyph else f"{prefix}{number}"


def format_flags(session: dict) -> str | None:
    """Return the reasoning effort, flagged with a bolt when fast mode is on.

    starship parses `effort` on `main` and exposes it to the `claude_model` format as
    `$effort`, but 1.26.0 does not: the field is absent from its `ClaudeCodeData`, so the
    variable resolves empty. Reporting it here works on both.

    ```{todo}
    Drop the effort half of this once the installed starship carries `$effort`, and read it
    from the `claude_model` format instead.
    ```

    `thinking.enabled` is deliberately not reported. It is on in every ordinary session, so it
    would cost a column permanently to say nothing.
    """
    parts = []
    effort = (session.get("effort") or {}).get("level")
    if effort:
        parts.append(str(effort))
    if session.get("fast_mode"):
        parts.append("⚡")
    return " ".join(parts) or None


def format_session_name(session: dict) -> str | None:
    """Return the session name, elided to `SESSION_NAME_MAX_LENGTH`."""
    name = session.get("session_name")
    if not name:
        return None
    name = str(name)
    if len(name) <= SESSION_NAME_MAX_LENGTH:
        return name
    return name[: SESSION_NAME_MAX_LENGTH - 1] + "…"


def format_worktree(session: dict) -> str | None:
    """Return the worktree name the session sits in.

    `worktree.name` is set only for a Claude Code worktree session; `workspace.git_worktree`
    covers any linked worktree, including one made by hand with `git worktree add`.
    """
    worktree = session.get("worktree") or {}
    workspace = session.get("workspace") or {}
    return worktree.get("name") or workspace.get("git_worktree")


def build_environment(session: dict, width: int | None) -> dict[str, str]:
    """Map the session JSON onto the `CC_*` variables the `env_var` modules read."""
    environment = {
        "CC_SESSION": format_session_name(session),
        "CC_WORKTREE": format_worktree(session),
        "CC_PR": format_pull_request(session),
        "CC_FLAGS": format_flags(session),
    }
    rate_limits = format_rate_limits(session)
    if rate_limits:
        variable, value = rate_limits
        environment[variable] = value

    if width is not None:
        for threshold, dropped in WIDTH_BUDGET:
            if width < threshold:
                environment.update(dict.fromkeys(dropped, None))
    return {name: value for name, value in environment.items() if value}


def main() -> int:
    payload = sys.stdin.buffer.read()
    command = STARSHIP_COMMAND.copy()
    environment = os.environ.copy()
    width = terminal_width()

    try:
        session = json.loads(payload)
    except json.JSONDecodeError:
        session = None
    if isinstance(session, dict):
        directory = session_directory(session)
        if directory:
            command += ["--path", directory, "--logical-path", directory]
        environment.update(build_environment(session, width))

    if width:
        command += ["--terminal-width", str(width)]

    # `add_newline` defaults to true and applies to a profile as much as to the prompt, so
    # starship opens the render with a blank line. In a shell that is the gap before each
    # prompt; in the status line it is a wasted terminal row. Only stdout is captured, so
    # starship's own warnings still reach `claude --debug`.
    render = subprocess.run(
        command, input=payload, env=environment, stdout=subprocess.PIPE, check=False
    )
    sys.stdout.buffer.write(render.stdout.lstrip(b"\r\n"))
    return render.returncode


if __name__ == "__main__":
    sys.exit(main())
