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

Usage: audit_defaults.py [--scan] [--menubar] macos-config.sh

Without --scan only the parse runs (instant, no system access), which is enough
to iterate on the parser or to catch malformed invocations.

--menubar switches to a different question. Instead of asking whether a key is
still read by anything, it diffs what the script declares for the menu bar
against what the running system actually stores, key by key. That closes the
loop the string scan cannot: `menuExtras` passes the scan, because
SystemUIServer still carries the name, while every value written to it is
discarded. Rearrange the menu bar in System Settings, re-run with --menubar,
and the diff names the keys to copy back into the script. It exits non-zero
while the two disagree, so it can drive a fix-and-recheck loop.
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

# Every store holding menu bar state, as (domain, per-host, keys). Control
# Center appears twice on purpose: the module placement codes live in the
# per-host plist that System Settings writes, while the plain status items and
# the menu bar behaviour sit in the global one. They are separate files, and a
# key found in one says nothing about the other.
#
# `keys` is None when the whole domain is menu bar state, so that a module
# added by a future macOS shows up on its own. Siri, Spotlight and the input
# menu keep their icon in a domain they share with unrelated settings, from
# spell checking to keyboard shortcuts, so only the one key is in scope there.
MENUBAR_DOMAINS: tuple[tuple[str, bool, frozenset[str] | None], ...] = (
    ("com.apple.Siri", False, frozenset({"StatusMenuVisible"})),
    ("com.apple.Spotlight", True, frozenset({"MenuItemHidden"})),
    ("com.apple.TextInputMenu", False, frozenset({"visible"})),
    ("com.apple.controlcenter", False, None),
    ("com.apple.controlcenter", True, None),
    ("com.apple.menuextra.clock", False, None),
)

# The menu bar plists mix configuration with runtime bookkeeping. Comparing the
# bookkeeping would report drift on every run: the heartbeat timestamps move on
# their own, and a preferred position changes whenever an icon is dragged.
#
# The numbered `Item-N` slots are dropped for a different reason. AppKit files
# a status item under its own name when it has one, and under an anonymous slot
# when it does not, so those entries name no module and cannot be acted on.
MENUBAR_NOISE_RE = re.compile(
    r"""
      ^NSStatusItem\ Preferred\ Position   # where an icon was last dragged
    | ^NSStatusItem\ Visible\ Item-\d+$    # anonymous status item slots
    | ^IIO_                                # launch timing telemetry
    | ^Last                                # heartbeat and analytics stamps
    | ^ControlCenterDisplayable            # serialised widget registry
    | ^LiveActivityState$
    | ^HasAttempted                        # one-shot migration flags
    | ^missionControlTooltipCount$
    | Token$
    """,
    re.VERBOSE,
)

# Processes that own a menu bar preference. The clock keys are read from a
# framework rather than an app, so the shared cache is scanned too, which is
# what makes --menubar --scan slow enough to keep behind the flag.
MENUBAR_BINARY_GLOBS = (
    "/System/Library/CoreServices/ControlCenter.app/Contents/MacOS/ControlCenter",
    "/System/Library/CoreServices/Siri.app/Contents/MacOS/Siri",
    "/System/Library/CoreServices/Spotlight.app/Contents/MacOS/Spotlight",
    "/System/Library/CoreServices/SystemUIServer.app/Contents/MacOS/SystemUIServer",
    "/System/Library/CoreServices/TextInputMenuAgent.app/Contents/MacOS/TextInputMenuAgent",
    "/System/Volumes/Preboot/Cryptexes/OS/System/Library/dyld/dyld_shared_cache_arm64e*",
)

# `defaults` spells a boolean six ways and stores the same CFBoolean for each.
BOOL_WORDS = {
    "true": True,
    "yes": True,
    "1": True,
    "false": False,
    "no": False,
    "0": False,
}

# Marks a declared value the audit will not compare: a container, a blob, or a
# shell expansion. Reporting it as drift would be noise, since no comparison
# was possible in the first place.
OPAQUE = object()

