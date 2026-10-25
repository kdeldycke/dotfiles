#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Grade speaker turns against the cues of the source, before naming the speakers.

A second with exactly one `speaker` cue, and no `room` cue, is taken as speech of that
speaker. The first table gives, for each speaker, the share of those seconds that
falls in a turn, the share of the most frequent tag, and how many tags hold 90% of
them: one tag per person is the goal.

The second table spreads the seconds of each tag over what the cues show then: a
speaker, the room under one owner, the room without an owner. A tag whose seconds
split between two columns may mix two voices; a room tag that speaks mostly under one
owner is likely that owner.

The script imports `build_transcript.py`, which must stay in the same folder.
"""

from __future__ import annotations

import argparse
import bisect
from collections import Counter, defaultdict
from pathlib import Path

from build_transcript import load_cues, load_speakers


def tag_at(time: float, segments: list[dict], starts: list[float]) -> str | None:
    """Return the tag of the turn that holds `time`, if any."""
    position = bisect.bisect_right(starts, time)
    for segment in reversed(segments[max(0, position - 12) : position]):
        if segment["start"] <= time <= segment["end"]:
            return str(segment["speaker"])
    return None


def covering(counts: Counter[str], share: float) -> int:
    """Return how many of the largest counts it takes to reach `share` of the total."""
    running, needed = 0, 0
    for _, count in counts.most_common():
        running += count
        needed += 1
        if running >= share * counts.total():
            break
    return needed


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--speakers",
        type=Path,
        action="append",
        required=True,
        help="Speaker turns, as for build_transcript.py. Repeat it.",
    )
    parser.add_argument(
        "--cues", type=Path, required=True, help="Cue file, as for build_transcript.py."
    )
    args = parser.parse_args()

    segments = load_speakers(args.speakers)
    starts = [segment["start"] for segment in segments]
    cues = load_cues(args.cues)
    truth: dict[str, Counter[str]] = defaultdict(Counter)
    alone: Counter[str] = Counter()
    table: dict[str, Counter[str]] = defaultdict(Counter)
    for second in cues.seconds:
        rooms = cues.room.get(second, [])
        people = sorted(set(cues.speaker.get(second, [])))
        tag = tag_at(second + 0.5, segments, starts)
        if len(people) == 1 and not rooms:
            column = people[0]
            alone[column] += 1
            if tag:
                truth[column][tag] += 1
        elif rooms and not people:
            shown = cues.owner.get(second, [])
            column = f"room, owner {shown[0]}" if shown else "room, no owner"
        elif rooms:
            column = "room and speaker"
        elif people:
            column = "several speakers"
        else:
            column = "no cue"
        if tag:
            table[tag][column] += 1

    print(f"{len({s['speaker'] for s in segments})} tags in all.\n")
    print("| Speaker | Seconds alone | In a turn | Top tag | Tags for 90% |")
    print("| :-- | --: | --: | :-- | --: |")
    for person, seconds in alone.most_common():
        counts = truth[person]
        if not counts:
            print(f"| {person} | {seconds} | 0% | - | - |")
            continue
        top, top_seconds = counts.most_common(1)[0]
        print(
            f"| {person} | {seconds} | {100 * counts.total() / seconds:.0f}% "
            f"| {top} ({100 * top_seconds / counts.total():.0f}%) "
            f"| {covering(counts, 0.9)} |"
        )

    speakers = [person for person, _ in alone.most_common()]
    rooms = sorted({
        c for counts in table.values() for c in counts if c.startswith("room, ")
    })
    others = [
        c
        for c in ("room and speaker", "several speakers", "no cue")
        if any(c in t for t in table.values())
    ]
    columns = speakers + rooms + others
    print("\n| Tag | " + " | ".join(columns) + " |")
    print("| :-- |" + " --: |" * len(columns))
    for tag in sorted(table, key=lambda tag: -table[tag].total()):
        cells = " | ".join(str(table[tag][column]) for column in columns)
        print(f"| {tag} | {cells} |")


if __name__ == "__main__":
    main()
