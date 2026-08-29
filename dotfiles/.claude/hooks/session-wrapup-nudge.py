#!/usr/bin/env python3
"""Session wrap-up nudge for Claude Code: a ``SessionEnd`` hook.

Claude Code counterpart of the pi extension ``dotfiles/.pi/agent/extensions/bye.ts``. Only the
nudge half ports: Claude Code has no interceptable quit and no way for a hook or skill to run one
more agentic turn at exit, so the wrap-up itself stays a manual ``/session-wrapup`` last turn, and
this hook reminds about it when a session with real prompts quits without one.

Verified against Claude Code 2.1.236 (2026-08-29), by strings-grepping the Caskroom binary and
inspecting a live transcript:

- The ``SessionEnd`` payload carries ``session_id``, ``transcript_path`` and ``reason``; the
  reason enum is ``clear``, ``logout``, ``prompt_input_exit``, ``other``, ``resume``. Only
  ``prompt_input_exit`` is an interactive exit (Ctrl+C, Ctrl+D, ``/exit``), so only it nudges:
  headless ``claude -p`` runs, ``/clear`` and resume-switches stay silent.
- Hook stdout at ``SessionEnd`` is not rendered to the terminal, so the nudge writes to
  ``/dev/tty`` directly. Without a tty (cron, CI) the write fails and the hook stays silent.
- A typed prompt in the transcript JSONL is an entry of type ``user`` whose ``message.content``
  is a string and which has no ``toolUseResult`` key; tool results carry a content array instead.
  Synthetic user messages (command wrappers, system reminders) start with ``<`` and do not count.
- A wrap-up ran when an assistant entry holds a ``Skill`` tool_use with ``input.skill`` equal to
  ``session-wrapup``, or a user entry contains the ``/session-wrapup`` command tag.

The hook always exits 0: a reminder must never block or delay an exit.
"""

import json
import sys

SKILL_NAME = "session-wrapup"

DIM = "\x1b[2m"
RESET = "\x1b[0m"


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


def main() -> None:
    # The default target only exists on an interactive exit; --tty makes the logic testable
    # by pipe (`--tty /dev/stdout`).
    tty_path = "/dev/tty"
    if len(sys.argv) == 3 and sys.argv[1] == "--tty":
        tty_path = sys.argv[2]

    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return
    if payload.get("reason") != "prompt_input_exit":
        return
    transcript_path = payload.get("transcript_path")
    if not transcript_path:
        return
    try:
        typed_prompts, wrapped_up = scan_transcript(transcript_path)
    except OSError:
        return
    if wrapped_up or typed_prompts == 0:
        return

    session_id = payload.get("session_id")
    resume = f"claude --resume {session_id}" if session_id else "claude --continue"
    try:
        with open(tty_path, "w", encoding="UTF-8") as tty:
            tty.write(f"{DIM}Wrap-up skipped: `{resume}` then `/{SKILL_NAME}` closes it properly.{RESET}\n")
    except OSError:
        return


if __name__ == "__main__":
    main()
