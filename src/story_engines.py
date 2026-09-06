"""글감을 만드는 엔진들입니다. 원고를 쓰지 않고 **재료만** 내놓습니다.

왜 필요한가
-----------
2026-09-05에 벤치마크(재테크농부) 100편(8/6~9/5)을 받아 소재별로 세어 보니
우리와 이렇게 달랐습니다.

    증권사 목표주가·투자의견   73%      우리 없음
    실적 캘린더·가이던스      73%      우리 없음
    밸류에이션(FWD PER)      67%      우리 없음
    거시 지표(CPI·고용·금리)   62%      우리 있음  ← 우리가 쓰는 유일한 소재
    기관 수급(13F)           46%      우리 없음
    내부자 자사주 매수         29%      우리 없음

저쪽은 하루 3.3편이 나오고 우리는 1편에서 막혔는데, 원인은 분량이 아니라
**재료가 하나뿐인 것**이었습니다. 저쪽은 매번 새 소재를 찾는 게 아니라 같은
데이터 소스를 같은 틀로 반복해서 돌립니다 — 13F가 나오면 「기관 매매 분석」,
Form 4가 쌓이면 「CEO가 매수한 3개 종목」, 조정이 오면 「FWD PER 8개 비교」.
소스 하나가 시리즈 하나입니다.

무엇을 하지 않는가
------------------
**문장을 만들지 않습니다.** 이 파일은 숫자와 사실만 모아 돌려주고, 그것으로
글을 쓸지 말지는 사람이 정합니다. 규칙 기반 생성물을 그대로 공개하지 않는다는
저장소 원칙(AGENTS.md)이 여기에도 그대로 적용됩니다.

**빈손도 결과입니다.** 그날 내부자 매수가 없으면 없다고 돌려줍니다. 채우려고
기준을 낮추면 "그날 할 말이 약한 것까지 들어간다"는 인사이트 절의 실수를
그대로 반복하게 됩니다.

소스 확인 기록 (2026-09-05 실측)
--------------------------------
    SEC EDGAR Form 4 / 13F     OK  (키 불필요, User-Agent에 연락처만)
    yfinance 등급·목표주가 변경  OK  (MU 880행)
    yfinance FWD PER·목표주가   OK  (한국 종목도 됨: 000660.KS)
    yfinance 실적 캘린더        OK
    DART OpenAPI               키 필요 — 무료 발급 후 DART_API_KEY로
    KRX 공매도(data.krx)       막힘 — 로그인 요구(pykrx가 막힌 것과 같은 벽)

사용법
------
    python -m src.story_engines valuation --market kr
    python -m src.story_engines ratings --market us --days 7
    python -m src.story_engines earnings --market us --days 21
    python -m src.story_engines insiders --days 14
    python -m src.story_engines flows --date 2026-09-04
    python -m src.story_engines seasonality --market kr
    python -m src.story_engines all --market us        # 되는 엔진 전부
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import re
import statistics
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
import yaml

# ETF·선물에는 재무 데이터가 없어 yfinance가 404를 stderr로 찍습니다. 종목별
# 실패는 이미 건너뛰고 있으므로 로그만 조용히 시킵니다.
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

ROOT = Path(__file__).resolve().parent.parent
CONFIG = {"kr": ROOT / "config" / "watchlist_kr.yaml",
          "us": ROOT / "config" / "watchlist_us.yaml"}
DATA = ROOT / "data"

# SEC는 연락처가 없는 요청을 차단합니다. 저장소 소유자 주소를 씁니다.
SEC_UA = {"User-Agent": "market-brief research kimwhey21@gmail.com"}


def core_watchlist(market: str) -> list[dict]:
    """코어(고정) 종목만 돌려줍니다.

    그날 편입된 dynamic 종목은 뺍니다. 이름도 모르는 종목 하나가 발행 전체를
    멈추게 하면 안 된다는 기존 가드와 같은 이유입니다.
    """
    config = yaml.safe_load(CONFIG[market].read_text(encoding="utf-8"))
    entries = []
    for row in config.get("watchlist") or []:
        ticker = row["ticker"]
        # 한국 종목 코드는 야후에서 `.KS`(유가증권)/`.KQ`(코스닥)를 붙여야 합니다.
        yahoo = ticker if market == "us" else None
        entries.append({**row, "yahoo": yahoo})
    return entries


def _kr_yahoo_candidates(code: str) -> list[str]:
    return [f"{code}.KS", f"{code}.KQ"]


def _resolve_yahoo(entry: dict, market: str):
    """야후 티커를 정하고 Ticker 객체를 돌려줍니다. 실패하면 None."""
    import yfinance as yf

    if market == "us":
        return entry["ticker"], yf.Ticker(entry["ticker"])
    for candidate in _kr_yahoo_candidates(entry["ticker"]):
        ticker = yf.Ticker(candidate)
        try:
            info = ticker.info
        except Exception:
            continue
        if info.get("regularMarketPrice") or info.get("currentPrice"):
            return candidate, ticker
    return None, None


# ── 엔진 1. 밸류에이션 비교표 ──────────────────────────────────────────
def valuation(market: str) -> dict:
    """FWD PER과 목표주가 괴리를 한 표로 모읍니다.

    벤치마크의 「저평가 반도체 주식은? 8개 FWD PER 분석」이 이 자리입니다.
    그 글의 결론이 중요합니다 — **낮은 PER이 곧 저평가가 아닙니다.** 사이클
    업종은 이익이 정점일 때 예상 이익이 크게 잡혀 PER이 가장 낮아 보입니다.
    그래서 이 엔진은 판단을 내리지 않고 숫자만 나란히 둡니다.
    """
    rows = []
    for entry in core_watchlist(market):
        symbol, ticker = _resolve_yahoo(entry, market)
        if ticker is None:
            continue
        try:
            info = ticker.info
        except Exception:
            continue
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        target = info.get("targetMeanPrice")
        rows.append({
            "name": entry["name"], "ticker": entry["ticker"], "symbol": symbol,
            "sector": entry.get("sector"),
            "price": price,
            "forward_pe": info.get("forwardPE"),
            "trailing_pe": info.get("trailingPE"),
            "target_mean": target,
            "upside_pct": round(100 * (target / price - 1), 1) if price and target else None,
            "analysts": info.get("numberOfAnalystOpinions"),
            "off_52w_high_pct": round(100 * (price / info["fiftyTwoWeekHigh"] - 1), 1)
            if price and info.get("fiftyTwoWeekHigh") else None,
        })
    # FWD PER이 음수면 내년에 적자가 예상된다는 뜻입니다. 그대로 정렬하면 "가장
    # 싼 종목"으로 맨 위에 올라오므로 따로 뺍니다.
    priced = [r for r in rows if r["forward_pe"] and r["forward_pe"] > 0]
    loss_making = [r for r in rows if r["forward_pe"] and r["forward_pe"] < 0]
    return {
        "engine": "valuation", "market": market,
        "asof": dt.date.today().isoformat(),
        "rows": sorted(priced, key=lambda r: r["forward_pe"]),
        "loss_making": [r["name"] for r in loss_making],
        "no_estimate": [r["name"] for r in rows if not r["forward_pe"]],
        "median_forward_pe": round(statistics.median([r["forward_pe"] for r in priced]), 1)
        if priced else None,
    }


# ── 엔진 2. 애널리스트 등급·목표주가 변경 ──────────────────────────────
def ratings(market: str, days: int = 7) -> dict:
    """최근 N일 안에 바뀐 투자의견과 목표주가만 추립니다.

    벤치마크가 가장 자주 쓰는 소재입니다(100편 중 73%). 중요한 것은 현재
    의견이 아니라 **바뀌었다는 사실**이므로, 변경 이력만 봅니다.
    """
    cutoff = dt.datetime.now() - dt.timedelta(days=days)
    changes = []
    for entry in core_watchlist(market):
        symbol, ticker = _resolve_yahoo(entry, market)
        if ticker is None:
            continue
        try:
            frame = ticker.upgrades_downgrades
        except Exception:
            continue
        if frame is None or len(frame) == 0:
            continue
        try:
            recent = frame[frame.index >= cutoff.strftime("%Y-%m-%d")]
        except Exception:
            continue
        for when, row in recent.iterrows():
            changes.append({
                "name": entry["name"], "symbol": symbol,
                "date": str(when)[:10],
                "firm": row.get("Firm"),
                "from_grade": row.get("FromGrade") or None,
                "to_grade": row.get("ToGrade"),
                "action": row.get("Action"),
            })
    changes.sort(key=lambda c: c["date"], reverse=True)
    # 야후는 '유지(reiterate)'까지 같은 표에 담습니다. 한 주에 스무 건이 나오는데
    # 대부분이 `Buy → Buy`라 이야기가 되지 않습니다. 실제로 등급이 바뀐 것과
    # 새로 분석을 시작한 것만 남기고, 유지는 개수만 셉니다.
    moved = [c for c in changes if c["action"] in {"up", "down", "init"}]
    upgrades = [c for c in moved if c["action"] == "up"]
    downgrades = [c for c in moved if c["action"] == "down"]
    return {
        "engine": "ratings", "market": market, "days": days,
        "asof": dt.date.today().isoformat(),
        "changes": moved,
        "reiterations": len(changes) - len(moved),
        "upgrade_count": len(upgrades), "downgrade_count": len(downgrades),
        "note": "빈 결과도 결과입니다 — 그 주에 의견 변경이 없었다는 뜻입니다.",
    }


# ── 엔진 3. 실적 캘린더 ────────────────────────────────────────────────
def earnings(market: str, days: int = 21) -> dict:
    """앞으로 N일 안에 실적을 내는 종목을 모읍니다.

    벤치마크의 「9월 30일 실적에서 확인할 5가지」가 이 소재입니다. 글의 수명이
    하루가 아니라 그 실적일까지 갑니다 — 우리 글에 없는 성질입니다.
    """
    today = dt.date.today()
    limit = today + dt.timedelta(days=days)
    upcoming = []
    for entry in core_watchlist(market):
        symbol, ticker = _resolve_yahoo(entry, market)
        if ticker is None:
            continue
        try:
            calendar = ticker.calendar or {}
        except Exception:
            continue
        dates = calendar.get("Earnings Date") or []
        if not isinstance(dates, (list, tuple)):
            dates = [dates]
        for when in dates:
            when = when if isinstance(when, dt.date) else None
            if when and today <= when <= limit:
                upcoming.append({
                    "name": entry["name"], "symbol": symbol,
                    "date": when.isoformat(),
                    "days_away": (when - today).days,
                    "eps_estimate": calendar.get("Earnings Average"),
                    "revenue_estimate": calendar.get("Revenue Average"),
                })
                break
    upcoming.sort(key=lambda r: r["date"])
    return {"engine": "earnings", "market": market, "days": days,
            "asof": today.isoformat(), "upcoming": upcoming}


# ── 엔진 4. 내부자 매수 (SEC Form 4) ───────────────────────────────────
_FORM4_TX = re.compile(r"<transactionCode>(\w)</transactionCode>")
_FORM4_SHARES = re.compile(r"<transactionShares>\s*<value>([\d.]+)</value>")
_FORM4_PRICE = re.compile(r"<transactionPricePerShare>\s*<value>([\d.]+)</value>")
_FORM4_OWNER = re.compile(r"<rptOwnerName>([^<]+)</rptOwnerName>")
_FORM4_TITLE = re.compile(r"<officerTitle>([^<]+)</officerTitle>")


def insiders(days: int = 14, limit_per_ticker: int = 10) -> dict:
    """미국 코어 종목의 최근 내부자 **공개시장 매수**(거래코드 P)만 추립니다.

    벤치마크의 「CEO가 직접 매수한 3개 주식, 그러나 전부 호재는 아니다」가 이
    자리입니다. 그 글의 요지가 이 엔진의 설계를 정합니다 — 내부자 매수는 그
    자체로 신호가 아니라 **누가·얼마를** 샀는지가 신호입니다. 나녹스 CEO는
    4만 달러를 샀고 화이자 임원 셋은 열흘 새 300만 달러를 샀습니다. 그래서
    금액과 직위를 반드시 함께 돌려줍니다.

    매도(코드 S)는 넣지 않습니다. 세금·자산배분 등 개인 사정이 섞여 있어
    그대로는 신호가 되지 않기 때문입니다.
    """
    cutoff = dt.date.today() - dt.timedelta(days=days)
    found = []
    for entry in core_watchlist("us"):
        symbol = entry["ticker"]
        try:
            listing = requests.get(
                "https://www.sec.gov/cgi-bin/browse-edgar",
                # `company=`는 회사 이름 검색이라 티커로는 0건이 나옵니다. EDGAR는
                # `CIK=`에 티커를 넣으면 알아서 회사를 찾아 줍니다(실측).
                params={"action": "getcompany", "CIK": symbol, "type": "4",
                        "dateb": "", "owner": "include", "count": str(limit_per_ticker),
                        "output": "atom"},
                headers=SEC_UA, timeout=20)
            listing.raise_for_status()
            root = ET.fromstring(listing.text)
        except Exception:
            continue
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for item in root.findall("a:entry", ns):
            updated = (item.findtext("a:updated", default="", namespaces=ns) or "")[:10]
            if not updated or dt.date.fromisoformat(updated) < cutoff:
                continue
            href = item.find("a:link", ns)
            url = href.get("href") if href is not None else None
            if not url:
                continue
            try:
                doc = requests.get(url, headers=SEC_UA, timeout=20).text
                # 신고서 페이지에는 .xml이 둘 있습니다. 앞의 `xslF345X0*/`는 사람이
                # 보라고 HTML로 변환해 주는 경로라 태그가 안 나옵니다. 원본만 씁니다.
                candidates = [href for href in re.findall(r'href="([^"]+\.xml)"', doc)
                              if "/xsl" not in href]
                if not candidates:
                    continue
                raw = requests.get("https://www.sec.gov" + candidates[0],
                                   headers=SEC_UA, timeout=20).text
            except Exception:
                continue
            if "P" not in _FORM4_TX.findall(raw):
                continue                       # 공개시장 매수가 아닌 신고서
            shares = _FORM4_SHARES.search(raw)
            price = _FORM4_PRICE.search(raw)
            if not (shares and price):
                continue
            value = float(shares.group(1)) * float(price.group(1))
            owner = _FORM4_OWNER.search(raw)
            title = _FORM4_TITLE.search(raw)
            found.append({
                "name": entry["name"], "symbol": symbol, "date": updated,
                "owner": owner.group(1) if owner else None,
                "title": title.group(1) if title else None,
                "shares": float(shares.group(1)),
                "price": float(price.group(1)),
                "value_usd": round(value),
                "filing": url,
            })
    found.sort(key=lambda f: f["value_usd"], reverse=True)
    return {"engine": "insiders", "days": days, "asof": dt.date.today().isoformat(),
            "buys": found,
            "note": "금액과 직위를 함께 보십시오. 같은 '내부자 매수'라도 4만 달러와 "
                    "300만 달러는 다른 신호입니다."}


# ── 엔진 5. 외국인 vs 기관 반대 매매 ───────────────────────────────────
def flows(date: str | None = None) -> dict:
    """같은 종목을 외국인은 팔고 기관은 산(또는 그 반대) 날을 찾습니다.

    새 수집이 필요 없습니다 — `data/price_kr_<날짜>.json`에 이미 들어 있는
    값입니다. "외국인이 팔았다"만 보면 악재 같지만 받아 준 쪽이 있으면 주가는
    덜 흔들립니다. 그 대비가 하루의 성격을 가릅니다.
    """
    if date is None:
        files = sorted(DATA.glob("price_kr_*.json"))
        if not files:
            return {"engine": "flows", "error": "price_kr_*.json이 없습니다."}
        path = files[-1]
        date = path.stem.replace("price_kr_", "")
    else:
        path = DATA / f"price_kr_{date}.json"
        if not path.exists():
            return {"engine": "flows", "date": date, "error": f"{path.name}이 없습니다."}

    price_data = json.loads(path.read_text(encoding="utf-8"))
    opposed, aligned = [], []
    for entry in (price_data.get("watchlist") or {}).values():
        foreign = entry.get("foreign_net")
        institution = entry.get("institution_net")
        if foreign is None or institution is None or foreign == 0 or institution == 0:
            continue
        row = {"name": entry.get("name"), "ticker": entry.get("ticker"),
               "change_pct": entry.get("change_pct"),
               "foreign_net": foreign, "institution_net": institution,
               "source": entry.get("source")}
        (opposed if (foreign > 0) != (institution > 0) else aligned).append(row)
    opposed.sort(key=lambda r: -min(abs(r["foreign_net"]), abs(r["institution_net"])))
    return {"engine": "flows", "date": date, "opposed": opposed, "aligned": aligned,
            "note": "opposed = 외국인과 기관이 반대로 간 종목. 겹치는 물량이 큰 순."}


# ── 엔진 6. 계절성 ─────────────────────────────────────────────────────
def seasonality(market: str, years: int = 20) -> dict:
    """지수의 월별 평균 등락을 셉니다.

    벤치마크가 「8월, 주식 투자 가장 위험한 달입니다」 같은 글에 쓰는 소재이고,
    100편 중 21%가 이런 통계를 인용합니다. 우리 시세 이력은 며칠뿐이라
    야후에서 장기 이력을 따로 받습니다.
    """
    import yfinance as yf

    index = {"kr": "^KS11", "us": "^GSPC"}[market]
    frame = yf.Ticker(index).history(period=f"{years}y", interval="1mo")
    if frame is None or len(frame) == 0:
        return {"engine": "seasonality", "market": market, "error": "이력을 받지 못했습니다."}
    frame = frame[frame["Close"] > 0]
    monthly = frame["Close"].pct_change().dropna() * 100
    by_month = {}
    for when, value in monthly.items():
        by_month.setdefault(when.month, []).append(float(value))
    months = []
    for month in range(1, 13):
        values = by_month.get(month) or []
        if not values:
            continue
        months.append({
            "month": month, "samples": len(values),
            "mean_pct": round(statistics.mean(values), 2),
            "median_pct": round(statistics.median(values), 2),
            "win_rate_pct": round(100 * sum(1 for v in values if v > 0) / len(values)),
        })
    this_month = next((m for m in months if m["month"] == dt.date.today().month), None)
    return {"engine": "seasonality", "market": market, "index": index,
            "years": years, "months": months, "this_month": this_month}



# ── 엔진 7. 한국 내부자 매수 (DART 임원·주요주주 소유상황보고서) ─────────
_DART_SEARCH = "https://dart.fss.or.kr/dsab007/detailSearch.ax"
_DART_MAIN = "https://dart.fss.or.kr/dsaf001/main.do"
_DART_VIEWER = "https://dart.fss.or.kr/report/viewer.do"
_DART_UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"}
_DART_ROW = re.compile(
    r"openCorpInfoNew\('\d+'.*?>\s*([^<]+?)\s*</a>.*?"
    r"rcpNo=(\d+)\".*?<td class=\"tL ellipsis\" title=\"([^\"]*)\">.*?"
    r"<td>(\d{4}\.\d{2}\.\d{2})</td>", re.S)
_DART_NODE = re.compile(r"node\d+\['(\w+)'\]\s*=\s*\"([^\"]*)\";")
_DART_TAGS = re.compile(r"<[^>]+>")


def _dart_get(session, url, *, params=None, data=None, tries: int = 3):
    """DART는 연속 요청에 연결을 끊습니다. 끊기면 쉬었다가 다시 겁니다."""
    last = None
    for attempt in range(tries):
        try:
            response = (session.post(url, data=data, timeout=25) if data is not None
                        else session.get(url, params=params, timeout=25))
            response.raise_for_status()
            return response
        except Exception as exc:               # 연결 끊김·5xx 모두 같은 처리
            last = exc
            time.sleep(2 * (attempt + 1))
    raise last


def _dart_cells(html: str) -> list[str]:
    text = _DART_TAGS.sub("|", html).replace("&nbsp;", " ")
    return [c.strip() for c in text.split("|")]


def kr_insiders(days: int = 7, scan: int = 40) -> dict:
    """한국 상장사 임원·주요주주의 **장내매수**만 추립니다.

    DART OpenAPI는 키가 필요하지만 공시검색 화면은 키 없이 열립니다(2026-09-06
    실측). 미국 Form 4 엔진과 같은 원칙을 씁니다 — 매도는 넣지 않고, 금액과
    직위를 함께 돌려줍니다. 사유가 `장내매수`가 아닌 것(상속·증여·대여주식상환·
    스톡옵션 행사)은 본인 판단으로 산 것이 아니라 신호가 되지 않습니다.

    `scan`편만 열어 봅니다. 이 공시는 하루 수십 건이 올라오는데 전부 열면
    수백 번을 두드리게 되고, 그중 대부분은 우리가 이름도 모르는 회사입니다.
    """
    session = requests.Session()
    session.headers.update(_DART_UA)
    today = dt.date.today()
    start = (today - dt.timedelta(days=days)).strftime("%Y%m%d")
    try:
        listing = _dart_get(session, _DART_SEARCH, data={
            "currentPage": "1", "maxResults": str(scan), "reportNamePopYn": "Y",
            "reportName": "임원ㆍ주요주주특정증권등소유상황보고서",
            "startDate": start, "endDate": today.strftime("%Y%m%d"),
            "finalReport": "recent"})
    except Exception as exc:
        return {"engine": "kr_insiders", "error": f"공시 목록을 받지 못했습니다: {exc}"}

    core = {row["name"] for row in core_watchlist("kr")}
    buys = []
    failed = 0
    rows = _DART_ROW.findall(listing.text)[:scan]
    for company, rcp_no, filer, filed in rows:
        try:
            page = _dart_get(session, _DART_MAIN, params={"rcpNo": rcp_no}).text
            nodes = _DART_NODE.findall(page)
            node, section = {}, None
            for key, value in nodes:
                if key == "text":
                    if node.get("dcmNo") and "소유상황" in (node.get("text") or ""):
                        section = dict(node)
                    node = {"text": value}
                else:
                    node[key] = value
            if node.get("dcmNo") and "소유상황" in (node.get("text") or ""):
                section = dict(node)
            if not section:
                continue
            body = _dart_get(session, _DART_VIEWER, params={
                "rcpNo": rcp_no, "dcmNo": section["dcmNo"], "eleId": section["eleId"],
                "offset": section["offset"], "length": section["length"],
                "dtd": section["dtd"]})
            body.encoding = body.apparent_encoding
            cells = _dart_cells(body.text)
        except Exception:
            # 여기를 조용히 넘기면 "매수가 없었다"와 "서버가 끊었다"가 같은 0건으로
            # 보입니다. DART는 빠르게 두드리면 연결을 끊습니다(실측). 세어서 알립니다.
            failed += 1
            continue

        # 세부변동내역 행: 보고사유 · 변동일 · 종류 · 변동전 · 증감 · 변동후 · 단가
        #
        # 빈 칸을 **먼저** 걸러야 합니다. `cells[i:i+12]`처럼 자르면 표 사이의 빈
        # 칸이 자릿수를 잡아먹어 단가가 창 밖으로 밀려나고, 그러면 매수가 있는데도
        # 없는 것으로 지나갑니다.
        filled = [c for c in cells if c]
        for i, cell in enumerate(filled):
            if "장내매수" not in cell:
                continue
            window = filled[i:i + 12]
            numbers = [c for c in window if re.fullmatch(r"[+\-]?[\d,]+", c)]
            if len(numbers) < 4:
                continue
            change = int(numbers[1].replace(",", ""))
            price = int(numbers[3].replace(",", ""))
            if change <= 0 or price <= 0:
                continue
            when = next((c for c in window if re.fullmatch(r"\d{4}\.\d{2}\.\d{2}", c)), filed)
            buys.append({
                "company": company, "is_core": company in core,
                "filer": filer, "date": when.replace(".", "-"),
                "shares": change, "price": price, "value_krw": change * price,
                "filing": f"{_DART_MAIN}?rcpNo={rcp_no}",
            })
        time.sleep(1.0)                       # DART는 빠르게 두드리면 연결을 끊습니다

    buys.sort(key=lambda b: b["value_krw"], reverse=True)
    return {"engine": "kr_insiders", "days": days, "scanned": len(rows),
            "failed": failed, "asof": today.isoformat(), "buys": buys,
            "core_hits": [b for b in buys if b["is_core"]],
            "note": "장내매수만 담았습니다. 상속·증여·대여주식상환·스톡옵션 행사는 "
                    "본인이 값을 치르고 산 것이 아니라 신호가 되지 않습니다."}



# ── 엔진 8. 기관 보유 변동 (SEC 13F) ──────────────────────────────────
# CIK는 2026-09-06에 EDGAR 회사 검색으로 하나씩 확인했습니다. 이름이 비슷한
# 법인이 여럿이라 추측해서 넣으면 다른 펀드의 매매를 그 사람 것으로 쓰게 됩니다.
FUNDS = [
    ("0001536411", "듀케인(드러켄밀러)"),
    ("0001350694", "브리지워터(달리오)"),
    ("0001037389", "르네상스 테크놀로지"),
    ("0001336528", "퍼싱스퀘어(애크먼)"),
    ("0001067983", "버크셔 해서웨이(버핏)"),
    ("0001135730", "코튜 매니지먼트"),
    ("0001167483", "타이거 글로벌"),
    ("0001649339", "사이언(버리)"),
]
_INFO_NS = {"i": "http://www.sec.gov/edgar/document/thirteenf/informationtable"}


def _13f_holdings(raw: str) -> dict:
    """정보표를 CUSIP별로 합칩니다.

    같은 종목이 매니저·재량권별로 여러 줄에 나뉘어 나옵니다(버크셔의 ALLY는
    다섯 줄). 합치지 않으면 보유량이 실제의 몇 분의 일로 잡힙니다.
    """
    root = ET.fromstring(raw)
    holdings: dict[str, dict] = {}
    for item in root.findall(".//i:infoTable", _INFO_NS):
        cusip = item.findtext("i:cusip", default="", namespaces=_INFO_NS)
        shares = item.findtext("i:shrsOrPrnAmt/i:sshPrnamt", default="0",
                               namespaces=_INFO_NS)
        value = item.findtext("i:value", default="0", namespaces=_INFO_NS)
        if not cusip:
            continue
        # 알파벳처럼 종류주가 있는 회사는 이름이 같고 CUSIP이 다릅니다. 이름만
        # 찍으면 같은 줄이 두 번 나온 것처럼 보이므로 종류를 함께 답니다.
        row = holdings.setdefault(cusip, {
            "name": item.findtext("i:nameOfIssuer", default="", namespaces=_INFO_NS),
            "klass": item.findtext("i:titleOfClass", default="", namespaces=_INFO_NS),
            "shares": 0, "value": 0})
        row["shares"] += int(float(shares or 0))
        row["value"] += int(float(value or 0))
    return holdings


def _13f_latest_two(cik: str) -> list[tuple[str, str]]:
    """가장 최근 13F-HR 두 건의 (기준일, 정보표 URL)."""
    meta = requests.get(f"https://data.sec.gov/submissions/CIK{cik}.json",
                        headers=SEC_UA, timeout=25).json()
    recent = meta["filings"]["recent"]
    found = []
    for i, form in enumerate(recent["form"]):
        if form != "13F-HR":
            continue
        accession = recent["accessionNumber"][i].replace("-", "")
        base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}"
        listing = requests.get(base + "/", headers=SEC_UA, timeout=25).text
        # primary_doc.xml은 표지입니다. 보유 내역은 다른 xml에 있습니다.
        tables = [href for href in re.findall(r'href="([^"]+\.xml)"', listing)
                  if "primary_doc" not in href]
        if tables:
            found.append((recent["reportDate"][i], "https://www.sec.gov" + tables[0]))
        if len(found) == 2:
            break
    return found


def institutions(top: int = 12) -> dict:
    """유명 기관들이 지난 분기에 무엇을 늘리고 무엇을 줄였는지 셉니다.

    벤치마크의 「기관 매매 분석 — 메모리를 팔고 아마존·엔비디아·TSMC를 산 이유」가
    이 소재입니다. 그 글의 요지가 설계를 정합니다 — **이름만 보면 절반만 보는
    것입니다.** 같은 매수라도 바닥에서 산 것과 네 배 오른 뒤 산 것은 뜻이 다르고,
    같은 매도라도 손절과 차익 실현은 다릅니다. 그래서 증감과 함께 직전 분기
    보유량을 같이 돌려줍니다.

    13F는 분기에 한 번, 기준일로부터 45일 뒤에 나옵니다. **지난 분기의 흔적이지
    지금의 포지션이 아닙니다.**
    """
    moves, failed = [], []
    for cik, label in FUNDS:
        try:
            filings = _13f_latest_two(cik)
            if len(filings) < 2:
                failed.append(label)
                continue
            (new_date, new_url), (old_date, old_url) = filings
            new = _13f_holdings(requests.get(new_url, headers=SEC_UA, timeout=30).text)
            time.sleep(0.4)
            old = _13f_holdings(requests.get(old_url, headers=SEC_UA, timeout=30).text)
        except Exception:
            failed.append(label)
            continue

        for cusip, row in new.items():
            before = old.get(cusip, {}).get("shares", 0)
            change = row["shares"] - before
            if before == 0 and change == 0:
                continue
            moves.append({
                "fund": label, "issuer": row["name"], "klass": row.get("klass"),
                "cusip": cusip,
                "quarter": new_date, "prev_quarter": old_date,
                "shares_before": before, "shares_after": row["shares"],
                "change": change, "value_usd": row["value"],
                "is_new": before == 0,
                "change_pct": round(100 * change / before, 1) if before else None,
            })
        for cusip, row in old.items():
            if cusip not in new:
                moves.append({
                    "fund": label, "issuer": row["name"], "klass": row.get("klass"),
                    "cusip": cusip,
                    "quarter": new_date, "prev_quarter": old_date,
                    "shares_before": row["shares"], "shares_after": 0,
                    "change": -row["shares"], "value_usd": 0,
                    "is_new": False, "is_exit": True, "change_pct": -100.0,
                })
        time.sleep(0.4)

    added = sorted([m for m in moves if m["change"] > 0],
                   key=lambda m: -m["value_usd"])[:top]
    trimmed = sorted([m for m in moves if m["change"] < 0],
                     key=lambda m: m["change"])[:top]
    return {"engine": "institutions", "asof": dt.date.today().isoformat(),
            "funds": len(FUNDS) - len(failed), "failed": failed,
            "added": added, "trimmed": trimmed,
            "note": "13F는 기준일로부터 45일 뒤에 공개됩니다. 지난 분기의 흔적이지 "
                    "지금의 포지션이 아닙니다."}


# ── 출력 ───────────────────────────────────────────────────────────────
def _print(result: dict) -> None:
    engine = result.get("engine")
    if result.get("error"):
        print(f"[{engine}] {result['error']}")
        return
    if engine == "valuation":
        print(f"[밸류에이션] {result['market'].upper()} · {result['asof']} · "
              f"FWD PER 중앙값 {result['median_forward_pe']}")
        print(f"  {'종목':<12}{'FWD PER':>9}{'목표가 대비':>11}{'52주고점 대비':>13}{'애널':>6}")
        for row in result["rows"]:
            # f-string 안에 같은 따옴표를 중첩하는 것은 파이썬 3.12부터입니다.
            # 워크플로는 3.11로 돌아서 로컬(3.14)에서만 통과하는 문법이 됩니다.
            upside = ("-" if row["upside_pct"] is None
                      else f"{row['upside_pct']:+.1f}%")
            off_high = ("-" if row["off_52w_high_pct"] is None
                        else f"{row['off_52w_high_pct']:+.1f}%")
            name = row["name"][:11]
            print(f"  {name:<12}{row['forward_pe']:>9.1f}{upside:>11}"
                  f"{off_high:>13}{row['analysts'] or '-':>6}")
        if result.get("loss_making"):
            print(f"  (내년 적자 예상: {', '.join(result['loss_making'])})")
        if result["no_estimate"]:
            print(f"  (추정치 없음: {', '.join(result['no_estimate'])})")
    elif engine == "ratings":
        print(f"[의견 변경] {result['market'].upper()} · 최근 {result['days']}일 · "
              f"상향 {result['upgrade_count']} 하향 {result['downgrade_count']} "
              f"(의견 유지 {result['reiterations']}건은 뺐습니다)")
        for change in result["changes"]:
            arrow = {"up": "▲", "down": "▼"}.get(change["action"], "·")
            print(f"  {change['date']} {arrow} {change['name']:<12} {change['firm']}: "
                  f"{change['from_grade'] or '?'} → {change['to_grade']}")
        if not result["changes"]:
            print("  " + result["note"])
    elif engine == "earnings":
        print(f"[실적 일정] {result['market'].upper()} · 앞으로 {result['days']}일")
        for row in result["upcoming"]:
            print(f"  D-{row['days_away']:<3} {row['date']}  {row['name']}")
        if not result["upcoming"]:
            print("  해당 기간에 예정된 코어 종목 실적이 없습니다.")
    elif engine == "insiders":
        print(f"[내부자 매수] 최근 {result['days']}일 · {len(result['buys'])}건")
        for buy in result["buys"]:
            print(f"  {buy['date']} {buy['name']:<10} ${buy['value_usd']:>12,}  "
                  f"{buy['owner']} ({buy['title'] or '직위 미상'})")
        print("  " + result["note"])
    elif engine == "institutions":
        print(f"[기관 보유 변동] 펀드 {result['funds']}곳 · 13F "
              f"{result['added'][0]['quarter'] if result['added'] else '?'} 기준")
        if result["failed"]:
            print(f"  ※ 받지 못한 곳: {', '.join(result['failed'])}")
        print("  늘린 쪽")
        for move in result["added"]:
            tag = "신규" if move["is_new"] else f"{move['change_pct']:+.0f}%"
            label = f"{move['issuer']} {move.get('klass') or ''}".strip()
            print(f"    {move['fund'][:14]:<15}{label[:26]:<28}"
                  f"{move['change']:>+12,}주 ({tag})")
        print("  줄인 쪽")
        for move in result["trimmed"]:
            tag = "전량매도" if move.get("is_exit") else f"{move['change_pct']:+.0f}%"
            label = f"{move['issuer']} {move.get('klass') or ''}".strip()
            print(f"    {move['fund'][:14]:<15}{label[:26]:<28}"
                  f"{move['change']:>+12,}주 ({tag})")
        print("  " + result["note"])
    elif engine == "kr_insiders":
        print(f"[한국 내부자 매수] 최근 {result['days']}일 · 공시 {result['scanned']}건을 열어 "
              f"장내매수 {len(result['buys'])}건")
        if result.get("failed"):
            print(f"  ※ {result['failed']}건은 열지 못했습니다 — 이 결과는 그만큼 덜 셌습니다.")
        for buy in result["buys"][:15]:
            mark = "★" if buy["is_core"] else " "
            print(f" {mark}{buy['date']} {buy['company'][:12]:<13}{buy['value_krw']:>14,}원  "
                  f"{buy['filer']} ({buy['shares']:,}주 @ {buy['price']:,})")
        print("  ★ = 우리 코어 워치리스트 종목")
        print("  " + result["note"])
    elif engine == "flows":
        print(f"[수급 엇갈림] {result['date']} · 반대 {len(result['opposed'])}종목 "
              f"/ 같은 방향 {len(result['aligned'])}종목")
        for row in result["opposed"]:
            print(f"  {row['name']:<12} {row['change_pct']:+6.2f}%  "
                  f"외국인 {row['foreign_net']:>+12,}  기관 {row['institution_net']:>+12,}")
    elif engine == "seasonality":
        current = result.get("this_month")
        print(f"[계절성] {result['index']} · 최근 {result['years']}년")
        for row in result["months"]:
            mark = "  ←이번 달" if current and row["month"] == current["month"] else ""
            print(f"  {row['month']:>2}월  평균 {row['mean_pct']:+6.2f}%  "
                  f"중앙 {row['median_pct']:+6.2f}%  상승확률 {row['win_rate_pct']:>3}%  "
                  f"(n={row['samples']}){mark}")


def main() -> int:
    parser = argparse.ArgumentParser(description="글감 엔진 — 재료만 만들고 문장은 쓰지 않습니다.")
    parser.add_argument("engine", choices=["valuation", "ratings", "earnings",
                                           "insiders", "kr_insiders", "institutions", "flows",
                                           "seasonality", "all"])
    parser.add_argument("--market", choices=["kr", "us"], default="us")
    parser.add_argument("--days", type=int)
    parser.add_argument("--date")
    parser.add_argument("--json", action="store_true", help="사람이 읽는 표 대신 JSON")
    args = parser.parse_args()

    runners = {
        "valuation": lambda: valuation(args.market),
        "ratings": lambda: ratings(args.market, args.days or 7),
        "earnings": lambda: earnings(args.market, args.days or 21),
        "insiders": lambda: insiders(args.days or 14),
        "kr_insiders": lambda: kr_insiders(args.days or 7),
        "institutions": lambda: institutions(),
        "flows": lambda: flows(args.date),
        "seasonality": lambda: seasonality(args.market),
    }
    names = list(runners) if args.engine == "all" else [args.engine]
    if args.engine == "all" and args.market == "us":
        for name in ("flows", "kr_insiders"):
            names.remove(name)                 # 한국장 전용
    elif args.engine == "all":
        for name in ("insiders", "institutions"):
            names.remove(name)                 # SEC는 미국 종목 전용

    for name in names:
        result = runners[name]()
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=1, default=str))
        else:
            _print(result)
            print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
