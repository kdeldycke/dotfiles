# Model benchmark on French speech

Measured on an M1 Pro with 32 GiB, with the speech runtime that Nativ `0.4.0` bundles (mlx-audio `0.5.8`). [Revisions](#revisions) gives the weights of each model.

## Verdict

**Prime model: Whisper large-v3.** It ties for the best accuracy (8.6% word error rate, and the best result of any model in one listening condition: 4.4%). Of the three most accurate models, it is the only one that invents almost nothing in silence (one word) and never loops. It gives word times and takes the dictionary as a prompt. It runs at about 4 times real time and takes 8.3 GiB.

- **Canary 1B v2** matches its accuracy (8.5%) in a third of the time and memory. It loops on silence and noise, gives no word times and takes no hints. A speech filter stops the loops but raises its error rate to 12.3%.
- **Cohere Transcribe** is close (9.8%) and the fastest of the three (about 35 times real time). It is the least robust: it loops in silence and on short noisy stretches. It gives 30-second times only, takes no hints, and needs its gated licence accepted.
- **MOSS-Transcribe-Diarize** gives usable speaker turns, but its tags restart every 10 minutes, so **pyannote community-1** replaced it for the turns: see [Speaker turns](#speaker-turns). Like Qwen3-ASR, it writes what is spoken, such as `je suis pas`, where the other models rewrite into written French. Its error rate is higher (14.7%): use it for who spoke, not for what was said.
- **A vote of five models** (Whisper, Canary, Cohere, Parakeet, MOSS) scored 5.0% on the clips. That figure is optimistic, see below. It costs about 30 minutes of compute for one hour of speech.

## Test material

- One French recording of a meeting with several speakers, mono, 16 kHz.
- Three listening conditions, one per clip: two room microphones, and remote speakers.
- Many domain terms, like acronyms and proper names.

## Method

- **Full runs.** Each model transcribed the whole recording, alone in memory, in the mode that suits it: its own logic for long audio where it has one, otherwise windows cut at the quietest moment near each boundary.
- **Hints.** A dictionary of 117 terms came from the related documents. Its 74 terms most likely said aloud went to the models that take hints: Whisper (initial prompt), MOSS (prompt) and Qwen3-ASR (hotwords).
- **Human word error rate.** Three clips of 2 minutes, one per listening condition: 901 words, corrected by ear. Each model's words over a clip come from its alignment with the word times of Parakeet; with the times of Whisper, the figures move by 0.3 point at most. The content rate ignores `ne`, discourse words like `voilà` and `enfin`, and words said twice. On 901 words, a gap under about 2 points is noise.
- **Agreement word error rate.** Over the whole recording, each model against the word-by-word vote of all the other models, on the time line of Parakeet (of Whisper for Parakeet itself). A speech-only variant votes with the seven full runs. This rate rewards agreement with the majority, not truth, but it covers the whole recording instead of 6 minutes.
- **Words invented in silence.** The words that a model places in the stretches of 20 seconds or more below -55 dB.

| Model                        | Human rate, all / content | Agreement rate, content | Speed, times real time | Peak MLX memory | Words invented in silence | Longest loop | `ne` per 100 `pas` |
| :--------------------------- | ------------------------: | ----------------------: | ---------------------: | --------------: | ------------------------: | -----------: | -----------------: |
| Canary 1B v2                 |                 8.5 / 8.0 |                    13.1 |                     13 |         2.6 GiB |                        16 |           23 |                 96 |
| Whisper large-v3             |                 8.6 / 8.2 |                    13.1 |                      4 |         8.3 GiB |                         1 |            2 |                 77 |
| Cohere Transcribe 03-2026    |                 9.8 / 9.3 |                    15.5 |                     35 |         5.3 GiB |                       167 |           30 |                 87 |
| Parakeet TDT 0.6B v3         |               12.3 / 11.9 |                    21.6 |                     35 |         4.9 GiB |                         0 |            2 |                 82 |
| Granite Speech 4.1 2B NAR    |               14.5 / 13.5 |                    14.5 |                     14 |         5.4 GiB |                        11 |            1 |                 76 |
| MOSS-Transcribe-Diarize 0.9B |               14.7 / 12.9 |                    13.8 |                    6.5 |         3.6 GiB |                         0 |            2 |                 29 |
| Qwen3-ASR 1.7B               |               16.2 / 13.2 |                    15.1 |                      8 |         6.9 GiB |                       n/a |            4 |                 35 |
| Canary, speech only          |               12.3 / 11.6 |                    11.8 |                     13 |         2.6 GiB |                         0 |            2 |                 94 |
| Cohere, speech only          |               12.8 / 11.6 |                    11.9 |                     20 |         4.5 GiB |                         0 |           40 |                 73 |
| Granite, speech only         |               16.3 / 15.0 |                    13.9 |                     11 |         5.4 GiB |                         0 |            1 |                 79 |

- **Speed:** each model ran alone, with two exceptions. The speed of MOSS comes from a 10-minute test alone. Whisper shared the GPU with short tests during part of its run, so its speed is a lower bound.
- **Words invented in silence:** exact for the models with word or sentence times (Whisper, Parakeet, MOSS), approximate for the blocks of 25 to 30 seconds, and not measurable for the 5-minute blocks of Qwen3-ASR.
- **Longest loop:** how many times in a row one group of four words repeats.
- **`ne` per 100 `pas`:** spoken French mostly drops `ne`. A low value means that the model writes what is spoken, a high one that it rewrites into written French.

## Accuracy per listening condition

Human word error rate on all words, per clip. Each clip holds about 300 words: gaps under about 3 points are noise.

| Model                        | Room microphone A | Room microphone B | Remote speakers |
| :--------------------------- | ----------------: | ----------------: | --------------: |
| Whisper large-v3             |               4.4 |              10.2 |            10.4 |
| Canary 1B v2                 |              11.0 |               7.5 |             7.7 |
| Cohere Transcribe 03-2026    |              11.7 |               9.9 |             8.2 |
| Parakeet TDT 0.6B v3         |               8.4 |              14.4 |            13.4 |
| Granite Speech 4.1 2B NAR    |              15.8 |              12.6 |            15.3 |
| MOSS-Transcribe-Diarize 0.9B |              14.7 |              14.1 |            15.3 |
| Qwen3-ASR 1.7B               |              14.3 |              15.0 |            18.6 |

## Votes between models

A word-by-word vote between models, with Whisper as the pivot, scored on the same 901 words:

| Vote                                         | Rate, all / content |
| :------------------------------------------- | ------------------: |
| Best single model (Canary)                   |           8.5 / 8.0 |
| Whisper, Parakeet, MOSS                      |           7.5 / 7.0 |
| Whisper, Canary, Cohere                      |           7.3 / 6.9 |
| Whisper, Canary, Cohere, Parakeet, Qwen3-ASR |           5.1 / 5.3 |
| Whisper, Canary, Cohere, Parakeet, MOSS      |           5.0 / 5.2 |
| All seven                                    |           5.0 / 5.2 |

The reference started from a draft voted by Whisper, Canary, Cohere, Parakeet and MOSS. Each draft error that the listener did not catch counts in favour of these models and of their vote, so the vote results are optimistic.

## Speaker turns

pyannote `speaker-diarization-community-1` (pyannote.audio `4.0.7`, MPS) against the turns of MOSS, on the same recording and with the same cues. A second with one `speaker` cue and no `room` cue counts as speech of that speaker.

| Measure                                                  |                 MOSS | pyannote community-1 |
| :------------------------------------------------------- | -------------------: | -------------------: |
| Tags over the whole recording                            |                   59 |                   10 |
| Tags that hold 90% of the seconds of one speaker cue     |               2 to 8 |                    1 |
| Share of those seconds under the main tag of the speaker |            32 to 90% |            98 to 99% |
| Words under an anonymous label in the transcript         |                41.5% |                 6.0% |
| Speed, times real time                                   | part of the MOSS run |                   14 |

- 82% of the seconds that the largest pyannote cluster spoke under an owner cue fell under one owner, and clips of the cluster, checked by ear, all held the voice of that owner.
- A tag that spans the whole recording also speaks when no owner is shown, so the naming rule counts only its seconds under an owner cue. On the per-window tags of MOSS, the rule counts all their room seconds.

## Candidates on standalone clips

Each model transcribed the three corrected clips as standalone 2-minute WAV files, so every model heard the same audio. Without the surrounding audio, rates run higher than in the tables above. Speed is in times real time on the M1 Pro. `review.py clips` computes these tables from the runs on the clip WAVs.

| Model                                       | Rate, all / content | Per clip         |     Speed | Notes                                                                  |
| :------------------------------------------ | ------------------: | :--------------- | --------: | :--------------------------------------------------------------------- |
| Voxtral Mini 4B Realtime, fp16, 2.4 s delay |          10.7 / 9.8 | 9.9, 11.4, 10.7  |      0.38 | No word times.                                                         |
| Canary 1B v2                                |         10.9 / 10.5 | 12.5, 8.4, 12.1  |         8 |                                                                        |
| Cohere Transcribe 03-2026                   |         11.1 / 10.6 | 13.2, 10.2, 10.4 |        14 |                                                                        |
| Whisper large-v3                            |         13.2 / 12.2 | 13.2, 13.8, 12.6 |       3.5 | Drops the half sentence at the cut.                                    |
| MOSS-Transcribe-Diarize                     |         14.6 / 13.2 | 12.1, 15.3, 15.9 |         5 |                                                                        |
| Kyutai stt-1b-en_fr (MLX)                   |         19.3 / 19.0 | 11.0, 12.0, 32.3 |       1.3 | Drops whole sentences of fast, overlapping talk.                       |
| Parakeet TDT 0.6B v3                        |         19.4 / 18.3 | 9.2, 35.3, 12.6  |        20 | Lost 80 words on the second clip.                                      |
| VibeVoice-ASR 9B, 8-bit                     |         20.2 / 16.3 | 23.1, 19.2, 18.9 |       1.5 | Verbatim, with fillers and `[Silence]` tags; gives speakers and times. |
| whisper-large-v3-french                     |         22.3 / 19.7 | 11.4, 35.0, 18.9 |         5 | Skips the start of the second clip and invents a sentence.             |
| Hojo-ASR-Multi-V1                           |      35.9 on clip 1 | 35.9             | under 0.5 | Junk first tokens and empty windows on MPS.                            |
| VibeVoice-ASR Streaming 1.5B                |         59.8 / 57.9 | 43.2, 84.1, 49.9 |       1.2 | Garbles words and loops.                                               |

Votes on the same clips, with Whisper as the pivot:

| Vote                                    | Rate, all / content |
| :-------------------------------------- | ------------------: |
| Whisper, Canary, Cohere, Parakeet, MOSS |           8.5 / 8.1 |
| The five, plus Kyutai                   |           8.1 / 7.8 |
| The five, plus Voxtral and Kyutai       |           7.5 / 7.1 |
| The five, plus whisper-large-v3-french  |           8.7 / 8.4 |
| The five, plus Voxtral                  |           9.3 / 8.4 |

On 901 words, gaps under about 2 points are noise, so no vote above beats the five clearly. A decision between them needs a larger corrected sample, and the second set below does not give one.

Runtime notes:

- Hojo-ASR-Multi-V1 (`hojo-asr` 0.1.3) pins torch below 2.6, whose MPS attention fails on grouped-query heads, and it turns on autocast for CUDA only. With both patched, it still writes a junk first token and returns empty windows.
- `mlx-community/Voxtral-Mini-4B-Realtime-6bit` has no `model_type` and writes garbage. `mlx-community/Voxtral-Mini-4B-Realtime-2602-fp16` works in the mlx-audio that Nativ bundles.
- VibeVoice and whisper-large-v3-french checkpoints carry a spare output head: load them with `strict=False`.
- Kyutai runs with `moshi_mlx` 0.3.0, which needs Python 3.12 or older: `uv run --no-project --python 3.12 --with 'moshi_mlx==0.3.0' -- python -m moshi_mlx.run_inference --hf-repo kyutai/stt-1b-en_fr-mlx {wav} --temp 0`.

## A second set of clips

Three more clips of 2 minutes, one per listening condition: 1061 words. Their drafts came from another mix: Parakeet as the pivot, with Canary, Cohere, MOSS and Kyutai. The listener kept the drafts as they were.

| Model or vote, rate on all words        | First set | Second set |
| :-------------------------------------- | --------: | ---------: |
| Whisper, Canary, Cohere, Parakeet, MOSS |       8.5 |       10.7 |
| The five, plus Kyutai                   |       8.1 |       11.3 |
| The mix of the second drafts            |       9.1 |        0.0 |
| Canary 1B v2                            |      10.9 |       12.8 |
| Cohere Transcribe 03-2026               |      11.1 |       12.8 |
| Whisper large-v3                        |      13.2 |       17.9 |
| MOSS-Transcribe-Diarize                 |      14.6 |       19.0 |
| Kyutai stt-1b-en_fr (MLX)               |      19.3 |       14.9 |
| Parakeet TDT 0.6B v3                    |      19.4 |        7.5 |

- The second set measures the distance to its drafts, not accuracy. The mix of the drafts scores 0 there, and its pivot, Parakeet, goes from last to first.
- The models outside that mix write words that the drafts leave out, like `enfin`. Whisper and Kyutai also add written forms that nobody said, like `il` in `il vaut mieux` or `ne` in `je ne connais pas`.
- Kyutai brings no clear gain to the five-model vote on either set.

## Domain terms

A domain acronym that sounds like a common French noun shows what the hints are worth. Counts over the whole recording:

| Model             | Hints | Acronym | Common noun |
| :---------------- | :---- | ------: | ----------: |
| MOSS              | yes   |      27 |           0 |
| Whisper large-v3  | yes   |      21 |           5 |
| Parakeet v3       | no    |      20 |           7 |
| Cohere Transcribe | no    |       9 |          19 |
| Canary 1B v2      | no    |       3 |          23 |
| Granite 4.1       | no    |       3 |          15 |

For a model without hints, a short list of replacements built from the dictionary fixes such words after the run.

## Features

| Model                        | Weights | Licence           | Times            | Speakers                             | Hints    |
| :--------------------------- | ------: | :---------------- | :--------------- | :----------------------------------- | :------- |
| Whisper large-v3             | 2.9 GiB | Apache-2.0        | word             | no                                   | prompt   |
| Canary 1B v2                 | 3.0 GiB | CC-BY-4.0         | 25-second window | no                                   | no       |
| Cohere Transcribe 03-2026    | 3.9 GiB | Apache-2.0, gated | 30-second block  | no                                   | no       |
| Parakeet TDT 0.6B v3         | 2.3 GiB | CC-BY-4.0         | word             | no                                   | no       |
| Granite Speech 4.1 2B NAR    | 4.2 GiB | Apache-2.0        | 25-second window | no                                   | no       |
| MOSS-Transcribe-Diarize 0.9B | 1.7 GiB | Apache-2.0        | sentence         | yes, restarting per 10-minute window | prompt   |
| Qwen3-ASR 1.7B               | 3.8 GiB | Apache-2.0        | 5-minute block   | no                                   | hotwords |

- **Canary:** the loader reports one unused tensor at load. It is harmless: the output is good.
- **Parakeet:** leaves long stretches without punctuation.
- **MOSS:** in 2 windows, it wrote times without speaker labels.
- **Helper models:** Qwen3-ForcedAligner 0.6B gives word times to any text (17 seconds for 10 minutes of audio). Nemotron 3 Diarization finds speaker turns at 380 times real time, but with 8 slots it mixes people over a long meeting. Silero detects speech.

## Models left out

| Model                                | Reason                                                                                                               |
| :----------------------------------- | :------------------------------------------------------------------------------------------------------------------- |
| Voxtral Mini 3B                      | Its audio pre-processing needs PyTorch, which the runtime of Nativ does not include.                                 |
| VibeVoice-ASR (8-bit)                | 38 minutes and 13 GiB for a 10-minute clip, and no text in the output.                                               |
| Hojo-ASR-Multi-V1                    | Best open-weight French score on the Open ASR Leaderboard, but the runtime of Nativ has no loader for it.            |
| Cohere Transcribe on `mlx-community` | That conversion is for the `mlx-speech` library: the loader of Nativ accepts it without an error and writes garbage. |

## Revisions

Each model ran from the Hugging Face revision below: the one on `main` when it was downloaded.

| Model                          | Repository                                         | Revision  | Revision date |
| :----------------------------- | :------------------------------------------------- | :-------- | :------------ |
| Whisper large-v3               | `mlx-community/whisper-large-v3-asr-fp16`          | `f4b9d56` | 2026-01-13    |
| Canary 1B v2                   | `CogniSoftOrg/canary-1b-v2-mlx-bf16` (community)   | `f86c158` | 2026-06-02    |
| Cohere Transcribe 03-2026      | `CohereLabs/cohere-transcribe-03-2026`             | `d552dad` | 2026-10-07    |
| Parakeet TDT 0.6B v3           | `mlx-community/parakeet-tdt-0.6b-v3`               | `ed2b7e8` | 2025-08-16    |
| Granite Speech 4.1 2B NAR      | `mlx-community/granite-speech-4.1-2b-nar-mlx`      | `6acb789` | 2026-05-28    |
| MOSS-Transcribe-Diarize 0.9B   | `OpenMOSS-Team/MOSS-Transcribe-Diarize`            | `704aa4a` | 2026-09-02    |
| Qwen3-ASR 1.7B                 | `mlx-community/Qwen3-ASR-1.7B-bf16`                | `e1f6c26` | 2026-01-29    |
| Voxtral Mini 4B Realtime, fp16 | `mlx-community/Voxtral-Mini-4B-Realtime-2602-fp16` | `9977a0f` | 2026-02-09    |
| Kyutai stt-1b-en_fr (MLX)      | `kyutai/stt-1b-en_fr-mlx`                          | `2b99572` | 2025-06-19    |
| VibeVoice-ASR 9B, 8-bit        | `mlx-community/VibeVoice-ASR-8bit`                 | `725c72e` | 2026-01-23    |
| VibeVoice-ASR Streaming 1.5B   | `microsoft/VibeVoice-ASR-Streaming-1.5B`           | `4262d23` | 2026-09-03    |
| whisper-large-v3-french        | `bofenghuang/whisper-large-v3-french`              | `90a7cd1` | 2024-02-05    |
| Hojo-ASR-Multi-V1              | `HojoAI/Hojo-ASR-Multi-V1`                         | `aa1d0df` | 2026-08-30    |
| pyannote community-1           | `pyannote/speaker-diarization-community-1`         | `3533c8c` | 2025-09-29    |
| Qwen3-ForcedAligner 0.6B       | `mlx-community/Qwen3-ForcedAligner-0.6B-bf16`      | `53c8c0e` | 2026-01-29    |
| Nemotron 3 Diarization         | `mlx-community/Nemotron-3-Diarization`             | `59ed2db` | 2026-09-23    |
| Silero VAD                     | `mlx-community/silero-vad`                         | `7bc17f2` | 2026-04-30    |
