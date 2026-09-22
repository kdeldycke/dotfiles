#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Convert a Claude Code transcript into a pi session file.

Claude Code stores one session as JSONL under
`~/.claude/projects/--<cwd>--/<session-uuid>.jsonl`. pi stores one session as
JSONL under `~/.pi/agent/sessions/--<cwd>--/<timestamp>_<session-id>.jsonl`,
with a version 3 header and a tree of entries linked by `id`/`parentId`.

The two formats disagree on five points this script resolves:

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
   content, so they are dropped and counted in the report.

With --trash-source the script moves the migrated session's Claude Code
artifacts to the Trash through the `trash` CLI, and only after the pi file
was written: the transcript, its tool-results directory, the session title,
the session-env marker, the session tasks directory, and the wrapup-nudge
marker when it names this session. Shared files that only reference the
session (the prompt history, the global config and its backups) are left in
place: other sessions write them too, and the references age out on their
own. Trashing always goes through `trash`, never `rm`, so a mistaken import
stays recoverable, and the script trashes nothing at all when the
CLI is missing.

Entry ids derive from the Claude row uuid, so re-running the script on one
transcript writes byte-identical output.
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
from datetime import datetime, timezone
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


def entry_id(seed: str) -> str:
    """Return a deterministic 8-char hex entry id for `seed`."""
    return hashlib.md5(seed.encode("UTF-8")).hexdigest()[:8]


def parse_timestamp(value: str) -> int:
    """Return Unix milliseconds for an ISO 8601 timestamp."""
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)


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


def model_rates(provider: str, model_id: str) -> dict | None:
    """Return per-million-token cost rates from the bundled pi-ai catalogue."""
    root = pi_install_root()
    if root is None:
        return None
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
        return None
    try:
        payload = json.loads(catalog.read_text(encoding="UTF-8"))
    except (OSError, json.JSONDecodeError):
        return None
    for api_models in payload.values():
        model = api_models.get(model_id) if isinstance(api_models, dict) else None
        if isinstance(model, dict) and isinstance(model.get("cost"), dict):
            return model["cost"]
    return None


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


def claude_session_artifacts(transcript: Path, session_id: str) -> list[Path]:
    """Return every `~/.claude` path holding artifacts of this one session.

    Only paths whose name, or content in the case of the nudge marker, ties
    them to `session_id` qualify. Shared files that merely reference the
    session are deliberately excluded: other sessions write them too.
    """
    claude = Path.home() / ".claude"
    artifacts: list[Path] = []
    # The transcript and its tool-results directory belong to this session
    # only when they sit in the standard project store a live Claude Code
    # session would have written them to. A transcript passed from elsewhere
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
    for path in artifacts:
        subprocess.run([trash, str(path)], check=True)
    return artifacts


class SessionWriter:
    """Accumulate pi session entries as one linear chain."""

    def __init__(self, header: dict) -> None:
        self.entries: list[dict] = [header]
        self.parent_id: str | None = None

    def _append(
        self, entry_type: str, field: str, stamp: str, seed: str, value: dict | str
    ) -> str:
        """Append one entry after the current leaf and return its id."""
        new_id = entry_id(seed)
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
    report: dict = {"skipped": {}, "dropped": 0, "tools": {}}

    session_id = next((r["sessionId"] for r in rows if r.get("sessionId")), None)
    cwds = [r["cwd"] for r in rows if isinstance(r.get("cwd"), str)]
    cwd = max(set(cwds), key=cwds.count) if cwds else str(Path.cwd())
    stamps = [r["timestamp"] for r in rows if isinstance(r.get("timestamp"), str)]
    first_stamp = min(stamps) if stamps else datetime.now(timezone.utc).isoformat()

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
        name = tool_names.get(result.get("tool_use_id"), "unknown")
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
            rates_cache[model_id] = model_rates(provider, model_id)
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
            "stopReason": STOP_REASON_MAP.get(stop_reason, "stop"),
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


def write_session(entries: list[dict], destination: Path, mtime_ms: int) -> None:
    """Write entries as JSONL and backdate the file to the session activity."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="UTF-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, ensure_ascii=False))
            handle.write("\n")
    # pi picks the session to continue by modification time, so an imported
    # archive must not outdate the sessions recorded after it.
    seconds = mtime_ms / 1000
    os.utime(destination, (seconds, seconds))


def main() -> int:
    """Convert one Claude Code transcript into a pi session file."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("transcript", type=Path, help="Claude Code session .jsonl")
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
        "--force", action="store_true", help="overwrite an existing destination"
    )
    parser.add_argument(
        "--trash-source",
        action="store_true",
        help="move the migrated Claude Code session to the Trash",
    )
    args = parser.parse_args()

    if not args.transcript.is_file():
        print(f"No such transcript: {args.transcript}", file=sys.stderr)
        return 1

    rows = read_transcript(args.transcript)
    entries, report = convert(rows)
    if not report.get("session_id"):
        print(
            "Transcript holds no sessionId; cannot name a pi session.", file=sys.stderr
        )
        return 1

    stamp = report["first_timestamp"].replace(":", "-").replace(".", "-")
    destination = (
        args.output
        or session_dir_for(report["cwd"], args.agent_dir)
        / f"{stamp}_{report['session_id']}.jsonl"
    )
    if destination.exists() and not args.force:
        print(f"Refusing to overwrite {destination}; pass --force.", file=sys.stderr)
        return 1

    write_session(entries, destination, parse_timestamp(report["last_timestamp"]))

    roles: dict[str, int] = {}
    cost = 0.0
    for entry in entries:
        if entry["type"] != "message":
            continue
        message = entry["message"]
        roles[message["role"]] = roles.get(message["role"], 0) + 1
        cost += message.get("usage", {}).get("cost", {}).get("total", 0.0)
    print(f"Wrote {destination}")
    counts = ", ".join(f"{k}={v}" for k, v in sorted(roles.items()))
    print(f"  entries: {len(entries)} ({counts})")
    print(f"  title: {report['title']}")
    print(f"  cwd: {report['cwd']}")
    print(f"  span: {report['first_timestamp']} .. {report['last_timestamp']}")
    print(f"  tool results: {report['tools']}")
    print(f"  dropped rows: {report['dropped']} (no content pi can render)")
    print(f"  skipped row types: {report['skipped']}")
    if cost:
        print(f"  cost: ${cost:.4f}")
    else:
        print("  cost: not computed (pi-ai catalogue unreachable)")
    if args.trash_source:
        artifacts = claude_session_artifacts(args.transcript, report["session_id"])
        if not artifacts:
            print("  source: nothing to trash (already gone)")
            return 0
        try:
            for moved in trash_source(artifacts):
                print(f"  moved to Trash: {moved}")
        except (FileNotFoundError, subprocess.CalledProcessError) as error:
            print(f"Failed to trash the source: {error}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
