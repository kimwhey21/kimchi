"""그날 거래대금 상위 종목(= 시장이 실제로 돈을 쓴 곳)을 골라옵니다.

왜 필요한가
-----------
고정 워치리스트만으로는 "목록 밖에서 터진 날"을 담지 못합니다. 2026-09-03
한국장이 그랬습니다. 그날을 이끈 것은 보험·은행이었는데 워치리스트에 금융주가
하나도 없어서, KB금융(+5.20%)·신한지주(+3.62%)는 카드도 외국인 수급도 없이
본문 문장으로만 인용됐습니다.

왜 거래대금인가
---------------
등락률 상위로 뽑으면 안 됩니다. 같은 날 네이버 등락률 상위는 써니전자
+11.80%, 키움 레버리지 조선TOP10 ETN 같은 것들이었습니다. 반면 시가총액 상위
안에서 거래대금으로 줄을 세우면 삼성전기·KB금융·두산에너빌리티·현대차가
나옵니다 — 그날 글이 실제로 다뤄야 했던 종목입니다.

거르는 것
---------
- ETF/ETN: 응답의 ``stockEndType``이 "stock"인 것만 남깁니다. KODEX 200,
  TIGER 미국S&P500, CD금리액티브처럼 거래대금 상위를 채우지만 시황에서
  개별 종목으로 다룰 대상이 아닌 것들이 여기서 빠집니다.
- 우선주: 삼성전자우처럼 본주와 같은 이야기를 두 번 하게 되는 종목.
  종목코드 끝자리가 0이 아니거나 이름이 '우'로 끝나면 제외합니다.
- 시가총액 하한 미달 종목.

실패하면 빈 목록을 돌려줍니다. 이 데이터가 없어도 코어 워치리스트만으로
글은 나가야 하기 때문입니다.
"""
from __future__ import annotations

import requests

_URL = "https://m.stock.naver.com/api/stocks/marketValue/{market}"
_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
_TIMEOUT_SECONDS = 10
_PAGE_SIZE = 50


def _to_int(value: str | None) -> int:
    try:
        return int(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return 0


def _is_common_stock(item: dict) -> bool:
    """ETF·ETN·우선주를 걸러냅니다."""
    if item.get("stockEndType") != "stock":
        return False
    code = item.get("itemCode") or ""
    if not code.endswith("0"):  # 우선주는 끝자리가 0이 아닙니다 (예: 005935)
        return False
    name = item.get("stockName") or ""
    return not (name.endswith("우") or name.endswith("우B"))


def _universe(market: str, universe_size: int) -> list[dict]:
    """시가총액 상위 universe_size개를 가져옵니다."""
    rows: list[dict] = []
    for page in range(1, (universe_size + _PAGE_SIZE - 1) // _PAGE_SIZE + 1):
        response = requests.get(
            _URL.format(market=market),
            params={"page": page, "pageSize": _PAGE_SIZE},
            headers=_HEADERS,
            timeout=_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        stocks = response.json().get("stocks") or []
        if not stocks:
            break
        rows.extend(stocks)
    return rows[:universe_size]


def fetch_top_turnover(
    exclude_tickers: set[str],
    count: int = 6,
    universe_size: int = 100,
    min_market_cap: int = 1_000_000_000_000,
    markets: tuple[str, ...] = ("KOSPI", "KOSDAQ"),
) -> list[dict]:
    """거래대금 상위 종목을 [{ticker, name, market, trading_value, market_cap}] 로.

    exclude_tickers에 든 종목(=코어 워치리스트)은 빼고 돌려줍니다.
    """
    candidates: list[dict] = []
    for market in markets:
        try:
            rows = _universe(market, universe_size)
        except Exception as exc:  # 네트워크·응답 형식 문제 모두 포함
            print(f"[경고] {market} 거래대금 상위 조회 실패: {exc}")
            continue
        for item in rows:
            ticker = item.get("itemCode") or ""
            if not ticker or ticker in exclude_tickers:
                continue
            if not _is_common_stock(item):
                continue
            if _to_int(item.get("marketValueRaw")) < min_market_cap:
                continue
            candidates.append(
                {
                    "ticker": ticker,
                    "name": item.get("stockName") or ticker,
                    "market": market,
                    "trading_value": _to_int(item.get("accumulatedTradingValueRaw")),
                    "market_cap": _to_int(item.get("marketValueRaw")),
                }
            )

    candidates.sort(key=lambda row: row["trading_value"], reverse=True)
    return candidates[:count]


if __name__ == "__main__":
    for row in fetch_top_turnover(set()):
        print(f"{row['name']:16s} {row['ticker']} {row['market']:6s} "
              f"거래대금 {row['trading_value'] / 1e8:>10,.0f}억")
