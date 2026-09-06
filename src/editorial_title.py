"""제목이 시황 제목의 문법을 지키는지 봅니다.

왜 필요한가
-----------
2026-09-04에 제목 규칙을 정하고 `docs/editorial-style.md`에 적었지만, 그날 재보니
규칙을 전부 어긴 제목 네 개가 기존 검사를 그대로 통과했다 — 꼬리표를 단 제목,
29.91%를 30%로 반올림한 제목, 벤치마크가 한 번도 쓰지 않은 말을 지어낸 제목,
`왜 ~했을까?`로 되묻는 제목. 이 경로는 사람 검수 없이 바로 공개되므로, 문서에만
적힌 규칙은 지켜지리라는 근거가 "모델이 문서를 읽는다"뿐이었다.

기준의 출처
-----------
벤치마크(재테크농부) 제목 1,089개 중 **시황 계열 199개**를 세었다. 전체로 세면
종목 분석·자료 공지가 섞여 시황의 문법이 묻힌다.

  이유 144회(1위) 중 110회가 "~한 이유" 단정형
  첫 절에 숫자% 41% · 급등/급락 43% · 느낌표 32% · 물음표 34%
  길이 중앙값 48자(p25 38 · p75 56 · p90 64) · 존댓말 어미 4%
  "왜 ~했을까" 식 과거 되묻기는 199개 중 1개
  코앞 0회 · 문턱 0회 · 상한가 0회 · 폭등 7회(급등은 94회)

무엇을 일부러 보지 않는가
-------------------------
- 뼈대(`[종목 N% 급등!] + [~한 이유]`)를 강제하지 않는다. 벤치마크 제목의
  59%는 다른 모양이고, 좋은 제목을 한 형태로 몰면 매일 같은 제목이 나온다.
- 물음표·느낌표·숫자를 요구하지 않는다. 셋 다 절반이 안 된다.
- 영어판 제목은 보지 않는다. 이 문법은 한국어 블로그의 것이다.

즉 **하지 말라고 정한 것만** 막는다. 잘 쓰는 것은 문서와 사람의 몫이다.
"""
from __future__ import annotations

import re


class EditorialTitleError(ValueError):
    """제목이 시황 제목 문법에 어긋날 때 발생합니다."""


# 제목 끝의 꼬리표. 시장과 날짜는 제목 윗줄과 글 주소에 이미 있다.
_TRAILING_TAG = re.compile(r"[\[(][^\])]*(?:시황|브리핑|마감|\d+/\d+|\d+월\s*\d+일)[^\])]*[\])]\s*$")

# 과거를 되묻는 물음표. 설명해 주겠다는 약속이 아니라 퀴즈가 된다.
# 앞을 보는 질문(`반등할 수 있을까?`)은 막지 않는다.
_PAST_QUIZ = re.compile(r"왜\s*[^?]{0,25}?(?:했|았|었|졌|랐|렸|겼|onder)(?:을|나|는지)?까[요?]|왜\s*[^?]{0,25}?(?:했|았|었|졌|랐|렸)(?:나|는가)\s*\?")

# 존댓말 종결. 시황 제목의 4%뿐이라 기본값으로 삼지 않는다.
# 낱말을 나열해 두면 목록에 없는 형태가 그대로 빠져나갑니다 — `갈립니다`가
# 실제로 통과했습니다(2026-09-06). 하십시오체 종결은 전부 `니다`로 끝나므로
# 형태로 봅니다.
_POLITE_ENDING = re.compile(r"니다\s*[.!?]?\s*$")

# 벤치마크가 한 번도 쓰지 않은 말. 2026-09-04에 셋 다 지어내 썼다.
_INVENTED = {
    "코앞": "벤치마크 제목 1,089개에 0회입니다.",
    "문턱": "벤치마크 제목 1,089개에 0회입니다.",
    "상한가": "벤치마크 제목 1,089개에 0회입니다(미국 시장에는 없는 제도입니다).",
}

_ROUND_HINT = re.compile(r"^(?:대\b|대\s|가까이|안팎|남짓|넘게|이상|미만|가량|쯤)")
# 이름과 등락률 사이에 올 수 있는 것: 조사·부호·공백뿐입니다. 사이에 다른 낱말이
# 끼면 그 숫자는 남의 것입니다("테슬라 -6%, 나스닥 -2%"에서 -2%는 나스닥의 것).
_NAME_TO_PCT = re.compile(r"^[은는이가도의을를,\s]*[+\-−]?\s*(\d+(?:\.\d+)?)\s*%")


