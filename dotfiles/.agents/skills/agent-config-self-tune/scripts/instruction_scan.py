#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Size one instruction file, and find what other layers state word for word.

Two reports about `TARGET`, an instruction file with no hard wrap, where one
line holds one rule:

- The longest lines, with their line number and their size in characters. The
  longest lines are the largest rules, and a procedure among them is the first
  candidate for the Extract verdict.
- With one or more `LAYER` arguments, each line of `TARGET` that holds a
  sentence found verbatim in a layer file, with the files that hold it. Such a
  sentence is a candidate for the Drop verdict.

A `LAYER` is a file or a directory. A directory inside a git work tree gives
its tracked files. Any other directory gives every file under it, apart from
the `.git`, `__pycache__`, `node_modules` and `venv` folders. `--suffix`
selects the files of a directory by extension.

Each run of whitespace counts as one space on both sides of the comparison, so
a sentence that a layer wraps over two lines still matches.

Example:

    instruction_scan.py ~/.claude/CLAUDE.md ~/code/garden ~/code/kitchen
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

# How many of the longest lines the first report prints.
DEFAULT_LONGEST = 20

# The shortest sentence the second report compares, in words.
DEFAULT_MIN_WORDS = 8

# File extensions read in a layer directory, unless --suffix names others.
DEFAULT_SUFFIXES = (".md", ".py", ".toml", ".yaml")

# How many characters of a line each report row prints.
HEAD_WIDTH = 80

# How many layer files each duplicated line names.
MAX_HOMES = 4

# A list marker or a quote marker at the start of a line.
LINE_MARKER = re.compile(r"^(?:[-*+>]|\d+\.)\s+")

# A sentence ends on a period, a question mark or an exclamation mark, before
# a space and the opening character of the next sentence.
SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z`*\"\[(])")

# Folders that hold no layer text when a directory is walked without git.
SKIPPED_DIRECTORIES = frozenset({".git", "__pycache__", "node_modules", "venv"})


def normalize(text: str) -> str:
    """Collapse each run of whitespace to one space."""
    return re.sub(r"\s+", " ", text).strip()


def layer_files(layer: Path, suffixes: tuple[str, ...]) -> list[Path]:
    """List the files of one layer.

    :param layer: A file, or a directory.
    :param suffixes: The extensions to keep in a directory.
    :return: The file itself, the tracked files of a directory inside a git
        work tree, or every file under any other directory.
    """
    if layer.is_file():
        return [layer]
    # The -z option has no long form: it stops git from quoting a path.
    listing = subprocess.run(
        ["git", "-C", str(layer), "ls-files", "-z"],
        capture_output=True,
        check=False,
    )
    if listing.returncode == 0:
        names = listing.stdout.decode("UTF-8").split("\0")
        candidates = [layer / name for name in names if name]
    else:
        candidates = [
            path
            for path in layer.rglob("*")
            if not SKIPPED_DIRECTORIES.intersection(path.relative_to(layer).parts)
        ]
    return sorted(
        path for path in candidates if path.suffix in suffixes and path.is_file()
    )


def read_layers(
    layers: list[Path], suffixes: tuple[str, ...], target: Path
) -> dict[Path, str]:
    """Read the normalized text of each layer file, apart from the target.

    :param layers: The files and directories that hold the other layers.
    :param suffixes: The extensions to keep in a directory.
    :param target: The scanned file, which a layer directory can also hold.
    :return: The normalized text of each file, keyed by its path.
    """
    scanned = target.resolve()
    texts: dict[Path, str] = {}
    for layer in layers:
        for path in layer_files(layer, suffixes):
            if path.resolve() == scanned:
                continue
            content = path.read_text(encoding="UTF-8", errors="replace")
            texts[path] = normalize(content)
    return texts


def prose_lines(text: str) -> list[tuple[int, str]]:
    """Pair each prose line of a Markdown text with its line number.

    A heading, a table row and a fenced block hold no sentence to compare.
    """
    rows = []
    fenced = False
    for number, line in enumerate(text.splitlines(), start=1):
        body = line.strip()
        if body.startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if fenced or not body or body.startswith(("#", "|")):
            continue
        rows.append((number, body))
    return rows


def sentences(body: str, min_words: int) -> list[str]:
    """Split one prose line into the sentences long enough to compare."""
    parts = SENTENCE_END.split(LINE_MARKER.sub("", body))
    return [
        sentence
        for sentence in map(normalize, parts)
        if len(sentence.split()) >= min_words
    ]


def report_longest(lines: list[str], count: int) -> None:
    """Print the longest lines of the file, largest first."""
    ranked = sorted(
        ((len(line), number) for number, line in enumerate(lines, start=1)),
        reverse=True,
    )
    print(f"Longest lines, of {len(lines)}:")
    for size, number in ranked[:count]:
        print(f"  L{number} {size} chars: {lines[number - 1][:HEAD_WIDTH]}")


def report_duplicates(text: str, layers: dict[Path, str], min_words: int) -> None:
    """Print each line that holds a sentence a layer file states verbatim."""
    rows = []
    for number, body in prose_lines(text):
        homes: dict[Path, int] = {}
        duplicated = 0
        for sentence in sentences(body, min_words):
            holders = [path for path, layer in layers.items() if sentence in layer]
            if holders:
                duplicated += len(sentence)
            for path in holders:
                homes[path] = homes.get(path, 0) + len(sentence)
        if duplicated:
            rows.append((duplicated, number, len(body), homes, body[:HEAD_WIDTH]))
    rows.sort(key=lambda row: (row[0], row[1]), reverse=True)
    print(f"\nSentences that one of {len(layers)} layer files states verbatim:")
    for duplicated, number, size, homes, head in rows:
        print(f"  L{number} {duplicated} of {size} chars: {head}")
        largest = sorted(homes.items(), key=lambda home: home[1], reverse=True)
        for path, held in largest[:MAX_HOMES]:
            print(f"      {held} chars in {path}")
    total = sum(row[0] for row in rows)
    print(f"  {len(rows)} lines, {total} chars in all.")


def main() -> None:
    """Parse the command line and print the reports."""
    parser = argparse.ArgumentParser(
        description="Size one instruction file, and find what other layers state.",
    )
    parser.add_argument("target", type=Path, help="The instruction file to scan.")
    parser.add_argument(
        "layers",
        type=Path,
        nargs="*",
        help="Files or directories that hold the other layers.",
    )
    parser.add_argument(
        "--longest",
        type=int,
        default=DEFAULT_LONGEST,
        metavar="COUNT",
        help=f"How many of the longest lines to print. Default: {DEFAULT_LONGEST}.",
    )
    parser.add_argument(
        "--min-words",
        type=int,
        default=DEFAULT_MIN_WORDS,
        metavar="COUNT",
        help=f"The shortest sentence to compare. Default: {DEFAULT_MIN_WORDS} words.",
    )
    parser.add_argument(
        "--suffix",
        action="append",
        metavar="EXTENSION",
        help="An extension to read in a layer directory, repeatable. "
        f"Default: {', '.join(DEFAULT_SUFFIXES)}.",
    )
    args = parser.parse_args()
    for path in (args.target, *args.layers):
        if not path.exists():
            parser.error(f"{path} does not exist.")
    text = args.target.read_text(encoding="UTF-8")
    report_longest(text.splitlines(), args.longest)
    if args.layers:
        suffixes = tuple(args.suffix or DEFAULT_SUFFIXES)
        layers = read_layers(args.layers, suffixes, args.target)
        report_duplicates(text, layers, args.min_words)


if __name__ == "__main__":
    main()
