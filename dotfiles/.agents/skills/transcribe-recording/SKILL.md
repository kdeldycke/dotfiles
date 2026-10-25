---
name: transcribe-recording
description: Transcribe a recording of speech, like a meeting, a call, a podcast or an interview, on this Mac with local open-weight models, in French or English. A word-by-word vote of five models gives the text, pyannote gives the speaker turns, and a table lists the doubtful words. The video of a Teams call can also give the names. Use it for a recording that must stay on this machine.
compatibility: 'Designed for Claude Code on an Apple Silicon Mac with Nativ, whose bundled Python holds the mlx-audio runtime, and with ffmpeg and uv. Recommended model: Opus.'
argument-hint: '[recording file] [folder of related documents]'
---

# Transcribe a recording

The process runs on this Mac only:

1. Check the recording, and cut its speech to a WAV file.
1. Build a dictionary of names and terms from the related documents.
1. Run five speech models, one at a time.
1. Find the speaker turns over the whole recording.
1. Check that the models agree.
1. Vote the text word by word.
1. Read the cues of the source, like the names that the video of a call shows.
1. Build the transcript: Markdown, SRT and VTT, a table of doubtful words, and a table of voices to name.
1. Deliver the files.

For one hour of speech, the five models take about 30 minutes, and the speaker turns about 5 more. [`references/benchmark.md`](references/benchmark.md) gives the measurements behind the choice of models, made on French speech.

## Ask first

- The recording: audio, video, or both, and its source, like a Teams call or a podcast. A source with a page in step 7 can name the speakers.
- The language of the recording, from the table of languages below.
- The speakers, when known, like the hosts and the guests of a podcast. Their names go to the dictionary and to the labels.
- A folder of related documents for the dictionary, like notes, slides, mails or show notes.
- The destination folder and the stem of the file names, like `{date} - {title}, transcription`.

Keep the recording and its text on this Mac. Do not send them to a hosted API.

## Languages

Each script that reads or writes words takes `--language {code}`. The page of the language says what changes with it: the words that the comparison leaves out, the labels of the transcript and the rules of the listening check.

| Language | Code | Page                                                       |
| :------- | :--- | :--------------------------------------------------------- |
| English  | `en` | [`references/languages/en.md`](references/languages/en.md) |
| French   | `fr` | [`references/languages/fr.md`](references/languages/fr.md) |

To add a language, add its entry to `scripts/languages.py` and its page to `references/languages/`, on the pattern of the others.

## Set up

| Placeholder      | Value                                                                                                                            |
| :--------------- | :------------------------------------------------------------------------------------------------------------------------------- |
| `{nativ python}` | `/Applications/Nativ.app/Contents/Frameworks/NativServerKit.framework/Versions/A/Resources/mlx-vlm-server/python/bin/python3.12` |
| `{skill}`        | The base directory of this skill.                                                                                                |
| `{work}`         | A folder in the session scratchpad, like `{scratchpad}/transcription`.                                                           |

- A script with a `uv` shebang runs with `uv run --script`. A script without one imports mlx-audio and runs with `{nativ python}`.
- Run each `{nativ python}` command with the Bash sandbox off: MLX fails inside it with `No Metal device available`, and the Hugging Face cache (`~/.cache/huggingface/hub`) is not writable there.
- `ffmpeg` and `ffprobe` must be on the path.

The models:

| Run name            | Family     | Repository                                | Role                                               |
| :------------------ | :--------- | :---------------------------------------- | :------------------------------------------------- |
| `whisper_large_v3`  | `whisper`  | `mlx-community/whisper-large-v3-asr-fp16` | Pivot: the written text, the word times, the hints |
| `moss`              | `moss`     | `OpenMOSS-Team/MOSS-Transcribe-Diarize`   | Voter, and fallback speaker turns                  |
| `canary_1b_v2`      | `canary`   | `CogniSoftOrg/canary-1b-v2-mlx-bf16`      | Voter                                              |
| `cohere_transcribe` | `cohere`   | `CohereLabs/cohere-transcribe-03-2026`    | Voter, gated                                       |
| `parakeet_v3`       | `parakeet` | `mlx-community/parakeet-tdt-0.6b-v3`      | Voter, and second pivot of the agreement check     |

Three helpers: `mlx-community/Qwen3-ForcedAligner-0.6B-bf16` for `align_words.py`, `mlx-community/Nemotron-3-Diarization` for `diarize.py`, and `mlx-community/silero-vad` for `run_model.py --vad`. `run_model.py` also keeps the `granite_nar` and `qwen3` families, which scored lower, for a new test.

