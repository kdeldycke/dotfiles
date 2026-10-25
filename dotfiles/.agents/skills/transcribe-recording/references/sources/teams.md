# Source: video of a Microsoft Teams call

The video of a Teams call shows who speaks, in two areas:

- The participant strip: Teams draws a violet box behind the name of each person who speaks. The box of a meeting room account covers every voice in that room.
- The slide corner: shared slides can show the initials of their owner in a coloured box.

`scripts/sources/teams.py` reads both areas, one frame per second, and writes the cue file of [`../cues.md`](../cues.md).

## Read the cues

1. Save one frame:

   ```shell-session
   $ uv run --script {skill}/scripts/sources/teams.py frame {video} --at 600 --out {work}/frame.png
   ```

1. Read the frame and note two crop boxes, as `width:height:x:y` in pixels of the full frame: the participant strip and the slide corner. On a 1080p Teams recording, the boxes were `246:1012:1674:68` and `420:110:1255:72`.

1. Save the two areas of each second, then group the boxes that show the same text:

   ```shell-session
   $ uv run --script {skill}/scripts/sources/teams.py extract {video} --until {end of speech, in seconds} --strip {box} --corner {box} --folder {work}/teams
   $ uv run --script {skill}/scripts/sources/teams.py scan --folder {work}/teams
   ```

1. Read each contact sheet, `P_sheet_*.png` for the participants and `O_sheet_*.png` for the slide owners, then fill the two names files. A room that joins through the account of a person is a room account.

   | File           | Value for each group                                                                                                                        |
   | :------------- | :------------------------------------------------------------------------------------------------------------------------------------------ |
   | `P_names.json` | The full name of a remote participant; `room` or `room: {account}` for the account of a meeting room; `ignore` for a box that names nobody. |
   | `O_names.json` | The name of the slide owner, or `ignore`.                                                                                                   |

1. Write the cue file:

   ```shell-session
   $ uv run --script {skill}/scripts/sources/teams.py export --folder {work}/teams --cues {work}/cues.json
   ```

## What the cues give

| Names file value            | Cue kind  | Effect on the transcript                                                                                   |
| :-------------------------- | :-------- | :--------------------------------------------------------------------------------------------------------- |
| A participant name          | `speaker` | A remote participant takes the name in its box.                                                            |
| `room` or `room: {account}` | `room`    | The voices of the room keep anonymous labels, like `Room, voice 1`.                                        |
| A slide owner               | `owner`   | In the room, the voice that speaks most under the slides of one owner takes that name, marked as probable. |

## Header lines

Add these lines to the header of the transcript:

- **Remote participants** are named from the name that Teams highlights.
- **Room voices marked (probable)** are named from the initials on the slides shown.

## Traps

- The thresholds of `violet_boxes` and `owner_box` suit Teams at 1080p. When a sheet shows no group, adjust them. When a sheet splits one name into several groups, give each group the same name.
