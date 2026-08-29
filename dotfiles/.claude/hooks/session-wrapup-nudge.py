#!/usr/bin/env python3
"""Session wrap-up nudge for Claude Code: a ``SessionEnd`` hook.

Claude Code counterpart of the pi extension ``dotfiles/.pi/agent/extensions/bye.ts``. Only the
nudge half ports: Claude Code has no interceptable quit and no way for a hook or skill to run one
more agentic turn at exit, so the wrap-up itself stays a manual ``/session-wrapup`` last turn, and
this hook reminds about it when a session with real prompts quits without one.

Verified against Claude Code 2.1.236 (2026-08-29), by strings-grepping the Caskroom binary, live
transcripts, and this hook's own log across real exits:

- The ``SessionEnd`` payload carries ``session_id``, ``transcript_path``, ``reason``, ``cwd`` and
  ``hook_event_name``; the reason enum is ``clear``, ``logout``, ``prompt_input_exit``, ``other``,
  ``resume``. Only ``prompt_input_exit`` is an interactive exit (Ctrl+C, Ctrl+D, ``/exit``), so
  only it nudges: headless ``claude -p`` runs, ``/clear`` and resume-switches stay silent.
- ``SessionEnd`` can fire more than once for one goodbye (observed twice, 16s apart, the second
  without ``prompt_id``), hence the per-session dedupe window below.
- Hook stdout at ``SessionEnd`` is not rendered as terminal output, and hook processes run with
  **no controlling terminal**: ``open("/dev/tty")`` fails with ``ENXIO`` from the hook itself. The
  terminal device is recovered by walking ancestor PIDs with ``ps -o tty=`` until a process with a
  tty appears (the CLI holds it), then opening ``/dev/ttysNNN`` by explicit path, which needs only
  ownership, never a controlling-terminal relationship.
- A typed prompt in the transcript JSONL is an entry of type ``user`` whose ``message.content``
  is a string and which has no ``toolUseResult`` key; tool results carry a content array instead.
  Synthetic user messages (command wrappers, system reminders) start with ``<`` and do not count.
- A wrap-up ran when an assistant entry holds a ``Skill`` tool_use with ``input.skill`` equal to
  ``session-wrapup``, or a user entry contains the ``/session-wrapup`` command tag.

The tty write is detached and delayed rather than direct. Under ``tui: fullscreen`` the session
runs on the alternate screen, and an immediate write can land there and vanish when Claude Code
restores the main screen on its way out. A child process detached with ``start_new_session``
sleeps past the restore and writes the line beside the fresh shell prompt through the inherited
descriptor (it must inherit: after ``setsid`` the child could not reopen any controlling path).

The tty device is the only working channel. The hook-output schema documents a ``systemMessage``
display field for all hooks, but a ``SessionEnd`` hook printing one renders nothing (tested live,
2.1.236, 2026-08-29): the session is past displaying anything through the harness by then.

Every invocation appends one line to ``~/.claude/debug/session-wrapup-nudge.log`` with the
payload keys and the decision, and the delayed writer appends its own outcome, because a hook
that only acts at exit is otherwise invisible: the log is the only way to tell "did not fire"
from "fired and chose silence" from "wrote to a dead terminal". The file is wiped when it grows
past 64 KiB.

The hook always exits 0: a reminder must never block or delay an exit.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

SKILL_NAME = "session-wrapup"

DIM = "\x1b[2m"
RESET = "\x1b[0m"

LOG_PATH = Path.home() / ".claude" / "debug" / "session-wrapup-nudge.log"
LOG_MAX_BYTES = 65536

LAST_NUDGE_PATH = Path.home() / ".claude" / "debug" / "session-wrapup-nudge.last"
DEDUPE_SECONDS = 60

TTY_DELAY_SECONDS = 0.5
"""How long the detached writer sleeps before writing.

Long enough for Claude Code to finish hooks, leave the alternate screen and exit; short enough
that the line lands right beside the returning shell prompt.
"""

DETACHED_WRITER = f"""
import sys, time
time.sleep({TTY_DELAY_SECONDS})
try:
    sys.stdout.write(sys.argv[1])
    sys.stdout.flush()
    note = "delayed write ok"
except OSError as error:
    note = f"delayed write failed: {{error}}"
try:
    with open(sys.argv[2], "a", encoding="UTF-8") as log:
        log.write(time.strftime("%Y-%m-%d %H:%M:%S ") + note + "\\n")
except OSError:
    pass
