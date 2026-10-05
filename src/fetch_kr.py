"""한국 시장 시세 수집 스크립트.

코스피·코스닥은 네이버 지수 일별 목록과 실시간 확정값, 환율은 하나은행 고시, 관심 종목은
FinanceDataReader(네이버 일봉)와 KRX 정규장 확정 종가로 종가·등락률·최근 종가 흐름을 가져옵니다.

주의:
    이 스크립트는 KRX/네이버 등 데이터 소스에 접속해야 동작합니다.
    외부 인터넷 접속이 막힌 환경(일부 샌드박스 등)에서는 실행되지 않으니,
    실제로는 여러분의 컴퓨터나 GitHub Actions처럼 접속이 자유로운 곳에서 돌리세요.
"""
from __future__ import annotations

import re

import datetime as dt
import json
import math
import os
import time
from pathlib import Path

import FinanceDataReader as fdr
import requests
import yaml

from src import fetch_foreign_flows, price_history, fetch_movers

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "watchlist_kr.yaml"

# 결측값(NaN) 재시도. 전에는 5초 간격 3회, 즉 재시도 창이 총 15초뿐이었습니다.
# 그런데 실제로 관측된 지연은 분 단위입니다 — 2026-08-31~09-01에 정각 실행이
# USD/KRW 결측으로 3회 연속 죽었고, **7분 뒤** 수동 실행은 성공했습니다.
# 15초 창으로는 애초에 닿지 않는 지연이었습니다. 지수 백오프로 창을 4분으로
# 넓힙니다(10 + 30 + 60 + 120초).
_NAN_RETRY_DELAYS = (10, 30, 60, 120)
_NAN_RETRY_ATTEMPTS = len(_NAN_RETRY_DELAYS) + 1
_NAVER_TIMEOUT_SECONDS = 10
_NAVER_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
_NAVER_INDEX_CODES = {"KS11": "KOSPI", "KQ11": "KOSDAQ"}
_NAVER_INDEX_URL = "https://polling.finance.naver.com/api/realtime"
_NAVER_USDKRW_URL = "https://api.stock.naver.com/marketindex/exchange/FX_USDKRW"
_NAVER_USDKRW_PRICES_URL = f"{_NAVER_USDKRW_URL}/prices"


# 거래일을 읽는 지수. 2026-10-05부터는 환율까지 설정의 모든 항목을 빼지 않는다(받지 못하면 다시 묻고, 그래도 안 되면 멈춘다).
# 2026-09-01에 원/달러 결측(그때는 FinanceDataReader)으로 하루를 잃은 뒤 환율을 빼고 진행하게 했었다 — 지금 원천은 하나은행
# 고시(네이버)이고 세 번 다시 묻는다.
_REQUIRED = {"KS11", "KQ11"}




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



def _fetch_naver_item_quotes(codes: list[str]) -> dict[str, dict]:
    """종목의 **KRX 정규장 확정 종가**를 네이버 실시간 폴링에서 받습니다(2026-09-25).

    왜 필요한가: FinanceDataReader(네이버 fchart) 일봉의 오늘 행은 15:30 이후에도 NXT 애프터마켓(~20:00)을 따라
    계속 움직입니다. 16:20~16:40에 세 번 수집한 9/23 파일은 27종목 중 14종목이 서로 달랐고, 발행된 등락률은
    KRX 기준(삼성전자 3.62%)도 NXT 확정 기준(3.24%)도 아닌 제3의 값(2.70%)이었습니다. 폴링 응답의 ``nv``는
    15:30~16:00에는 정규장 종가로 멈춰 있지만 **16:00부터 KRX 시간외 단일가를 따라 다시 움직이고**, 넥스트레이드 애프터마켓
    때문에 ``ms``는 20:00까지 OPEN입니다(2026-09-28 확인) — 그래서 그 창에 찍어 둔 사진(_krx_close_snapshot)을 먼저 씁니다.
    ``pcv``는 KRX 전일 종가, ``sv``는 그날 기준가(배당락·권리락 날만 pcv와 다르다), ``cr``은 언론·HTS가 쓰는 그 등락률(기준가 대비)입니다.
    한 요청에 여러 종목을 묶어 보냅니다.
    """
    quotes: dict[str, dict] = {}
    for i in range(0, len(codes), 20):
        chunk = [str(c) for c in codes[i:i + 20]]
        response = requests.get(_NAVER_INDEX_URL, params={"query": "SERVICE_ITEM:" + ",".join(chunk)},
                                headers=_NAVER_HEADERS, timeout=_NAVER_TIMEOUT_SECONDS)
        response.raise_for_status()
        areas = (response.json().get("result") or {}).get("areas") or []
        for area in areas:
            for item in area.get("datas") or []:
                if item.get("cd"):
                    quotes[str(item["cd"])] = item
    return quotes


_DAUM = "https://finance.daum.net/api"
_DAUM_RETRY_DELAYS = (3, 10, 30)
KST = dt.timezone(dt.timedelta(hours=9))
_PRICE_LIMIT = 0.30   # 거래소 가격제한폭 ±30% — 이보다 크게 움직였다면 종목 코드나 응답이 어긋난 것이다


_daum_down: list[str] = []   # 이번 실행에서 다음이 재시도 끝에 실패했으면 이유를 담는다 — 그 뒤로는 묻지 않는다(종목마다 43초씩 기다리지 않게)


def _daum_get(path: str, code: str, params: dict | None = None) -> dict:
    """다음 금융 API(비공식). Referer가 없으면 막힌다. 실패하면 세 번(3·10·30초 뒤) 더 묻고, 그래도 안 되면 예외."""
    if _daum_down:
        raise ValueError(f"{code}: 이번 실행에서 다음 금융이 이미 실패했습니다 — {_daum_down[0]}")
    headers = {**_NAVER_HEADERS, "Referer": f"https://finance.daum.net/quotes/A{code}"}
    for attempt, delay in enumerate((0,) + _DAUM_RETRY_DELAYS):
        if delay:
            time.sleep(delay)
        try:
            response = requests.get(f"{_DAUM}/{path}", params=params, headers=headers, timeout=_NAVER_TIMEOUT_SECONDS)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last = exc
            print(f"[안내] 다음 {path} 재시도 {attempt + 1}/{len(_DAUM_RETRY_DELAYS) + 1}: {exc}")
    _daum_down.append(f"{path}: {last}")
    raise ValueError(f"{code}: 다음 금융 {path}를 받지 못했습니다 — {last}")


