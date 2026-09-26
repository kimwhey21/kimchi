"""기준표(feature) 원고가 `docs/feature-style.md`를 지켰는지 기계로 봅니다.

왜 필요한가
-----------
2026-09-06 첫 편에서 네 번을 고쳤습니다. 제목이 설명적이었고(41자, 지표 용어),
시각자료가 0장이었습니다. 둘 다 **어디에도 적혀 있지 않아서** 벌어진 일입니다.

문서에만 적어 두면 지켜지지 않는다는 것은 이미 겪었습니다 — `editorial-style.md`에
"소제목에 종결 어미를 붙이지 않는다"고 적어 뒀는데 다음 원고의 소제목 6개 중
4개가 `~했습니다`로 끝났습니다. 그래서 검사로 옮깁니다.

무엇을 하지 않는가
------------------
**말맛을 기계로 재려 하지 않습니다.** "결론을 제목에 넣지 않았는가"는 사람만
판단할 수 있습니다. 여기서 보는 것은 세어서 틀렸다고 말할 수 있는 것뿐입니다 —
후킹 장치가 하나라도 있는지, 그림이 최소 개수를 넘는지, 확인 날짜가 박혔는지.

`editorial_quality`·`editorial_title` 검사는 별도로 통과해야 합니다. 이 파일은
그 위에 기준표 글에만 해당하는 것을 더합니다.
"""
from __future__ import annotations

import argparse
import json
import datetime as dt
import re
import sys
from pathlib import Path

from src import editorial_title


# 제목 후킹 장치·지표 용어·소제목·절 수는 editorial_title에 있습니다(2026-09-08, 모든 글 공통).
MIN_GRAPHICS = 6          # 벤치마크 이미지 p25

# 시리즈별 시각자료 하한. 기준표는 위 기본값이고, 밤 10시 미국장 프리뷰(2026-09-08)는
# 짧은 글이라 표지 + 본문 둘이면 된다. 절 수 하한은 editorial_title.SECTION_FLOORS에 있다
# (모든 글의 소제목 규칙이 그쪽에 모여 있다). 새 시리즈를 만들면 두 곳에 한 줄씩 더한다.
# 주말 편성(2026-09-12, 사용자 결정): 토요일 「주간 결산」은 숫자 글이라 표지 + 지수 카드 + 종목
# 막대 + 흐름 넷, 일요일 「다음 주 일정」은 프리뷰처럼 셋이면 된다.
# 프리뷰는 2026-09-17부터 **그날 미국장의 메인 글**이다(사장님: "1번2번3번 진행"). 12절·4,500~6,000자·
# 그림 8~10장. 9/15 합본 실험에서 드러난 셋을 여기서 막는다 — 절당 얕음(13절에 5,884자) → 절당 400자,
# `number_cards` 네 번 → 같은 종류 2장까지, 초보자 상자 하나 → 둘 이상. 시간(19분)은 지시문의 22:00 마감.
SERIES_LIMITS = {"프리뷰": {"graphics": 8, "min_section_chars": 400, "max_same_kind": 2, "min_beginner": 2},
                 "주간 결산": {"graphics": 4}, "다음 주 일정": {"graphics": 3},
                 # 유입 편성(2026-09-12, 사용자 승인 "1번 2번 4번 진행"): 상시 가이드는 표·차트 둘이면 되고
                 # 글의 힘은 질문에 바로 답하는 본문에 있다. 이벤트 글은 일정표 + 차트.
                 "가이드": {"graphics": 2}, "Guide": {"graphics": 2}, "이벤트": {"graphics": 2},
                 "매거진": {"graphics": 0}}   # 두 번째 네이버 블로그(2026-09-13): 데이터 그래픽 없이 사진 한 장

# 영어 가이드(series "Guide", lang "en")는 한국어 제목 문법·문체 검사를 받지 않는다. 대신 아래 셋을 본다 —
# 제목 길이(구글 결과에 잘리지 않는 70자), 절 수(SECTION_FLOORS), 본문에 확인 연도. 2026-09-12 실측:
# 구글 노출 710건 중 700건이 영어 가이드 9편에서 나왔다("kospi vs kosdaq", "kospi trading hours").
EN_TITLE_MAX = 70
EN_TITLE_MIN = 30

