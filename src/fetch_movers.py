"""그날 거래대금 상위 종목(= 시장이 실제로 돈을 쓴 곳)을 골라옵니다.

한국장은 네이버 금융, 미국장은 나스닥 스크리너를 씁니다. 두 시장 모두 방식은
같습니다 — 시가총액이 일정 규모 이상인 종목 중에서 그날 거래대금 순으로 뽑고,
고정 워치리스트에 이미 있는 종목은 뺍니다.

왜 필요한가
-----------
고정 워치리스트만으로는 "목록 밖에서 터진 날"을 담지 못합니다. 2026-09-03
한국장이 그랬습니다. 그날을 이끈 것은 보험·은행이었는데 워치리스트에 금융주가
하나도 없어서, KB금융(+5.20%)·신한지주(+3.62%)는 카드도 외국인 수급도 없이
본문 문장으로만 인용됐습니다.

미국장도 같습니다. 고정 16종목으로는 2026-09-02의 DELL(+15.81%, 거래대금
181억 달러)이나 AVGO·SNDK·PLTR이 잡히지 않습니다.

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

import re

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


_US_URL = "https://api.nasdaq.com/api/screener/stocks"
_US_HEADERS = {**_HEADERS, "Accept": "application/json"}


def _us_number(value: str | None) -> float:
    """"$151.39", "3,130,819" 같은 문자열을 숫자로 바꿉니다."""
    try:
        return float(str(value).replace("$", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return 0.0


_US_NAME_SUFFIXES = (
    " Common Stock",
    " American Depositary Shares",
    " Incorporated",
    " Corporation",
    " Holdings",
    " Company",
    " Corp.",
    " Inc.",
    " plc",
    " Ltd.",
    " N.V.",
    " S.A.",
    " A/S",
    " & Co.",
    ",",
)


def clean_us_name(name: str) -> str:
    """스크리너 종목명을 카드에 쓸 만한 길이로 다듬습니다.

    "NVIDIA Corporation Common Stock" -> "NVIDIA"
    "Palantir Technologies Inc. Class A" -> "Palantir Technologies"

    법인 형태 표기는 카드 폭만 잡아먹고 종목을 알아보는 데 도움이 되지
    않습니다. 이름이 통째로 사라지지 않도록 접미사를 떼고도 남는 게 있을
    때만 잘라냅니다.
    """
    cleaned = name.split(" Class ")[0].strip()
    changed = True
    while changed:
        changed = False
        for suffix in _US_NAME_SUFFIXES:
            if cleaned.endswith(suffix) and len(cleaned) > len(suffix) + 1:
                cleaned = cleaned[: -len(suffix)].strip()
                changed = True
    return cleaned or name


def _is_us_common_stock(symbol: str, name: str) -> bool:
    """우선주·워런트·유닛처럼 시황에서 개별 종목으로 다루지 않는 것을 거릅니다.

    나스닥 스크리너의 stocks 엔드포인트는 ETF를 이미 제외하고 돌려줍니다
    (SPY·QQQ가 상위에 없는 것으로 확인). 남는 것은 같은 회사의 파생 종목이며,
    심볼의 특수문자(BRK/A, ABC^B)와 종목명으로 걸러집니다.
    """
    if any(char in symbol for char in ("^", "/", ".")):
        return False
    lowered = name.lower()
    # 2026-09-26: 'depositary'가 ADR(보통주 예탁증서 — ARM·BABA·PDD)까지 막았고, 'right'가 'Brightspring'까지 막았다.
    # 우선주 예탁증서는 이름에 'preferred'가 있어 그대로 걸러지고, 권리(rights)는 낱말로만 찾는다.
    # config/watchlist_us.yaml의 이름표에 "Arm Holdings plc American Depositary Shares"가 이미 있다 — 받으려던 종목이다.
    if "depositary" in lowered and "american depositary" not in lowered:
        return False
    if re.search(r"\brights?\b", lowered):
        return False
    return not any(word in lowered for word in ("preferred", "warrant", " unit"))


def fetch_top_dollar_volume_us(
    exclude_tickers: set[str],
    count: int = 6,
    min_market_cap: float = 10_000_000_000.0,
    reference_prices: dict[str, float] | None = None,
    trading_date: str | None = None,
) -> list[dict]:
    """미국장 거래대금(= 종가 x 거래량) 상위 종목을 돌려줍니다.

    2026-10-06: 나스닥 스크리너는 9/24부터 수집 시각(마감 2시간 20분 뒤)에 **전 거래일** 종가·거래량을 준다(9/25 'AMD 159억달러'는
    9/24 값이었다). 그래서 `trading_date`가 오면 스크리너는 후보를 모으는 데만 쓰고, 순위는 그날 야후 일별 종가 × 거래량으로 다시 매긴다
    (`_rank_same_day`). 후보에 야후 '거래 활발' 100개(그날 값)를 더해 스크리너가 놓친 종목도 들어오게 한다.

    나스닥 스크리너는 한 번의 요청으로 미국 상장 종목 전체(약 7,000개)의
    거래량·종가·시가총액을 줍니다. 거래대금 항목은 없으므로 종가와 거래량을
    곱해 계산합니다.

    한국장(fetch_top_turnover)과 달리 시가총액 상위 N개로 우주를 자르지 않고
    시가총액 하한만 둡니다. 응답에 전 종목이 들어 있어 굳이 자를 이유가 없고,
    하한(기본 100억 달러)만으로 테마성 소형주가 걸러지기 때문입니다.

    reference_prices에 {티커: 종가}를 주면 스크리너 값과 대조한 결과를 로그로
    남깁니다. 마감 뒤 스크리너가 언제 갱신되는지 확인하기 위한 것입니다.
    """
    reference_prices = reference_prices or {}
    try:
        response = requests.get(
            _US_URL,
            params={"tableonly": "true", "limit": "25", "download": "true"},
            headers=_US_HEADERS,
            timeout=_TIMEOUT_SECONDS * 2,
        )
        response.raise_for_status()
        rows = (response.json().get("data") or {}).get("rows") or []
    except Exception as exc:  # 네트워크·응답 형식 문제 모두 포함
        print(f"[경고] 미국장 거래대금 상위 조회 실패: {exc}")
        return []

    candidates: list[dict] = []
    for item in rows:
        symbol = (item.get("symbol") or "").strip()
        name = (item.get("name") or "").strip()
        if symbol and symbol in reference_prices:
            # 스크리너가 마감 뒤 언제 당일 데이터로 바뀌는지 아직 실측하지
            # 못했습니다. 늦게 갱신되면 시세는 오늘 것인데 편입 순위만 어제
            # 기준이 됩니다. 코어 종목의 종가와 대조한 결과를 로그에 남겨,
            # 실행 기록만 보고도 어긋난 날을 알 수 있게 합니다.
            screener_price = _us_number(item.get("lastsale"))
            expected = reference_prices[symbol]
            if expected and screener_price:
                gap = abs(screener_price - expected) / expected * 100
                verdict = "같음" if gap < 0.5 else f"차이 {gap:.2f}%"
                print(
                    f"[확인] 스크리너 {symbol} {screener_price:,.2f} vs 종가 "
                    f"{expected:,.2f} — {verdict}"
                )
        if not symbol or symbol in exclude_tickers:
            continue
        if not _is_us_common_stock(symbol, name):
            continue
        market_cap = _us_number(item.get("marketCap"))
        if market_cap < min_market_cap:
            continue
        trading_value = _us_number(item.get("lastsale")) * _us_number(item.get("volume"))
        if trading_value <= 0:
            continue
        candidates.append(
            {
                "ticker": symbol,
                "name": clean_us_name(name),
                "market": "US",
                "sector": item.get("sector") or "",
                "trading_value": trading_value,
                "market_cap": market_cap,
            }
        )

    candidates.sort(key=lambda row: row["trading_value"], reverse=True)
    if trading_date:
        return _rank_same_day(candidates[:40], exclude_tickers, count, min_market_cap, trading_date)
    return candidates[:count]


def _rank_same_day(pool: list[dict], exclude: set[str], count: int, min_market_cap: float, day: str) -> list[dict]:
    """후보(스크리너 상위 + 야후 '거래 활발')를 그날 야후 일별 종가 × 거래량으로 다시 줄 세운다. 그날 값이 없는 후보는 빼고 개수를 찍는다."""
    import datetime as _dt
    import yfinance as yf
    by_symbol = {row["ticker"]: dict(row) for row in pool}
    try:
        actives = (yf.screen("most_actives", count=100) or {}).get("quotes") or []
    except Exception as exc:  # noqa: BLE001 — 센다: 스크리너 후보만으로 계속하고 이유를 남긴다
        print(f"[경고] 야후 '거래 활발' 목록을 받지 못했습니다 — 스크리너 후보만으로 줄 세웁니다: {exc}")
        actives = []
    for q in actives:
        symbol = str(q.get("symbol") or "").strip()
        name = str(q.get("longName") or q.get("shortName") or "").strip()
        if (not symbol or symbol in exclude or symbol in by_symbol or q.get("quoteType") != "EQUITY"
                or (q.get("marketCap") or 0) < min_market_cap or not _is_us_common_stock(symbol, name)):
            continue
        by_symbol[symbol] = {"ticker": symbol, "name": clean_us_name(name), "market": "US", "sector": "",
                             "trading_value": 0.0, "market_cap": float(q.get("marketCap") or 0)}
    if not by_symbol:
        return []
    end = (_dt.date.fromisoformat(day) + _dt.timedelta(days=1)).isoformat()
    frame = yf.download(sorted(by_symbol), start=day, end=end, auto_adjust=False, progress=False, threads=True, group_by="column")
    ranked, missing = [], []
    for symbol, row in by_symbol.items():
        try:
            close = float(frame["Close"][symbol].loc[day]) if len(by_symbol) > 1 else float(frame["Close"].loc[day])
            volume = float(frame["Volume"][symbol].loc[day]) if len(by_symbol) > 1 else float(frame["Volume"].loc[day])
        except (KeyError, TypeError, ValueError):
            missing.append(symbol)
            continue
        if not (close > 0 and volume > 0):
            missing.append(symbol)
            continue
        ranked.append({**row, "trading_value": close * volume})
    if missing:
        print(f"[안내] 편입 후보 {len(missing)}개는 {day} 야후 일별 값이 없어 순위에서 뺐습니다: {', '.join(missing[:10])}")
    ranked.sort(key=lambda r: r["trading_value"], reverse=True)
    print(f"[대조] 편입 순위는 {day} 종가 × 거래량(야후 일별)으로 매겼습니다 — 후보 {len(by_symbol)}개 중 {len(ranked)}개")
    return ranked[:count]


if __name__ == "__main__":
    print("[한국장]")
    for row in fetch_top_turnover(set()):
        print(f"  {row['name']:16s} {row['ticker']} {row['market']:6s} "
              f"거래대금 {row['trading_value'] / 1e8:>10,.0f}억원")
    print("[미국장]")
    for row in fetch_top_dollar_volume_us(set()):
        print(f"  {row['name'][:28]:30s} {row['ticker']:6s} "
              f"거래대금 {row['trading_value'] / 1e9:>6.1f}B달러  {row['sector']}")
