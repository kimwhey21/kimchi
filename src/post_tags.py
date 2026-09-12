"""글에서 검색어 태그를 뽑는다 (2026-09-12, 사용자: "검색어 태그가 너무 부족한 것 아닌가" → "진행, 이미 올라간 글도 고쳐").

왜 필요한가
-----------
2026-09-12까지 태그는 손으로 정한 고정 목록이었다 — 한국어 시황은 워드프레스에 `코스피·코스닥·원달러 환율`
세 개가 매일 똑같았고, Checkpoint는 네이버에 `주식·투자체크포인트·페르마타`뿐, 워드프레스에는 0개였다.
「인텔 CEO의 매수는 진짜일까」에 인텔도 내부자매수도 없었다. 태그는 검색 순위를 정하지는 않지만
(순위는 제목·본문의 검색어와 글의 품질) 네이버 안의 태그 검색·관련 글 묶음·주제 판단의 재료라서,
그 글에서 실제로 검색될 말이 빠져 있으면 그 묶음에서 빠진다.

무엇을 뽑는가 (순서대로, 12개까지)
---------------------------------
1. 글 종류의 고정어(코스피·주식시황·페르마타 …)
2. 원고에 적힌 `tags`(사람이 정한 것)
3. 본문에 이름이 나오는 종목 — 시황은 2% 넘게 움직인 것, 그 밖의 글은 제목·소제목·본문 순으로 나온 것
4. 제목·소제목·본문에서 찾은 주제어(유가·금리·외국인순매수·반도체·실적발표 …) — 사전에 있는 것만
5. 달 단위 검색어(`9월증시`)

네이버 요약본(`scripts/naver_post.py`)과 워드프레스 한국어 글(`publish_editorial`·`publish_feature`)이
같은 목록을 쓴다. 규칙은 이 파일 하나에서 고친다.
"""
from __future__ import annotations

import datetime as dt
import re

from pathlib import Path
import json

from src.editorial_title import _configured_names

ROOT = Path(__file__).resolve().parent.parent
LIMIT = 15             # 네이버 상한은 30. 12로 두니 달 태그가 늘 밀려나 15로(2026-09-12 시험 실행)
MIN_MOVE_PCT = 2.0     # 시황에서 종목 이름을 태그로 올리는 등락 하한 (전에는 3%·최대 3개)
MAX_STOCK_TAGS = 5
# 이름 뒤에 올 수 있는 조사. 두 글자 이름은 이것 말고 다른 한글이 붙으면 다른 낱말이다 — '소비자물가'에서 '비자'가 잡혔다.
_PARTICLES = "가는은이를을의도와과에로만"

FIXED_TAGS = {
    "kr": ["코스피", "주식시황", "코스피마감", "페르마타"],
    "us": ["미국증시", "주식시황", "뉴욕증시마감", "페르마타"],
    "기준표": ["주식", "투자체크포인트", "페르마타"],
    "프리뷰": ["미국증시", "미국장프리뷰", "주식시황", "페르마타"],
    "주간 결산": ["주간증시", "코스피", "미국증시", "주식시황", "페르마타"],
    "다음 주 일정": ["다음주증시", "증시일정", "실적발표", "주식시황", "페르마타"],
    "가이드": ["주식", "주식공부", "주식초보", "페르마타"],
    "이벤트": ["증시일정", "주식시황", "페르마타"],          # 유입 편성(2026-09-12)
}
# 영어 가이드(series "Guide", lang "en"): 한국어 고정어·주제어 사전은 맞지 않는다. 고정어 + 원고 tags + 영어 종목명.
EN_FIXED_TAGS = ["Korean stocks", "KOSPI", "foreign investors"]

