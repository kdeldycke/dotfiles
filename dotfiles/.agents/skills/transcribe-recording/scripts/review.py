#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["num2words", "rapidfuzz"]
# ///
"""Measure the models against clips that a person corrects by ear.

- `prepare`: cut clips from the audio, as M4A to listen to and as WAV for the models.
  With `--runs`, write beside each clip a draft to correct: the vote of the runs on
  the whole recording, in lowercase, one line per 15 seconds. A clip whose draft
  exists keeps it, and gets its audio again when the audio is missing. `README.md`
  gives the person the rules of the listening check, with those of the language.
- `draft`: write the draft of each clip that has none from the vote of its clip runs,
  for clips cut without runs on the whole recording.
- `score`: the word error rate of each model on the corrected clips, for all words and
  for content words, in total and per clip, from the runs on the whole recording.
- `votes`: the word error rate of the vote of each group of models.
- `clips`: the word error rate of runs made on the clip WAVs, with one folder of runs
  per clip, and with `--group` the rate of their votes. Each model hears the same
  2 minutes without the audio around them, so the rates run higher than with
  `score`. This tests a new model without a run on the whole recording.

Every subcommand takes `--language`, the code of an entry of `languages.py`. The
script imports `languages.py` and `wordvote.py`, which must stay in the same folder.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import defaultdict
from pathlib import Path

from languages import LANGUAGES, Language
from rapidfuzz.distance import Levenshtein
from wordvote import (
    align,
    content,
    load_runs,
    normalize,
    pivot_tokens,
    run_tokens,
    vote,
)

GUIDE = Path(__file__).parent.parent / "assets" / "listening-check.md"
"""Instructions for the person who corrects the drafts, without the language rules."""

LINE_SECONDS = 15
"""Seconds of audio per line of a draft."""


def clock(seconds: int) -> str:
    return f"{seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def span(text: str) -> tuple[int, int]:
    """Read `START+LENGTH` in seconds, with START in seconds or as `h:mm:ss`."""
    start, _, length = text.partition("+")
    seconds = 0
    for part in start.split(":"):
        seconds = seconds * 60 + int(part)
    return seconds, int(length or 120)


def rate(errors: int, words: int) -> str:
    return f"{100 * errors / max(1, words):.1f}"


def write_guide(folder: Path, language: Language) -> None:
    """Write the listening check as `README.md`, with the rules of the language."""
    text = GUIDE.read_text(encoding="UTF-8")
    text = text.replace("{name of the language}", language.name)
    text = text.replace("{rules of the language}", language.guide.rstrip("\n"))
    (folder / "README.md").write_text(text, encoding="UTF-8")


def voted_tokens(
    runs: dict[str, dict], pivot_name: str, voters: str | None, language: Language
) -> list[dict]:
    """Vote the pivot with the named voters, or with every other run."""
    names = voters.split(",") if voters is not None else list(runs)
    members = [name for name in names if name and name != pivot_name]
    pivot, times, _ = pivot_tokens(runs[pivot_name], language)
    others = {name: run_tokens(runs[name], language) for name in members}
    return vote(pivot, times, others)


def write_draft(
    path: Path,
    voted: list[dict],
    start: int,
    length: int,
    offset: int,
    language: Language,
) -> None:
    """Write the voted words of a clip, one line per `LINE_SECONDS` of audio.

    `offset` moves the vote's times onto the time line of the recording: 0 for runs on
    the whole recording, the start of the clip for runs on the clip alone.
    """
    pattern, replacement = language.apostrophe
    lines = []
    for first in range(start, start + length, LINE_SECONDS):
        words = [
            item["token"]
            for item in voted
            if first <= item["time"] + offset < first + LINE_SECONDS
        ]
        lines.append(f"[{clock(first)}] " + pattern.sub(replacement, " ".join(words)))
    path.write_text("\n".join(lines) + "\n", encoding="UTF-8")


def prepare(args: argparse.Namespace) -> None:
    language = LANGUAGES[args.language]
    voted = None
    if args.runs:
        voted = voted_tokens(load_runs(args.runs), args.pivot, args.voters, language)
    args.out.mkdir(parents=True, exist_ok=True)
    listing = args.out / "samples.json"
    samples = []
    if listing.exists():
        samples = json.loads(listing.read_text(encoding="UTF-8"))
    known = {sample["name"] for sample in samples}
    for start, length in args.samples:
        name = "sample_" + clock(start).replace(":", "h", 1).replace(":", "m") + "s"
        audio = [args.out / f"{name}.m4a", args.out / f"{name}.wav"]
        if not all(path.exists() for path in audio):
            subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-ss", str(start), "-t", str(length), "-i", str(args.audio),
                    "-c:a", "aac", "-b:a", "96k", str(audio[0]),
                    "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(audio[1]),
                ],
                check=True,
            )  # fmt: skip
            print(f"wrote {audio[0]} and .wav")
        text = args.out / f"{name}.txt"
        if text.exists():
            print(f"{text} exists already: kept as it is.")
        elif voted is not None:
            write_draft(text, voted, start, length, 0, language)
            print(f"wrote {text}")
        if name not in known:
            samples.append({"name": name, "start": start, "length": length})
            known.add(name)
    listing.write_text(json.dumps(samples, indent=1), encoding="UTF-8")
    write_guide(args.out, language)


def draft(args: argparse.Namespace) -> None:
    language = LANGUAGES[args.language]
    for sample in json.loads(
        (args.samples_dir / "samples.json").read_text(encoding="UTF-8")
    ):
        path = args.samples_dir / f"{sample['name']}.txt"
        if path.exists():
            print(f"{path} exists already: kept as it is.")
            continue
        runs = load_runs(args.runs / sample["name"])
        voted = voted_tokens(runs, args.pivot, args.voters, language)
        start, length = sample["start"], sample["length"]
        write_draft(path, voted, start, length, start, language)
        print(f"wrote {path}")


def read_samples(
    folder: Path, language: Language
) -> list[tuple[str, int, int, list[str]]]:
    """Return each corrected clip: its name, start, end and normalized words."""
    samples = []
    written = 0
    for sample in json.loads((folder / "samples.json").read_text(encoding="UTF-8")):
        text = (folder / f"{sample['name']}.txt").read_text(encoding="UTF-8")
        words = " ".join(line.split("] ", 1)[-1] for line in text.splitlines())
        written += len(words.split())
        end = sample["start"] + sample["length"]
        samples.append((
            sample["name"],
            sample["start"],
            end,
            normalize(words, language),
        ))
    print(f"{len(samples)} clips, {written} words as written.\n")
    return samples


def clip_words(
    name: str,
    pivot_name: str,
    pivot: list[str],
    times: list[float],
    alignments: dict[str, tuple[dict[int, str], dict[int, list[str]]]],
    start: int,
    end: int,
) -> list[str]:
    """Return the words of one model over a clip, placed on the pivot's time line."""
    indices = [index for index, time in enumerate(times) if start <= time < end]
    if not indices:
        return []
    low, high = indices[0], indices[-1]
    if name == pivot_name:
        return pivot[low : high + 1]
    matched, inserted = alignments[name]
    words: list[str] = []
    for index in range(low, high + 1):
        if index in matched:
            words.append(matched[index])
        words.extend(inserted.get(index, []))
    return words