# AppKit files a status item's visibility under a key it builds at runtime, by
# appending the item's autosave name to a fixed prefix. Neither the assembled
# key nor the prefix survives into a string table, so the binary scan can say
# nothing about the family and reports every one of them dead. They are
# excluded from the verdict instead: an untestable key is not a dead one.
COMPOSED_KEY_RE = re.compile(r"^NSStatusItem (?:Visible|VisibleCC|Preferred Position) ")


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


def parse_value(tokens: list[str]) -> object:
    """Decode the value of a `defaults write` into what would land in the plist.

    Only the scalar types are decoded, which is all the menu bar uses. A
    container, a `-data` blob or anything carrying a shell expansion comes back
    as OPAQUE: the script's text alone does not say what those store, and
    guessing would manufacture drift.

    Booleans and integers deliberately share a comparison space. `defaults`
    accepts `-bool false` and `-int 0` for what macOS treats as the same
    setting, and Python's `False == 0` lets one match a plist holding the
    other, which is the answer the audit wants.
    """
    if not tokens:
        return OPAQUE
    flag = tokens[0]
    if not flag.startswith("-"):
        # An untyped write. `defaults` guesses the type from the text, and so
        # does this: a bare integer is stored as one.
        raw = " ".join(tokens)
        if "$" in raw:
            return OPAQUE
        return int(raw) if raw.lstrip("-").isdigit() else raw
    rest = tokens[1:]
    if any("$" in token for token in rest):
        return OPAQUE
    if flag in ("-bool", "-boolean") and len(rest) == 1:
        return BOOL_WORDS.get(rest[0].lower(), OPAQUE)
    if flag in ("-int", "-integer") and len(rest) == 1:
        try:
            return int(rest[0])
        except ValueError:
            return OPAQUE
    if flag == "-float" and len(rest) == 1:
        try:
            return float(rest[0])
        except ValueError:
            return OPAQUE
    if flag == "-string":
        return " ".join(rest)
    return OPAQUE


def parse_defaults_calls(script: Path) -> list[dict]:
    """Extract every defaults invocation as a dict of its parsed arguments."""
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
        # Host-scoping flags. -host takes a hostname argument, -currentHost does
        # not. Either one sends the write to the ByHost plist, a different file
        # from the global one, so the scope is part of the key's identity.
        per_host = False
        while tokens and tokens[0] in ("-currentHost", "-host"):
            per_host = True
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
        calls.append(
            {
                "line": lineno,
                "verb": verb,
                "domain": domain,
                "key": key,
                "per_host": per_host,
                "value": parse_value(tokens) if verb == "write" else OPAQUE,
                "malformed": malformed,
            }
        )
    return calls


def collect_binaries(globs: tuple[str, ...] = BINARY_GLOBS) -> list[Path]:
    """Resolve the binary globs to existing, non-empty, non-metadata files."""
    found = []
    for pattern in globs:
        for hit in glob.glob(pattern):
            path = Path(hit)
            if path.suffix in EXCLUDED_SUFFIXES:
                continue
            if path.is_file() and path.stat().st_size:
                found.append(path)
    return sorted(set(found))


