"""Minimum publication checks for the deterministic English market brief."""
from __future__ import annotations

import re


class EnglishEditorialQualityError(ValueError):
    pass


_HANGUL_RE = re.compile(r"[가-힣]")

# Our own plumbing. "the largest move on the watchlist" tells the reader the stock
# topped a list they have never seen — it reads as a system note, not a sentence.
# Say "among the stocks we follow" when the scope has to be stated.
_INTERNAL_JARGON = re.compile(r"watchlist|core tier|dynamic tier", re.IGNORECASE)


def validate_generated(generated: dict) -> None:
    title = str(generated.get("title", "")).strip()
    narrative = generated.get("narrative") or []
    if not title:
        raise EnglishEditorialQualityError("English title is missing.")
    if len(narrative) < 2:
        raise EnglishEditorialQualityError("English draft needs at least two factual sections.")

    fields = [("title", title)]
    for index, section in enumerate(narrative, start=1):
        fields.extend(
            [
                (f"heading {index}", str(section.get("heading", ""))),
                (f"body {index}", str(section.get("body", ""))),
            ]
        )
    for key in ("theme_section", "stock_section", "outlook", "closing"):
        section = generated.get(key) or {}
        fields.append((f"{key} heading", str(section.get("heading", ""))))
        fields.append((f"{key} body", str(section.get("body") or section.get("commentary") or "")))

    jargon = [
        f"{label}: {_INTERNAL_JARGON.search(text).group()!r}"
        for label, text in fields
        if _INTERNAL_JARGON.search(text)
    ]
    if jargon:
        raise EnglishEditorialQualityError(
            "English draft leaks internal jargon (say 'among the stocks we follow'): "
            + ", ".join(jargon)
        )

    hangul_fields = [label for label, value in fields if _HANGUL_RE.search(value)]
    if hangul_fields:
        raise EnglishEditorialQualityError(
            "Hangul was found outside the original-language source list: " + ", ".join(hangul_fields)
        )
