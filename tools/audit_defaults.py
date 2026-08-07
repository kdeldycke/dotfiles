#!/usr/bin/env python3
"""Audit the `defaults` keys of macos-config.sh against the running macOS.

For every `defaults write` / `defaults delete` in the script, extract the
(domain, key) pair, then look for the key in the string tables of the system's
binaries: the app executables and the dyld shared cache holding every framework
and daemon. A key no system binary carries cannot be read by anything and is a
strong dead-key candidate.

The match is exact, against the standalone C strings a binary embeds, which is
how a preference key is normally stored. So a key reported as referenced is
almost certainly alive, while a key reported dead could in theory still be
built at runtime by string concatenation. Verify a prune candidate in the UI
before removing it.

Usage: audit_defaults.py [--scan] macos-config.sh

Without --scan only the parse runs (instant, no system access), which is enough
to iterate on the parser or to catch malformed invocations.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import plistlib
import shlex
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

# Binaries that read preferences: standalone app executables, plus the dyld
# shared cache holding every system framework and daemon (since Big Sur the
# frameworks no longer exist as individual files on disk).
#
# Only the arm64e cache is scanned. The x86_64 cache next to it serves the
# retired Rosetta translation path and duplicates the same strings, at the cost
# of 4.9 GB of extra reads. The .map and .atlas siblings are cache layout
# metadata carrying no preference strings.
BINARY_GLOBS = (
    "/Applications/*.app/Contents/MacOS/*",
    "/System/Applications/*.app/Contents/MacOS/*",
    "/System/Applications/Utilities/*.app/Contents/MacOS/*",
    "/System/Library/CoreServices/*.app/Contents/MacOS/*",
    "/System/Volumes/Preboot/Cryptexes/OS/System/Library/dyld/dyld_shared_cache_arm64e*",
)
EXCLUDED_SUFFIXES = (".map", ".atlas")

DEFAULTS_RE = re.compile(r"^\s*(?:sudo\s+)?defaults\s")

# Apple's own apps and frameworks store preference keys as literal strings, so
# a missing key is good evidence the setting is gone. Third-party apps, Swift
# ones especially, routinely build keys at runtime ("\(module)_widget"), which
# makes a missing key meaningless there. Stats is the proven case: its binary
# carries `_widget` and `_state`, never `CPU_widget`.
APPLE_DOMAIN_RE = re.compile(r"^(com\.apple\.|NSGlobalDomain$|\.GlobalPreferences)")

# Bundles holding the apps whose Info.plist declares a preference domain.
APP_GLOBS = (
    "/Applications/*.app",
    "/System/Applications/*.app",
    "/System/Applications/Utilities/*.app",
    "/System/Library/CoreServices/*.app",
)


def normalize_domain(domain: str) -> str:
    """Reduce a domain to its bare identifier.

    A `defaults` domain can be given as a path to a plist, possibly inside
    another app's container: only the file name identifies the owner. So
    `~/Library/Containers/com.apple.ScreenSaver.../com.JohnCoates.Aerial.plist`
    belongs to Aerial, not to Apple's screen saver engine.
    """
    bare = domain.rsplit("/", 1)[-1]
    return bare[: -len(".plist")] if bare.endswith(".plist") else bare


def installed_bundle_ids() -> set[str]:
    """Bundle identifiers declared by the app bundles present on this system."""
    ids: set[str] = set()
    for pattern in APP_GLOBS:
        for bundle in glob.glob(pattern):
            info = Path(bundle) / "Contents/Info.plist"
            try:
                with info.open("rb") as fh:
                    data = plistlib.load(fh)
            except (OSError, ValueError, plistlib.InvalidFileException):
                continue
            identifier = data.get("CFBundleIdentifier")
            if isinstance(identifier, str):
                ids.add(identifier)
    return ids


def join_continuations(text: str) -> list[str]:
    """Merge backslash-continued lines into single logical lines.

    The line number reported is that of the first physical line.
    """
    lines: list[tuple[int, str]] = []
    buffer = ""
    start = 0
    for lineno, raw in enumerate(text.splitlines(), 1):
        if not buffer:
            start = lineno
        if raw.rstrip().endswith("\\"):
            buffer += raw.rstrip()[:-1] + " "
            continue
        lines.append((start, buffer + raw))
        buffer = ""
    if buffer:
        lines.append((start, buffer))
    return lines


def parse_defaults_calls(script: Path) -> list[dict]:
    """Extract every defaults invocation as {line, verb, domain, key, malformed}."""
    calls = []
    for lineno, line in join_continuations(script.read_text()):
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
        # Skip host-scoping flags. -host takes a hostname argument, -currentHost
        # does not.
        while tokens and tokens[0] in ("-currentHost", "-host"):
            if tokens.pop(0) == "-host" and tokens:
                tokens.pop(0)
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
            # A type flag where the key belongs means the intended key was
            # consumed as the domain: the write lands in a bogus domain.
            if tokens[0].startswith("-"):
                malformed = True
            else:
                key = tokens.pop(0)
        elif verb == "write":
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
    """Resolve the binary globs to existing, non-empty, non-metadata files."""
    found = []
    for pattern in BINARY_GLOBS:
        for hit in glob.glob(pattern):
            path = Path(hit)
            if path.suffix in EXCLUDED_SUFFIXES:
                continue
            if path.is_file() and path.stat().st_size:
                found.append(path)
    return sorted(set(found))


def keys_in_binary(path: Path, keys: set[str]) -> set[str]:
    """Return the keys stored as a standalone string inside `path`."""
    found: set[str] = set()
    try:
        process = subprocess.Popen(
            ["strings", "-a", str(path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            errors="replace",
        )
    except OSError:
        return found
    assert process.stdout is not None
    for line in process.stdout:
        candidate = line.rstrip("\n")
        if candidate in keys:
            found.add(candidate)
    process.wait()
    return found


def scan_keys(keys: set[str], binaries: list[Path]) -> dict[str, set[str]]:
    """Map each key to the set of binaries carrying it.

    Cache splits all report as the single `dyld-cache` consumer, since a
    per-split attribution says nothing useful.
    """
    hits: dict[str, set[str]] = defaultdict(set)
    for index, path in enumerate(binaries, 1):
        name = path.name
        label = "dyld-cache" if name.startswith("dyld_shared_cache") else name
        for key in keys_in_binary(path, keys):
            hits[key].add(label)
        if index % 25 == 0 or index == len(binaries):
            print(f"  scanned {index}/{len(binaries)} binaries", file=sys.stderr)
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
        help="Scan system binaries for key consumers (macOS only).",
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
        lines.append("| Line | Parsed as |")
        lines.append("| ---: | :--- |")
        for call in malformed:
            lines.append(
                f"| {call['line']} | `{call['verb']}` on domain "
                f"`{call['domain']}` with no key |"
            )
        lines.append("")

    if not args.scan:
        lines.append("Scan skipped (no `--scan`): parse-only run.")
        emit("\n".join(lines))
        return 0

    binaries = collect_binaries()
    keys = {c["key"] for c in keyed}
    started = time.monotonic()
    hits = scan_keys(keys, binaries)
    elapsed = time.monotonic() - started

    dead = sorted((c for c in keyed if not hits.get(c["key"])), key=lambda c: c["line"])
    bundle_ids = installed_bundle_ids()

    # An app that is not installed cannot carry its own keys, so its whole
    # domain is inconclusive rather than dead. Only domains shaped like a
    # bundle identifier can be checked this way: a domain like
    # com.apple.screencapture names a system setting owned by no app, and
    # correctly stays out of this bucket.
    absent, apple_dead, other_dead = [], [], []
    for call in dead:
        domain = normalize_domain(call["domain"])
        call["owner"] = domain
        if domain.count(".") >= 2 and domain not in bundle_ids:
            absent.append(call)
        elif APPLE_DOMAIN_RE.search(domain):
            apple_dead.append(call)
        else:
            other_dead.append(call)

    lines.append(
        f"Scanned {len(binaries)} binaries for {len(keys)} distinct keys "
        f"in {elapsed:.0f}s."
    )
    lines.append("")

    lines.append(f"## Prune candidates: {len(apple_dead)}")
    lines.append("")
    lines.append(
        "Carried by no system binary, in an installed Apple domain that stores "
        "keys literally. Confirm in the UI, then prune."
    )
    lines.append("")
    lines.append("| Line | Domain | Key |")
    lines.append("| ---: | :--- | :--- |")
    for call in apple_dead:
        lines.append(f"| {call['line']} | `{call['domain']}` | `{call['key']}` |")
    lines.append("")

    lines.append(f"## Inconclusive, owning app not installed: {len(absent)}")
    lines.append("")
    lines.append(
        "No bundle on this system declares these domains, so their keys could "
        "not be found whatever their state. Re-check on a machine that has the "
        "app."
    )
    lines.append("")
    lines.append("| Line | Domain | Key |")
    lines.append("| ---: | :--- | :--- |")
    for call in absent:
        lines.append(f"| {call['line']} | `{call['owner']}` | `{call['key']}` |")
    lines.append("")

    lines.append(f"## Inconclusive, keys likely built at runtime: {len(other_dead)}")
    lines.append("")
    lines.append(
        "The owning app is installed but does not store these keys literally, "
        "which is normal for apps assembling key names at runtime."
    )
    lines.append("")
    lines.append("| Line | Domain | Key |")
    lines.append("| ---: | :--- | :--- |")
    for call in other_dead:
        lines.append(f"| {call['line']} | `{call['domain']}` | `{call['key']}` |")
    lines.append("")

    alive = [c for c in keyed if hits.get(c["key"])]
    lines.append(f"## Referenced keys: {len(alive)}")
    lines.append("")
    lines.append("| Line | Domain | Key | Consumers |")
    lines.append("| ---: | :--- | :--- | :--- |")
    for call in alive:
        consumers = hits[call["key"]]
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
