#!/usr/bin/env python3
"""Session title hook for Claude Code.

Background — why this workaround exists (Claude Code v2.1.x, verified 2026-07):

- Claude Code itself writes ``{"type":"custom-title","customTitle":"MM-DD@HH:MM
  <cwd>",...}`` lines into the session JSONL at init and re-writes them
  repeatedly during a session (observed 6x in a 1-turn session, 99x in a
  36-turn one). The ``/resume`` picker shows the *last* such line, so a title
  merely appended by a hook is clobbered by Claude Code's next default write.
  This ``MM-DD@HH:MM <cwd>`` default is distinct from the documented
  ``dirname-XX`` agent-view label.
- Only a ``SessionStart`` hook can set a *sticky* title, by printing
  ``{"hookSpecificOutput":{"hookEventName":"SessionStart","sessionTitle":...}}``
  on stdout (``sessionTitle`` nested inside ``hookSpecificOutput``). ``Stop`` and
  ``UserPromptSubmit`` cannot: the hooks docs list ``sessionTitle`` only for
  SessionStart, and UserPromptSubmit attempts are silently ignored by the
  auto-titler. Once set via SessionStart, Claude Code treats the value as the
  session *name* (a ``--resume`` handle) and stops writing its cwd default
  entirely (verified live: 1 custom-title line instead of dozens).
- There is no setting to disable Claude Code's auto-titler (the first-prompt
  Haiku summary) or the cwd default. Appending ``custom-title`` lines to the
  JSONL is an unsupported, version-fragile pattern (the sidebar/index reads
  from a separate store).
- SessionStart fires *before* the first prompt, so a fresh session has no
  content to summarize; only ``resume``/``compact`` sources do. Its stdin
  carries ``session_id``, ``transcript_path``, ``source``, and ``session_title``
  (Claude Code's current default, e.g. ``MM-DD@HH:MM /full/cwd/path``).

Design: the ``Stop`` worker writes the Haiku summary to a sidecar at
``~/.claude/session-titles/<session_id>`` (the reliable, sticky path) *and*
appends a live ``custom-title`` line to the JSONL (so one-off, never-resumed
sessions still get titled during their single run). The ``SessionStart`` hook
re-applies the sidecar as a sticky name on the next start/resume, which stops
the clobbering for resumed and long-running sessions.

Subcommands:

- ``hook``: invoked by the ``Stop`` hook in settings.json. Reads the JSON
  payload on stdin, decides whether the current turn is on the refresh
  schedule, and (if so) detaches a ``generate`` worker.
- ``generate <session_id> <transcript_path> <prefix>``: backgrounded worker.
  Calls Claude Haiku to summarize the transcript, writes the sidecar, appends a
  ``custom-title`` line to the JSONL, and writes OSC 0 to ``/dev/tty``.
- ``sessionstart``: invoked by the ``SessionStart`` hook. Reads the sidecar and
  emits ``hookSpecificOutput.sessionTitle`` (skipping if the user set their own
  non-prefixed name). Fast: no Haiku call, so it adds no startup latency.
- ``set <session_id> <transcript_path> <title>``: manual setter used by the
  ``session-title`` skill. Same sidecar + JSONL persistence, no Haiku call.

Refresh schedule: turns 1, 3, 6, 10, 15, 20, ... (i.e. {1, 3, 6} then every
5 turns starting at 10). 33% of past sessions never reach turn 2, so turn 1
is mandatory; the rest tracks the long tail without spamming Haiku.

Upstream: the supported "set the session title from a hook" feature (which
would replace this workaround) is tracked in
https://github.com/anthropics/claude-code/issues/44786 (open).
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


def append_title(jsonl: Path, session_id: str, title: str) -> None:
    record = {"type": "custom-title", "customTitle": title, "sessionId": session_id}
    with jsonl.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


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
    if os.environ.get(GUARD_ENV) == "1":
        return 0
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
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
    _turns, _first, last_title, prompts = parse_transcript(jsonl)
    if not prompts:
        return 0
    summary = call_haiku("\n\n---\n\n".join(prompts))
    if not summary:
        return 0
    final = compose(prefix, summary)
    if not final:
        return 0
    write_sidecar(session_id, final)
    if final == last_title:
        return 0
    append_title(jsonl, session_id, final)
    write_osc(final)
    return 0


def cmd_set(session_id: str, transcript: str, title: str) -> int:
    jsonl = Path(transcript)
    if not jsonl.exists():
        print(f"transcript not found: {transcript}", file=sys.stderr)
        return 1
    _turns, first_title, last_title, _prompts = parse_transcript(jsonl)
    cleaned = sanitize(title)
    if not cleaned:
        print("empty or invalid title", file=sys.stderr)
        return 1
    prefix = extract_prefix(first_title)
    if prefix and not TIMESTAMP_RE.match(cleaned):
        cleaned = compose(prefix, cleaned)
    write_sidecar(session_id, cleaned)
    if cleaned == last_title:
        print(cleaned)
        return 0
    append_title(jsonl, session_id, cleaned)
    write_osc(cleaned)
    print(cleaned)
    return 0


def cmd_sessionstart() -> int:
    if os.environ.get(GUARD_ENV) == "1":
        return 0
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    session_id = payload.get("session_id")
    if not session_id:
        return 0
    title = read_sidecar(session_id)
    if not title:
        return 0
    # Respect a deliberate user-set name: one that is non-empty and does not
    # carry our MM-DD@HH:MM prefix (which both our titles and Claude Code's
    # "<prefix> <cwd>" default do). Anything else is the user's own rename, so
    # leave it alone.
    current = payload.get("session_title")
    if isinstance(current, str) and current and not TIMESTAMP_RE.match(current):
        return 0
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "sessionTitle": title,
                }
            }
        )
    )
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: session-title.py {hook|generate|set} ...", file=sys.stderr)
        return 2
    cmd = argv[1]
    if cmd == "hook":
        return cmd_hook()
    if cmd == "sessionstart":
        return cmd_sessionstart()
    if cmd == "generate" and len(argv) == 5:
        return cmd_generate(argv[2], argv[3], argv[4])
    if cmd == "set" and len(argv) == 5:
        return cmd_set(argv[2], argv[3], argv[4])
    print(f"bad invocation: {' '.join(argv[1:])}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
