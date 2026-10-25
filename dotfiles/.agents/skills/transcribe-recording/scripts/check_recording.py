#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Check a recording before transcription: damage, long silences, end of speech.

A recording recovered from a truncated archive can keep its declared length while its
tail holds silence or undecodable data. A model fed that tail invents text. This
script decodes the audio stream window by window, lists the long silences and finds
where speech ends; `--cut` then writes the mono 16 kHz WAV that the models read.

Needs `ffmpeg` and `ffprobe` on the path.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


def clock(seconds: float) -> str:
    seconds = int(seconds)
    return f"{seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def ffmpeg(*arguments: str) -> str:
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", *arguments],
        capture_output=True,
        text=True,
        encoding="UTF-8",
        errors="replace",
        check=False,
    )
    return result.stderr


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("media", type=Path, help="Audio or video file.")
    parser.add_argument(
        "--window", type=int, default=300, help="Seconds per decoding check."
    )
    parser.add_argument("--silence-db", type=int, default=-55)
    parser.add_argument("--silence-seconds", type=int, default=20)
    parser.add_argument(
        "--json", type=Path, help="Write the findings here, for wordvote.py."
    )
    parser.add_argument(
        "--cut", type=Path, help="Write a mono 16 kHz WAV of the speech part here."
    )
    args = parser.parse_args()

    probe = json.loads(
        subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries",
                "format=duration:stream=codec_type,codec_name,sample_rate,channels",
                "-of", "json", str(args.media),
            ],
            capture_output=True,
            text=True,
            encoding="UTF-8",
            check=True,
        ).stdout
    )  # fmt: skip
    duration = float(probe["format"]["duration"])
    print(
        f"declared length {clock(duration)}; streams: "
        + ", ".join(f"{s['codec_type']} {s['codec_name']}" for s in probe["streams"])
    )

    windows = []
    decodable_end = 0.0
    print("\n| Window | Bad packets | Decoded s | RMS dB |\n| :-- | --: | --: | --: |")
    for start in range(0, int(duration) + 1, args.window):
        log = ffmpeg(
            "-loglevel", "info", "-ss", str(start), "-t", str(args.window),
            "-i", str(args.media), "-map", "0:a:0",
            "-af", "astats=measure_perchannel=none", "-f", "null", "-",
        )  # fmt: skip
        bad = len(re.findall(r"Error submitting|Invalid data|Reserved bit", log))
        samples = re.search(r"Number of samples: (\d+)", log)
        rms = re.search(r"RMS level dB: (-?[\w.]+)", log)
        rate = next(
            (
                int(s["sample_rate"])
                for s in probe["streams"]
                if s["codec_type"] == "audio"
            ),
            16000,
        )
        decoded = int(samples.group(1)) / rate if samples else 0.0
        level = rms.group(1) if rms else "n/a"
        windows.append({
            "start": start,
            "bad_packets": bad,
            "decoded_seconds": decoded,
            "rms_db": level,
        })
        if decoded > 1:
            decodable_end = start + decoded
        print(f"| {clock(start)} | {bad} | {decoded:.0f} | {level} |")

    log = ffmpeg(
        "-loglevel", "info", "-t", str(decodable_end), "-i", str(args.media),
        "-map", "0:a:0",
        "-af", f"silencedetect=noise={args.silence_db}dB:d={args.silence_seconds}",
        "-f", "null", "-",
    )  # fmt: skip
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", log)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
    silences = [
        [s, ends[i] if i < len(ends) else decodable_end] for i, s in enumerate(starts)
    ]
    speech_end = decodable_end
    if silences and silences[-1][1] >= decodable_end - 1:
        speech_end = silences[-1][0]
        silences = silences[:-1]
    print(f"\ndecodable audio ends at {clock(decodable_end)}")
    print(f"speech ends at {clock(speech_end)}")
    print(
        "long silences inside the speech: "
        + (", ".join(f"{clock(a)}-{clock(b)}" for a, b in silences) or "none")
    )

    if args.json:
        args.json.write_text(
            json.dumps(
                {
                    "media": str(args.media),
                    "declared_seconds": duration,
                    "decodable_seconds": decodable_end,
                    "speech_end": speech_end,
                    "silences": silences,
                    "windows": windows,
                },
                indent=1,
            ),
            encoding="UTF-8",
        )
    if args.cut:
        subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-t", f"{speech_end + 1:.1f}", "-i", str(args.media), "-map", "0:a:0",
                "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(args.cut),
            ],
            check=True,
        )  # fmt: skip
        print(f"wrote {args.cut}")


if __name__ == "__main__":
    main()
