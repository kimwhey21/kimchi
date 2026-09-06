"""원고가 밖에서 가져온 사실을 몇 개나 담았는지 셉니다.

왜 필요한가
-----------
2026-09-06에 같은 주제·같은 형식의 두 글을 문장 단위로 대조했습니다.

    숫자 밀도     벤치마크 18개/1000자   우리 16개/1000자
    외부 출처     벤치마크 7곳           우리 0곳

**숫자를 적게 쓴 것이 아니었습니다. 밀도는 같았습니다.** 벤치마크의 숫자는
트렌드포스 계약가 전망, 1928년 이후 계절성, 한국 수출 통계, 배런스 목표가처럼
밖에서 새로 가져온 사실이고, 우리 숫자는 앞 절에서 이미 준 값의 재등장이었습니다.
그래서 우리 글은 사실로 설득하지 않고 논증으로 설득하게 됐고 교과서처럼 읽혔습니다.

`src/story_engines.py`에 재료를 뽑는 엔진 여덟 개를 만들어 두고도 그 글에는 하나도
쓰지 않았습니다. 사람이 기억해서 돌리는 단계는 빠집니다. 그래서 셉니다.

무엇을 세는가
-------------
벤치마크 100편에서 실제로 인용 주체로 등장한 이름을 세어 목록을 만들었습니다
(53종 989회, 편당 약 10회). 여기에 우리 엔진이 뽑아 주는 자료 종류를 더했습니다.

세는 것은 **서로 다른 출처의 개수**입니다. 같은 곳을 열 번 인용해도 하나입니다.
"""
from __future__ import annotations

import re

# 벤치마크 100편에서 셌습니다. 짧아서 다른 낱말에 섞이는 이름(우드·버리 등)은
# 오탐이 나므로 뺐습니다 — `버리다`가 `버리`로 잡혔습니다.
INSTITUTIONS = (
    "골드만삭스", "모건스탠리", "JP모건", "뱅크오브아메리카", "BofA", "씨티",
    "웰스파고", "바클레이즈", "UBS", "도이체방크", "번스타인", "베어드",
    "파이퍼", "캔터", "로젠블라트", "니덤", "미즈호", "에버코어", "울프리서치",
    "아거스", "스티펠", "레이먼드제임스", "키뱅크", "TD코웬", "제프리스",
    "오펜하이머", "서스퀘하나", "멜리우스",
)
RESEARCH = (
    "트렌드포스", "옴디아", "카운터포인트", "가트너", "IDC", "팩트셋",
    "리피니티브", "에포크", "세미애널리시스",
)
MEDIA = (
    "블룸버그", "로이터", "CNBC", "배런스", "WSJ", "월스트리트저널",
    "마켓워치", "닛케이",
)
OFFICIAL = (
    "연준", "노동부", "상무부", "BLS", "관세청", "한국은행", "통계청",
    "산업통상자원부", "금융감독원", "한국거래소", "CME", "페드워치", "DART",
)
# 우리 엔진이 뽑아 주는 자료. 기관 이름이 아니라 자료의 종류로 셉니다.
OUR_ENGINES = (
    ("13F", r"13F|기관 보유|헤지펀드[^\n]{0,10}(보유|매수|매도)"),
    ("내부자 매매", r"내부자|자사주[^\n]{0,6}매수|임원[^\n]{0,6}매수"),
    ("등급·목표주가 변경", r"투자의견[^\n]{0,10}(상향|하향)|목표주가[^\n]{0,10}(상향|하향)"),
    ("계절성", r"\d{4}년(부터|이후)[^\n]{0,30}(평균|수익률)|역사적으로[^\n]{0,20}(달|월)"),
    ("실적 일정", r"\d+월 \d+일[^\n]{0,20}실적"),
    ("밸류에이션", r"FWD PER|선행 PER|예상 이익 기준"),
)

# 벤치마크는 편당 약 10회 인용합니다. 서로 다른 출처로는 3곳을 하한으로 둡니다 —
# 하한을 높이면 억지 인용이 붙고, 없으면 오늘처럼 0곳짜리 글이 나갑니다.
MIN_DISTINCT_SOURCES = 3


def _body(doc: dict) -> str:
    ko = doc.get("ko") or doc
    parts = [s.get("body", "") for s in (ko.get("narrative") or [])]
    for key in ("outlook", "closing"):
        parts.append((ko.get(key) or {}).get("body", ""))
    return re.sub(r"<[^>]+>", " ", "\n".join(p for p in parts if p))


def collect(doc: dict) -> dict:
    """원고에서 찾은 외부 출처를 종류별로 돌려줍니다."""
    text = _body(doc)
    found: dict[str, list[str]] = {}
    for label, names in (("증권사", INSTITUTIONS), ("리서치", RESEARCH),
                         ("언론", MEDIA), ("공공·시장", OFFICIAL)):
        hits = sorted({name for name in names if name in text})
        if hits:
            found[label] = hits
    engine_hits = [label for label, pattern in OUR_ENGINES
                   if re.search(pattern, text)]
    if engine_hits:
        found["우리 엔진 자료"] = engine_hits
    distinct = sum(len(v) for v in found.values())
    return {"found": found, "distinct": distinct}


def collect_issues(doc: dict) -> list[str]:
    result = collect(doc)
    if result["distinct"] >= MIN_DISTINCT_SOURCES:
        return []
    have = ", ".join(f"{k}: {', '.join(v)}" for k, v in result["found"].items())
    return [
        f"밖에서 가져온 사실이 {result['distinct']}곳뿐입니다"
        f"({have or '없음'}). 최소 {MIN_DISTINCT_SOURCES}곳이 필요합니다.\n"
        f"    벤치마크는 한 편에 서로 다른 출처를 7곳 인용합니다. 우리가 그보다"
        f" 못한 것은 문장이 아니라 재료입니다.\n"
        f"    `python -m src.story_engines all --market kr`로 재료부터 뽑으십시오"
        f" — 등급 변경, 내부자 매수, 기관 수급, 계절성, 실적 일정, 밸류에이션."
    ]
