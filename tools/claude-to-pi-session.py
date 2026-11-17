#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Convert Claude Code transcripts into pi session files.

Claude Code stores one session as JSONL under
`~/.claude/projects/--<cwd>--/<session-uuid>.jsonl`. pi stores one session as
JSONL under `~/.pi/agent/sessions/--<cwd>--/<timestamp>_<session-id>.jsonl`,
with a version 3 header and a tree of entries linked by `id`/`parentId`.

The two formats disagree on six points this script resolves:

1. Claude Code writes one API response as several rows sharing a `message.id`,
   one row per content block, and it interleaves tool results between them. pi
   stores one `assistant` message per response, so rows of one `message.id` are
   merged and the results they produced are held back and emitted after it.
2. Claude Code parents parallel tool results to different ancestors, which
   yields several leaves. pi chains parallel tool results linearly, so this
   script emits a single chain in conversation order.
3. Claude Code records Anthropic usage field names. pi records `Usage` with
   `input`/`output`/`cacheRead`/`cacheWrite` plus a `cost` breakdown. Rates
   come from the pi-ai model catalogue when it is reachable, else cost is zero.
   A reachable catalogue can still list no cost for a model: that model costs
   zero too, and the report names it.
4. These models' reasoning arrives encrypted: the thinking block carries an
   empty text field and only a signature blob, and Claude Code persists that
   verbatim (older transcripts keep readable thinking text, so the emptiness
   is the API's, not the writer's). The block maps to pi's redacted-thinking
   form: the turn shows a `[Reasoning redacted]` marker, and the signature
   rides along for a same-model replay. That signature was minted for Claude
   Code's context, so replaying it from pi's converted context may 400; a
   block holding neither text nor signature is dropped.
5. Claude Code keeps internal rows (`attachment`, `system`, `cost-state`,
   `bridge-session`, title and mode markers). They carry no conversation
   content, so they are dropped and counted in the report. A transcript that
   holds nothing else, like the one-row stub a Remote Control bridge leaves,
   has no session to write.
6. Claude Code can write a row a second time, later in the file, with the same
   uuid and message and only new metadata (`promptId`, `slug`, `parentUuid`).
   The first copy is kept and the repeat is counted in the report. pi walks
   parent links from the leaf to the root, so two entries sharing an id close
   a loop that pi cannot load; every entry id is unique for that reason.

With --all the script converts every transcript in `~/.claude/projects/`,
except the sessions still in use: one that a running Claude Code process holds,
as `~/.claude/sessions/` registers them, and one whose transcript changed
within the cooldown period (--cooldown-days), as it may still resume in Claude
Code. --entrypoint, repeatable, limits --all
to the transcripts of the clients it names. Claude Code stamps each row with
the client that wrote it (`cli` for the terminal, `sdk-cli` for a
non-interactive run like `claude --print`, `claude-desktop` for the Code tab of
Claude Desktop), and a transcript matches when any of its rows does, so a
session resumed from another client matches both.

With --trash-source the script moves the migrated session's Claude Code
artifacts to the Trash through the `trash` CLI, and only once the pi file holds
the conversion: the transcript, its session directory (tool results, and the
subagent transcripts this script does not convert), the session title, the
session-env marker, the session tasks directory, and the wrapup-nudge marker
when it names this session. Shared files that only reference the session (the
prompt history, the global config and its backups) are left in place: other
sessions write them too, and the references age out on their own. Trashing
always goes through `trash`, never `rm`, so a mistaken import stays
recoverable, and the script trashes nothing at all when the CLI is missing.

Entry ids derive from the Claude row uuid, so re-running the script on one
transcript writes byte-identical output. A destination that already starts
with that output counts as migrated and is not written again, so the entries
pi appends when the session continues there survive a re-run. A destination
holding anything else is left alone unless --force is passed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Claude Code tool name -> pi tool name. Only a tool whose arguments pi reads
# with the same keys belongs here: pi renders a mapped name with its own
# renderer, and a mismatched argument shape renders worse than a generic one.
TOOL_NAME_MAP = {"Bash": "bash"}

