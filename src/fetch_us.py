"""미국 시장 시세 수집 스크립트.

yfinance로 주요 지수/금리와 관심 종목의 종가, 등락률, 최근 며칠간의
종가 흐름(스파크라인용 시계열)을 가져옵니다.

주의:
    이 스크립트는 Yahoo Finance 서버에 접속해야 동작합니다.
    외부 인터넷 접속이 막힌 환경(일부 샌드박스 등)에서는 실행되지 않으니,
    실제로는 여러분의 컴퓨터나 GitHub Actions처럼 접속이 자유로운 곳에서 돌리세요.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

import yaml
import yfinance as yf

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "watchlist_us.yaml"

_NAN_RETRY_ATTEMPTS = 3
_NAN_RETRY_DELAY_SECONDS = 5


def _fetch_one(ticker: str, name: str, name_en: str = "", lookback: int = 7, is_yield: bool = False,
                unit: str = "", **_ignore) -> dict:
    """종목/지수 하나의 최근 시세를 가져와 카드에 필요한 형태로 정리합니다."""
    closes: list[float] | None = None
    for attempt in range(1, _NAN_RETRY_ATTEMPTS + 1):
        hist = yf.Ticker(ticker).history(period=f"{lookback + 2}d")
        if hist.empty or len(hist) < 2:
            raise ValueError(f"{ticker}: 시세 데이터를 가져오지 못했습니다.")

        candidate = hist["Close"].tolist()[-(lookback + 1):]
        if not any(math.isnan(c) for c in candidate):
            closes = candidate
            last_trading_date = hist.index[-1].date().isoformat()
            break
        # Yahoo Finance가 일시적으로 결측치(NaN)를 줄 때가 있습니다 (몇 초 후
        # 재조회하면 채워져 있는 경우가 많음). "숫자는 절대 지어내지 않는다"는
        # 원칙상 nan을 그대로 쓸 수는 없으니, 몇 번 재시도해보고 그래도 안 되면
        # 최종적으로 실패시킵니다 (파이프라인이 멈추고 발행 없이 다음 스케줄을 기다림).
        print(
            f"[경고] {ticker}: 시세 데이터에 결측값(NaN) 발견, 재시도 {attempt}/{_NAN_RETRY_ATTEMPTS}"
        )
        if attempt < _NAN_RETRY_ATTEMPTS:
            time.sleep(_NAN_RETRY_DELAY_SECONDS)

    if closes is None:
        raise ValueError(f"{ticker}: 시세 데이터에 결측값(NaN)이 있습니다 ({_NAN_RETRY_ATTEMPTS}번 재시도 후에도).")

    if is_yield:
        closes = [c / 10 for c in closes]  # ^TNX, ^TYX 는 실제 금리*10 으로 표기됨

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

    trading_date: 다우존스(첫 macro 항목)의 실제 마지막 거래일입니다. 미국
    증시가 휴장(공휴일·주말)이었다면 데이터 소스가 그 전 거래일 값을 그대로
    돌려주므로, 이 값으로 "이 거래일을 이미 발행했는지"를 main.py에서
    판단합니다.
    """
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    macro = {row["ticker"]: _fetch_one(**row) for row in config["macro"]}
    watchlist = {row["ticker"]: _fetch_one(**row) for row in config["watchlist"]}
    trading_date = next(iter(macro.values()))["trading_date"]
    return {"macro": macro, "watchlist": watchlist, "trading_date": trading_date}


if __name__ == "__main__":
    print(json.dumps(fetch_all(), ensure_ascii=False, indent=2))
