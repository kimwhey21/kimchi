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
from pathlib import Path

import FinanceDataReader as fdr
import yaml

from src import fetch_foreign_flows

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "watchlist_kr.yaml"


def _fetch_one(
    ticker: str, name: str, name_en: str = "", lookback: int = 7, unit: str = "", **_ignore
) -> dict:
    """종목/지수 하나의 최근 시세를 가져와 카드에 필요한 형태로 정리합니다."""
    end = dt.date.today()
    start = end - dt.timedelta(days=lookback * 3)  # 주말·공휴일 감안 여유있게 조회
    df = fdr.DataReader(ticker, start, end)
    if df.empty or len(df) < 2:
        raise ValueError(f"{ticker}: 시세 데이터를 가져오지 못했습니다.")

    df = df.tail(lookback + 1)
    closes = df["Close"].tolist()
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
    }


def fetch_all() -> dict:
    """설정 파일에 등록된 모든 지수/종목의 시세를 가져옵니다."""
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    macro = {row["ticker"]: _fetch_one(**row) for row in config["macro"]}
    watchlist = {row["ticker"]: _fetch_one(**row) for row in config["watchlist"]}
    fetch_foreign_flows.attach_foreign_flows(watchlist)
    return {"macro": macro, "watchlist": watchlist}


if __name__ == "__main__":
    print(json.dumps(fetch_all(), ensure_ascii=False, indent=2))
