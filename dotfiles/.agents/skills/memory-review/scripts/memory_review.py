#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Mechanics of a memory review: inventory, batches, apply and check.

The memories live under `{root}/{project}/memory/`, one `.md` file per fact
with a YAML frontmatter, plus a `MEMORY.md` index of one line per file, in the
form `- [Title](file.md) — hook`. The default root is `~/.claude/projects`.

Subcommands:

- `inventory`: one row per memory folder, with its index and frontmatter
  issues. Exits 1 when a folder has an issue.
- `batches OUT_DIR`: writes one file list per review batch, about `--size`
  files each: one project per batch where it fits, a large project split, the
  small projects pooled.
- `apply JSON_DIR [--apply]`: reads every `apply-*.json` of the directory,
  then moves the DELETE files to the Trash and rewrites the indexes. Without
  `--apply`, it prints the plan and the problems and changes nothing.
- `check`: index consistency, `[[links]]` that resolve to no memory, lines
  that call someone "he", and empty folders. Exits 1 on an index problem.

An `apply-*.json` file holds one object, or a list of them:

    {"dir": "/abs/memory/dir",
     "delete": ["file.md"],
     "index": {"file.md": "- [Title](file.md) — new hook"}}

`dirs`, a list, replaces `dir` for a batch spanning several folders: each file
is then looked up in exactly one of them. Other keys, like `unsure` and
`outside`, are kept for the final report and ignored here.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_ROOT = Path.home() / ".claude" / "projects"
INDEX = "MEMORY.md"
INDEX_LINK = re.compile(r"\]\(([^)]+\.md)\)")
WIKI_LINK = re.compile(r"\[\[([^\]]+)\]\]")
PRONOUN = re.compile(r"\b(he|him|his|himself)\b", re.IGNORECASE)
FRONTMATTER_KEYS = ("name:", "description:", "type:")


def memory_dirs(root: Path) -> list[Path]:
    """Every `memory` folder under `root` that holds at least one file."""
    return sorted(d for d in root.glob("*/memory") if any(d.glob("*.md")))


def memory_files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.glob("*.md") if p.name != INDEX)


def index_lines(folder: Path) -> list[str]:
    index = folder / INDEX
    if not index.exists():
        return []
    return index.read_text(encoding="UTF-8").splitlines()


def linked_files(lines: list[str]) -> list[str]:
    return [m.group(1) for line in lines for m in [INDEX_LINK.search(line)] if m]


def frontmatter(path: Path) -> str | None:
    """The frontmatter block of a memory, or `None` when it has none."""
    match = re.match(r"---\n(.*?)\n---\n", path.read_text(encoding="UTF-8"), re.DOTALL)
    return match.group(1) if match else None


def frontmatter_name(path: Path) -> str | None:
    block = frontmatter(path) or ""
    match = re.search(r"^name:\s*(.+)$", block, re.MULTILINE)
    return match.group(1).strip().strip("\"'") if match else None


def folder_issues(folder: Path) -> list[str]:
    files = [p.name for p in memory_files(folder)]
    linked = linked_files(index_lines(folder))
    issues = [f"index line with no file: {f}" for f in linked if f not in files]
    issues += [f"file with no index line: {f}" for f in files if f not in linked]
    issues += [
        f"indexed twice: {f}" for f in sorted(set(linked)) if linked.count(f) > 1
    ]
    for path in memory_files(folder):
        block = frontmatter(path)
        if block is None or any(key not in block for key in FRONTMATTER_KEYS):
            issues.append(f"bad frontmatter: {path.name}")
    return issues


def project_label(folder: Path) -> str:
    """A short label for a memory folder: `-Users-kde-code-mpm` gives `mpm`."""
    name = folder.parent.name
    name = re.sub(r"^-Users-[^-]+-code-", "", name)
    return name.strip("-")[-40:] or "root"


def cmd_inventory(args: argparse.Namespace) -> int:
    failed = False
    total = 0
    for folder in memory_dirs(args.root):
        files = memory_files(folder)
        total += len(files)
        size = sum(p.stat().st_size for p in files) // 1024
        issues = folder_issues(folder)
        failed |= bool(issues)
        print(f"{len(files):4d} files {size:5d} KiB  {folder}")
        for issue in issues:
            print(f"      {issue}")
    print(f"{total} memory files")
    return 1 if failed else 0


