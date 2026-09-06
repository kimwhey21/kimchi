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


def render(doc: dict, kicker: str, figures: dict[int, dict] | None = None,
           meta_description: str | None = None) -> str:
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
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)),
                      autoescape=select_autoescape(["html", "xml"]))
    template = env.get_template("feature.html.j2")
    return template.render(
        title=ko["title"], kicker=kicker, sections=sections,
        meta_description=meta_description,
        closing={"heading": closing.get("heading", ""),
                 "paragraphs": _paragraphs(closing.get("body", ""))},
    )
