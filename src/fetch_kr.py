"""한국 시장 시세 수집 스크립트.

FinanceDataReader로 코스피/코스닥/환율과 관심 종목의 종가, 등락률,
최근 며칠간의 종가 흐름(스파크라인용 시계열)을 가져옵니다.

주의:
    이 스크립트는 KRX/네이버 등 데이터 소스에 접속해야 동작합니다.
    외부 인터넷 접속이 막힌 환경(일부 샌드박스 등)에서는 실행되지 않으니,
    실제로는 여러분의 컴퓨터나 GitHub Actions처럼 접속이 자유로운 곳에서 돌리세요.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import time
from pathlib import Path

import FinanceDataReader as fdr
import yaml

from src import fetch_foreign_flows

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "watchlist_kr.yaml"

_NAN_RETRY_ATTEMPTS = 3
_NAN_RETRY_DELAY_SECONDS = 5


def _fetch_one(
    ticker: str, name: str, name_en: str = "", lookback: int = 7, unit: str = "", **_ignore
) -> dict:
    """종목/지수 하나의 최근 시세를 가져와 카드에 필요한 형태로 정리합니다."""
    end = dt.date.today()
    start = end - dt.timedelta(days=lookback * 3)  # 주말·공휴일 감안 여유있게 조회

    closes: list[float] | None = None
    for attempt in range(1, _NAN_RETRY_ATTEMPTS + 1):
        df = fdr.DataReader(ticker, start, end)
        if df.empty or len(df) < 2:
            raise ValueError(f"{ticker}: 시세 데이터를 가져오지 못했습니다.")

        # 환율 데이터에는 최신 행이나 중간 거래일의 OHLC 일부가 비어 있는
        # 경우가 있습니다. 원고에 쓰는 값은 종가뿐이므로 유효한 종가만 골라
        # 최근 흐름을 만들고, 그중 마지막 두 값으로 등락률을 계산합니다.
        # 마지막 유효 종가가 두 개보다 적을 때만 데이터 부족으로 재시도합니다.
        valid_closes = df["Close"].dropna().tail(lookback + 1)
        candidate = [float(value) for value in valid_closes.tolist()]
        if len(candidate) >= 2 and all(math.isfinite(value) for value in candidate):
            closes = candidate
            last_trading_date = valid_closes.index[-1].date().isoformat()
            break
        # 데이터 소스가 일시적으로 결측치(NaN)를 줄 때가 있습니다 (몇 초 후 재조회하면
        # 채워져 있는 경우가 많음). "숫자는 절대 지어내지 않는다"는 원칙상 nan을 그대로
        # 쓸 수는 없으니, 몇 번 재시도해보고 그래도 안 되면 최종적으로 실패시킵니다.
        print(
            f"[경고] {ticker}: 유효한 종가가 부족하거나 비정상 값이 있어 재시도 "
            f"{attempt}/{_NAN_RETRY_ATTEMPTS}"
        )
        if attempt < _NAN_RETRY_ATTEMPTS:
            time.sleep(_NAN_RETRY_DELAY_SECONDS)

    if closes is None:
        raise ValueError(
            f"{ticker}: 유효한 종가를 2개 이상 가져오지 못했습니다 "
            f"({_NAN_RETRY_ATTEMPTS}번 재시도 후에도)."
        )

    prev_close, last_close = closes[-2], closes[-1]
    change_pct = (last_close - prev_close) / prev_close * 100

    return {
        "ticker": ticker,
        "name": name,
        "name_en": name_en or name,
        "price": round(last_close, 2),
        "change_pct": round(change_pct, 2),
        "series": [round(c, 4) for c in closes],
        "unit": unit,
        "trading_date": last_trading_date,
    }


def fetch_all() -> dict:
    """설정 파일에 등록된 모든 지수/종목의 시세를 가져옵니다.

    trading_date: 코스피(첫 macro 항목)의 실제 마지막 거래일입니다. 오늘
    한국 증시가 휴장(공휴일·주말)이었다면 데이터 소스가 그 전 거래일 값을
    그대로 돌려주므로, 이 값으로 "오늘 실제로 장이 열렸는지"와 "이 거래일을
    이미 발행했는지"를 main.py에서 판단합니다.
    """
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    macro = {row["ticker"]: _fetch_one(**row) for row in config["macro"]}
    watchlist = {row["ticker"]: _fetch_one(**row) for row in config["watchlist"]}
    fetch_foreign_flows.attach_foreign_flows(watchlist)
    trading_date = next(iter(macro.values()))["trading_date"]
    return {"macro": macro, "watchlist": watchlist, "trading_date": trading_date}


if __name__ == "__main__":
    print(json.dumps(fetch_all(), ensure_ascii=False, indent=2))