def _fetch_daum_days(code: str, rows: int = price_history.DAYS) -> list[tuple[str, float]]:
    """다음 일별 시세 — **KRX 정규장 종가**(넥스트레이드·시간외 제외), 오래된 것부터.

    2026-10-05 대조: 9/30·10/1·10/2 사진 205종목 600건이 종가·등락률·기준가 모두 같았다(기준가가 바뀐 10/2 삼성바이오로직스
    포함). 네이버 일봉(FinanceDataReader)·모바일 일별 목록·basic은 KRX+넥스트레이드 통합값이라 같은 600건 중 486건이 달랐다.
    """
    body = _daum_get(f"quote/A{code}/days", code, {"symbolCode": f"A{code}", "page": 1, "perPage": rows, "pagination": "true"})
    out = {str(r["date"])[:10]: float(r["tradePrice"]) for r in body.get("data") or [] if r.get("date") and r.get("tradePrice")}
    return sorted(out.items())


def _fetch_daum_quote(code: str) -> dict:
    """다음 현재가 — `regularTradePrice`(정규장 종가)와 `basePrice`(거래소 기준가). 16:00 이후·넥스트레이드 중에도 정규장 값이 따로 있다."""
    body = _daum_get(f"quotes/A{code}", code, {"summary": "false", "changeStatistics": "true"})
    close, base = body.get("regularTradePrice"), body.get("basePrice")
    return {"date": str(body.get("date") or "")[:10], "close": float(close) if close else None,
            "base": float(base) if base else None}


def _fetch_stock(ticker: str, name: str, name_en: str = "", lookback: int = 7, unit: str = "", **_ignore) -> dict:
    """종목 하나의 최근 KRX 정규장 종가 이력(다음 일별 시세 70거래일, 2026-10-05).

    전에는 FinanceDataReader(네이버 일봉, 넥스트레이드 합산)라 이력의 앞 행들이 KRX 값이 아니었다(주간 통계에 ±0.3%p 섞임).
    오늘 행은 `_apply_krx_closes`가 두 원천으로 확인한 값으로 바꾸거나 덧붙인다.
    """
    try:
        rows = _fetch_daum_days(str(ticker))
        if len(rows) < 2:
            raise ValueError(f"{ticker}: 다음 일별 시세를 {len(rows)}개만 받았습니다.")
    except ValueError as exc:
        # 다음이 막힌 날에도 종목을 빼지 않는다 — 이력만 FinanceDataReader(통합값)로 받고 그렇다고 적는다. 오늘 값은 여전히
        # `_apply_krx_closes`가 KRX 사진으로 확인하고, close_check가 이 표시를 운영 대화로 알린다.
        print(f"[경고] {ticker}: 다음 일별 시세를 못 받아 이력을 FinanceDataReader(KRX+넥스트레이드 통합)로 받습니다 — {exc}")
        return {**_fetch_one(ticker=ticker, name=name, name_en=name_en, lookback=lookback, unit=unit),
                "history_source": "FinanceDataReader (KRX+NXT combined; Daum unavailable)"}
    closes = [c for _, c in rows]
    return {
        "ticker": ticker,
        "name": name,
        "name_en": name_en or name,
        "price": round(closes[-1], 2),
        "change_pct": round((closes[-1] / closes[-2] - 1) * 100, 2),
        "series": [round(c, 4) for c in closes[-(lookback + 1):]],
        "history": {"dates": [d for d, _ in rows], "close": [round(c, 4) for c in closes]},
        "unit": unit,
        "trading_date": rows[-1][0],
    }


def yahoo_close(code: str, day: str) -> float | None:
    """세 번째 원천(2026-10-05): 야후 일별 종가. KRX 정규장 값이다 — 10/2 무작위 300종목 중 거래가 있던 296개가 다음과 모두 같았고
    (네이버 통합값과는 달랐다), 다른 셋은 거래정지 종목이라 거래량 0인 날은 쓰지 않는다. 두 원천이 다를 때만 묻는다. 못 받으면 None."""
    import yfinance as yf
    start = dt.date.fromisoformat(day)
    for suffix in (".KS", ".KQ"):
        try:
            hist = yf.Ticker(code + suffix).history(start=day, end=(start + dt.timedelta(days=1)).isoformat(), auto_adjust=False)
        except Exception as exc:  # noqa: BLE001 — 센다: 다른 시장 접미사를 묻고, 끝내 없으면 None(부른 쪽이 멈춘다)
            print(f"[안내] 야후 {code}{suffix}: {exc}")
            continue
        rows = hist[hist.index.strftime("%Y-%m-%d") == day] if len(hist) else hist
        if len(rows) and float(rows["Volume"].iloc[0] or 0) > 0:
            return float(rows["Close"].iloc[0])
    return None


def pick_base(close: float, bases: dict[str, float], prev_close: float | None = None, rate: float | None = None) -> str | None:
    """기준가가 원천마다 다를 때 맞는 쪽 — 다음 `basePrice`는 거래소 기준가다(배당락·액면병합 날엔 전일 종가와 다르다).
    1) 다른 쪽이 전일 종가 그대로면(네이버 `sv`가 없어 `pcv`를 쓴 경우) 다음이 맞다. 2) 네이버가 준 등락률(`cr`, 기준가로 계산된
    값)과 맞는 쪽이 하나뿐이면 그쪽. 셋째 근거가 없으면 None."""
    if len(set(bases.values())) == 1:
        return next(iter(bases))
    others = [k for k in bases if k != "daum"]
    if "daum" in bases and prev_close is not None and all(abs(bases[k] - prev_close) < 0.5 for k in others):
        return "daum"
    if rate is not None:
        fit = [k for k, b in bases.items() if abs(abs(close / b - 1) * 100 - float(rate)) <= 0.05]
        if len(fit) == 1:
            return fit[0]
    return None