# 설명 없이 지나가면 초보자가 문장을 못 따라가는 말들. 벤치마크는 이런 말이
# 나올 때마다 `초보자용 설명` 블록을 따로 답니다(100편 중 30%).
#
# 30%라는 숫자는 "열 편 중 세 편에 넣어라"는 뜻이 아닙니다. **이런 말이 나온 글에는
# 넣고, 안 나온 글에는 안 넣은 결과**가 30%입니다. 그래서 개수가 아니라
# 글 안에 실제로 그런 말이 있는지로 봅니다.
JARGON_IN_BODY = (
    "PER", "EPS", "FWD", "밸류에이션", "컨센서스", "가이던스", "CAPEX",
    "HBM", "D램", "낸드", "계약가", "현물가", "매출총이익률", "영업이익률",
    "이동평균", "50일선", "200일선", "볼린저", "순매수", "순매도", "공매도",
    "듀레이션", "베이시스", "bp", "선물시장", "패시브", "ETF",
)


# 우리는 종목을 들고 있지 않습니다. 1인칭 포지션 화법을 흉내 내면 거짓말이 됩니다.
POSITION_PHRASES = ("제가 매수", "제가 매도", "저는 매수", "저는 매도", "제 계좌",
                    "보유 물량", "익절했", "저는 이렇게 대응하겠", "제 포트폴리오")


ROOT = Path(__file__).resolve().parents[1]


def beginner_issues(body: str) -> tuple[list[str], list[str]]:
    """(막을 것, 참고) — 초보자 설명: 무조건 요구하지도, 그냥 넘기지도 않습니다.

    **글에 설명이 필요한 말이 실제로 들어 있는지**를 보고 정합니다. 매번 요구하면
    필요 없는 자리에도 들어가고, 그냥 넘기면 PER·HBM·계약가가 설명 없이 지나갑니다.
    시황에도 같은 규칙입니다(2026-09-08, 사용자: 재테크농부처럼 초보자 설명 한 토막).
    """
    issues, notes = [], []
    used = [word for word in JARGON_IN_BODY if word in body]
    if "초보자" not in body:
        if len(used) >= 3:
            issues.append(
                f"초보자 설명이 없는데 설명이 필요한 말이 {len(used)}개 나옵니다: "
                f"{', '.join(used[:8])}. '초보자 설명:'으로 시작하는 문단 하나로 이 중 이 글의 "
                f"논지에 꼭 필요한 것 하나는 풀어 쓰십시오. docs/feature-style.md 0절.")
        elif used:
            notes.append(f"설명이 필요할 수 있는 말: {', '.join(used)}. "
                         f"독자가 모르면 논지를 못 따라가는지 보십시오.")
    return issues, notes


def position_issues(body: str) -> list[str]:
    for phrase in POSITION_PHRASES:
        if phrase in body:
            return [f"본문에 포지션 화법 {phrase!r}이 있습니다 — 우리는 종목을 들고 있지 않습니다. "
                    "판단은 '우리는 이렇게 봅니다'로 씁니다. docs/feature-style.md 0절."]
    return []


def deadline_issue(doc: dict) -> str | None:
    """기준표의 마감일(최상위 `deadline`, YYYY-MM-DD) — 글 머리말 'Checkpoint · N월 N일까지 확인할 것'이
    이 값으로 그려진다(2026-09-09). 성적표에 적은 확인 지점 중 마지막 날짜와 같아야 한다."""
    deadline = doc.get("deadline")
    if not deadline:
        return ("최상위 `deadline`(YYYY-MM-DD)이 없습니다 — 성적표에 적은 확인 지점 중 마지막 날짜를 "
                "적으십시오. 글 머리말 'Checkpoint · N월 N일까지 확인할 것'이 이 값으로 그려집니다.")
    try:
        day = dt.date.fromisoformat(str(deadline))
    except ValueError:
        return f"`deadline` {deadline!r}은(는) YYYY-MM-DD가 아닙니다."
    try:
        posted = dt.date.fromisoformat(str(doc.get("date")))
    except (TypeError, ValueError):
        return None
    if day <= posted:
        return f"`deadline` {deadline}이(가) 글 날짜 {posted} 이전입니다 — 확인 지점은 앞날이어야 합니다."
    return None


