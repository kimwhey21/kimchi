"""실제 시세로 1200×630 대표 이미지를 만들어 사진 검색 오류를 없앱니다.

**좌우 안전 영역(SAFE_LEFT~SAFE_RIGHT)을 반드시 지킬 것.**
워드프레스 테마의 대표 이미지 블록은 `aspect-ratio: 3/2` + `object-fit: cover`로
표시합니다(2026-09-01 실측: 컨테이너 720×480). 1200×630(1.90:1) 이미지를 1.5:1
컨테이너에 cover로 넣으면 높이에 맞춰 확대된 뒤 **좌우가 각각 약 127px씩 잘립니다.**
실제로 이 때문에 "FERMATA"가 "RMATA"로, "Ecopro"가 "opro"로 잘려 보였습니다.

1200×630은 소셜 공유(OG) 표준 비율이라 유지하고, 대신 글자와 카드를 가운데
946px 영역 안에만 배치해 어느 쪽에서 잘려도 내용이 살아남게 합니다.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


_FONT_REGULAR = (
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)
_FONT_BOLD = (
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)


# 그날 성격에 따라 카드 색을 바꿉니다.
#
# 왜: 이 카드는 매일 같은 레이아웃이라, 숫자만 바뀌면 목록에서 어제 글과
# 구분이 안 됩니다. 사진을 자동으로 붙이는 방법은 검수를 못 해 위험하므로
# (원화 검색에 위안화가 나온 사례), 대신 그날 대표 지수의 등락 폭으로
# 배경과 강조색을 바꿔 한눈에 구분되게 합니다. 색은 데이터에서 나오므로
# 잘못된 그림이 붙을 위험이 없습니다.
#
# 기준은 대표 지수(macro 첫 항목: 코스피 / 다우존스)의 등락률입니다.
_TONES = {
    "plunge": {  # -1.5% 이하
        "page": "#F3ECEA", "panel": "#3A1D22", "card": "#4E262C",
        "rule": "#6E3A42", "eyebrow": "#E8A79C", "muted": "#D9C4C0",
        "label": "SHARP DECLINE",
    },
    "down": {    # -1.5% ~ -0.3%
        "page": "#F2EFEC", "panel": "#2A2330", "card": "#3A3040",
        "rule": "#544862", "eyebrow": "#C0A8D4", "muted": "#CFC6D6",
        "label": "LOWER",
    },
    "flat": {    # -0.3% ~ +0.3%
        "page": "#F6F3ED", "panel": "#13283F", "card": "#1C354E",
        "rule": "#36506A", "eyebrow": "#8FC6E8", "muted": "#D8E2EA",
        "label": "LITTLE CHANGED",
    },
    "up": {      # +0.3% ~ +1.5%
        "page": "#EEF3EF", "panel": "#152F2A", "card": "#1E4038",
        "rule": "#325B50", "eyebrow": "#87C9AE", "muted": "#CFDFD8",
        "label": "HIGHER",
    },
    "surge": {   # +1.5% 이상
        "page": "#EDF2EC", "panel": "#12331F", "card": "#1B462B",
        "rule": "#2F6440", "eyebrow": "#8ED39B", "muted": "#CCE0CF",
        "label": "SHARP GAIN",
    },
}


def _tone(price_data: dict) -> dict:
    """대표 지수의 등락률로 색 조합을 고릅니다."""
    macro = list(price_data.get("macro", {}).values())
    if not macro:
        return _TONES["flat"]
    change = macro[0].get("change_pct")
    if change is None:
        return _TONES["flat"]
    if change <= -1.5:
        return _TONES["plunge"]
    if change <= -0.3:
        return _TONES["down"]
    if change < 0.3:
        return _TONES["flat"]
    if change < 1.5:
        return _TONES["up"]
    return _TONES["surge"]


# 3:2 중앙 크롭에서 살아남는 좌우 안전 영역 (1200×630 기준, 각 변 127px 잘림)
SAFE_LEFT = 140
SAFE_RIGHT = 1060
_PAD = 40                      # 패널 안쪽 여백
_CONTENT_LEFT = SAFE_LEFT + _PAD   # 180
_CONTENT_RIGHT = SAFE_RIGHT - _PAD  # 1020


def _font(size: int, bold: bool = False):
    for candidate in _FONT_BOLD if bold else _FONT_REGULAR:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default(size=size)


def _name(entry: dict) -> str:
    return entry.get("name_en") or entry.get("name") or entry.get("ticker", "Market")


def _short_name(entry: dict) -> str:
    aliases = {
        "Dow Jones Industrial Average": "DOW JONES",
        "Nasdaq Composite": "NASDAQ",
        "US 10-Year Treasury Yield": "U.S. 10Y YIELD",
        "US 30-Year Treasury Yield": "U.S. 30Y YIELD",
    }
    # 카드 폭이 안전 영역에 맞춰 좁아졌으므로 라벨도 함께 줄입니다.
    name = aliases.get(_name(entry), _name(entry))
    if len(name) <= 18:
        return name
    shortened = name[:18].rsplit(" ", 1)[0]
    return shortened or name[:18]


def _change(entry: dict) -> str:
    return f"{entry['change_pct']:+.2f}%"


def _is_renderable(entry: dict) -> bool:
    """이 이미지의 폰트로 이름이 그려지는지 — 즉 영문 표기가 있는지 봅니다.

    대표 이미지는 영어로만 짜여 있습니다(제목 "KOREA MARKET CLOSE", 라벨 KOSPI,
    Helvetica 계열 폰트). 그래서 한글 이름을 그리면 글자가 아니라 두부 상자
    (□□□□)가 찍힙니다. 실제로 name_en이 없는 편입 종목을 대문에 걸었다가
    "□□□□□ +8.58%"가 나온 것을 스크린샷으로 확인하고 이 검사를 넣었습니다.

    코어 종목은 config에 name_en이 모두 있고, 그날 편입 종목은 name_en_map에
    있을 때만 통과합니다.
    """
    name = _name(entry)
    return bool(name) and all(ord(char) < 0x2E80 for char in name)


def lead_watchlist_entry(price_data: dict) -> dict | None:
    """대문에 이름을 걸 종목 — 그날 절대 등락 폭이 가장 큰 워치리스트 종목입니다.

    그날 거래대금으로 자동 편입된 종목(source="dynamic")도 후보에 넣습니다.
    한 번 코어만 고르게 해봤다가 되돌렸습니다. 이미지에 걸리는 라벨이
    "LARGEST WATCHLIST MOVE"인데, 워치리스트에 삼성중공업(+8.58%)이 들어 있는
    상태에서 KB금융(+5.20%)을 걸면 라벨이 사실과 어긋나기 때문입니다.

    사진(publish_editorial._concrete_image_query)과 달리 여기서는 편입 종목을
    막을 이유가 없습니다. 대표 이미지는 데이터에서 텍스트를 그리는 것이라
    "엉뚱한 그림이 붙는" 위험 자체가 없습니다. 다만 영문 표기가 없는 종목은
    글자가 깨지므로 건너뛰고 다음 순위를 봅니다.
    """
    ranked = sorted(
        price_data.get("watchlist", {}).values(),
        key=lambda entry: abs(entry["change_pct"]),
        reverse=True,
    )
    return next((entry for entry in ranked if _is_renderable(entry)), None)


def create(market: str, date_str: str, price_data: dict, output_path: Path) -> dict:
    """대표 이미지 파일을 만들고 publish_wordpress가 받는 메타데이터를 반환합니다."""
    tone = _tone(price_data)
    canvas = Image.new("RGB", (1200, 630), tone["page"])
    draw = ImageDraw.Draw(canvas)

    # 패널과 모든 글자는 안전 영역 안에만 둡니다 (모듈 상단 설명 참고).
    draw.rounded_rectangle((SAFE_LEFT, 44, SAFE_RIGHT, 586), radius=30, fill=tone["panel"])
    draw.text(
        (_CONTENT_LEFT, 82),
        "FERMATA  /  MARKET BRIEF",
        font=_font(24, True),
        fill=tone["eyebrow"],
    )
    date_font = _font(23)
    draw.text(
        (_CONTENT_RIGHT - draw.textlength(date_str, font=date_font), 82),
        date_str,
        font=date_font,
        fill=tone["muted"],
    )

    market_label = "KOREA MARKET CLOSE" if market == "kr" else "U.S. MARKET CLOSE"
    draw.text((_CONTENT_LEFT, 142), market_label, font=_font(54, True), fill="#FFFFFF")
    draw.line((_CONTENT_LEFT, 222, _CONTENT_RIGHT, 222), fill=tone["rule"], width=2)

    macro = list(price_data.get("macro", {}).values())[:3]
    gap = 20
    card_width = (_CONTENT_RIGHT - _CONTENT_LEFT - gap * 2) // 3  # 266
    for index, entry in enumerate(macro):
        left = _CONTENT_LEFT + index * (card_width + gap)
        right = left + card_width
        draw.rounded_rectangle((left, 258, right, 438), radius=18, fill=tone["card"])
        draw.text(
            (left + 24, 283), _short_name(entry), font=_font(22, True), fill=tone["muted"]
        )
        unit = " KRW" if entry.get("unit") == "원" else entry.get("unit", "")
        draw.text(
            (left + 24, 329),
            f"{entry['price']:,}{unit}",
            font=_font(33, True),
            fill="#FFFFFF",
        )
        change_color = "#F08A7A" if entry["change_pct"] >= 0 else "#82B6F2"
        draw.text((left + 24, 384), _change(entry), font=_font(27, True), fill=change_color)

    lead = lead_watchlist_entry(price_data)
    if lead:
        draw.text(
            (_CONTENT_LEFT, 487),
            "LARGEST WATCHLIST MOVE",
            font=_font(18, True),
            fill=tone["eyebrow"],
        )
        draw.text(
            (_CONTENT_LEFT, 519),
            f"{_name(lead)[:30]}  {_change(lead)}",
            font=_font(28, True),
            fill="#FFFFFF",
        )
    # 오른쪽 아래 라벨도 그날 성격을 말해 줍니다("SHARP DECLINE" 등).
    snapshot_font = _font(18, True)
    snapshot_label = tone["label"]
    draw.text(
        (_CONTENT_RIGHT - draw.textlength(snapshot_label, font=snapshot_font), 531),
        snapshot_label,
        font=snapshot_font,
        fill=tone["eyebrow"],
    )

    output_path.parent.mkdir(exist_ok=True)
    canvas.save(output_path, format="PNG", optimize=True)
    alt_values = ", ".join(
        f"{_short_name(entry)} {entry['price']:,} ({_change(entry)})" for entry in macro
    )
    # 그림에 그린 LARGEST WATCHLIST MOVE도 alt에 넣습니다.
    #
    # 설명글로서 맞기도 하지만, publish_wordpress._featured_media_matches가 이
    # alt로 "같은 데이터로 만든 이미지인지"를 판단하기 때문이기도 합니다.
    # 지수 값만 넣었더니 2026-09-03에 이런 일이 있었습니다 — 워치리스트가
    # 넓어져 대문 종목이 알테오젠에서 삼성중공업으로 바뀌었는데, 지수 숫자가
    # 같아 alt가 동일했고, 기존 미디어를 재사용하는 바람에 제목은 삼성중공업
    # 8.58%인데 대표 이미지는 "Alteogen -5.19%"인 글이 공개됐습니다.
    if lead:
        alt_values += f", largest watchlist move {_name(lead)} ({_change(lead)})"
    return {
        "local_path": str(output_path),
        "alt": f"{market_label.title()} data snapshot for {date_str}: {alt_values}.",
        "caption": "Market snapshot graphic generated from the figures in this article.",
    }
