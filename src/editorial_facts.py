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
    r"(장중|오전|오후|시각|\d+시\s*\d*분|기준으로|현재|한때|출발|시가(?!총)|intraday|as of|morning"
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
    r"|yesterday|the day before|previous (?:day|session)|prior (?:day|session)|a day earlier|last week"
    # 2026-10-06: 기간 등락("over the full month, the Dow fell 4.90%"·"이번 주 3%")과 영어 날짜("on the 28th")도 그날 숫자가 아니다
    r"|이달|이번\s?달|한\s?달|이번\s?주|올해|연초|분기|\d+\s*거래일\s*전|상승분|하락분|오름폭|낙폭"
    r"|\b(?:month|monthly|week|weekly|year|annual|quarter|year-to-date|YTD|since)\b"
    r"|\bon the \d{1,2}(?:st|nd|rd|th)\b"
    r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.? \d{1,2}\b)",
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
# 기간 등락의 표지는 **같은 문장 앞쪽**에만 있어도 그 문장의 숫자가 기간 등락이다("Over the full month, the Dow fell 4.9% and the
# S&P 500 lost 0.7%" — S&P 500 앞 20자 창에는 'month'가 없다, 2026-10-06 재실행에서 확인).
_PERIOD_MARK = re.compile(
    r"이달|이번\s?달|한\s?달|이번\s?주|올해|연초|분기|\d+월\s?(?:한\s?달|중|들어)"
    r"|\b(?:month|monthly|week|weekly|year|annual|quarter|year-to-date|YTD|since)\b",
    re.IGNORECASE,
)
_WINDOW_BEFORE, _WINDOW_AFTER = 20, 45

# 지수·환율 이름과 등락률 사이에 올 수 있는 것: 조사, 숫자, 단위, 부호뿐입니다.
# 종목명과 달리 지수 이름은 수식어로도 쓰여서("코스닥 장비주도 심텍 4.78%"),
# 뒤에 나오는 첫 퍼센트를 그대로 가져오면 남의 숫자를 읽습니다. 실제로 2026-09-03
# 원고의 저 문장에서 4.78%(심텍)를 코스닥 등락률로 읽었습니다.
_MACRO_FILLER = re.compile(r"^[은는이가도의을를]?[\s0-9,.\-+()원달러포인트p]*$")
# 2026-10-06(감사 F-014·F-054): 위 꼴은 "코스피 지수는 1.46%"·"원/달러 환율은 1,347원으로 0.23%"·"The S&P 500 rose 1.95%"를
# 모두 건너뛰었다. 지수 이름 뒤에 붙는 **정해진 낱말**만 지우고 나머지가 숫자·단위·부호뿐이면 그 지수의 숫자로 본다 — 목록 밖 낱말이
# 하나라도 끼면("코스닥 장비주도 심텍") 여전히 남의 숫자로 보고 건너뛴다.
_MACRO_WORDS = re.compile(
    r"(?:종합지수|지수|종합|환율|금값|값|가격|선물|종가|고시|기준|배럴당|온스당|서울|외환시장|외환|시장|오늘|이날|으로|로|에서|은|는|이|가|도|의|을|를"
    r"|\b(?:the|index|composite|average|rose|fell|gained|lost|added|slipped|climbed|declined|dropped|jumped|advanced|slid"
    r"|surged|sank|tumbled|rallied|ended|closed|finished|was|were|up|down|by|to|at|or|a|points?|pts?|per|dollar|barrel|ounce"
    r"|won|percent|today)\b)",
    re.IGNORECASE,
)


def _macro_filler(between: str) -> bool:
    """지수·환율 이름과 퍼센트 사이가 그 지수의 숫자를 잇는 말뿐인가."""
    if _MACRO_FILLER.match(between):
        return True
    if re.search(r",(?!\d)", between):
        return False   # 숫자 안의 쉼표가 아니면 다른 말이 이어진다("listed on the KOSDAQ, gained 9.33%" — 그 종목의 숫자)
    rest = _MACRO_WORDS.sub(" ", between)
    return bool(re.fullmatch(r"[\s0-9,.\-+()$원달러포인트p/]*", rest))

# 경계 표현까지 보는 자리(제목류). `_texts`의 위치 이름이 이 접두어로 시작하면 해당합니다.
_TITLE_LIKE = ("제목", "본문 소제목")


_TAG = re.compile(r"<[^>]+>")

# ── 2026-09-26 점검에서 나온 네 구멍 ────────────────────────────────────────────────────────────────
# ① 방향: 크기만 보고 부호는 안 봐서 "삼성전자 2.70% 하락"(실제 +2.70%)이 통과했다. 숫자 **바로 뒤**(한국어)·**바로 앞**
#    (영어)의 등락 낱말이나 숫자 앞 부호가 시세와 반대일 때만 막는다 — 떨어진 곳의 낱말은 다른 종목 이야기일 수 있다.
# ② 남의 숫자: 그날 **어느 종목이든** 그만큼 움직였으면 통과시켜 옆 종목과 숫자가 뒤바뀐 문장이 나갔을 것이다. 이제
#    **같은 문장에 이름·티커가 나온** 종목의 숫자일 때만 넘어간다("각각 0.20%, 1.05%"는 그대로 통과).
# ③ 건너뛰기 창이 문장·문단을 넘었다: 다음 문단의 "장중"이 앞 문장의 숫자 검사를 껐다. 창을 **그 문장 안**으로 자른다.
# ④ 이름을 낱말 속에서 찾았다: "소셜미디어"의 '디어'(Deere)를 잡아 맞는 글을 막고, '미디어'만 있어도 Deere를 다뤘다고 봤다.
#    이름 앞이 글자면 이름으로 보지 않고, 영어 이름은 뒤도 본다. 알려진 합성어('애플리케이션' 등)는 뺀다.
_SENTENCE_END = re.compile(r"[.!?](?=\s|$)|\n")
_WORD_CHAR = re.compile(r"[가-힣A-Za-z0-9]")
_COMPOUNDS = {"애플": ("애플리케이션",), "메타": ("메타버스", "메타데이터"), "인텔": ("인텔리전스",), "델": ("델타",),
              "다우": ("다우데이타", "다우기술")}