The speaker turns come from `pyannote/speaker-diarization-community-1`, through `diarize_pyannote.py` and its own PyTorch environment. The model is gated: accept its conditions on its Hugging Face page, then run `hf auth login` once. The token that Nativ keeps in the Keychain does not reach it.

Download what the cache lacks:

```shell-session
$ {nativ python} {skill}/scripts/download_models.py {repository} {repository}
```

Cohere Transcribe is gated: accept its licence on Hugging Face first. The token is in Nativ (in the Keychain), not in the shell, so the script then asks Nativ's server to download the weights: Nativ must be open. Quit Nativ before the long runs, because its server can keep a model in memory.

## 1. Check the recording

```shell-session
$ uv run --script {skill}/scripts/check_recording.py {recording} --json {work}/recording.json --cut {work}/audio.wav
```

The table shows, for each 5-minute window, the packets that fail to decode, the seconds decoded and the level. A recording recovered from a damaged file can keep its length while its end holds silence or bad data, and a model fed that end invents text. `--cut` writes a mono 16 kHz WAV that stops 1 second after the end of speech. All the models read this WAV, and all times count from its start.

## 2. Build the dictionary

```shell-session
$ uv run --script {skill}/scripts/build_dictionary.py --root {documents} --language {code} --out {work}/dictionary
```

Read `{work}/dictionary/candidates.json`: acronyms, proper names, `Firstname LASTNAME` pairs and rare words, each with its count and number of documents. `--skip {folder name}` leaves out a folder, like copies or generated notes. Then write `{work}/dictionary/dictionary.tsv` with four tab-separated columns, after a header line:

| Column     | Content                                                       |
| :--------- | :------------------------------------------------------------ |
| `term`     | The written form, like `Lyon` or `Marie Curie`.               |
| `category` | `person`, `place`, `company`, `project`, `acronym` or `term`. |
| `hotword`  | `yes` for a term likely said aloud in the recording.          |
| `note`     | Free text, like a role or the full form of an acronym.        |

Without related documents, write the dictionary from what is known: the names of the speakers and the topics. The `yes` terms go to the models that take hints: Whisper and MOSS in their prompts, Qwen3-ASR as hotwords. Whisper reads at most 224 tokens of prompt: the script keeps all the person names and the first 30 other terms, so put the most important terms first.

## 3. Run the models

Run one model at a time: two large models at once push a 32 GiB Mac into swap. Keep the run names of the table, because the later steps use them.

```shell-session
$ HF_HUB_OFFLINE=1 {nativ python} {skill}/scripts/run_model.py --family whisper --model mlx-community/whisper-large-v3-asr-fp16 --name whisper_large_v3 --audio {work}/audio.wav --language {code} --dictionary {work}/dictionary/dictionary.tsv --context '{one sentence about the recording}' --out {work}/runs
```

For the other models, change `--family`, `--model` and `--name`. Give `--dictionary` to MOSS too: the other families take no hints. The times on an M1 Pro, for one hour of speech: Whisper 14 minutes, MOSS 9, Canary 5, Cohere 2, Parakeet 2.

After each run:

1. Read the warnings. Fewer than 20 words per minute means that the model stopped early. Letters outside the Latin script mean that the weights do not match the loader.
1. Read the first segments of the run JSON.

## 4. Find the speaker turns

```shell-session
$ PYTORCH_ENABLE_MPS_FALLBACK=1 uv run --script {skill}/scripts/diarize_pyannote.py --audio {work}/audio.wav --out {work}/turns/pyannote.json
```

Run it with the Bash sandbox off. pyannote clusters the voices over the whole recording, so one voice keeps one tag, like `S03`, from start to end: it runs at about 14 times real time. Keep its output out of `{work}/runs`, because the vote reads every file there.

Without a Hugging Face token, fall back to the turns of MOSS. Their tags restart in each 10-minute window, so one person carries several labels. MOSS can also return a window with times but no speaker labels, and the run log names that window. Rerun the window alone, without hints. Its start and end are in the `windows` list of the MOSS run, and `{window}` is its tag, like `W03`:

```shell-session
$ ffmpeg -ss {start} -to {end} -i {work}/audio.wav {work}/turns/{window}.wav
$ HF_HUB_OFFLINE=1 {nativ python} {skill}/scripts/run_model.py --family moss --model OpenMOSS-Team/MOSS-Transcribe-Diarize --name moss_{window} --audio {work}/turns/{window}.wav --language {code} --no-hints --offset {start} --tag {window} --out {work}/turns
```

When the rerun has no labels either, find the turns with Nemotron. It has 8 speaker slots and mixes people over a long stretch, so use it on one window only:

```shell-session
$ {nativ python} {skill}/scripts/diarize.py --audio {work}/turns/{window}.wav --offset {start} --tag {window} --out {work}/turns/{window}_nemotron.json
```

## 5. Check the agreement

```shell-session
$ uv run --script {skill}/scripts/wordvote.py agreement --runs {work}/runs --language {code} --recording {work}/recording.json
```

The script scores each model against the vote of the others. This measures agreement with the majority, not truth, but it covers the whole recording. Look for:

- A model far above the others: wrong weights or a wrong language.
- Words in silence: a model that invents text where nobody speaks.
- A long loop: one group of four words, repeated many times.
- A 10-minute block where a model writes 25% more or fewer words than the median: a stall, a loop or a missed stretch.

Leave a faulty model out of the vote. `--vad` feeds Canary and Cohere speech only, which stops their loops but costs about 3 points of word error rate.

## 6. Vote the text

```shell-session
$ uv run --script {skill}/scripts/wordvote.py vote --runs {work}/runs --language {code} --pivot whisper_large_v3 --voters canary_1b_v2,cohere_transcribe,parakeet_v3,moss --dictionary {work}/dictionary/dictionary.tsv --replacements {work}/replacements.json --out {work}/voted.json
```

The pivot gives the time line and the written form. Where most models agree with the pivot, its word stays as written. Elsewhere the word comes from the vote. Each word records its votes and what each model had in its place.

- `replacements.json` maps a frequent misspelling, in lowercase, to its written form, like `{"curry": "Curie"}`. Find such words in the doubtful words of a first build, then vote again.
- `--voters ''` keeps the pivot alone, with no doubtful words.
- A pivot needs word times. Whisper and Parakeet have them. For another model, add them first with `{nativ python} {skill}/scripts/align_words.py --run {run JSON} --audio {work}/audio.wav --language {code}`.
- Before the vote, the script normalizes the words of each model as the page of the language says: it spells numbers out, splits words at apostrophes and leaves out hesitations.

## 7. Read the cues of the source

Some sources show who speaks, like the video of a call. A script reads these cues into `{work}/cues.json`, in the format of [`references/cues.md`](references/cues.md). Follow the page of the source:

| Source                          | Page                                                         | Script                     |
| :------------------------------ | :----------------------------------------------------------- | :------------------------- |
| Video of a Microsoft Teams call | [`references/sources/teams.md`](references/sources/teams.md) | `scripts/sources/teams.py` |

Skip this step for a source without such cues, like a podcast. Its voices keep anonymous labels, like `Speaker 1`, until the user names them in step 8. To add a source, follow [`references/cues.md`](references/cues.md).

Then check the speaker turns against the cues:

```shell-session
$ uv run --script {skill}/scripts/check_speakers.py --speakers {work}/turns/pyannote.json --cues {work}/cues.json
```

Each speaker should fall under one tag. The second table spreads the seconds of each tag over what the cues show: a tag split between two columns may mix two voices.

## 8. Build the transcript

Fill [`assets/transcript-header.md`](assets/transcript-header.md) into `{work}/header.md`, in the language of the recording. Add the header lines of the source page, and delete each line that does not apply.

```shell-session
$ uv run --script {skill}/scripts/build_transcript.py --words {work}/voted.json --speakers {work}/turns/pyannote.json --cues {work}/cues.json --language {code} --header {work}/header.md --out {work}/final/{stem}
```

Leave out `--cues` for a recording without cues. With the turns of MOSS instead, give `--speakers {work}/runs/moss.json`, then each rerun file: a later `--speakers` file replaces the turns of the earlier files over its own span. The labels and the file names come from the page of the language. The script writes:

| File                          | Content                                                                        |
| :---------------------------- | :----------------------------------------------------------------------------- |
| `{stem}.md`                   | The transcript: one paragraph per speaker turn, the doubtful words in italics. |
| `{stem}.srt`, `{stem}.vtt`    | Subtitles of at most 20 seconds each.                                          |
| `{stem}, {doubtful words}.md` | Each doubtful stretch, with what each model heard.                             |
| `{stem}, {voices to name}.md` | Each anonymous voice, with times to listen to.                                 |

A word is doubtful when 2 or fewer of the models voted for it (`--doubt`). The voices table gives times to listen to for each anonymous voice, so that the user can name it. A probable name rests on an owner cue only: cut a few clips of that voice under other owners and in open discussion, and ask the user to confirm it by ear. When the user recognizes a voice or confirms a name, write the old and new labels to a JSON file, like `{"Speaker 1": "{name}", "{name} (probable)": "{name}"}`, and build again with `--rename {file}`.

