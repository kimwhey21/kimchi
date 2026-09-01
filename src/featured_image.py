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


def create(market: str, date_str: str, price_data: dict, output_path: Path) -> dict:
    """대표 이미지 파일을 만들고 publish_wordpress가 받는 메타데이터를 반환합니다."""
    canvas = Image.new("RGB", (1200, 630), "#F6F3ED")
    draw = ImageDraw.Draw(canvas)

    # 패널과 모든 글자는 안전 영역 안에만 둡니다 (모듈 상단 설명 참고).
    draw.rounded_rectangle((SAFE_LEFT, 44, SAFE_RIGHT, 586), radius=30, fill="#13283F")
    draw.text(
        (_CONTENT_LEFT, 82), "FERMATA  /  MARKET BRIEF", font=_font(24, True), fill="#8FC6E8"
    )
    date_font = _font(23)
    draw.text(
        (_CONTENT_RIGHT - draw.textlength(date_str, font=date_font), 82),
        date_str,
        font=date_font,
        fill="#D8E2EA",
    )

    market_label = "KOREA MARKET CLOSE" if market == "kr" else "U.S. MARKET CLOSE"
    draw.text((_CONTENT_LEFT, 142), market_label, font=_font(54, True), fill="#FFFFFF")
    draw.line((_CONTENT_LEFT, 222, _CONTENT_RIGHT, 222), fill="#36506A", width=2)

    macro = list(price_data.get("macro", {}).values())[:3]
    gap = 20
    card_width = (_CONTENT_RIGHT - _CONTENT_LEFT - gap * 2) // 3  # 266
    for index, entry in enumerate(macro):
        left = _CONTENT_LEFT + index * (card_width + gap)
        right = left + card_width
        draw.rounded_rectangle((left, 258, right, 438), radius=18, fill="#1C354E")
        draw.text((left + 24, 283), _short_name(entry), font=_font(22, True), fill="#C9D5DF")
        unit = " KRW" if entry.get("unit") == "원" else entry.get("unit", "")
        draw.text(
            (left + 24, 329),
            f"{entry['price']:,}{unit}",
            font=_font(33, True),
            fill="#FFFFFF",
        )
        change_color = "#F08A7A" if entry["change_pct"] >= 0 else "#82B6F2"
        draw.text((left + 24, 384), _change(entry), font=_font(27, True), fill=change_color)

    ranked = sorted(
        price_data.get("watchlist", {}).values(),
        key=lambda entry: abs(entry["change_pct"]),
        reverse=True,
    )
    if ranked:
        lead = ranked[0]
        draw.text(
            (_CONTENT_LEFT, 487),
            "LARGEST WATCHLIST MOVE",
            font=_font(18, True),
            fill="#8FC6E8",
        )
        draw.text(
            (_CONTENT_LEFT, 519),
            f"{_name(lead)[:30]}  {_change(lead)}",
            font=_font(28, True),
            fill="#FFFFFF",
        )
    snapshot_font = _font(18, True)
    draw.text(
        (_CONTENT_RIGHT - draw.textlength("MARKET SNAPSHOT", font=snapshot_font), 531),
        "MARKET SNAPSHOT",
        font=snapshot_font,
        fill="#8EA2B4",
    )

    output_path.parent.mkdir(exist_ok=True)
    canvas.save(output_path, format="PNG", optimize=True)
    alt_values = ", ".join(
        f"{_short_name(entry)} {entry['price']:,} ({_change(entry)})" for entry in macro
    )
    return {
        "local_path": str(output_path),
        "alt": f"{market_label.title()} data snapshot for {date_str}: {alt_values}.",
        "caption": "Market snapshot graphic generated from the figures in this article.",
    }