_UP_AFTER = re.compile(r"^\s*(?:의\s*)?(?:상승|올랐|오른|오르며|올라|급등|뛰었|뛴|뛰며|반등|강세)")
_DOWN_AFTER = re.compile(r"^\s*(?:의\s*)?(?:하락|내렸|내린|내리며|내려|급락|떨어|빠졌|빠진|빠지며|밀렸|밀린|밀리며|약세)")
_UP_BEFORE = re.compile(r"\b(?:rose|gained|climbed|jumped|surged|rallied|soared|added|advanced|up)\s+(?:by\s+)?$", re.IGNORECASE)
_DOWN_BEFORE = re.compile(r"\b(?:fell|lost|dropped|slid|plunged|tumbled|sank|slumped|declined|down)\s+(?:by\s+)?$", re.IGNORECASE)


# 같은 회사의 다른 주식 — 글은 회사 이름 하나로 쓰므로 서로의 등락률을 남의 숫자로 보지 않는다(GOOGL 이름은 "Google",
# GOOG는 "Alphabet"인데 글은 "Alphabet rose 3.22%"로 GOOGL 값을 쓴다). 한국 우선주는 코드 끝자리만 다르다(005930·005935).
_SAME_COMPANY = ({"GOOG", "GOOGL"}, {"BRK-A", "BRK-B"})


def _same_company(a: dict, b: dict) -> bool:
    ta, tb = str(a.get("ticker") or ""), str(b.get("ticker") or "")
    if any(ta in group and tb in group for group in _SAME_COMPANY):
        return True
    return len(ta) == len(tb) == 6 and ta.isdigit() and tb.isdigit() and ta[:5] == tb[:5]


_TIGHT = re.compile(
    r"^\s*(?:[은는이가도의]|'s)?\s*(?:\([A-Z0-9.\-]{1,8}\))?\s*"
    r"(?:rose|fell|gained|lost|added|climbed|dropped|jumped|slid|surged|plunged|tumbled|soared|sank|rallied|slumped"
    r"|advanced|declined|was up|was down)?\s*(?:by\s+)?[+\-−]?$", re.IGNORECASE)


def _sentence_bounds(text: str, at: int) -> tuple[int, int]:
    start = 0
    for m in _SENTENCE_END.finditer(text, 0, at):
        start = m.end()
    m = _SENTENCE_END.search(text, at)
    return start, (m.start() + 1 if m else len(text))


def _name_at(text: str, at: int, name: str) -> bool:
    """`text[at:]`에서 시작하는 `name`이 낱말 속 글자가 아니라 이름인가."""
    if at > 0 and _WORD_CHAR.match(text[at - 1]):
        return False
    end = at + len(name)
    if name[-1:].isascii() and name[-1:].isalpha() and end < len(text) and text[end].isascii() and text[end].isalpha():
        return False
    return not any(text.startswith(word, at) for word in _COMPOUNDS.get(name, ()))


def _mentions(text: str, name: str) -> bool:
    start = 0
    while True:
        at = text.find(name, start)
        if at < 0:
            return False
        if _name_at(text, at, name):
            return True
        start = at + 1


