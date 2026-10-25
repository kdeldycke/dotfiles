#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Merge timed words, speaker turns and source cues into a named transcript.

- The words come from `wordvote.py vote`: one entry per word, with its times, its
  votes and what each model had in its place.
- The speaker turns come from `diarize_pyannote.py`, whose tags like `S03` hold for the
  whole recording, or from MOSS and `diarize.py`, whose tags restart in each window,
  like `W03-S01`. A later `--speakers` file replaces the turns of the earlier files
  over the span that it covers.
- The cues come from a script in `sources/`, like `sources/teams.py` for the video of
  a Teams call, in the format of `references/cues.md`. A tag takes the name of a
  `speaker` cue that covers most of its speech. Among the tags heard under a `room`
  cue, the tag that speaks most under one `owner` cue in its window takes the name of
  that owner, marked as probable. A tag without a window counts only its seconds
  with an owner, because it also speaks when no owner is shown. Every other tag keeps
  an anonymous label.

The script writes a Markdown transcript, SRT and VTT subtitles, a table of the
doubtful words with what each model heard, and a table of the anonymous voices with
times to listen to. `--rename` gives a name to a voice that a person recognized there.
"""

from __future__ import annotations

import argparse
import bisect
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from languages import LANGUAGES

FINAL = (".", "?", "!", "…")
"""Marks that end a sentence."""

MIN_SHARE = 0.6
"""Share of a tag's seconds that one cue must hold to give the tag its name."""


@dataclass
class Cues:
    """The names that each kind of cue shows at each second."""

    speaker: dict[int, list[str]] = field(default_factory=dict)
    """A named person speaks."""

    room: dict[int, list[str]] = field(default_factory=dict)
    """A shared microphone speaks, with several voices that the cue does not name."""

    owner: dict[int, list[str]] = field(default_factory=dict)
    """A named person presents, like the owner of the slides on screen."""

    seconds: range = range(0)
    """The seconds that the source covers."""


def clock(seconds: float, separator: str = ",") -> str:
    millis = round(seconds * 1000)
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def cell(text: str) -> str:
    """Escape the text for a Markdown table cell."""
    return text.replace("|", "\\|")


def window_of(tag: str) -> str:
    """Return the window number of a tag like `W03-S01`, or nothing."""
    head, _, rest = tag.partition("-")
    return head.lstrip("W") if rest else ""


def load_speakers(paths: list[Path]) -> list[dict]:
    """Read the turns: a later file replaces the earlier turns over its own span."""
    segments: list[dict] = []
    for path in paths:
        data = json.loads(path.read_text(encoding="UTF-8"))
        found = [s for s in data["segments"] if s.get("speaker")]
        if not found:
            print(f"WARNING: {path} holds no speaker turn.")
            continue
        low = min(s["start"] for s in found)
        high = max(s["end"] for s in found)
        segments = [s for s in segments if s["end"] <= low or s["start"] >= high]
        segments += found
    return sorted(segments, key=lambda s: s["start"])


def load_cues(path: Path | None) -> Cues:
    """Read a cue file, in the format of `references/cues.md`."""
    cues = Cues()
    if path is None:
        return cues
    data = json.loads(path.read_text(encoding="UTF-8"))
    cues.seconds = range(math.floor(data["start"]), math.ceil(data["end"]))
    for span in data["spans"]:
        if span["kind"] not in {"speaker", "room", "owner"}:
            raise SystemExit(f"{path}: unknown cue kind {span['kind']!r}.")
        shown: dict[int, list[str]] = getattr(cues, span["kind"])
        for second in range(math.floor(span["start"]), math.ceil(span["end"])):
            shown.setdefault(second, []).append(span["name"])
    return cues


