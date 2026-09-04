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
import requests
import yaml

from src import fetch_foreign_flows, fetch_movers

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "watchlist_kr.yaml"

_NAN_RETRY_ATTEMPTS = 3
_NAN_RETRY_DELAY_SECONDS = 5
_NAVER_TIMEOUT_SECONDS = 10
_NAVER_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
_NAVER_INDEX_CODES = {"KS11": "KOSPI", "KQ11": "KOSDAQ"}
_NAVER_INDEX_URL = "https://polling.finance.naver.com/api/realtime"
_NAVER_USDKRW_URL = "https://api.stock.naver.com/marketindex/exchange/FX_USDKRW"
_NAVER_USDKRW_PRICES_URL = f"{_NAVER_USDKRW_URL}/prices"


def _fetch_naver_index_quotes() -> dict[str, dict]:
    """16시 직후에도 확정된 코스피·코스닥 종가만 가져옵니다.

    FinanceDataReader 일봉은 거래일 날짜를 먼저 만들고 장중 값이 한동안 남을
    수 있습니다. 네이버 실시간 지수 응답의 ``ms=CLOSE``를 함께 확인해야
    장중 스냅숏을 종가로 잘못 발행하지 않을 수 있습니다.
    """
    response = requests.get(
        _NAVER_INDEX_URL,
        params={"query": "SERVICE_INDEX:KOSPI,KOSDAQ"},
        headers=_NAVER_HEADERS,
        timeout=_NAVER_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    areas = (payload.get("result") or {}).get("areas") or []
    datas = next(
        (area.get("datas") or [] for area in areas if area.get("name") == "SERVICE_INDEX"),
        [],
    )
    return {item.get("cd"): item for item in datas if item.get("cd")}


def _apply_final_index_quote(entry: dict, ticker: str, quote: dict | None) -> dict:
    """오늘 거래일 행을 네이버의 장마감 확정값으로 교체합니다."""
    if entry.get("trading_date") != dt.date.today().isoformat():
        return entry
    code = _NAVER_INDEX_CODES[ticker]
    if not quote or quote.get("ms") != "CLOSE":
        raise ValueError(f"{code}: 장마감 확정 지수(ms=CLOSE)를 아직 확인하지 못했습니다.")

    price = round(float(quote["nv"]) / 100, 2)
    series = list(entry.get("series") or [])
    if series:
        series[-1] = price
    return {
        **entry,
        "price": price,
        "change_pct": round(float(quote["cr"]), 2),
        "series": series,
        "data_source": "Naver Finance realtime index",
    }


def _fetch_usdkrw_reference(
    ticker: str, name: str, name_en: str = "", lookback: int = 7, unit: str = "", **_ignore
) -> dict:
    """원/달러는 하나은행의 최신 고시환율과 기준시각을 명시해 가져옵니다.

    서울 외환시장 종가와 은행 고시환율은 서로 다른 값입니다. 16시 자동 글에서
    Yahoo의 진행 중 환율을 '종가'로 쓰지 않도록, 구조화된 네이버 금융 응답의
    ``priceDataType=NOTICE_ROUND``만 참고환율로 사용합니다.
    """
    detail_response = requests.get(
        _NAVER_USDKRW_URL,
        headers=_NAVER_HEADERS,
        timeout=_NAVER_TIMEOUT_SECONDS,
    )
    detail_response.raise_for_status()
    detail = (detail_response.json().get("exchangeInfo") or {})
    if detail.get("priceDataType") != "NOTICE_ROUND":
        raise ValueError("USD/KRW: 하나은행 고시환율 응답 형식을 확인하지 못했습니다.")

    prices_response = requests.get(
        _NAVER_USDKRW_PRICES_URL,
        params={"page": 1, "pageSize": lookback + 1},
        headers=_NAVER_HEADERS,
        timeout=_NAVER_TIMEOUT_SECONDS,
    )
    prices_response.raise_for_status()
    rows = prices_response.json()
    if len(rows) < 2:
        raise ValueError("USD/KRW: 최근 고시환율을 2개 이상 가져오지 못했습니다.")

    traded_at = dt.datetime.fromisoformat(detail["localTradedAt"])
    series = [
        float(row["closePrice"].replace(",", ""))
        for row in reversed(rows[: lookback + 1])
    ]
    price = float(detail["closePrice"].replace(",", ""))
    # 상세 응답이 일별 목록보다 몇 초 더 최신일 수 있으므로 마지막 값은 상세
    # 응답으로 맞춥니다.
    series[-1] = price
    reference_ko = f"{traded_at:%Y-%m-%d %H:%M} 하나은행 고시"
    reference_en = f"{traded_at:%Y-%m-%d %H:%M} Hana Bank notice"
    return {
        "ticker": ticker,
        "name": name,
        "name_en": name_en or name,
        "price": round(price, 2),
        "change_pct": round(float(detail["fluctuationsRatio"]), 2),
        "series": [round(value, 4) for value in series],
        "unit": unit,
        "trading_date": traded_at.date().isoformat(),
        "quote_type": "reference_rate",
        # 카드에는 짧은 표기를, 본문에는 날짜까지 포함한 전체 표기를 씁니다.
        "as_of_label": f"{traded_at:%H:%M} 하나은행 고시",
        "as_of_label_en": f"{traded_at:%H:%M} Hana Bank",
        "reference_label": reference_ko,
        "reference_label_en": reference_en,
        "data_source": "Naver Finance / Hana Bank notice rate",
    }


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
    index_quotes = _fetch_naver_index_quotes()
    macro: dict[str, dict] = {}
    for row in config["macro"]:
        ticker = row["ticker"]
        if ticker == "USD/KRW":
            macro[ticker] = _fetch_usdkrw_reference(**row)
            continue
        entry = _fetch_one(**row)
        if ticker in _NAVER_INDEX_CODES:
            entry = _apply_final_index_quote(
                entry, ticker, index_quotes.get(_NAVER_INDEX_CODES[ticker])
            )
        macro[ticker] = entry
    # sector는 _fetch_one이 쓰지 않지만 원고와 업종 그래픽에서 필요하므로
    # 설정에서 그대로 실어 나릅니다.
    watchlist = {
        row["ticker"]: {
            **_fetch_one(**row),
            "source": "core",
            **({"sector": row["sector"]} if row.get("sector") else {}),
        }
        for row in config["watchlist"]
    }
    trading_date = next(iter(macro.values()))["trading_date"]
    watchlist.update(_fetch_dynamic_tier(config, watchlist, trading_date))
    fetch_foreign_flows.attach_foreign_flows(watchlist)
    return {"macro": macro, "watchlist": watchlist, "trading_date": trading_date}


def _fetch_dynamic_tier(
    config: dict, core: dict[str, dict], trading_date: str
) -> dict[str, dict]:
    """그날 거래대금 상위 종목을 코어 워치리스트 뒤에 붙입니다.

    코어와 달리 여기서는 종목 하나가 실패해도 그 종목만 빼고 진행합니다.
    이름도 모르는 종목 하나 때문에 그날 발행 전체가 멈추면 안 되기 때문입니다.
    같은 이유로 기준일이 코어와 다른 종목(거래정지·데이터 지연 등)도 버립니다 —
    data_quality.validate_trading_dates가 기준일이 섞인 걸 발행 중단 사유로
    보기 때문에, 여기서 걸러야 코어만으로라도 글이 나갑니다.
    """
    settings = config.get("dynamic") or {}
    if not settings.get("enabled"):
        return {}

    name_en_map = config.get("name_en_map") or {}
    try:
        movers = fetch_movers.fetch_top_turnover(
            exclude_tickers=set(core),
            count=settings.get("count", 6),
            universe_size=settings.get("universe_size", 100),
            min_market_cap=settings.get("min_market_cap", 1_000_000_000_000),
            markets=tuple(settings.get("markets") or ("KOSPI", "KOSDAQ")),
        )
    except Exception as exc:
        print(f"[경고] 거래대금 상위 종목을 가져오지 못해 코어 워치리스트로만 진행합니다: {exc}")
        return {}

    added: dict[str, dict] = {}
    for mover in movers:
        ticker, name = mover["ticker"], mover["name"]
        name_en = name_en_map.get(name)
        if not name_en:
            print(
                f"[안내] '{name}'의 영어 표기가 config/watchlist_kr.yaml의 "
                "name_en_map에 없어 영어판에도 한글 이름이 나갑니다."
            )
        try:
            entry = _fetch_one(ticker=ticker, name=name, name_en=name_en or name)
        except Exception as exc:
            print(f"[안내] 동적 편입 제외 — {name}({ticker}) 시세 조회 실패: {exc}")
            continue
        if entry.get("trading_date") != trading_date:
            print(
                f"[안내] 동적 편입 제외 — {name}({ticker}) 기준일 {entry.get('trading_date')}"
                f"이 코어({trading_date})와 다릅니다."
            )
            continue
        added[ticker] = {
            **entry,
            "source": "dynamic",
            "trading_value": mover["trading_value"],
        }

    if added:
        names = ", ".join(entry["name"] for entry in added.values())
        print(f"[안내] 그날 거래대금 상위로 편입: {names}")
    return added


if __name__ == "__main__":
    print(json.dumps(fetch_all(), ensure_ascii=False, indent=2))
