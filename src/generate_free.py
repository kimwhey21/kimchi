"""실제 시세와 RSS만으로 외부 AI API 비용 없는 시황 초안을 만듭니다."""
from __future__ import annotations

import re

_NEWS_PRIMARY_TERMS = {
    "kr": (
        "증시", "주식시장", "주가", "코스피", "코스닥", "환율", "원/달러",
        "달러/원", "원·달러", "원달러", "금리", "채권", "국고채", "외국인",
        "순매수", "순매도", "수급", "장초반", "장중", "마감", "거래대금",
        "거래량", "상한가", "하한가", "상폐", "빚투", "신용융자", "공매도",
    ),
    "us": (
        "stock", "market", "nasdaq", "dow", "s&p", "treasury", "yield", "dollar",
        "fed", "rate", "inflation", "jobs", "earnings", "shares", "investor", "oil",
        "gold", "bitcoin", "tariff", "trade", "chip", "ai",
    ),
}

_NEWS_SECONDARY_TERMS = {
    "kr": (
        "반도체", "2차전지", "바이오", "실적", "순익", "영업이익", "매출",
        "배당", "자사주", "공시", "상장", "펀드", "etf", "ipo", "관세",
        "수출", "투자자",
    ),
    "us": (),
}


def _headline_term_count(title: str, terms: tuple[str, ...]) -> int:
    """영문 짧은 검색어가 다른 단어 안에서 우연히 잡히는 일을 막습니다.

    예를 들어 ``ai``가 ``chairman``에, ``rate``가 ``separate``에 포함됐다는
    이유만으로 미국장 기사로 분류하면 안 됩니다. 한글·기호 포함 검색어는
    일반 부분 문자열로, 영문·숫자 검색어는 단어 경계로 비교합니다.
    """
    count = 0
    for term in terms:
        if term.isascii() and term.isalnum():
            matched = re.search(
                rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", title
            )
        else:
            matched = term in title
        count += bool(matched)
    return count


def _change_sentence(entry: dict) -> str:
    change = entry["change_pct"]
    if change > 0:
        movement = f"전일 대비 {change:.2f}% 상승했습니다"
    elif change < 0:
        movement = f"전일 대비 {abs(change):.2f}% 하락했습니다"
    else:
        movement = "전일과 같은 수준이었습니다"
    return f"{entry['name']}: {entry['price']:,}{entry.get('unit', '')}, {movement}"


def _title_change(entry: dict) -> str:
    change = entry["change_pct"]
    if change > 0:
        return f"{entry['name']} {change:.2f}% 상승"
    if change < 0:
        return f"{entry['name']} {abs(change):.2f}% 하락"
    return f"{entry['name']} 보합"


def _ranked_entries(price_data: dict) -> list[dict]:
    return sorted(
        price_data.get("watchlist", {}).values(),
        key=lambda entry: abs(entry["change_pct"]),
        reverse=True,
    )


def _market_summary(price_data: dict, date_str: str) -> str:
    macro = list(price_data.get("macro", {}).values())
    if not macro:
        return "주요 지수 데이터가 확인되지 않았습니다."
    parts = []
    for entry in macro:
        as_of = entry.get("trading_date")
        note = f" ({as_of} 기준)" if as_of and as_of != date_str else ""
        parts.append(f"{_change_sentence(entry)}{note}.")
    return " ".join(parts)


def _watchlist_summary(price_data: dict) -> str:
    entries = list(price_data.get("watchlist", {}).values())
    if not entries:
        return "관심 종목 데이터가 확인되지 않았습니다."
    up = sum(entry["change_pct"] > 0 for entry in entries)
    down = sum(entry["change_pct"] < 0 for entry in entries)
    flat = len(entries) - up - down
    ranked = sorted(entries, key=lambda entry: abs(entry["change_pct"]), reverse=True)[:3]
    breadth = f"관심 종목 {len(entries)}개 중 {up}개가 상승하고 {down}개가 하락했습니다"
    if flat:
        breadth += f". 보합은 {flat}개였습니다"
    moves = ", ".join(
        f"{entry['name']} {entry['change_pct']:+.2f}%" for entry in ranked
    )
    return f"{breadth}. 절대 등락 폭이 큰 종목은 {moves} 순이었습니다."


