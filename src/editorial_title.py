"""제목·소제목 규칙 — **블로그에 올라가는 모든 글**(시황·기준표·프리뷰·가이드)이 같은 것을 씁니다.

한 곳에 두는 이유 (2026-09-08)
------------------------------
사용자: "제목과 소제목 규칙은 블로그에 올라가는 모든 글에 적용되어야 한다. 따로
나뉘어 있으면 매번 수정을 해야 한다." 전에는 후킹 장치·절 수·소제목 길이가
feature_checks(기준표·프리뷰)와 editorial_quality(시황)에 따로 있었고 문서도 셋이었다.
이제 이 모듈 하나가 제목과 소제목을 다 보고, 시황(publish_editorial·editorial_gate)·
기준표·프리뷰(feature_gate)·가이드(publish_guide)가 같은 `collect_issues`를 부른다.
글 종류에 따라 다른 것은 **절 수 하한(SECTION_FLOORS)뿐**이다. 규칙은 여기와
docs/editorial-style.md 「제목 문법」·「소제목」 절에서만 고친다.


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

import functools
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


class EditorialTitleError(ValueError):
    """제목이 시황 제목 문법에 어긋날 때 발생합니다."""


# 제목 끝의 꼬리표. 시장과 날짜는 제목 윗줄과 글 주소에 이미 있다.
_TRAILING_TAG = re.compile(r"[\[(][^\])]*(?:시황|브리핑|마감|\d+/\d+|\d+월\s*\d+일)[^\])]*[\])]\s*$")

# 과거를 되묻는 물음표. 설명해 주겠다는 약속이 아니라 퀴즈가 된다.
# 앞을 보는 질문(`반등할 수 있을까?`)은 막지 않는다.
_PAST_QUIZ = re.compile(r"왜\s*[^?]{0,25}?(?:했|았|었|졌|랐|렸|겼|onder)(?:을|나|는지)?까[요?]|왜\s*[^?]{0,25}?(?:했|았|었|졌|랐|렸)(?:나|는가)\s*\?")

# 존댓말 종결. 시황 제목의 4%뿐이라 기본값으로 삼지 않는다.
# 하십시오체 종결은 전부 `니다`로 끝납니다. **이 검사는 막지 않습니다.**
#
# 전에는 "시황 제목의 존댓말 어미는 4%뿐"이라는 옛 표본을 근거로 차단했습니다.
# 2026-09-06에 최근 시황 46편을 다시 세니 15%가 존댓말로 끝났습니다 —
# `미국 주식 급등 이유, 오늘이 매우 중요합니다`, `내일 고용보고서가 결정합니다`.
# 벤치마크가 실제로 쓰는 어법을 우리만 금지하고 있었습니다. 드문 것과 틀린 것은
# 다르므로 상수는 남기되(다른 검사가 참고합니다) 차단은 하지 않습니다.
_POLITE_ENDING = re.compile(r"니다\s*[.!?]?\s*$")

# 벤치마크가 한 번도 쓰지 않은 말. 2026-09-04에 셋 다 지어내 썼다.
_INVENTED = {
    "코앞": "벤치마크 제목 1,089개에 0회입니다.",
    "문턱": "벤치마크 제목 1,089개에 0회입니다.",
    "상한가": "벤치마크 제목 1,089개에 0회입니다(미국 시장에는 없는 제도입니다).",
}

# 제목 속 등락률. 벤치마크 최근 104편(2026-08-06~09-05)에서 등락률이 둘 이상인
# 제목은 0개, 하나인 제목도 12개뿐이다(88%는 숫자% 없음). 우리는 9/7·9/8 이틀 연속
# "A 8.47% 급등, B 5.78% 급락. 코스피가 0.58% 하락한 이유."처럼 셋을 나열했고,
# 사용자가 "재테크농부처럼 나왔으면 좋겠다"고 짚었다(2026-09-08). 숫자 나열은
# 이야기가 아니라 시세표다.
_PCT = re.compile(r"[+\-−]?\d+(?:\.\d+)?\s*%")

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


# ── 후킹 장치 (모든 글) ────────────────────────────────────────────────────────
# 기준표 검사(2026-09-06)의 다섯 유형에, 시황 제목이 실제로 쓰는 둘(설명 약속·기록/고비)을
# 더했다. 재테크농부 최근 104편(2026-08-06~09-05)에 돌리면 98편이 걸리고, 빠진 여섯은
# "SK하이닉스 매도 인증" 같은 계좌 공지다 — 우리가 쓰지 않는 종류다. `코스피는
# 하락했습니다`처럼 아무 장치도 없는 제목은 안내문이지 제목이 아니다.
HOOKS = {
    "설명 약속": r"이유|비결|이렇게 (?:봅니다|합니다|대응|보|하)|이것입니다|정리했",
    "약속+반전": (r"그러나|하지만|그런데|인데도|했는데|지만,|아니다|아닙니다|아니었다"
                r"|반대로|정반대|오히려|만 무너|만 빠|만 올|만 하락|만 상승|그래도|여전히"),
    "미해결 질문": r"\?|할까|될까|일까|갈린다|갈립니다|정한다|정합니다|결정",
    "범위 축소": r"\d\s*가지|[한두세네]\s*가지|다섯 가지|여섯 가지|딱 \d|가지만|하나만|둘만|만 보세요|만 체크|만 확인",
    "시한 압박": r"\d+분 뒤|오늘|내일|이번 ?주|다음 ?주|\d+월 \d+일|지금|이제|하반기|앞두고|다가온|시작",
    "권위+반전": r"증권사|월가|기관|헤지펀드|CEO|내부자|외국인|개미|정부",
    "기록·고비": (r"사상 최고|최고치|최저치|신고가|저점|만에|급등|급락|폭락|폭등|재돌파|\d+(?:\.\d+)?%"
                r"|반등|무너|흔들|위험|경고|조심|주의|절대|필수|중요|\d,\d{3}선|선 앞|선을|고비|턱밑|눈앞"
                r"|\d+(?:일|주|달|년)째|[이사]틀째|사흘째|나흘째|닷새째|연속"),
}

# 제목의 지표 용어. 벤치마크 100편 제목 중 PER이 든 것은 1편뿐 — 드문 것이지 틀린 것은
# 아니라서 **알려만 준다**(notes_out).
JARGON = ("FWD PER", "PER", "EPS", "PBR", "ROE", "밸류에이션", "컨센서스",
          "가이던스", "CAPEX", "FWD")

# ── 소제목·절 수 (모든 글) ─────────────────────────────────────────────────────
# 벤치마크 최근 104편의 번호 소제목 556개: 길이 중앙값 23자, p75 32자, 4~8자 명사 토막은
# 4%뿐. 편당 개수 중앙값 14(p25 12). 우리 9/8 한국장은 6절, 소제목 30~35자였다.
HEADING_MAX_CHARS = 32
HEADING_MIN_CHARS = 6      # "1. 지금 숫자"(5자) 같은 슬라이드 라벨 — 드문 것이라 알려만 준다
SECTION_FLOORS = {"시황": 8, "기준표": 5, "프리뷰": 3, "가이드": 5}
_HEADING_NUMBER = re.compile(r"^\s*\d{1,2}\.\s*")

# 소제목의 "꼴" (2026-09-08, 사용자: "재테크농부의 표현 방법과 말투를 잘 보고 배워야 한다.
# 사람이 쓴 것처럼 보여야 한다. AI 같은 표현은 안 된다.")
#
# 재테크농부 소제목 462개를 꼴로 나누면 — 완전한 문장(~습니다) 46% · 짧은 이름표(`오늘
# 투자심리`, `프리장 주요 종목`) 33% · 질문 8% · 반말 문장 4% · "수식절+명사" 6%(그것도
# `반도체주가 다시 흔들린 이유`처럼 이유·방법·영향으로 끝남) · "…한 것" 0.6%.
# 우리 최근 66개는 "수식절+명사"가 24%(`가속으로 답한 스노우플레이크`, `예상을 넘고도
# 하락한 브로드컴`), "…한 것" 4%(`엔비디아가 산 것`), "…고, …고" 4%(`메모리는 오르고,
# 설계는 내리고`)였다. 이 셋이 기계가 뽑은 헤드라인처럼 읽히는 지점이다.
# 회사 이름으로 끝나는 헤드라인 꼴만 **막고**, 보통 명사(`너무 강했던 고용`)는 알려만 준다 —
# 벤치마크에도 후자는 있다. 회사 이름은 두 시장의 워치리스트 설정(코어·한글 표기표)과
# 그날 시세(편입 종목)에서 온다.
_HEADLINE_TAIL = re.compile(
    r"[가-힣]{1,8}(?:한|된|린|른|난|온|본|친|든|산|던|운|긴|킨|쓴|준|센|낸|깬)\s+([A-Za-z가-힣()·]+)$")
_SENTENCE_END = re.compile(r"(?:습니다|입니다|합니다|됩니다|다|요|까|나|\?|!)\s*$")
_NOMINAL_END = re.compile(r"([가-힣]+)\s?것\s*$")


@functools.lru_cache(maxsize=1)
def _configured_names() -> frozenset[str]:
    names: set[str] = set()
    for market in ("kr", "us"):
        path = ROOT / "config" / f"watchlist_{market}.yaml"
        if not path.exists():
            continue
        config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for row in config.get("watchlist") or []:
            for key in ("name", "name_en"):
                if row.get(key):
                    names.add(str(row[key]).strip())
        for value in (config.get("name_ko_map") or {}).values():
            names.add(str(value).strip())
    return frozenset(n for n in names if n)


def _headline_shape(bare: str, names: frozenset[str] | set[str]) -> tuple[bool, str] | None:
    """`가속으로 답한 스노우플레이크`처럼 [수식절]+[이름]으로 끝나는 헤드라인 꼴.

    (막는가, 안내문)을 돌려준다. 끝 낱말이 회사 이름이면 막고, 보통 명사면 알려만 준다.
    """
    if _SENTENCE_END.search(bare):
        return None
    match = _HEADLINE_TAIL.search(bare)
    if not match:
        return None
    tail = match.group(1).strip("()·")
    company = any(tail == n or tail.endswith(n) for n in names if len(n) >= 2)
    text = ("수식절로 꾸민 이름으로 끝나는 헤드라인 꼴입니다(우리 24%, 벤치마크 6%뿐이고 그마저 "
            "`~한 이유`·`~하는 방법`). 사람이 말하듯 문장으로 쓰세요 — "
            "`예상을 넘고도 하락한 브로드컴` → `브로드컴은 예상을 넘기고도 하락했습니다`, "
            "짧게 가려면 이름표로 — `브로드컴 실적`.")
    return company, text


def hook_names(title: str) -> list[str]:
    return [name for name, pattern in HOOKS.items() if re.search(pattern, title)]


# `초보자 설명: 순매수는 …`처럼 본문 블록의 라벨을 소제목에 올린 것(2026-09-08, 기준표
# 시험 실행). `라벨: 내용` 꼴 자체는 재테크농부도 쓴다(`실적 성적표: 무엇이 예상을 넘었나`) —
# 막는 것은 초보자 설명·요약·참고처럼 **문단 첫머리에 다는 라벨**이 소제목이 된 경우다.
# 그것은 기계가 표에 붙인 제목처럼 읽힌다. 콜론 뒤에 띄어쓰기가 있을 때만 잡는다.
_BLOCK_LABEL_HEADING = re.compile(
    r"^(?:초보자(?:용)?(?:\s*설명)?|요약|한\s*줄\s*요약|참고|주의|정리|핵심\s*정리|팁|TIP)\s*[:：]\s+\S", re.I)


def collect_heading_issues(sections: list, kind: str | None = None,
                           min_sections: int | None = None,
                           notes_out: list[str] | None = None,
                           names: set[str] | frozenset[str] | None = None) -> list[str]:
    """절 수·소제목 길이·꼴. 글 종류(kind)는 절 수 하한만 정합니다.

    `names`는 헤드라인 꼴 판정에 쓰는 회사 이름(없으면 워치리스트 설정에서).
    """
    issues: list[str] = []
    names = _configured_names() | set(names or ())
    floor = min_sections if min_sections is not None else SECTION_FLOORS.get(str(kind or ""))
    if floor and len(sections) < floor:
        hint = (" 긴 절을 쪼개고 지수·업종·수급·주인공 종목·환율·유가·다음 거래일처럼 절마다 "
                "하나만 말하세요(벤치마크 편당 소제목 중앙값 14개)." if kind == "시황" else "")
        issues.append(f"절이 {len(sections)}개입니다 — {kind or '이 글'}은 {floor}개 이상 씁니다.{hint}")
    for index, section in enumerate(sections, start=1):
        bare = _HEADING_NUMBER.sub("", str(section.get("heading", ""))).strip()
        if len(bare) > HEADING_MAX_CHARS:
            issues.append(
                f"소제목 {index} '{bare}'이(가) {len(bare)}자입니다 — {HEADING_MAX_CHARS}자 이하로 "
                "줄이세요(벤치마크 중앙값 23자). 절반쯤은 명사구로 끊습니다 — `오늘 투자심리`, "
                "`움직이는 주요 종목`, `케빈 워시 의장은 무슨 말을 했나`.")
        if _BLOCK_LABEL_HEADING.match(bare):
            issues.append(f"소제목 {index} '{bare}': 본문 블록의 라벨('초보자 설명:' 등)을 소제목에 올렸습니다 — "
                          "기계가 표에 붙인 제목처럼 읽힙니다. 라벨은 본문 문단 첫머리에 두고, 소제목은 "
                          "그 절이 하는 말로 쓰세요(`순매수는 지수를 이렇게 움직입니다`).")
        if re.search(r"[고,]\s*$", bare):
            issues.append(f"소제목 {index} '{bare}': '…고, …고'로 끝나는 대구(對句)입니다. 벤치마크 "
                          "소제목 462개에 0개 — 한 문장으로 말하세요(`메모리는 올랐고 설계주는 하락했습니다`).")
        nominal = _NOMINAL_END.search(bare)
        if nominal and not nominal.group(1).endswith(("할", "볼", "일")):
            issues.append(f"소제목 {index} '{bare}': '…한 것'으로 끝나는 명사절입니다(벤치마크 0.6%). "
                          "무엇인지 문장으로 말하세요 — `엔비디아가 산 것` → `엔비디아는 전력 회사를 샀습니다`.")
        shape = _headline_shape(bare, names)
        if shape:
            blocking, text = shape
            if blocking:
                issues.append(f"소제목 {index} '{bare}': {text}")
            elif notes_out is not None:
                notes_out.append(f"소제목 {index} '{bare}': {text}")
        if 0 < len(bare) < HEADING_MIN_CHARS and notes_out is not None:
            notes_out.append(f"소제목 {index} '{bare}'은(는) {len(bare)}자 명사 토막입니다 — "
                             "슬라이드 라벨처럼 읽힙니다(벤치마크 4%). 그 절이 무슨 말을 하는지 드러나게 쓰십시오.")
    return issues


def collect_title_issues(title: str, price_data: dict | None = None,
                         notes_out: list[str] | None = None) -> list[str]:
    """제목 하나의 규칙 위반 목록."""
    title = str(title or "").strip()
    if not title:
        return []
    issues: list[str] = []

    if _TRAILING_TAG.search(title):
        issues.append(
            "제목 끝의 꼬리표를 빼세요. 시장과 날짜는 제목 바로 윗줄과 글 주소에 "
            "이미 있어, 목록에서도 검색 결과에서도 같은 말이 두 번 보입니다.")

    if _PAST_QUIZ.search(title):
        issues.append(
            "'왜 ~했을까?'는 지나간 일을 퀴즈로 냅니다. 벤치마크 시황 제목 199개 중 "
            "1개뿐입니다. '~한 이유'로 끊어 설명해 주겠다고 약속하거나, "
            "'반등할 수 있을까?'처럼 앞을 보는 질문으로 쓰세요.")

    if len(_PCT.findall(title)) >= 2:
        issues.append(
            "제목에 등락률이 둘 이상입니다. 벤치마크 최근 104편 중 등락률이 둘 이상인 "
            "제목은 0개이고 하나인 제목도 12개뿐입니다. 숫자를 나열하지 말고 그날의 "
            "이야기 하나로 쓰세요 — `반도체 주식 급락, 고점 신호일까?`, "
            "`다시 커지는 이란 위험, 반도체만 상승한 이유`, "
            "`미국 증시 사상 최고치, 그런데 AMD와 스페이스X는 급락했습니다`.")

    for word, why in _INVENTED.items():
        if word in title:
            issues.append(f"제목의 '{word}'는 지어낸 말입니다 — {why}")

    if not hook_names(title):
        issues.append(
            f"제목에 후킹 장치가 없습니다: {title!r} — 일곱 유형 중 하나는 있어야 합니다"
            f"({', '.join(HOOKS)}). `코스피는 하락했습니다`는 안내문입니다. "
            "`~한 이유`, `그런데 ~`, `~일까?`, `N가지`, `오늘 밤`, `외국인`, `사상 최고치` 같은 "
            "장치 하나로 읽을 이유를 만드세요. docs/editorial-style.md 「제목 문법」.")

    if notes_out is not None and len(title) > 35:
        notes_out.append(f"제목이 {len(title)}자입니다 — 벤치마크 최근 104편 중앙값은 25자이고 35자 안쪽이 보통입니다.")
    if notes_out is not None:
        for word in JARGON:
            if word in title:
                notes_out.append(
                    f"제목에 지표 용어 {word!r}가 있습니다. 벤치마크 100편 중 1편만 "
                    "이렇게 씁니다 — 누구나 아는 말로 바꿀 수 있는지 한 번 보십시오.")
                break

    if price_data:
        issues += _rounded_from_actual(title, price_data)
    return issues


def collect_issues(doc: dict, price_data: dict | None = None, *,
                   kind: str | None = None, min_sections: int | None = None,
                   notes_out: list[str] | None = None) -> list[str]:
    """제목 + 소제목 규칙을 한 번에. 모든 발행 경로가 이 함수를 부릅니다.

    `doc`은 `{"title", "narrative", ...}`(시황의 ko) 또는 `{"ko": {...}}`(기준표·프리뷰)
    둘 다 받습니다. `kind`는 절 수 하한(SECTION_FLOORS)에만 쓰입니다.
    """
    ko = doc.get("ko") if isinstance(doc.get("ko"), dict) else doc
    issues = collect_title_issues(ko.get("title", ""), price_data, notes_out=notes_out)
    names: set[str] = set()
    for entry in (price_data or {}).get("watchlist", {}).values():
        for key in ("name", "name_en"):
            if entry.get(key):
                names.add(str(entry[key]).strip())
    issues += collect_heading_issues(ko.get("narrative") or [], kind=kind,
                                     min_sections=min_sections, notes_out=notes_out, names=names)
    return issues


def validate(doc: dict, price_data: dict | None = None, **kwargs) -> None:
    """제목·소제목 규칙에 어긋나면 예외 — 루틴 관문에서 씁니다(발행 단계는 경고만)."""
    issues = collect_issues(doc, price_data, **kwargs)
    if issues:
        ko = doc.get("ko") if isinstance(doc.get("ko"), dict) else doc
        raise EditorialTitleError(
            f"제목·소제목 검사 실패 — {ko.get('title')!r}\n- " + "\n- ".join(issues))
