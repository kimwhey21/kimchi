"""발행 전에 한국장 핵심 시세의 기준일이 같은지 확인합니다."""
from __future__ import annotations


class MarketDataNotReadyError(ValueError):
    pass


def validate_trading_dates(market: str, price_data: dict) -> None:
    """한국 지수와 종목이 서로 다른 거래일이면 혼합 원고 생성을 막습니다.

    장중에는 개별 종목이 오늘 값인데 코스피·코스닥 종가는 전 거래일 값일 수
    있습니다. 환율은 시장의 기준 시각이 달라 하루 늦을 수 있어 핵심 일치
    검사에서는 제외하고, 렌더러가 별도 기준일을 표시합니다.
    """
    if market != "kr":
        return

    core_dates: dict[str, str] = {}
    for ticker in ("KS11", "KQ11"):
        entry = price_data.get("macro", {}).get(ticker) or {}
        if entry.get("trading_date"):
            core_dates[ticker] = entry["trading_date"]
    for ticker, entry in price_data.get("watchlist", {}).items():
        if entry.get("trading_date"):
            core_dates[ticker] = entry["trading_date"]

    unique_dates = set(core_dates.values())
    if len(unique_dates) > 1:
        grouped = {
            date: [ticker for ticker, value in core_dates.items() if value == date]
            for date in sorted(unique_dates)
        }
        raise MarketDataNotReadyError(
            "한국장 시세 기준일이 아직 일치하지 않습니다: " + str(grouped)
        )
