"""지난 거래일의 시세 파일을 만들거나, 원고에 박힌 시세에 3개월 이력(`history`)을 채웁니다.

왜 (2026-09-08)
---------------
옛 글을 재테크농부 규칙(10~14절, 시각자료 6개 이상)으로 다시 쓰려면 3개월 흐름 그래픽
(`price_history`)이 필요한데, 2026-09-08 이전 시세 파일과 원고의 `price_data`에는
`history`가 없다. 또 시황 이전 옛 글 5편(8/28~8/31)은 시세 파일 자체가 없다.

    python -m scripts.backfill_prices --market kr --date 2026-08-28          # data/price_kr_2026-08-28.json 생성(코어만)
    python -m scripts.backfill_prices --manuscript editorial/kr_2026-09-03.json   # 원고 price_data에 history 채움

한국은 FinanceDataReader(과거 일봉 가능), 미국은 yfinance(이 컴퓨터에서만 — 샌드박스는 막힘).
동적 편입 종목·외국인 순매매는 과거로 되돌려 받을 수 없어 새 파일에는 코어만 담는다.
원고 쪽은 이미 있는 항목(편입 종목 포함)을 그대로 두고 `history`만 더한다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import yaml

from src import price_history

ROOT = Path(__file__).resolve().parent.parent


def _frame(market: str, ticker: str, end: dt.date):
    start = end - dt.timedelta(days=price_history.CALENDAR_DAYS)
    if market == "kr":
        import FinanceDataReader as fdr
        return fdr.DataReader(ticker, start, end)
    import yfinance as yf
    return yf.Ticker(ticker).history(start=start.isoformat(), end=(end + dt.timedelta(days=1)).isoformat())


def _entry(market: str, row: dict, end: dt.date, lookback: int = 7) -> dict:
    frame = _frame(market, row["ticker"], end)
    valid = frame["Close"].dropna()
    if len(valid) < 2:
        raise ValueError(f"{row['ticker']}: {end}까지 종가가 부족합니다")
    closes = [float(v) for v in valid.tail(lookback + 1).tolist()]
    last_date = valid.index[-1].date().isoformat()
    change = (closes[-1] - closes[-2]) / closes[-2] * 100
    return {
        "ticker": row["ticker"], "name": row["name"], "name_en": row.get("name_en") or row["name"],
        "price": round(closes[-1], 2), "change_pct": round(change, 2),
        "series": [round(c, 4) for c in closes], "history": price_history.from_frame(frame),
        "unit": row.get("unit", ""), "trading_date": last_date,
    }


def build(market: str, date: dt.date) -> dict:
    config = yaml.safe_load((ROOT / "config" / f"watchlist_{market}.yaml").read_text(encoding="utf-8"))
    macro, watchlist, missing = {}, {}, []
    for row in config["macro"]:
        try:
            macro[row["ticker"]] = _entry(market, row, date)
        except Exception as exc:  # noqa: BLE001 - 빠진 항목은 세어서 보고한다
            missing.append(f"{row['name']}: {exc}")
    for row in config["watchlist"]:
        try:
            entry = _entry(market, row, date)
        except Exception as exc:  # noqa: BLE001
            missing.append(f"{row['name']}: {exc}"); continue
        entry["source"] = "core"
        if row.get("sector"):
            entry["sector"] = row["sector"]
        watchlist[row["ticker"]] = entry
    # 기준일은 첫 지수(코스피·다우)의 마지막 거래일. 그날과 다른 종목은 버린다 —
    # 수집기가 편입 종목에 쓰는 규칙과 같다. 환율(USD/KRW)은 달력이 달라 검사에서 뺀다.
    first = config["macro"][0]["ticker"]
    if first not in macro:
        raise SystemExit(f"{first} 시세를 받지 못해 기준일을 정할 수 없습니다.")
    trading_date = macro[first]["trading_date"]
    for ticker, entry in list(watchlist.items()):
        if entry["trading_date"] != trading_date:
            missing.append(f"{entry['name']}: 기준일 {entry['trading_date']} ≠ {trading_date}")
            del watchlist[ticker]
    for ticker, entry in list(macro.items()):
        if ticker != "USD/KRW" and entry["trading_date"] != trading_date:
            missing.append(f"{entry['name']}: 기준일 {entry['trading_date']} ≠ {trading_date}")
            del macro[ticker]
    if missing:
        print(f"[안내] 빠진 항목 {len(missing)}개: " + "; ".join(missing))
    return {"macro": macro, "watchlist": watchlist, "trading_date": trading_date, "missing": missing,
            "backfilled": dt.date.today().isoformat()}


def merge_history(path: Path) -> int:
    doc = json.loads(path.read_text(encoding="utf-8"))
    market, end = doc["market"], dt.date.fromisoformat(doc["date"])
    price = doc["price_data"]
    added = 0
    for group in ("macro", "watchlist"):
        for ticker, entry in (price.get(group) or {}).items():
            if entry.get("history"):
                continue
            if ticker == "USD/KRW" and market == "kr":
                continue  # 하나은행 고시환율은 일봉 소스가 달라 이력을 섞지 않는다
            try:
                frame = _frame(market, entry.get("ticker") or ticker, end)
                entry["history"] = price_history.from_frame(frame)
                added += 1
            except Exception as exc:  # noqa: BLE001
                print(f"[안내] {ticker} 이력 없이 갑니다: {exc}")
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # 같은 날 시세 파일에도 넣어 둔다(있으면)
    data_file = ROOT / "data" / f"price_{market}_{doc['date']}.json"
    if data_file.exists():
        data = json.loads(data_file.read_text(encoding="utf-8"))
        for group in ("macro", "watchlist"):
            for ticker, entry in (data.get(group) or {}).items():
                src = (price.get(group) or {}).get(ticker)
                if src and src.get("history") and not entry.get("history"):
                    entry["history"] = src["history"]
        data_file.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return added


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--market", choices=["kr", "us"])
    parser.add_argument("--date")
    parser.add_argument("--manuscript", type=Path)
    args = parser.parse_args(argv)
    if args.manuscript:
        print(f"{args.manuscript}: history {merge_history(args.manuscript)}개 추가")
        return 0
    if not (args.market and args.date):
        parser.error("--market과 --date, 또는 --manuscript")
    payload = build(args.market, dt.date.fromisoformat(args.date))
    out = ROOT / "data" / f"price_{args.market}_{payload['trading_date']}.json"
    if out.exists():
        print(f"이미 있습니다: {out} — 덮어쓰지 않습니다. 원고 이력은 --manuscript로 채우십시오.")
        return 1
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"완료: {out} (코어 {len(payload['watchlist'])}종목, 지수 {len(payload['macro'])})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