def name_tags(
    segments: list[dict], cues: Cues, labels: dict[str, str]
) -> tuple[dict[str, str], set[str]]:
    """Name each speaker tag, and return the anonymous labels apart."""
    speakers: dict[str, Counter[str]] = defaultdict(Counter)
    in_room: Counter[str] = Counter()
    owners: dict[str, Counter[str]] = defaultdict(Counter)
    for segment in segments:
        tag = segment["speaker"]
        for second in range(int(segment["start"]), int(segment["end"]) + 1):
            for _ in cues.room.get(second, []):
                in_room[tag] += 1
                # An empty key counts the seconds without a named owner.
                owners[tag][next(iter(cues.owner.get(second, [])), "")] += 1
            for name in cues.speaker.get(second, []):
                speakers[tag][name] += 1
    names: dict[str, str] = {}
    for tag, counts in speakers.items():
        best, seconds = counts.most_common(1)[0]
        if seconds >= MIN_SHARE * (counts.total() + in_room[tag]):
            names[tag] = best

    by_window: dict[str, list[str]] = defaultdict(list)
    for tag in sorted({segment["speaker"] for segment in segments}):
        if tag not in names:
            by_window[window_of(tag)].append(tag)
    if cues.room:
        anonymous = f"{labels['room']}, {labels['voice']}"
    else:
        anonymous = labels["speaker"]
    unnamed: set[str] = set()
    for window, members in sorted(by_window.items()):
        # In each window, the room tag that speaks most under one owner takes the
        # name of that owner.
        claims: dict[str, tuple[int, str]] = {}
        for tag in members:
            shown = Counter({person: n for person, n in owners[tag].items() if person})
            if not shown:
                continue
            person, seconds = shown.most_common(1)[0]
            base = owners[tag].total() if window else shown.total()
            strong = seconds >= MIN_SHARE * base
            if strong and seconds > claims.get(person, (0, ""))[0]:
                claims[person] = (seconds, tag)
        for person, (_, tag) in claims.items():
            names[tag] = f"{person} ({labels['probable']})"
        rest = [tag for tag in members if tag not in names]
        for number, tag in enumerate(rest, start=1):
            label = f"{window}.{number}" if window else str(number)
            names[tag] = f"{anonymous} {label}"
            unnamed.add(names[tag])
    return names, unnamed


def speaker_at(time: float, segments: list[dict], starts: list[float]) -> str | None:
    """Return the tag of the turn at `time`, or of the nearest turn within 1 s."""
    position = bisect.bisect_right(starts, time)
    best, gap = None, 1.0
    for segment in segments[max(0, position - 8) : position + 2]:
        if segment["start"] <= time <= segment["end"]:
            return str(segment["speaker"])
        distance = min(abs(time - segment["start"]), abs(time - segment["end"]))
        if distance < gap:
            best, gap = str(segment["speaker"]), distance
    return best


def smooth(timed: list[list]) -> None:
    """Move one or two words across a speaker change to complete their sentence.

    A speaker change inside a sentence is more often an alignment slip than a real
    interruption: the words that end the sentence go back to the speaker who started
    it, and the words that open a new sentence go to the speaker who goes on with it.
    """
    for i in range(1, len(timed)):
        before, after = timed[i - 1][3], timed[i][3]
        if before == after or timed[i - 1][2].endswith(FINAL):
            continue
        for j in range(i, min(i + 2, len(timed))):
            if timed[j][3] != after:
                break
            if timed[j][2].endswith(FINAL) and timed[j][1] - timed[i][0] < 1.5:
                for k in range(i, j + 1):
                    timed[k][3] = before
                break
    for i in range(1, len(timed)):
        before, after = timed[i - 1][3], timed[i][3]
        if before == after:
            continue
        for back in (1, 2):
            p = i - 1 - back
            if p < 0 or timed[p][3] != before or not timed[p][2].endswith(FINAL):
                continue
            short = timed[i - 1][1] - timed[p + 1][0] < 1.5
            if short and not timed[i - 1][2].endswith(FINAL):
                for k in range(p + 1, i):
                    timed[k][3] = after
            break


def capitalize(text: str) -> str:
    """Put the first letter of the text in upper case."""
    index = next((i for i, char in enumerate(text) if char.isalpha()), None)
    if index is None:
        return text
    return text[:index] + text[index].upper() + text[index + 1 :]


