"""미국 시장 시세 수집 스크립트.

yfinance로 주요 지수/금리와 관심 종목의 종가, 등락률, 최근 며칠간의
종가 흐름(스파크라인용 시계열)을 가져옵니다.

주의:
    이 스크립트는 Yahoo Finance 서버에 접속해야 동작합니다.
    외부 인터넷 접속이 막힌 환경(일부 샌드박스 등)에서는 실행되지 않으니,
    실제로는 여러분의 컴퓨터나 GitHub Actions처럼 접속이 자유로운 곳에서 돌리세요.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import time
from pathlib import Path

import requests
import yaml
import yfinance as yf

from src import fetch_movers, price_history

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "watchlist_us.yaml"

# 결측값(NaN) 재시도. 전에는 5초 간격 3회, 즉 재시도 창이 총 15초뿐이었습니다.
# 그런데 실제로 관측된 지연은 분 단위입니다 — 2026-08-31~09-01에 정각 실행이
# USD/KRW 결측으로 3회 연속 죽었고, **7분 뒤** 수동 실행은 성공했습니다.
# 15초 창으로는 애초에 닿지 않는 지연이었습니다. 지수 백오프로 창을 4분으로
# 넓힙니다(10 + 30 + 60 + 120초).
_NAN_RETRY_DELAYS = (10, 30, 60, 120)
_NAN_RETRY_ATTEMPTS = len(_NAN_RETRY_DELAYS) + 1


def previous_close(historical_prev: float, last_close: float, quote_metadata: dict | None) -> float:
    """등락률의 분모가 될 직전 종가.

    Yahoo 일봉 이력에는 드물게 직전 거래일 한 줄이 빠집니다. 2026-08-31에는 주요 지수와 DE의 8/28 값이 누락돼
    8/27 대비 등락률이 계산됐습니다. 메타데이터의 previousClose는 이 경우에도 실제 직전 종가를 주므로,
    regularMarketPrice가 마지막 일봉과 일치할 때 우선 씁니다.

    **예외(2026-09-26): 그 사이에 장이 없었던 날.** 채권만 쉬는 날(콜럼버스 데이·재향군인의 날)이나 휴장 뒤 재실행에서는
    메타데이터의 previousClose가 마지막 종가와 같게 나와 등락률이 0.00%가 됩니다 — 9/04 파일의 ^TNX가 -0.0으로 찍혔는데
    일봉으로는 4.762→4.784(+0.46%)였습니다. 메타데이터 직전 종가가 마지막 종가와 같은데 일봉으로는 움직임이 있으면,
    메타데이터가 '오늘 장이 없었다'는 뜻이므로 일봉을 믿습니다. 진짜 보합인 날은 둘 다 같아서 어느 쪽이든 0입니다.
    """
    try:
        metadata_last = float((quote_metadata or {}).get("regularMarketPrice"))
        metadata_prev = float((quote_metadata or {}).get("previousClose"))
    except (TypeError, ValueError, KeyError):
        # 메타데이터가 없는 종목은 기존 일봉 계산으로 안전하게 폴백합니다.
        return historical_prev
    tolerance = max(0.02, abs(last_close) * 0.001)
    if not (math.isfinite(metadata_last) and math.isfinite(metadata_prev) and metadata_prev != 0):
        return historical_prev
    if abs(metadata_last - last_close) > tolerance:
        return historical_prev
    no_session = abs(metadata_prev - last_close) <= tolerance < abs(historical_prev - last_close)
    return historical_prev if no_session else metadata_prev


def required_trading_date(macro: dict) -> str:
    """필수 지수(다우·S&P·나스닥)의 기준일 — 셋이 다르면 멈춘다(2026-09-26).

    전에는 집합(set)에서 `next()`로 하나를 골라, 실행마다 어느 지수의 날짜를 쓸지가 바뀌었다(파이썬 해시가 실행마다
    달라진다). 한 지수 일봉이 하루 늦으면 파일 날짜가 무작위로 틀어지고, 늦은 지수의 등락률이 오늘 파일에 경고 없이
    들어갈 수 있었다. 한국장은 `data_quality`가 이미 이렇게 막는다. 멈추면 main이 다시 시도하고, 예약 재시도(:27/:34)가 있다.
    """
    dates = {t: str(macro[t]["trading_date"]) for t in sorted(_REQUIRED) if t in macro}
    if not dates:
        raise ValueError("필수 지수(다우·S&P·나스닥)를 하나도 받지 못했습니다.")
    if len(set(dates.values())) > 1:
        raise ValueError(f"필수 지수의 기준일이 서로 다릅니다: {dates} — 늦은 지수가 따라올 때까지 기다립니다.")
    return next(iter(dates.values()))


def _fetch_one(ticker: str, name: str, name_en: str = "", lookback: int = 7, is_yield: bool = False,
                unit: str = "", **_ignore) -> dict:
    """종목/지수 하나의 최근 시세를 가져와 카드에 필요한 형태로 정리합니다."""
    closes: list[float] | None = None
    ticker_client = yf.Ticker(ticker)
    try:
        quote_metadata = ticker_client.get_history_metadata()
    except Exception as exc:  # noqa: BLE001 - 메타데이터 실패 시 일봉으로 폴백(종가는 second_close가 공식 원천과 따로 맞춘다)
        print(f"[안내] {ticker}: 야후 메타데이터를 못 받아 직전 종가를 일봉에서 씁니다 — {type(exc).__name__}: {exc}")
        quote_metadata = {}
    for attempt in range(1, _NAN_RETRY_ATTEMPTS + 1):
        # 최근 3개월 이력(history)까지 한 번에 받습니다 — 본문 기간 차트용(2026-09-08).
        # 등락률·스파크라인은 여전히 마지막 lookback+1개만 씁니다.
        hist = ticker_client.history(period="4mo")
        if hist.empty or len(hist) < 2:
            raise ValueError(f"{ticker}: 시세 데이터를 가져오지 못했습니다.")

        # 최신 행이나 중간 거래일에 빈 종가가 섞여도, 실제 원고에 사용하는
        # 유효 종가가 두 개 이상이면 안전하게 최근 흐름과 등락률을 계산합니다.
        valid_closes = hist["Close"].dropna().tail(lookback + 1)
        candidate = [float(value) for value in valid_closes.tolist()]
        if len(candidate) >= 2 and all(math.isfinite(value) for value in candidate):
            closes = candidate
            last_trading_date = valid_closes.index[-1].date().isoformat()
            break
        # Yahoo Finance가 일시적으로 결측치(NaN)를 줄 때가 있습니다 (몇 초 후
        # 재조회하면 채워져 있는 경우가 많음). "숫자는 절대 지어내지 않는다"는
        # 원칙상 nan을 그대로 쓸 수는 없으니, 몇 번 재시도해보고 그래도 안 되면
        # 최종적으로 실패시킵니다 (파이프라인이 멈추고 발행 없이 다음 스케줄을 기다림).
        print(
            f"[경고] {ticker}: 유효한 종가가 부족하거나 비정상 값이 있어 재시도 "
            f"{attempt}/{_NAN_RETRY_ATTEMPTS}"
        )
        if attempt < _NAN_RETRY_ATTEMPTS:
            time.sleep(_NAN_RETRY_DELAYS[attempt - 1])

    if closes is None:
        raise ValueError(
            f"{ticker}: 유효한 종가를 2개 이상 가져오지 못했습니다 "
            f"({_NAN_RETRY_ATTEMPTS}번 재시도 후에도)."
        )

    # Yahoo Finance는 현재 ^TNX/^TYX를 이미 실제 금리(예: 4.758%)로 돌려줍니다.
    # 과거처럼 10으로 나누면 4.758%가 0.48%로 잘못 표시됩니다.

    historical_prev, last_close = closes[-2], closes[-1]
    prev_close = previous_close(historical_prev, last_close, quote_metadata)
    change_pct = (last_close - prev_close) / prev_close * 100

    return {
        "ticker": ticker,
        "name": name,
        "name_en": name_en or name,
        "price": round(last_close, 2),
        "change_pct": round(change_pct, 2),
        "series": [round(c, 4) for c in closes],
        "history": price_history.from_frame(hist),
        "unit": unit,
        "trading_date": last_trading_date,
    }


# ── 두 번째 원천(2026-10-05) ───────────────────────────────────────────────────────
# 야후 하나로 받던 종가를 공식 원천과 맞춘다 — 개별 종목·ETF는 나스닥 공식 일별 종가(12개 파일 240건이 야후와 모두 같았다),
# 나스닥 종합은 나스닥, 다우는 FRED(미국 18:02 ET에 올라온다). S&P500(20:01 ET)·VIX는 수집 시각(18:20 ET)에 아직 없어
# 그날 저녁 close_check가 맞춘다. 금리·금·원유·러셀은 두 번째 원천이 없다(야후 하나 — 대신 빼지 않는다).
_NASDAQ = "https://api.nasdaq.com/api/quote/{symbol}/historical"
_NASDAQ_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/141 Safari/537.36",
                   "Accept": "application/json"}
_FRED = "https://api.stlouisfed.org/fred/series/observations"
_FRED_SERIES = {"^DJI": "DJIA", "^GSPC": "SP500", "^IXIC": "NASDAQCOM", "^VIX": "VIXCLS"}


def nasdaq_closes(symbol: str, day: str) -> dict[str, float]:
    """나스닥 공식 일별 종가 {날짜: 종가}(그날까지 열흘). 종목이 아니면 ETF로, ^IXIC은 COMP 지수로 묻는다. 못 받으면 빈 dict."""
    if symbol == "^IXIC":
        tries = [("COMP", "index")]
    elif symbol.startswith("^") or "=" in symbol:
        return {}
    else:
        tries = [(symbol.replace("-", "."), "stocks"), (symbol.replace("-", "."), "etf")]
    start = (dt.date.fromisoformat(day) - dt.timedelta(days=10)).isoformat()
    for sym, cls in tries:
        try:
            body = requests.get(_NASDAQ.format(symbol=sym), headers=_NASDAQ_HEADERS, timeout=20,
                                params={"assetclass": cls, "fromdate": start, "todate": day, "limit": 15}).json()
        except (requests.RequestException, ValueError) as exc:
            print(f"[안내] 나스닥 {sym}: {exc}")
            return {}
        rows = (((body or {}).get("data") or {}).get("tradesTable") or {}).get("rows") or []
        if rows:
            return {f"{r['date'][6:]}-{r['date'][:2]}-{r['date'][3:5]}": float(str(r["close"]).replace("$", "").replace(",", ""))
                    for r in rows if r.get("date") and r.get("close")}
    return {}


def fred_closes(ticker: str, start: str) -> dict[str, float]:
    """FRED 공식 종가 {날짜: 값}. 열쇠가 없으면 예외 — 조용히 건너뛰지 않는다."""
    series = _FRED_SERIES.get(ticker)
    if not series:
        return {}
    key = os.environ.get("FRED_API_KEY")
    if not key:
        raise RuntimeError("FRED_API_KEY가 없습니다 — 워크플로 env 또는 .env를 확인하세요")
    body = requests.get(_FRED, timeout=20, params={"series_id": series, "api_key": key, "file_type": "json",
                                                    "observation_start": start}).json()
    return {o["date"]: float(o["value"]) for o in body.get("observations") or [] if o.get("value") not in (None, ".", "")}


def second_close(ticker: str, day: str) -> float | None:
    """그날 두 번째 원천의 종가. 없거나(아직 안 올라옴·원천 없음) 못 받으면 None."""
    if ticker == "^DJI":
        try:
            return fred_closes(ticker, day).get(day)
        except requests.RequestException as exc:
            print(f"[안내] FRED {ticker}: {exc}")
            return None
    return nasdaq_closes(ticker, day).get(day)


def _verify_second_source(entries: dict[str, dict]) -> list[str]:
    """야후 종가를 두 번째 원천과 맞춘다. 다르면 문제 목록에, 같으면 close_sources에 둘 다 적는다."""
    problems = []
    for ticker, entry in entries.items():
        other = second_close(ticker, str(entry.get("trading_date")))
        if other is None:
            entry["close_sources"] = ["yahoo"]
            continue
        if abs(other - float(entry["price"])) > max(0.011, abs(other) * 0.00001):
            problems.append(f"{entry.get('name', ticker)}({ticker}): 야후 {entry['price']} / 공식 {other}")
            continue
        entry["close_sources"] = ["yahoo", "fred" if ticker == "^DJI" else "nasdaq"]
    return problems


# 거래일을 읽는 지수. 2026-10-05부터는 설정의 모든 항목이 필수다(하나라도 못 받으면 멈춘다) — 이 셋은 기준일 판정에만 쓴다.
_REQUIRED = {"^DJI", "^GSPC", "^IXIC"}




def _fetch_group(rows, extra=None) -> tuple[dict, list[str]]:
    """설정의 각 줄을 받아온다. 실패한 항목은 (이유와 함께) 따로 돌려준다 — 2026-10-05부터 부른 쪽이 하나라도 있으면 멈춘다."""
    out: dict[str, dict] = {}
    missing: list[str] = []
    for row in rows:
        ticker = row["ticker"]
        try:
            entry = _fetch_one(**row)
        except Exception as exc:  # noqa: BLE001 — 센다: 부른 쪽이 모아서 멈춘다
            missing.append(f"{row.get('name', ticker)}({ticker}): {exc}")
            continue
        out[ticker] = {**entry, **(extra(row) if extra else {})}
    return out, missing


def fetch_all() -> dict:
    """설정 파일에 등록된 모든 지수/종목의 시세를 가져옵니다.

    trading_date: 다우존스(첫 macro 항목)의 실제 마지막 거래일입니다. 미국
    증시가 휴장(공휴일·주말)이었다면 데이터 소스가 그 전 거래일 값을 그대로
    돌려주므로, 이 값으로 "이 거래일을 이미 발행했는지"를 main.py에서
    판단합니다.
    """
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    macro, miss_macro = _fetch_group(config["macro"])
    watchlist, miss_stock = _fetch_group(
        config["watchlist"], extra=lambda row: {"source": "core"}
    )
    # 2026-10-05: 하나도 빼지 않는다. 전에는 지수 셋만 필수였고 코어는 80%까지 빠져도 글을 냈다 — 데이터가 중요한 사이트에서
    # 빼는 것은 누락이다. 야후는 항목마다 4분까지 다시 묻는다(_fetch_one). 그래도 못 받은 항목은 이름을 모두 적고 멈춘다.
    if miss_macro or miss_stock:
        raise ValueError(f"미국장 시세 {len(miss_macro) + len(miss_stock)}개를 받지 못했습니다 — 빼지 않고 멈춥니다: "
                         + " / ".join(miss_macro + miss_stock))
    # 거래일은 필수 지수에서 읽습니다.
    trading_date = required_trading_date(macro)
    watchlist.update(_fetch_dynamic_tier(config, watchlist, trading_date))
    problems = _verify_second_source(macro) + _verify_second_source(watchlist)
    if problems:
        raise ValueError(f"야후 종가가 공식 원천과 다른 항목 {len(problems)}개 — 쓰지 않고 멈춥니다: " + " / ".join(problems))
    return {"macro": macro, "watchlist": watchlist, "trading_date": trading_date,
            "missing": []}


def _fetch_dynamic_tier(
    config: dict, core: dict[str, dict], trading_date: str
) -> dict[str, dict]:
    """그날 거래대금 상위 종목을 코어 워치리스트 뒤에 붙입니다.

    2026-10-05부터 코어와 같다 — 조회 실패·기준일 차이를 빼지 않고 이름을 적고 멈춘다(그날 거래대금 상위가 빠진 글은 누락이다).
    """
    settings = config.get("dynamic") or {}
    if not settings.get("enabled"):
        return {}

    # 스크리너 이름("Dell Technologies Inc.")과 설정 키("Dell Technologies")가
    # 법인 형태 표기 때문에 어긋나므로, 양쪽 다 다듬어서 맞춥니다.
    name_ko_map = {
        fetch_movers.clean_us_name(key).lower(): value
        for key, value in (config.get("name_ko_map") or {}).items()
    }
    movers = None
    for attempt, delay in enumerate((0, 10, 30)):
        if delay:
            time.sleep(delay)
        try:
            movers = fetch_movers.fetch_top_dollar_volume_us(
                exclude_tickers=set(core),
                count=settings.get("count", 6),
                min_market_cap=settings.get("min_market_cap", 10_000_000_000),
                # 스크리너가 당일 데이터로 갱신됐는지 로그로 확인하려고 넘깁니다.
                reference_prices={
                    ticker: float(entry["price"])
                    for ticker, entry in list(core.items())[:3]
                    if entry.get("price")
                },
            )
            if movers:
                break
            print(f"[안내] 거래대금 상위 목록이 비었습니다 — 다시 묻습니다({attempt + 1}/3)")
        except Exception as exc:  # noqa: BLE001 — 센다: 세 번 모두 실패하면 멈춘다
            print(f"[안내] 거래대금 상위 조회 실패 {attempt + 1}/3: {exc}")
    if not movers:
        raise ValueError("그날 거래대금 상위 종목을 세 번 모두 받지 못했습니다 — 편입 종목을 빼고 쓰지 않고 멈춥니다.")

    added: dict[str, dict] = {}
    failed: list[str] = []
    for mover in movers:
        ticker, name_en = mover["ticker"], mover["name"]
        name_ko = name_ko_map.get(name_en.lower())
        if not name_ko:
            print(
                f"[안내] '{name_en}'의 한글 표기가 config/watchlist_us.yaml의 "
                "name_ko_map에 없어 한국어판에도 영문 이름이 나갑니다."
            )
        try:
            entry = _fetch_one(
                ticker=ticker, name=name_ko or name_en, name_en=name_en
            )
        except Exception as exc:  # noqa: BLE001 — 센다: 아래에서 모아 멈춘다
            failed.append(f"{name_en}({ticker}): {exc}")
            continue
        if entry.get("trading_date") != trading_date:
            failed.append(f"{name_en}({ticker}): 기준일 {entry.get('trading_date')}이 코어({trading_date})와 다릅니다")
            continue
        added[ticker] = {
            **entry,
            "source": "dynamic",
            "trading_value": mover["trading_value"],
            "sector": mover["sector"],
        }

    if failed:
        raise ValueError(f"편입 종목 {len(failed)}개의 시세를 받지 못했습니다 — 빼지 않고 멈춥니다: " + " / ".join(failed))
    if added:
        names = ", ".join(entry["name"] for entry in added.values())
        print(f"[안내] 그날 거래대금 상위로 편입: {names}")
    return added


if __name__ == "__main__":
    print(json.dumps(fetch_all(), ensure_ascii=False, indent=2))