# 레이더에서 골랐는지 원고에 남긴다(2026-09-14, 사용자 "넣어라").
#
# 왜 필요한가: 아침 레이더를 Checkpoint·가이드에 붙였는데, 원고에 그 기록이 없으면 몇 주 뒤에
# **"레이더로 고른 글이 더 읽혔나"를 셀 수 없다.** 붙인 장치의 효과를 못 재면 그 장치를 지울지
# 늘릴지도 근거 없이 정하게 된다. 한 줄로 남긴다 — 어느 제목에서 출발했는지, 아니면 안 썼는지.
RADAR_SERIES = {"기준표", "가이드", "Guide", "매거진"}
RADAR_NONE = {"목록 순서", "레이더 실패", "list order", "radar failed"}
# 이 날짜부터 쓴 원고에만 요구한다. 그 전 글에는 이 필드가 없었고, 이미 공개된 글을 뒤늦게
# 막으면 관문이 "틀리게 우는 검사"가 된다 — 그런 검사는 곧 무시당한다(tests/test_rule_files.py 머리말).
RADAR_FROM = "2026-09-15"


def radar_origin_issue(doc: dict) -> str | None:
    """최상위 `radar_origin` — 레이더 제목 그대로, 또는 안 썼으면 `목록 순서`(영어 글은 `list order`).

    레이더가 비거나 피드가 다 막힌 날은 `레이더 실패`. **빈 값으로 두지 않는다** — 비어 있으면
    "안 썼다"와 "적기를 잊었다"가 같아 보이고, 그것이 곧 셀 수 없는 기록이다.
    """
    if str(doc.get("series") or "") not in RADAR_SERIES:
        return None
    if str(doc.get("date") or "") < RADAR_FROM:
        return None
    origin = doc.get("radar_origin")
    if not isinstance(origin, str) or not origin.strip():
        return ("최상위 `radar_origin`이 없습니다 — 아침 레이더에서 고른 주제면 **그 제목 그대로**, "
                "레이더를 안 썼으면 `목록 순서`(영어 글은 `list order`), 레이더가 비었거나 피드가 "
                "다 막혔으면 `레이더 실패`를 적으십시오. 몇 주 뒤에 레이더의 효과를 세려면 이 한 줄이 필요합니다.")
    origin = origin.strip()
    if origin in RADAR_NONE:
        return None
    if len(origin) < 10:
        return (f"`radar_origin`이 {origin!r}입니다 — 레이더 제목을 그대로 적거나, 안 썼으면 "
                f"`목록 순서`/`list order`, 실패했으면 `레이더 실패`라고 적으십시오.")
    return None


