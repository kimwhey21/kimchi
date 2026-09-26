"""영어 글의 출처 칸을 영어로 (2026-09-26).

왜: 본진을 온전한 영어 사이트로 바꾸고 나서(사장님 "온전히 영어사이트로 탈바꿈하자" → "모두 진행해") 세어 보니, 공개 글 57편 중
17편의 본문에 한국어가 남아 있었고 대부분이 출처 칸이었다 — 9/1~9/14 영어 시황이 인용한 한국 매체 기사 제목이 원문 그대로
("아시아경제 코스피, 6800선 강보합 마감") 나갔다. 원고를 한 편씩 고치는 대신 **그리는 곳에서** 바꾼다: 한국 매체 이름은 영어
이름(없으면 사이트 주소)으로, 한국어 기사 제목은 "Korean-language article"로. 링크는 원문 그대로 둔다 — 출처를 지우지 않는다.
한국어 글에는 쓰지 않는다. 시황(`render_html`)과 가이드(`render_feature`) 두 곳이 같은 함수를 쓴다.
"""
from __future__ import annotations

import re

_HANGUL = re.compile("[가-힣]")
KOREAN_ARTICLE = "Korean-language article"

# 영문판·영문 표기가 있는 매체만 적는다. 모르는 매체는 사이트 주소로 쓴다(지어낸 영어 이름을 붙이지 않는다).
OUTLET_EN = {
    "연합뉴스": "Yonhap News",
    "한국경제": "Korea Economic Daily",
    "한국경제 유레카": "Korea Economic Daily",
    "매일경제": "Maeil Business Newspaper",
    "머니투데이": "Money Today",
    "아시아경제": "Asia Economy",
    "파이낸셜뉴스": "Financial News",
    "서울경제": "Seoul Economic Daily",
    "이데일리": "Edaily",
    "이투데이": "Etoday",
    "뉴스1": "News1",
    "뉴스핌": "Newspim",
    "아주경제": "Aju Business Daily",
    "세계일보": "Segye Ilbo",
    "헤럴드경제": "Herald Business",
    "EBN": "EBN",
    "이비엔뉴스": "EBN",
    "이비엔(EBN)뉴스센터": "EBN",
    "블록미디어": "Blockmedia",
    "NSP통신": "NSP News",
    "CBC뉴스": "CBC News",
}


def has_hangul(text: object) -> bool:
    return bool(_HANGUL.search(str(text or "")))


def _host(url: str) -> str:
    host = re.sub(r"^https?://", "", str(url or "")).split("/")[0]
    return re.sub(r"^(www|m|news|view|biz)\.", "", host)


def english_source(source: dict) -> dict:
    """출처 한 줄을 영어 글용으로. 한글이 없으면 그대로 돌려준다."""
    if not isinstance(source, dict):
        return source
    name, title = source.get("name", ""), source.get("title", "")
    if not (has_hangul(name) or has_hangul(title)):
        return source
    out = dict(source)
    if has_hangul(name):
        out["name"] = OUTLET_EN.get(str(name).strip()) or _host(source.get("url", "")) or "Korean media"
    if has_hangul(title):
        out["title"] = KOREAN_ARTICLE
    return out


def english_sources(sources: list | None) -> list:
    return [english_source(s) for s in (sources or [])]
