"""한국어 시황의 번역투·상투 표현을 발행 전에 차단합니다."""
from __future__ import annotations

import re


class EditorialQualityError(ValueError):
    """원고가 저장소의 한국어 편집 기준을 통과하지 못했을 때 발생합니다."""


_AWKWARD_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"(?:\d{1,2}월|이번\s*달|한\s*달|이번\s*주|한\s*주)을\s*"
            r"(?:강세|약세|상승|하락)로\s*(?:닫|마감)"
        ),
        "기간을 '강세/약세로 닫다'라고 쓰지 말고 실제 거래일의 상승·하락을 직접 쓰세요.",
    ),
    (
        re.compile(r"(?:증시|시장|지수)(?:는|가)\s*(?:물러섰|숨을\s*골랐|휘청였)"),
        "시장 의인화 표현 대신 '상승/하락/보합 마감'처럼 움직임을 직접 쓰세요.",
    ),
    (
        re.compile(r"(?:증시|시장|지수)(?:를|가|는).*?(?:붉게|파랗게)\s*물들"),
        "색깔 비유 대신 상승·하락 폭을 직접 쓰세요.",
    ),
    (
        # "듀레이션이 긴 자산부터 맞았습니다"처럼 **목적어 없이** 쓴 '맞다'.
        # 영어의 hit/hammered를 그대로 옮기면 나오는 형태이고, 무엇에 맞았는지가
        # 빠져 있어 한국어로는 문장이 성립하지 않습니다.
        #
        # 반대로 "반도체가 직격탄을 맞았습니다"는 막지 않습니다. '직격탄을 맞다',
        # '타격을 입다'처럼 목적어가 있는 관용구는 한국어 경제 기사에서 자연스럽게
        # 쓰는 표현입니다. 그래서 주어 뒤에 조사만 오고 바로 '맞았'이 붙는 경우만
        # 잡습니다 — 사이에 '~을/를'이 들어가면 걸리지 않습니다.
        re.compile(
            r"(?:자산|지수|종목|증시|주가|섹터|업종|기술주|반도체)"
            r"(?:[가-힣]{0,4}(?:부터|까지|들|이|가|은|는|도|만))?\s*맞았"
        ),
        "무엇에 맞았는지 없이 '맞았다'만 쓰지 마세요. "
        "'낙폭이 컸다', '먼저 하락했다'처럼 직접 쓰거나 '직격탄을 맞았다'처럼 목적어를 넣으세요.",
    ),
)


def collect_issues(generated: dict) -> list[str]:
    """제목·소제목과 본문에서 어색한 한국어 표현을 찾아 설명 목록으로 반환합니다.

    전에는 제목과 소제목만 봤습니다. 그런데 금지하려는 표현은 본문에 써도
    똑같이 어색하고, 실제로 소제목에서 한 번 걸러낸 뒤에도 본문에 남는 일이
    있었습니다. 그래서 본문 문단과 마무리까지 함께 검사합니다.
    """
    fields: list[tuple[str, str]] = [("제목", str(generated.get("title", "")))]
    for index, section in enumerate(generated.get("narrative") or [], start=1):
        fields.append((f"본문 소제목 {index}", str(section.get("heading", ""))))
        fields.append((f"본문 {index}", str(section.get("body", ""))))
    for key, label in (("outlook", "전망 본문"), ("closing", "마무리 본문")):
        fields.append((label, str((generated.get(key) or {}).get("body", ""))))
    for index, story in enumerate(
        (generated.get("insight_section") or {}).get("stories") or [], start=1
    ):
        fields.append((f"인사이트 본문 {index}", str(story.get("body", ""))))

    for key, label in (
        ("theme_section", "테마 소제목"),
        ("stock_section", "종목 소제목"),
        ("outlook", "전망 소제목"),
        ("closing", "마무리 소제목"),
        ("insight_section", "인사이트 소제목"),
    ):
        section = generated.get(key) or {}
        fields.append((label, str(section.get("heading", ""))))
        if key == "insight_section":
            for index, story in enumerate(section.get("stories") or [], start=1):
                fields.append((f"인사이트 제목 {index}", str(story.get("heading", ""))))

    issues: list[str] = []
    for field, text in fields:
        for pattern, guidance in _AWKWARD_PATTERNS:
            if pattern.search(text):
                issues.append(f"{field} '{text}': {guidance}")
    return issues


def validate_generated(generated: dict) -> None:
    """편집 기준에 어긋난 문구가 있으면 발행 파이프라인을 중단합니다."""
    issues = collect_issues(generated)
    if issues:
        raise EditorialQualityError("한국어 편집 품질 검사 실패:\n- " + "\n- ".join(issues))
