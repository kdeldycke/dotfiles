#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["num2words", "rapidfuzz"]
# ///
"""Compare and combine the transcriptions that several models made of one recording.

A pivot model with word times (Whisper or Parakeet) gives the time line. Every other
model's word sequence is aligned to the pivot's with an edit-distance alignment, so
each of its words lands on a pivot position. The models then vote word by word.

Subcommands:

- `agreement`: score each model against the vote of all the others (leave one out),
  count words per 10-minute block, repetition loops, words in silence, and how often
  the model writes the marker of the language, like `ne` in French, which speech
  mostly drops.
- `vote`: write the voted text as readable words with times. Where the majority
  agrees with the pivot, the pivot's written word stays, with its case and
  punctuation; elsewhere the word is rebuilt from the vote. Each word records its
  support and what every model had in its place.

The normalization follows the entry of `languages.py` that `--language` names: it
spells numbers out with `num2words`, splits words at apostrophes and hyphens, and
drops hesitation words.
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from languages import LANGUAGES, Language
from num2words import num2words
from rapidfuzz.distance import Levenshtein

TRAILING = re.compile(r"[\s.,;:!?…»\")\]]+$")


def normalize(text: str, language: Language) -> list[str]:
    """Lowercase, spell numbers out, split at apostrophes and hyphens, drop fillers."""
    text = text.lower().replace("’", "'").replace("œ", "oe")
    text = re.sub(r"(\d+)\s*%", lambda m: f"{m.group(1)} {language.percent}", text)
    text = re.sub(
        r"\d+",
        lambda m: " " + num2words(int(m.group(0)), lang=language.code) + " ",
        text,
    )
    return [t for t in re.findall(r"[a-zà-öø-ÿ]+", text) if t not in language.fillers]


def content(tokens: list[str], language: Language) -> list[str]:
    """Drop discourse words, and collapse a word or a pair said twice."""
    result: list[str] = []
    for token in tokens:
        if token in language.discourse or (result and result[-1] == token):
            continue
        if len(result) >= 3 and result[-3:-1] == [result[-1], token]:
            result.pop()
            continue
        result.append(token)
    return result


def load_runs(folder: Path) -> dict[str, dict]:
    runs = {}
    for path in sorted(folder.glob("*.json")):
        data = json.loads(path.read_text(encoding="UTF-8"))
        runs[data["name"]] = data
    return runs


def run_tokens(run: dict, language: Language) -> list[str]:
    return normalize(" ".join(segment["text"] for segment in run["segments"]), language)


def pivot_words(run: dict) -> list[dict]:
    """Return the pivot's written words, joining pieces without a leading space.

    Whisper can split a word at its apostrophe, like the French `c'est` into ` c` and
    `'est`: a piece that does not start with a space belongs to the word before it.
    """
    words: list[dict] = []
    for piece in run["words"]:
        if not piece["text"].strip():
            continue
        if words and not piece["text"].startswith(" "):
            words[-1]["text"] += piece["text"]
            words[-1]["end"] = piece["end"]
        else:
            words.append(dict(piece))
    return words


def pivot_tokens(
    run: dict, language: Language
) -> tuple[list[str], list[float], list[int]]:
    """Return the pivot's tokens, their start times, and the word of each token."""
    tokens, times, owners = [], [], []
    for index, word in enumerate(pivot_words(run)):
        for token in normalize(word["text"], language):
            tokens.append(token)
            times.append(float(word["start"]))
            owners.append(index)
    return tokens, times, owners


def align(
    pivot: list[str], other: list[str]
) -> tuple[dict[int, str], dict[int, list[str]]]:
    """Map each pivot position to the other model's word, and collect its insertions."""
    matched: dict[int, str] = {}
    inserted: dict[int, list[str]] = defaultdict(list)
    for tag, i1, i2, j1, j2 in Levenshtein.opcodes(pivot, other):
        if tag in {"equal", "replace"}:
            for k in range(min(i2 - i1, j2 - j1)):
                matched[i1 + k] = other[j1 + k]
            if j2 - j1 > i2 - i1:
                inserted[i2 - 1].extend(other[j1 + (i2 - i1) : j2])
        elif tag == "insert":
            inserted[i1 - 1].extend(other[j1:j2])
    return matched, inserted


def vote(
    pivot: list[str], times: list[float], others: dict[str, list[str]]
) -> list[dict]:
    """Return the voted tokens: one vote per model at each pivot position."""
    alignments = {name: align(pivot, tokens) for name, tokens in others.items()}
    voters = len(others) + 1
    result: list[dict] = []
    for index, token in enumerate(pivot):
        votes: Counter[str | None] = Counter({token: 1})
        for matched, _ in alignments.values():
            votes[matched.get(index)] += 1
        winner, count = votes.most_common(1)[0]
        if winner is not None:
            result.append({"time": times[index], "token": winner, "support": count})
        slots: Counter = Counter()
        for _, inserted in alignments.values():
            for word in dict.fromkeys(inserted.get(index, [])):
                slots[word] += 1
        for word, count in slots.items():
            if count > voters / 2:
                result.append({"time": times[index], "token": word, "support": count})
    return result