def collect_issues(doc: dict, graphics: int | None = None,
                   notes_out: list[str] | None = None) -> list[str]:
    """막을 것만 돌려줍니다.

    **드문 것과 틀린 것을 구분합니다.** 벤치마크에서 드물 뿐인 어법(존댓말 제목,
    지표 용어, 초보자 설명 생략)을 차단으로 바꿨더니 쓸 수 있는 글이 좁아지고
    통계에 맞추는 글이 나왔습니다. 그런 항목은 `notes_out`으로 알려만 줍니다.
    """
    ko = doc.get("ko") or doc
    issues: list[str] = []
    notes: list[str] = notes_out if notes_out is not None else []

    title = ko.get("title") or ""
    if not title:
        return ["제목이 없습니다."]
    # 제목 후킹 장치·지표 용어·절 수·소제목 길이는 editorial_title.collect_issues가 봅니다
    # (feature_gate가 kind=series로 부릅니다). 여기는 기준표 본문에만 있는 것만 봅니다.

    limits = SERIES_LIMITS.get(str(doc.get("series") or ""), {})
    min_graphics = limits.get("graphics", MIN_GRAPHICS)

    sections = ko.get("narrative") or []
    body = " ".join(s.get("body", "") for s in sections) + (
        ko.get("closing", {}).get("body", ""))

    # 6절(확인 지점)이 이 글 형식의 존재 이유입니다. 날짜가 없으면 그냥 시황입니다.
    # 잡지(2026-09-13)는 예외 — 소금의 역사에 확인 날짜가 있을 리 없다. 잡지 꼴은 magazine_issues가 따로 본다.
    if str(doc.get("series") or "") != "매거진" and not re.search(r"\d+월 \d+일", body):
        issues.append("본문에 확인 날짜(`N월 N일`)가 없습니다 — 기준표 글은 날짜를 "
                      "박아야 글의 수명이 그날까지 갑니다. docs/feature-style.md 4절.")

    problem = radar_origin_issue(doc)
    if problem:
        issues.append(problem)

    # 표지 사진은 `url`로 적는다. 루틴이 샌드박스에 받은 `output/…` 경로를 `local_path`로 적으면 관문은 통과하고
    # 발행 러너에서 "표지 사진이 없습니다"로 죽는다(2026-09-20 wall_street_sign, 2026-09-26 samsung_semiconductor —
    # 두 번 다 워드프레스 글이 안 만들어졌다). output/은 커밋하지 않으므로 여기서 미리 막는다.
    photo = doc.get("featured_photo") or {}
    local = str(photo.get("local_path") or "")
    if local and not photo.get("url") and (local.startswith("output/") or not (ROOT / local).exists()):
        issues.append(f"표지 사진 `featured_photo.local_path`={local!r}는 발행 러너에 없는 파일입니다(output/은 커밋하지 "
                      "않습니다). 고른 사진의 Unsplash 주소를 `featured_photo.url`에 적으세요(docs/routine_feature.md).")

    # 시리즈별 부피 규칙(2026-09-17, 프리뷰 확대). 절당 글자·같은 그래픽 종류·초보자 상자 수.
    min_chars = limits.get("min_section_chars")
    if min_chars:
        thin = [(i + 1, len(re.sub(r"<[^>]+>", "", str(sec.get("body") or "")).strip()))
                for i, sec in enumerate(sections)]
        thin = [(i, n) for i, n in thin if n < min_chars]
        if thin:
            issues.append(f"절이 얕습니다 — {', '.join(f'{i}절 {n}자' for i, n in thin)}. 이 시리즈는 절마다 "
                          f"{min_chars}자 이상입니다(9/15 실험: 13절에 5,884자, 절당 450자라 얕았습니다). "
                          "절을 줄이지 말고 근거·숫자·초보자 설명으로 채우십시오.")
    max_same = limits.get("max_same_kind")
    if max_same:
        kinds = [str(g.get("kind")) for g in (doc.get("graphics") or []) if isinstance(g, dict) and g.get("kind") != "cover"]
        for kind in sorted(set(kinds)):
            if kinds.count(kind) > max_same:
                issues.append(f"그래픽 `{kind}`이 {kinds.count(kind)}장입니다 — 같은 종류는 {max_same}장까지"
                              "(9/15 실험에서 `number_cards`가 네 번 나와 단조로웠습니다). fact_table·price_history·"
                              "calendar_strip·checklist·valuation_bars·rate_compare로 나누십시오.")
    min_beginner = limits.get("min_beginner")
    if min_beginner:
        boxes = len(re.findall(r"초보자\s*(?:용\s*)?설명", body))
        if boxes < min_beginner:
            issues.append(f"초보자 설명이 {boxes}개입니다 — 이 시리즈는 {min_beginner}개 이상입니다. 재테크농부 FOMC 글은 "
                          "개념마다(bp·점도표·2년물·선반영) 상자를 달았습니다. '초보자 설명:'으로 시작하는 문단으로.")

    # 머리말에 쓰는 마감일 (2026-09-09). 시리즈가 명시된 기준표만 — 프리뷰는 그날 밤으로 끝난다.
    if doc.get("series") == "기준표":
        problem = deadline_issue(doc)
        if problem:
            issues.append(problem)

    # 제목이 약속한 것을 본문이 답하는지 (제목 원칙 7)
    dates_in_title = re.findall(r"\d+월 \d+일", title)
    for date in dates_in_title:
        if date not in body:
            issues.append(f"제목의 {date}이 본문에 없습니다 — 제목이 약속한 것을 "
                          f"본문이 다뤄야 합니다.")

    # 초보자 설명과 포지션 화법은 시황과 같은 함수를 씁니다(2026-09-08, 모든 글 공통).
    body_issues, body_notes = beginner_issues(body)
    issues += body_issues
    notes += body_notes
    issues += position_issues(body)

    if graphics is not None and graphics < min_graphics:
        issues.append(f"시각자료가 {graphics}장입니다 — 최소 {min_graphics}장. "
                      f"벤치마크는 편당 중앙값 10장입니다.")

    return issues


