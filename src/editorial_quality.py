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
)


def collect_issues(generated: dict) -> list[str]:
    """제목과 소제목에서 어색한 한국어 표현을 찾아 설명 목록으로 반환합니다."""
    fields: list[tuple[str, str]] = [("제목", str(generated.get("title", "")))]
    for index, section in enumerate(generated.get("narrative") or [], start=1):
        fields.append((f"본문 소제목 {index}", str(section.get("heading", ""))))

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