def score(args: argparse.Namespace) -> None:
    language = LANGUAGES[args.language]
    runs = load_runs(args.runs)
    pivot, times, _ = pivot_tokens(runs[args.pivot], language)
    alignments = {
        name: align(pivot, run_tokens(run, language))
        for name, run in runs.items()
        if name != args.pivot
    }
    samples = read_samples(args.samples_dir, language)
    totals = {name: [0, 0, 0, 0] for name in runs}
    per_clip: dict[str, list[str]] = {name: [] for name in runs}
    for _, start, end, reference in samples:
        expected = content(reference, language)
        for name in runs:
            found = clip_words(name, args.pivot, pivot, times, alignments, start, end)
            errors = Levenshtein.distance(reference, found)
            totals[name][0] += errors
            totals[name][1] += len(reference)
            totals[name][2] += Levenshtein.distance(expected, content(found, language))
            totals[name][3] += len(expected)
            per_clip[name].append(rate(errors, len(reference)))
    clips = "".join(f" {name} |" for name, *_ in samples)
    print(f"| Model | WER, all words | WER, content words |{clips}")
    print("| :-- | --: | --: |" + " --: |" * len(samples))
    for name in sorted(runs, key=lambda run: totals[run][0] / max(1, totals[run][1])):
        errors, words, content_errors, content_words = totals[name]
        cells = "".join(f" {value} |" for value in per_clip[name])
        print(
            f"| {name} | {rate(errors, words)} | "
            f"{rate(content_errors, content_words)} |{cells}"
        )


def votes(args: argparse.Namespace) -> None:
    language = LANGUAGES[args.language]
    runs = load_runs(args.runs)
    pivot, times, _ = pivot_tokens(runs[args.pivot], language)
    samples = read_samples(args.samples_dir, language)
    print("| Vote | WER, all words | WER, content words |")
    print("| :-- | --: | --: |")
    for group in args.group:
        members = [name for name in group.split(",") if name and name != args.pivot]
        others = {name: run_tokens(runs[name], language) for name in members}
        voted = vote(pivot, times, others)
        errors = words = content_errors = content_words = 0
        for _, start, end, reference in samples:
            found = [item["token"] for item in voted if start <= item["time"] < end]
            expected = content(reference, language)
            errors += Levenshtein.distance(reference, found)
            words += len(reference)
            content_errors += Levenshtein.distance(expected, content(found, language))
            content_words += len(expected)
        print(
            f"| {', '.join([args.pivot, *members])} | {rate(errors, words)} | "
            f"{rate(content_errors, content_words)} |"
        )


