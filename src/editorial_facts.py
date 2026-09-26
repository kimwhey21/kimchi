"""원고가 인용한 종목 등락률이 시세와 맞는지, 그날 주인공을 다뤘는지 봅니다.

왜 필요한가
-----------
`editorial_quality`는 번역투·의인화 같은 **형식**만 봅니다. 그래서 다음 두 가지를
잡지 못했습니다.

- 2026-09-02 미국장 원고는 그날 15.81% 오른 델을 한 번도 언급하지 않았습니다.
  워치리스트에 없어 글쓴이의 시야 밖이었고, 형식 검사는 전부 통과했습니다.
- 숫자는 시세 파일에서만 가져온다는 규칙이 사람의 성실성에만 기대고 있었습니다.
  이 경로는 사람 검수 없이 바로 공개됩니다.

여기서 하는 것은 판단이 아니라 대조입니다. 원고에 적힌 "종목명 ... N.NN%"를
뽑아 시세와 맞춰 보고, 그날 절대 등락 1위 종목이 원고 어디에도 없으면 알립니다.

무엇을 일부러 보지 않는가
-------------------------
- 소수점이 없는 비율("5%대 상승")은 본문에서는 건너뜁니다. 어림수는 원고에서 정상입니다.
  **제목·제목 후보·소제목만** 예외입니다(아래 「2026-09-25」).
- 보유율·지분율 문맥의 퍼센트는 건너뜁니다("외국인 보유율은 5.54%").
- 종목명 근처에 등락을 뜻하는 말이 없으면 건너뜁니다. 업종지수나 수급 비중처럼
  종목 등락률이 아닌 숫자를 잘못 잡지 않기 위해서입니다.

즉 확실할 때만 실패시킵니다. 놓치는 것은 있어도, 맞는 원고를 막지는 않습니다.

2026-09-25에 더한 것 (검증에서 나온 세 구멍)
--------------------------------------------
① `ko.title_candidates`는 대조 대상이 아니었습니다. 그래서 'SK스퀘어가 … 5% 넘게 오른
   이유'(실제 3.88%)가 후보로 남아 있어도 통과했습니다. 후보도 제목과 같은 자리로 봅니다.
   제목류(제목·후보·소제목)는 어림수로 쓰는 것이 문법(등락률 반올림)이라 소수점이 없습니다.
   그래서 제목류에 한해 **경계 표현**("5% 넘게"·"5% 이상"·"5%대")을 시세와 대조합니다 —
   "넘게·이상"은 시세가 그 수 아래면, "N%대"는 시세가 N~N+1 사이가 아니면 지적합니다.
   본문에는 걸지 않습니다: 원고 전체를 세어 보니 경계 표현 120곳 가운데 "올해 500% 넘게",
   "8거래일 전보다 16% 넘게", "6월 고점 대비 40% 넘게"처럼 하루 등락이 아닌 것이 많았습니다.
② 프리뷰(`feature_gate`)에는 이 검사가 아예 없었습니다. 그대로 붙이면 밸류에이션 문장이
   걸립니다 — 9/22 8건·9/23 4건 실측: "목표주가까지 +45.1%", "52주 고점 대비 -14.5%",
   "FWD PER 59.1배 … 4.4% 웃돌고", "프리마켓 상승분(+5.09%)", "0.70%포인트 하락". 이런
   문맥은 등락률이 아니므로 `_NOT_A_MOVE`에 더했습니다(원고는 '목표가'가 아니라 '목표주가'로
   씁니다). 프리뷰 진입점은 `collect_issues_for_preview` — 미국장 전일(D-1) 파일은 1위 종목까지
   요구하고(9절 「서학개미 보유 상위」가 "어젯밤 크게 움직인 것"을 쓰는 자리), 한국장 당일 파일은
   숫자만 대조합니다(10절은 장세 요약이지 종목 순위가 아닙니다).
③ 프리뷰에서 "어제"는 그 미국장 파일의 날입니다. 시황용 `_OTHER_DAY`(어제·전날을 건너뜀)를
   그대로 쓰면 미국장 대조가 거의 전부 빠지므로 프리뷰용 `_OTHER_DAY_PREVIEW`를 따로 둡니다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class EditorialFactError(ValueError):
    """원고의 숫자가 시세와 어긋날 때 발생합니다."""


# "8.58%" 처럼 소수점이 있는 비율만 봅니다.
_PERCENT = re.compile(r"(\d+\.\d+)\s*%")
# 제목류에서만 보는 경계 표현(2026-09-25). "5% 넘게"·"5% 이상"은 하한, "5%대"는 5~6 구간.
# "5%대 넘게"는 글쓴이 뜻이 '5 초과'이므로 하한으로 읽고, "3~5%대"처럼 범위의 끝은 보지 않습니다.
# "0.25%포인트"의 "25%"를 정수로 읽지 않도록 앞에 숫자·점이 오면 제외합니다.
_BOUND = re.compile(
    r"(?<![\d.~\-–])(\d+)\s*%\s*(?:대\s*)?(?P<floor>넘게|넘는|넘어|넘은|이상)"
    r"|(?<![\d.~\-–])(\d+)\s*%\s*(?P<band>대)(?!\s*(?:넘|이상|비))"
)
# 종목명 주변에 이런 말이 있어야 '등락률을 말한 것'으로 봅니다.
# 2026-09-25: 뛰다·빠지다·밀리다·떨어지다·무너지다·치솟다·폭등·폭락을 더했습니다 — 소제목
# "성호전자는 왜 15% 넘게 뛰었나"처럼 제목류가 즐겨 쓰는 동사가 빠져 있어 대조가 아예 안 됐습니다.
_MOVE_WORDS = re.compile(
    r"(올랐|올라|오른|오르|상승|내렸|내려|내린|하락|급등|급락|마감|반등|약세|강세"
    r"|뛰었|뛴|뛰어|빠졌|빠진|빠져|밀렸|밀린|밀려|떨어졌|떨어진|떨어져|무너졌|무너진|치솟|폭등|폭락"
    r"|rose|fell|gained|lost|closed|climbed|dropped|slid|added|up |down "
    r"|jumped|surged|plunged|tumbled|soared|sank|rallied|slumped)",
    re.IGNORECASE,
)
# 이런 말이 있으면 등락률이 아니라 보유율·비중입니다.
# 2026-09-25: 프리뷰의 밸류에이션 문맥을 더했습니다 — 목표주가 대비 괴리("목표주가까지 +45.1%"),
# 52주 고·저점 대비("52주 고점 대비 -14.5%"), PER 배수 옆의 괴리율, 프리마켓·시간외 등락
# ("프리마켓 상승분(+5.09%)"), 퍼센트포인트("0.70%포인트 하락"). 전부 종가 등락률이 아닙니다.
# 창(이름 앞 20자·뒤 45자) 안에서만 봅니다 — 글 전체에서 찾으면 멀쩡한 종목까지 건너뜁니다.
_NOT_A_MOVE = re.compile(
    r"(보유율|지분|비중|점유율|ratio|stake|ownership|holding|share of"
    r"|목표(?:주)?가|52주\s*(?:신)?(?:고|저)점|(?:고|저)점\s*(?:대비|보다)"
    r"|(?<![A-Za-z])PER(?![A-Za-z])|(?<![A-Za-z])P/E|forward P/E|52-week|target price|price target"
    r"|프리마켓|시간외|애프터마켓|pre-?market|after-?hours|extended[- ]hours"
    r"|%\s*(?:포인트|p(?![A-Za-z]))|percentage points?)",
    re.IGNORECASE,
)
# 퍼센트 바로 뒤의 단위. 창이 45자에서 잘리면 "0.70%포인트"가 "0.70%"로 보일 수 있어,
# 창이 아니라 원문에서 숫자 바로 뒤를 한 번 더 봅니다(2026-09-25).
_POINT_UNIT = re.compile(r"\s*(?:포인트|p(?![A-Za-z]))")
# 시각이 붙은 숫자는 장중 값이라 종가와 다른 것이 정상입니다.
# "CBC뉴스는 오전 9시 44분 기준으로 삼성중공업 1.55% 상승을 전했습니다" 같은
# 인용은 좋은 원고에서 흔하고, 이걸 실패로 잡으면 검사가 쓸모없어집니다.
_INTRADAY = re.compile(
    r"(장중|오전|오후|시각|\d+시\s*\d*분|기준으로|현재|한때|출발|시가|intraday|as of|morning"
    r"|afternoon|opened|by midday)",
    re.IGNORECASE,
)
# 다른 거래일의 숫자를 인용한 자리도 건너뜁니다. 이틀을 비교하는 서술은
# 좋은 원고에서 흔합니다 — "KB금융은 어제 5.20% 오르고 오늘 3.32% 내렸습니다".
# 장중 인용과 같은 이유로, 오늘 종가와 다른 것이 정상인 숫자입니다.
_OTHER_DAY = re.compile(
    r"(어제|전날|지난|직전|이틀|전 거래일|다음 거래일|\d+월 \d+일|\d+/\d+|→"
    # 영어판(2026-09-25): 'jumped'를 등락 낱말에 더하자 kr 9/09 영어판의 "Daewoo E&C, which jumped
    # 8.47% yesterday"가 걸렸습니다 — 한국어 '어제'만 있고 영어가 없었습니다.
    r"|yesterday|the day before|previous (?:day|session)|prior (?:day|session)|a day earlier|last week)",
    re.IGNORECASE,
)
# 프리뷰의 미국장(D-1) 파일용(2026-09-25). 프리뷰에서 "어제·어젯밤"은 곧 그 파일의 날이라 건너뛰면
# 안 되고, 대신 "오늘"(아직 열리지 않은 장·프리마켓)·"올해·이달"(기간 등락)·"N거래일 전"·
# "어제 프리뷰"(D-2 숫자를 인용하는 자리)를 건너뜁니다.
_OTHER_DAY_PREVIEW = re.compile(
    r"(지난|직전|이틀|전 거래일|다음 거래일|\d+월 \d+일|\d+/\d+|→"
    r"|오늘|그제|그저께|올해|이달|이번\s?주|거래일\s*전|프리뷰|시황)"
)
# 날짜 표기. 시세 파일의 `trading_date`와 같은 날짜("9월 23일")는 '다른 날'이 아니므로 건너뛰지 않고,
# 다른 날짜는 같은 **문단** 안에서 이름 앞에 있기만 해도 건너뜁니다(2026-09-25). 창(20자)만 보면
# "미국이 노동절로 쉰 9월 7일, 서울은 같은 이야기를 이어받았습니다. SK하이닉스가 8.26%…"처럼
# 앞 문장의 날짜를 놓쳐 9/07 숫자를 9/08 파일과 대조했습니다(9/08 프리뷰 실측).
_DATE_MARK = re.compile(r"\d+월 \d+일|\d+/\d+")
_WINDOW_BEFORE, _WINDOW_AFTER = 20, 45

# 지수·환율 이름과 등락률 사이에 올 수 있는 것: 조사, 숫자, 단위, 부호뿐입니다.
# 종목명과 달리 지수 이름은 수식어로도 쓰여서("코스닥 장비주도 심텍 4.78%"),
# 뒤에 나오는 첫 퍼센트를 그대로 가져오면 남의 숫자를 읽습니다. 실제로 2026-09-03
# 원고의 저 문장에서 4.78%(심텍)를 코스닥 등락률로 읽었습니다.
_MACRO_FILLER = re.compile(r"^[은는이가도의을를]?[\s0-9,.\-+()원달러포인트p]*$")

# 경계 표현까지 보는 자리(제목류). `_texts`의 위치 이름이 이 접두어로 시작하면 해당합니다.
_TITLE_LIKE = ("제목", "본문 소제목")


_TAG = re.compile(r"<[^>]+>")


def _strip_tags(text: str) -> str:
    """강조 태그를 걷어냅니다.

    원고는 숫자를 <b>로 강조합니다("코스피 6,687.21 <b>+1.64%</b>"). 태그를 그대로
    두면 이름과 등락률 사이에 낯선 글자가 끼어, 아래 인접 규칙이 남의 숫자로 봅니다.
    """
    return _TAG.sub("", text)


def _texts(doc: dict, include_candidates: bool = True) -> list[tuple[str, str]]:
    """원고에서 숫자가 들어갈 수 있는 자리를 (위치 이름, 글) 목록으로 모읍니다.

    `ko.title_candidates`(2026-09-25)도 제목과 같은 자리입니다 — 관문이 후보 가운데 하나를
    제목으로 요구하므로 후보의 숫자도 독자에게 나갈 수 있는 숫자입니다. 다만 1위 종목을
    다뤘는지 볼 때(`include_candidates=False`)는 뺍니다: 버려진 후보에만 이름이 있는 것은
    다룬 것이 아닙니다.
    """
    out: list[tuple[str, str]] = [("제목", str(doc.get("title", "")))]
    if include_candidates:
        for index, candidate in enumerate(doc.get("title_candidates") or [], start=1):
            out.append((f"제목 후보 {index}", str(candidate)))
    for index, section in enumerate(doc.get("narrative") or [], start=1):
        out.append((f"본문 {index}", str(section.get("body", ""))))
        out.append((f"본문 소제목 {index}", str(section.get("heading", ""))))
    for key, label in (("outlook", "전망"), ("closing", "마무리")):
        out.append((label, str((doc.get(key) or {}).get("body", ""))))
    for index, story in enumerate(
        (doc.get("insight_section") or {}).get("stories") or [], start=1
    ):
        out.append((f"인사이트 {index}", str(story.get("heading", ""))))
        out.append((f"인사이트 본문 {index}", str(story.get("body", ""))))
        for row in story.get("table") or []:
            out.append(
                (f"인사이트 표 {index}", f"{row.get('label', '')} {row.get('value', '')}")
            )
    for key in ("theme_section", "stock_section"):
        section = doc.get(key) or {}
        out.append((key, str(section.get("commentary", ""))))
    return [(where, _strip_tags(text)) for where, text in out if text]


def _entries(price_data: dict) -> list[dict]:
    """그날의 주인공을 고를 때 쓰는 목록 — 종목만 봅니다.

    지수나 환율이 크게 움직인 날 그것이 '주인공'으로 뽑히면 안 됩니다. 이 검사가
    요구하는 것은 '가장 크게 움직인 종목을 다뤘는가'이기 때문입니다.
    """
    return list((price_data.get("watchlist") or {}).values())


def _checkable_entries(price_data: dict) -> list[dict]:
    """숫자를 대조할 목록 — 종목에 지수·환율을 더합니다.

    전에는 워치리스트만 봤습니다. 그래서 2026-09-04 한국장 원고가 원/달러 등락률을
    두 군데 모두 -0.58%로 적었는데(시세는 -0.53%) 검사를 그대로 통과했습니다.
    카드는 시세에서 그리므로 -0.53%로 나와, 같은 글 안에서 숫자가 갈렸습니다.

    다만 **값 자체가 퍼센트인 항목(금리)은 뺍니다.** 원고는 금리를 "미 10년물
    4.761%"처럼 수준으로 적는데, 그것을 등락률로 읽으면 멀쩡한 문장이 걸립니다.
    """
    macro = [
        {**entry, "_is_macro": True}
        for entry in (price_data.get("macro") or {}).values()
        if str(entry.get("unit") or "") != "%"
    ]
    return _entries(price_data) + macro


# 원고가 부르는 이름이 시세 파일의 name과 다른 경우입니다. 짧고 흔한 말은
# 넣지 않습니다 — '금'을 넣으면 금리·금융이 걸립니다.
_ALIASES = {
    "원/달러 환율": ("원/달러", "원·달러", "원달러"),
    "나스닥종합": ("나스닥",),
    "S&P500": ("S&P 500",),
    "Nasdaq Composite": ("Nasdaq",),
    # 편입 종목 가운데 시세 파일에 한글 이름이 없는 것. 원고는 음차로 씁니다(2026-09-25 실측: 9/09·9/17
    # 프리뷰가 '루멘텀'으로 세 번 다뤘는데 1위 누락으로 잡혔습니다).
    "Lumentum": ("루멘텀",),
}

# 1위 종목이 원고에 있는지 볼 때 이름 대신 인정하는 것들(2026-09-25). 이름을 글자 그대로만 찾으면
# "WTI는 어제 배럴당…"(파일 이름은 'WTI 원유')·'루멘텀'(파일 이름은 'Lumentum')이 누락으로 잡힙니다 —
# 9/09·9/11·9/17 프리뷰 실측. 대문자 약어(3자 이상)와 3~5자 알파벳 티커는 앞뒤에 알파벳이 없을 때만 셉니다.
_ABBREVIATION = re.compile(r"[A-Z]{3,}")
_TICKER_SHAPE = re.compile(r"^[A-Z]{3,5}$")


def _lead_mentioned(lead: dict, haystack: str, tickers: set) -> bool:
    """1위 종목이 원고에 나오는가 — 이름·영어 이름·별칭·대문자 약어·티커 가운데 하나면 됩니다."""
    names = [str(lead.get("name") or ""), str(lead.get("name_en") or "")]
    for name in list(names):
        names.extend(_ALIASES.get(name, ()))
    for name in names:
        if name and name in haystack:
            return True
    ticker = str(lead.get("ticker") or "")
    if ticker in tickers:
        return True
    # 한국 종목코드(여섯 자리)를 적은 것도 다룬 것이다(2026-09-26). 영어 이름을 못 찾은 편입 종목은 name_en이 한글이라,
    # 영어판이 "1위 종목을 다뤘나"를 통과하려면 한글을 써야 했고, 그 한글은 영어 문체 검사가 막는다.
    if ticker.isdigit() and len(ticker) == 6 and re.search(rf"(?<!\d){ticker}(?!\d)", haystack):
        return True
    tokens = {ticker} if _TICKER_SHAPE.match(ticker) else set()
    for name in names:
        tokens.update(_ABBREVIATION.findall(name))
    return any(
        re.search(rf"(?<![A-Za-z]){re.escape(token)}(?![A-Za-z])", haystack) for token in tokens
    )


def _names_by_length(price_data: dict, lang: str) -> list[tuple[str, dict]]:
    """긴 이름부터 봅니다 — '에코프로비엠'을 '에코프로'로 잘못 읽지 않으려고."""
    key = "name_en" if lang == "en" else "name"
    pairs: list[tuple[str, dict]] = []
    for entry in _checkable_entries(price_data):
        name = str(entry.get(key) or entry.get("name") or "")
        if not name:
            continue
        pairs.append((name, entry))
        for alias in _ALIASES.get(name, ()):
            pairs.append((alias, entry))
    return sorted(pairs, key=lambda p: len(p[0]), reverse=True)


def _same_sentence_tail(text: str, end: int, names: list[tuple[str, dict]]) -> str:
    """종목명 뒤에서, **같은 문장 안에 그 종목만 있는** 구간을 돌려줍니다.

    창을 글자 수로만 자르면 다음 문장의 숫자를 끌어옵니다. 실제로 이런 문장에서
    걸렸습니다 — "삼성전기가 3.71% 내렸고 한미반도체와 SK하이닉스, 삼성전자가
    뒤를 이었다. 코스닥 장비주도 심텍 4.78% ... 밀렸다." 뒤 문장의 4.78%가
    앞 문장 종목들의 등락률로 읽혔습니다. 문장 경계와 다음 종목명에서 끊습니다.
    """
    tail = text[end : end + _WINDOW_AFTER]
    for boundary in ("다.", ". ", "\n"):
        cut = tail.find(boundary)
        if cut >= 0:
            tail = tail[:cut]
    for name, _ in names:
        cut = tail.find(name)
        if cut >= 0:
            tail = tail[:cut]
    return tail


def _bound_violation(quoted: int, kind: str, actual: float) -> bool:
    """경계 표현이 시세와 어긋나는지. floor("N% 넘게·이상")는 시세가 N 아래일 때,
    band("N%대")는 시세가 N~N+1 구간 밖일 때 어긋난 것입니다."""
    value = round(actual, 2)
    if kind == "floor":
        return value < quoted
    return not (quoted <= value < quoted + 1)


def _own_day_markers(price_data: dict) -> frozenset[str]:
    """시세 파일 자신의 날짜를 원고가 적는 꼴들("9월 23일"·"09/23"·"9/23"). 없으면 빈 집합."""
    raw = str(price_data.get("trading_date") or "")
    found = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if found is None:
        return frozenset()
    month, day = int(found.group(2)), int(found.group(3))
    return frozenset({
        f"{month}월 {day}일", f"{month:02d}월 {day:02d}일",
        f"{month}/{day}", f"{month:02d}/{day:02d}",
    })


def _mentions_other_day(
    text: str, at: int, window: str, other_day: re.Pattern[str], own_days: frozenset[str]
) -> bool:
    """창 안의 '다른 날' 표지, 또는 같은 문단에서 이름 앞에 나온 **다른** 날짜가 있으면 True.

    시세 파일과 같은 날짜는 다른 날이 아닙니다 — "9월 22일 밤, 마이크론이 5.00% 올라"는 대조합니다.
    """
    for hit in other_day.finditer(window):
        if hit.group(0) not in own_days:
            return True
    paragraph_start = text.rfind("\n\n", 0, at)
    before = text[0 if paragraph_start < 0 else paragraph_start + 2 : at]
    return any(hit.group(0) not in own_days for hit in _DATE_MARK.finditer(before))


def _quoted_moves(
    text: str,
    names: list[tuple[str, dict]],
    other_day: re.Pattern[str] = _OTHER_DAY,
    bounds: bool = False,
    own_days: frozenset[str] = frozenset(),
) -> list[tuple[dict, float, tuple[str, str] | None]]:
    """글에서 (종목, 원고가 적은 등락률, 경계) 쌍을 뽑습니다.

    경계는 소수점 등락률이면 None, `bounds=True`(제목류)에서 "5% 넘게"를 읽었으면
    ("floor", "넘게"), "5%대"를 읽었으면 ("band", "대")입니다.
    """
    found: list[tuple[dict, float, tuple[str, str] | None]] = []
    claimed: list[tuple[int, int]] = []  # 이미 긴 이름이 차지한 구간
    for name, entry in names:
        start = 0
        while True:
            at = text.find(name, start)
            if at < 0:
                break
            end = at + len(name)
            start = end
            if any(s <= at < e for s, e in claimed):
                continue  # '에코프로비엠' 안의 '에코프로'
            if end < len(text) and text[end].isdigit():
                continue  # '나스닥100', '코스피200'은 다른 지표입니다
            claimed.append((at, end))
            window = text[max(0, at - _WINDOW_BEFORE) : end + _WINDOW_AFTER]
            if _NOT_A_MOVE.search(window) or _INTRADAY.search(window):
                continue
            if _mentions_other_day(text, at, window, other_day, own_days):
                continue
            tail = _same_sentence_tail(text, end, names)
            match = _PERCENT.search(tail)
            kind: tuple[str, str] | None = None
            if match is None and bounds:
                bound = _BOUND.search(tail)
                if bound is None:
                    continue
                match = bound
                kind = ("floor", bound.group("floor")) if bound.group("floor") else ("band", "대")
                quoted = float(bound.group(1) or bound.group(3))
            elif match is None:
                continue
            else:
                quoted = float(match.group(1))
                if _POINT_UNIT.match(text, end + match.end()):
                    continue  # "0.70%포인트" — 퍼센트포인트는 등락률이 아닙니다
            if entry.get("_is_macro"):
                # 지수·환율은 요약 줄에서 움직임을 뜻하는 말 없이 숫자만 나열합니다
                # ("코스피 6,687.21 +1.64%"). 그래서 종목과 달리 _MOVE_WORDS를
                # 요구하지 않고, **이름과 등락률이 붙어 있는지**로 판단합니다.
                # 사이에 다른 낱말이 끼면("코스닥 장비주도 심텍 4.78%") 남의 숫자입니다.
                if not _MACRO_FILLER.match(tail[: match.start()]):
                    continue
            elif not _MOVE_WORDS.search(window) and "(" not in window:
                continue
            found.append((entry, quoted, kind))
    return found


def collect_issues(
    doc: dict,
    price_data: dict,
    lang: str = "ko",
    *,
    other_day: re.Pattern[str] = _OTHER_DAY,
    require_lead: bool = True,
) -> list[str]:
    """숫자 대조와 주인공 누락 검사를 한 번에 수행합니다.

    `other_day`는 '다른 날의 숫자'로 보고 건너뛸 말의 목록(프리뷰는 `_OTHER_DAY_PREVIEW`),
    `require_lead=False`면 1위 종목 누락은 보지 않습니다(프리뷰의 한국장 파일).
    """
    issues: list[str] = []
    entries = _entries(price_data)
    if not entries:
        return issues

    names = _names_by_length(price_data, lang)
    own_days = _own_day_markers(price_data)
    known_percents = {
        round(abs(float(e["change_pct"])), 2) for e in _checkable_entries(price_data)
    }
    for where, text in _texts(doc):
        title_like = where.startswith(_TITLE_LIKE)
        for entry, quoted, bound in _quoted_moves(
            text, names, other_day, bounds=title_like, own_days=own_days
        ):
            actual = round(abs(float(entry["change_pct"])), 2)
            if bound is not None:
                kind, word = bound
                if not _bound_violation(int(quoted), kind, actual):
                    continue
                phrase = f"{int(quoted)}%{'' if kind == 'band' else ' '}{word}"
                issues.append(
                    f"{where}: '{entry['name']}'을 '{phrase}'로 적었는데 시세는 {actual:.2f}%입니다. "
                    "제목의 어림수도 시세 안에 있어야 합니다."
                )
                continue
            if round(quoted, 2) == actual:
                continue
            # 같은 글에서 다른 종목의 등락률을 나란히 적는 문장이 흔합니다.
            # 시세에 실제로 있는 값이면 문장 구조 문제일 뿐이라 넘어갑니다.
            if round(quoted, 2) in known_percents:
                continue
            issues.append(
                f"{where}: '{entry['name']}' 등락률을 {quoted:.2f}%로 적었는데 "
                f"시세는 {actual:.2f}%입니다. 숫자는 시세 파일에서만 가져오세요."
            )

    if not require_lead:
        return issues
    lead = max(entries, key=lambda e: abs(float(e["change_pct"])))
    haystack = " ".join(text for _, text in _texts(doc, include_candidates=False))
    tickers = set((doc.get("stock_section") or {}).get("featured_tickers") or [])
    tickers |= {
        h.get("ticker") for h in (doc.get("theme_section") or {}).get("highlights") or []
    }
    if not _lead_mentioned(lead, haystack, tickers) and abs(float(lead["change_pct"])) >= 1.0:
        issues.append(
            f"그날 등락 폭이 가장 큰 {lead['name']}({lead['change_pct']:+.2f}%)이 "
            "원고 어디에도 없습니다. 다루지 않을 이유가 있다면 본문에서 밝히세요."
        )
    return issues


def validate(doc: dict, price_data: dict, lang: str = "ko") -> None:
    """대조에 실패하면 발행을 중단합니다."""
    issues = collect_issues(doc, price_data, lang=lang)
    if issues:
        raise EditorialFactError("원고와 시세 대조 실패:\n- " + "\n- ".join(issues))


# ---------------------------------------------------------------------------
# 프리뷰 (2026-09-25)
# ---------------------------------------------------------------------------
_PRICE_FILE = re.compile(r"price_(kr|us)_(\d{4}-\d{2}-\d{2})\.json$")


def preview_price_files(doc: dict, root: Path = ROOT) -> dict[str, Path | None]:
    """프리뷰 원고가 대조할 시세 파일 — {"us": 미국장 전일(D-1) 파일, "kr": 한국장 당일 파일 또는 None}.

    규칙은 `docs/routine_preview.md`의 「읽을 것」 4·5와 10절 재료 칸과 같습니다: 미국장은
    `data/price_us_<가장 최근>.json`(어제 종가, "가격대 숫자는 여기서만"), 한국장은
    `data/price_kr_<KST 오늘>.json`. 원고가 `graphics[*].price_file`로 파일을 가리켰으면 그것이
    루틴이 실제로 읽은 파일이므로 먼저 씁니다(한국장 휴장이면 전 거래일 파일을 가리키기도 합니다 —
    9/24 프리뷰가 9/23 파일을 썼습니다). 없으면 원고 `date`로 찾습니다.

    미국장 파일을 못 찾으면 예외입니다 — 조용히 건너뛰면 검사가 돌지 않은 것을 통과로 읽습니다.
    """
    date_str = str(doc.get("date") or "")
    named: dict[str, set[str]] = {"kr": set(), "us": set()}
    for index, graphic in enumerate(doc.get("graphics") or [], start=1):
        price_file = graphic.get("price_file")
        if not price_file:
            continue
        found = _PRICE_FILE.search(str(price_file))
        if found is None:
            raise ValueError(
                f"그래픽 {index}의 price_file 이름을 읽을 수 없습니다: {price_file!r} "
                "(data/price_<kr|us>_<YYYY-MM-DD>.json 꼴이어야 합니다)"
            )
        named[found.group(1)].add(found.group(2))
    files: dict[str, Path | None] = {}
    for market in ("us", "kr"):
        dates = named[market]
        if len(dates) > 1:
            raise ValueError(
                f"프리뷰가 {market} 시세 파일을 두 날짜로 가리킵니다: {sorted(dates)} — "
                "숫자를 어느 날과 대조할지 정할 수 없습니다."
            )
        if dates:
            files[market] = root / "data" / f"price_{market}_{next(iter(dates))}.json"
            continue
        if market == "kr":
            candidate = root / "data" / f"price_kr_{date_str}.json"
            files["kr"] = candidate if candidate.exists() else None
            continue
        earlier = sorted(
            p for p in (root / "data").glob("price_us_*.json")
            if date_str and p.stem < f"price_us_{date_str}"
        )
        files["us"] = earlier[-1] if earlier else None
    if files["us"] is None or not files["us"].exists():
        raise ValueError(
            f"프리뷰({date_str})가 대조할 미국장 전일 시세 파일이 없습니다: {files['us']} — "
            "그래픽의 price_file이나 data/price_us_<날짜>.json을 확인하세요."
        )
    if files["kr"] is not None and not files["kr"].exists():
        raise ValueError(f"프리뷰가 가리킨 한국장 시세 파일이 없습니다: {files['kr']}")
    return files


def _load_price_files(price_files) -> list[tuple[str, Path]]:
    """(시장, 경로) 목록으로 정리합니다. dict({"us": ..., "kr": ...})나 경로 목록 둘 다 받습니다."""
    if isinstance(price_files, dict):
        pairs = [(market, Path(path)) for market, path in price_files.items() if path]
    else:
        pairs = []
        for path in price_files:
            found = _PRICE_FILE.search(str(path))
            if found is None:
                raise ValueError(f"시세 파일 이름에서 시장을 읽을 수 없습니다: {path}")
            pairs.append((found.group(1), Path(path)))
    for market, _ in pairs:
        if market not in ("kr", "us"):
            raise ValueError(f"모르는 시장입니다: {market!r} (kr·us만)")
    return pairs


def collect_issues_for_preview(
    doc: dict, price_files, *, notes_out: list[str] | None = None
) -> list[str]:
    """프리뷰 원고를 시세 파일 둘과 대조합니다(2026-09-25).

    `price_files`는 `preview_price_files(doc)`의 결과({"us": 경로, "kr": 경로|None})나 경로 목록.
    미국장(D-1) 파일: 숫자 대조 + 1위 종목 누락(프리뷰용 다른-날 규칙 `_OTHER_DAY_PREVIEW`).
    한국장(당일) 파일: 숫자 대조만. 지적 앞에 어느 파일인지 붙입니다. 한국장 파일이 없으면
    `notes_out`에 남깁니다 — 검사가 안 돈 것을 통과로 읽지 않게.
    """
    ko = doc.get("ko") or doc
    pairs = _load_price_files(price_files)
    if not any(market == "us" for market, _ in pairs):
        raise ValueError("프리뷰 대조에는 미국장 전일 시세 파일이 있어야 합니다.")
    if notes_out is not None and not any(market == "kr" for market, _ in pairs):
        notes_out.append("한국장 당일 시세 파일이 없어 10절(내일 아침 한국장)의 숫자는 대조하지 않았습니다.")
    issues: list[str] = []
    for market, path in pairs:
        price_data = json.loads(path.read_text(encoding="utf-8"))
        if market == "us":
            found = collect_issues(ko, price_data, lang="ko",
                                   other_day=_OTHER_DAY_PREVIEW, require_lead=True)
        else:
            found = collect_issues(ko, price_data, lang="ko", require_lead=False)
        issues.extend(f"[{path.stem}] {issue}" for issue in found)
    return issues


def validate_preview(doc: dict, price_files, *, notes_out: list[str] | None = None) -> None:
    """프리뷰 대조에 실패하면 예외 — `validate`와 같은 꼴입니다."""
    issues = collect_issues_for_preview(doc, price_files, notes_out=notes_out)
    if issues:
        raise EditorialFactError("프리뷰와 시세 대조 실패:\n- " + "\n- ".join(issues))
