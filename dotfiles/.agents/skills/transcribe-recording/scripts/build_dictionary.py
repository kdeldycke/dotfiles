#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["extract-msg", "pymupdf", "wordfreq"]
# ///
"""Extract the text of related documents and list candidate terms for a dictionary.

The candidates are acronyms, proper names (with `Firstname LASTNAME` pairs from mail
headers and signatures) and rare words that recur across documents. A word is rare
when `wordfreq` finds it rare in the language of `--language`, and in English, which
documents often mix in. Read
`candidates.json`, then write `dictionary.tsv` by hand with four tab-separated
columns: `term`, `category` (`person`, `place`, `company`, `project`, `acronym`,
`term`), `hotword` (`yes` for the terms likely spoken, which go to the models as
hints) and `note`. The first line is the header.

Reads PDF, Outlook `.msg`, `.eml`, Office files (`.pptx`, `.docx`, `.xlsx`, `.odt`),
Markdown, text and CSV. `corpus/` keeps the extracted text of each document.
"""

from __future__ import annotations

import argparse
import email
import email.policy
import hashlib
import html
import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import extract_msg
import pymupdf as fitz
from languages import LANGUAGES
from wordfreq import zipf_frequency

TEXT_SUFFIXES = {
    ".csv",
    ".docx",
    ".eml",
    ".md",
    ".msg",
    ".odt",
    ".pdf",
    ".pptx",
    ".txt",
    ".xlsx",
}

WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿŒœ0-9][A-Za-zÀ-ÖØ-öø-ÿŒœ0-9'’\-]*")
ACRONYM = re.compile(r"[A-Z][A-Z0-9&]{1,7}")
FULL_NAME = re.compile(
    r"\b([A-ZÉ][a-zéèëïîôç]+(?:[- ][A-ZÉ][a-zéèëïîôç]+)?)\s+"
    r"((?:[A-ZÉ]{2,}|[A-ZÉ][a-zéèëïîôç]+)(?:[- ][A-ZÉ]{2,})?)\b"
)


def xml_text(archive: zipfile.ZipFile, names: list[str], tag: str) -> str:
    parts: list[str] = []
    for name in names:
        data = archive.read(name).decode("UTF-8", errors="replace")
        parts.extend(
            html.unescape(t)
            for t in re.findall(rf"<{tag}(?:\s[^>]*)?>(.*?)</{tag}>", data, re.DOTALL)
        )
    return " ".join(parts)


def extract(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        with fitz.open(path) as document:
            return "\n".join(page.get_text() for page in document)
    if suffix == ".msg":
        with extract_msg.openMsg(str(path)) as message:
            header = [
                message.subject or "",
                message.sender or "",
                message.to or "",
                message.cc or "",
            ]
            return "\n".join(header) + "\n" + (message.body or "")
    if suffix == ".eml":
        message = email.message_from_bytes(
            path.read_bytes(), policy=email.policy.default
        )
        body = message.get_body(preferencelist=("plain", "html"))
        text = body.get_content() if body else ""
        return (
            "\n".join(str(message.get(h, "")) for h in ("Subject", "From", "To", "Cc"))
            + "\n"
            + re.sub(r"<[^>]+>", " ", text)
        )
    if suffix in {".pptx", ".docx", ".xlsx", ".odt"}:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if suffix == ".pptx":
                slides = [
                    n
                    for n in names
                    if re.match(r"ppt/(slides|notesSlides)/\w+\d+\.xml$", n)
                ]
                return xml_text(archive, slides, "a:t")
            if suffix == ".docx":
                return xml_text(
                    archive,
                    [n for n in names if n.startswith("word/") and n.endswith(".xml")],
                    "w:t",
                )
            if suffix == ".xlsx":
                return xml_text(
                    archive, [n for n in names if n == "xl/sharedStrings.xml"], "t"
                )
            data = archive.read("content.xml").decode("UTF-8", errors="replace")
            return html.unescape(re.sub(r"<[^>]+>", " ", data))
    return path.read_text(encoding="UTF-8", errors="replace")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--skip",
        action="append",
        default=[],
        help="Folder name to leave out, like copies or generated notes. Repeat it.",
    )
    parser.add_argument(
        "--language",
        choices=sorted(LANGUAGES),
        required=True,
        help="Code of the language of the documents, an entry of languages.py.",
    )
    args = parser.parse_args()
    code = args.language
    corpus = args.out / "corpus"
    corpus.mkdir(parents=True, exist_ok=True)

    manifest: list[dict] = []
    texts: dict[str, str] = {}
    for path in sorted(args.root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if set(args.skip) & set(path.relative_to(args.root).parts):
            continue
        # A broken file must not stop the inventory: the manifest lists its error.
        try:
            text = extract(path)
        except Exception as error:  # noqa: BLE001
            manifest.append({
                "path": str(path),
                "error": f"{type(error).__name__}: {error}",
            })
            continue
        key = hashlib.sha1(str(path).encode("UTF-8")).hexdigest()[:12]
        (corpus / f"{key}.txt").write_text(text, encoding="UTF-8")
        texts[str(path)] = text
        manifest.append({"path": str(path), "key": key, "chars": len(text)})
    (args.out / "manifest.json").write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False), encoding="UTF-8"
    )

    acronyms: Counter[str] = Counter()
    capitals: Counter[str] = Counter()
    lower_forms: Counter[str] = Counter()
    rare: Counter[str] = Counter()
    names: Counter[str] = Counter()
    docs: dict[str, set[str]] = defaultdict(set)
    for source, text in texts.items():
        for name in FULL_NAME.finditer(text):
            first, last = name.group(1), name.group(2)
            if zipf_frequency(first.lower(), code) < 4.5 or last.isupper():
                names[f"{first} {last}"] += 1
        for token in WORD.findall(text):
            token = token.strip("'’-")
            if len(token) < 2:
                continue
            lower = token.lower()
            if ACRONYM.fullmatch(token):
                if zipf_frequency(lower, code) < 3.5:
                    acronyms[token] += 1
                    docs[token].add(source)
            elif token[0].isupper():
                capitals[token] += 1
                docs[token].add(source)
            else:
                lower_forms[lower] += 1
                if (
                    len(token) >= 4
                    and not token.isdigit()
                    and zipf_frequency(lower, code) < 1.5
                    and zipf_frequency(lower, "en") < 3.0
                ):
                    rare[lower] += 1
                    docs[lower].add(source)

    proper = Counter({
        token: count
        for token, count in capitals.items()
        if count >= 2
        and count >= 4 * lower_forms.get(token.lower(), 0)
        and zipf_frequency(token.lower(), code) < 3.0
    })
    failed = [m for m in manifest if "error" in m]
    candidates: dict[str, list[tuple]] = {
        "acronyms": [(t, c, len(docs[t])) for t, c in acronyms.most_common() if c >= 2],
        "proper": [(t, c, len(docs[t])) for t, c in proper.most_common()],
        "names": [(t, c) for t, c in names.most_common() if c >= 2],
        "rare": [
            (t, c, len(docs[t]))
            for t, c in rare.most_common()
            if c >= 3 and len(docs[t]) >= 2
        ],
    }
    report = {"documents": len(texts), "failed": failed, **candidates}
    (args.out / "candidates.json").write_text(
        json.dumps(report, indent=1, ensure_ascii=False), encoding="UTF-8"
    )
    print(f"documents={len(texts)} failed={len(failed)}")
    for key, found in candidates.items():
        print(f"{key}: {len(found)} candidates")


if __name__ == "__main__":
    main()