def cmd_batches(args: argparse.Namespace) -> int:
    args.out.mkdir(parents=True, exist_ok=True)
    batches: list[tuple[str, list[Path]]] = []
    pool: list[Path] = []
    for folder in memory_dirs(args.root):
        files = memory_files(folder)
        label = project_label(folder)
        if len(files) > args.size:
            parts = -(-len(files) // args.size)
            width = -(-len(files) // parts)
            for index in range(parts):
                batches.append((
                    f"{label}-{index + 1}",
                    files[index * width : (index + 1) * width],
                ))
        elif len(files) >= args.size // 2:
            batches.append((label, files))
        else:
            pool.extend(files)
            if len(pool) >= args.size:
                batches.append(("pool", pool))
                pool = []
    if pool:
        batches.append(("pool", pool))
    for number, (label, files) in enumerate(batches, 1):
        path = args.out / f"b{number:02d}-{label}.txt"
        path.write_text("".join(f"{p}\n" for p in files), encoding="UTF-8")
        size = sum(p.stat().st_size for p in files) // 1024
        print(f"{path.name}: {len(files)} files, {size} KiB")
    print(f"{len(batches)} batches, {sum(len(f) for _, f in batches)} files")
    return 0


def entries(json_dir: Path) -> list[dict]:
    """Every entry of every apply-*.json, each with its list of folders."""
    found = []
    for path in sorted(json_dir.glob("apply-*.json")):
        data = json.loads(path.read_text(encoding="UTF-8"))
        for entry in data if isinstance(data, list) else [data]:
            dirs = entry.get("dirs") or [entry["dir"]]
            found.append({
                **entry,
                "dirs": [Path(d) for d in dirs],
                "source": path.name,
            })
    return found


def locate(dirs: list[Path], name: str) -> Path:
    """The one folder among `dirs` holding the file `name`."""
    hits = [d for d in dirs if (d / name).is_file()]
    if len(hits) != 1:
        raise LookupError(f"{name}: found in {len(hits)} of {len(dirs)} folders")
    return hits[0]


def cmd_apply(args: argparse.Namespace) -> int:
    errors: list[str] = []
    deletions: list[Path] = []
    replacements: dict[Path, dict[str, str]] = {}
    for entry in entries(args.json_dir):
        for name in entry.get("delete", []):
            try:
                deletions.append(locate(entry["dirs"], name) / name)
            except LookupError as error:
                errors.append(f"{entry['source']}: delete {error}")
        for name, line in entry.get("index", {}).items():
            try:
                folder = locate(entry["dirs"], name)
            except LookupError as error:
                errors.append(f"{entry['source']}: index {error}")
                continue
            replacements.setdefault(folder, {})[name] = line
    folders = {p.parent for p in deletions} | set(replacements)
    new_indexes: dict[Path, str] = {}
    for folder in sorted(folders):
        gone = {p.name for p in deletions if p.parent == folder}
        updates = dict(replacements.get(folder, {}))
        kept = []
        for line in index_lines(folder):
            match = INDEX_LINK.search(line)
            file = match.group(1) if match else None
            if file in gone:
                continue
            kept.append(updates.pop(file, line) if file else line)
        errors += [f"{folder / INDEX}: no line for {file}" for file in updates]
        new_indexes[folder / INDEX] = "".join(f"{line}\n" for line in kept)
    trash = shutil.which("trash") or "/usr/bin/trash"
    if deletions and not Path(trash).exists():
        errors.append("no `trash` command: move the files by hand")

    print(f"deletions: {len(deletions)}")
    for path in deletions:
        print(f"  {project_label(path.parent)}/{path.name}")
    print(f"indexes rewritten: {len(new_indexes)}")
    print(f"errors: {len(errors)}")
    for error in errors:
        print(f"  {error}")
    if not args.apply:
        return 1 if errors else 0
    if errors:
        print("refusing to apply with errors")
        return 1
    backup_root = args.json_dir / "backup"
    for index, text in new_indexes.items():
        backup = backup_root / index.parent.parent.name / INDEX
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(index.read_bytes())
        index.write_text(text, encoding="UTF-8")
    if deletions:
        subprocess.run([trash, *map(str, deletions)], check=True)
    print(f"applied; index backups under {backup_root}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    failed = False
    folders = memory_dirs(args.root)
    known = set()
    for folder in folders:
        for path in memory_files(folder):
            known.add(path.stem)
            name = frontmatter_name(path)
            if name:
                known.add(name)
    for folder in folders:
        issues = folder_issues(folder)
        failed |= bool(issues)
        for issue in issues:
            print(f"INDEX {folder}: {issue}")
    unresolved = []
    pronouns = []
    for folder in folders:
        for path in [*memory_files(folder), folder / INDEX]:
            if not path.exists():
                continue
            for number, line in enumerate(
                path.read_text(encoding="UTF-8").splitlines(), 1
            ):
                unresolved += [
                    f"{path}:{number} [[{l}]]"
                    for l in WIKI_LINK.findall(line)
                    if l not in known
                ]
                if PRONOUN.search(line):
                    pronouns.append(f"{path}:{number}: {line.strip()[:120]}")
    print(f"unresolved links: {len(unresolved)}")
    for item in unresolved:
        print(f"  {item}")
    print(f"pronoun lines: {len(pronouns)}")
    for item in pronouns:
        print(f"  {item}")
    empty = sorted(
        d for d in args.root.glob("*/memory") if d.is_dir() and not any(d.glob("*.md"))
    )
    print(f"empty folders: {len(empty)}")
    for folder in empty:
        print(f"  {folder}")
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root", type=Path, default=DEFAULT_ROOT, help="The projects root."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("inventory").set_defaults(func=cmd_inventory)
    batches = subparsers.add_parser("batches")
    batches.add_argument("out", type=Path, help="Where to write the batch lists.")
    batches.add_argument("--size", type=int, default=45, help="Files per batch.")
    batches.set_defaults(func=cmd_batches)
    apply = subparsers.add_parser("apply")
    apply.add_argument(
        "json_dir", type=Path, help="The folder of the apply-*.json files."
    )
    apply.add_argument(
        "--apply", action="store_true", help="Change the files; a plan otherwise."
    )
    apply.set_defaults(func=cmd_apply)
    subparsers.add_parser("check").set_defaults(func=cmd_check)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
