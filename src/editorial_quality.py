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
    (
        # '타격'은 '받다/입다'와 결합합니다. '타격을 맞다'는 어울리지 않는
        # 조합입니다. 반면 '직격탄을 맞다'는 맞는 표현이라 여기서 걸리지 않습니다
        # (직격탄은 날아와 맞는 것, 타격은 받거나 입는 것).
        re.compile(r"타격을\s*맞"),
        "'타격을 맞다'가 아니라 '타격을 받다' 또는 '타격을 입다'로 쓰세요.",
    ),
)


# 등락을 말할 때 쓰는 '내리다'. 벤치마크 본문 60편을 세어 보니 하락 계열이
# 523회(하락 425 · 하락했 72 · 하락한 26)인데 내리- 계열은 53회로 10배 차이였다.
# 우리 원고는 반대로 '내렸습니다'가 기본값이었다.
#
# 다만 '내리다'가 전부 등락은 아니라서, 아래 세 갈래는 그대로 둔다.
#   - 금리를 내리다  : 인하이지 하락이 아니다
#   - 끌어내리다      : 다른 합성어다("지수를 끌어내린 쪽")
#   - 내려가다/내려오다/내려서다 : 다른 동사다("8만 달러 아래로 내려갔습니다")
# '내려' 뒤에 보조동사가 붙으면 '내려가다/내려오다/내려서다'라는 다른 동사다.
# 내려가다·내려오다·내려서다·내려놓다·내려두다·내려주다는 등락이 아니라 다른 동사다.
# 어미까지 다 열거하려다 빠뜨린 적이 있어(내려'온'이 빠져 "인상 확률이 내려온
# 자리에서"가 걸렸다) 어간 음절 블록 전체를 제외한다 — 가~갛은 '가'로 시작하는
# 모든 활용형(가·갔·갈·간·감…)을 한 번에 덮는다.
_DECLINE_VERB = re.compile(
    r"내(렸|린|려(?![가-갛오-옿와-왛서-섷노-놓두-둫주-줗]))"
)
_NOT_A_DECLINE = re.compile(r"(금리|결론|판단|평가|명령|지시|처방|진단|끌어)")
# 창이 좁으면 "금리를 0.25%포인트 내렸습니다"에서 '금리'를 놓친다.
_DECLINE_WINDOW = 28


def _decline_wording(field: str, text: str) -> list[str]:
    """등락을 '내렸다'로 쓴 자리를 모읍니다."""
    issues: list[str] = []
    for match in _DECLINE_VERB.finditer(text):
        before = text[max(0, match.start() - _DECLINE_WINDOW) : match.start()]
        if _NOT_A_DECLINE.search(before):
            continue
        snippet = text[max(0, match.start() - 18) : match.end() + 6].strip()
        issues.append(
            f"{field} '...{snippet}...': 등락은 '하락했습니다'로 씁니다. "
            "'내렸습니다'는 벤치마크 본문에서 하락 계열의 10분의 1로만 쓰입니다. "
            "(금리 인하·끌어내리다·내려가다는 그대로 두세요.)"
        )
    return issues


# 우리 쪽 장치 이름. 읽는 사람에게는 뜻이 없고, 글을 시스템 설명서처럼 만든다.
# "이날 워치리스트에서 가장 큰 상승 폭입니다"는 그 종목이 그날 시장 전체에서
# 1등이었다는 말이 아니라 우리 목록 안에서 1등이었다는 말인데, 읽는 사람은
# 그 목록을 모른다. 범위를 밝히려면 '우리가 보는 종목 가운데'처럼 쓴다.
_INTERNAL_JARGON = re.compile(r"(워치리스트|watchlist|동적 편입|코어 종목|dynamic 편입)", re.IGNORECASE)

# 벤치마크가 한 번도 쓰지 않은 말. 제목뿐 아니라 본문·소제목에서도 막습니다 —
# 2026-09-04에 '코앞'·'문턱'을 제목에서 걸렀더니, 다음 날 자동 발행 원고가
# 소제목에 '반대편'을 썼습니다(제가 쓴 '외국인 – ...' 형식을 보고 따라 만든
# 것이라, 제 실수가 매일 복제되는 구조였습니다).
#
# 세어 본 결과: 반대편은 본문 60편·제목 1,089개에 0회. 같은 뜻으로 그쪽이
# 쓰는 말은 약세(113회)·부진(63회)·반대로(47회)입니다.
_NEVER_USED = {
    "반대편": "약세·부진·반대로를 쓰세요 (본문 60편·제목 1,089개에 0회).",
    "코앞": "제목 1,089개에 0회입니다.",
    "문턱": "제목 1,089개에 0회입니다.",
}


def _invented(field: str, text: str) -> list[str]:
    return [
        f"{field}: '{word}'는 벤치마크가 쓰지 않는 말입니다 — {why}"
        for word, why in _NEVER_USED.items()
        if word in text
    ]


def _jargon(field: str, text: str) -> list[str]:
    match = _INTERNAL_JARGON.search(text)
    if not match:
        return []
    return [
        f"{field}: '{match.group()}'는 우리 쪽 장치 이름이라 글에 쓰지 않습니다. "
        "범위를 밝혀야 하면 '우리가 보는 종목 가운데'처럼 쓰세요."
    ]


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
        issues += _decline_wording(field, text)
        issues += _jargon(field, text)
        issues += _invented(field, text)
    return issues


def validate_generated(generated: dict) -> None:
    """편집 기준에 어긋난 문구가 있으면 발행 파이프라인을 중단합니다."""
    issues = collect_issues(generated)
    if issues:
        raise EditorialQualityError("한국어 편집 품질 검사 실패:\n- " + "\n- ".join(issues))
