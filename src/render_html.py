"""가격 데이터(fetch_*.py) + 생성된 문구(generate_post.py)를 합쳐
최종 HTML 결과물을 만듭니다.

카드에 들어가는 가격·등락률 숫자는 항상 fetch 단계의 실제
데이터에서만 가져옵니다. generate_post.py가 돌려준 featured_tickers는
"어떤 종목을 보여줄지"만 고르고, 숫자 자체는 여기서 원본 데이터를 다시
조회해서 채웁니다.

insight_section의 icon/chart/table은 저작권 문제가 없도록 외부 이미지를 쓰지 않고,
아래 ICONS에 정의된 원본 SVG 아이콘과 Chart.js로만 구성합니다.
"""
from __future__ import annotations

import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

# 저작권 걱정 없는 원본 라인 아이콘. 32x32 뷰박스, currentColor 사용.
ICONS: dict[str, str] = {
    "server": (
        '<rect x="6" y="6" width="20" height="7" rx="1.5"/>'
        '<rect x="6" y="19" width="20" height="7" rx="1.5"/>'
        '<circle cx="10" cy="9.5" r="1"/><circle cx="10" cy="22.5" r="1"/>'
    ),
    "robot": (
        '<rect x="9" y="12" width="14" height="12" rx="2"/>'
        '<circle cx="13" cy="17" r="1.4"/><circle cx="19" cy="17" r="1.4"/>'
        '<line x1="16" y1="12" x2="16" y2="7"/><circle cx="16" cy="6" r="1.4"/>'
        '<line x1="9" y1="18" x2="5" y2="18"/><line x1="23" y1="18" x2="27" y2="18"/>'
    ),
    "coin": (
        '<circle cx="16" cy="16" r="10"/>'
        '<line x1="16" y1="10" x2="16" y2="22"/>'
        '<line x1="12" y1="13" x2="20" y2="13"/><line x1="12" y1="19" x2="20" y2="19"/>'
    ),
    "gold": (
        '<polygon points="8,20 11,12 21,12 24,20"/>'
        '<line x1="8" y1="20" x2="24" y2="20"/>'
    ),
    "scale": (
        '<line x1="16" y1="6" x2="16" y2="24"/><line x1="8" y1="10" x2="24" y2="10"/>'
        '<path d="M8 10 L5 17 A4 4 0 0 0 11 17 Z"/>'
        '<path d="M24 10 L21 17 A4 4 0 0 0 27 17 Z"/>'
        '<line x1="12" y1="26" x2="20" y2="26"/>'
    ),
    "chip": (
        '<rect x="10" y="10" width="12" height="12" rx="1"/>'
        '<line x1="13" y1="6" x2="13" y2="10"/><line x1="19" y1="6" x2="19" y2="10"/>'
        '<line x1="13" y1="22" x2="13" y2="26"/><line x1="19" y1="22" x2="19" y2="26"/>'
        '<line x1="6" y1="13" x2="10" y2="13"/><line x1="6" y1="19" x2="10" y2="19"/>'
        '<line x1="22" y1="13" x2="26" y2="13"/><line x1="22" y1="19" x2="26" y2="19"/>'
    ),
    "battery": (
        '<rect x="6" y="11" width="18" height="10" rx="1.5"/>'
        '<rect x="24" y="14" width="2.5" height="4" rx="0.5"/>'
        '<line x1="10" y1="14" x2="10" y2="18"/><line x1="14" y1="14" x2="14" y2="18"/>'
    ),
    "shield": (
        '<path d="M16 5 L25 9 V16 C25 22 20 26 16 27 C12 26 7 22 7 16 V9 Z"/>'
    ),
}
DEFAULT_ICON = "chip"


def _display_name(entry: dict, lang: str) -> str:
    return entry.get("name_en") or entry["name"] if lang == "en" else entry["name"]


def _to_card(entry: dict, lang: str = "ko", reference_date: str | None = None) -> dict:
    direction = "up" if entry["change_pct"] >= 0 else "down"
    sign = "+" if entry["change_pct"] >= 0 else ""
    unit = entry.get("unit", "")
    if lang == "en" and unit == "원":
        unit = " KRW"
    return {
        "name": _display_name(entry, lang),
        "ticker": entry.get("ticker", ""),
        "price": f'{entry["price"]:,}{unit}',
        "change_pct": entry["change_pct"],
        "change_label": f'{sign}{entry["change_pct"]}%',
        "direction": direction,
        "as_of": entry.get("as_of_label_en" if lang == "en" else "as_of_label") or (
            (f"As of {entry['trading_date']}" if lang == "en" else f"{entry['trading_date']} 기준")
            if reference_date
            and entry.get("trading_date")
            and entry["trading_date"] != reference_date
            else ""
        ),
    }


