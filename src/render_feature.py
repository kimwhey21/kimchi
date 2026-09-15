"""가이드 글을 시황과 **같은 스타일**로 렌더합니다.

2026-09-06에 가이드 글을 평범한 h1/h2/p로만 올렸더니 시황과 폰트도 글자 크기도
달라 "완전히 다른 사람이 쓴 것" 같았습니다. 스타일을 복사해 두면 한쪽만 바뀌어
같은 일이 또 생기므로, `templates/_styles.html.j2` 한 파일을 시황 템플릿과
나눠 씁니다.
"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"


def _paragraphs(body: str) -> list[str]:
    return [chunk.strip() for chunk in body.split("\n\n") if chunk.strip()]


# 영어 가이드(2026-09-12)는 같은 템플릿을 영어 문구로 렌더한다 — 템플릿을 둘로 나누면 스타일이 갈라진다.
STRINGS = {
    "ko": {"lang": "ko", "locale": "ko_KR", "related": "관련 글",
           "method_label": "확인한 것",
           "checked": "{date} 기준으로 아래 출처에서 확인했습니다.",
           "byline": "글: 페르마타 편집팀 · fermata.it.kr",
           "footer": "이 글은 정보 제공을 목적으로 하며 특정 종목의 매수·매도를 권유하지 않습니다."},
    "en": {"lang": "en", "locale": "en_US", "related": "Related",
           "method_label": "How we checked",
           "checked": "Checked {date} against the sources below.",
           "byline": "Written by the Fermata editorial desk · fermata.it.kr",
           "footer": "This article is for information only and is not a recommendation to buy or sell any security."},
}


def _checked_line(doc: dict, strings: dict) -> str:
    """'언제 기준인가'를 화면에 박는다 — 상시 글은 이 한 줄이 없으면 언제 쓴 글인지 독자가 모른다."""
    date = str(doc.get("checked") or doc.get("date") or "").strip()
    return strings["checked"].format(date=date) if date else ""


def render(doc: dict, kicker: str, figures: dict[int, dict] | None = None,
           meta_description: str | None = None, lang: str = "ko") -> str:
    """`figures`는 {절 번호(0부터): {"url", "alt"}} 입니다."""
    ko = doc.get("ko") or doc
    figures = figures or {}
    sections = []
    for index, section in enumerate(ko.get("narrative") or []):
        sections.append({
            "heading": section["heading"],
            "paragraphs": _paragraphs(section["body"]),
            "figure": figures.get(index),
        })
    closing = ko.get("closing") or {}
    strings = STRINGS.get(lang, STRINGS["ko"])
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)),
                      autoescape=select_autoescape(["html", "xml"]))
    template = env.get_template("feature.html.j2")
    return template.render(
        title=ko["title"], kicker=kicker, sections=sections,
        meta_description=meta_description,
        closing={"heading": closing.get("heading", ""),
                 "paragraphs": _paragraphs(closing.get("body", ""))},
        related=doc.get("related") or [],
        strings=strings,
        # 원고의 `sources`를 화면에 싣는다(2026-09-15). 그전에는 `source_check`가 개수만 세고
        # 독자에게는 보이지 않아, 조사해 놓고 인용을 버리는 꼴이었다.
        sources=[s for s in (doc.get("sources") or []) if s.get("name")],
        checked_line=_checked_line(doc, strings),
        byline=doc.get("byline") or strings["byline"],
    )
