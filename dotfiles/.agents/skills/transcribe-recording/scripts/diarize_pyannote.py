#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10,<3.14"
# dependencies = ["pyannote.audio==4.0.7"]
# ///
"""Find speaker turns over a whole recording with pyannote community-1.

The pipeline clusters the voices over the whole file, so one voice keeps one tag, like
`S03`, from start to end. MOSS restarts its tags in each 10-minute window.

Run it outside the Bash sandbox: it uses the GPU through the MPS backend of PyTorch
and writes to the Hugging Face cache. The model is gated: accept its conditions once
on its page, then log in with `hf auth login`:

    https://huggingface.co/pyannote/speaker-diarization-community-1

The output holds the exclusive turns (one speaker at a time, for the transcript) as
`segments`, and the turns with overlaps as `overlapping`.
"""

from __future__ import annotations

import argparse
import json
import time
import wave
from pathlib import Path

import numpy as np
import torch
from pyannote.audio import Pipeline

PIPELINE = "pyannote/speaker-diarization-community-1"


def turns(annotation) -> list[dict]:
    """Return the turns of a pyannote annotation, with tags like `S03`."""
    return [
        {
            "start": round(segment.start, 3),
            "end": round(segment.end, 3),
            "speaker": "S" + label.rsplit("_", 1)[-1],
        }
        for segment, _, label in annotation.itertracks(yield_label=True)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--audio", type=Path, required=True, help="Mono 16 kHz WAV.")
    parser.add_argument("--out", type=Path, required=True, help="JSON with `segments`.")
    args = parser.parse_args()

    with wave.open(str(args.audio), "rb") as handle:
        rate = handle.getframerate()
        frames = handle.readframes(handle.getnframes())
    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    started = time.perf_counter()
    pipeline = Pipeline.from_pretrained(PIPELINE)
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    pipeline.to(device)
    loaded = time.perf_counter()
    print(f"loaded in {loaded - started:.0f} s on {device}", flush=True)
    output = pipeline({
        "waveform": torch.from_numpy(audio).unsqueeze(0),
        "sample_rate": rate,
    })
    finished = time.perf_counter()
    seconds = len(audio) / rate
    exclusive = turns(output.exclusive_speaker_diarization)
    report = {
        "pipeline": PIPELINE,
        "device": str(device),
        "audio_seconds": seconds,
        "run_seconds": round(finished - loaded, 1),
        "speed_x_realtime": round(seconds / max(finished - loaded, 1e-6), 1),
        "segments": exclusive,
        "overlapping": turns(output.speaker_diarization),
    }
    args.out.write_text(json.dumps(report, indent=1), encoding="UTF-8")
    talk: dict[str, float] = {}
    for turn in exclusive:
        speaker = turn["speaker"]
        talk[speaker] = talk.get(speaker, 0.0) + turn["end"] - turn["start"]
    print(
        f"{len(exclusive)} turns, {len(talk)} speakers, "
        f"{report['speed_x_realtime']}x real time"
    )
    for speaker, total in sorted(talk.items(), key=lambda item: -item[1]):
        print(f"   {speaker}: {total / 60:.1f} min")


if __name__ == "__main__":
    main()