def clips(args: argparse.Namespace) -> None:
    language = LANGUAGES[args.language]
    samples = read_samples(args.samples_dir, language)
    names = [name for name, *_ in samples]
    runs = {
        name: load_runs(args.runs / name)
        for name in names
        if (args.runs / name).is_dir()
    }
    totals: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    per_clip: dict[str, dict[str, str]] = defaultdict(dict)
    for name, _, _, reference in samples:
        expected = content(reference, language)
        for model, run in runs.get(name, {}).items():
            found = run_tokens(run, language)
            errors = Levenshtein.distance(reference, found)
            totals[model][0] += errors
            totals[model][1] += len(reference)
            totals[model][2] += Levenshtein.distance(expected, content(found, language))
            totals[model][3] += len(expected)
            per_clip[model][name] = rate(errors, len(reference))
    header = "".join(f" {name} |" for name in names)
    print(f"| Model | WER, all words | WER, content words |{header}")
    print("| :-- | --: | --: |" + " --: |" * len(names))
    for model in sorted(
        totals, key=lambda run: totals[run][0] / max(1, totals[run][1])
    ):
        errors, words, content_errors, content_words = totals[model]
        cells = "".join(f" {per_clip[model].get(name, '-')} |" for name in names)
        print(
            f"| {model} | {rate(errors, words)} | "
            f"{rate(content_errors, content_words)} |{cells}"
        )
    if not args.group:
        return
    print("\n| Vote | WER, all words | WER, content words |")
    print("| :-- | --: | --: |")
    for group in args.group:
        members = [name for name in group.split(",") if name and name != args.pivot]
        errors = words = content_errors = content_words = 0
        for name, _, _, reference in samples:
            clip = runs[name]
            pivot, times, _ = pivot_tokens(clip[args.pivot], language)
            others = {member: run_tokens(clip[member], language) for member in members}
            found = [item["token"] for item in vote(pivot, times, others)]
            expected = content(reference, language)
            errors += Levenshtein.distance(reference, found)
            words += len(reference)
            content_errors += Levenshtein.distance(expected, content(found, language))
            content_words += len(expected)
        print(
            f"| {', '.join([args.pivot, *members])} | {rate(errors, words)} | "
            f"{rate(content_errors, content_words)} |"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(required=True)
    cut = commands.add_parser("prepare", help="Cut the clips and write the drafts.")
    cut.add_argument("--audio", type=Path, required=True, help="WAV of the runs.")
    cut.add_argument(
        "--samples",
        type=span,
        nargs="+",
        required=True,
        help="Clips as START+LENGTH, like 0:20:00+120.",
    )
    cut.add_argument(
        "--runs",
        type=Path,
        help="Folder of runs on the whole recording, to draft the clips from.",
    )
    cut.set_defaults(run=prepare)
    write = commands.add_parser("draft", help="Draft the clips from their clip runs.")
    write.set_defaults(run=draft)
    for command in (cut, write):
        command.add_argument(
            "--voters",
            help="Comma-separated runs that vote with the pivot (default: all runs).",
        )
    check = commands.add_parser("score", help="Score each model on the clips.")
    check.set_defaults(run=score)
    group = commands.add_parser("votes", help="Score the vote of groups of models.")
    group.add_argument(
        "--group",
        action="append",
        required=True,
        help="Comma-separated runs that vote with the pivot. Repeat it.",
    )
    group.set_defaults(run=votes)
    alone = commands.add_parser("clips", help="Score the runs made on the clip WAVs.")
    alone.add_argument(
        "--group",
        action="append",
        help="Comma-separated clip runs that vote with the pivot. Repeat it.",
    )
    alone.set_defaults(run=clips)
    for command in (write, check, group, alone):
        command.add_argument(
            "--runs",
            type=Path,
            required=True,
            help="Run folder; for clips, a folder with one run folder per clip.",
        )
    for command in (cut, write, check, group, alone):
        command.add_argument("--pivot", default="whisper_large_v3")
        command.add_argument(
            "--language",
            choices=sorted(LANGUAGES),
            required=True,
            help="Code of the language, an entry of languages.py.",
        )
    cut.add_argument("--out", type=Path, required=True, help="Folder of the clips.")
    for command in (write, check, group, alone):
        command.add_argument("--samples-dir", type=Path, required=True)
    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
