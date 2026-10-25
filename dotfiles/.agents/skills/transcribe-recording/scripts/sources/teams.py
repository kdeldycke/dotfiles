#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pillow"]
# ///
"""Read the cues of the video of a Teams call, one frame per second.

Two areas of the video show who speaks:

- The participant strip: Teams draws a violet box behind the name of each person who
  speaks. The box of a meeting room account covers every voice in that room.
- The slide corner: a shared deck can show the initials of its owner in a coloured
  box.

Subcommands:

- `frame`: save one whole frame, to find the two areas and their crop boxes.
- `extract`: save the two areas of each second as PNG files, with ffmpeg.
- `scan`: find the boxes and group the boxes that show the same text. For each area,
  write a timeline, contact sheets with one example per group, and a names file to
  fill in. `P` groups come from the participant strip, `O` groups from the slide
  corner.
- `export`: write the named groups as a cue file, in the format of
  `references/cues.md`. A participant gives a `speaker` cue, a meeting room account
  (`room` or `room: …` in the names file) a `room` cue, and a slide owner an `owner`
  cue.

The thresholds suit a 1080p Teams recording. When a scan finds no box, or splits one
name into many groups, compare the sheets with a frame and adjust the thresholds.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

TYPE_CHECKING = False
if TYPE_CHECKING:
    from collections.abc import Callable

    Box = tuple[int, int, int, int]

SHEET_ROWS = 20
"""Groups per contact sheet: a taller sheet shrinks too much on screen."""

SKIP = {"?", "ignore"}
"""Values of a names file that name nobody."""


def clock(seconds: int) -> str:
    return f"{seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def crop_box(text: str) -> str:
    if not re.fullmatch(r"\d+:\d+:\d+:\d+", text):
        raise argparse.ArgumentTypeError("use W:H:X:Y in pixels, like 246:1012:1674:68")
    return text


def is_room(name: str) -> bool:
    """Tell a meeting room account, named `room` or `room: …` in a names file."""
    return name.lower().startswith("room")


def ffmpeg(*arguments: str) -> None:
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-loglevel", "error", "-y", *arguments],
        check=True,
    )


def frame(args: argparse.Namespace) -> None:
    ffmpeg("-ss", str(args.at), "-i", str(args.video), "-frames:v", "1", str(args.out))
    with Image.open(args.out) as image:
        print(f"wrote {args.out}: {image.width} x {image.height} pixels")


def extract(args: argparse.Namespace) -> None:
    areas = {
        name: crop
        for name, crop in (("strip", args.strip), ("corner", args.corner))
        if crop
    }
    if not areas:
        raise SystemExit("Give --strip, --corner or both.")
    split = "".join(f"[{name}_in]" for name in areas)
    graph = [f"[0:v]fps=1,split={len(areas)}{split}"]
    outputs = []
    for name, crop in areas.items():
        folder = args.folder / f"{name}s"
        folder.mkdir(parents=True, exist_ok=True)
        graph.append(f"[{name}_in]crop={crop}[{name}]")
        outputs += ["-map", f"[{name}]", str(folder / f"{name}_%05d.png")]
    limit = ["-t", str(args.until)] if args.until else []
    ffmpeg(*limit, "-i", str(args.video), "-filter_complex", ";".join(graph), *outputs)
    for name in areas:
        folder = args.folder / f"{name}s"
        print(f"{name}: {len(list(folder.glob('*.png')))} frames in {folder}")


def violet_boxes(pixels: np.ndarray) -> list[Box]:
    """Find the violet boxes that Teams draws behind the name of a speaker."""
    r, g, b = (pixels[..., i].astype(np.int16) for i in range(3))
    mask = (
        (np.abs(r - g) < 28)
        & (r > 70)
        & (r < 135)
        & (b > 140)
        & (b < 200)
        & (b - r > 35)
    )
    rows = mask.sum(axis=1) >= 30
    boxes = []
    y = 0
    while y < len(rows):
        if not rows[y]:
            y += 1
            continue
        y0 = y
        while y < len(rows) and rows[y]:
            y += 1
        y1 = y
        if not 18 <= y1 - y0 <= 34:
            continue
        filled = mask[y0:y1].sum(axis=0) >= (y1 - y0) * 0.4
        x = 0
        while x < len(filled):
            if not filled[x]:
                x += 1
                continue
            x0, gap = x, 0
            while x < len(filled) and gap < 6:
                gap = 0 if filled[x] else gap + 1
                x += 1
            x1 = x - gap
            white = (pixels[y0:y1, x0:x1].min(axis=2) > 170).mean()
            violet = mask[y0:y1, x0:x1].mean()
            if x1 - x0 >= 40 and violet >= 0.45 and 0.03 <= white <= 0.5:
                boxes.append((x0, y0, x1, y1))
    return boxes


def owner_box(pixels: np.ndarray) -> list[Box]:
    """Find the coloured box that holds the initials of the slide owner."""
    spread = pixels.max(axis=2).astype(np.int16) - pixels.min(axis=2)
    coloured = (spread > 60) & (pixels.max(axis=2) > 90)
    if coloured.sum() < 4000:
        return []
    keys = (
        (pixels[..., 0] // 24).astype(np.int32) * 10000
        + (pixels[..., 1] // 24).astype(np.int32) * 100
        + (pixels[..., 2] // 24).astype(np.int32)
    )
    values, counts = np.unique(keys[coloured], return_counts=True)
    mask = (keys == values[counts.argmax()]) & coloured
    rows = np.flatnonzero(mask.sum(axis=1) >= 60)
    columns = np.flatnonzero(mask.sum(axis=0) >= 30)
    if len(rows) < 40 or len(columns) < 100:
        return []
    x0, x1 = int(columns[0]), int(columns[-1]) + 1
    y0, y1 = int(rows[0]), int(rows[-1]) + 1
    if not (110 <= x1 - x0 <= 220 and 50 <= y1 - y0 <= 100):
        return []
    if mask[y0:y1, x0:x1].mean() < 0.6:
        return []
    return [(x0, y0, x1, y1)]


def trim(mask: np.ndarray) -> np.ndarray:
    """Crop a text mask to its lit pixels, so that a shift of the box does not count."""
    rows = np.flatnonzero(mask.any(axis=1))
    columns = np.flatnonzero(mask.any(axis=0))
    if not len(rows):
        return mask
    return mask[rows[0] : rows[-1] + 1, columns[0] : columns[-1] + 1]


def same_text(a: np.ndarray, b: np.ndarray, slack: int) -> bool:
    if abs(a.shape[0] - b.shape[0]) > slack or abs(a.shape[1] - b.shape[1]) > slack:
        return False
    height, width = min(a.shape[0], b.shape[0]), min(a.shape[1], b.shape[1])
    a, b = a[:height, :width], b[:height, :width]
    union = (a | b).sum()
    return bool(union > 0 and (a ^ b).sum() / union < 0.4)


def write_sheets(groups: list[dict], prefix: str, out: Path) -> None:
    """Draw one row per group: its id, its seconds on screen and an example box."""
    for old in out.glob(f"{prefix}_sheet_*.png"):
        old.unlink()
    font = ImageFont.load_default(size=18)
    for page, first in enumerate(range(0, len(groups), SHEET_ROWS), start=1):
        chunk = groups[first : first + SHEET_ROWS]
        examples = [
            g["example"].resize((g["example"].width * 2, g["example"].height * 2))
            for g in chunk
        ]
        row = max(e.height for e in examples) + 10
        sheet = Image.new(
            "RGB", (340 + max(e.width for e in examples), row * len(chunk)), "black"
        )
        draw = ImageDraw.Draw(sheet)
        for offset, (group, example) in enumerate(zip(chunk, examples)):
            top = offset * row
            sheet.paste(example, (330, top + 5))
            label = (
                f"{prefix}{first + offset:02d}  {group['seconds']} s,"
                f" from {clock(group['first'])}"
            )
            draw.text((8, top + row // 2 - 10), label, fill="white", font=font)
        sheet.save(out / f"{prefix}_sheet_{page}.png")


def scan(
    folder: Path,
    finder: Callable[[np.ndarray], list[Box]],
    white: int,
    slack: int,
    prefix: str,
    out: Path,
) -> None:
    groups: list[dict] = []
    timeline = []
    for path in sorted(folder.glob("*.png")):
        second = int(path.stem.rsplit("_", 1)[1]) - 1
        with Image.open(path) as image:
            pixels = np.asarray(image.convert("RGB"))
        found = []
        for x0, y0, x1, y1 in finder(pixels):
            mask = trim(pixels[y0:y1, x0:x1].min(axis=2) > white)
            for index, group in enumerate(groups):
                if same_text(mask, group["mask"], slack):
                    group["seconds"] += 1
                    break
            else:
                index = len(groups)
                example = pixels[max(0, y0 - 3) : y1 + 3, x0:x1].copy()
                groups.append({
                    "mask": mask,
                    "seconds": 1,
                    "first": second,
                    "example": Image.fromarray(example),
                })
            found.append(f"{prefix}{index:02d}")
        timeline.append({"second": second, "groups": found})
    (out / f"{prefix}_timeline.json").write_text(json.dumps(timeline), encoding="UTF-8")
    write_sheets(groups, prefix, out)
    ids = [f"{prefix}{index:02d}" for index in range(len(groups))]
    names = out / f"{prefix}_names.json"
    if not names.exists():
        names.write_text(
            json.dumps(dict.fromkeys(ids, "?"), indent=1), encoding="UTF-8"
        )
    elif sorted(json.loads(names.read_text(encoding="UTF-8"))) != ids:
        print(f"WARNING: {names} lists other groups than this scan: update it.")
    lit = sum(1 for entry in timeline if entry["groups"])
    print(f"{prefix}: {len(timeline)} frames, {lit} with a box, {len(groups)} groups")


def scan_all(args: argparse.Namespace) -> None:
    strips, corners = args.folder / "strips", args.folder / "corners"
    if strips.is_dir():
        scan(strips, violet_boxes, 170, 2, "P", args.folder)
    if corners.is_dir():
        scan(corners, owner_box, 185, 3, "O", args.folder)


def export(args: argparse.Namespace) -> None:
    """Merge the named seconds of each group into spans, and write the cue file."""
    spans: list[dict] = []
    seconds: list[int] = []
    for prefix in ("P", "O"):
        path = args.folder / f"{prefix}_timeline.json"
        if not path.exists():
            continue
        names = json.loads(
            (args.folder / f"{prefix}_names.json").read_text(encoding="UTF-8")
        )
        unnamed = [group for group, name in names.items() if name == "?"]
        if unnamed:
            print(f"WARNING: {prefix}_names.json leaves {len(unnamed)} groups unnamed.")
        current: dict[tuple[str, str], dict] = {}
        for entry in json.loads(path.read_text(encoding="UTF-8")):
            second = entry["second"]
            seconds.append(second)
            for group in entry["groups"]:
                name = names.get(group, "?")
                if name in SKIP:
                    continue
                if prefix == "O":
                    kind = "owner"
                else:
                    kind = "room" if is_room(name) else "speaker"
                span = current.get((kind, name))
                if span and span["end"] >= second:
                    span["end"] = second + 1
                    continue
                span = {"kind": kind, "name": name, "start": second, "end": second + 1}
                current[kind, name] = span
                spans.append(span)
    if not seconds:
        raise SystemExit(f"No timeline in {args.folder}: run scan first.")
    spans.sort(key=lambda span: span["start"])
    cues = {
        "source": "teams",
        "start": min(seconds),
        "end": max(seconds) + 1,
        "spans": spans,
    }
    args.cues.write_text(
        json.dumps(cues, ensure_ascii=False, indent=1), encoding="UTF-8"
    )
    kinds = ", ".join(
        f"{sum(1 for s in spans if s['kind'] == kind)} {kind}"
        for kind in ("speaker", "room", "owner")
    )
    print(f"wrote {args.cues}: {kinds} spans")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(required=True)
    one = commands.add_parser("frame", help="Save one whole frame.")
    one.add_argument("video", type=Path)
    one.add_argument("--at", type=float, default=600.0, help="Second of the frame.")
    one.add_argument("--out", type=Path, required=True, help="PNG file.")
    one.set_defaults(run=frame)
    cut = commands.add_parser("extract", help="Save the two areas of each second.")
    cut.add_argument("video", type=Path)
    cut.add_argument(
        "--strip", type=crop_box, help="Participant strip as W:H:X:Y in pixels."
    )
    cut.add_argument("--corner", type=crop_box, help="Slide corner as W:H:X:Y.")
    cut.add_argument("--until", type=float, help="Last second: the end of speech.")
    cut.set_defaults(run=extract)
    find = commands.add_parser("scan", help="Group the boxes, write the sheets.")
    find.set_defaults(run=scan_all)
    write = commands.add_parser("export", help="Write the named groups as cues.")
    write.add_argument("--cues", type=Path, required=True, help="Cue file to write.")
    write.set_defaults(run=export)
    for command in (cut, find, write):
        command.add_argument(
            "--folder", type=Path, required=True, help="Working folder of the cues."
        )
    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
