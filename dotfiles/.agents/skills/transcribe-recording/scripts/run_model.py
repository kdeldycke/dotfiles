"""Transcribe a whole recording with one speech model and save its timed segments.

Run this file with the Python that Nativ bundles, outside the Bash sandbox: only that
interpreter holds mlx-audio and the model loaders, and MLX needs the GPU.

    MLX_PYTHON=/Applications/Nativ.app/Contents/Frameworks/NativServerKit.framework/Versions/A/Resources/mlx-vlm-server/python/bin/python3.12
    HF_HUB_OFFLINE=1 "$MLX_PYTHON" run_model.py --family whisper \\
        --model mlx-community/whisper-large-v3-asr-fp16 --audio audio.wav \\
        --dictionary dictionary.tsv --name whisper_large_v3 --out runs

Each family takes the audio the way it handles best. A family without its own logic
for long audio gets windows cut at the quietest moment near each boundary. The output
JSON holds `segments` (start, end, text, and a speaker tag for MOSS), `words` for the
models with word times, and the start and end of each window that this script cut.
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
import time
import wave
from pathlib import Path

import mlx.core as mx
import numpy as np
from languages import LANGUAGES, Language
from mlx_audio.stt.models.cohere_asr.vad import SpeechRun, get_backend, merge_runs
from mlx_audio.stt.models.moss_transcribe_diarize.moss_transcribe_diarize import (
    DEFAULT_PROMPT,
)
from mlx_audio.stt.utils import load as load_stt

SAMPLE_RATE = 16000

WINDOWS = {
    "moss": (600, 30),
    "canary": (25, 5),
    "granite_nar": (25, 5),
    "cohere": (30, 5),
}
"""Target window and search span, in seconds, for the families cut by this script."""


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as handle:
        if handle.getframerate() != SAMPLE_RATE or handle.getnchannels() != 1:
            raise SystemExit(
                f"{path} must be mono at {SAMPLE_RATE} Hz: convert it with ffmpeg."
            )
        frames = handle.readframes(handle.getnframes())
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0


def windows(audio: np.ndarray, target: float, search: float) -> list[tuple[int, int]]:
    """Split the audio near every `target` seconds, at the quietest 0.2 s nearby."""
    hop = int(0.2 * SAMPLE_RATE)
    frames = len(audio) // hop
    energy = np.sqrt(
        np.mean(audio[: frames * hop].reshape(frames, hop) ** 2, axis=1) + 1e-12
    )
    total = len(audio) / SAMPLE_RATE
    cuts = [0]
    position = target
    while position < total - 0.3 * target:
        low = max(int((position - search) / 0.2), cuts[-1] // hop + 1)
        high = min(int((position + search) / 0.2), frames - 1)
        if high <= low:
            break
        index = low + int(np.argmin(energy[low:high]))
        cuts.append(index * hop + hop // 2)
        position = index * 0.2 + target
    cuts.append(len(audio))
    return list(itertools.pairwise(cuts))


def speech_windows(audio: np.ndarray, max_seconds: float) -> list[tuple[int, int]]:
    """Return windows of speech only, found by Silero, at most `max_seconds` long.

    Silero runs on 5-minute pieces: on a whole recording at once it exceeds the Metal
    limit on buffer count.
    """
    backend = get_backend(True)
    piece = 300 * SAMPLE_RATE
    runs = []
    for first in range(0, len(audio), piece):
        for run in backend.detect_speech(audio[first : first + piece]):
            runs.append(SpeechRun(first + run.start_sample, first + run.end_sample))
        mx.clear_cache()
    merged = merge_runs(runs, SAMPLE_RATE, merge_gap_s=1.0, max_chunk_s=max_seconds)
    return [(run.start_sample, run.end_sample) for run in merged]


LOOSE_MOSS = re.compile(
    r"\[(?P<start>\d+(?:\.\d+)?)\](?:\[(?P<speaker>S\d+)\])?(?P<text>.*?)\[(?P<end>\d+(?:\.\d+)?)\]",
    re.DOTALL,
)
"""MOSS output with optional speaker tags: the bundled parser requires the tags."""


def moss_segments(found: list[dict], log, window: int) -> list[dict]:
    """Re-parse a MOSS window that came back with timestamps but no speaker tags."""
    if len(found) != 1 or not re.search(
        r"\[\d+(?:\.\d+)?\]", str(found[0].get("text", ""))
    ):
        return found
    log(
        f"window {window}: MOSS gave no speaker labels. Rerun the window with"
        " --no-hints, or diarize it with diarize.py."
    )
    return [
        {
            "start": float(m.group("start")),
            "end": float(m.group("end")),
            "text": m.group("text").strip(),
        }
        | ({"speaker_id": m.group("speaker")} if m.group("speaker") else {})
        for m in LOOSE_MOSS.finditer(found[0]["text"])
        if m.group("text").strip()
    ]


def as_dict(item) -> dict:
    return item if isinstance(item, dict) else vars(item)


def load_terms(path: Path | None) -> tuple[list[str], list[str]]:
    """Return the names of persons and the other terms flagged as hints."""
    if path is None:
        return [], []
    names: list[str] = []
    terms: list[str] = []
    for line in path.read_text(encoding="UTF-8").splitlines()[1:]:
        fields = line.split("\t")
        if len(fields) >= 3 and fields[2] == "yes":
            (names if fields[1] == "person" else terms).append(fields[0])
    return names, terms


def whisper_prompt(
    context: str, names: list[str], terms: list[str], language: Language
) -> str | None:
    """Build Whisper's initial prompt: it reads at most 224 tokens, so keep it short."""
    people, topics = language.prompt_headings
    colon = language.labels["colon"]
    parts = [context.strip()] if context else []
    if names:
        parts.append(f"{people}{colon} {', '.join(names)}.")
    if terms:
        parts.append(f"{topics}{colon} {', '.join(terms[:30])}.")
    return " ".join(parts) or None


