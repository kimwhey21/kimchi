"""Build an English Korea-market draft without a paid generative-AI API."""
from __future__ import annotations

import re

from src.generate_free import _select_diverse_headlines

_HANGUL_RE = re.compile(r"[가-힣]")


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
        if entry.get("quote_type") == "reference_rate":
            reference = entry.get("reference_label_en") or entry.get(
                "as_of_label_en", "time unavailable"
            )
            sentences.append(
                f"The {_name(entry)} reference rate was {entry['price']:,}{_unit(entry)}, "
                f"{_change_phrase(entry['change_pct'])} from the previous Hana Bank notice "
                f"(as of {reference})."
            )
            continue
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
        return "No price data was available for the stocks we follow."
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
        "The table above lists the largest net purchases and sales with foreign ownership ratios."
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


def _english_ready(price_data: dict) -> dict:
    """Drop watchlist entries whose English name is still Korean.

    2026-09-04 한국장이 이것 때문에 통째로 실패했다. 그날 거래대금 상위로 편입된
    로보티즈·원익홀딩스가 `name_en_map`에 없어 name_en에 한글이 그대로 들어왔고,
    영어 초안 제목과 본문에 한글이 섞이면서 editorial_quality_en이 예외를 냈다.
    그 예외로 프로세스가 죽는 바람에 이미 정상적으로 받아 둔 시세 파일까지
    커밋되지 못했고, 루틴이 읽을 데이터가 없어 그날 글이 나가지 않았다.

    영어판에서 종목 하나가 빠지는 것과 그날 발행 전체가 멈추는 것 중에는
    전자가 낫다. 한국어판은 그대로 그 종목을 쓴다 — 여기서만 걸러낸다.
    (AGENTS.md: "이름도 모르는 종목 하나가 그날 발행 전체를 멈추게 하면 안 된다")
    """
    watchlist = {}
    for ticker, entry in (price_data.get("watchlist") or {}).items():
        name_en = str(entry.get("name_en") or "")
        if _HANGUL_RE.search(name_en):
            print(
                f"[안내] 영어판에서 제외 — {entry.get('name')}({ticker})의 영어 표기가 "
                "없습니다. config/watchlist_kr.yaml의 name_en_map에 추가하면 다음부터 "
                "영어판에도 나옵니다."
            )
            continue
        watchlist[ticker] = entry
    return {**price_data, "watchlist": watchlist}


def generate(
    date_str: str, price_data: dict, recent_news: list[dict] | None = None
) -> dict:
    """Create English copy directly from the same facts as the Korean edition."""
    price_data = _english_ready(price_data)
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
        # "watchlist" is our own plumbing — the reader has never seen that list.
        {"heading": "Breadth across the stocks we follow",
         "body": _watchlist_summary(price_data)},
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