def _resolve_krx_close(code: str, today: str, naver: dict | None, daum: dict | None) -> dict:
    """오늘 KRX 정규장 종가를 **서로 다른 두 원천**으로 확인한다(2026-10-05). 빼지 않는다 — 받거나, 못 받으면 멈추고 이유를 말한다.

    - 네이버: 15:31~15:59에 찍은 사진(`nv`, 기준가 `sv`·없으면 `pcv`). 16:00부터 폴링 `nv`는 시간외 단일가를 따라 움직여 쓰지 않는다.
    - 다음: `regularTradePrice`·`basePrice`(날짜가 오늘일 때만).
    둘 다 있으면 종가와 기준가가 같아야 한다 — 다르면 셋째 근거로 가린다(종가는 야후 `yahoo_close`와 같은 쪽, 기준가는 `pick_base`).
    가리지 못하면 멈춘다 — 옛 값이나 한 원천 값으로 내보내지 않는다(2026-10-05 사장님: 데이터가 정확해야 한다). 하나만 있으면 그것을 쓰고(다음 날 아침
    `close_check`가 네이버 '전일'과 한 번 더 대조한다), 둘 다 없으면 멈춘다. 기준가 대비 ±30%를 넘으면 응답이 어긋난 것이라 멈춘다.
    """
    found: dict[str, tuple[float, float]] = {}
    if naver and naver.get("nv"):
        base = float(naver.get("sv") or 0) or float(naver.get("pcv") or 0)
        if base:
            found["naver_snapshot"] = (float(naver["nv"]), base)
    if daum and daum.get("date") == today and daum.get("close") and daum.get("base"):
        found["daum"] = (float(daum["close"]), float(daum["base"]))
    if not found:
        raise ValueError(f"{code}: 오늘({today}) KRX 정규장 종가를 네이버 사진에서도 다음에서도 받지 못했습니다"
                         f"(다음 날짜 {daum.get('date') if daum else '응답 없음'}).")
    values = set(found.values())
    sources = sorted(found)
    if len(values) > 1:
        # 두 원천이 다르다 — 셋째 근거로 맞는 값을 가린다(2026-10-05 사장님: 옛 값이 아니라 정확한 값). 종가는 야후와 같은 쪽,
        # 기준가는 pick_base. 가리지 못하면 아래에서 멈춘다.
        closes = {k: c for k, (c, _) in found.items()}
        winner, third = None, None
        if len(set(closes.values())) == 1:
            winner = next(iter(closes.values()))
        else:
            third = yahoo_close(code, today)
            agree = [k for k, c in closes.items() if third is not None and abs(c - third) < 0.5]
            winner = closes[agree[0]] if agree else None
        if winner is not None:
            right = [k for k, c in closes.items() if abs(c - winner) < 0.5]
            if len(right) == 1:            # 종가가 틀린 원천의 기준가는 믿지 않는다
                pick = right[0]
            else:                          # 종가는 같고 기준가만 다르다
                pick = pick_base(winner, {k: b for k, (_, b) in found.items()},
                                 prev_close=float(naver["pcv"]) if naver and naver.get("pcv") and not naver.get("sv") else None,
                                 rate=naver.get("cr") if naver else None)
            if pick is not None:
                found = {"resolved": (winner, found[pick][1])}
                values = {found["resolved"]}
                sources = sorted(set(k for k, c in closes.items() if abs(c - winner) < 0.5) | ({"yahoo"} if third is not None else set()))
                print(f"[안내] {code}: 두 원천이 달라 셋째 근거로 정했습니다 — 종가 {winner:,.0f}({'·'.join(sources)}), 기준가는 {pick}")
    if len(values) > 1:
        detail = ", ".join(f"{k} 종가 {c:,.0f}·기준가 {b:,.0f}" for k, (c, b) in found.items())
        override = os.environ.get("KR_CLOSE_OVERRIDE", "").strip()
        if override in found:
            # 사장님 승인 경로(2026-10-05): 두 원천이 다른 날 "내보내"라고 하면 지목한 원천 값에 꼬리표를 달아 내보낸다
            # (market_brief.yml 수동 실행의 close_override 입력). 자동 실행에는 이 값이 없다.
            print(f"[경고] {code}: 두 원천이 달라 사장님 승인으로 {override} 값을 씁니다 — {detail}")
            close, base = found[override]
            return {"close": close, "base": base, "sources": [f"{override} (owner override)"]}
        raise ValueError(f"{code}: 두 원천의 KRX 종가가 다르고 야후로도 가리지 못했습니다 — {detail}. 맞는 값을 확인할 때까지 쓰지 않습니다.")
    close, base = next(iter(values))
    if abs(close / base - 1) > _PRICE_LIMIT:
        raise ValueError(f"{code}: 종가 {close:,.0f}가 기준가 {base:,.0f}에서 가격제한폭(±30%) 넘게 벗어났습니다 — 응답이 어긋났습니다.")
    if naver and naver.get("cr") is not None and abs(float(naver.get("nv") or 0) - close) < 0.5 and \
            abs((float(naver.get("sv") or 0) or float(naver.get("pcv") or 0)) - base) < 0.5:
        # 폴링의 cr은 부호가 없다(KB금융 9/23: nv < pcv인데 cr 0.91). 크기만 대조해 응답 형식이 바뀐 것을 잡는다.
        pct = (close - base) / base * 100
        if abs(abs(pct) - float(naver["cr"])) > 0.05:
            raise ValueError(f"{code}: 계산한 등락률 {pct:.2f}%와 네이버 cr {naver['cr']}이 다릅니다 — 응답 형식 확인 필요.")
    return {"close": close, "base": base, "sources": sources}


def _apply_krx_close(entry: dict, resolved: dict, today: str) -> dict:
    """확인한 오늘 종가를 이력 끝에 바꿔 넣거나(다음 일별 시세에 오늘 줄이 있으면) 덧붙인다(아직 없으면)."""
    close, base = resolved["close"], resolved["base"]
    series, history = list(entry.get("series") or []), entry.get("history")
    if str(entry.get("trading_date") or "") == today:
        if series:
            series[-1] = round(close, 4)
        history = price_history.replace_last(history, close)
    else:
        series = (series + [round(close, 4)])[-len(series):] if len(series) >= 2 else series + [round(close, 4)]
        history = price_history.append(history, today, close)
    return {**entry, "price": round(close, 2), "change_pct": round((close - base) / base * 100, 2),
            "prev_close_krx": round(base, 2), "series": series, "history": history, "trading_date": today,
            "close_sources": resolved["sources"],
            "data_source": "KRX regular-session close (" + " + ".join(resolved["sources"]) + ")"}


