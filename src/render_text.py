"""가격 데이터 + 생성된 문구를 블로그에 바로 복사·붙여넣기 좋은
일반 텍스트로 변환합니다. (render_html.py의 텍스트 버전)
"""
from __future__ import annotations


def _fmt_price(entry: dict, lang: str = "ko") -> str:
    unit = entry.get("unit", "")
    if lang == "en" and unit == "원":
        unit = " KRW"
    sign = "+" if entry["change_pct"] >= 0 else ""
    name = (entry.get("name_en") or entry["name"]) if lang == "en" else entry["name"]
    return f'{name} {entry["price"]:,}{unit} ({sign}{entry["change_pct"]}%)'


def _fmt_section(heading: str, body: str) -> str:
    return f"■ {heading}\n\n{body}"


def render(
    market: str, date_str: str, price_data: dict, generated: dict, lang: str = "ko"
) -> str:
    market_label = (
        ("US Market Close" if market == "us" else "Korea Market Close")
        if lang == "en"
        else ("미국장" if market == "us" else "한국장")
    )
    lines: list[str] = []

    lines.append(generated["title"])
    lines.append(
        f"{date_str} {market_label}" if lang == "en" else f"{date_str} {market_label} 마감 시황"
    )
    lines.append("")

    macro_line = " / ".join(_fmt_price(v, lang) for v in price_data["macro"].values())
    if macro_line:
        lines.append(macro_line)
        lines.append("")

    for section in generated.get("narrative", []):
        lines.append(_fmt_section(section["heading"], section["body"]))
        lines.append("")

    theme_section = generated.get("theme_section") or {}
    if theme_section:
        lines.append(f"■ {theme_section.get('heading', '업종·테마')}")
        lines.append("")
        for h in theme_section.get("highlights", []):
            entry = price_data["watchlist"].get(h["ticker"]) or price_data["macro"].get(h["ticker"])
            if entry:
                lines.append(f"- {h['label']}: {_fmt_price(entry, lang)}")
        if theme_section.get("commentary"):
            lines.append("")
            lines.append(theme_section["commentary"])
        lines.append("")

    stock_section = generated.get("stock_section") or {}
    if stock_section:
        lines.append(f"■ {stock_section.get('heading', '주요 종목')}")
        lines.append("")
        for t in stock_section.get("featured_tickers", []):
            entry = price_data["watchlist"].get(t)
            if entry:
                lines.append(f"- {_fmt_price(entry, lang)}")
        if stock_section.get("commentary"):
            lines.append("")
            lines.append(stock_section["commentary"])
        lines.append("")

    outlook = generated.get("outlook")
    if outlook:
        lines.append(_fmt_section(outlook["heading"], outlook["body"]))
        lines.append("")

    closing = generated.get("closing")
    if closing:
        lines.append(_fmt_section(closing["heading"], closing["body"]))
        lines.append("")

    sources = generated.get("sources") or []
    if sources:
        lines.append("■ Sources" if lang == "en" else "■ 자료 확인")
        for source in sources:
            lines.append(f"- {source.get('name', '')}: {source.get('title', '')}")
            if source.get("url"):
                lines.append(f"  {source['url']}")
        lines.append("")

    insight_section = generated.get("insight_section")
    if insight_section and insight_section.get("stories"):
        lines.append(f"■ {insight_section.get('heading', '인사이트')}")
        lines.append("")
        for story in insight_section["stories"]:
            lines.append(f"[{story['heading']}]")
            lines.append("")
            lines.append(story["body"])
            chart = story.get("chart")
            if chart and chart.get("labels") and chart.get("data"):
                unit = chart.get("unit", "")
                pairs = ", ".join(
                    f"{label} {value}{unit}"
                    for label, value in zip(chart["labels"], chart["data"])
                )
                lines.append(f"({chart.get('title', '')}: {pairs})")
            for row in story.get("table") or []:
                lines.append(f"- {row['label']}: {row['value']}")
            lines.append("")

    calendar = generated.get("calendar") or []
    if calendar:
        lines.append("■ 주요 일정")
        lines.append("")
        for item in calendar:
            lines.append(f"- {item['date']} {item['title']}: {item['desc']}")
        lines.append("")

    lines.append(
        "For informational purposes only. Not investment advice."
        if lang == "en"
        else "투자 참고용이며 투자 권유가 아닙니다."
    )

    return "\n".join(lines).strip() + "\n"