def _rounded_from_actual(title: str, price_data: dict) -> list[str]:
    """제목에 적은 종목의 등락률을 어림수로 쓴 경우를 잡습니다.

    `editorial_facts`는 소수점 없는 비율을 일부러 건너뜁니다 — 본문의 "5%대 상승"
    같은 어림수는 정상이기 때문입니다. 그래서 제목에 "30% 급등"이라고 쓰면
    실제가 29.91%여도 대조를 빠져나갑니다. 제목은 그 예외를 두지 않습니다.

    **이름 바로 뒤에 붙은 숫자만** 봅니다. 시세에서 비슷한 값을 찾아 붙이면
    제목에 없는 종목의 숫자를 끌어옵니다 — "인텔 7% 급등"에 (워치리스트에 있는)
    S-Oil의 6.36%가 붙는 식입니다. 실측으로 확인한 오탐입니다.

    `5%대`, `10% 가까이`처럼 어림수임을 밝힌 표현은 그대로 둡니다.
    """
    entries = list((price_data.get("watchlist") or {}).values())
    entries += list((price_data.get("macro") or {}).values())
    names = sorted(
        ((str(e.get("name") or ""), e) for e in entries if e.get("name")),
        key=lambda p: len(p[0]),
        reverse=True,
    )

    issues: list[str] = []
    claimed: list[tuple[int, int]] = []
    for name, entry in names:
        at = title.find(name)
        if at < 0 or any(s <= at < e for s, e in claimed):
            continue
        end = at + len(name)
        claimed.append((at, end))
        match = _NAME_TO_PCT.match(title[end:])
        if not match:
            continue
        raw = match.group(1)
        if "." in raw:
            continue  # 소수점이 있으면 editorial_facts가 시세와 대조합니다
        if _ROUND_HINT.match(title[end + match.end() :].lstrip()):
            continue  # "5%대", "10% 가까이"는 어림수임을 밝힌 표현입니다
        actual = abs(float(entry["change_pct"]))
        if round(actual, 2) == float(raw):
            continue  # 마침 딱 떨어지는 값입니다
        issues.append(
            f"제목의 '{name} {raw}%'는 어림수입니다. 실제 등락률 {actual:.2f}%를 "
            "그대로 쓰세요 — 반올림하면 시세 대조 검사가 그 숫자를 건너뜁니다."
        )
    return issues


def collect_issues(doc: dict, price_data: dict | None = None) -> list[str]:
    """한국어 제목에서 어긴 규칙을 모읍니다."""
    title = str(doc.get("title") or "").strip()
    if not title:
        return []

    issues: list[str] = []

    if _TRAILING_TAG.search(title):
        issues.append(
            "제목 끝의 꼬리표를 빼세요. 시장과 날짜는 제목 바로 윗줄과 글 주소에 "
            "이미 있어, 목록에서도 검색 결과에서도 같은 말이 두 번 보입니다."
        )

    if _PAST_QUIZ.search(title):
        issues.append(
            "'왜 ~했을까?'는 지나간 일을 퀴즈로 냅니다. 벤치마크 시황 제목 199개 중 "
            "1개뿐입니다. '~한 이유'로 끊어 설명해 주겠다고 약속하거나, "
            "'반등할 수 있을까?'처럼 앞을 보는 질문으로 쓰세요."
        )

    if _POLITE_ENDING.search(title):
        issues.append(
            "제목을 존댓말로 끝내지 마세요. 시황 제목의 4%뿐입니다. "
            "명사형으로 끊거나('~한 이유.') 반말로 단정하세요('~ 뒤집었다')."
        )

    for word, why in _INVENTED.items():
        if word in title:
            issues.append(f"제목의 '{word}'는 지어낸 말입니다 — {why}")

    if price_data:
        issues += _rounded_from_actual(title, price_data)

    return issues


def validate(doc: dict, price_data: dict | None = None) -> None:
    """제목 문법에 어긋나면 발행을 중단합니다."""
    issues = collect_issues(doc, price_data)
    if issues:
        raise EditorialTitleError(
            f"제목 문법 검사 실패 — {doc.get('title')!r}\n- " + "\n- ".join(issues)
        )