def emphasize(tokens: list[tuple[str, bool]]) -> str:
    """Write the words, with each run of doubtful words in italics."""
    parts: list[str] = []
    run: list[str] = []
    for text, unsure in tokens + [("", False)]:
        if unsure:
            run.append(text)
            continue
        if run:
            parts.append(f"*{' '.join(run)}*")
            run = []
        if text:
            parts.append(text)
    return " ".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--words", type=Path, required=True, help="wordvote.py JSON.")
    parser.add_argument(
        "--speakers",
        type=Path,
        action="append",
        default=[],
        help="Speaker turns from MOSS or diarize.py. Repeat it: a later file wins.",
    )
    parser.add_argument(
        "--cues", type=Path, help="Cue file from a script in sources/, like teams.py."
    )
    parser.add_argument(
        "--language",
        choices=sorted(LANGUAGES),
        required=True,
        help="Code of the language, an entry of languages.py: it gives the labels.",
    )
    parser.add_argument(
        "--doubt", type=int, default=2, help="Mark words with this many votes or fewer."
    )
    parser.add_argument("--header", type=Path, help="Markdown to put first.")
    parser.add_argument(
        "--rename", type=Path, help="JSON map of labels to names, found by ear."
    )
    parser.add_argument(
        "--out", type=Path, required=True, help="Path of the outputs, no extension."
    )
    args = parser.parse_args()
    labels = LANGUAGES[args.language].labels

    entries = json.loads(args.words.read_text(encoding="UTF-8"))["aligned_words"]
    segments = load_speakers(args.speakers)
    source_cues = load_cues(args.cues)
    names, unnamed = name_tags(segments, source_cues, labels)
    if args.rename:
        renames = json.loads(args.rename.read_text(encoding="UTF-8"))
        names = {tag: renames.get(label, label) for tag, label in names.items()}
        unnamed -= set(renames)
    starts = [segment["start"] for segment in segments]

    def from_cues(second: int) -> str:
        """Name a word without a speaker turn from the speaker cue at that second."""
        lit = sorted(set(source_cues.speaker.get(second, [])))
        if len(lit) == 1:
            return lit[0]
        return labels["room"] if source_cues.room else labels["unknown"]

    timed = []
    for entry in entries:
        tag = speaker_at(entry["start"] + 0.1, segments, starts)
        name = names[tag] if tag in names else from_cues(int(entry["start"]))
        timed.append([entry["start"], entry["end"], entry["text"], name])
    smooth(timed)
    doubtful = [
        entry.get("of", 0) >= 3 and entry.get("support", 0) <= args.doubt
        for entry in entries
    ]

    cues: list[dict] = []
    for (start, end, text, name), unsure in zip(timed, doubtful):
        last = cues[-1] if cues else None
        if (
            last
            and last["name"] == name
            and start - last["end"] < 2.0
            and end - last["start"] < 20.0
        ):
            last["tokens"].append((text, unsure))
            last["end"] = end
        else:
            cues.append({
                "start": start,
                "end": end,
                "name": name,
                "tokens": [(text, unsure)],
            })
    for cue in cues:
        first, unsure = cue["tokens"][0]
        cue["tokens"][0] = (capitalize(first), unsure)
        cue["text"] = " ".join(text for text, _ in cue["tokens"])

    stem = str(args.out)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    srt = [
        f"{index}\n{clock(c['start'])} --> {clock(c['end'])}\n"
        f"{c['name']}{labels['colon']} {c['text']}\n"
        for index, c in enumerate(cues, start=1)
    ]
    Path(f"{stem}.srt").write_text("\n".join(srt), encoding="UTF-8")
    vtt = ["WEBVTT\n"] + [
        f"{clock(c['start'], '.')} --> {clock(c['end'], '.')}\n<v {c['name']}>"
        f"{c['text']}\n"
        for c in cues
    ]
    Path(f"{stem}.vtt").write_text("\n".join(vtt), encoding="UTF-8")

    turns: list[tuple[str, float, list[tuple[str, bool]]]] = []
    for cue in cues:
        if not turns or turns[-1][0] != cue["name"]:
            turns.append((cue["name"], cue["start"], []))
        turns[-1][2].extend(cue["tokens"])
    body = "\n\n".join(
        f"**{name}** ({clock(start)[:8]})\\\n{emphasize(tokens)}"
        for name, start, tokens in turns
    )
    header = ""
    if args.header:
        header = args.header.read_text(encoding="UTF-8").rstrip() + "\n\n"
    Path(f"{stem}.md").write_text(header + body + "\n", encoding="UTF-8")

    spans: list[list[int]] = []
    for index, unsure in enumerate(doubtful):
        if not unsure:
            continue
        if spans and index - spans[-1][-1] <= 2:
            spans[-1].append(index)
        else:
            spans.append([index])
    has_votes = bool(entries) and entries[0].get("of", 0) >= 3
    models = list(entries[0].get("alternatives", {})) if has_votes else []
    if models:
        rows = [
            "# Doubtful words: what each model heard",
            "",
            "The voted text is in the third column, with the doubtful words in bold.",
            "",
            "| Time | Speaker | Voted text | " + " | ".join(models) + " |",
            "| :-- | :-- | :-- |" + " :-- |" * len(models),
        ]
        for span in spans:
            first_index, last_index = span[0], span[-1]
            around = range(max(0, first_index - 2), min(len(entries), last_index + 3))
            voted = " ".join(
                f"**{entries[i]['text']}**" if doubtful[i] else entries[i]["text"]
                for i in around
            )
            heard = []
            for model in models:
                pieces = [
                    entries[i]["alternatives"].get(model, "")
                    for i in range(first_index, last_index + 1)
                ]
                heard.append(
                    " ".join(piece for piece in pieces if piece) or "(nothing)"
                )
            rows.append(
                f"| {clock(timed[first_index][0])[:8]} | {timed[first_index][3]} | "
                + " | ".join(cell(text) for text in [voted, *heard])
                + " |"
            )
        doubt_file = Path(f"{stem}, {labels['doubtful']}.md")
        doubt_file.write_text("\n".join(rows) + "\n", encoding="UTF-8")

    voices: dict[str, list[dict]] = defaultdict(list)
    for cue in cues:
        if cue["name"] in unnamed:
            voices[cue["name"]].append(cue)
    lines = [
        "# Anonymous voices, with times to listen to",
        "",
        "| Voice | Seconds | Listen at | Words heard |",
        "| :-- | --: | :-- | :-- |",
    ]
    talk = {
        name: sum(c["end"] - c["start"] for c in items)
        for name, items in voices.items()
    }
    for name in sorted(voices, key=lambda voice: -talk[voice]):
        if talk[name] < 10:
            continue
        longest = sorted(voices[name], key=lambda c: c["start"] - c["end"])[:2]
        longest.sort(key=lambda c: c["start"])
        listen = ", ".join(clock(c["start"])[:8] for c in longest)
        said = " / ".join(" ".join(c["text"].split()[:12]) + " ..." for c in longest)
        lines.append(f"| {name} | {talk[name]:.0f} | {listen} | {cell(said)} |")
    voices_file = Path(f"{stem}, {labels['voices']}.md")
    voices_file.write_text("\n".join(lines) + "\n", encoding="UTF-8")

    seconds: Counter[str] = Counter()
    for cue in cues:
        seconds[cue["name"]] += round(cue["end"] - cue["start"])
    print(
        f"{len(cues)} subtitles, {len(turns)} turns, {len(spans)} doubtful spans, "
        f"{sum(doubtful)} doubtful words"
    )
    print(
        "seconds per speaker: "
        + ", ".join(f"{n}: {s}" for n, s in seconds.most_common())
    )


if __name__ == "__main__":
    main()
