"""코스피·코스닥 지수 대조 — 원천이 멈추거나 틀리면 운영 대화(텔레그램)로 알린다 (2026-10-05).

왜
--
지수 원천(FinanceDataReader의 깃허브 사본)이 9/17부터 멈춰 있었는데 2주 넘게 아무도 몰랐다. 빈 날을 메우는 장치가
글은 내보냈지만 문제를 가렸고, 실행 기록에 날마다 찍힌 "일봉이 9/17에 머물러"는 아무도 읽지 않았다. 그 사본의 9/17 값은
장중 값이라 우리 이력 그림에도 틀린 점(6,724.34 — 확정 6,715.41)이 들어가 있었다.

무엇을 보나
-----------
1. 네이버 지수 일별 목록(지금 원천)이 우리 시세 파일보다 2거래일 넘게 뒤처졌는가 — 목록이 멈춤. 하루는 봐준다.
2. 시세 파일의 지수 이력이 한국은행 ECOS 「주식시장(일)」(작성기관 한국거래소)과 같은가 — 겹치는 날짜만, 0.01 넘게
   다르면 문제. ECOS가 우리 이력보다 3거래일 넘게 뒤처졌으면 그것도 알린다(대조할 눈이 멈춤).

발행은 막지 않는다 — 알리기만 한다. 한국장 시세 수집 바로 뒤에 돈다(market_brief.yml, `continue-on-error`).

    python -m src.index_check                          # 가장 최근 한국장 시세 파일
    python -m src.index_check data/price_kr_<날짜>.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

from src import alert, fetch_kr

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
ECOS_URL = "https://ecos.bok.or.kr/api/StatisticSearch/{key}/json/kr/1/100/802Y001/D/{start}/{end}/{item}"
ECOS_ITEMS = {"KS11": "0001000", "KQ11": "0089000"}   # 802Y001 KOSPI지수·KOSDAQ지수
NAVER_CODES = {"KS11": "KOSPI", "KQ11": "KOSDAQ"}
TOLERANCE = 0.011
NAVER_LAG_DAYS = 2       # 목록이 이만큼(거래일) 넘게 뒤처지면 멈춘 것
ECOS_LAG_DAYS = 3


def latest_price_file() -> Path:
    files = sorted((ROOT / "data").glob("price_kr_*.json"))
    if not files:
        raise FileNotFoundError("data/price_kr_*.json이 없습니다")
    return files[-1]


def _history(entry: dict) -> dict[str, float]:
    hist = entry.get("history") or {}
    return dict(zip(hist.get("dates") or [], (float(c) for c in hist.get("close") or [])))


def naver_lag_issues(ticker: str, history: dict[str, float], naver: list[tuple[str, float]]) -> list[str]:
    """목록의 마지막 날 뒤로 우리 이력에 거래일이 몇 개 더 있나 — NAVER_LAG_DAYS를 넘으면 목록이 멈춘 것이다."""
    if not naver:
        return [f"{NAVER_CODES[ticker]}: 네이버 지수 일별 목록이 비어 있습니다"]
    last = naver[-1][0]
    ahead = [d for d in history if d > last]
    if len(ahead) > NAVER_LAG_DAYS:
        return [f"{NAVER_CODES[ticker]}: 네이버 지수 일별 목록이 {last}에 멈춰 있습니다(우리 시세 파일은 {max(history)}까지)"]
    return []


def ecos_rows(key: str, ticker: str, start: str, end: str) -> dict[str, float]:
    """ECOS의 그 기간 지수 종가. 해당 자료가 없으면(INFO-200) 빈 dict, 다른 오류는 예외."""
    url = ECOS_URL.format(key=key, start=start.replace("-", ""), end=end.replace("-", ""), item=ECOS_ITEMS[ticker])
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    body = response.json()
    if "StatisticSearch" not in body:
        result = body.get("RESULT") or {}
        if result.get("CODE") == "INFO-200":
            return {}
        raise ValueError(f"ECOS 응답 오류: {result.get('CODE')} {result.get('MESSAGE')}")
    out = {}
    for row in body["StatisticSearch"].get("row") or []:
        t = str(row["TIME"])
        out[f"{t[:4]}-{t[4:6]}-{t[6:8]}"] = float(row["DATA_VALUE"])
    return out


def ecos_issues(ticker: str, history: dict[str, float], ecos: dict[str, float]) -> list[str]:
    name = NAVER_CODES[ticker]
    wrong = [f"{d} 우리 {history[d]:,.2f} / ECOS {ecos[d]:,.2f}" for d in sorted(history)
             if d in ecos and abs(history[d] - ecos[d]) > TOLERANCE]
    issues = [f"{name}: 지수 이력이 ECOS와 다릅니다 — " + ", ".join(wrong)] if wrong else []
    last = max(ecos) if ecos else ""
    behind = [d for d in history if d > last]
    if len(behind) > ECOS_LAG_DAYS:
        issues.append(f"{name}: ECOS가 {last or '(자료 없음)'}에 멈춰 있어 최근 {len(behind)}거래일을 대조하지 못했습니다")
    return issues


def check(price_doc: dict, key: str) -> list[str]:
    issues: list[str] = []
    macro = price_doc.get("macro") or {}
    for ticker in ("KS11", "KQ11"):
        entry = macro.get(ticker)
        if not entry:
            issues.append(f"{ticker}: 시세 파일에 지수가 없습니다")
            continue
        history = _history(entry)
        if not history:
            issues.append(f"{NAVER_CODES[ticker]}: 시세 파일에 지수 이력이 없습니다")
            continue
        issues += naver_lag_issues(ticker, history, fetch_kr._fetch_naver_index_daily(NAVER_CODES[ticker]))
        issues += ecos_issues(ticker, history, ecos_rows(key, ticker, min(history), max(history)))
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="코스피·코스닥 지수를 네이버 목록·ECOS와 대조합니다")
    parser.add_argument("path", nargs="?", help="한국장 시세 파일(기본: 가장 최근)")
    args = parser.parse_args(argv)
    try:
        key = os.environ.get("ECOS_API_KEY")
        if not key:
            raise RuntimeError("ECOS_API_KEY가 없습니다 — 워크플로 env 또는 .env를 확인하세요")
        path = Path(args.path) if args.path else latest_price_file()
        issues = check(json.loads(path.read_text(encoding="utf-8")), key)
    except Exception as exc:  # noqa: BLE001 — 대조를 못 한 것도 알린다(조용히 넘기지 않는다)
        alert.send(f"지수 대조를 하지 못했습니다 — {exc}", "warn")
        raise
    if issues:
        print("\n".join(issues))
        alert.send(f"지수 대조 ({path.name}): " + " / ".join(issues), "warn")
        return 1
    print(f"지수 대조 정상 ({path.name}): 네이버 목록·ECOS와 같습니다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