# Anthropic `stop_reason` -> pi `StopReason`.
STOP_REASON_MAP = {
    "end_turn": "stop",
    "max_tokens": "length",
    "pause_turn": "stop",
    "refusal": "error",
    "stop_sequence": "stop",
    "tool_use": "toolUse",
}

# Text of a thinking block whose reasoning arrived encrypted. Mirrors what
# pi-ai stores for `redacted_thinking` events, so an imported session renders
# like a native one.
REDACTED_THINKING_PLACEHOLDER = "[Reasoning redacted]"

# Shapes the pi package takes under an install prefix.
PI_PACKAGE_NAME = "@earendil-works/pi-coding-agent"
PI_PACKAGE_LAYOUTS = (
    ("lib", "node_modules"),
    ("libexec", "lib", "node_modules"),
    ("node_modules",),
)

# A transcript modified within this many days belongs to a session that may
# still resume in Claude Code, so --all leaves it in place.
DEFAULT_COOLDOWN_DAYS = 21


def entry_id(seed: str) -> str:
    """Return a deterministic 8-char hex entry id for `seed`."""
    return hashlib.md5(seed.encode("UTF-8")).hexdigest()[:8]


def parse_timestamp(value: str) -> int:
    """Return Unix milliseconds for an ISO 8601 timestamp."""
    return int(datetime.fromisoformat(value).timestamp() * 1000)


