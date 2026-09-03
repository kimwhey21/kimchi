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

from src import fetch_movers

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "watchlist_us.yaml"

_NAN_RETRY_ATTEMPTS = 3
_NAN_RETRY_DELAY_SECONDS = 5


def _fetch_one(ticker: str, name: str, name_en: str = "", lookback: int = 7, is_yield: bool = False,
                unit: str = "", **_ignore) -> dict:
    """종목/지수 하나의 최근 시세를 가져와 카드에 필요한 형태로 정리합니다."""
    closes: list[float] | None = None
    ticker_client = yf.Ticker(ticker)
    try:
        quote_metadata = ticker_client.get_history_metadata()
    except Exception:  # noqa: BLE001 - 메타데이터 실패 시 일봉으로 폴백
        quote_metadata = {}
    for attempt in range(1, _NAN_RETRY_ATTEMPTS + 1):
        hist = ticker_client.history(period=f"{lookback + 2}d")
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
            time.sleep(_NAN_RETRY_DELAY_SECONDS)

    if closes is None:
        raise ValueError(
            f"{ticker}: 유효한 종가를 2개 이상 가져오지 못했습니다 "
            f"({_NAN_RETRY_ATTEMPTS}번 재시도 후에도)."
        )

    # Yahoo Finance는 현재 ^TNX/^TYX를 이미 실제 금리(예: 4.758%)로 돌려줍니다.
    # 과거처럼 10으로 나누면 4.758%가 0.48%로 잘못 표시됩니다.

    historical_prev, last_close = closes[-2], closes[-1]
    prev_close = historical_prev

    # Yahoo 일봉 이력에는 드물게 직전 거래일 한 줄이 빠집니다. 2026-08-31에는
    # 주요 지수와 DE의 8/28 값이 누락돼 8/27 대비 등락률이 계산됐습니다.
    # 메타데이터의 previousClose는 이 경우에도 실제 직전 종가를 제공하므로,
    # regularMarketPrice가 마지막 일봉과 일치할 때 우선 사용합니다.
    try:
        metadata_last = float(quote_metadata.get("regularMarketPrice"))
        metadata_prev = float(quote_metadata.get("previousClose"))
        tolerance = max(0.02, abs(last_close) * 0.001)
        if (
            math.isfinite(metadata_last)
            and math.isfinite(metadata_prev)
            and metadata_prev != 0
            and abs(metadata_last - last_close) <= tolerance
        ):
            prev_close = metadata_prev
    except (TypeError, ValueError, KeyError):
        # 메타데이터가 없는 종목은 기존 일봉 계산으로 안전하게 폴백합니다.
        pass

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
    watchlist = {
        row["ticker"]: {**_fetch_one(**row), "source": "core"}
        for row in config["watchlist"]
    }
    trading_date = next(iter(macro.values()))["trading_date"]
    watchlist.update(_fetch_dynamic_tier(config, watchlist, trading_date))
    return {"macro": macro, "watchlist": watchlist, "trading_date": trading_date}


def _fetch_dynamic_tier(
    config: dict, core: dict[str, dict], trading_date: str
) -> dict[str, dict]:
    """그날 거래대금 상위 종목을 코어 워치리스트 뒤에 붙입니다.

    한국장(fetch_kr._fetch_dynamic_tier)과 같은 구조입니다. 코어와 달리 종목
    하나가 실패해도 그 종목만 빼고 진행하고, 기준일이 코어와 다른 종목도
    버립니다 — 이름도 모르는 종목 하나 때문에 그날 발행이 멈추면 안 됩니다.
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
    except Exception as exc:
        print(f"[경고] 거래대금 상위 종목을 가져오지 못해 코어 워치리스트로만 진행합니다: {exc}")
        return {}

    added: dict[str, dict] = {}
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
        except Exception as exc:
            print(f"[안내] 동적 편입 제외 — {name_en}({ticker}) 시세 조회 실패: {exc}")
            continue
        if entry.get("trading_date") != trading_date:
            print(
                f"[안내] 동적 편입 제외 — {name_en}({ticker}) 기준일 "
                f"{entry.get('trading_date')}이 코어({trading_date})와 다릅니다."
            )
            continue
        added[ticker] = {
            **entry,
            "source": "dynamic",
            "trading_value": mover["trading_value"],
            "sector": mover["sector"],
        }

    if added:
        names = ", ".join(entry["name"] for entry in added.values())
        print(f"[안내] 그날 거래대금 상위로 편입: {names}")
    return added


if __name__ == "__main__":
    print(json.dumps(fetch_all(), ensure_ascii=False, indent=2))
