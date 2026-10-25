# Cue file

A script in `scripts/sources/` reads what a source shows about the speakers, and writes it to `{work}/cues.json`. `build_transcript.py` and `check_speakers.py` read that file, whatever the source.

```json
{
  "source": "teams",
  "start": 0,
  "end": 3600,
  "spans": [
    {
      "kind": "room",
      "name": "room",
      "start": 0,
      "end": 95
    },
    {
      "kind": "owner",
      "name": "Marie Curie",
      "start": 40,
      "end": 600
    },
    {
      "kind": "speaker",
      "name": "Louis Pasteur",
      "start": 95,
      "end": 130
    }
  ]
}
```

| Field          | Content                                                                  |
| :------------- | :----------------------------------------------------------------------- |
| `source`       | The name of the script that wrote the file, like `teams`.                |
| `start`, `end` | The seconds that the source covers. `check_speakers.py` counts them all. |
| `spans`        | The cues, with their times in seconds from the start of the recording.   |

Each span has a `kind`:

| Kind      | What the source shows                                                    | What the build does with it                                                                                                         |
| :-------- | :----------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------- |
| `speaker` | A named person speaks.                                                   | A speaker tag takes the name when the cue holds 60% of the seconds that the tag speaks under `speaker` and `room` cues.             |
| `room`    | A shared microphone speaks: several voices, which the cue does not name. | The anonymous voices become room voices, like `Room, voice 1`.                                                                      |
| `owner`   | A named person presents, like the owner of the slides on screen.         | Among the tags heard under a `room` cue, the tag that speaks most under one owner takes the name of that owner, marked as probable. |

- The build rounds the `start` of a span down and its `end` up, to whole seconds.
- A name is on or off at a given second: one name at one time takes one span, not two.
- Owner spans do not overlap. At a second with two owners, the build reads the first one listed.
- The `name` of a `room` span only tells two rooms apart, in the tables of `check_speakers.py`.

## Add a source

1. Write `scripts/sources/{source}.py`, a `uv` script that reads the source and writes this file, like `teams.py`.
1. Write `references/sources/{source}.md` on the pattern of `teams.md`: what the source shows, how to read its cues, what each cue gives, the header lines of the transcript and the traps.
1. Add a row for the source to the table of step 7 in `SKILL.md`.
