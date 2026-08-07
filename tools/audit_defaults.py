#!/usr/bin/env python3
"""Audit the `defaults` keys of macos-config.sh against the running macOS.

For every `defaults write` / `defaults delete` in the script, extract the
(domain, key) pair, then scan the system's binaries (app executables and the
dyld shared cache) for the key string. A key referenced nowhere in system code
cannot be read by anything and is a strong dead-key candidate; a referenced key
is likely still consumed. String presence is a heuristic: it proves at most
that some binary knows the key, and short generic names can collide with
unrelated strings, so treat "referenced" as "probably alive" and "unreferenced"
as "almost certainly dead".

Also flags malformed invocations, like a `defaults write` whose first argument
after the verb is followed by a type flag instead of a key: that writes to a
bogus domain named after what was meant to be the key.

Usage: audit_defaults.py [--scan] macos-config.sh
Without --scan, only the parse and malformed-line report run (fast, no system
access): useful to iterate on the parser locally.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import shlex
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

# Locations of binaries that read preferences: standalone app executables plus
# the dyld shared cache holding every system framework and daemon.
BINARY_GLOBS = (
    "/Applications/*.app/Contents/MacOS/*",
    "/System/Applications/*.app/Contents/MacOS/*",
    "/System/Applications/Utilities/*.app/Contents/MacOS/*",
    "/System/Library/CoreServices/*.app/Contents/MacOS/*",
    "/System/Volumes/Preboot/Cryptexes/OS/System/Library/dyld/dyld_shared_cache_*",
)

DEFAULTS_RE = re.compile(r"^\s*(?:sudo\s+)?defaults\s")


def join_continuations(text: str) -> list[str]:
    """Merge backslash-continued lines into single logical lines."""
    lines: list[str] = []
    buffer = ""
    for raw in text.splitlines():
        if raw.rstrip().endswith("\\"):
            buffer += raw.rstrip()[:-1] + " "
            continue
        lines.append(buffer + raw)
        buffer = ""
    if buffer:
        lines.append(buffer)
    return lines


def parse_defaults_calls(script: Path) -> list[dict]:
    """Extract every defaults invocation as {line, verb, domain, key, malformed}."""
    calls = []
    for lineno_text in enumerate(join_continuations(script.read_text()), 1):
        lineno, line = lineno_text
        stripped = line.strip()
        if stripped.startswith("#") or not DEFAULTS_RE.match(line):
            continue
        try:
            tokens = shlex.split(stripped, comments=True)
        except ValueError:
            continue
        # Drop everything before the defaults verb.
        while tokens and tokens[0] != "defaults":
            tokens.pop(0)
        tokens.pop(0)
        # Skip host-scoping flags.
        while tokens and tokens[0] in ("-currentHost", "-host"):
            tokens.pop(0)
            if tokens and not tokens[0].startswith("-"):
                continue
        if not tokens:
            continue
        verb = tokens.pop(0)
        if verb not in ("write", "delete"):
            continue
        if not tokens:
            continue
        domain = tokens.pop(0)
        key = None
        malformed = False
        if tokens:
            if tokens[0].startswith("-"):
                # A type flag where the key belongs: the intended key was
                # parsed as the domain. Real-world case: a missing domain.
                malformed = True
            else:
                key = tokens.pop(0)
        elif verb == "write":
            # A write without any key at all.
            malformed = True
        calls.append({
            "line": lineno,
            "verb": verb,
            "domain": domain,
            "key": key,
            "malformed": malformed,
        })
    return calls


def collect_binaries() -> list[Path]:
    """Resolve the binary globs to existing, non-empty files."""
    found = []
    for pattern in BINARY_GLOBS:
        for hit in glob.glob(pattern):
            path = Path(hit)
            if path.is_file() and path.stat().st_size:
                found.append(path)
    return found


def scan_keys(keys: set[str], binaries: list[Path]) -> dict[str, set[str]]:
    """Single-pass fixed-string scan of all binaries for all keys.

    Returns {key: {consumer label, ...}}. The dyld cache files are labeled
    "dyld-cache", app binaries by their basename.
    """
    hits: dict[str, set[str]] = defaultdict(set)
    if not keys or not binaries:
        return hits
    patterns = "\n".join(sorted(keys))
    # -w bounds matches at non-word characters, cutting substring noise
    # (a key named "ring" must not match "string"). -a treats binaries as
    # text, -o emits each match, -H prefixes the file name.
    result = subprocess.run(
        ["grep", "-aowHF", "-f", "/dev/stdin", *map(str, binaries)],
        input=patterns,
        capture_output=True,
        text=True,
        check=False,
    )
    for match_line in set(result.stdout.splitlines()):
        path_str, _, key = match_line.rpartition(":")
        if key not in keys:
            continue
        name = Path(path_str).name
        label = "dyld-cache" if name.startswith("dyld_shared_cache") else name
        hits[key].add(label)
    return hits


def emit(report: str) -> None:
    """Print the report, duplicating it into the GitHub job summary if any."""
    print(report)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="UTF-8") as fh:
            fh.write(report + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("script", type=Path)
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Scan system binaries for key consumers (slow, macOS only).",
    )
    args = parser.parse_args()

    calls = parse_defaults_calls(args.script)
    malformed = [c for c in calls if c["malformed"]]
    keyed = [c for c in calls if c["key"]]

    lines = [f"# `defaults` audit of {args.script.name}", ""]
    lines.append(
        f"{len(calls)} defaults invocations: {len(keyed)} with a key, "
        f"{len(malformed)} malformed."
    )
    lines.append("")

    if malformed:
        lines.append("## Malformed invocations")
        lines.append("")
        lines.append("| Line | Invocation parsed as |")
        lines.append("| ---: | :--- |")
        for call in malformed:
            lines.append(
                f"| {call['line']} | `{call['verb']}` on domain "
                f"`{call['domain']}` with no key |"
            )
        lines.append("")

    if not args.scan:
        lines.append("Scan skipped (no --scan): parse-only run.")
        emit("\n".join(lines))
        return 0

    binaries = collect_binaries()
    keys = {c["key"] for c in keyed}
    hits = scan_keys(keys, binaries)

    dead = sorted(
        (c for c in keyed if not hits.get(c["key"])),
        key=lambda c: c["line"],
    )
    lines.append(f"Scanned {len(binaries)} binaries for {len(keys)} keys.")
    lines.append("")
    lines.append("## Dead-key candidates (referenced by no system binary)")
    lines.append("")
    lines.append("| Line | Domain | Key |")
    lines.append("| ---: | :--- | :--- |")
    for call in dead:
        lines.append(f"| {call['line']} | `{call['domain']}` | `{call['key']}` |")
    lines.append("")
    lines.append("## Referenced keys")
    lines.append("")
    lines.append("| Line | Domain | Key | Consumers |")
    lines.append("| ---: | :--- | :--- | :--- |")
    for call in keyed:
        consumers = hits.get(call["key"])
        if not consumers:
            continue
        shown = ", ".join(f"`{c}`" for c in sorted(consumers)[:4])
        if len(consumers) > 4:
            shown += f" +{len(consumers) - 4} more"
        lines.append(
            f"| {call['line']} | `{call['domain']}` | `{call['key']}` | {shown} |"
        )

    emit("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
