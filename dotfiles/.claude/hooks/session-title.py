#!/usr/bin/env python3
"""Session title hook for Claude Code.

How titling works (verified against Claude Code 2.1.224, 2026-08):

- A ``UserPromptSubmit`` hook can set a *persistent* title by printing
  ``{"hookSpecificOutput":{"hookEventName":"UserPromptSubmit",
  "sessionTitle":...}}`` on stdout. Claude Code applies it through the same
  write path as ``/rename`` (source ``"hook"``): it appends the
  ``{"type":"custom-title",...}`` record to the session JSONL itself,
  updates the session-name metadata, and pushes the title to the
  remote-control bridge and ccr sessions. The ``/resume`` picker shows the
  last such record.
- A ``SessionStart`` hook can also carry ``sessionTitle``, but that path is
  cache-only: it sets the in-memory title for the run and writes nothing to
  disk, so on its own it never reaches the ``/resume`` picker. It is still
  used below to display the sidecar title immediately on start/resume,
  before the first prompt.
- The AI auto-titler (first-prompt Haiku summary) writes a separate
  ``{"type":"ai-title",...}`` record into a separate slot, and the display
  always prefers the custom title, so the auto-titler can never clobber a
  title set here.
- The ``MM-DD@HH:MM <cwd>`` default title is seeded by this repo's own zsh
  wrapper in ``.zshrc`` (``claude () { command claude --name "$(date
  +%m-%d@%H:%M) ..." "$@" }``), not by Claude Code. ``TIMESTAMP_RE``
  recognizes that prefix, which both the wrapper default and our titles
  carry, and the hook payload's ``session_title`` tells us the current one.
- ``Stop`` hooks have no ``sessionTitle`` in their output schema: the
  titling hand-off must happen on ``UserPromptSubmit`` or ``SessionStart``.

Older releases (verified 2026-07) inverted this: only SessionStart stuck,
UserPromptSubmit output was silently dropped, and Claude Code re-wrote the
wrapper's cwd default over a merely appended title dozens of times per
session. The sidecar, the SessionStart re-apply and the hand-appended JSONL
lines were built for that world. The supported UserPromptSubmit path has
since replaced the JSONL appends; the sidecar survives as the hand-off queue
between the backgrounded worker and the next hook, because UserPromptSubmit
is synchronous on every prompt and cannot host the Haiku call itself. Cost:
a generated title lands one prompt late.

Design: the ``Stop`` hook detaches a backgrounded ``generate`` worker on a
refresh schedule. The worker summarizes the transcript with Haiku and writes
the result to the sidecar at ``~/.claude/session-titles/<session_id>``. The
next ``UserPromptSubmit`` persists it through the supported path, and every
``SessionStart`` re-applies it in-memory for instant display.

Subcommands:

- ``hook``: invoked by the ``Stop`` hook in settings.json. Reads the JSON
  payload on stdin, decides whether the current turn is on the refresh
  schedule, and (if so) detaches a ``generate`` worker.
- ``generate <session_id> <transcript_path> <prefix>``: backgrounded worker.
  Calls Claude Haiku to summarize the transcript, writes the sidecar, and
  writes OSC 0 to ``/dev/tty`` for instant tab feedback.
- ``sessionstart``: invoked by the ``SessionStart`` hook. Reads the sidecar
  and emits ``hookSpecificOutput.sessionTitle`` (cache-only; skips if the
  user set their own non-prefixed name). Fast: no Haiku call, so it adds no
  startup latency.
- ``userpromptsubmit``: invoked by the ``UserPromptSubmit`` hook. Reads the
  sidecar and emits ``hookSpecificOutput.sessionTitle``, which Claude Code
  then persists like a ``/rename`` (skips if the user set their own
  non-prefixed name).
- ``set <session_id> <transcript_path> <title>``: manual setter used by the
  ``session-title`` skill. Writes the sidecar + OSC 0; the title lands at
  the next prompt via ``userpromptsubmit``. No Haiku call.

Refresh schedule: turns 1, 3, 6, 10, 15, 20, ... (i.e. {1, 3, 6} then every
5 turns starting at 10). 33% of past sessions never reach turn 2, so turn 1
is mandatory; the rest tracks the long tail without spamming Haiku.

Upstream: anthropics/claude-code#44786 asked for exactly this and was closed
2026-08-17 as available today, with anthropics/claude-code#34243 and
anthropics/claude-code#33527 closed alongside it.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

GUARD_ENV = "CC_SESSION_TITLE_GUARD"
SIDECAR_DIR = Path.home() / ".claude" / "session-titles"
SCHEDULE_FIXED = {1, 3, 6}
SCHEDULE_OFFSET = 10
SCHEDULE_STEP = 5
TIMESTAMP_RE = re.compile(r"^(\d\d-\d\d@\d\d:\d\d)\s+(.+)$")
MAX_TITLE_LEN = 80
HAIKU_TIMEOUT = 60
TRANSCRIPT_CAP = 4000

SYSTEM_PROMPT = """You generate a concise summary title for a coding-assistant session.