Read the start of the transcript and the voices table before the delivery.

## 9. Deliver

1. Confirm the destination folder and the stem.
1. Make sure that no file in the destination starts with the stem: never overwrite.
1. Build again with `--out {destination}/{stem}`. A destination under ProtonDrive needs the Bash sandbox off.
1. List the written files with their sizes.

## Measure the models by ear

Do this for a new model, for a new kind of recording (a phone call, another language), or to check the choice of models. The person corrects about 6 minutes of audio.

```shell-session
$ uv run --script {skill}/scripts/review.py prepare --audio {work}/audio.wav --runs {work}/runs --language {code} --samples 0:20:00+120 1:00:00+120 1:40:00+120 --out {work}/review
```

Pick one clip of 2 minutes per listening condition, like each microphone, room or speaker that the recording holds. The `README.md` in the folder tells the person how to correct the drafts, with the rules of the language. Then:

```shell-session
$ uv run --script {skill}/scripts/review.py score --runs {work}/runs --language {code} --pivot parakeet_v3 --samples-dir {work}/review
$ uv run --script {skill}/scripts/review.py votes --runs {work}/runs --language {code} --samples-dir {work}/review --group canary_1b_v2,cohere_transcribe --group canary_1b_v2,cohere_transcribe,parakeet_v3,moss
```

A draft starts from a vote, so a draft error that the person misses counts in favour of the models of that vote: their scores are optimistic. `--voters` picks the models of the draft: draft a second set of clips from another mix, so that no vote keeps that advantage. On about 900 words, a gap under 2 points is noise.

When the person keeps a draft as it is, its clips measure the distance to that draft: the vote of the draft scores 0, and its pivot comes first. Do not rank the models on such clips.

A restart of the Mac empties the scratchpad, with the corrected drafts in it. Ask the user whether to keep a copy of them and of `samples.json` in another folder.

To test a new model without a run on the whole recording, run it on the WAV clips, with one run folder per clip. Run the current models on the clips too, to compare like with like. Without runs on the whole recording, `prepare` cuts the clips only, and `draft` writes the drafts from the clip runs:

```shell-session
$ HF_HUB_OFFLINE=1 {nativ python} {skill}/scripts/run_model.py --family {family} --model {repository} --name {run name} --audio {work}/review/{clip}.wav --language {code} --out {work}/review/clip_runs/{clip}
$ uv run --script {skill}/scripts/review.py draft --runs {work}/review/clip_runs --language {code} --samples-dir {work}/review --pivot parakeet_v3 --voters canary_1b_v2,cohere_transcribe,moss
$ uv run --script {skill}/scripts/review.py clips --runs {work}/review/clip_runs --language {code} --samples-dir {work}/review --group canary_1b_v2,cohere_transcribe,parakeet_v3,moss
```

Each model hears the same 2 minutes without the audio around them, so the rates run higher than with `score`. [`references/benchmark.md`](references/benchmark.md) lists the candidates tested this way.

## Traps

These were seen with Nativ `0.4.0` (mlx-audio `0.5.8`). Check them again after a Nativ update.

- A model whose tensor names do not match the loader loads without an error and writes garbage, because the loader falls back to `strict=False`. Read the first lines of output. The `mlx-community` conversion of Cohere Transcribe is for another library: use the `CohereLabs` weights.
- Load a model by its repository name, never by a snapshot path: the loader can read the snapshot hash as the model type.
- MOSS: the `hotwords` argument drops the speaker labels, so `run_model.py` appends the hints to the default prompt. The bundled parser also writes `[S01]` into the text, which the script removes.
- Qwen3-ASR: `max_tokens` bounds the whole file, and chunks of 20 minutes stop early. `run_model.py` uses 5-minute chunks and about 500 tokens per minute.
- Silero exceeds a Metal buffer limit on a whole recording, so `run_model.py --vad` runs it on 5-minute pieces. Cohere's own `vad=True` path fails on an `mx.array`.
- Voxtral Mini 3B needs PyTorch, which the bundle lacks; Voxtral Realtime runs in it. VibeVoice-ASR 9B returned no text for a 10-minute window, but works on 2-minute clips.
- Whisper can split a word at its apostrophe into two pieces, the second without a leading space: `wordvote.py` joins such a piece to the word before it.
- pyannote runs in PyTorch, which Nativ's Python lacks: `diarize_pyannote.py` brings its own environment through `uv`.
- A model deleted in Nativ can leave its weights in `~/.cache/huggingface/hub/blobs/`. A file there whose `.refs` sidecar lists no existing path is an orphan: move it and its sidecar to the Trash.