def _krx_close_snapshot(today: str, data_dir: Path | None = None) -> dict[str, dict]:
    path = (data_dir or Path(__file__).resolve().parent.parent / "data") / "krx_close" / f"{today}.json"
    if not path.exists():
        return {}
    return (json.loads(path.read_text(encoding="utf-8")).get("quotes") or {})


def _apply_krx_closes(watchlist: dict[str, dict], trading_date: str, prev_day: str | None = None) -> dict[str, dict]:
    """워치리스트 전체(코어+편입)의 오늘 값을 KRX 정규장 확정 종가로. **한 종목이라도 확인하지 못하면 멈춘다** — 빼지 않는다(2026-10-05).

    전에는 편입 종목은 조용히 빼고 코어는 80%까지 빠져도 글을 냈다. 데이터가 중요한 사이트에서 빼는 것은 누락이다.
    `prev_day`(지수의 직전 거래일)가 주어지면, 다음 일별 시세가 그보다 더 뒤처진 종목도 멈춘다(빈 날이 생긴다).
    """
    today = dt.date.today().isoformat()
    if trading_date != today:
        return watchlist
    snap = _krx_close_snapshot(today)
    now = dt.datetime.now(KST).time()
    from src.stock_db import close_window
    window = close_window(dt.date.today())     # 수능일은 16:31~16:59 (2026-10-05)
    if window[0] <= now < window[1]:
        # 창 안에서 손으로 돌리면 지금 폴링이 곧 사진이다. 창 밖의 폴링은 시간외 단일가라 쓰지 않는다(2026-09-28).
        live = _fetch_naver_item_quotes([t for t in watchlist if str(t) not in snap])
        snap = {**live, **snap}
    out: dict[str, dict] = {}
    problems: list[str] = []
    for ticker, entry in watchlist.items():
        code = str(ticker)
        try:
            last = str(entry.get("trading_date") or "")
            if prev_day and last < prev_day:
                raise ValueError(f"{code}: 다음 일별 시세가 {last}에 멈춰 있습니다(직전 거래일 {prev_day}).")
            try:
                daum = _fetch_daum_quote(code)
            except ValueError as exc:   # 다음이 막혔으면 사진 하나로 — 사진도 없으면 아래에서 멈춘다
                print(f"[경고] {code}: 다음 현재가를 못 받아 네이버 사진만으로 확인합니다 — {exc}")
                daum = None
            out[ticker] = _apply_krx_close(entry, _resolve_krx_close(code, today, snap.get(code), daum), today)
        except ValueError as exc:
            problems.append(f"{entry.get('name', ticker)}({code}): {exc}")
    if problems:
        raise ValueError(f"KRX 종가를 확인하지 못한 종목 {len(problems)}개 — 빼지 않고 멈춥니다: " + " / ".join(problems))
    return out


DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _latest_committed_index(ticker: str, before: str, data_dir: Path | None = None) -> dict | None:
    """우리가 이미 커밋한 가장 최근 시세 파일(오늘 이전)의 지수 항목.

    2026-09-10: FinanceDataReader의 코스피·코스닥 일봉이 09-07에서 사흘째 멈춰 있었다(개별
    종목은 09-10까지 정상). 하루 지연만 메우던 등식 보정은 전일 종가를 일봉 마지막 행에서
    가져오므로 사흘 공백을 못 메웠고, 워크플로 3회와 예비 루틴이 전부 "기준일 불일치"로
    멈춰 그날 한국장 글이 빠졌다. 그런데 우리 파일에는 09-08·09-09 종가가 이미 있다 —
    그날그날 네이버 확정값으로 덧붙인 것이다. 그러니 일봉이 우리 파일보다 뒤처지면 우리
    파일의 이력을 밑바탕으로 쓰고, 등식은 그 마지막 종가와 맞춘다.
    """
    folder = data_dir or DATA_DIR
    files = sorted(p for p in folder.glob("price_kr_*.json") if p.stem.split("_")[-1] < before)
    for path in reversed(files):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        entry = (doc.get("macro") or {}).get(ticker)
        if entry and entry.get("trading_date") and (entry.get("history") or {}).get("close"):
            return entry
    return None



def _prior_change_pct(prior: dict) -> float | None:
    """우리가 커밋해 둔 파일의 등락률. 없으면 이력의 마지막 두 종가로 계산한다(2026-09-25)."""
    if prior.get("change_pct") is not None:
        return round(float(prior["change_pct"]), 2)
    hist = prior.get("history") or {}
    closes = hist.get("close") or []
    if len(closes) >= 2 and closes[-2]:
        return round((float(closes[-1]) / float(closes[-2]) - 1) * 100, 2)
    return None

_NAVER_INDEX_PAGE = 35   # 한 쪽에 60줄까지 준다(70은 빈 응답, 2026-10-05) — 70거래일은 35줄 두 쪽으로 받는다


