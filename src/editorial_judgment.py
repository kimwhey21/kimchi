"""시황 원고의 **판단**(Fermata's Take + 확인 지점), **어제 판정**(review), **초보자 설명** 검사.

왜 (2026-09-08, 사용자 승인 "1~3번 진행하자")
------------------------------------------------
재테크농부와의 남은 차이는 "사람이 판단하고 책임지는 글"이다. 그래서 시황도
1. 마무리(Fermata's Take)를 한 절로 — 우리는 이렇게 봅니다 + 근거 + 언제 무엇으로 확인하겠다
   (`closing.check`: due·what). 확인 지점은 성적표에 자동으로 쌓인다(`scoreboard_sync`).
2. "어제 본 것, 오늘은 어땠나" 절 — 어제 글의 확인 지점을 오늘 결과로 판정한다(`review`).
3. 어려운 말이 세 개 이상이면 초보자 설명 한 토막.

관문(editorial_gate)은 막고, 발행(publish_editorial)은 경고만 남긴다 — 다른 문체 검사와 같다.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

from src import feature_checks

ROOT = Path(__file__).resolve().parent.parent
EDITORIAL = ROOT / "editorial"
VERDICTS = {"hit", "miss", "mixed"}
_SENTENCE_END = re.compile(r"[.!?。]|다\s|까\s|요\s")
_REVIEW_HEADING = re.compile(r"어제|지난 거래일|지난 장|전날")
MIN_TAKE_SENTENCES = 3


def previous_manuscript(market: str, date_str: str) -> dict | None:
    """같은 시장의 바로 전 원고(editorial/<market>_<date>.json, date < 오늘)."""
    files = sorted(p for p in EDITORIAL.glob(f"{market}_*.json") if p.stem < f"{market}_{date_str}")
    if not files:
        return None
    return json.loads(files[-1].read_text(encoding="utf-8"))


def _sentences(text: str) -> int:
    text = re.sub(r"<[^>]+>", "", text or "")
    return len([s for s in re.split(r"(?<=[.!?])\s+|\n\n", text.strip()) if s.strip()])


def collect_issues(doc: dict, previous: dict | None = None) -> tuple[list[str], list[str]]:
    """(막을 것, 참고). `doc`은 시황 원고 전체(market·date·ko·review)."""
    issues: list[str] = []
    notes: list[str] = []
    ko = doc.get("ko") or {}
    market, date_str = doc.get("market", ""), str(doc.get("date", ""))

    # 1. 판단 + 확인 지점
    closing = ko.get("closing") or {}
    body = str(closing.get("body", ""))
    if _sentences(body) < MIN_TAKE_SENTENCES:
        issues.append(
            f"Fermata's Take가 {_sentences(body)}문장입니다. 세 문장 이상 — 우리는 이렇게 봅니다(판단), "
            "왜 그렇게 보는지(근거), 언제 무엇으로 확인하겠다(확인 지점). 앞 내용 요약이 아닙니다.")
    check = closing.get("check") or {}
    due, what = str(check.get("due", "")), str(check.get("what", "")).strip()
    if not (due and what):
        issues.append(
            "closing.check가 없습니다. {\"due\": \"YYYY-MM-DD\", \"what\": \"무엇을 어떤 숫자로 확인할지\"} — "
            "이 확인 지점이 성적표(/scoreboard/)에 자동으로 올라가고, 다음 날 글이 판정합니다.")
    else:
        try:
            due_day = dt.date.fromisoformat(due)
            if date_str and due_day <= dt.date.fromisoformat(date_str):
                issues.append(f"closing.check.due({due})가 글 날짜({date_str}) 이후가 아닙니다.")
        except ValueError:
            issues.append(f"closing.check.due는 YYYY-MM-DD여야 합니다: {due!r}")
        if len(what) < 10:
            issues.append("closing.check.what이 너무 짧습니다 — 무엇을 어떤 숫자·기준으로 볼지 한 문장.")

    # 2. 어제 판정 — 전 원고에 확인 지점이 있을 때만 요구한다(옛 형식 글은 건너뜀)
    prev_check = ((previous or {}).get("ko") or {}).get("closing", {}).get("check") if previous else None
    if previous and prev_check:
        prev_date = str(previous.get("date", ""))
        review = doc.get("review") or {}
        if not review:
            issues.append(
                f"review가 없습니다. 어제 글({prev_date})의 확인 지점 '{str(prev_check.get('what',''))[:40]}'을 "
                "오늘 결과로 판정하세요 — {\"of_date\": \"" + prev_date + "\", \"verdict\": \"hit|miss|mixed\", "
                "\"result\": \"실제로 나온 것(숫자와 함께)\"}.")
        else:
            if str(review.get("verdict", "")) not in VERDICTS:
                issues.append(f"review.verdict는 hit·miss·mixed 중 하나입니다: {review.get('verdict')!r}")
            if len(str(review.get("result", "")).strip()) < 10:
                issues.append("review.result가 비었거나 짧습니다 — 실제로 나온 것을 숫자와 함께.")
            if str(review.get("of_date", "")) != prev_date:
                issues.append(f"review.of_date는 바로 전 원고의 날짜({prev_date})여야 합니다.")
        headings = [str(s.get("heading", "")) for s in ko.get("narrative") or []]
        if not any(_REVIEW_HEADING.search(h) for h in headings):
            issues.append(
                "'어제 본 것, 오늘은 어땠나' 절이 없습니다. 소제목에 '어제'·'지난 거래일'이 들어간 절에서 "
                "어제 글의 확인 지점이 실제로 어떻게 됐는지 씁니다(재테크농부의 '지난주 시장이 우리에게 남긴 것').")
    elif previous and not prev_check:
        notes.append(f"전 원고({previous.get('date')})에 확인 지점이 없어 어제 판정은 건너뜁니다(옛 형식).")

    # 3. 초보자 설명 + 포지션 화법 (기준표와 같은 함수)
    text = " ".join(str(s.get("body", "")) for s in ko.get("narrative") or [])
    text += " " + " ".join(str(s.get("body", "")) for s in (ko.get("insight_section") or {}).get("stories") or [])
    text += " " + body
    b_issues, b_notes = feature_checks.beginner_issues(text)
    issues += b_issues
    notes += b_notes
    issues += feature_checks.position_issues(text)
    return issues, notes