def _stated_direction(text: str, pct_start: int, pct_end: int) -> int:
    """숫자에 바로 붙은 방향: +1 오름, -1 내림, 0 모름(부호 → 한국어 뒤 낱말 → 영어 앞 낱말 순)."""
    sign = text[pct_start - 1: pct_start] if pct_start > 0 else ""
    if sign == "+":
        return 1
    if sign in ("-", "−"):
        return -1
    after = text[pct_end: pct_end + 8]
    if _UP_AFTER.match(after):
        return 1
    if _DOWN_AFTER.match(after):
        return -1
    before = text[max(0, pct_start - 16): pct_start]
    if _UP_BEFORE.search(before):
        return 1
    if _DOWN_BEFORE.search(before):
        return -1
    return 0


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
    # 2026-10-06(감사 F-014): 어제 판정의 결과 문장(그날 숫자로 판정한다)과 그림 설명·제목도 독자에게 나가는 숫자다
    if doc.get("_review_result"):
        out.append(("어제 판정", str(doc["_review_result"])))
    for index, section in enumerate(doc.get("narrative") or [], start=1):
        for graphic in [section.get("graphic")] + list(section.get("graphics") or []):
            if isinstance(graphic, dict):
                for field in ("title", "note", "subtitle"):
                    if graphic.get(field):
                        out.append((f"그림 {index}", str(graphic[field])))
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
    "나스닥종합": ("나스닥", "나스닥 종합지수", "나스닥종합지수"),
    "다우존스": ("다우",),
    "Dow Jones Industrial Average": ("Dow Jones", "the Dow"),
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
        if name and _mentions(haystack, name):
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
        if lang == "en" and name.isupper() and len(name) > 3 and name.isalpha():
            pairs.append((name.capitalize(), entry))   # 'NVIDIA'를 글은 'Nvidia'로 쓴다(감사 F-014)
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
    import calendar
    full, short = calendar.month_name[month], calendar.month_abbr[month]
    suffix = "th" if 10 <= day % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return frozenset({
        f"{month}월 {day}일", f"{month:02d}월 {day:02d}일",
        f"{month}/{day}", f"{month:02d}/{day:02d}",
        f"{full} {day}", f"{short} {day}", f"{short}. {day}", f"Sept {day}", f"Sept. {day}", f"on the {day}{suffix}",
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
) -> list[tuple]:
    """글에서 (종목, 원고가 적은 등락률, 경계, (이름 위치, 숫자 시작, 숫자 끝))을 뽑습니다.

    경계는 소수점 등락률이면 None, `bounds=True`(제목류)에서 "5% 넘게"를 읽었으면
    ("floor", "넘게"), "5%대"를 읽었으면 ("band", "대")입니다.
    """
    found: list[tuple] = []
    claimed: list[tuple[int, int]] = []  # 이미 긴 이름이 차지한 구간
    for name, entry in names:
        start = 0
        while True:
            at = text.find(name, start)
            if at < 0:
                break
            end = at + len(name)
            start = end
            if not _name_at(text, at, name):
                start = at + 1
                continue  # '소셜미디어' 안의 '디어'
            if any(s <= at < e for s, e in claimed):
                continue  # '에코프로비엠' 안의 '에코프로'
            if end < len(text) and text[end].isdigit():
                continue  # '나스닥100', '코스피200'은 다른 지표입니다
            claimed.append((at, end))
            s_start, s_end = _sentence_bounds(text, at)
            window = text[max(s_start, at - _WINDOW_BEFORE) : min(s_end, end + _WINDOW_AFTER)]
            # 장중·다른 날 표지는 창(이름 앞 20자·뒤 45자) 어디에 있어도 건너뛴다. 숫자 앞에서만 보게 좁혀 보았으나(2026-10-06, 감사
            # F-054) 지난 원고 재실행에서 맞는 문장 7개가 새로 걸렸다 — 영어는 때를 숫자 뒤에 쓴다("jumped 8.47% yesterday",
            # "(2.70%) on the 28th"). '확실할 때만 막는다'에 따라 넓은 창을 그대로 둔다.
            if _NOT_A_MOVE.search(window) or _INTRADAY.search(window):
                continue
            if _mentions_other_day(text, at, window, other_day, own_days):
                continue
            if _PERIOD_MARK.search(text[s_start:at]):
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
                if re.match(r"\s*(?:에서|부터)", text[end + match.end():end + match.end() + 4]):
                    continue  # "5.11%에서 더 오르는지" — 출발점 수준이지 그 종목의 등락률이 아니다(2026-10-06)
            if entry.get("_is_macro"):
                # 지수·환율은 요약 줄에서 움직임을 뜻하는 말 없이 숫자만 나열합니다
                # ("코스피 6,687.21 +1.64%"). 그래서 종목과 달리 _MOVE_WORDS를
                # 요구하지 않고, **이름과 등락률이 붙어 있는지**로 판단합니다.
                # 사이에 다른 낱말이 끼면("코스닥 장비주도 심텍 4.78%") 남의 숫자입니다.
                if not _macro_filler(tail[: match.start()]):
                    continue
            elif not _MOVE_WORDS.search(window) and "(" not in window:
                continue
            found.append((entry, quoted, kind, (at, end, end + match.start(), end + match.end())))
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
    by_ticker = {str(e.get("ticker")): e for e in _checkable_entries(price_data) if e.get("ticker")}
    for where, text in _texts(doc):
        title_like = where.startswith(_TITLE_LIKE)
        for entry, quoted, bound, (name_at, name_end, pct_start, pct_end) in _quoted_moves(
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
                stated = _stated_direction(text, pct_start, pct_end)
                change = float(entry["change_pct"])
                if stated and change and (stated > 0) != (change > 0):
                    issues.append(
                        f"{where}: '{entry['name']}'을 {quoted:.2f}% {'상승' if stated > 0 else '하락'}으로 적었는데 "
                        f"시세는 {change:+.2f}%입니다 — 방향이 반대입니다.")
                continue
            # 같은 문장에서 다른 종목의 등락률을 나란히 적는 일이 흔합니다("각각 0.20%, 1.05%").
            # **같은 문장에 이름·티커가 나온** 종목의 값이면 문장 구조 문제일 뿐이라 넘어갑니다(2026-09-26 — 전에는
            # 그날 어느 종목의 값이든 넘어가서 옆 종목과 숫자가 뒤바뀐 문장도 통과했다).
            s_start, s_end = _sentence_bounds(text, name_at)
            sentence = text[s_start:s_end]
            # 숫자가 이름에 바로 붙어 있으면("삼성전자가 1.36%", "Samsung rose 1.36%") 그 이름의 숫자다 — 이웃 종목의 값이어도
            # 넘기지 않는다. 사이에 다른 말이 끼면("…는 각각 0.20%, 1.05%") 누구의 숫자인지 문장 구조로만 알 수 있어 넘긴다.
            tight = bool(_TIGHT.match(text[name_end:pct_start])) and not re.search(r"각각|respectively", sentence,
                                                                                  re.IGNORECASE)
            neighbours = set() if tight else {round(abs(float(e["change_pct"])), 2) for n, e in names if e is not entry and _mentions(sentence, n)}
            neighbours |= {round(abs(float(e["change_pct"])), 2) for t, e in by_ticker.items()
                           if e is not entry and re.search(rf"(?<![A-Za-z0-9]){re.escape(t)}(?![A-Za-z0-9])", sentence)}
            neighbours |= {round(abs(float(e["change_pct"])), 2) for e in by_ticker.values()
                           if e is not entry and _same_company(e, entry)}
            if round(quoted, 2) in neighbours:
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


def with_review(part: dict, doc: dict) -> dict:
    """한국어 본문에 어제 판정의 결과 문장(원고 최상위 `review.result`)을 붙인 사본 — 그 문장의 숫자도 그날 시세로 대조한다."""
    result = (doc.get("review") or {}).get("result")
    return {**part, "_review_result": result} if result else part


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


# ── 원고 속 시세 사본 vs 커밋된 시세 파일(2026-10-06) ─────────────────────────────────────────────
# 관문의 숫자 대조는 원고에 붙은 price_data로 한다. 그 사본이 커밋된 data/price_<시장>_<거래일>.json과 다르면(감사: 한국 9/17·9/21·9/23,
# 미국 9/4·9/8·9/16·9/17·9/21·9/22 원고 12편) 파일은 맞아도 글은 틀린 숫자로 나가고, 아무 대조도 그것을 보지 못했다.
# 가격·등락률·기준일만 본다 — 수급(foreign_net 등)은 다음 날 아침 파일에 채워지는 칸이라 다를 수 있다.
_COPY_FIELDS = ("price", "change_pct", "trading_date")
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def copy_issues(price_data: dict, market: str, data_dir: Path | None = None) -> list[str]:
    """원고의 price_data가 커밋된 같은 거래일 시세 파일과 다른 칸. 파일이 없으면 그것도 문제다."""
    day = str(price_data.get("trading_date") or "")
    path = (data_dir or DATA_DIR) / f"price_{market}_{day}.json"
    if not day or not path.exists():
        return [f"원고의 시세 사본(기준일 {day or '없음'})에 해당하는 커밋된 시세 파일 {path.name}이 없습니다 — 시세 파일에서 그대로 옮기십시오"]
    committed = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for group in ("macro", "watchlist"):
        mine, theirs = price_data.get(group) or {}, committed.get(group) or {}
        for ticker, entry in mine.items():
            ref = theirs.get(ticker)
            if ref is None:
                out.append(f"{entry.get('name', ticker)}({ticker}): 커밋된 시세 파일에 없는 종목입니다")
                continue
            for field in _COPY_FIELDS:
                a, b = entry.get(field), ref.get(field)
                if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                    if abs(float(a) - float(b)) > 1e-9:
                        out.append(f"{entry.get('name', ticker)}({ticker}) {field}: 원고 {a} / 시세 파일 {b}")
                elif a != b:
                    out.append(f"{entry.get('name', ticker)}({ticker}) {field}: 원고 {a} / 시세 파일 {b}")
    return out


# ── '목표주가보다 N% 낮다'(2026-10-06) ─────────────────────────────────────────────────────────
# 엔진의 '목표가까지 +73%'는 목표주가가 주가보다 73% 높다는 뜻이다. 이것을 '주가가 목표주가보다 73% 낮다'로 옮기면 틀린다
# (실제로는 42% 낮다) — 9/8~10/2 33편 83곳이 그렇게 나갔다. 한 가지 꼴만 쓰게 한다: "목표주가가 주가보다 N% 높다" /
# "목표주가까지 N%". 반대 꼴은 숫자를 바르게 바꿔도 헷갈리므로 막는다.
_TARGET_BELOW_KO = re.compile(r"목표\s*주?가[^.。\n]{0,15}?(?:보다|대비|에\s*비해)[^.。\n0-9]{0,15}?[0-9]+(?:\.[0-9]+)?\s*%?\s*대?\s*(?:가량|정도|가까이|이상|넘게|안팎|남짓)?\s*(?:이상\s*)?(?:낮|아래|밑|싸|저평가|할인)"
                              r"|목표\s*주?가\s*대비\s*[-−–]\s*[0-9]")
_TARGET_BELOW_EN = re.compile(r"[0-9]+(?:\.[0-9]+)?\s*%\s+(?:below|under|beneath|short of)\s+(?:its\s+|the\s+|their\s+)?(?:average\s+|consensus\s+|analysts?'?\s+)*(?:price\s+)?target", re.I)


def _all_strings(node) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [s for k, v in node.items() if k not in ("price_data", "graphics_data") for s in _all_strings(v)]
    if isinstance(node, list):
        return [s for v in node for s in _all_strings(v)]
    return []


def target_phrase_issues(doc: dict) -> list[str]:
    """원고 어디에서든 '주가가 목표주가보다 N% 낮다' 꼴을 찾는다."""
    out = []
    for text in _all_strings({k: v for k, v in doc.items() if k != "price_data"}):
        for pattern in (_TARGET_BELOW_KO, _TARGET_BELOW_EN):
            for m in pattern.finditer(text):
                out.append(f"'{m.group(0)}' — 목표주가와의 거리는 '목표주가가 주가보다 N% 높다'(엔진의 '목표가까지 +N%' 그대로)로만 "
                           "쓰십시오. '주가가 목표주가보다 N% 낮다'는 다른 숫자입니다(+73%는 42% 낮음)")
    return out


# ── 값 수준·판단 낱말·금리 표기(2026-10-06) ──────────────────────────────────────────────────────
# 대조는 '이름 ... N.NN%' 등락률뿐이었다(감사 F-031). 그래서 금 '온스당 N달러'·원유 '배럴당 N달러'·지수 'N로 마감'·VIX·금리 수준·
# 환율 'N원'·종목 'N원(달러)으로 마감', 그리고 숫자 없이 쓴 '보합'·'급락·급등'은 아무것과도 맞춰 보지 않았다. 9/18 'WTI 6.32% 급락'
# 같은 문장은 등락률 대조가 원고 사본과만 맞춰 통과했지만, 판단 낱말과 값은 따로 틀릴 수 있다.
# 원칙은 그대로다 — 확실할 때만 실패시킨다: 값 앞에 '고점·저점·목표·전망·선·52주·평균·사상·연중' 같은 말이 있으면 그날 종가가
# 아니므로 건너뛰고, 적힌 자릿수만큼 반올림(또는 버림)한 값과 맞으면 통과다.
_LEVEL_SKIP = re.compile(r"고점|저점|목표|전망|예상|선(?:을|이|에|까지|으로|$)|52주|평균|사상|연중|최고|최저|지지|저항|이전|당시|작년|지난해|"
                         r"장중|한때|개장|시초|출발|넘|돌파|회복|아래|위로|말\s|초\s|브렌트|만약|라면|면\s|"
                         r"high|low|target|forecast|record|average|support|resistance|year-to-date|since|intraday|during|session|"
                         r"open|touched|\bhit\b|near|around|above|below|past|would|from|Brent|if\b", re.I)
_NUM = r"([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)"


def _gap(n: int) -> str:
    """이름과 값 사이 n자 — 문장을 넘지 않되 소수점(1.73%)의 점은 문장 끝으로 보지 않는다(2026-10-06: 그래서 보통 문장을 다 놓쳤다)."""
    return r"(?:[^.。!?\n]|\.(?=\d)){0,%d}?" % n


def _level_rules(lang: str) -> list[tuple[str, re.Pattern]]:
    """(티커, 패턴) — 패턴의 마지막 그룹이 그날 종가 수준이다."""
    if lang == "en":
        return [
            ("GC=F", re.compile(r"\bgold\b" + _gap(50) + r"\$" + _NUM + r"\s*(?:an|per|a|/)\s*(?:troy\s+)?ounce", re.I)),
            ("CL=F", re.compile(r"\b(?:WTI|crude|oil)\b" + _gap(50) + r"\$" + _NUM + r"\s*(?:a|per|/)\s*barrel", re.I)),
            ("^DJI", re.compile(r"\bDow(?: Jones)?\b" + _gap(50) + r"\b(?:to|at)\s+" + _NUM)),
            ("^GSPC", re.compile(r"\bS&P\s?500\b" + _gap(50) + r"\b(?:to|at)\s+" + _NUM)),
            ("^IXIC", re.compile(r"\bNasdaq(?: Composite)?\b" + _gap(50) + r"\b(?:to|at)\s+" + _NUM)),
            ("^RUT", re.compile(r"\bRussell\s?2000\b" + _gap(50) + r"\b(?:to|at)\s+" + _NUM)),
            ("KS11", re.compile(r"\bKOSPI\b" + _gap(50) + r"\b(?:to|at)\s+" + _NUM)),
            ("KQ11", re.compile(r"\bKOSDAQ\b" + _gap(50) + r"\b(?:to|at)\s+" + _NUM)),
            ("^TNX", re.compile(r"\b10-year\b" + _gap(50) + r"\b" + _NUM + r"%(?!\s*(?:points?|pp))", re.I)),
            ("^TYX", re.compile(r"\b30-year\b" + _gap(50) + r"\b" + _NUM + r"%(?!\s*(?:points?|pp))", re.I)),
            ("USD/KRW", re.compile(_NUM + r"\s*won\b", re.I)),
            # 영어 환율 꼴 "the won … to 1,372.70 per dollar"는 넣지 않았다(2026-10-06): 지난 원고에서 이 꼴은 대부분 서울 외환시장
            # 종가(뉴스)를 인용해 우리 파일의 하나은행 고시와 정의가 다르다 — 9/4·9/9 맞는 문장 둘이 걸렸다(환율 기준은 사장님 결정 대기).
        ]
    return [
        ("GC=F", re.compile(r"(?:국제\s*금|금값|금\s*선물|금은|금이|금도)" + _gap(40) + r"온스당\s*" + _NUM + r"\s*달러")),
        ("CL=F", re.compile(r"(?:WTI|서부텍사스산\s*원유|국제\s*유가|원유|유가)" + _gap(40) + r"배럴당\s*" + _NUM + r"\s*달러")),
        ("^DJI", re.compile(r"다우(?:존스)?" + _gap(40) + r"" + _NUM + r"\s*(?:로|으로|에)\s*(?:마감|마쳤|끝났|장을)")),
        ("^GSPC", re.compile(r"S&P\s?500" + _gap(40) + r"" + _NUM + r"\s*(?:로|으로|에)\s*(?:마감|마쳤|끝났|장을)")),
        ("^IXIC", re.compile(r"나스닥(?:종합)?" + _gap(40) + r"" + _NUM + r"\s*(?:로|으로|에)\s*(?:마감|마쳤|끝났|장을)")),
        ("^RUT", re.compile(r"러셀\s?2000" + _gap(40) + r"" + _NUM + r"\s*(?:로|으로|에)\s*(?:마감|마쳤|끝났|장을)")),
        ("KS11", re.compile(r"코스피" + _gap(40) + r"" + _NUM + r"\s*(?:로|으로|에)\s*(?:마감|마쳤|끝났|장을)")),
        ("KQ11", re.compile(r"코스닥" + _gap(40) + r"" + _NUM + r"\s*(?:로|으로|에)\s*(?:마감|마쳤|끝났|장을)")),
        ("^VIX", re.compile(r"VIX" + _gap(30) + r"" + _NUM + r"(?:\s*(?:로|으로|을|를|에|까지)|\)|$)")),
        ("^TNX", re.compile(r"10년(?:물|\s*만기)" + _gap(40) + r"" + _NUM + r"\s*%(?!\s*(?:p|포인트|P))")),
        ("^TYX", re.compile(r"30년(?:물|\s*만기)" + _gap(40) + r"" + _NUM + r"\s*%(?!\s*(?:p|포인트|P))")),
        ("USD/KRW", re.compile(r"(?:원/달러|원·달러|원달러|환율)" + _gap(40) + r"" + _NUM + r"\s*원")),
    ]


def _num(text: str) -> tuple[float, int]:
    clean = text.replace(",", "")
    return float(clean), (len(clean.split(".")[1]) if "." in clean else 0)


def _level_matches(written: str, actual: float) -> bool:
    value, places = _num(written)
    step = 10 ** -places
    return abs(value - actual) <= step + 1e-9      # 그 자릿수로 반올림·버림한 값이면 맞다


def _other_day_in_sentence(text: str, start: int, end: int) -> bool:
    """같은 문장에 다른 날을 가리키는 말(어제·전날·지난·날짜…)이 있으면 그날 종가 문장이 아니다."""
    lo, hi = _sentence_bounds(text, start)
    return bool(_OTHER_DAY.search(text[lo:max(hi, end)]))


def level_issues(doc: dict, price_data: dict, lang: str = "ko") -> list[str]:
    """그날 종가 수준(지수·금·원유·VIX·금리·환율)이 시세와 맞는지."""
    entries = {**(price_data.get("macro") or {}), **(price_data.get("watchlist") or {})}
    out = []
    for where, text in _texts(doc):
        for ticker, pattern in _level_rules(lang):
            entry = entries.get(ticker)
            if not entry or entry.get("price") is None:
                continue
            actual = float(entry["price"])
            for m in pattern.finditer(text):
                written = m.group(m.lastindex)
                between = text[m.start():m.start(m.lastindex)]
                lo, hi = _sentence_bounds(text, m.start())
                sentence = text[lo:max(hi, m.end())]
                tail = text[m.end():m.end() + 10]
                if (_LEVEL_SKIP.search(between) or _other_day_in_sentence(text, m.start(), m.end())
                        or re.search(r"^\s*(?:%\s*)?(?:을|를|이|가)?\s*(?:넘|돌파|웃|밑|하회|상회|선|이상|이하|에서|부터)", tail)
                        or re.search(r"서울\s*외환|외환시장|15시\s*30분|오후\s*3시\s*30분|Seoul FX|3:30\s*p\.?m", sentence, re.I)):
                    continue   # 조건·기준선, 또는 다른 기준(서울 외환시장 종가)을 밝힌 인용
                value, places = _num(written)
                if places == 0 or not (0.7 * actual <= value <= 1.3 * actual):   # 어림수(100달러·6,900선)와 전혀 다른 숫자는 대조하지 않는다
                    continue
                if not _level_matches(written, actual):
                    out.append(f"{where}: {entry.get('name', ticker)} '{m.group(0)[-60:]}' — 그날 종가 {actual:g}와 다릅니다")
    return out


_JUDGE_WORDS = re.compile(r"보합|급락|급등|폭락|폭등|plunge|plummet|soar|surge|flat|unchanged", re.I)


def judgment_word_issues(doc: dict, price_data: dict, lang: str = "ko") -> list[str]:
    """이름 바로 뒤의 '보합'·'급락·급등'이 그날 등락과 맞는지 — 보합은 ±0.2% 안, 급락·급등은 방향이 같고 1% 이상."""
    names = _names_by_length(price_data, lang)
    out = []
    for where, text in _texts(doc):
        for m in _JUDGE_WORDS.finditer(text):
            start = max(0, m.start() - 25)
            window = text[start:m.start()]
            if re.search(r"[.。!?]", window):
                window = re.split(r"[.。!?]", window)[-1]
            lo, hi = _sentence_bounds(text, m.start())
            sentence = text[lo:max(hi, m.end())]
            if (_other_day_in_sentence(text, m.start(), m.end())
                    or re.search(r"장중|한때|intraday|earlier|최근|며칠|뒤\s|이후|후\s|recent|after", sentence, re.I)
                    or text[max(0, m.start() - 1):m.start()] in ("강", "약")   # 강보합·약보합은 작은 상승·하락을 뜻하는 맞는 말
                    or text[m.end():m.end() + 1] == "분" or re.search(r"되돌|만회|회복", sentence)   # '급락분을 되돌렸다'는 장중 이야기
                    or re.match(r"\s*(?:에서|으로부터|from)\b", text[m.end():m.end() + 6])):   # '급등에서 급락으로' — 앞 낱말은 전의 상태(그림 제목, 2026-10-06)
                continue
            hit = next(((n, e) for n, e in names if n and window.rfind(n) >= 0
                        and not re.search(r"[0-9]", window[window.rfind(n) + len(n):])), None)
            if not hit or hit[1].get("change_pct") is None:
                continue
            name, entry = hit
            pct, word = float(entry["change_pct"]), m.group(0).lower()
            if word in ("보합", "flat", "unchanged"):
                if abs(pct) >= 0.2:
                    out.append(f"{where}: {name} '{word}' — 그날 {pct:+.2f}%")
            elif word in ("급락", "폭락", "plunge", "plummet"):
                if pct > -1.0:
                    out.append(f"{where}: {name} '{word}' — 그날 {pct:+.2f}%(방향이 다르거나 1% 미만)")
            elif pct < 1.0:
                out.append(f"{where}: {name} '{word}' — 그날 {pct:+.2f}%(방향이 다르거나 1% 미만)")
    return out


_NO_PCT_GAP = r"(?:[^.。!?\n%]|\.(?=\d)){0,40}?"   # 사이에 다른 %가 끼면 다른 숫자다('…4.81% as WTI jumped 3.16%')
_YIELD_CHANGE = {
    "ko": re.compile(r"(?:10년물|30년물|10년\s*만기|30년\s*만기|국채\s*금리)" + _NO_PCT_GAP + _NUM
                     + r"\s*%(?!\s*(?:p|P|포인트))\s*(?:올|오르|오른|상승|내|내린|내리|하락|떨어|급등|급락|뛰|높아|낮아)"),
    "en": re.compile(r"\b(?:10-year|30-year|Treasury)\b" + _NO_PCT_GAP
                     + r"\b(?:rose|climbed|jumped|fell|dropped|slid|gained|added|eased|up|down)\s+(?:by\s+)?" + _NUM + r"%(?!\s*points?)", re.I),
}


def yield_change_issues(doc: dict, price_data: dict, lang: str = "ko") -> list[str]:
    """금리 등락을 %로 쓴 곳 — 금리 등락은 %p(bp)로 쓴다(2026-10-06, 감사 F-035). 적힌 수가 그날 금리 수준이면 통과."""
    macro = price_data.get("macro") or {}
    levels = [float(e["price"]) for t, e in macro.items() if str(e.get("unit") or "").strip() == "%" and e.get("price") is not None]
    out = []
    for where, text in _texts(doc):
        for m in _YIELD_CHANGE[lang].finditer(text):
            written = m.group(m.lastindex)
            if any(_level_matches(written, level) for level in levels):
                continue
            out.append(f"{where}: '{m.group(0)[-50:]}' — 금리 등락은 %p(또는 bp)로 쓰십시오(5.11% 금리가 '3.04% 올랐다'는 0.15%p)")
    return out


# ── 원고에 내부 도구 이름(2026-10-06) ───────────────────────────────────────────────────────────
# 'story_engines 계절성 엔진에 따르면'처럼 우리 내부 모듈·파일 이름이 출처인 양 독자에게 나갔다(감사 F-067). 독자에게는 원천(야후·
# EDGAR·한국거래소 등)을 밝히고 도구 이름은 쓰지 않는다.
_INTERNAL = re.compile(r"story_engines|editorial_(?:facts|gate|quality)|feature_gate|weekly_stats|routine_\w+|"
                       r"engines_(?:kr|us)|price_(?:kr|us)_\d|\b\w+\.(?:py|json|txt)\b|"
                       r"(?:계절성|밸류에이션|의견\s*변경|내부자|월가 리포트|13F|업종)\s*엔진|엔진(?:에 따르면|이 집계|으로 계산|출력)", re.I)


def internal_name_issues(doc: dict) -> list[str]:
    out = []
    for text in _all_strings({k: v for k, v in doc.items() if k not in ("price_data", "sources", "graphics")}):
        for m in _INTERNAL.finditer(text):
            out.append(f"'{m.group(0)}' — 내부 도구·파일 이름은 본문에 쓰지 않습니다. 원천(야후 파이낸스·EDGAR·한국거래소 등)을 밝히십시오")
    return out


# 주간 결산(2026-10-06): 주간 등락률을 `scripts/weekly_stats`와 같은 계산으로 대조한다. 하루 등락·다른 주·장중 숫자는
# 건너뛴다 — 요일·'하루'·'지난주'·날짜가 창에 있으면 그날·그 주의 숫자다. 업종 평균은 대조하지 않고 이웃 숫자로만
# 쓴다("자동차(-2.89%, 현대차·기아)와 조선·방산(-0.03%" — 기아에 뒤 업종 숫자가 붙는다). 지난 네 편에 돌려 0건.
_OTHER_DAY_WEEK = re.compile(
    r"(어제|전날|하루|당일|월요일|화요일|수요일|목요일|금요일|첫날|마지막 날|장중|지난주|전주|직전|이틀|사흘|\d+거래일"
    r"|\d+월 \d+일|\d+/\d+|\d+일|→|올해|이달|한 달|석 달|연초|yesterday|last week)"
)


def weekly_price_data(path: Path) -> dict:
    """시세 파일 하나를 '주간 등락이 change_pct인' 시세 꼴로 — 금리·VIX(포인트로 읽는 것)는 뺀다. 업종 평균은 `_sector`."""
    from scripts import weekly_stats
    market = "kr" if "_kr_" in path.name else "us"
    price_data = json.loads(path.read_text(encoding="utf-8"))
    weekly_stats.augment_from_daily_files(price_data, market, path.parent)
    result = weekly_stats.compute(price_data, market)
    by_ticker = {str(e.get("ticker") or k): (g, k) for g in ("macro", "watchlist")
                 for k, e in (price_data.get(g) or {}).items()}
    out: dict = {"trading_date": None, "macro": {}, "watchlist": {}}
    for row in [*result["macro"], *result["stocks"]]:
        if row["points"] or row["week_pct"] is None or row["ticker"] not in by_ticker:
            continue
        group, key = by_ticker[row["ticker"]]
        out[group][key] = {**price_data[group][key], "change_pct": row["week_pct"]}
    for row in result["sectors"]:
        out["watchlist"][f"sector:{row['name']}"] = {"name": row["name"], "ticker": f"sector:{row['name']}",
                                                    "change_pct": row["avg_pct"], "_sector": True}
    return out


def weekly_issues(doc: dict, root: Path = ROOT) -> list[str]:
    """주간 결산 원고: 그래픽이 가리키는 시세 파일마다 (1) 이력이 날마다 확인한 종가와 같은지(`weekly_stats.verify`),
    (2) 본문·제목·숫자 카드에 적은 주간 등락률이 그 파일의 주간 계산과 같은지."""
    from scripts import weekly_stats
    ko = doc.get("ko") or doc
    files = sorted({str(spec["price_file"]) for spec in doc.get("graphics") or [] if spec.get("price_file")})
    if not files:
        return ["그래픽에 price_file이 하나도 없어 주간 숫자를 대조할 수 없습니다 — 시세 그래픽에 시세 파일을 적으십시오."]
    texts = dict(ko)
    extra = [{"heading": "", "body": " ".join(str(v) for v in _all_strings(ko.get("closing") or {}))}]
    for spec in doc.get("graphics") or []:
        for item in (spec.get("args") or {}).get("items") or []:
            extra.append({"heading": "", "body": f"{item.get('label', '')} {item.get('change', '')}"})
    texts["narrative"] = list(ko.get("narrative") or []) + extra
    issues: list[str] = []
    for name in files:
        path = root / name
        if not path.exists():
            issues.append(f"[{name}] 시세 파일이 없습니다.")
            continue
        price_data = json.loads(path.read_text(encoding="utf-8"))
        market = "kr" if "_kr_" in path.name else "us"
        issues.extend(f"[{path.stem}] {i}" for i in weekly_stats.verify(price_data, market, path.parent))
        weekly = weekly_price_data(path)
        sectors = {e["name"] for e in weekly["watchlist"].values() if e.get("_sector")}
        for issue in collect_issues(texts, weekly, other_day=_OTHER_DAY_WEEK, require_lead=False):
            if not any(f"'{s}'" in issue for s in sectors):
                issues.append(f"[{path.stem}] 주간 {issue}")
    return issues


# ── 날짜가 박힌 숫자(2026-10-06, 감사 F-030·F-052·F-063) ──────────────────────────────────────────────
# Checkpoint·가이드·이벤트·다음 주 일정은 시세 파일과 대조하지 않아 "9월 23일 코스피 0.09% 상승"(실제 +0.90%)이 그대로 나갔다.
# 문장에 'M월 D일'이 있고 그날 커밋한 시세 파일이 있으면 그 문장을 그 파일과 대조한다 — 날짜가 없는 문장은 어느 날 값인지 몰라 보지 않는다.
_KO_DATE = re.compile(r"(?<!\d)(\d{1,2})월\s*(\d{1,2})일")


def dated_issues(doc: dict, year: int | None = None, data_dir: Path | None = None) -> list[str]:
    folder = data_dir or DATA_DIR
    part = doc.get("ko") or doc
    year = year or int(str(doc.get("date") or "2026")[:4])
    out: list[str] = []
    for where, text in _texts(part):
        for m in _KO_DATE.finditer(text):
            try:
                day = f"{year}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
            except ValueError:
                continue
            lo, hi = _sentence_bounds(text, m.start())
            if len(_KO_DATE.findall(text[lo:hi])) != 1 or re.search(r"거래일|_", text[lo:m.start()]) \
                    or _PERIOD_MARK.search(text[lo:hi]) or _OTHER_DAY.search(text[lo:m.start()]):
                continue   # 날짜가 둘 이상이거나 기간·다른 날 이야기면 어느 숫자가 어느 날 것인지 모른다
            sentence = text[m.start():hi]   # 날짜 뒤의 이름·숫자만 — 날짜 앞의 숫자는 다른 날 것일 수 있다
            for market in ("kr", "us"):
                path = folder / f"price_{market}_{day}.json"
                if not path.exists():
                    continue
                price_data = json.loads(path.read_text(encoding="utf-8"))
                if any(len(e.get("close_sources") or []) < 2 for e in (price_data.get("watchlist") or {}).values()):
                    continue   # 두 원천 확인 전 파일(10/6 전 한국장·10/5 전 미국장)은 값 자체가 틀린 것이 있어 기준으로 쓰지 않는다
                mini = {"narrative": [{"heading": "", "body": sentence}]}
                found = collect_issues(mini, price_data, require_lead=False) + level_issues(mini, price_data)
                head = sentence[:len(m.group(0)) + 30]   # 이름이 날짜 바로 뒤(30자 안)에 있을 때만 — "9월 23일 코스피는 0.09%"
                for issue in found:
                    named = re.search(r"'([^']+)'", issue)
                    if named and named.group(1) in head:
                        out.append(f"{where} [{day} {market}]: {issue.split(': ', 1)[-1]}")
    return sorted(set(out))
