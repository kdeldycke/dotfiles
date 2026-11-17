#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     # The simple_outline table format ships in 0.9.0, and colalign in 0.8.3.
#     "tabulate>=0.9.0",
# ]
# ///
"""Aggregate coding-agent usage by model across Claude, OpenRouter and Copilot.

`codexbar cost` (CodexBar `0.84.0`) reports the cost of each Claude model only
inside each day row, with a token total and no split. This script sums those
rows per model through the `codexbar` CLI. It reads the input, output, cache
read, cache write and web search counts of each model from the raw Claude Code
logs, the way the CodexBar scanner does, and warns when their sum differs from
the CodexBar total.

`codexbar cost` has no OpenRouter or Copilot report, and its pi source does not
count the sessions pi sends there. This script reads the pi session logs for
those two providers: OpenRouter, where pi records the spend it actually paid,
and GitHub Copilot, a subscription pi estimates at API rates. Their token
counts come from the pi usage records.

One Unicode table carries every provider, with a provider column and the
per-provider cost meanings as a legend below it. The billing column names how
each model charges: subscription plans bill a flat price and get an estimated
cost here, prepaid credits bill the recorded spend, and free endpoints bill
nothing.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from tabulate import tabulate

UNITS = (("b", 1e9), ("m", 1e6), ("k", 1e3))

# Token components each model row reports, in table order.
COMPONENTS = ("input", "output", "cache_read", "cache_write", "web_search")

# Claude Desktop session trees the CodexBar scanner walks for embedded stores.
SESSION_ROOT_NAMES = ("local-agent-mode-sessions", "claude-code-sessions")
SKIPPED_DIRECTORY_NAMES = {
    ".build",
    ".git",
    "build",
    "DerivedData",
    "node_modules",
    "outputs",
    "target",
}

# Pi provider ids, mapped to the section names this report prints.
PI_SECTIONS = {"openrouter": "openrouter", "github-copilot": "copilot"}

# How each section bills, with the cost column meaning that follows from it.
BILLING = {"claude": "subscription", "openrouter": "prepaid", "copilot": "subscription"}

SECTION_NOTES = {
    "claude": "cost estimated at API list prices from local Claude Code logs",
    "openrouter": "cost recorded by pi at OpenRouter prices",
    "copilot": "cost estimated at API rates, billed as plan credits",
}

HEADERS = [
    "provider",
    "model",
    "billing",
    "input",
    "output",
    "cache read",
    "cache write",
    "web search",
    "cost",
    "cost%",
    "tokens",
    "days",
    "active",
]
ALIGNS = (
    "left",
    "left",
    "left",
    "right",
    "right",
    "right",
    "right",
    "right",
    "right",
    "right",
    "right",
    "right",
    "left",
)


def find_codexbar() -> str:
    """Return the `codexbar` executable, or exit when it is not installed."""
    found = shutil.which("codexbar") or "/opt/homebrew/bin/codexbar"
    if not shutil.which(found):
        sys.exit(f"codexbar CLI not found at {found}.")
    return found


def zero_components() -> dict:
    """Return one empty token component accumulator."""
    return dict.fromkeys(COMPONENTS, 0)


def local_day(record: dict) -> date | None:
    """Return the local calendar day of one log record, if it carries one."""
    raw = record.get("timestamp")
    if not raw:
        return None
    try:
        stamp = datetime.fromisoformat(str(raw))
    except ValueError:
        return None
    return stamp.astimezone().date()


def claude_roots() -> list[Path]:
    """Return every project log root the CodexBar Claude scanner reads."""
    home = Path.home()
    roots = [home / ".config/claude/projects", home / ".claude/projects"]
    queue = [
        (home / "Library/Application Support/Claude" / name, 0)
        for name in SESSION_ROOT_NAMES
    ]
    visited = {url for url, _ in queue}
    index = 0
    while index < len(queue):
        url, depth = queue[index]
        index += 1
        projects = url / ".claude" / "projects"
        if projects.is_dir():
            roots.append(projects)
        if depth >= 4:
            continue
        try:
            children = sorted(url.iterdir())
        except OSError:
            continue
        for child in children:
            if not child.is_dir() or child.name in SKIPPED_DIRECTORY_NAMES:
                continue
            if child in visited:
                continue
            visited.add(child)
            queue.append((child, depth + 1))
    return [r for r in dict.fromkeys(roots) if r.is_dir()]


def normalize_model(raw: str, known: set[str]) -> str:
    """Map one raw log model name onto the names the CodexBar report uses."""
    if raw in known:
        return raw
    trimmed = raw.removeprefix("anthropic.")
    if "." in trimmed:
        tail = trimmed.rsplit(".", 1)[1]
        if tail.startswith("claude-"):
            trimmed = tail
    trimmed = re.sub(r"-v\d+:\d+$", "", trimmed)
    base = re.sub(r"-\d{8}$", "", trimmed)
    if base in known:
        return base
    if trimmed in known:
        return trimmed
    return raw


def scan_claude_components(cutoff: date, known: set[str]) -> dict[str, dict]:
    """Sum the raw Claude Code log token components per model.

    Keeps the final cumulative row of each response, the way the CodexBar
    scanner deduplicates streamed and resumed messages.
    """
    keyed: dict[tuple, dict] = {}
    unkeyed: list[dict] = []
    for root in claude_roots():
        for path in root.rglob("*.jsonl"):
            with path.open(encoding="UTF-8") as handle:
                for line in handle:
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if record.get("type") != "assistant":
                        continue
                    message = record.get("message") or {}
                    usage = message.get("usage") or {}
                    raw_model = message.get("model")
                    if not raw_model or not usage:
                        continue
                    model = normalize_model(raw_model, known)
                    row = zero_components()
                    row["input"] = max(0, usage.get("input_tokens") or 0)
                    row["output"] = max(0, usage.get("output_tokens") or 0)
                    row["cache_read"] = max(
                        0, usage.get("cache_read_input_tokens") or 0
                    )
                    row["cache_write"] = max(
                        0, usage.get("cache_creation_input_tokens") or 0
                    )
                    tools = usage.get("server_tool_use") or {}
                    row["web_search"] = max(0, tools.get("web_search_requests") or 0)
                    if not any(row[name] for name in COMPONENTS):
                        continue
                    day = local_day(record)
                    if day is None or day < cutoff:
                        continue
                    row["incomplete"] = (
                        message.get("stop_reason", "absent") is None
                        and row["input"] > 0
                        and row["output"] == 0
                        and "cache_read_input_tokens" not in usage
                        and "cache_creation_input_tokens" not in usage
                    )
                    row["model"] = model
                    message_id = message.get("id")

                    request_id = record.get("requestId")
                    session_id = record.get("sessionId") or record.get("session_id")
                    if message_id and request_id:
                        key: tuple | None = ("request", message_id, request_id)
                    elif message_id and session_id:
                        key = ("session", session_id, message_id)
                    else:
                        key = None
                    if key is None:
                        unkeyed.append(row)
                        continue
                    existing = keyed.get(key)
                    if (
                        not row["incomplete"]
                        or existing is None
                        or existing["incomplete"]
                    ):
                        keyed[key] = row
    totals: dict[str, dict] = defaultdict(zero_components)
    for row in [*keyed.values(), *unkeyed]:
        entry = totals[row["model"]]
        for name in COMPONENTS:
            entry[name] += row[name]
    return totals


def fetch_claude_rows(days: int, cutoff: date) -> list[dict]:
    """Sum the CodexBar per-day model rows of the Claude provider per model."""
    command = [
        find_codexbar(),
        "cost",
        "--provider",
        "claude",
        "--json",
        "--days",
        str(days),
    ]
    proc = subprocess.run(
        command, capture_output=True, text=True, encoding="UTF-8", check=False
    )
    if proc.returncode != 0:
        sys.exit(f"codexbar cost failed ({proc.returncode}): {proc.stderr.strip()}")
    report = next(
        (e for e in json.loads(proc.stdout) if e.get("provider") == "claude"), None
    )
    if report is None:
        sys.exit("codexbar cost returned no report for provider 'claude'.")
    daily = report.get("daily", [])
    known = {
        row["modelName"] for day in daily for row in day.get("modelBreakdowns", [])
    }
    components = scan_claude_components(cutoff, known)
    models: dict[str, dict] = defaultdict(
        lambda: {"cost": 0.0, "tokens": 0, "days": 0, "first": "", "last": ""}
    )
    for day in daily:
        for row in day.get("modelBreakdowns", []):
            entry = models[row["modelName"]]
            entry["cost"] += row["cost"]
            entry["tokens"] += row["totalTokens"]
            entry["days"] += 1
            entry["first"] = entry["first"] or day["date"]
            entry["last"] = day["date"]
    rows = []
    for name, entry in models.items():
        sums = components.get(name) or zero_components()
        total = sum(sums[c] for c in COMPONENTS[:4])
        if abs(total - entry["tokens"]) > entry["tokens"] * 0.001:
            print(
                f"warning: claude {name} component sum {total} "
                f"differs from the codexbar total {entry['tokens']}.",
                file=sys.stderr,
            )
        rows.append(
            dict(model=name, billing=billing_for("claude", name), **sums, **entry)
        )
    return rows


def fetch_pi_rows(sections: set[str], cutoff: date) -> dict[str, list[dict]]:
    """Sum pi session usage per model, per mapped provider section."""
    root = Path.home() / ".pi" / "agent" / "sessions"
    seen: set[str] = set()
    models: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"cost": 0.0, "tokens": 0, "days": set(), "first": "", "last": ""}
    )
    for path in root.rglob("*.jsonl"):
        with path.open(encoding="UTF-8") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                message = record.get("message") or {}
                if message.get("role") != "assistant" or not message.get("usage"):
                    continue
                section = PI_SECTIONS.get(message.get("provider") or "")
                if section not in sections:
                    continue
                if record.get("id") in seen:
                    continue
                seen.add(record.get("id"))
                day = local_day(record)
                if day is None or day < cutoff:
                    continue
                model = message.get("model")
                if not model:
                    continue
                usage = message["usage"]
                entry = models[(section, model)]
                entry["cost"] += (usage.get("cost") or {}).get("total") or 0.0
                entry["tokens"] += usage.get("totalTokens") or 0
                entry["input"] = entry.get("input", 0) + (usage.get("input") or 0)
                entry["output"] = entry.get("output", 0) + (usage.get("output") or 0)
                entry["cache_read"] = entry.get("cache_read", 0) + (
                    usage.get("cacheRead") or 0
                )
                entry["cache_write"] = entry.get("cache_write", 0) + (
                    usage.get("cacheWrite") or 0
                )
                entry["web_search"] = entry.get("web_search", 0)
                entry["days"].add(day.isoformat())
                entry["first"] = min(entry["first"] or day.isoformat(), day.isoformat())
                entry["last"] = max(entry["last"], day.isoformat())
    rows: dict[str, list] = defaultdict(list)
    for (section, model), entry in models.items():
        days = entry.pop("days")
        for name in COMPONENTS:
            entry.setdefault(name, 0)
        rows[section].append(
            dict(
                model=model,
                billing=billing_for(section, model),
                days=len(days),
                **entry,
            )
        )
    return rows


def billing_for(section: str, model: str) -> str:
    """Return how one model bills, free endpoints included."""
    if model.endswith(":free"):
        return "free"
    return BILLING[section]


def format_count(count: float) -> str:
    """Render one count with one decimal and lowercase k, m, b units."""
    if count < 1000:
        return str(int(count))
    for unit, divisor in UNITS:
        if count >= divisor:
            return f"{count / divisor:.1f}{unit}"
    return str(int(count))


def render_table(
    header: list[str], body: list[list[str]], footer: list[str] | None = None
) -> str:
    """Render one Unicode table from pre-formatted cell strings."""
    rows = [*body, *([footer] if footer else [])]
    return str(
        tabulate(
            rows,
            headers=header,
            tablefmt="simple_outline",
            colalign=ALIGNS,
            disable_numparse=True,
        )
    )


def model_row(row: dict, cost: float) -> list[str]:
    """Format one model aggregate into table cells."""
    share = f"{100 * row['cost'] / cost:.1f}%" if cost else ""
    search = str(row["web_search"]) if row["web_search"] else ""
    return [
        row["provider"],
        row["model"],
        row["billing"],
        *[format_count(row[name]) for name in COMPONENTS[:4]],
        search,
        f"{row['cost']:,.2f}",
        share,
        format_count(row["tokens"]),
        str(row["days"]),
        f"{row['first']}..{row['last']}",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--days", type=int, default=60, help="window length in days (default: 60)"
    )
    parser.add_argument(
        "--provider",
        default="claude,openrouter,copilot",
        help="comma-separated provider sections (default: claude,openrouter,copilot)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="print the aggregate as JSON",
    )
    args = parser.parse_args()

    sections = [s.strip() for s in args.provider.split(",") if s.strip()]
    unknown = [s for s in sections if s not in SECTION_NOTES]
    if unknown:
        sys.exit(f"unknown provider(s): {', '.join(unknown)}.")
    cutoff = (datetime.now().astimezone() - timedelta(days=args.days - 1)).date()

    data: dict[str, list[dict]] = {}
    if "claude" in sections:
        data["claude"] = fetch_claude_rows(args.days, cutoff)
    pi_sections = {s for s in sections if s != "claude"}
    if pi_sections:
        data.update(fetch_pi_rows(pi_sections, cutoff))
    for name in sections:
        data.setdefault(name, [])

    if args.as_json:
        print(
            json.dumps(
                {
                    name: sorted(data[name], key=lambda r: -r["cost"])
                    for name in sections
                },
                indent=2,
            )
        )
        return

    print(f"usage by model, last {args.days} days (since {cutoff}):")
    rows = [dict(row, provider=name) for name in sections for row in data[name]]
    rows.sort(key=lambda row: -row["cost"])
    if not rows:
        print("no usage in window")
        return
    total_cost = sum(row["cost"] for row in rows)
    total_tokens = sum(row["tokens"] for row in rows)
    totals = {name: sum(row[name] for row in rows) for name in COMPONENTS}
    body = [model_row(row, total_cost) for row in rows]
    footer = [
        "TOTAL",
        "",
        "",
        *[format_count(totals[name]) for name in COMPONENTS[:4]],
        str(totals["web_search"]) or "",
        f"{total_cost:,.2f}",
        "",
        format_count(total_tokens),
        "",
        "",
    ]
    print()
    print(render_table(HEADERS, body, footer))
    for name in sections:
        print(f"{name}: {SECTION_NOTES[name]}")


if __name__ == "__main__":
    main()