"""


def log(note: str) -> None:
    """Append one timestamped line to the debug log, never failing."""
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        if LOG_PATH.exists() and LOG_PATH.stat().st_size > LOG_MAX_BYTES:
            LOG_PATH.unlink()
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_PATH, "a", encoding="UTF-8") as handle:
            handle.write(f"{stamp} {note}\n")
    except OSError:
        pass


def scan_transcript(path: str) -> tuple[int, bool]:
    """Count typed user prompts and detect a wrap-up invocation, in one pass."""
    typed_prompts = 0
    wrapped_up = False
    with open(path, encoding="UTF-8") as transcript:
        for line in transcript:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            kind = entry.get("type")
            message = entry.get("message") or {}
            if kind == "user" and "toolUseResult" not in entry:
                content = message.get("content")
                if not isinstance(content, str):
                    continue
                text = content.strip()
                if text and not text.startswith("<"):
                    typed_prompts += 1
                if f"<command-name>/{SKILL_NAME}" in content:
                    wrapped_up = True
            elif kind == "assistant":
                for block in message.get("content") or []:
                    if (
                        isinstance(block, dict)
                        and block.get("type") == "tool_use"
                        and block.get("name") == "Skill"
                        and (block.get("input") or {}).get("skill") == SKILL_NAME
                    ):
                        wrapped_up = True
    return typed_prompts, wrapped_up


def decide(payload: dict) -> tuple[bool, str]:
    """Return (nudge or not, reason for the log)."""
    reason = payload.get("reason")
    if reason != "prompt_input_exit":
        return False, f"reason={reason!r}"
    transcript_path = payload.get("transcript_path")
    if not transcript_path:
        return False, "no transcript_path"
    try:
        typed_prompts, wrapped_up = scan_transcript(transcript_path)
    except OSError as error:
        return False, f"transcript unreadable: {error}"
    if wrapped_up:
        return False, f"wrap-up ran, typed_prompts={typed_prompts}"
    if typed_prompts == 0:
        return False, "no typed prompts"
    return True, f"typed_prompts={typed_prompts}"


def recently_nudged(session_id: str) -> bool:
    """Whether this session already got a nudge inside the dedupe window."""
    now = time.time()
    try:
        previous_id, previous_stamp = LAST_NUDGE_PATH.read_text(encoding="UTF-8").split()
        if previous_id == session_id and now - float(previous_stamp) < DEDUPE_SECONDS:
            return True
    except (OSError, ValueError):
        pass
    try:
        LAST_NUDGE_PATH.write_text(f"{session_id} {now}", encoding="UTF-8")
    except OSError:
        pass
    return False


def find_terminal() -> str | None:
    """Walk ancestor processes for the terminal device the CLI holds."""
    pid = os.getppid()
    for _ in range(6):
        try:
            # Absolute path: the user's PATH shims ps through a grc colorizer whose ANSI
            # output would break this parsing, and hooks inherit that PATH.
            fields = subprocess.run(
                ["/bin/ps", "-o", "tty=,ppid=", "-p", str(pid)],
                capture_output=True,
                text=True,
                timeout=5,
            ).stdout.split()
        except (OSError, subprocess.SubprocessError):
            return None
        if len(fields) < 2:
            return None
        tty, parent = fields[0], fields[1]
        if tty not in ("??", "?", "-"):
            return f"/dev/{tty}"
        if parent in ("0", "1"):
            return None
        pid = parent
    return None


def emit(message: str, tty_path: str | None) -> str:
    """Deliver the nudge; return what happened for the log."""
    if tty_path is None:
        tty_path = find_terminal()
        if tty_path is None:
            return "no terminal found on ancestor chain"
        delayed = True
    else:
        # Test path (--tty): write synchronously so a pipe-test can assert on the file.
        delayed = False
    try:
        tty = open(tty_path, "w", encoding="UTF-8")
    except OSError as error:
        return f"open {tty_path} failed: {error}"
    with tty:
        if not delayed:
            try:
                tty.write(message)
            except OSError as error:
                return f"write to {tty_path} failed: {error}"
            return f"wrote to {tty_path}"
        try:
            subprocess.Popen(
                [sys.executable, "-c", DETACHED_WRITER, message, str(LOG_PATH)],
                stdin=subprocess.DEVNULL,
                stdout=tty,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as error:
            return f"detached writer failed: {error}"
    return f"detached writer spawned on {tty_path}"


def main() -> None:
    tty_path = None
    if len(sys.argv) == 3 and sys.argv[1] == "--tty":
        tty_path = sys.argv[2]

    try:
        payload = json.load(sys.stdin)
    except ValueError:
        log("unparseable stdin payload")
        return
    nudge, why = decide(payload)
    if not nudge:
        log(f"skip ({why}) keys={sorted(payload)}")
        return

    session_id = str(payload.get("session_id") or "")
    if tty_path is None and recently_nudged(session_id):
        log(f"skip (nudged this session within {DEDUPE_SECONDS}s)")
        return
    resume = f"claude --resume {session_id}" if session_id else "claude --continue"
    # A CLI-argument prompt dispatches skill slash commands (verified live in print mode,
    # 2.1.236, 2026-08-29), so this one-liner reopens the session with the wrap-up already
    # running. Deliberately not `-p`: a wrap-up opens threads. It can surface work left to
    # do, draft contributions back to the downstream or upstream repository, or propose
    # changes to the wrap-up skill itself, whose improvements compound across every later
    # session. Each of those needs the user present to pick up, steer, and approve, so the
    # wrap-up never runs headless.
    plain = f'Wrap-up skipped: `{resume} "/{SKILL_NAME}"` closes it properly.'
    outcome = emit(f"{DIM}{plain}{RESET}\n", tty_path)
    log(f"nudge ({why}): {outcome} keys={sorted(payload)}")


if __name__ == "__main__":
    main()