# 네이버용 본문(2026-09-12, 사용자: "네이버도 애드포스트가 있고 본진만큼 중요하다" → "2번 제외 진행").
# 오래 읽히는 시리즈는 네이버에 요약본이 아니라 **다른 문장으로 쓴 완전한 글**을 싣는다 — 애드포스트 수익과 네이버 검색은
# 그 글 자체가 끝까지 읽히는지를 본다. 본진과 같은 문장이 있으면 유사문서로 잡히므로 25자 이상 같은 문장을 막는다.
NAVER_FULL_SERIES = {"가이드", "주간 결산", "다음 주 일정", "이벤트"}
NAVER_FULL_SINCE = "2026-09-13"          # 이 날짜 이후 원고부터 요구한다(그전 원고는 요약본으로 나갔다)
NAVER_FULL_ENDED = "2026-09-23"          # 이 날짜부터는 요구하지 않는다 — 본진이 비공개가 되어 쌍둥이가 없다(2026-09-22 사장님 결정)
NAVER_SECTIONS = (4, 6)
NAVER_CHARS = (1200, 3000)
NAVER_DUP_MIN_CHARS = 25

# 시황도 네이버 전용 본문을 쓴다(2026-09-14부터). 2026-09-13 실측: 네이버에 올라간 시황이 본진 글과
# 21.9~40.9% 겹쳤다(가이드 2.1%, 프리뷰 0.5%). 시황만 이 규칙에서 빠져 있어 본진 문장을 그대로 옮기고 있었고,
# 하필 하루 두 번으로 가장 자주 올리는 종류다 — 유사문서로 걸리면 네이버 통로가 통째로 막힌다.
# 문턱은 가이드보다 낮다. 목적은 분량을 늘리는 것이 아니라 겹침을 없애는 것이다.
NAVER_DAILY_SINCE = "2026-09-14"
NAVER_DAILY_ENDED = "2026-09-16"   # 이 날짜부터 시황은 네이버 전용(본문 그대로)
NAVER_DAILY_MARKETS = {"kr", "us"}
NAVER_DAILY_SECTIONS = (3, 5)
NAVER_DAILY_CHARS = (900, 2200)


def naver_spec(doc: dict) -> tuple[str, tuple[int, int], tuple[int, int]] | None:
    """(무엇이라 부를지, 절 범위, 글자 범위) — 네이버 전용 본문을 요구하지 않는 원고면 None."""
    date = str(doc.get("date") or "")
    series = str(doc.get("series") or "")
    if series in NAVER_FULL_SERIES:
        if date >= NAVER_FULL_ENDED:
            return None        # 2026-09-22부터 네이버에 `ko.narrative` 전문이 간다 — 다시 쓸 본문이 없다
        return (series, NAVER_SECTIONS, NAVER_CHARS) if date >= NAVER_FULL_SINCE else None
    if series == "매거진":
        return None            # 본진 쌍둥이가 없다 — 이 원고의 본문이 곧 네이버 본문이다(magazine_issues가 따로 본다)
    if not series and str(doc.get("market") or "") in NAVER_DAILY_MARKETS:
        # 2026-09-16부터 한국어 시황은 네이버에만, 본문 그대로 나간다(사용자 결정) — 쌍둥이가 없으니
        # 다시 쓸 대상도 없다. 그 전에 쓴 원고는 규칙이 있던 시절 것이라 그대로 검사한다.
        if date >= NAVER_DAILY_ENDED:
            return None
        return ("시황", NAVER_DAILY_SECTIONS, NAVER_DAILY_CHARS) if date >= NAVER_DAILY_SINCE else None
    return None


def _sentences(text: str) -> set[str]:
    plain = re.sub(r"<[^>]+>", "", str(text or ""))
    return {x.strip() for x in re.split(r"(?<=[.!?다요])\s+", plain) if len(x.strip()) >= NAVER_DUP_MIN_CHARS}


