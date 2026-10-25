# French

Code `fr`. Its entry in `scripts/languages.py` holds the word lists and labels that this page names.

## Models

The five-model vote of `SKILL.md` was chosen on French speech: [`../benchmark.md`](../benchmark.md) holds the measurements. Whisper and MOSS take the dictionary as hints. MOSS and Qwen3-ASR write what is said, like `je suis pas`, where the other models rewrite it into written French, like `je ne suis pas`.

## Normalization

Before a comparison, `wordvote.py` changes the words of each model:

- It spells numbers out, like `50 %` as `cinquante pour cent`.
- It splits a word at its apostrophe, like `c'est` into `c` and `est`, and joins the two again in rebuilt text.
- It leaves out hesitations, like `euh`, `hum` or `ben`.
- The content rate also leaves out discourse words, like `enfin`, `voilà` or `donc`, and the negation `ne`.

Spoken French mostly drops `ne`. The agreement report counts `ne` per 100 `pas`: a low value means that a model writes what is said, a high one that it rewrites speech into written French.

## Labels

| Label                | French                       |
| :------------------- | :--------------------------- |
| Anonymous speaker    | `Intervenant 1`              |
| Anonymous room voice | `Salle, voix 1`              |
| Doubtful words file  | `{stem}, mots incertains.md` |
| Voices file          | `{stem}, voix à nommer.md`   |

The subtitles put a space before the colon after a name, as French typography does.

## Listening check

The listener keeps the discourse words, like `enfin` or `voilà`, writes `ne` only when it is said, and leaves out hesitations, like `euh` or `bah`.

## Traps

- Whisper splits `c'est` into ` c` and `'est`: `wordvote.py` joins the second piece to the first.
