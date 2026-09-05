"""실제 시세로 1200×630 대표 이미지를 만들어 사진 검색 오류를 없앱니다.

레이아웃 둘을 그날 상황에 따라 고릅니다
--------------------------------------
2026-09-05까지는 레이아웃이 하나였고 색만 다섯 단계로 바뀌었습니다. 그래서
목록에서 훑으면 매일 같은 그림으로 보였습니다 — 지수 카드 3개가 화면을
차지하고, 그날의 주인공 종목은 맨 아래 작은 줄 하나였습니다.

지금은 **그날 이야기의 모양**에 따라 둘 중 하나를 그립니다.

  single — 주인공이 하나인 날. 종목명과 등락률을 화면 크기로 씁니다.
  trio   — 여러 종목이 함께 움직인 날. 상위 셋을 타일로 나열합니다.

고르는 기준은 아래 `choose_layout()`에 있습니다. 원고 제목이 종목을 하나만
부르면 그 종목이 그날의 주인공이므로 single, 여럿을 부르거나 아무 종목도
부르지 않으면 수치로 판단합니다.

**좌우 안전 영역(SAFE_LEFT~SAFE_RIGHT)을 반드시 지킬 것.**
테마의 목록 카드는 `aspect-ratio: 4/3` + `object-fit: cover`입니다
(2026-09-05 실측: 데스크톱 311×233, 모바일 330×248. 맨 위 대표 카드만 16:9).
1200×630(1.905:1) 이미지를 1.333:1 상자에 cover로 넣으면 높이에 맞춰 확대된 뒤
보이는 폭이 630×4/3 = 840px뿐이라 **좌우가 각각 180px씩 잘립니다.**

이 값은 두 번 틀렸습니다. 처음엔 안전 영역이 없어 "FERMATA"가 "RMATA"로,
"Ecopro"가 "opro"로 잘렸습니다. 2026-09-01에 3:2(각 127px)로 고쳤는데, 그 뒤
테마 카드가 4:3으로 바뀌어 있었습니다 — 2026-09-05에 새 레이아웃을 올리고
사이트를 열어 보니 종목 타일의 왼쪽 막대와 등락률 끝이 잘려 있었습니다.
**화면을 직접 재기 전에는 이 숫자를 바꾸지 말 것.**

1200×630은 소셜 공유(OG) 표준 비율이라 유지하고, 대신 글자와 카드를 가운데
840px 영역 안에만 배치해 어느 쪽에서 잘려도 내용이 살아남게 합니다.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from . import data_graphics

# 4:3 중앙 크롭에서 살아남는 좌우 안전 영역 (1200×630 기준, 각 변 180px 잘림)
SAFE_LEFT = 180
SAFE_RIGHT = 1020
_PAD = 20                           # 경계에 딱 붙지 않도록 한 뼘
_CONTENT_LEFT = SAFE_LEFT + _PAD    # 200
_CONTENT_RIGHT = SAFE_RIGHT - _PAD  # 1000

# 오르면 빨강, 내리면 파랑 — 본문 그래픽(data_graphics)과 같은 약속입니다.
_UP = "#E5484D"
_DOWN = "#3E7BFA"
_UP_DARK = "#FF6B62"      # 어두운 바탕에서 읽히게 한 단계 밝힌 색
_DOWN_DARK = "#5C9DFF"


def _font(size: int, bold: bool = True):
    return data_graphics.korean_font(size, bold)


# 영문판에서 그대로 쓰면 카드를 넘치는 지수 이름들
_EN_ALIASES = {
    "Dow Jones Industrial Average": "Dow Jones",
    "Nasdaq Composite": "Nasdaq",
    "US 10-Year Treasury Yield": "U.S. 10Y Yield",
    "US 30-Year Treasury Yield": "U.S. 30Y Yield",
}


def _name(entry: dict, lang: str = "ko") -> str:
    """그림에 쓸 이름.

    영문판(lang="en")은 영어 독자가 읽는 글이므로 영문 표기만 씁니다. 한국어판은
    한글 이름을 쓰되, 한글 폰트가 없으면(우분투 러너에 fonts-nanum이 빠진 경우)
    영문 표기로 물러섭니다. 한글 폰트 없이 한글을 그리면 두부 상자(□□□)가 찍힌
    그림이 그대로 사이트에 올라갑니다 — 2026-09-04에 실제로 겪은 일입니다.
    """
    korean = entry.get("name") or entry.get("ticker", "Market")
    english = entry.get("name_en") or entry.get("name") or entry.get("ticker", "Market")
    if lang == "en":
        return _EN_ALIASES.get(english, english)
    if data_graphics.has_korean_font():
        return korean
    return _EN_ALIASES.get(english, english)


def _change(entry: dict) -> str:
    return f"{entry['change_pct']:+.2f}%"


def _price(entry: dict, lang: str = "ko") -> str:
    """지수·환율은 호가 그대로 씁니다(코스피 6,687.21 / 원/달러 1,351.3원)."""
    if entry.get("unit") != "원":
        return f"{entry['price']:,}"
    return f"{entry['price']:,} KRW" if lang == "en" else f"{entry['price']:,}원"


def _stock_price(entry: dict, market: str, lang: str = "ko") -> str:
    """종목 주가. 108,000.0과 154.27이 섞이면 타일이 지저분해집니다."""
    value = entry["price"]
    if market == "kr":
        return f"{value:,.0f} KRW" if lang == "en" else f"{value:,.0f}원"
    return f"{value:,.0f}" if abs(value) >= 1000 else f"{value:,.2f}"


def _macro(price_data: dict) -> list[dict]:
    return list(price_data.get("macro", {}).values())[:3]


def _ranked(price_data: dict) -> list[dict]:
    """그날 절대 등락 폭 순서. 거래대금으로 편입된 종목도 함께 봅니다.

    사진(publish_editorial._concrete_image_query)과 달리 여기서는 편입 종목을
    막을 이유가 없습니다. 대표 이미지는 데이터에서 텍스트를 그리는 것이라
    "엉뚱한 그림이 붙는" 위험 자체가 없습니다.
    """
    return sorted(
        price_data.get("watchlist", {}).values(),
        key=lambda entry: abs(entry["change_pct"]),
        reverse=True,
    )


def lead_watchlist_entry(price_data: dict) -> dict | None:
    """대문에 이름을 걸 종목 — 그날 절대 등락 폭이 가장 큰 종목입니다."""
    ranked = _ranked(price_data)
    return ranked[0] if ranked else None


# 1위가 2위를 이만큼 앞서면 "주인공이 하나인 날"로 봅니다.
#
# 실제 7거래일에 대보면 이렇게 갈립니다(2026-09-01~04):
#   2.72배 델 테크놀로지스(15.81%) vs 팔란티어(5.81%)     → single
#   1.18배 에코프로비엠(-7.06%) vs 에코프로(-5.96%)        → trio
# 앞의 날은 델 하나로 설명되는 날이고, 뒤의 날은 2차전지가 통째로 밀린
# 날입니다. 그림도 그렇게 달라야 합니다.
_SOLO_RATIO = 2.0


def _stocks_named_in_title(doc: dict | None, price_data: dict) -> list[dict]:
    """원고 제목이 부른 종목들.

    그날 그림의 주인공은 우리가 계산한 1위가 아니라 **그날 글이 다룬 종목**입니다.
    제목이 "샌디스크 11.90% 급등!"이면 샌디스크가 주인공이고, 제목이 종목을
    둘 이상 부르거나 하나도 부르지 않으면 그날은 한 종목의 날이 아닙니다.
    """
    title = (doc or {}).get("title") or ""
    if not title:
        return []

    # 긴 이름부터 보고, 맞은 자리는 지웁니다.
    #
    # "에코프로비엠 7.06% 급락!"은 종목 하나를 부른 제목인데, 그냥 부분 문자열로
    # 세면 에코프로비엠과 에코프로 둘이 잡혀 "여러 종목의 날"로 넘어갑니다.
    # 삼성전자/삼성전기, 에코프로/에코프로비엠처럼 이름이 겹치는 짝이 실제로
    # 워치리스트에 있습니다.
    remaining = title
    found = []
    entries = _ranked(price_data)
    by_length = sorted(
        ((len(name), name, entry)
         for entry in entries
         for name in (entry.get("name"), entry.get("name_en")) if name),
        key=lambda item: item[0],
        reverse=True,
    )
    seen: set[int] = set()
    for _, name, entry in by_length:
        if id(entry) in seen or name not in remaining:
            continue
        remaining = remaining.replace(name, " ")
        seen.add(id(entry))
        found.append(entry)
    # 등락 폭 순서를 유지합니다 — single일 때 주인공을 고르는 순서가 됩니다.
    return [entry for entry in entries if id(entry) in seen] if found else []


def choose_layout(price_data: dict, doc: dict | None = None) -> str:
    """그날 그릴 레이아웃을 고릅니다 — "single" 또는 "trio"."""
    ranked = _ranked(price_data)
    if len(ranked) < 3:
        # 셋을 나열할 수 없으면 하나짜리로 갑니다.
        return "single"

    named = _stocks_named_in_title(doc, price_data)
    if len(named) == 1:
        return "single"
    if len(named) >= 2:
        return "trio"

    # 제목이 종목을 부르지 않은 날(지수·정책이 주인공인 날)은 수치로 봅니다.
    top, second = abs(ranked[0]["change_pct"]), abs(ranked[1]["change_pct"])
    if second and top / second >= _SOLO_RATIO:
        return "single"
    return "trio"


def _lead_for(price_data: dict, doc: dict | None) -> dict | None:
    """single 레이아웃에 세울 종목 — 제목이 부른 종목이 있으면 그 종목입니다."""
    named = _stocks_named_in_title(doc, price_data)
    if len(named) == 1:
        return named[0]
    return lead_watchlist_entry(price_data)


def _market_line(market: str, date_str: str, lang: str = "ko") -> str:
    if lang == "en" or not data_graphics.has_korean_font():
        label = "Korea Market Close" if market == "kr" else "U.S. Market Close"
    else:
        label = "한국장 마감" if market == "kr" else "미국장 마감"
    return f"{label}  ·  {date_str}"


def _fit(draw, text: str, size: int, width: int, bold: bool = True):
    """폭에 들어갈 때까지 글자 크기를 줄입니다.

    "델 테크놀로지스"처럼 긴 이름이 안전 영역 밖으로 나가면 잘려 보입니다.
    """
    font = _font(size, bold)
    while size > 24 and draw.textlength(text, font=font) > width:
        size -= 4
        font = _font(size, bold)
    return font


def _draw_macro_row(draw, top: int, price_data: dict, *, ink: str, sub: str,
                    dark: bool, lang: str) -> None:
    """아래쪽 지수 한 줄. 시황이니 마감 숫자는 대문에 남습니다."""
    up, down = (_UP_DARK, _DOWN_DARK) if dark else (_UP, _DOWN)
    x = _CONTENT_LEFT
    for entry in _macro(price_data):
        draw.text((x, top), _name(entry, lang), font=_font(19, False), fill=sub)
        price = _price(entry, lang)
        draw.text((x, top + 26), price, font=_font(24), fill=ink)
        draw.text(
            (x + draw.textlength(price, font=_font(24)) + 10, top + 29),
            _change(entry),
            font=_font(20),
            fill=up if entry["change_pct"] >= 0 else down,
        )
        x += 270


def _render_single(canvas: Image.Image, market: str, date_str: str,
                   price_data: dict, lead: dict, lang: str) -> None:
    """주인공이 하나인 날 — 종목명과 등락률만으로 채웁니다."""
    draw = ImageDraw.Draw(canvas)
    ink, sub, line = "#111111", "#8A9099", "#DDDDDD"

    draw.text((_CONTENT_LEFT, 96), "FERMATA", font=_font(22), fill=ink)
    meta = _market_line(market, date_str, lang)
    draw.text(
        (_CONTENT_RIGHT - draw.textlength(meta, font=_font(22, False)), 98),
        meta, font=_font(22, False), fill=sub,
    )
    draw.line((_CONTENT_LEFT, 140, _CONTENT_RIGHT, 140), fill=ink, width=3)

    width = _CONTENT_RIGHT - _CONTENT_LEFT
    name = _name(lead, lang)
    draw.text((_CONTENT_LEFT, 196), name, font=_fit(draw, name, 78, width), fill=ink)
    change = _change(lead)
    draw.text((_CONTENT_LEFT, 300), change,
              font=_fit(draw, change, 140, width),
              fill=_UP if lead["change_pct"] >= 0 else _DOWN)

    draw.line((_CONTENT_LEFT, 486, _CONTENT_RIGHT, 486), fill=line, width=1)
    _draw_macro_row(draw, 508, price_data, ink=ink, sub=sub, dark=False, lang=lang)


def _render_trio(canvas: Image.Image, market: str, date_str: str,
                 price_data: dict, top3: list[dict], lang: str) -> None:
    """여러 종목이 함께 움직인 날 — 상위 셋을 나열합니다.

    머리글을 달지 않습니다. 한때 "오늘 크게 움직인 종목"을 붙였는데, 종목명과
    등락률이 이미 그 말을 하고 있어 글자만 늘었습니다. 게다가 최상급을 피하려고
    고른 문구라 길기만 하고, 목록 썸네일 크기에서는 읽히지도 않았습니다.
    """
    draw = ImageDraw.Draw(canvas)
    ink, sub, tile = "#FFFFFF", "#6B7280", "#1C2029"

    draw.text((_CONTENT_LEFT, 88), "FERMATA", font=_font(22), fill=sub)
    meta = _market_line(market, date_str, lang)
    draw.text(
        (_CONTENT_RIGHT - draw.textlength(meta, font=_font(22, False)), 88),
        meta, font=_font(22, False), fill=sub,
    )

    top = 148
    for entry in top3:
        up = entry["change_pct"] >= 0
        accent = _UP_DARK if up else _DOWN_DARK
        draw.rounded_rectangle((SAFE_LEFT, top, SAFE_RIGHT, top + 118), radius=16, fill=tile)
        draw.rounded_rectangle((SAFE_LEFT, top, SAFE_LEFT + 7, top + 118), radius=4, fill=accent)
        name = _name(entry, lang)
        draw.text((SAFE_LEFT + 30, top + 28), name,
                  font=_fit(draw, name, 40, 460), fill=ink)
        draw.text((SAFE_LEFT + 30, top + 80), _stock_price(entry, market, lang),
                  font=_font(20, False), fill=sub)
        change = _change(entry)
        font = _font(48)
        draw.text((SAFE_RIGHT - 30 - draw.textlength(change, font=font), top + 34),
                  change, font=font, fill=accent)
        top += 138

    x = _CONTENT_LEFT
    for entry in _macro(price_data):
        draw.text((x, 572), f"{_name(entry, lang)} {_change(entry)}",
                  font=_font(19, False), fill=sub)
        x += 270


def create(market: str, date_str: str, price_data: dict, output_path: Path,
           doc: dict | None = None, lang: str = "ko") -> dict:
    """대표 이미지 파일을 만들고 publish_wordpress가 받는 메타데이터를 반환합니다.

    doc:  그날 원고(한국어). 제목이 부른 종목으로 레이아웃과 주인공을 정합니다.
          없으면(main.py의 규칙 기반 초안) 수치만 보고 정합니다.
    lang: 그림에 쓸 언어. 영어판 글에는 종목명·지수명·시장 라벨이 모두 영어로
          들어가야 합니다 — 영어 글에 한글 이름이 박힌 그림이 붙으면 읽는
          사람이 무슨 종목인지 알 수 없습니다. 레이아웃 선택은 두 언어가 같으므로
          (같은 날 같은 이야기) 한국어 원고 하나로 정합니다.
    """
    layout = choose_layout(price_data, doc)
    ranked = _ranked(price_data)

    if layout == "trio":
        drawn = ranked[:3]
        canvas = Image.new("RGB", (1200, 630), "#12141A")
        _render_trio(canvas, market, date_str, price_data, drawn, lang)
    else:
        lead = _lead_for(price_data, doc)
        drawn = [lead] if lead else []
        canvas = Image.new("RGB", (1200, 630), "#FBFBF9")
        if not lead:
            # 종목이 하나도 없으면 지수만 그립니다(자료 장애 날).
            lead = _macro(price_data)[0] if _macro(price_data) else {
                "name": "-", "name_en": "-", "price": 0, "change_pct": 0.0}
        _render_single(canvas, market, date_str, price_data, lead, lang)

    output_path.parent.mkdir(exist_ok=True)
    canvas.save(output_path, format="PNG", optimize=True)

    # alt에는 **그림에 실제로 그린 것**을 전부 넣습니다.
    #
    # 설명글로서 맞기도 하지만, publish_wordpress._featured_media_matches가 이
    # alt로 "같은 데이터로 만든 이미지인지"를 판단하기 때문이기도 합니다.
    # 지수 값만 넣었더니 2026-09-03에 이런 일이 있었습니다 — 대문 종목이
    # 알테오젠에서 삼성중공업으로 바뀌었는데 지수 숫자가 같아 alt가 동일했고,
    # 기존 미디어를 재사용하는 바람에 제목은 삼성중공업 8.58%인데 대표 이미지는
    # "Alteogen -5.19%"인 글이 공개됐습니다. 레이아웃이 바뀌어도 그린 종목
    # 목록이 달라지므로 alt가 함께 달라집니다.
    #
    # alt는 언어와 무관하게 영어로 씁니다(워드프레스 미디어 설명). 다만 한국어판과
    # 영어판은 서로 다른 파일이므로 뒤에 언어를 붙여 alt가 겹치지 않게 합니다 —
    # 겹치면 영어 글에 한국어 그림이 재사용됩니다.
    market_label = "Korea Market Close" if market == "kr" else "U.S. Market Close"
    macro_values = ", ".join(
        f"{entry.get('name_en') or entry.get('name')} {entry['price']:,} ({_change(entry)})"
        for entry in _macro(price_data)
    )
    stock_values = ", ".join(
        f"{entry.get('name_en') or entry.get('name')} ({_change(entry)})"
        for entry in drawn if entry
    )
    alt = f"{market_label} data snapshot for {date_str}: {macro_values}"
    if stock_values:
        alt += f", biggest moves we track {stock_values}"
    return {
        "local_path": str(output_path),
        "alt": f"{alt} [{lang}].",
        "caption": "Market snapshot graphic generated from the figures in this article.",
        "layout": layout,
    }
