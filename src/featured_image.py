"""실제 시세로 1200×630 대표 이미지를 만들어 사진 검색 오류를 없앱니다."""
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
    name = aliases.get(_name(entry), _name(entry))
    if len(name) <= 22:
        return name
    shortened = name[:22].rsplit(" ", 1)[0]
    return shortened or name[:22]


def _change(entry: dict) -> str:
    return f"{entry['change_pct']:+.2f}%"


def create(market: str, date_str: str, price_data: dict, output_path: Path) -> dict:
    """대표 이미지 파일을 만들고 publish_wordpress가 받는 메타데이터를 반환합니다."""
    canvas = Image.new("RGB", (1200, 630), "#F6F3ED")
    draw = ImageDraw.Draw(canvas)

    # 상단 브랜드 띠
    draw.rounded_rectangle((52, 44, 1148, 586), radius=30, fill="#13283F")
    draw.text((92, 82), "FERMATA  /  MARKET BRIEF", font=_font(24, True), fill="#8FC6E8")
    draw.text((920, 82), date_str, font=_font(23), fill="#D8E2EA")

    market_label = "KOREA MARKET CLOSE" if market == "kr" else "U.S. MARKET CLOSE"
    draw.text((92, 142), market_label, font=_font(54, True), fill="#FFFFFF")
    draw.line((92, 222, 1108, 222), fill="#36506A", width=2)

    macro = list(price_data.get("macro", {}).values())[:3]
    card_width = 316
    for index, entry in enumerate(macro):
        left = 92 + index * 336
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
        draw.text((92, 487), "LARGEST WATCHLIST MOVE", font=_font(18, True), fill="#8FC6E8")
        draw.text(
            (92, 519),
            f"{_name(lead)[:34]}  {_change(lead)}",
            font=_font(28, True),
            fill="#FFFFFF",
        )
    draw.text((906, 531), "CLOSING DATA", font=_font(18, True), fill="#8EA2B4")

    output_path.parent.mkdir(exist_ok=True)
    canvas.save(output_path, format="PNG", optimize=True)
    return {
        "local_path": str(output_path),
        "alt": f"{market_label.title()} data snapshot for {date_str}",
        "caption": "Market-close data graphic generated from the figures in this article.",
    }