def _to_theme_card(label: str, ticker: str, price_data: dict, lang: str = "ko") -> dict | None:
    entry = price_data["watchlist"].get(ticker) or price_data["macro"].get(ticker)
    if entry is None:
        print(
            f"[경고] theme_section: '{ticker}'는 가격 데이터에 없는 ticker라 카드에서 "
            f"빠졌습니다 (label: {label!r}). 본문에는 언급됐을 수 있으니 확인하세요.",
            file=sys.stderr,
        )
        return None
    base = _to_card(entry, lang)
    return {**base, "label": label, "sub_label": _display_name(entry, lang)}


def _build_foreign_flow_table(price_data: dict, lang: str) -> list[dict] | None:
    """해외 개인투자자를 위한 "오늘의 외국인 순매매 동향" 표를 만듭니다.

    fetch_kr.py가 watchlist 종목마다 붙여준 foreign_net(외국인 순매매량,
    양수=순매수)을 그대로 가져와 정렬만 합니다 — 숫자는 Claude가 만들지
    않고 여기서 그대로 옮기기만 합니다 (다른 카드들과 동일한 원칙).
    """
    rows = [
        {
            "name": _display_name(entry, lang),
            "ticker": ticker,
            "foreign_net": entry["foreign_net"],
            "foreign_ratio": entry.get("foreign_ratio"),
            "direction": "up" if entry["foreign_net"] >= 0 else "down",
        }
        for ticker, entry in price_data.get("watchlist", {}).items()
        if "foreign_net" in entry
    ]
    if not rows:
        return None
    rows.sort(key=lambda r: r["foreign_net"], reverse=True)
    return rows


def _prep_insight_section(insight_section: dict | None, lang: str = "ko") -> dict | None:
    if not insight_section:
        return None
    suffix = "×" if lang == "en" else "배"
    stories = []
    for story in insight_section.get("stories", []):
        icon_key = story.get("icon") if story.get("icon") in ICONS else DEFAULT_ICON
        story = {**story, "icon_svg": ICONS[icon_key]}
        chart = story.get("chart")
        if chart and chart.get("type") == "stat" and chart.get("data"):
            data = chart["data"]
            multiples = []
            for a, b in zip(data, data[1:]):
                m = round(b / a, 1) if a else None
                multiples.append(f"{suffix}{m}" if (m and lang == "en") else f"{m}{suffix}" if m else "")
            story["chart"] = {**chart, "multiples": multiples}
        stories.append(story)
    return {**insight_section, "stories": stories}


def render(
    market: str,
    date_str: str,
    price_data: dict,
    generated: dict,
    lang: str = "ko",
    market_label: str | None = None,
    subscribe_form_action: str | None = None,
) -> str:
    macro_cards = [_to_card(v, lang, date_str) for v in price_data["macro"].values()]

    first_body = (generated.get("narrative") or [{}])[0].get("body", "")
    meta_description = first_body.split("\n\n")[0][:155].strip()

    theme_section = generated.get("theme_section") or {}
    theme_cards = [
        card for card in (
            _to_theme_card(h["label"], h["ticker"], price_data, lang)
            for h in theme_section.get("highlights", [])
        )
        if card is not None
    ]

    stock_section = generated.get("stock_section") or {}
    featured_tickers = stock_section.get("featured_tickers", [])
    for t in featured_tickers:
        if t not in price_data["watchlist"]:
            print(
                f"[경고] stock_section: '{t}'는 가격 데이터에 없는 ticker라 카드에서 "
                f"빠졌습니다. 본문에는 언급됐을 수 있으니 확인하세요.",
                file=sys.stderr,
            )
    stock_cards = [
        _to_card({**price_data["watchlist"][t], "ticker": t}, lang)
        for t in featured_tickers
        if t in price_data["watchlist"]
    ]

    foreign_flow_rows = _build_foreign_flow_table(price_data, lang) if market == "kr" else None

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
    template = env.get_template("post.html.j2")

    return template.render(
        lang=lang,
        market_label=market_label or ("미국장" if market == "us" else "한국장"),
        date_str=date_str,
        title=generated["title"],
        narrative=generated["narrative"],
        macro_cards=macro_cards,
        theme_heading=theme_section.get("heading", "업종·테마"),
        theme_commentary=theme_section.get("commentary", ""),
        theme_cards=theme_cards,
        stock_heading=stock_section.get("heading", "주요 종목"),
        stock_commentary=stock_section.get("commentary", ""),
        stock_cards=stock_cards,
        outlook=generated.get("outlook"),
        closing=generated.get("closing"),
        source_notes=generated.get("sources", []),
        insight_section=_prep_insight_section(generated.get("insight_section"), lang),
        calendar=generated.get("calendar", []),
        foreign_flow_rows=foreign_flow_rows,
        meta_description=meta_description,
        subscribe_form_action=subscribe_form_action,
    )