# (정규식, 태그). 앞에 있는 것부터 찾고, 제목 → 소제목 → 본문 순으로 먼저 나온 것을 앞에 둔다.
THEMES: tuple[tuple[str, str], ...] = (
    (r"유가|WTI|브렌트|원유", "유가"),
    (r"국채금리|10년물|2년물|30년물|금리", "금리"),
    (r"금리 ?인상", "금리인상"),
    (r"금리 ?인하", "금리인하"),
    (r"FOMC|연방준비제도|연준", "연준"),
    (r"CPI|소비자물가", "소비자물가"),
    (r"PCE|개인소비지출", "PCE"),
    (r"고용|비농업|실업률", "고용지표"),
    (r"환율|원/달러|원달러", "원달러환율"),
    (r"외국인", "외국인순매수"),
    (r"반도체|HBM|메모리|D램", "반도체"),
    (r"은행주|은행|금융주", "은행주"),
    (r"조선", "조선주"),
    (r"방산", "방산주"),
    (r"원전|원자력", "원전주"),
    (r"바이오", "바이오주"),
    (r"2차전지|배터리", "2차전지"),
    (r"자동차", "자동차주"),
    (r"로봇", "로봇주"),
    (r"\bAI\b|인공지능", "AI"),
    (r"실적|어닝", "실적발표"),
    (r"목표주가|투자의견", "목표주가"),
    (r"내부자|직접 매수|임원[^\n]{0,6}매수", "내부자매수"),
    (r"자사주", "자사주매입"),
    (r"13F|헤지펀드", "헤지펀드"),
    (r"공매도", "공매도"),
    (r"관세", "관세"),
    (r"국제 금|금값|금 가격|온스당", "금값"),
    (r"비트코인|가상자산|암호화폐", "비트코인"),
    (r"네 마녀|옵션 ?만기|선물 ?만기|만기일", "선물옵션만기"),
    (r"코스닥", "코스닥"),
    (r"나스닥", "나스닥"),
    (r"다우", "다우지수"),
    (r"7,?000선", "코스피7000"),
    (r"사상 ?최고", "사상최고가"),
    (r"밸류에이션|PER", "밸류에이션"),
    (r"배당", "배당주"),
    (r"MSCI", "MSCI"),
    (r"추석|연휴", "추석연휴"),
)
_TAG_CLEAN = re.compile(r"[^0-9A-Za-z가-힣]+")


def kind_of(doc: dict) -> str:
    market = doc.get("market")
    if market in ("kr", "us"):
        return str(market)
    return str(doc.get("series") or ("가이드" if doc.get("kind") == "guide" else "기준표"))


def _texts(doc: dict) -> tuple[str, str, str]:
    ko = doc.get("ko") or doc
    title = str(ko.get("title") or "")
    sections = ko.get("narrative") or []
    headings = " ".join(str(s.get("heading", "")) for s in sections)
    parts = [str(s.get("body", "")) for s in sections]
    for key in ("closing", "outlook"):
        parts.append(str((ko.get(key) or {}).get("body", "")))
    body = re.sub(r"<[^>]+>", " ", " ".join(parts))
    return title, headings, body


def clean(tag: str) -> str:
    """네이버 태그 입력은 띄어쓰기·기호를 받지 않는다 — 글자·숫자만 남긴다."""
    return _TAG_CLEAN.sub("", str(tag or ""))


def known_names(data_dir: Path | None = None, recent: int = 10) -> frozenset[str]:
    """워치리스트 설정의 이름 + 최근 시세 파일에 실린 이름(그날 거래대금으로 편입된 종목까지).
    Checkpoint가 다루는 회사(인텔·델처럼 고정 목록 밖의 것)는 편입 종목으로 들어온 날의 파일에 있다."""
    names = set(_configured_names())
    folder = data_dir or (ROOT / "data")
    for market in ("kr", "us"):
        for path in sorted(folder.glob(f"price_{market}_*.json"))[-recent:]:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            for entry in (data.get("watchlist") or {}).values():
                if entry.get("name"):
                    names.add(str(entry["name"]).strip())
    return frozenset(n for n in names if n)