Hard rules:
- 3 to 7 words. Maximum 50 characters.
- Sentence case: capitalize the first word and proper nouns only.
- Capture the main topic or goal. Be specific, not vague.
- Return JSON with a single "title" field. No prose, no clarification questions.

Examples:
Input: "fix the login button on mobile"
Output: {"title": "Fix login button on mobile"}

Input: "refactor the API client error handling and add retries"
Output: {"title": "Refactor API client error handling"}

Input: "investigate the flaky test in tests/integration/test_auth.py"
Output: {"title": "Debug flaky integration auth test"}
"""


def in_schedule(turn: int) -> bool:
    if turn in SCHEDULE_FIXED:
        return True
    if turn >= SCHEDULE_OFFSET and (turn - SCHEDULE_OFFSET) % SCHEDULE_STEP == 0:
        return True
    return False


def sanitize(title: str) -> str:
    title = title.replace("\x1b", "").replace("\x07", "")
    title = title.replace("\r", "").replace("\n", " ").strip()
    if not title:
        return ""
    if (
        title.startswith("/")
        or "/var/folders/" in title
        or "/tmp/" in title
        or "/private/" in title
    ):
        return ""
    if len(title) > MAX_TITLE_LEN:
        title = title[:MAX_TITLE_LEN]
    return title


def parse_transcript(jsonl: Path) -> tuple[int, str | None, str | None, list[str]]:
    """Return (user_turns, first_custom_title, last_custom_title, prompts)."""
    user_turns = 0
    first_title: str | None = None
    last_title: str | None = None
    prompts: list[str] = []
    with jsonl.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = obj.get("type")
            if kind == "custom-title":
                ct = obj.get("customTitle")
                if isinstance(ct, str) and ct:
                    if first_title is None:
                        first_title = ct
                    last_title = ct
            elif kind == "user":
                msg = obj.get("message")
                if not isinstance(msg, dict):
                    continue
                content = msg.get("content")
                text = ""
                if isinstance(content, str):
                    text = content
                elif isinstance(content, list):
                    parts: list[str] = []
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "text":
                            v = c.get("text")
                            if isinstance(v, str):
                                parts.append(v)
                    text = "\n".join(parts)
                if text and not text.lstrip().startswith("<"):
                    user_turns += 1
                    prompts.append(text)
    return user_turns, first_title, last_title, prompts


def extract_prefix(title: str | None) -> str:
    if not title:
        return ""
    m = TIMESTAMP_RE.match(title)
    return m.group(1) if m else ""


def sidecar_path_for(session_id: str) -> Path:
    return SIDECAR_DIR / session_id


def write_sidecar(session_id: str, title: str) -> None:
    try:
        SIDECAR_DIR.mkdir(parents=True, exist_ok=True)
        sidecar_path_for(session_id).write_text(title + "\n", encoding="utf-8")
    except OSError:
        pass


def read_sidecar(session_id: str) -> str | None:
    try:
        text = sidecar_path_for(session_id).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return text or None


def write_osc(title: str) -> None:
    try:
        with open("/dev/tty", "w") as tty:
            tty.write(f"\x1b]0;{title}\x07")
            tty.flush()
    except OSError:
        pass


def call_haiku(transcript: str) -> str | None:
    if len(transcript) > TRANSCRIPT_CAP:
        transcript = transcript[:TRANSCRIPT_CAP]
    env = dict(os.environ)
    env[GUARD_ENV] = "1"
    schema = (
        '{"type":"object","properties":{"title":{"type":"string"}},'
        '"required":["title"],"additionalProperties":false}'
    )
    try:
        proc = subprocess.run(
            [
                "claude",
                "--print",
                "--model",
                "claude-haiku-4-5",
                "--output-format",
                "json",
                "--json-schema",
                schema,
                "--system-prompt",
                SYSTEM_PROMPT,
                "--tools",
                "",
                "--disable-slash-commands",
                "--no-session-persistence",
                "--",
                transcript,
            ],
            capture_output=True,
            text=True,
            timeout=HAIKU_TIMEOUT,
            env=env,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if proc.returncode != 0:
        return None
    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    structured = result.get("structured_output")
    if not isinstance(structured, dict):
        return None
    title = structured.get("title")
    return title if isinstance(title, str) else None


def transcript_path_for(session_id: str, cwd: str) -> Path:
    sanitized = cwd.replace("/", "-")
    return Path.home() / ".claude" / "projects" / sanitized / f"{session_id}.jsonl"


def cmd_hook() -> int:
    payload = read_hook_payload()
    if payload is None:
        return 0
    if payload.get("hook_event_name") != "Stop":
        return 0
    if payload.get("stop_hook_active"):
        return 0
    session_id = payload.get("session_id")
    if not session_id:
        return 0
    transcript = payload.get("transcript_path")
    jsonl = (
        Path(transcript)
        if transcript
        else transcript_path_for(session_id, payload.get("cwd") or os.getcwd())
    )
    if not jsonl.exists():
        return 0
    user_turns, first_title, _last_title, _prompts = parse_transcript(jsonl)
    if user_turns == 0 or not in_schedule(user_turns):
        return 0
    prefix = extract_prefix(first_title)
    script = os.path.realpath(__file__)
    subprocess.Popen(
        [sys.executable, script, "generate", session_id, str(jsonl), prefix],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env={**os.environ, GUARD_ENV: "1"},
    )
    return 0


def compose(prefix: str, summary: str) -> str:
    summary = sanitize(summary)
    if not summary:
        return ""
    return f"{prefix} {summary}"[:MAX_TITLE_LEN] if prefix else summary


def cmd_generate(session_id: str, transcript: str, prefix: str) -> int:
    jsonl = Path(transcript)
    if not jsonl.exists():
        return 0
    _turns, _first, _last_title, prompts = parse_transcript(jsonl)
    if not prompts:
        return 0
    summary = call_haiku("\n\n---\n\n".join(prompts))
    if not summary:
        return 0
    final = compose(prefix, summary)
    if not final:
        return 0
    # Persistence happens at the next UserPromptSubmit through Claude Code's
    # own rename path; the sidecar is the queue until then. OSC 0 gives
    # instant tab feedback in the meantime.
    write_sidecar(session_id, final)
    write_osc(final)
    return 0


def cmd_set(session_id: str, transcript: str, title: str) -> int:
    jsonl = Path(transcript)
    if not jsonl.exists():
        print(f"transcript not found: {transcript}", file=sys.stderr)
        return 1
    _turns, first_title, _last_title, _prompts = parse_transcript(jsonl)
    cleaned = sanitize(title)
    if not cleaned:
        print("empty or invalid title", file=sys.stderr)
        return 1
    prefix = extract_prefix(first_title)
    if prefix and not TIMESTAMP_RE.match(cleaned):
        cleaned = compose(prefix, cleaned)
    # The sidecar is persisted at the next UserPromptSubmit through Claude
    # Code's own rename path; OSC 0 gives instant tab feedback meanwhile.
    write_sidecar(session_id, cleaned)
    write_osc(cleaned)
    print(cleaned)
    return 0


def read_hook_payload() -> dict | None:
    """The hook JSON payload on stdin, or ``None`` to bail out silently."""
    if os.environ.get(GUARD_ENV) == "1":
        return None
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def is_user_rename(current: object) -> bool:
    """Whether ``session_title`` holds a deliberate rename by the user.

    Both our titles and the zsh wrapper's ``<prefix> <cwd>`` default carry
    the ``MM-DD@HH:MM`` prefix, so anything else is the user's own rename
    and must be left alone.
    """
    return (
        isinstance(current, str)
        and bool(current)
        and not TIMESTAMP_RE.match(current)
    )


def emit_session_title(event: str, title: str) -> None:
    print(
        json.dumps({
            "hookSpecificOutput": {
                "hookEventName": event,
                "sessionTitle": title,
            }
        })
    )


def sidecar_title_for(payload: dict) -> str | None:
    """The sidecar title to emit, if any, for this hook payload."""
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        return None
    title = read_sidecar(session_id)
    if not title:
        return None
    if is_user_rename(payload.get("session_title")):
        return None
    return title


def cmd_sessionstart() -> int:
    payload = read_hook_payload()
    if payload is None:
        return 0
    title = sidecar_title_for(payload)
    if title:
        emit_session_title("SessionStart", title)
    return 0


def cmd_userpromptsubmit() -> int:
    payload = read_hook_payload()
    if payload is None:
        return 0
    title = sidecar_title_for(payload)
    if title:
        emit_session_title("UserPromptSubmit", title)
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(
            "usage: session-title.py "
            "{hook|generate|sessionstart|userpromptsubmit|set} ...",
            file=sys.stderr,
        )
        return 2
    cmd = argv[1]
    if cmd == "hook":
        return cmd_hook()
    if cmd == "sessionstart":
        return cmd_sessionstart()
    if cmd == "userpromptsubmit":
        return cmd_userpromptsubmit()
    if cmd == "generate" and len(argv) == 5:
        return cmd_generate(argv[2], argv[3], argv[4])
    if cmd == "set" and len(argv) == 5:
        return cmd_set(argv[2], argv[3], argv[4])
    print(f"bad invocation: {' '.join(argv[1:])}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