def _recent_trend_summary(price_data: dict) -> str | None:
    parts = []
    for entry in price_data.get("macro", {}).values():
        series = entry.get("series") or []
        if len(series) < 6 or not series[-6]:
            continue
        change = (series[-1] / series[-6] - 1) * 100
        parts.append(f"{entry['name']} {change:+.2f}%")
    if not parts:
        return None
    return (
        "최근 5거래일 종가를 비교하면 " + ", ".join(parts) + "였습니다. "
        "하루 등락률과 함께 보면 당일 움직임이 최근 구간에서 차지하는 크기를 확인할 수 있습니다."
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
        f"관심 종목 중 외국인 순매수는 {bought}개, 순매도는 {sold}개였습니다. "
        f"순매수 상위는 {top_buy['name']} {top_buy['foreign_net']:+,}주, "
        f"순매도 상위는 {top_sell['name']} {top_sell['foreign_net']:+,}주였습니다. "
        "본문 앞의 표에서 종목별 순매매량과 외국인 보유율을 함께 확인할 수 있습니다."
    )


def _select_diverse_headlines(
    recent_news: list[dict], limit: int = 6, market: str | None = None
) -> list[dict]:
    """시장 관련성을 먼저 본 뒤 매체별로 번갈아 골라 한 곳의 편중을 막습니다."""
    primary_terms = _NEWS_PRIMARY_TERMS.get(market or "", ())
    secondary_terms = _NEWS_SECONDARY_TERMS.get(market or "", ())
    ranked: list[tuple[int, int, dict]] = []
    for index, item in enumerate(recent_news):
        title = item.get("title", "").lower()
        primary_hits = _headline_term_count(title, primary_terms)
        secondary_hits = _headline_term_count(title, secondary_terms)
        # 지수·환율·수급처럼 장 마감과 직접 연결되는 표현이 하나라도 있거나,
        # 업종·실적 같은 보조 표현이 둘 이상 함께 있어야 시장 기사로 인정합니다.
        relevant = primary_hits > 0 or secondary_hits >= 2
        score = primary_hits * 10 + secondary_hits
        if not primary_terms or relevant:
            ranked.append((score, index, item))
    if primary_terms and not ranked:
        return []

    grouped: dict[str, list[tuple[int, int, dict]]] = {}
    for score, index, item in ranked:
        grouped.setdefault(item.get("source", "기타"), []).append((score, index, item))
    for items in grouped.values():
        items.sort(key=lambda row: (-row[0], row[1]))

    per_source_limit = max(1, (limit + len(grouped) - 1) // len(grouped))
    for source, items in grouped.items():
        grouped[source] = items[:per_source_limit]

    selected: list[dict] = []
    while len(selected) < limit:
        added = False
        for items in grouped.values():
            if items and len(selected) < limit:
                selected.append(items.pop(0)[2])
                added = True
        if not added:
            break
    return selected


def _headline_section(
    market: str, recent_news: list[dict] | None
) -> tuple[dict | None, list[dict]]:
    if not recent_news:
        return None, []
    selected = _select_diverse_headlines(recent_news, market=market)
    if not selected:
        return None, []
    source_count = len({item.get("source") for item in selected})
    return (
        {
            "heading": "함께 확인할 최신 뉴스",
            "body": (
                f"시장 관련 키워드가 확인된 최근 RSS 기사 {len(selected)}건을 "
                f"{source_count}개 매체에서 고르게 골랐습니다. 기사 제목과 원문 링크는 "
                "글 아래 자료 확인에 정리했으며, 원문을 읽지 않은 상태에서 인과관계를 만들지 않았습니다."
            ),
        },
        [
            {"name": item["source"], "title": item["title"], "url": item.get("link", "")}
            for item in selected
            if item.get("link")
        ],
    )


def generate(
    market: str, date_str: str, price_data: dict, recent_news: list[dict] | None = None
) -> dict:
    """AI 호출 없이 렌더러가 요구하는 한국어 콘텐츠 구조를 만듭니다."""
    market_label = "미국장" if market == "us" else "한국장"
    ranked = _ranked_entries(price_data)
    positive = sorted(
        (entry for entry in ranked if entry["change_pct"] > 0),
        key=lambda entry: entry["change_pct"],
        reverse=True,
    )
    negative = sorted(
        (entry for entry in ranked if entry["change_pct"] < 0),
        key=lambda entry: entry["change_pct"],
    )
    lead_macro = next(iter(price_data.get("macro", {}).values()), None)
    title_parts = [_title_change(lead_macro)] if lead_macro else []
    if ranked:
        title_parts.append(_title_change(ranked[0]))
    title = ", ".join(title_parts) or f"{date_str} {market_label} 마감 시황"

    narrative = [
        {"heading": "주요 지수와 환율", "body": _market_summary(price_data, date_str)},
        {"heading": "관심 종목에서 확인된 흐름", "body": _watchlist_summary(price_data)},
    ]
    recent_trend = _recent_trend_summary(price_data)
    if recent_trend:
        narrative.append({"heading": "최근 5거래일 흐름", "body": recent_trend})
    foreign_flow = _foreign_flow_summary(price_data)
    if foreign_flow:
        narrative.append({"heading": "외국인 순매매 점검", "body": foreign_flow})
    headlines, sources = _headline_section(market, recent_news)
    if headlines:
        narrative.append(headlines)

    highlights = []
    if positive:
        highlights.append({"label": "상승 폭 상위", "ticker": positive[0]["ticker"]})
    if negative:
        highlights.append({"label": "하락 폭 상위", "ticker": negative[0]["ticker"]})

    featured = ranked[: min(6, len(ranked))]
    if market == "us":
        outlook_body = (
            "다음 거래일에는 주요 지수의 방향과 미 국채금리, VIX, 금·원유 같은 교차자산 흐름을 "
            "함께 확인할 필요가 있습니다. 개별 종목은 하루 등락률만으로 추세를 단정하지 않고 "
            "거래량과 후속 공시를 함께 살펴봐야 합니다."
        )
    else:
        outlook_body = (
            "다음 거래일에는 주요 지수의 방향, 원/달러 환율, 외국인 순매매가 같은 방향으로 "
            "이어지는지 확인할 필요가 있습니다. 개별 종목은 하루 등락률만으로 추세를 단정하지 "
            "않고 거래량과 후속 공시를 함께 살펴봐야 합니다."
        )
    return {
        "title": title,
        "narrative": narrative,
        "theme_section": {
            "heading": "등락 폭이 컸던 종목",
            "commentary": "상승·하락 폭은 수집한 종가 기준으로 정리했습니다.",
            "highlights": highlights,
        },
        "stock_section": {
            "heading": "주요 종목 등락",
            "commentary": "절대 등락 폭이 큰 순서로 배치했습니다. 수치는 모두 해당 거래일 종가 기준입니다.",
            "featured_tickers": [entry["ticker"] for entry in featured],
        },
        "outlook": {
            "heading": "다음 거래일에 확인할 항목",
            "body": outlook_body,
        },
        "closing": {
            "heading": "오늘의 수치 요약",
            "body": "이 글은 실제 종가와 등락률, 언론사 RSS 헤드라인을 구분해 정리했습니다. "
            "뉴스 원문을 확인하지 않은 내용은 시장 움직임의 원인으로 단정하지 않았습니다.",
        },
        "insight_section": None,
        "calendar": [],
        "sources": sources,
    }