def longest_loop(tokens: list[str], size: int = 4) -> int:
    """Return how many times in a row the most repeated group of `size` words occurs."""
    best = 1
    for offset in range(size):
        grams = [
            tuple(tokens[i : i + size])
            for i in range(offset, len(tokens) - size + 1, size)
        ]
        run = 1
        for previous, current in itertools.pairwise(grams):
            run = run + 1 if current == previous else 1
            best = max(best, run)
    return best


def words_in_silence(run: dict, silences: list[list[float]]) -> float:
    """Count the words a model places in silent stretches, weighted by overlap."""
    total = 0.0
    for segment in run["segments"]:
        start, end = segment.get("start"), segment.get("end")
        if start is None or end is None or end <= start:
            continue
        overlap = sum(max(0.0, min(end, b) - max(start, a)) for a, b in silences)
        total += len(segment["text"].split()) * overlap / (end - start)
    return total


def agreement(args: argparse.Namespace) -> None:
    language = LANGUAGES[args.language]
    marker = language.marker
    runs = load_runs(args.runs)
    tokens = {name: run_tokens(run, language) for name, run in runs.items()}
    first, second = args.pivots.split(",")
    timed = {name: pivot_tokens(runs[name], language)[:2] for name in (first, second)}
    silences = (
        json.loads(args.recording.read_text(encoding="UTF-8"))["silences"]
        if args.recording
        else []
    )

    rows = []
    for name, run in runs.items():
        pivot_name = first if name != first else second
        pivot, times = timed[pivot_name]
        others = {o: tokens[o] for o in runs if o not in {name, pivot_name}}
        reference = [item["token"] for item in vote(pivot, times, others)]
        all_words = (
            100 * Levenshtein.distance(reference, tokens[name]) / max(1, len(reference))
        )
        content_ref = content(reference, language)
        content_words = (
            100
            * Levenshtein.distance(content_ref, content(tokens[name], language))
            / max(1, len(content_ref))
        )
        marked = None
        if marker:
            raw = Counter(
                re.findall(
                    r"[a-zà-öø-ÿ']+",
                    " "
                    .join(s["text"] for s in run["segments"])
                    .lower()
                    .replace("’", "'"),
                )
            )
            found = raw[marker.word] + sum(
                c for w, c in raw.items() if w.startswith(marker.elided)
            )
            marked = 100 * found / max(1, raw[marker.base])
        rows.append((
            content_words,
            name,
            all_words,
            run["speed_x_realtime"],
            run["peak_memory_gib"],
            words_in_silence(run, silences) if silences else None,
            longest_loop(tokens[name]),
            marked,
        ))
    header = (
        "| Model | Agreement WER, all / content | Speed, times real time | Peak GiB"
        " | Words in silence | Longest loop |"
    )
    if marker:
        header += f" `{marker.word}` per 100 `{marker.base}` |"
    print(header)
    print("| :-- | --: | --: | --: | --: | --: |" + (" --: |" if marker else ""))
    for row in sorted(rows):
        content_words, name, all_words, speed, peak, silent, loop, marked = row
        silent_cell = f"{silent:.0f}" if silent is not None else "-"
        line = (
            f"| {name} | {all_words:.1f} / {content_words:.1f} | {speed:.1f}"
            f" | {peak} | {silent_cell} | {loop} |"
        )
        if marked is not None:
            line += f" {marked:.0f} |"
        print(line)

    pivot, times = timed[first]
    blocks = sorted({int(t // 600) for t in times})
    counts: dict[str, Counter] = {}
    for name in runs:
        per_block: Counter = Counter()
        if name == first:
            for t in times:
                per_block[int(t // 600)] += 1
        else:
            matched, inserted = align(pivot, tokens[name])
            for index in matched:
                per_block[int(times[index] // 600)] += 1
            for index, extra in inserted.items():
                per_block[int(times[max(index, 0)] // 600)] += len(extra)
        counts[name] = per_block
    print("\n10-minute blocks where the word count of a model is 25% off the median:")
    flagged = False
    for block in blocks:
        values = sorted(counts[n][block] for n in runs)
        median = values[len(values) // 2]
        for name in runs:
            value = counts[name][block]
            if median and abs(value - median) > 0.25 * median:
                flagged = True
                span = f"{block * 10}-{block * 10 + 10}"
                print(f"   {name}: {value} words in minutes {span}, median {median}")
    if not flagged:
        print("   none")


def casing(path: Path | None) -> dict[str, str]:
    """Map the lowercase form of each dictionary word to its written form."""
    forms: dict[str, str] = {}
    if path is None:
        return forms
    for line in path.read_text(encoding="UTF-8").splitlines()[1:]:
        for word in line.split("\t")[0].split():
            if word.lower() != word:
                forms[word.lower()] = word
    return forms


def rebuild(
    tokens: list[str], template: str, forms: dict[str, str], language: Language
) -> str:
    """Write voted tokens as text, with the template's case and punctuation."""
    pattern, replacement = language.apostrophe
    text = pattern.sub(replacement, " ".join(forms.get(t, t) for t in tokens))
    stripped = template.strip()
    if stripped[:1].isupper() and text:
        text = text[0].upper() + text[1:]
    tail = TRAILING.search(stripped)
    return text + (tail.group(0).strip() if tail else "")


def readable_vote(args: argparse.Namespace) -> None:
    language = LANGUAGES[args.language]
    runs = load_runs(args.runs)
    forms = casing(args.dictionary)
    replacements: dict[str, str] = {}
    if args.replacements:
        found = json.loads(args.replacements.read_text(encoding="UTF-8"))
        replacements = {key.lower(): value for key, value in found.items()}
    words = pivot_words(runs[args.pivot])
    pivot, _, owners = pivot_tokens(runs[args.pivot], language)
    voters = [name for name in args.voters.split(",") if name]
    alignments = {
        name: align(pivot, run_tokens(runs[name], language)) for name in voters
    }
    total = len(voters) + 1

    winners: list[tuple[str | None, int]] = []
    seen_per_position: list[dict[str, str | None]] = []
    insertions: dict[int, list[tuple[str, int]]] = defaultdict(list)
    for index, token in enumerate(pivot):
        votes: Counter[str | None] = Counter({token: 1})
        seen: dict[str, str | None] = {args.pivot: token}
        for name in voters:
            matched, _ = alignments[name]
            votes[matched.get(index)] += 1
            seen[name] = matched.get(index)
        winners.append(votes.most_common(1)[0])
        seen_per_position.append(seen)
        slots: Counter = Counter()
        for name in voters:
            for extra in dict.fromkeys(alignments[name][1].get(index, [])):
                slots[extra] += 1
        for extra, count in slots.items():
            if count > total / 2:
                insertions[index].append((extra, count))

    by_word: dict[int, list[int]] = defaultdict(list)
    for position, index in enumerate(owners):
        by_word[index].append(position)
    output, changed = [], 0
    for index, word in enumerate(words):
        positions = by_word.get(index, [])
        original = [pivot[p] for p in positions]
        voted = [winners[p][0] for p in positions]
        support = min((winners[p][1] for p in positions), default=total)
        if not positions or voted == original:
            text = word["text"].strip()
        else:
            changed += 1
            kept = [t for t in voted if t is not None]
            tail = TRAILING.search(word["text"].strip())
            text = (
                rebuild(kept, word["text"], forms, language)
                if kept
                else (tail.group(0).strip() if tail else "")
            )
        added = [e for p in positions for e, _ in insertions.get(p, [])]
        if added:
            tail = TRAILING.search(text)
            core = text[: tail.start()] if tail else text
            text = (core + " " + rebuild(added, "x", forms, language)).strip() + (
                tail.group(0).strip() if tail else ""
            )
            support = min(
                [support] + [c for p in positions for _, c in insertions.get(p, [])]
            )
        if not text:
            continue
        tail = TRAILING.search(text)
        core = text[: tail.start()] if tail else text
        if core.lower() in replacements:
            text = replacements[core.lower()] + text[len(core) :]
        output.append({
            "start": word["start"],
            "end": word["end"],
            "text": text,
            "support": support,
            "of": total,
            "alternatives": {
                name: " ".join(
                    t for p in positions if (t := seen_per_position[p][name])
                )
                for name in [args.pivot] + voters
            },
        })
    args.out.write_text(
        json.dumps({"aligned_words": output}, ensure_ascii=False, indent=1),
        encoding="UTF-8",
    )
    spread = Counter(w["support"] for w in output)
    print(
        f"{len(output)} words, {changed} rewritten from the vote; support: "
        + ", ".join(f"{k}/{total}: {v}" for k, v in sorted(spread.items()))
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(required=True)
    a = commands.add_parser(
        "agreement", help="Score each model against the vote of the others."
    )
    a.add_argument(
        "--runs",
        type=Path,
        required=True,
        help="Folder of run JSON files from run_model.py.",
    )
    a.add_argument(
        "--pivots",
        default="whisper_large_v3,parakeet_v3",
        help="Two runs with word times.",
    )
    a.add_argument(
        "--recording", type=Path, help="JSON from check_recording.py, for the silences."
    )
    a.set_defaults(run=agreement)
    v = commands.add_parser(
        "vote", help="Write the voted text as readable timed words."
    )
    v.add_argument("--runs", type=Path, required=True)
    v.add_argument("--pivot", default="whisper_large_v3")
    v.add_argument(
        "--voters", default="canary_1b_v2,cohere_transcribe,parakeet_v3,moss"
    )
    v.add_argument(
        "--dictionary", type=Path, help="dictionary.tsv, for the written form of terms."
    )
    v.add_argument(
        "--replacements", type=Path, help="JSON map of known misspellings to terms."
    )
    v.add_argument("--out", type=Path, required=True)
    v.set_defaults(run=readable_vote)
    for command in (a, v):
        command.add_argument(
            "--language",
            choices=sorted(LANGUAGES),
            required=True,
            help="Code of the language, an entry of languages.py.",
        )
    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