def naver_issues(doc: dict) -> list[str]:
    """`naver.narrative`(네이버용 본문) — 있어야 하는 시리즈에 없거나, 길이·절 수가 어긋나거나, 본진 문장을 그대로 썼으면 막는다."""
    spec = naver_spec(doc)
    if spec is None:
        return []
    what, section_range, char_range = spec
    naver = doc.get("naver") or {}
    sections = naver.get("narrative") or []
    if not sections:
        return [f"네이버용 본문(최상위 `naver.narrative`)이 없습니다 — {what}은(는) 네이버에 요약본이 아니라 완전한 글로 갑니다. "
                f"절 {section_range[0]}~{section_range[1]}개, {char_range[0]:,}~{char_range[1]:,}자, 본진과 다른 문장으로."]
    issues: list[str] = []
    if not section_range[0] <= len(sections) <= section_range[1]:
        issues.append(f"네이버용 본문이 {len(sections)}절입니다 — {section_range[0]}~{section_range[1]}절.")
    body = " ".join(str(s.get("body", "")) for s in sections)
    length = len(re.sub(r"<[^>]+>", "", body))
    if not char_range[0] <= length <= char_range[1]:
        issues.append(f"네이버용 본문이 {length:,}자입니다 — {char_range[0]:,}~{char_range[1]:,}자.")
    for index, section in enumerate(sections, start=1):
        if not str(section.get("heading") or "").strip():
            issues.append(f"네이버용 본문 {index}절에 소제목이 없습니다.")
    ko = doc.get("ko") or doc
    # 마무리 문단을 사이 공백 없이 붙이면 본문 마지막 문장과 마무리 첫 문장이 한 덩어리가 되어
    # 그 두 문장만 중복 검사에서 빠진다(2026-09-13, 시황으로 규칙을 넓히다 테스트가 잡았다).
    main_text = " ".join([str(s.get("body", "")) for s in (ko.get("narrative") or [])]
                         + [str((ko.get("closing") or {}).get("body", ""))])
    shared = sorted(_sentences(body) & _sentences(main_text))
    if shared:
        issues.append(f"네이버용 본문에 본진과 같은 문장이 {len(shared)}개 있습니다(유사문서) — 예: {shared[0][:40]}… 다른 문장으로 다시 쓰십시오.")
    if "**" in body:
        issues.append("네이버용 본문에 마크다운 볼드(**)가 있습니다 — 네이버 편집기는 그대로 찍습니다.")
    issues += position_issues(body)
    return issues


# 매거진(2026-09-13, 사용자: "두 번째 블로그는 blog.naver.com/jeunkim처럼 다양한 분야의 글을 잡지처럼").
# 참고 블로그 실측: 글마다 제목 → "📌 간단 브리핑"(요약 3~5줄) → 본문 3,700자 안팎 → "자료 출처". 하루 14편, 이웃 11만.
# 우리는 브리핑과 Fermata's Take 없이 표지 → 본문 → 자료 출처만 싣는다(사용자 결정, 2026-09-13 저녁).
# 그쪽 엔진은 외국 기사 전문 번역인데 그건 저작권 문제라 따라 하지 않는다 — 독자가 보는 모양만 가져오고,
# 본문은 출처 둘 이상을 종합해 우리 문장으로 쓴다(가이드와 같은 원칙, source_check가 본다).
MAGAZINE_SECTIONS = (4, 7)
MAGAZINE_CHARS = (2000, 4500)
# 2026-09-13 참고 블로그 210편 실측: 투자·시장 37%, AI·기술 15%, 기업·경영 13%, 심리 6%, 거시 5%, 과학 2%. "다양한 분야"의
# 실체는 금융 잡지에 과학·심리를 곁들인 것이다. 그래서 가장 큰 덩어리(해외 칼럼·리서치를 종합한 시장 이야기)를 코너로 둔다.
MAGAZINE_GROUPS = ("시장 읽기", "시장의 역사", "투자 심리", "기업과 기술", "과학", "돈의 상식", "만약에")


