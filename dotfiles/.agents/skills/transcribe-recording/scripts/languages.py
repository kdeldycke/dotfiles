"""What changes with the language of the recording: one `Language` per language.

The scripts take `--language` with the code of an entry of `LANGUAGES`. The page
`references/languages/{code}.md` tells the person who runs the skill what the entry
does. To add a language, add an entry here and its page there.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Marker:
    """A word that written style adds and speech drops, like `ne` in French."""

    word: str
    """The word, as the agreement report names it."""

    elided: str
    """The start of its elided form: a raw word that starts with it counts too."""

    base: str
    """The word that it goes with: the report counts the marker per 100 of these."""


@dataclass(frozen=True)
class Language:
    """The words and rules of one language."""

    code: str
    """ISO 639-1 code: most models, `num2words` and `wordfreq` take it."""

    name: str
    """English name of the language: Qwen3-ASR and the forced aligner take it."""

    fillers: frozenset[str]
    """Hesitation words, which models write or drop at will: no comparison counts
    them."""

    discourse: frozenset[str]
    """Discourse words, which clean-style models drop: the content rate leaves them
    out."""

    percent: str
    """The words that replace `%` before the numbers are spelled out."""

    apostrophe: tuple[re.Pattern[str], str]
    """Pattern and replacement that put the apostrophes back into rebuilt text: the
    comparison splits words at each apostrophe."""

    marker: Marker | None
    """The word that the agreement report counts, if the language has one."""

    prompt_headings: tuple[str, str]
    """Headings of Whisper's initial prompt: the participants, then the topics."""

    labels: dict[str, str]
    """Words of the transcript and of its tables."""

    guide: str
    """Rules of the listening check that depend on the language, as Markdown items."""


LANGUAGES = {
    "en": Language(
        code="en",
        name="English",
        fillers=frozenset(["uh", "um", "er", "erm", "hm", "hmm", "mm", "mhm"]),
        discourse=frozenset(["so", "well", "okay", "ok"]),
        percent="percent",
        apostrophe=(re.compile(r"\b([a-z]+) (t|s|re|ve|ll|d|m)\b"), r"\1'\2"),
        marker=None,
        prompt_headings=("Participants", "Topics"),
        labels={
            "colon": ":",
            "doubtful": "doubtful words",
            "probable": "probable",
            "room": "Room",
            "speaker": "Speaker",
            "unknown": "Unknown speaker",
            "voice": "voice",
            "voices": "voices to name",
        },
        guide=(
            "- Keep a repeated word, or a discourse word like `well` or `so`, when"
            " it is said.\n"
            "- Leave out hesitations, like `uh`, `um` and `er`.\n"
        ),
    ),
    "fr": Language(
        code="fr",
        name="French",
        fillers=frozenset([
            "euh",
            "heu",
            "hum",
            "hm",
            "mmh",
            "ben",
            "bah",
            "beh",
            "hein",
        ]),
        discourse=frozenset([
            "enfin",
            "voilà",
            "voila",
            "quoi",
            "donc",
            "bon",
            "alors",
            "ne",
            "n",
        ]),
        percent="pour cent",
        apostrophe=(
            re.compile(r"\b(c|d|j|l|m|n|qu|s|t|jusqu|lorsqu|puisqu) (?=[a-zà-öø-ÿ])"),
            r"\1'",
        ),
        marker=Marker(word="ne", elided="n'", base="pas"),
        prompt_headings=("Participants", "Sujets"),
        labels={
            "colon": " :",
            "doubtful": "mots incertains",
            "probable": "probable",
            "room": "Salle",
            "speaker": "Intervenant",
            "unknown": "Intervenant inconnu",
            "voice": "voix",
            "voices": "voix à nommer",
        },
        guide=(
            "- Keep a repeated word, or a discourse word like `enfin` or `voilà`,"
            " when it is said.\n"
            "- Write `ne` only when it is said.\n"
            "- Leave out hesitations, like `euh`, `hum`, `ben` and `bah`.\n"
        ),
    ),
}
"""The languages that the scripts know, by ISO 639-1 code."""