def transcribe(args: argparse.Namespace, model, audio: np.ndarray, log) -> dict:
    names, terms = load_terms(args.dictionary)
    hotwords = names + terms
    segments: list[dict] = []
    words: list[dict] = []
    spans: list[dict] = []
    family, language = args.family, args.language

    if family == "parakeet":
        result = model.generate(
            mx.array(audio), chunk_duration=120.0, overlap_duration=15.0
        )
        for sentence in result.sentences:
            segments.append({
                "start": sentence.start,
                "end": sentence.end,
                "text": sentence.text.strip(),
            })
            words.extend(
                {"start": t.start, "end": t.end, "text": t.text}
                for t in sentence.tokens
            )
    elif family == "whisper":
        # Conditioning on the previous window spreads a hallucination over the next
        # ones, so each 30-second window starts afresh.
        result = model.generate(
            audio,
            language=language,
            initial_prompt=whisper_prompt(
                args.context, names, terms, LANGUAGES[language]
            ),
            word_timestamps=True,
            condition_on_previous_text=False,
            verbose=False,
        )
        for segment in map(as_dict, result.segments):
            segments.append({
                "start": segment["start"],
                "end": segment["end"],
                "text": segment["text"].strip(),
            })
            for word in map(as_dict, segment.get("words") or []):
                words.append({
                    "start": word["start"],
                    "end": word["end"],
                    "text": word["word"],
                })
    elif family == "cohere" and not args.vad:
        result = model.generate(
            audio, language=language, sample_rate=SAMPLE_RATE, punctuation=True
        )
        segments = [
            {"start": s["start"], "end": s["end"], "text": s["text"].strip()}
            for s in result.segments
        ]
    elif family == "qwen3":
        # `max_tokens` bounds the whole file, not each chunk, and chunks of 20 minutes
        # stop early: 5-minute chunks and about 500 tokens per minute keep everything.
        budget = int(len(audio) / SAMPLE_RATE / 60 * 500) + 4096
        result = model.generate(
            audio,
            language=LANGUAGES[language].name,
            hotwords=hotwords or None,
            max_tokens=budget,
            chunk_duration=300.0,
        )
        segments = [
            {
                "start": as_dict(s).get("start"),
                "end": as_dict(s).get("end"),
                "text": as_dict(s)["text"].strip(),
            }
            for s in result.segments
        ]
    elif family in WINDOWS:
        target, search = WINDOWS[family]
        if family == "moss" and args.window:
            target = args.window
        cut_by_speech = args.vad and family in {"canary", "granite_nar", "cohere"}
        parts = (
            speech_windows(audio, target)
            if cut_by_speech
            else windows(audio, target, search)
        )
        for index, (first, last) in enumerate(parts):
            offset, length = first / SAMPLE_RATE, (last - first) / SAMPLE_RATE
            spans.append({"start": offset, "end": last / SAMPLE_RATE})
            chunk = audio[first:last]
            if family == "moss":
                # The `hotwords` argument replaces the default prompt and the speaker
                # labels disappear: append the words to the default prompt instead.
                prompt = (
                    f"{DEFAULT_PROMPT} Hotwords: {', '.join(hotwords)}"
                    if hotwords and not args.no_hints
                    else None
                )
                found = moss_segments(
                    [
                        as_dict(x)
                        for x in model.generate(
                            mx.array(chunk), max_tokens=16384, prompt=prompt
                        ).segments
                    ],
                    log,
                    index + 1,
                )
            elif family == "cohere":
                text = model.generate(
                    chunk, language=language, sample_rate=SAMPLE_RATE, punctuation=True
                ).text
                found = [{"start": 0.0, "end": length, "text": text}]
            elif family == "canary":
                text = model.generate(
                    mx.array(chunk),
                    source_lang=language,
                    target_lang=language,
                    use_pnc=True,
                    max_tokens=512,
                ).text
                found = [{"start": 0.0, "end": length, "text": text}]
            else:
                found = [
                    {
                        "start": 0.0,
                        "end": length,
                        "text": model.generate(mx.array(chunk)).text,
                    }
                ]
            for segment in map(as_dict, found or []):
                speaker = segment.get("speaker_id", segment.get("speaker"))
                # The MOSS parser also writes the speaker tag into the text.
                text = re.sub(
                    r"^\s*\[S\d+\]\s*", "", str(segment.get("text", ""))
                ).strip()
                entry = {
                    "start": offset + float(segment.get("start") or 0.0),
                    "end": offset + float(segment.get("end") or length),
                    "text": text,
                }
                if speaker is not None:
                    entry["speaker"] = f"{args.tag or f'W{index + 1:02d}'}-{speaker}"
                segments.append(entry)
            if family == "moss" or (index + 1) % 50 == 0:
                log(f"window {index + 1}/{len(parts)} done, at {offset / 60:.1f} min")
    else:
        raise SystemExit(f"Unknown family {family}")
    return {"segments": segments, "words": words, "windows": spans}


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--family",
        required=True,
        choices=[
            "whisper",
            "parakeet",
            "cohere",
            "canary",
            "granite_nar",
            "moss",
            "qwen3",
        ],
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Hugging Face repository name, never a snapshot path.",
    )
    parser.add_argument("--audio", type=Path, required=True, help="Mono 16 kHz WAV.")
    parser.add_argument(
        "--out", type=Path, required=True, help="Folder for the run JSON."
    )
    parser.add_argument(
        "--name", required=True, help="Run name, also the JSON file name."
    )
    parser.add_argument(
        "--language",
        choices=sorted(LANGUAGES),
        required=True,
        help="Code of the language, an entry of languages.py.",
    )
    parser.add_argument(
        "--dictionary",
        type=Path,
        help="dictionary.tsv: its hint terms go to Whisper, MOSS and Qwen3-ASR.",
    )
    parser.add_argument(
        "--context",
        default="",
        help="One sentence about the recording, for Whisper's prompt.",
    )
    parser.add_argument(
        "--vad", action="store_true", help="Feed speech only (Cohere, Canary, Granite)."
    )
    parser.add_argument(
        "--window", type=int, help="MOSS window in seconds (default 600, at most 5400)."
    )
    parser.add_argument(
        "--no-hints",
        action="store_true",
        help="MOSS default prompt, for windows that lost speaker labels.",
    )
    parser.add_argument(
        "--offset",
        type=float,
        default=0.0,
        help="Seconds to add to every time: the start of a window rerun.",
    )
    parser.add_argument("--tag", help="MOSS tag prefix for a window rerun, like W03.")
    args = parser.parse_args()

    started = time.perf_counter()

    def log(message: str) -> None:
        print(f"[{time.perf_counter() - started:7.0f} s] {message}", flush=True)

    audio = read_wav(args.audio)
    try:
        model = load_stt(args.model, strict=True)
        strict = True
    except Exception as error:  # noqa: BLE001
        # A checkpoint can carry a harmless extra tensor. Any other failure comes
        # back from the second load.
        log(f"strict load failed ({str(error)[:160]}): loading with strict=False")
        model = load_stt(args.model)
        strict = False
    loaded = time.perf_counter()
    log(f"model loaded in {loaded - started:.0f} s")
    mx.reset_peak_memory()
    output = transcribe(args, model, audio, log)
    if args.offset:
        for item in output["segments"] + output["words"] + output["windows"]:
            for key in ("start", "end"):
                if item.get(key) is not None:
                    item[key] += args.offset
    finished = time.perf_counter()
    seconds = len(audio) / SAMPLE_RATE
    report = {
        "name": args.name,
        "model": args.model,
        "family": args.family,
        "language": args.language,
        "vad": args.vad,
        "strict_load": strict,
        "hints": bool(args.dictionary)
        and args.family in {"moss", "whisper", "qwen3"}
        and not args.no_hints,
        "audio_seconds": seconds,
        "load_seconds": round(loaded - started, 1),
        "run_seconds": round(finished - loaded, 1),
        "speed_x_realtime": round(seconds / max(finished - loaded, 1e-6), 2),
        "peak_memory_gib": round(mx.get_peak_memory() / 2**30, 2),
        **output,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / f"{args.name}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="UTF-8"
    )
    count = sum(len(s["text"].split()) for s in output["segments"])
    log(
        f"done: {len(output['segments'])} segments, {count} words, "
        f"{report['speed_x_realtime']}x real time, peak {report['peak_memory_gib']} GiB"
    )
    text = " ".join(s["text"] for s in output["segments"])
    foreign = sum(
        1 for ch in text if ch.isalpha() and not re.match(r"[A-Za-zÀ-ÖØ-öø-ÿŒœ]", ch)
    )
    if count < 20 * seconds / 60:
        log(
            "WARNING: fewer than 20 words per minute: the model may have stopped early."
        )
    if foreign > 0.02 * max(1, len(text)):
        log(
            "WARNING: the output holds non-Latin letters:"
            " the weights may not match the loader."
        )


if __name__ == "__main__":
    main()