def _fetch_naver_index_daily(code: str, rows: int = 10) -> list[tuple[str, float]]:
    """네이버 지수 일별 종가(최근 `rows`거래일, 오래된 것부터). 장 마감 뒤 16:27에는 그날 줄이 이미 있다(2026-09-30 실행 기록)."""
    size = min(rows, _NAVER_INDEX_PAGE)
    out: dict[str, float] = {}
    for page in range(1, -(-rows // size) + 1):
        response = requests.get(f"https://m.stock.naver.com/api/index/{code}/price", params={"pageSize": size, "page": page},
                                headers=_NAVER_HEADERS, timeout=_NAVER_TIMEOUT_SECONDS)
        response.raise_for_status()
        for row in response.json():
            date, close = str(row.get("localTradedAt") or "")[:10], str(row.get("closePrice") or "").replace(",", "")
            if date and close:
                out[date] = float(close)
    return sorted(out.items())


def _fetch_index(ticker: str, name: str, name_en: str = "", lookback: int = 7, unit: str = "", **_ignore) -> dict:
    """코스피·코스닥 — 네이버 지수 일별 종가 70거래일(2026-10-05).

    전에는 FinanceDataReader(KS11/KQ11)였다. 그 지수는 개인 개발자가 깃허브에 쌓아 두는 사본이고, 그 사람의 거래소
    로그인이 실패한 9/17 낮부터 멈춰 있었다(9/17 행은 장중 값 6,724.34 — 확정 종가 6,715.41). 우리 수집은 빈 날을
    네이버 확정값·우리 파일로 메워 글이 계속 나갔고, 실행 기록에 날마다 "일봉이 9/17에 머물러"가 찍혔지만 아무도 몰랐다.
    네이버 목록은 70거래일 전부가 한국은행 ECOS(한국거래소 작성 통계)와 같았다(2026-10-05 대조). 목록에 오늘 줄이 아직
    없거나 목록이 멈춘 날은 `_apply_final_index_quote`가 확정값·우리 파일로 잇고, `close_check`가 다음 날 아침 운영 대화로 알린다.
    목록을 못 받으면 우리가 커밋한 마지막 파일을 밑바탕으로 쓴다(없으면 멈춘다).
    """
    try:
        rows = _fetch_naver_index_daily(_NAVER_INDEX_CODES[ticker], rows=price_history.DAYS)
        if len(rows) < 2:
            raise ValueError(f"일별 종가를 {len(rows)}개만 받았습니다")
    except (requests.RequestException, ValueError) as exc:
        prior = _latest_committed_index(ticker, dt.date.today().isoformat())
        if prior is None:
            raise ValueError(f"{ticker}: 네이버 지수 일별 목록을 받지 못했고 우리 파일도 없습니다 — {exc}") from exc
        print(f"[경고] {ticker}: 네이버 지수 일별 목록을 받지 못해 우리 파일({prior['trading_date']})을 밑바탕으로 씁니다 — {exc}")
        return {**prior, "data_source": "our committed file (Naver index daily list unavailable)"}
    closes = [close for _, close in rows]
    return {
        "ticker": ticker,
        "name": name,
        "name_en": name_en or name,
        "price": round(closes[-1], 2),
        "change_pct": round((closes[-1] / closes[-2] - 1) * 100, 2),
        "series": [round(c, 4) for c in closes[-(lookback + 1):]],
        "history": {"dates": [d for d, _ in rows], "close": [round(c, 4) for c in closes]},
        "unit": unit,
        "trading_date": rows[-1][0],
        "data_source": "Naver Finance index daily list",
    }


def last_closed_trading_day(today: str | None = None) -> str:
    """장이 끝난 마지막 거래일(코스피 기준) — 발행 점검(`check_publication`)이 쓴다(2026-10-05, 전에는 멈춘 FinanceDataReader).

    목록에서 오늘 이전의 마지막 날을 고른다. 지수가 장마감(``ms=CLOSE``)이고 목록에 오늘 줄이 있거나 확정 종가가 그 마지막
    날 종가와 다르면 오늘도 거래일이다(목록이 늦게 올라오는 날). 휴장일에는 확정값이 마지막 거래일 종가 그대로다(10/5 확인).
    """
    today = today or dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
    rows = _fetch_naver_index_daily("KOSPI")
    quote = _fetch_naver_index_quotes().get("KOSPI") or {}
    closes = dict(rows)
    before = [d for d, _ in rows if d < today]
    if not before:
        raise ValueError(f"네이버 코스피 일별 목록에 {today} 이전 날짜가 없습니다")
    if quote.get("ms") == "CLOSE" and (today in closes or abs(float(quote["nv"]) / 100 - closes[before[-1]]) > 0.005):
        return today
    return before[-1]


def _fill_gap_from_naver_daily(entry: dict, code: str, today: str, price: float, change: float,
                               daily: list[tuple[str, float]]) -> dict | None:
    """일봉·우리 파일이 오늘보다 이틀 이상 비었을 때(2026-09-30: 9/28·9/29를 건너뛰어 마지막이 9/23) 네이버 일별 목록으로 채운다.

    조건은 기존 등식과 같다 — 목록의 **직전 거래일 종가 + 오늘 등락폭 = 오늘 확정 종가**. 목록의 오늘 줄도 확정값과 같아야 한다.
    휴장일에는 목록에 오늘 줄이 없어 성립하지 않는다. 맞으면 마지막 날 뒤의 빈 날과 오늘을 이력에 덧붙인다.
    """
    last = str(entry.get("trading_date") or "")
    by_date = dict(daily)
    if abs(by_date.get(today, -1) - price) > 0.02:
        return None
    before = [d for d, _ in daily if d < today]
    if not before or abs(round(by_date[before[-1]] + change, 2) - price) > 0.02:
        return None
    missing = [d for d in before if d > last]
    history, series = entry.get("history"), list(entry.get("series") or [])
    for d in missing + [today]:
        history = price_history.append(history, d, by_date[d])
        series = (series + [by_date[d]])[-len(series):] if len(series) >= 2 else series + [by_date[d]]
    print(f"[안내] {code}: 일봉·우리 파일이 {last}에 멈춰 있어 네이버 일별 종가로 {', '.join(missing) or '없음'}를 채우고 "
          f"오늘({today}) {price:,.2f}를 덧붙입니다.")
    return {**entry, "price": price, "series": series, "history": history, "trading_date": today,
            "data_source": "Naver Finance realtime index + daily list (gap filled)"}


def _apply_final_index_quote(entry: dict, ticker: str, quote: dict | None,
                             prior: dict | None = None) -> dict:
    """오늘 거래일 행을 네이버의 장마감 확정값으로 교체하거나, 아직 없으면 덧붙입니다.

    두 경우가 있습니다.

    1. 일봉에 오늘 행이 **있다** — 장중 값이 남아 있을 수 있으니 확정 종가로 교체.
       확정(``ms=CLOSE``)이 아니면 예외로 멈춥니다(장중 스냅숏을 종가로 내지 않음).
    2. 일봉에 오늘 행이 **아직 없다** — 지수 일봉(KRX 집계)은 개별 종목(네이버)보다
       늦게 나옵니다. 2026-09-08에는 18:30 KST까지도 코스피·코스닥이 전날(09-07)에
       머물러 종목(09-08)과 기준일이 어긋났고, 16:29·16:37·16:41 워크플로와 17:40
       예비 루틴이 전부 같은 자리에서 멈춰 그날 한국장 글이 나가지 않았습니다.
       그날 네이버 실시간 응답은 이미 ``ms=CLOSE``였습니다(6,954.52 / -0.58%).

       덧붙이는 조건은 **전일 종가(일봉 마지막 행) + 등락폭(cv) = 확정 종가(nv)**가
       정확히 맞아떨어질 때뿐입니다. 이 등식이 맞으면 네이버의 확정값이 일봉
       마지막 행의 *다음* 거래일 종가라는 뜻입니다. 휴장일에는 성립하지 않습니다 —
       일봉 마지막 행이 곧 네이버의 확정 종가라 등락폭을 더하면 어긋납니다. 그래서
       주말·공휴일에 가짜 행이 생기지 않습니다. 등식이 안 맞으면 손대지 않고
       그대로 돌려줍니다(그러면 기존대로 기준일 불일치로 멈춥니다).
    """
    today = dt.date.today().isoformat()
    last = str(entry.get("trading_date") or "")
    code = _NAVER_INDEX_CODES[ticker]
    if prior and str(prior.get("trading_date") or "") > last and str(prior["trading_date"]) < today:
        # 일봉이 우리가 이미 커밋한 파일보다 뒤처졌다(2026-09-10, 사흘). 우리 파일의
        # 이력·종가를 밑바탕으로 쓰고 아래 등식은 그 마지막 종가와 맞춘다.
        print(f"[안내] {code}: 일봉이 {last}에 머물러 있어 우리 파일({prior['trading_date']})의 이력을 밑바탕으로 씁니다.")
        # 등락률·출처도 함께 옮긴다(2026-09-25). 그전에는 price·이력만 옮기고 change_pct는 FDR 옛 행 값이 남아
        # 휴장일 재수집(9/24)이 9/23 파일의 코스피 등락률을 0.90→0.09, 코스닥을 1.21→0.70으로 망가뜨렸고, 9/24 프리뷰에
        # "0.09% 오른 7,080.9"가 실제로 나갔다. prior에 change_pct가 없으면 이력의 마지막 두 종가로 계산한다.
        entry = {**entry, "price": float(prior["price"]), "series": list(prior.get("series") or entry.get("series") or []),
                 "history": prior.get("history"), "trading_date": str(prior["trading_date"]),
                 "change_pct": _prior_change_pct(prior),
                 "data_source": prior.get("data_source") or f"{entry.get('data_source') or 'FinanceDataReader'} (이력은 우리 파일)"}
        last = str(prior["trading_date"])
    if last == today:
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
            "history": price_history.replace_last(entry.get("history"), price),
            "data_source": "Naver Finance realtime index",
        }

    if not last or last > today or not quote or quote.get("ms") != "CLOSE":
        return entry
    price = round(float(quote["nv"]) / 100, 2)
    change = float(quote.get("cv") or 0) / 100
    prev_close = float(entry["price"])
    # 전일 종가의 기준은 둘이다 — 일봉 마지막 행, 그리고 우리가 어제 커밋한 파일의 종가(2026-09-18).
    # 일봉(KRX 집계)의 9/17 코스피 종가는 6,724.34였는데 우리 9/17 파일은 네이버 확정값 6,715.41이었다
    # (그날도 일봉이 늦어 네이버 값으로 덧붙였다). 네이버의 등락폭은 자기 기준(6,715.41)에서 잰 것이라
    # 일봉 기준으로는 등식이 영원히 안 맞았고, 16:27·16:36·16:39 세 번이 같은 자리에서 멈췄다.
    # 휴장 방어는 그대로다 — 휴장일엔 네이버 확정값이 어제 값이라 어느 기준으로도 등식이 안 맞는다.
    bases = [prev_close]
    if prior and str(prior.get("trading_date") or "") == last and prior.get("price") is not None:
        bases.append(float(prior["price"]))
    matched = next((b for b in bases if change != 0 and abs(round(b + change, 2) - price) <= 0.02), None)
    if matched is None:
        # 등식이 안 맞으면 오늘 장이 없었거나(휴장) 응답이 다른 날 것이거나, 일봉·우리 파일이 며칠 비었습니다(2026-09-30).
        try:
            filled = _fill_gap_from_naver_daily(entry, code, today, price, change, _fetch_naver_index_daily(code))
        except (requests.RequestException, ValueError) as exc:
            print(f"[안내] {code}: 네이버 지수 일별 목록을 받지 못했습니다 — {exc}")
            filled = None
        if filled is None:
            return entry
        return {**filled, "change_pct": round(float(quote["cr"]), 2)}
    if matched != prev_close:
        print(f"[안내] {code}: 일봉의 전일 종가 {prev_close:,.2f}와 우리 파일의 {matched:,.2f}가 달라 "
              "우리 파일(네이버 기준)로 등식을 맞췄습니다.")
    series = list(entry.get("series") or [])
    series = (series + [price])[-len(series):] if len(series) >= 2 else [prev_close, price]
    print(f"[안내] {code}: 일봉에 오늘({today}) 행이 아직 없어 네이버 확정 종가 "
          f"{price:,.2f}({float(quote['cr']):+.2f}%)를 오늘 행으로 덧붙입니다.")
    return {
        **entry,
        "price": price,
        "change_pct": round(float(quote["cr"]), 2),
        "series": series,
        "history": price_history.append(entry.get("history"), today, price),
        "trading_date": today,
        "data_source": "Naver Finance realtime index (daily bar not yet published)",
    }


def _retry(fn, what: str, delays: tuple[int, ...] = (10, 30, 60)):
    """세 번 더(10·30·60초 뒤) 해 보고 그래도 안 되면 마지막 예외를 올린다."""
    for attempt, delay in enumerate((0,) + delays):
        if delay:
            time.sleep(delay)
        try:
            return fn()
        except (requests.RequestException, ValueError, KeyError) as exc:
            last = exc
            print(f"[안내] {what} 재시도 {attempt + 1}/{len(delays) + 1}: {exc}")
    raise last


def _daum_fx() -> tuple[int, dt.datetime, float] | None:
    """다음 금융의 최신 하나은행 고시 (회차, 고시 시각, 매매기준율). 못 받으면 None — 부른 쪽이 네이버 하나로 쓰고 알린다."""
    try:
        body = requests.get(f"{_DAUM}/exchanges/FRX.KRWUSD", timeout=_NAVER_TIMEOUT_SECONDS,
                            headers={**_NAVER_HEADERS, "Referer": "https://finance.daum.net/exchanges/FRX.KRWUSD"}).json()
        return int(body["recurrenceCount"]), dt.datetime.fromisoformat(str(body["date"])).replace(tzinfo=KST), float(body["basePrice"])
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        print(f"[경고] 다음 환율을 받지 못해 원/달러를 네이버 하나로 확인합니다 — {exc}")
        return None


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
    change_pct = round(float(detail["fluctuationsRatio"]), 2)
    # 두 번째 원천(2026-10-05): 다음 금융의 같은 하나은행 고시. 회차가 같으면 값이 같아야 하고, 네이버 상세가 회차가 늦으면
    # (10/5 실측: 상세 2663회 1,345.50 · 네이버 일별 목록과 다음은 2665회 1,346.50) 일별 목록과 다음이 같은 최신 고시를 쓴다.
    # 둘이 같은 값을 못 찾으면 멈춘다(_retry가 다시 묻는다).
    sources = ["naver"]
    daum = _daum_fx()
    if daum:
        d_count, d_when, d_price = daum
        latest_day, latest = rows[0]["localTradedAt"][:10], float(rows[0]["closePrice"].replace(",", ""))
        if str(detail.get("degreeCount")) == str(d_count) and abs(price - d_price) < 0.005:
            sources = ["daum", "naver"]
            traded_at = d_when     # 네이버 localTradedAt은 고시 시각이 아니다(10/5 휴장일에 '15:31'로 왔다; 마지막 고시는 10/2 21:30)
        elif latest_day == d_when.date().isoformat() and abs(latest - d_price) < 0.005 and len(rows) >= 2:
            prev = float(rows[1]["closePrice"].replace(",", ""))
            print(f"[안내] USD/KRW: 네이버 상세({detail.get('degreeCount')}회 {price:,.2f})가 늦어 네이버 일별 목록·다음이 같은 "
                  f"{d_count}회 {d_price:,.2f}를 씁니다")
            price, traded_at, change_pct = d_price, d_when, round((d_price - prev) / prev * 100, 2)
            series[-1] = price
            sources = ["daum", "naver_list"]
        else:
            raise ValueError(f"USD/KRW: 네이버 {detail.get('degreeCount')}회 {price:,.2f}(일별 {latest_day} {latest:,.2f}) / "
                             f"다음 {d_count}회 {d_price:,.2f} — 같은 고시를 두 곳에서 확인하지 못했습니다")
    reference_ko = f"{traded_at:%Y-%m-%d %H:%M} 하나은행 고시"
    reference_en = f"{traded_at:%Y-%m-%d %H:%M} Hana Bank notice"
    return {
        "ticker": ticker,
        "name": name,
        "name_en": name_en or name,
        "price": round(price, 2),
        "change_pct": change_pct,
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
        "close_sources": sources,
    }


def _fetch_one(
    ticker: str, name: str, name_en: str = "", lookback: int = 7, unit: str = "", **_ignore
) -> dict:
    """종목/지수 하나의 최근 시세를 가져와 카드에 필요한 형태로 정리합니다."""
    end = dt.date.today()
    # 최근 3개월 이력(history)까지 한 번에 받습니다 — 본문 기간 차트용(2026-09-08).
    start = end - dt.timedelta(days=price_history.CALENDAR_DAYS)

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
            time.sleep(_NAN_RETRY_DELAYS[attempt - 1])

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
        "history": price_history.from_frame(df),
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
    _daum_down.clear()
    index_quotes = _fetch_naver_index_quotes()
    macro: dict[str, dict] = {}
    missing: list[str] = []
    for row in config["macro"]:
        ticker = row["ticker"]
        try:
            if ticker == "USD/KRW":
                macro[ticker] = _retry(lambda: _fetch_usdkrw_reference(**row), f"{ticker} 하나은행 고시환율")
                continue
            if ticker in _NAVER_INDEX_CODES:
                entry = _apply_final_index_quote(
                    _fetch_index(**row), ticker, index_quotes.get(_NAVER_INDEX_CODES[ticker]),
                    prior=_latest_committed_index(ticker, dt.date.today().isoformat()),
                )
            else:
                entry = _fetch_one(**row)
            macro[ticker] = entry
        except Exception as exc:  # noqa: BLE001 — 센다: 아래에서 모아 멈춘다(2026-10-05부터 환율도 빼지 않는다)
            if ticker in _REQUIRED:
                raise
            missing.append(f"{row.get('name', ticker)}({ticker}): {exc}")
    if missing:
        raise ValueError(f"한국장 지표 {len(missing)}개를 받지 못했습니다 — 빼지 않고 멈춥니다: " + " / ".join(missing))
    # 코어 종목은 하나도 빼지 않는다(2026-10-05). 전에는 80%까지 빠져도 글을 냈다 — 데이터가 중요한 사이트에서 빼는 것은
    # 누락이다. 다음 일별 시세를 세 번 다시 묻고(_daum_get), 그래도 못 받은 종목이 있으면 이름을 모두 적고 멈춘다.
    # 재시도 예약(:27/:34)이 다시 돈다. sector는 원고와 업종 그래픽에서 필요하므로 설정에서 실어 나른다.
    watchlist: dict[str, dict] = {}
    failed: list[str] = []
    for row in config["watchlist"]:
        ticker = row["ticker"]
        try:
            entry = _fetch_stock(**row)
        except Exception as exc:  # noqa: BLE001 — 센다: 아래에서 모두 모아 멈춘다
            failed.append(f"{row.get('name', ticker)}({ticker}): {exc}")
            continue
        watchlist[ticker] = {
            **entry,
            "source": "core",
            **({"sector": row["sector"]} if row.get("sector") else {}),
        }
    if failed:
        raise ValueError(f"코어 종목 {len(failed)}개의 시세를 받지 못했습니다 — 빼지 않고 멈춥니다: " + " / ".join(failed))
    # 거래일은 필수 지수에서 읽습니다. 선택 항목이 빠져도 기준일은 흔들리지
    # 않아야 합니다.
    trading_date = next(macro[t]["trading_date"] for t in _REQUIRED if t in macro)
    index_dates = ((macro.get("KS11") or {}).get("history") or {}).get("dates") or []
    prev_day = next((d for d in reversed(index_dates) if d < trading_date), None)
    watchlist.update(_fetch_dynamic_tier(config, watchlist, trading_date))
    # 오늘 값은 KRX 정규장 확정 종가 — 네이버 사진과 다음, 두 원천이 같아야 쓴다(2026-10-05).
    watchlist = _apply_krx_closes(watchlist, trading_date, prev_day)
    fetch_foreign_flows.attach_foreign_flows(watchlist, trading_date)
    return {"macro": macro, "watchlist": watchlist, "trading_date": trading_date,
            "missing": []}


_YAHOO_SUFFIX = {"KOSPI": ".KS", "KOSDAQ": ".KQ"}
_CORP_TAIL = re.compile(r"[,\s]+(?:co\.?,?\s*ltd\.?|co\.|ltd\.?|corp\.?|corporation|inc\.?|incorporated|plc)$", re.IGNORECASE)
_LATIN_NAME = re.compile(r"[A-Za-z0-9&.,'()\- ]{2,}")


def clean_english_name(raw: str) -> str | None:
    """야후 회사명을 글에 쓸 꼴로 — 법인 꼬리를 떼고, 전부 대문자면 낱말 첫 글자만 크게. 영문이 아니면 None."""
    name = str(raw or "").strip()
    previous = None
    while previous != name:
        previous = name
        name = _CORP_TAIL.sub("", name).strip().rstrip(",").strip()
    if not name or not _LATIN_NAME.fullmatch(name):
        return None
    if name.isupper():
        name = " ".join(w if len(w) <= 3 else w.capitalize() for w in name.split())
    return name


def english_name(ticker: str, market: str | None) -> str | None:
    """동적 편입 종목의 영어 이름 — 야후 회사명(2026-09-26).

    그전에는 `name_en_map`에 없으면 한글 이름이 영어판에 그대로 나갔다(9/17 "Sphere (스피어)", 9/18 가온전선, 9/21
    SFA반도체). 네이버 증권 API에는 종목 영어 이름이 없고, 야후는 **시장 접미어가 맞을 때만** 정확하다 — 347700.KQ는
    Sphere Corp.인데 347700.KS는 다른 회사가 나온다. 그래서 시장을 모르면 찾지 않는다.
    """
    suffix = _YAHOO_SUFFIX.get(str(market or "").upper())
    if not suffix:
        return None
    try:
        import yfinance as yf
        info = yf.Ticker(f"{ticker}{suffix}").info or {}
    except Exception as exc:  # noqa: BLE001 — 한 종목의 이름 조회라 이유를 찍고 한글 이름으로 간다
        print(f"[안내] {ticker}{suffix} 영어 이름 조회 실패: {exc}")
        return None
    return clean_english_name(info.get("longName") or info.get("shortName") or "")


def _fetch_dynamic_tier(
    config: dict, core: dict[str, dict], trading_date: str
) -> dict[str, dict]:
    """그날 거래대금 상위 종목을 코어 워치리스트 뒤에 붙입니다.

    2026-10-05부터 코어와 같다 — 하나라도 못 받으면 빼지 않고 멈춘다(전에는 조용히 뺐다. 그날 거래대금 상위가 빠진
    글은 누락이다). 오늘 값은 `_apply_krx_closes`가 두 원천으로 확인하므로, 다음 일별 시세에 오늘 줄이 아직 없어도
    (기준일이 하루 늦어도) 버리지 않는다. 후보는 krx_close_snapshot이 찍는 시가총액 상위 universe 안에서만 나온다.
    """
    settings = config.get("dynamic") or {}
    if not settings.get("enabled"):
        return {}

    name_en_map = config.get("name_en_map") or {}
    movers = None
    for attempt, delay in enumerate((0, 10, 30)):
        if delay:
            time.sleep(delay)
        try:
            movers = fetch_movers.fetch_top_turnover(
                exclude_tickers=set(core),
                count=settings.get("count", 6),
                universe_size=settings.get("universe_size", 100),
                min_market_cap=settings.get("min_market_cap", 1_000_000_000_000),
                markets=tuple(settings.get("markets") or ("KOSPI", "KOSDAQ")),
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
        ticker, name = mover["ticker"], mover["name"]
        name_en = name_en_map.get(name) or english_name(ticker, mover.get("market"))
        if not name_en:
            print(
                f"[안내] '{name}'의 영어 표기를 name_en_map에서도 야후에서도 찾지 못해 "
                "영어판에 한글 이름이 나갑니다 — config/watchlist_kr.yaml의 name_en_map에 적으십시오."
            )
        try:
            entry = _fetch_stock(ticker=ticker, name=name, name_en=name_en or name)
        except Exception as exc:  # noqa: BLE001 — 센다: 아래에서 모아 멈춘다
            failed.append(f"{name}({ticker}): {exc}")
            continue
        added[ticker] = {
            **entry,
            "source": "dynamic",
            "trading_value": mover["trading_value"],
        }
    if failed:
        raise ValueError(f"편입 종목 {len(failed)}개의 시세를 받지 못했습니다 — 빼지 않고 멈춥니다: " + " / ".join(failed))

    if added:
        names = ", ".join(entry["name"] for entry in added.values())
        print(f"[안내] 그날 거래대금 상위로 편입: {names}")
    return added


if __name__ == "__main__":
    print(json.dumps(fetch_all(), ensure_ascii=False, indent=2))
