# English

Code `en`. Its entry in `scripts/languages.py` holds the word lists and labels that this page names.

## Models

No English recording has been measured yet. Start with the five-model vote of `SKILL.md`, then measure the models by ear on a few clips before you trust the vote.

## Normalization

Before a comparison, `wordvote.py` changes the words of each model:

- It spells numbers out, like `50%` as `fifty percent`.
- It splits a word at its apostrophe, like `don't` into `don` and `t`, and joins the two again in rebuilt text.
- It leaves out hesitations, like `uh`, `um` or `er`.
- The content rate also leaves out discourse words, like `so`, `well` or `okay`.

The agreement report has no marker column in English.

## Labels

| Label                | English                     |
| :------------------- | :-------------------------- |
| Anonymous speaker    | `Speaker 1`                 |
| Anonymous room voice | `Room, voice 1`             |
| Doubtful words file  | `{stem}, doubtful words.md` |
| Voices file          | `{stem}, voices to name.md` |

## Listening check

The listener keeps the discourse words, like `well` or `so`, and leaves out hesitations, like `uh` or `um`.

## Traps

None seen yet.
