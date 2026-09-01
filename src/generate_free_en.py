"""Build an English Korea-market draft without a paid generative-AI API."""
from __future__ import annotations

from src.generate_free import _select_diverse_headlines


_SOURCE_NAMES = {
    "한국경제": "The Korea Economic Daily",
    "연합뉴스": "Yonhap News Agency",
    "이데일리": "Edaily",
}


def _name(entry: dict) -> str:
    return entry.get("name_en") or entry.get("name", entry.get("ticker", "Market"))


def _change_phrase(change: float) -> str:
    if change > 0:
        return f"up {change:.2f}%"
    if change < 0:
        return f"down {abs(change):.2f}%"
    return "unchanged"


def _unit(entry: dict) -> str:
    unit = entry.get("unit", "")
    if unit == "원":
        return " KRW"
    return f" {unit}" if unit else ""


def _title_phrase(entry: dict) -> str:
    change = entry["change_pct"]
    if change > 0:
        return f"{_name(entry)} gains {change:.2f}%"
    if change < 0:
        return f"{_name(entry)} falls {abs(change):.2f}%"
    return f"{_name(entry)} ends flat"


def _macro_summary(price_data: dict, date_str: str) -> str:
    entries = list(price_data.get("macro", {}).values())
    if not entries:
        return "No index or exchange-rate data was available."
    sentences = []
    for entry in entries:
        as_of = entry.get("trading_date")
        note = f" (as of {as_of})" if as_of and as_of != date_str else ""
        sentences.append(
            f"{_name(entry)} closed at {entry['price']:,}{_unit(entry)}, "
            f"{_change_phrase(entry['change_pct'])}{note}."
        )
    return " ".join(sentences)


def _watchlist_summary(price_data: dict) -> str:
    entries = list(price_data.get("watchlist", {}).values())
    if not entries:
        return "No watchlist data was available."
    up = sum(entry["change_pct"] > 0 for entry in entries)
    down = sum(entry["change_pct"] < 0 for entry in entries)
    flat = len(entries) - up - down
    ranked = sorted(entries, key=lambda entry: abs(entry["change_pct"]), reverse=True)[:3]
    leaders = ", ".join(
        f"{_name(entry)} {entry['change_pct']:+.2f}%" for entry in ranked
    )
    breadth = f"Among {len(entries)} tracked stocks, {up} rose and {down} fell"
    if flat:
        breadth += f", while {flat} finished unchanged"
    return f"{breadth}. The three largest absolute moves were {leaders}."


def _recent_trend_summary(price_data: dict) -> str | None:
    parts = []
    for entry in price_data.get("macro", {}).values():
        series = entry.get("series") or []
        if len(series) < 6 or not series[-6]:
            continue
        change = (series[-1] / series[-6] - 1) * 100
        parts.append(f"{_name(entry)} {change:+.2f}%")
    if not parts:
        return None
    return (
        "Across the latest five-session interval, " + ", ".join(parts) + ". "
        "This comparison puts the latest one-day move in the context of recent closes."
    )


def _foreign_flow_summary(price_data: dict) -> str | None:
    entries = [
        entry
        for entry in price_data.get("watchlist", {}).values()
        if entry.get("foreign_net") is not None
    ]
    if not entries:
        return None
    bought = sum(entry["foreign_net"] > 0 for entry in entries)
    sold = sum(entry["foreign_net"] < 0 for entry in entries)
    top_buy = max(entries, key=lambda entry: entry["foreign_net"])
    top_sell = min(entries, key=lambda entry: entry["foreign_net"])
    return (
        f"Foreign investors were net buyers in {bought} tracked stocks and net sellers in {sold}. "
        f"The largest net purchase was {_name(top_buy)} at {top_buy['foreign_net']:+,} shares; "
        f"the largest net sale was {_name(top_sell)} at {top_sell['foreign_net']:+,} shares. "
        "The table above includes the full watchlist and foreign ownership ratios."
    )


def _source_notes(recent_news: list[dict] | None) -> list[dict]:
    selected = _select_diverse_headlines(recent_news or [], market="kr")
    return [
        {
            "name": _SOURCE_NAMES.get(item.get("source", ""), item.get("source", "Source")),
            "title": f"[Korean] {item.get('title', '')}",
            "url": item.get("link", ""),
        }
        for item in selected
        if item.get("link")
    ]


def generate(
    date_str: str, price_data: dict, recent_news: list[dict] | None = None
) -> dict:
    """Create English copy directly from the same facts as the Korean edition."""
    watchlist = list(price_data.get("watchlist", {}).values())
    ranked = sorted(watchlist, key=lambda entry: abs(entry["change_pct"]), reverse=True)
    positive = sorted(
        (entry for entry in watchlist if entry["change_pct"] > 0),
        key=lambda entry: entry["change_pct"],
        reverse=True,
    )
    negative = sorted(
        (entry for entry in watchlist if entry["change_pct"] < 0),
        key=lambda entry: entry["change_pct"],
    )
    lead_macro = next(iter(price_data.get("macro", {}).values()), None)
    title_parts = [_title_phrase(lead_macro)] if lead_macro else []
    if ranked:
        title_parts.append(_title_phrase(ranked[0]))
    title = "; ".join(title_parts) or f"Korea market close for {date_str}"

    highlights = []
    if positive:
        highlights.append({"label": "Largest gain", "ticker": positive[0]["ticker"]})
    if negative:
        highlights.append({"label": "Largest decline", "ticker": negative[0]["ticker"]})

    sources = _source_notes(recent_news)
    narrative = [
        {"heading": "Indexes and exchange rate", "body": _macro_summary(price_data, date_str)},
        {"heading": "Breadth across the watchlist", "body": _watchlist_summary(price_data)},
    ]
    recent_trend = _recent_trend_summary(price_data)
    if recent_trend:
        narrative.append({"heading": "Five-session context", "body": recent_trend})
    foreign_flow = _foreign_flow_summary(price_data)
    if foreign_flow:
        narrative.append({"heading": "Foreign investor flows", "body": foreign_flow})
    if sources:
        source_count = len({source["name"] for source in sources})
        narrative.append(
            {
                "heading": "News links for further reading",
                "body": (
                    f"The source list contains {len(sources)} market-related RSS headlines from "
                    f"{source_count} Korean publishers, selected in rotation to reduce concentration. "
                    "The headlines are not treated as verified explanations for the market move."
                ),
            }
        )

    return {
        "title": title,
        "narrative": narrative,
        "theme_section": {
            "heading": "Largest moves",
            "commentary": "Gainers and decliners are ranked from the collected closing-price data.",
            "highlights": highlights,
        },
        "stock_section": {
            "heading": "Stocks in focus",
            "commentary": "Cards are ordered by the size of the daily move, regardless of direction.",
            "featured_tickers": [entry["ticker"] for entry in ranked[:6]],
        },
        "outlook": {
            "heading": "What to watch next",
            "body": (
                "The next session will show whether the index direction, USD/KRW move and foreign "
                "investor flows persist. A single-day move should be checked against trading volume "
                "and subsequent company disclosures before drawing a broader conclusion."
            ),
        },
        "closing": {
            "heading": "Method and limitations",
            "body": (
                "This brief separates closing-price facts from unverified news headlines. It does not "
                "assign a cause to the market move unless that explanation has been checked in a source."
            ),
        },
        "insight_section": None,
        "calendar": [],
        "sources": sources,
    }
