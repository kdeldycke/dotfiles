"""Find speaker turns with NVIDIA's Nemotron 3 diarizer, the fallback for MOSS.

Run this file with the Python that Nativ bundles, outside the Bash sandbox. Nemotron
runs at about 380 times real time but has 8 speaker slots: over a long recording with
more voices it mixes people. Use it on one window of about 10 minutes, where MOSS gave
no speaker labels, and give the window's start as `--offset`.
"""

from __future__ import annotations

import argparse
import json
import wave
from pathlib import Path

import numpy as np
from mlx_audio.vad import load as load_vad

DIARIZER = "mlx-community/Nemotron-3-Diarization"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--audio", type=Path, required=True, help="Mono 16 kHz WAV of the window."
    )
    parser.add_argument(
        "--offset",
        type=float,
        default=0.0,
        help="Start of the window in the recording, in seconds.",
    )
    parser.add_argument(
        "--tag", default="D", help="Prefix of the speaker tags, like W03."
    )
    parser.add_argument("--out", type=Path, required=True, help="JSON with `segments`.")
    args = parser.parse_args()

    with wave.open(str(args.audio), "rb") as handle:
        audio = (
            np.frombuffer(
                handle.readframes(handle.getnframes()), dtype=np.int16
            ).astype(np.float32)
            / 32768.0
        )
    result = load_vad(DIARIZER).generate(
        audio, 16000, threshold=0.5, min_duration=0.3, merge_gap=0.5
    )
    segments = [
        {
            "start": args.offset + float(s.start),
            "end": args.offset + float(s.end),
            "speaker": f"{args.tag}-D{s.speaker + 1}",
        }
        for s in result.segments
    ]
    args.out.write_text(json.dumps({"segments": segments}, indent=1), encoding="UTF-8")
    talk: dict[str, float] = {}
    for s in segments:
        talk[s["speaker"]] = talk.get(s["speaker"], 0.0) + s["end"] - s["start"]
    seconds = ", ".join(f"{tag}: {round(value)}" for tag, value in sorted(talk.items()))
    print(f"{len(segments)} segments; seconds per speaker: {seconds}")


if __name__ == "__main__":
    main()