def read_transcript(path: Path) -> list[dict]:
    """Return every JSON row of a Claude Code transcript."""
    rows = []
    with path.open(encoding="UTF-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def pi_install_root() -> Path | None:
    """Return the pi package root, or None when pi is not on PATH."""
    resolved = shutil.which("pi")
    if not resolved:
        return None
    target = Path(os.path.realpath(resolved))
    for parent in target.parents:
        for layout in PI_PACKAGE_LAYOUTS:
            candidate = parent.joinpath(*layout) / PI_PACKAGE_NAME
            if candidate.is_dir():
                return candidate
    return None


def model_rates(provider: str, model_id: str) -> tuple[dict | None, bool]:
    """Return `(rates, reachable)` from the bundled pi-ai catalogue.

    `reachable` is False when the catalogue cannot be read at all. Rates is
    None with `reachable` True when the catalogue is fine but lists no cost
    for the model.
    """
    root = pi_install_root()
    if root is None:
        return None, False
    catalog = (
        root
        / "node_modules"
        / "@earendil-works"
        / "pi-ai"
        / "dist"
        / "providers"
        / "data"
        / f"{provider}.json"
    )
    if not catalog.is_file():
        return None, False
    try:
        payload = json.loads(catalog.read_text(encoding="UTF-8"))
    except (OSError, json.JSONDecodeError):
        return None, False
    for api_models in payload.values():
        model = api_models.get(model_id) if isinstance(api_models, dict) else None
        cost = model.get("cost") if isinstance(model, dict) else None
        if isinstance(cost, dict):
            return cost, True
    return None, True


def build_usage(raw: dict, rates: dict | None) -> dict:
    """Return a pi `Usage` object built from an Anthropic `usage` object."""
    cache_write = raw.get("cache_creation_input_tokens") or 0
    long_write = (raw.get("cache_creation") or {}).get("ephemeral_1h_input_tokens") or 0
    usage = {
        "input": raw.get("input_tokens") or 0,
        "output": raw.get("output_tokens") or 0,
        "cacheRead": raw.get("cache_read_input_tokens") or 0,
        "cacheWrite": cache_write,
        "totalTokens": 0,
    }
    if long_write:
        usage["cacheWrite1h"] = long_write
    thinking = (raw.get("output_tokens_details") or {}).get("thinking_tokens")
    if thinking is not None:
        usage["reasoning"] = thinking
    usage["totalTokens"] = (
        usage["input"] + usage["output"] + usage["cacheRead"] + usage["cacheWrite"]
    )
    rates = rates or {}
    input_rate = rates.get("input", 0)
    short_write = cache_write - long_write
    cost = {
        "input": rates.get("input", 0) / 1_000_000 * usage["input"],
        "output": rates.get("output", 0) / 1_000_000 * usage["output"],
        "cacheRead": rates.get("cacheRead", 0) / 1_000_000 * usage["cacheRead"],
        # Anthropic bills a 1h cache write at twice the base input rate.
        "cacheWrite": (
            rates.get("cacheWrite", 0) * short_write + input_rate * 2 * long_write
        )
        / 1_000_000,
    }
    cost["total"] = (
        cost["input"] + cost["output"] + cost["cacheRead"] + cost["cacheWrite"]
    )
    usage["cost"] = cost
    return usage


def image_block(block: dict) -> dict | None:
    """Return a pi `ImageContent` block for a Claude image block."""
    source = block.get("source") or {}
    if source.get("type") != "base64":
        return None
    return {
        "type": "image",
        "data": source.get("data", ""),
        "mimeType": source.get("media_type", "image/png"),
    }


def content_blocks(value) -> list[dict]:
    """Return pi text and image blocks for Claude message content."""
    if isinstance(value, str):
        return [{"type": "text", "text": value}] if value else []
    blocks: list[dict] = []
    for block in value or []:
        if not isinstance(block, dict):
            continue
        kind = block.get("type")
        if kind == "text":
            if block.get("text"):
                blocks.append({"type": "text", "text": block["text"]})
        elif kind == "image":
            image = image_block(block)
            if image:
                blocks.append(image)
        else:
            # A block pi has no type for (Claude Code's `tool_reference`, for
            # one) still carries what the model read, so keep it as text.
            blocks.append({
                "type": "text",
                "text": json.dumps(block, ensure_ascii=False),
            })
    return blocks


def session_title(rows: list[dict], session_id: str | None) -> str | None:
    """Return the display title Claude Code recorded for this session."""
    if session_id:
        title_file = Path.home() / ".claude" / "session-titles" / session_id
        if title_file.is_file():
            title = title_file.read_text(encoding="UTF-8").strip()
            if title:
                return title
    for row in reversed(rows):
        if row.get("type") == "custom-title" and row.get("customTitle"):
            return str(row["customTitle"]).strip()
    return None


def session_dir_for(cwd: str, agent_dir: Path) -> Path:
    """Return pi's session directory for a working directory."""
    stripped = re.sub(r"^[/\\]", "", cwd)
    safe = re.sub(r"[/\\:]", "-", stripped)
    return agent_dir / "sessions" / f"--{safe}--"


def claude_transcripts() -> list[Path]:
    """Return every session transcript in the Claude Code project store.

    A subagent transcript sits one level deeper, in its parent session's
    directory, and is not a session of its own.
    """
    return sorted((Path.home() / ".claude" / "projects").glob("*/*.jsonl"))


def transcript_entrypoints(rows: list[dict]) -> set[str]:
    """Return the clients that wrote a transcript, from its `entrypoint` stamps."""
    return {row["entrypoint"] for row in rows if isinstance(row.get("entrypoint"), str)}


def pid_exists(pid: int) -> bool:
    """Return whether a process with this pid exists."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # The process exists, but this script may not signal it: a coding
        # agent's sandbox denies signals, and so does another user's process.
        return True
    return True


def running_sessions() -> dict[str, int]:
    """Return the pid of the running Claude Code process holding each session.

    Claude Code registers each process in `~/.claude/sessions/<pid>.json`, with
    the id of its current session. A file whose process is gone is stale and
    skipped. A file whose pid now belongs to another process still counts: it
    holds back one session too many, never one too few.
    """
    sessions: dict[str, int] = {}
    for path in (Path.home() / ".claude" / "sessions").glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="UTF-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        pid, session_id = data.get("pid"), data.get("sessionId")
        if isinstance(pid, int) and isinstance(session_id, str) and pid_exists(pid):
            sessions[session_id] = pid
    return sessions


def claude_session_artifacts(transcript: Path, session_id: str) -> list[Path]:
    """Return every `~/.claude` path holding artifacts of this one session.

    Only paths whose name, or content in the case of the nudge marker, ties
    them to `session_id` qualify. Shared files that merely reference the
    session are deliberately excluded: other sessions write them too.
    """
    claude = Path.home() / ".claude"
    artifacts: list[Path] = []
    # The transcript and its session directory belong to this session only
    # when they sit in the standard project store a live Claude Code session
    # would have written them to. A transcript passed from elsewhere
    # is a copy the caller owns, so it is not the script's to delete.
    if transcript.parent.parent.resolve() == (claude / "projects").resolve():
        artifacts.extend([transcript, transcript.parent / session_id])
    # Claude Code names the tasks directory after the session's first uuid
    # group, not the full id.
    artifacts.extend([
        claude / "session-titles" / session_id,
        claude / "session-env" / session_id,
        claude / "tasks" / f"session-{session_id.split('-', maxsplit=1)[0]}",
    ])
    nudge = claude / "debug" / "wrapup-session-nudge.last"
    if nudge.is_file():
        content = nudge.read_text(encoding="UTF-8").split()
        # The marker is "<session-id> <timestamp>" for whichever session the
        # wrapup nudge last fired on, so it belongs here only by content.
        if content and content[0] == session_id:
            artifacts.append(nudge)
    return [path for path in artifacts if path.exists()]


def trash_source(artifacts: list[Path]) -> list[Path]:
    """Move artifacts to the Trash through the `trash` CLI and return them.

    The script never calls `rm`: a move it should not have made stays
    recoverable from the Trash, and a missing `trash` CLI means nothing is
    trashed at all rather than deleted unrecoverably.
    """
    trash = shutil.which("trash")
    if trash is None:
        raise FileNotFoundError(
            "the `trash` CLI is required for --trash-source; nothing was trashed"
        )
    # One call per session, as --all can trash thousands of paths.
    subprocess.run([trash, *(str(path) for path in artifacts)], check=True)
    return artifacts


class SessionWriter:
    """Accumulate pi session entries as one linear chain."""

    def __init__(self, header: dict) -> None:
        self.entries: list[dict] = [header]
        self.parent_id: str | None = None
        self.used_ids: set[str] = set()

    def _append(
        self, entry_type: str, field: str, stamp: str, seed: str, value: dict | str
    ) -> str:
        """Append one entry after the current leaf and return its id."""
        new_id = entry_id(seed)
        attempt = 1
        while new_id in self.used_ids:
            attempt += 1
            new_id = entry_id(f"{seed}#{attempt}")
        self.used_ids.add(new_id)
        self.entries.append({
            "type": entry_type,
            "id": new_id,
            "parentId": self.parent_id,
            "timestamp": stamp,
            field: value,
        })
        self.parent_id = new_id
        return new_id

    def append_message(self, stamp: str, seed: str, message: dict) -> str:
        """Append one `message` entry and return its id."""
        return self._append("message", "message", stamp, seed, message)

    def append_session_info(self, stamp: str, seed: str, name: str) -> str:
        """Append one `session_info` entry and return its id."""
        return self._append("session_info", "name", stamp, seed, name)


def convert(rows: list[dict]) -> tuple[list[dict], dict]:
    """Return pi session entries and a conversion report for `rows`."""
    report: dict = {
        "skipped": {},
        "dropped": 0,
        "duplicates": 0,
        "tools": {},
        "rates_missing": [],
        "catalog_unreachable": False,
    }

    session_id = next((r["sessionId"] for r in rows if r.get("sessionId")), None)
    cwds = [r["cwd"] for r in rows if isinstance(r.get("cwd"), str)]
    cwd = max(set(cwds), key=cwds.count) if cwds else str(Path.cwd())
    stamps = [r["timestamp"] for r in rows if isinstance(r.get("timestamp"), str)]
    first_stamp = min(stamps) if stamps else datetime.now(UTC).isoformat()

    for row in rows:
        kind = row.get("type")
        if kind not in ("user", "assistant"):
            report["skipped"][kind] = report["skipped"].get(kind, 0) + 1

    # Conversation rows only. Claude Code marks injected context with `isMeta`.
    convo = [
        row
        for row in rows
        if row.get("type") in ("user", "assistant")
        and row.get("message")
        and not row.get("isMeta")
    ]
    # A row written again under its uuid with the same message is a repeat.
    first_messages: dict[str, dict] = {}
    unique = []
    for row in convo:
        uuid = row.get("uuid")
        if uuid in first_messages and first_messages[uuid] == row["message"]:
            report["duplicates"] += 1
            continue
        if uuid and uuid not in first_messages:
            first_messages[uuid] = row["message"]
        unique.append(row)
    convo = unique

    # Tool name lookup, so a tool result can name the tool that produced it.
    tool_names: dict[str, str] = {}
    for row in convo:
        if row["type"] == "assistant":
            for block in row["message"].get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tool_names[block["id"]] = block.get("name", "unknown")

    writer = SessionWriter({
        "type": "session",
        "version": 3,
        "id": session_id,
        "timestamp": first_stamp,
        "cwd": cwd,
    })
    title = session_title(rows, session_id)
    if title:
        writer.append_session_info(first_stamp, f"{session_id}:title", title)
    report["title"] = title

    rates_cache: dict[str, dict | None] = {}
    group: dict | None = None

    def emit_result(row: dict, result: dict, position: int) -> None:
        """Write one tool result entry."""
        name = tool_names.get(result.get("tool_use_id") or "", "unknown")
        report["tools"][name] = report["tools"].get(name, 0) + 1
        writer.append_message(
            row["timestamp"],
            f"{row.get('uuid', 'row')}:result{position}",
            {
                "role": "toolResult",
                "toolCallId": result.get("tool_use_id", ""),
                "toolName": TOOL_NAME_MAP.get(name, name),
                "content": content_blocks(result.get("content")),
                "isError": bool(result.get("is_error")),
                "timestamp": parse_timestamp(row["timestamp"]),
            },
        )

    def flush_group() -> None:
        """Write the merged assistant message, then the results it produced."""
        nonlocal group
        if group is None:
            return
        content: list[dict] = []
        for member in group["members"]:
            for block in member["message"].get("content") or []:
                kind = block.get("type")
                if kind == "text" and block.get("text"):
                    content.append({"type": "text", "text": block["text"]})
                elif kind == "thinking":
                    text = (block.get("thinking") or "").strip()
                    if text:
                        thinking: dict = {
                            "type": "thinking",
                            "thinking": block["thinking"],
                        }
                        if block.get("signature"):
                            thinking["thinkingSignature"] = block["signature"]
                        content.append(thinking)
                    elif block.get("signature"):
                        # The reasoning arrived encrypted: no text, only the
                        # signature. Map to the block pi-ai stores for a
                        # `redacted_thinking` event. The signature was minted
                        # for Claude Code's context, so a same-model replay
                        # from pi's converted context may 400.
                        content.append({
                            "type": "thinking",
                            "thinking": REDACTED_THINKING_PLACEHOLDER,
                            "redacted": True,
                            "thinkingSignature": block["signature"],
                        })
                elif kind == "tool_use":
                    name = block.get("name", "unknown")
                    content.append({
                        "type": "toolCall",
                        "id": block.get("id", ""),
                        "name": TOOL_NAME_MAP.get(name, name),
                        "arguments": block.get("input") or {},
                    })
        held = group["results"]
        if not content:
            report["dropped"] += 1 + len(held)
            group = None
            return
        last = group["members"][-1]
        provider = "anthropic"
        model_id = group["members"][0]["message"].get("model", "unknown")
        if model_id not in rates_cache:
            rates, reachable = model_rates(provider, model_id)
            if not reachable:
                report["catalog_unreachable"] = True
            elif rates is None and model_id not in report["rates_missing"]:
                report["rates_missing"].append(model_id)
            rates_cache[model_id] = rates
        stop_reason = next(
            (
                m["message"].get("stop_reason")
                for m in reversed(group["members"])
                if m["message"].get("stop_reason")
            ),
            None,
        )
        message = {
            "role": "assistant",
            "content": content,
            "api": "anthropic-messages",
            "provider": provider,
            "model": model_id,
            "responseId": group["message_id"],
            "usage": build_usage(
                last["message"].get("usage") or {}, rates_cache[model_id]
            ),
            "stopReason": STOP_REASON_MAP.get(stop_reason or "", "stop"),
            "timestamp": parse_timestamp(last["timestamp"]),
        }
        if last.get("effort"):
            message["providerThinkingLevel"] = last["effort"]
        writer.append_message(last["timestamp"], f"{group['uuid']}:assistant", message)
        for row, result, position in held:
            emit_result(row, result, position)
        group = None

    for row in convo:
        if row["type"] == "assistant":
            message_id = row["message"].get("id")
            if group is not None and group["message_id"] != message_id:
                flush_group()
            if group is None:
                group = {
                    "message_id": message_id,
                    "members": [],
                    "results": [],
                    "uuid": row.get("uuid", "row"),
                }
            group["members"].append(row)
            continue

        results = (
            [
                block
                for block in (row["message"].get("content") or [])
                if isinstance(block, dict) and block.get("type") == "tool_result"
            ]
            if isinstance(row["message"].get("content"), list)
            else []
        )
        if results and group is not None:
            # Claude Code writes a result before the response that produced it
            # is complete, so hold it until the merged message is written.
            for position, result in enumerate(results):
                group["results"].append((row, result, position))
            continue
        flush_group()
        for position, result in enumerate(results):
            emit_result(row, result, position)
        if not results:
            blocks = content_blocks(row["message"].get("content"))
            if blocks:
                writer.append_message(
                    row["timestamp"],
                    f"{row.get('uuid', 'row')}:user",
                    {
                        "role": "user",
                        "content": blocks,
                        "timestamp": parse_timestamp(row["timestamp"]),
                    },
                )
            else:
                report["dropped"] += 1
    flush_group()

    report["cwd"] = cwd
    report["session_id"] = session_id
    report["first_timestamp"] = first_stamp
    report["last_timestamp"] = max((r["timestamp"] for r in convo), default=first_stamp)
    return writer.entries, report


def session_bytes(entries: list[dict]) -> bytes:
    """Return entries in pi's JSONL session format."""
    return "".join(
        json.dumps(entry, ensure_ascii=False) + "\n" for entry in entries
    ).encode("UTF-8")


def write_session(payload: bytes, destination: Path, mtime_ms: int) -> None:
    """Write a session file and backdate it to the session activity."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
    # pi picks the session to continue by modification time, so an imported
    # archive must not outdate the sessions recorded after it.
    seconds = mtime_ms / 1000
    os.utime(destination, (seconds, seconds))


def migrate(
    transcript: Path,
    rows: list[dict],
    agent_dir: Path,
    output: Path | None = None,
    *,
    force: bool = False,
    trash: bool = False,
) -> tuple[list[dict], dict]:
    """Convert one transcript to a pi session file, then trash it if asked.

    `rows` are the rows of `transcript`, as `read_transcript` returns them.
    Return the entries and the report. The report's `status` is `written`,
    `migrated` when the destination already starts with this conversion,
    `conflict` when the destination holds anything else and `force` is off,
    `invalid` when the transcript holds no session id to name the file, or
    `empty` when it holds no conversation. Only a `written` or `migrated`
    session is trashed.
    """
    entries, report = convert(rows)
    if not report.get("session_id"):
        report["status"] = "invalid"
        return entries, report
    if not any(entry["type"] == "message" for entry in entries):
        report["status"] = "empty"
        return entries, report
    stamp = report["first_timestamp"].replace(":", "-").replace(".", "-")
    destination = (
        output
        or session_dir_for(report["cwd"], agent_dir)
        / f"{stamp}_{report['session_id']}.jsonl"
    )
    report["destination"] = destination
    payload = session_bytes(entries)
    existing = destination.read_bytes() if destination.exists() else None
    if existing is not None and existing.startswith(payload):
        report["status"] = "migrated"
    elif existing is not None and not force:
        report["status"] = "conflict"
        return entries, report
    else:
        write_session(payload, destination, parse_timestamp(report["last_timestamp"]))
        report["status"] = "written"
    report["trashed"] = []
    if trash:
        artifacts = claude_session_artifacts(transcript, report["session_id"])
        if artifacts:
            try:
                report["trashed"] = trash_source(artifacts)
            except (FileNotFoundError, subprocess.CalledProcessError) as error:
                report["trash_error"] = str(error)
    return entries, report


def print_report(entries: list[dict], report: dict) -> None:
    """Print what the pi session of one transcript holds."""
    roles: dict[str, int] = {}
    cost = 0.0
    for entry in entries:
        if entry["type"] != "message":
            continue
        message = entry["message"]
        roles[message["role"]] = roles.get(message["role"], 0) + 1
        cost += message.get("usage", {}).get("cost", {}).get("total", 0.0)
    counts = ", ".join(f"{k}={v}" for k, v in sorted(roles.items()))
    print(f"  entries: {len(entries)} ({counts})")
    print(f"  title: {report['title']}")
    print(f"  cwd: {report['cwd']}")
    print(f"  span: {report['first_timestamp']} .. {report['last_timestamp']}")
    print(f"  tool results: {report['tools']}")
    print(f"  dropped rows: {report['dropped']} (no content pi can render)")
    print(f"  repeated rows: {report['duplicates']} (kept once)")
    print(f"  skipped row types: {report['skipped']}")
    if report["catalog_unreachable"]:
        print("  cost: not computed (pi-ai catalogue unreachable)")
    else:
        print(f"  cost: ${cost:.4f}")
        if report["rates_missing"]:
            print(
                "  no rates for "
                + ", ".join(report["rates_missing"])
                + " in the pi-ai catalogue: their usage costs $0"
            )


def migrate_all(
    agent_dir: Path,
    cooldown_days: int,
    entrypoints: set[str],
    *,
    force: bool,
    trash: bool,
) -> int:
    """Convert the transcript of every session no longer in use, one line each.

    An empty `entrypoints` takes the transcripts of every client.
    """
    transcripts = claude_transcripts()
    running = running_sessions()
    # Claude Code appends to the transcript on every turn, so its modification
    # time is the last activity of the session.
    cutoff = (datetime.now(UTC) - timedelta(days=cooldown_days)).timestamp()
    tally: dict[str, int] = {}
    rates_missing: set[str] = set()
    catalog_unreachable = False
    held_open = recent = other_clients = trash_failures = 0
    for transcript in transcripts:
        pid = running.get(transcript.stem)
        if pid is not None:
            held_open += 1
            print(f"open: {transcript} (pid {pid})")
            continue
        if transcript.stat().st_mtime >= cutoff:
            recent += 1
            continue
        try:
            rows = read_transcript(transcript)
            if entrypoints and not entrypoints & transcript_entrypoints(rows):
                other_clients += 1
                continue
            _, report = migrate(transcript, rows, agent_dir, force=force, trash=trash)
        except (AttributeError, KeyError, OSError, TypeError, ValueError) as error:
            # A transcript that cannot be read, or that holds a row of an
            # unexpected shape, must not stop the others.
            tally["error"] = tally.get("error", 0) + 1
            print(f"error: {transcript}: {error}")
            continue
        status = report["status"]
        tally[status] = tally.get(status, 0) + 1
        rates_missing.update(report["rates_missing"])
        catalog_unreachable = catalog_unreachable or report["catalog_unreachable"]
        line = f"{status}: {report.get('destination', transcript)}"
        if report.get("trash_error"):
            trash_failures += 1
            line += f" (trash failed: {report['trash_error']})"
        elif report.get("trashed"):
            line += f" (source paths moved to Trash: {len(report['trashed'])})"
        print(line)
    counts = ", ".join(f"{k}={v}" for k, v in sorted(tally.items()))
    print(f"{len(transcripts)} transcripts")
    print(f"  open in a running Claude Code process: {held_open}")
    print(f"  modified in the last {cooldown_days} days: {recent}")
    if entrypoints:
        print(f"  from other entrypoints: {other_clients}")
    print(f"  processed: {counts or 'none'}")
    if trash_failures:
        print(f"  sessions whose trash failed: {trash_failures}")
    if catalog_unreachable:
        print("  cost: not computed (pi-ai catalogue unreachable)")
    elif rates_missing:
        print(
            "  no rates for "
            + ", ".join(sorted(rates_missing))
            + " in the pi-ai catalogue: their usage costs $0"
        )
    failures = (
        tally.get("conflict", 0)
        + tally.get("error", 0)
        + tally.get("invalid", 0)
        + trash_failures
    )
    return 1 if failures else 0


def main() -> int:
    """Convert one Claude Code transcript, or all of them, into pi sessions."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "transcript", nargs="?", type=Path, help="Claude Code session .jsonl"
    )
    source.add_argument(
        "--all",
        action="store_true",
        help="convert every transcript in ~/.claude/projects, except open sessions",
    )
    parser.add_argument(
        "--cooldown-days",
        type=int,
        default=DEFAULT_COOLDOWN_DAYS,
        metavar="N",
        help="with --all, skip transcripts modified in the last N days "
        "(default: %(default)s)",
    )
    parser.add_argument(
        "--entrypoint",
        action="append",
        metavar="NAME",
        help="with --all, take only transcripts this client wrote, like cli, "
        "sdk-cli or claude-desktop; repeat to take several",
    )
    parser.add_argument(
        "--agent-dir",
        type=Path,
        default=Path.home() / ".pi" / "agent",
        help="pi agent directory",
    )
    parser.add_argument(
        "--output", type=Path, help="write here instead of the pi session directory"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite a destination that holds another conversion",
    )
    parser.add_argument(
        "--trash-source",
        action="store_true",
        help="move the migrated Claude Code session to the Trash",
    )
    args = parser.parse_args()

    if args.all:
        if args.output:
            parser.error("--output names one file, so it cannot take --all")
        return migrate_all(
            args.agent_dir,
            args.cooldown_days,
            set(args.entrypoint or ()),
            force=args.force,
            trash=args.trash_source,
        )

    if not args.transcript.is_file():
        print(f"No such transcript: {args.transcript}", file=sys.stderr)
        return 1

    entries, report = migrate(
        args.transcript,
        read_transcript(args.transcript),
        args.agent_dir,
        args.output,
        force=args.force,
        trash=args.trash_source,
    )
    if report["status"] == "invalid":
        print(
            "Transcript holds no sessionId; cannot name a pi session.", file=sys.stderr
        )
        return 1
    if report["status"] == "empty":
        print("Transcript holds no conversation; nothing to write.", file=sys.stderr)
        return 1
    if report["status"] == "conflict":
        print(
            f"Refusing to overwrite {report['destination']}; pass --force.",
            file=sys.stderr,
        )
        return 1
    if report["status"] == "migrated":
        print(f"Already migrated: {report['destination']}")
    else:
        print(f"Wrote {report['destination']}")
    print_report(entries, report)
    if args.trash_source:
        if report.get("trash_error"):
            print(
                f"Failed to trash the source: {report['trash_error']}", file=sys.stderr
            )
            return 1
        if not report["trashed"]:
            print("  source: nothing to trash (already gone)")
        for moved in report["trashed"]:
            print(f"  moved to Trash: {moved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
