"""Give a time to each word of a run that has none, with the Qwen3 forced aligner.

Run this file with the Python that Nativ bundles, outside the Bash sandbox. Canary,
Cohere, Granite and Qwen3-ASR give times per block only: once aligned, such a run can
be the pivot of `wordvote.py`. The script adds `words` to the run JSON, in place unless
`--out` names another file. Give it the WAV that the run was made from.

The aligner takes at most 5 minutes of audio per call, so each segment of the run is
aligned on its own stretch of audio. It drops punctuation and hyphens and keeps one
item per whitespace token that holds a letter or a digit: the script walks the
original tokens in step with the items, so the written form survives.
"""

from __future__ import annotations

import argparse
import json
import time
import wave
from pathlib import Path

import numpy as np
from languages import LANGUAGES
from mlx_audio.stt.utils import load as load_stt

ALIGNER = "mlx-community/Qwen3-ForcedAligner-0.6B-bf16"

SAMPLE_RATE = 16000


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as handle:
        frames = handle.readframes(handle.getnframes())
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--run", type=Path, required=True, help="run_model.py JSON.")
    parser.add_argument("--audio", type=Path, required=True, help="WAV of the run.")
    parser.add_argument(
        "--language",
        choices=sorted(LANGUAGES),
        required=True,
        help="Code of the language, an entry of languages.py.",
    )
    parser.add_argument("--out", type=Path, help="Run JSON to write, if not --run.")
    args = parser.parse_args()

    run = json.loads(args.run.read_text(encoding="UTF-8"))
    audio = read_wav(args.audio)
    aligner = load_stt(ALIGNER)
    # The aligner takes the name of the language, not its code.
    language = LANGUAGES[args.language].name
    started = time.perf_counter()
    words: list[dict] = []
    for index, segment in enumerate(run["segments"]):
        text = segment["text"].strip()
        first = max(0, int(segment["start"] * SAMPLE_RATE))
        last = min(len(audio), int(segment["end"] * SAMPLE_RATE))
        if not text or last - first < SAMPLE_RATE // 2:
            continue
        result = aligner.generate(audio[first:last], text=text, language=language)
        items = list((result[0] if isinstance(result, list) else result).items)
        position = 0
        for token in text.split():
            if not aligner.aligner_processor.clean_token(token):
                # A token without a letter or a digit joins the word before it.
                if words and words[-1]["segment"] == index:
                    words[-1]["text"] += " " + token
                continue
            if position >= len(items):
                break
            item = items[position]
            position += 1
            words.append({
                "segment": index,
                "text": token,
                "start": segment["start"] + float(item.start_time),
                "end": segment["start"] + float(item.end_time),
            })
        if (index + 1) % 50 == 0:
            elapsed = time.perf_counter() - started
            print(
                f"[{elapsed:6.0f} s] {index + 1}/{len(run['segments'])} segments",
                flush=True,
            )
    # A leading space marks the start of each word, as in the words of Whisper.
    run["words"] = [
        {"start": word["start"], "end": word["end"], "text": " " + word["text"]}
        for word in words
    ]
    (args.out or args.run).write_text(
        json.dumps(run, ensure_ascii=False, indent=1), encoding="UTF-8"
    )
    elapsed = time.perf_counter() - started
    print(f"aligned {len(words)} words in {elapsed:.0f} s", flush=True)


if __name__ == "__main__":
    main()