def magazine_issues(doc: dict) -> list[str]:
    """브리핑 줄 수·본문 길이·절 수·출처 표기·코너 — 잡지 한 편의 꼴. 본진에 안 가는 글이라 여기서만 본다."""
    issues: list[str] = []
    # 간단 브리핑(`brief`)은 2026-09-13 저녁 사용자 결정으로 싣지 않는다 — 있어도 검사하지 않고 올리는 쪽도 무시한다.
    if str(doc.get("group") or "") not in MAGAZINE_GROUPS:
        issues.append(f"코너(`group`)가 없거나 목록 밖입니다 — {', '.join(MAGAZINE_GROUPS)} 중 하나.")
    ko = doc.get("ko") or doc
    sections = ko.get("narrative") or []
    if not MAGAZINE_SECTIONS[0] <= len(sections) <= MAGAZINE_SECTIONS[1]:
        issues.append(f"본문이 {len(sections)}절입니다 — {MAGAZINE_SECTIONS[0]}~{MAGAZINE_SECTIONS[1]}절.")
    body = " ".join(str(s.get("body", "")) for s in sections)
    length = len(re.sub(r"<[^>]+>", "", body))
    if not MAGAZINE_CHARS[0] <= length <= MAGAZINE_CHARS[1]:
        issues.append(f"본문이 {length:,}자입니다 — {MAGAZINE_CHARS[0]:,}~{MAGAZINE_CHARS[1]:,}자.")
    if "**" in body:
        issues.append("본문에 마크다운 볼드(**)가 있습니다 — 네이버 편집기는 그대로 찍습니다.")
    if "번역" in body[:400]:
        issues.append("첫머리에 '번역'이 있습니다 — 이 글은 번역이 아니라 출처를 종합해 쓴 글입니다. 그렇게 쓰지 않았다면 다시 씁니다.")
    if not (doc.get("featured_photo") or {}).get("url"):
        issues.append("표지 사진(`featured_photo.url`)이 없습니다 — 참고 블로그는 글마다 사진 한 장. 대조표를 눈으로 보고 고른 Unsplash 주소.")
    issues += position_issues(body)
    return issues


def collect_issues_en(doc: dict, graphics: int | None = None) -> list[str]:
    """영어 가이드 전용 검사. 한국어 검사(제목 문법·문체·초보자 설명)는 영어에 맞지 않아 건너뛴다."""
    ko = doc.get("ko") or doc
    issues: list[str] = []
    title = str(ko.get("title") or "")
    if not title:
        return ["Title is missing."]
    if not (EN_TITLE_MIN <= len(title) <= EN_TITLE_MAX):
        issues.append(f"Title is {len(title)} characters — keep it between {EN_TITLE_MIN} and {EN_TITLE_MAX} "
                      f"so Google shows the whole thing.")
    sections = ko.get("narrative") or []
    floor = editorial_title.SECTION_FLOORS.get(str(doc.get("series") or "Guide"), 5)
    if len(sections) < floor:
        issues.append(f"{len(sections)} sections — an English guide needs at least {floor}.")
    for index, section in enumerate(sections, start=1):
        heading = str(section.get("heading") or "")
        if len(heading) > 80:
            issues.append(f"Heading {index} is {len(heading)} characters — keep headings under 80.")
        if len(str(section.get("body") or "")) < 300:
            issues.append(f"Section {index} is under 300 characters — answer the question, do not list it.")
    body = " ".join(str(s.get("body", "")) for s in sections) + str((ko.get("closing") or {}).get("body", ""))
    if not re.search(r"\b20\d\d\b", body):
        issues.append("The body never states a year — evergreen guides must say when the rules were checked "
                      "(for example 'as of September 2026').")
    if re.search(r"[가-힣]", title + body):
        issues.append("Hangul found in an English guide — translate or transliterate it.")
    problem = radar_origin_issue(doc)
    if problem:                         # 본문이 아니라 기록용 필드라 한글 검사에 걸리지 않는다
        issues.append(problem)
    limits = SERIES_LIMITS.get(str(doc.get("series") or ""), {})
    min_graphics = limits.get("graphics", MIN_GRAPHICS)
    if graphics is not None and graphics < min_graphics:
        issues.append(f"{graphics} graphics — at least {min_graphics} are required.")
    return issues


def validate(doc: dict, graphics: int | None = None) -> None:
    issues = collect_issues(doc, graphics)
    if issues:
        raise ValueError("기준표 기준 검사 실패:\n- " + "\n- ".join(issues))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--graphics", type=int,
                        help="본문에 넣을 그림 장수(알면 함께 검사)")
    args = parser.parse_args()

    doc = json.loads(Path(args.path).read_text(encoding="utf-8"))
    notes: list[str] = []
    issues = collect_issues(doc, args.graphics, notes_out=notes)
    title = (doc.get("ko") or doc).get("title", "")
    series = str(doc.get("series") or "기준표")
    issues = editorial_title.collect_issues(doc, kind=series, notes_out=notes) + issues
    hooks = editorial_title.hook_names(title)
    print(f"제목: {title} ({len(title)}자)")
    print(f"후킹 장치: {', '.join(hooks) or '없음'}")
    for note in notes:
        print(f"  (참고) {note}")
    if not issues:
        print("가이드 검사 통과")
        return 0
    print("어긋난 항목:")
    for issue in issues:
        print(f"  - {issue}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