def keys_in_binary(path: Path, keys: set[str]) -> set[str]:
    """Return the keys stored as a standalone string inside `path`.

    `-arch all` is not cosmetic. System binaries are universal, and cctools
    `strings` otherwise reads only the slice matching the host architecture of
    its parent process. Run from an x86_64 Python under Rosetta it would read
    the x86_64 slice, which holds a fraction of the strings: SystemUIServer
    yields 21 kB that way against 39 kB for arm64e, and `dontAutoLoad` is only
    in the latter. That silently turns live keys into dead ones.
    """
    found: set[str] = set()
    try:
        process = subprocess.Popen(
            ["/usr/bin/strings", "-a", "-arch", "all", str(path)],
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


def in_menubar_scope(domain: str, per_host: bool, key: str) -> bool:
    """Whether a (domain, per-host, key) triplet holds menu bar state."""
    for candidate, scoped, keys in MENUBAR_DOMAINS:
        if candidate == domain and scoped == per_host:
            return keys is None or key in keys
    return False


def read_domain(
    domain: str, per_host: bool, keys: frozenset[str] | None
) -> dict[str, object]:
    """Read a preference domain into a plain dict, dropping the bookkeeping.

    `defaults export` is used rather than `defaults read`, because `read`
    prints the old NeXT plain-text format, which loses the distinction between
    the boolean `true` and the string "true". Exported XML keeps the types the
    comparison depends on.

    A missing domain is not an error here: a fresh account has never written
    most of these, and an empty dict is the honest answer.
    """
    command = ["defaults"]
    if per_host:
        command.append("-currentHost")
    command += ["export", domain, "-"]
    try:
        raw = subprocess.run(command, capture_output=True, check=False).stdout
    except OSError:
        return {}
    try:
        data = plistlib.loads(raw)
    except (ValueError, plistlib.InvalidFileException):
        return {}
    if not isinstance(data, dict):
        return {}
    # Data blobs are keyed archives and serialised registries. They are state,
    # never something the script would set, and their bytes differ every run.
    return {
        key: value
        for key, value in data.items()
        if (keys is None or key in keys)
        and not MENUBAR_NOISE_RE.search(key)
        and not isinstance(value, bytes)
    }


def format_value(value: object) -> str:
    """Render a plist value for the report, as the literal it would be set to."""
    if value is OPAQUE:
        return "_not compared_"
    if isinstance(value, bool):
        return "`true`" if value else "`false`"
    return f"`{value}`"


def menubar_report(script: Path, scan: bool) -> tuple[list[str], bool]:
    """Diff the menu bar the script declares against the one macOS stores.

    Returns the report lines and whether the two agree.
    """
    declared: dict[tuple[str, bool, str], dict] = {}
    removed: dict[tuple[str, bool, str], dict] = {}
    for call in parse_defaults_calls(script):
        if call["malformed"] or not call["key"]:
            continue
        scope = (normalize_domain(call["domain"]), call["per_host"], call["key"])
        if not in_menubar_scope(*scope):
            continue
        # The last invocation wins, exactly as it would when the script runs. A
        # delete is a declaration too, of a key that should not be there, so it
        # is held onto rather than dropped: that is what makes the removal of a
        # dead key verifiable instead of merely attempted.
        if call["verb"] == "delete":
            declared.pop(scope, None)
            removed[scope] = call
        else:
            removed.pop(scope, None)
            declared[scope] = call

    live: dict[tuple[str, bool, str], object] = {}
    for domain, per_host, keys in MENUBAR_DOMAINS:
        for key, value in read_domain(domain, per_host, keys).items():
            live[(domain, per_host, key)] = value

    drift, undeclared, unapplied, synced = [], [], [], []
    for scope, call in sorted(declared.items()):
        if scope not in live:
            unapplied.append((scope, call))
        elif call["value"] is OPAQUE or call["value"] == live[scope]:
            synced.append((scope, call))
        else:
            drift.append((scope, call, live[scope]))
    for scope in sorted(live):
        if scope not in declared and scope not in removed:
            undeclared.append((scope, live[scope]))
    stale = [(scope, call) for scope, call in sorted(removed.items()) if scope in live]

    def scope_label(scope: tuple[str, bool, str]) -> str:
        domain, per_host, key = scope
        return f"`{domain}`{' (per-host)' if per_host else ''} | `{key}`"

    lines = [f"# Menu bar audit of {script.name}", ""]
    lines.append(
        f"{len(declared)} keys declared, {len(removed)} declared gone, "
        f"{len(live)} stored by macOS: {len(drift)} in conflict, "
        f"{len(unapplied)} never applied, {len(stale)} not cleaned up, "
        f"{len(undeclared)} unmanaged, {len(synced)} in sync."
    )
    lines.append("")

    lines.append(f"## Conflicting: {len(drift)}")
    lines.append("")
    lines.append(
        "The script and the running system disagree. Either the system was "
        "changed in the UI and the change belongs in the script, or the script "
        "was edited and has not been run since."
    )
    lines.append("")
    lines.append("| Line | Domain | Key | Declared | Stored |")
    lines.append("| ---: | :--- | :--- | :--- | :--- |")
    for scope, call, current in drift:
        lines.append(
            f"| {call['line']} | {scope_label(scope)} | "
            f"{format_value(call['value'])} | {format_value(current)} |"
        )
    lines.append("")

    lines.append(f"## Declared but never applied: {len(unapplied)}")
    lines.append("")
    lines.append(
        "The script sets these and macOS stores nothing under them. Expected "
        "before the first run. Afterwards it means the write was rejected, "
        "which is how a dead key looks from here."
    )
    lines.append("")
    lines.append("| Line | Domain | Key | Declared |")
    lines.append("| ---: | :--- | :--- | :--- |")
    for scope, call in unapplied:
        lines.append(
            f"| {call['line']} | {scope_label(scope)} | {format_value(call['value'])} |"
        )
    lines.append("")

    lines.append(f"## Declared gone but still stored: {len(stale)}")
    lines.append("")
    lines.append(
        "The script deletes these and macOS still holds them. Expected before "
        "the first run, a failed delete afterwards."
    )
    lines.append("")
    lines.append("| Line | Domain | Key | Stored |")
    lines.append("| ---: | :--- | :--- | :--- |")
    for scope, call in stale:
        lines.append(
            f"| {call['line']} | {scope_label(scope)} | {format_value(live[scope])} |"
        )
    lines.append("")

    lines.append(f"## Stored but unmanaged: {len(undeclared)}")
    lines.append("")
    lines.append(
        "This machine carries settings the script would not reproduce. Copy "
        "the ones worth keeping into the Menubar section."
    )
    lines.append("")
    lines.append("| Domain | Key | Stored |")
    lines.append("| :--- | :--- | :--- |")
    for scope, current in undeclared:
        lines.append(f"| {scope_label(scope)} | {format_value(current)} |")
    lines.append("")

    if scan:
        seen = {scope[2] for scope in set(declared) | set(live)}
        composed = {key for key in seen if COMPOSED_KEY_RE.match(key)}
        probes = seen - composed
        binaries = collect_binaries(MENUBAR_BINARY_GLOBS)
        hits = scan_keys(probes, binaries)
        orphans = sorted(key for key in probes if not hits.get(key))
        lines.append(f"## Carried by no menu bar process: {len(orphans)}")
        lines.append("")
        lines.append(
            f"Scanned {len(binaries)} binaries for {len(probes)} keys, skipping "
            f"{len(composed)} that AppKit assembles at runtime. A key no menu "
            "bar process names is one macOS still stores and nothing reads, the "
            "shape left behind when a module is retired."
        )
        lines.append("")
        lines.append(
            "Absence proves far less than presence here, so confirm in System "
            "Settings before pruning. `Show24Hour` is the worked example: it "
            "governs a clock that visibly reads 24-hour time, and it is in no "
            "string table on this machine."
        )
        lines.append("")
        lines.append(
            "A presence is not proof either, since the match is on the key name "
            "alone and says nothing about which domain it belongs to. Control "
            "Center's retired `Spotlight` module code stays off this list only "
            "because Spotlight's own domain uses the same word."
        )
        lines.append("")
        for key in orphans:
            lines.append(f"- `{key}`")
        lines.append("")

    return lines, not (drift or unapplied or stale)


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
    parser.add_argument(
        "--menubar",
        action="store_true",
        help="Diff the declared menu bar against the live one (macOS only). "
        "Exits non-zero while they disagree.",
    )
    args = parser.parse_args()

    if args.menubar:
        lines, agreed = menubar_report(args.script, args.scan)
        emit("\n".join(lines))
        return 0 if agreed else 1

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
