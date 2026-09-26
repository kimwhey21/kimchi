"""Minimum publication checks for the deterministic English market brief."""
from __future__ import annotations

import json
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
    # 그림 명세와 인사이트도 독자에게 보인다(2026-09-26). 영어판 그림을 그리기 시작하면서 명세의 제목·설명·표 칸이
    # 그대로 그림에 박힌다 — us 9/23 영어판 명세는 제목이 전부 한국어였다. 인사이트에는 "Sphere (스피어)"처럼
    # 한글 종목명이 섞여 나갔다(9/17·9/18·9/21).
    for index, section in enumerate(narrative, start=1):
        spec = section.get("graphic") or {}
        if isinstance(spec, dict):
            for key in ("title", "subtitle", "note", "guide_label"):
                if spec.get(key):
                    fields.append((f"graphic {index} {key}", str(spec[key])))
            for key in ("columns", "rows", "items", "values"):
                if spec.get(key):
                    fields.append((f"graphic {index} {key}", json.dumps(spec[key], ensure_ascii=False)))
    for index, story in enumerate((generated.get("insight_section") or {}).get("stories") or [], start=1):
        fields.append((f"insight {index} heading", str(story.get("heading", ""))))
        fields.append((f"insight {index} body", str(story.get("body", ""))))
        for row in story.get("table") or []:
            fields.append((f"insight {index} table", f"{row.get('label', '')} {row.get('value', '')}"))
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
