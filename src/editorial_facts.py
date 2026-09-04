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
- 소수점이 없는 비율("5%대 상승")은 건너뜁니다. 어림수는 원고에서 정상입니다.
- 보유율·지분율 문맥의 퍼센트는 건너뜁니다("외국인 보유율은 5.54%").
- 종목명 근처에 등락을 뜻하는 말이 없으면 건너뜁니다. 업종지수나 수급 비중처럼
  종목 등락률이 아닌 숫자를 잘못 잡지 않기 위해서입니다.

즉 확실할 때만 실패시킵니다. 놓치는 것은 있어도, 맞는 원고를 막지는 않습니다.
"""
from __future__ import annotations

import re


class EditorialFactError(ValueError):
    """원고의 숫자가 시세와 어긋날 때 발생합니다."""


# "8.58%" 처럼 소수점이 있는 비율만 봅니다.
_PERCENT = re.compile(r"(\d+\.\d+)\s*%")
# 종목명 주변에 이런 말이 있어야 '등락률을 말한 것'으로 봅니다.
_MOVE_WORDS = re.compile(
    r"(올랐|올라|오른|오르|상승|내렸|내려|내린|하락|급등|급락|마감|반등|약세|강세"
    r"|rose|fell|gained|lost|closed|climbed|dropped|slid|added|up |down )",
    re.IGNORECASE,
)
# 이런 말이 있으면 등락률이 아니라 보유율·비중입니다.
_NOT_A_MOVE = re.compile(
    r"(보유율|지분|비중|점유율|ratio|stake|ownership|holding|share of)", re.IGNORECASE
)
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
    r"(어제|전날|지난|직전|이틀|전 거래일|다음 거래일|\d+월 \d+일|\d+/\d+|→)"
)
_WINDOW_BEFORE, _WINDOW_AFTER = 20, 45


def _texts(doc: dict) -> list[tuple[str, str]]:
    """원고에서 숫자가 들어갈 수 있는 자리를 (위치 이름, 글) 목록으로 모읍니다."""
    out: list[tuple[str, str]] = [("제목", str(doc.get("title", "")))]
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
    return [(where, text) for where, text in out if text]


def _entries(price_data: dict) -> list[dict]:
    return list((price_data.get("watchlist") or {}).values())


def _names_by_length(price_data: dict, lang: str) -> list[tuple[str, dict]]:
    """긴 이름부터 봅니다 — '에코프로비엠'을 '에코프로'로 잘못 읽지 않으려고."""
    key = "name_en" if lang == "en" else "name"
    pairs = [
        (str(entry.get(key) or entry.get("name") or ""), entry)
        for entry in _entries(price_data)
    ]
    return sorted((p for p in pairs if p[0]), key=lambda p: len(p[0]), reverse=True)


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


def _quoted_moves(text: str, names: list[tuple[str, dict]]) -> list[tuple[dict, float]]:
    """글에서 (종목, 원고가 적은 등락률) 쌍을 뽑습니다."""
    found: list[tuple[dict, float]] = []
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
            claimed.append((at, end))
            window = text[max(0, at - _WINDOW_BEFORE) : end + _WINDOW_AFTER]
            if _NOT_A_MOVE.search(window) or _INTRADAY.search(window):
                continue
            if _OTHER_DAY.search(window):
                continue
            if not _MOVE_WORDS.search(window) and "(" not in window:
                continue
            for match in _PERCENT.finditer(_same_sentence_tail(text, end, names)):
                found.append((entry, float(match.group(1))))
                break  # 이름 뒤 첫 번째 비율만 봅니다
    return found


def collect_issues(doc: dict, price_data: dict, lang: str = "ko") -> list[str]:
    """숫자 대조와 주인공 누락 검사를 한 번에 수행합니다."""
    issues: list[str] = []
    entries = _entries(price_data)
    if not entries:
        return issues

    names = _names_by_length(price_data, lang)
    known_percents = {round(abs(float(e["change_pct"])), 2) for e in entries}
    for where, text in _texts(doc):
        for entry, quoted in _quoted_moves(text, names):
            actual = round(abs(float(entry["change_pct"])), 2)
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

    lead = max(entries, key=lambda e: abs(float(e["change_pct"])))
    haystack = " ".join(text for _, text in _texts(doc))
    tickers = set((doc.get("stock_section") or {}).get("featured_tickers") or [])
    tickers |= {
        h.get("ticker") for h in (doc.get("theme_section") or {}).get("highlights") or []
    }
    mentioned = (
        str(lead.get("name", "")) in haystack
        or str(lead.get("name_en", "")) in haystack
        or lead.get("ticker") in tickers
    )
    if not mentioned and abs(float(lead["change_pct"])) >= 1.0:
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