def mentioned(name: str, text: str) -> bool:
    """이름이 낱말로 나오는지 — 앞에 글자가 붙어 있으면 다른 낱말('소비자물가'의 '비자')이고,
    두 글자 이름은 뒤에 조사 말고 다른 한글이 붙어도 다른 낱말이다."""
    if not name:
        return False
    pattern = r"(?<![가-힣A-Za-z0-9])" + re.escape(name)
    if len(name) <= 2:
        pattern += r"(?:(?![가-힣])|(?=[" + _PARTICLES + r"](?:[^가-힣]|$)))"
    return re.search(pattern, text) is not None


def _rank(name: str, title: str, headings: str, body: str) -> int | None:
    if mentioned(name, title):
        return 0
    if mentioned(name, headings):
        return 1
    if mentioned(name, body):
        return 2
    return None


def stock_tags(doc: dict, title: str, headings: str, body: str) -> list[str]:
    """본문에 이름이 나오는 종목. 시황은 시세 파일의 등락으로 고르고, 그 밖의 글은 워치리스트 이름으로 찾는다."""
    found: list[tuple[int, float, str]] = []
    watchlist = (doc.get("price_data") or {}).get("watchlist") or {}
    if watchlist:
        for entry in watchlist.values():
            name = str(entry.get("name") or "").strip()
            move = abs(float(entry.get("change_pct") or 0))
            if not name or move < MIN_MOVE_PCT:
                continue
            rank = _rank(name, title, headings, body)
            if rank is not None:
                found.append((rank, -move, name))
    else:
        for name in known_names():
            if not re.search(r"[가-힣]", name):
                continue   # 영어 이름은 한국어 글의 태그가 아니다
            rank = _rank(name, title, headings, body)
            if rank is not None:
                found.append((rank, 0.0, name))
    found.sort()
    return [name for _, _, name in found][:MAX_STOCK_TAGS]


def theme_tags(title: str, headings: str, body: str) -> list[str]:
    ranked: list[tuple[int, int, str]] = []
    for order, (pattern, tag) in enumerate(THEMES):
        regex = re.compile(pattern)
        rank = 0 if regex.search(title) else (1 if regex.search(headings) else (2 if regex.search(body) else None))
        if rank is not None:
            ranked.append((rank, order, tag))
    ranked.sort()
    return [tag for _, _, tag in ranked]


def month_tag(doc: dict) -> str:
    try:
        day = dt.date.fromisoformat(str(doc.get("date")))
    except (TypeError, ValueError):
        return ""
    return f"{day.month}월증시"


def build_tags_en(doc: dict, limit: int = LIMIT) -> list[str]:
    """영어 가이드(2026-09-12): 고정어 + 원고 tags + 본문에 나오는 영어 종목명. 한국어 주제어 사전은 쓰지 않는다."""
    title, headings, body = _texts(doc)
    candidates = list(EN_FIXED_TAGS) + [str(t) for t in (doc.get("tags") or [])]
    for name in sorted(known_names()):
        if re.search(r"[가-힣]", name):
            continue
        if _rank(name, title, headings, body) is not None:
            candidates.append(name)
    out: list[str] = []
    for tag in candidates:
        tag = str(tag).strip()
        if tag and tag.lower() not in {t.lower() for t in out}:
            out.append(tag)
    return out[:limit]


def build_tags(doc: dict, limit: int = LIMIT) -> list[str]:
    """고정어 → 원고의 tags → 종목 → 주제어 → 달. 겹치는 것은 빼고 `limit`개까지."""
    if str(doc.get("lang") or "ko") == "en":
        return build_tags_en(doc, limit)
    kind = kind_of(doc)
    title, headings, body = _texts(doc)
    candidates: list[str] = list(FIXED_TAGS.get(kind, FIXED_TAGS["기준표"]))
    candidates += [str(t) for t in (doc.get("tags") or [])]
    candidates += stock_tags(doc, title, headings, body)
    candidates += theme_tags(title, headings, body)
    candidates.append(month_tag(doc))
    out: list[str] = []
    for raw in candidates:
        tag = clean(raw)
        if len(tag) < 2 or tag in out:
            continue
        out.append(tag)
        if len(out) >= limit:
            break
    return out
