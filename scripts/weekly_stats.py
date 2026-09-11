"""주간 결산 재료 — 시세 파일의 3개월 이력에서 한 주를 계산한다 (2026-09-12, 주말 편성).

왜 따로 있는가
--------------
토요일 아침 「주간 결산」 루틴이 쓰는 숫자는 전부 우리가 평일마다 커밋한 시세 파일
(`data/price_<market>_<날짜>.json`)에서 나온다. 2026-09-08부터 시세 파일마다 지수·종목의
3개월 종가 이력(`history`)이 들어 있으므로, 금요일 파일 하나로 한 주(월~금)의 등락과
전주 대비 변화를 셀 수 있다. 검색도, 외부 API도 필요 없다 — 그래서 샌드박스에서도 돈다.

    python -m scripts.weekly_stats                          # 두 시장, KST 오늘 기준 가장 최근 거래일까지의 한 주
    python -m scripts.weekly_stats --market kr --date 2026-09-12
    python -m scripts.weekly_stats --json output/weekly/2026-09-12.json   # 루틴이 읽을 JSON도 남긴다

거래일이 3일 미만인 주(긴 연휴)는 결산을 쓰지 않는다 — 종료 코드 2로 멈추고 이유를 찍는다.
억지로 얇은 결산을 쓰지 않는 것이 규칙이다(`--allow-thin`은 시험용).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MIN_TRADING_DAYS = 3
INDEX_OF = {"kr": "KS11", "us": "^GSPC"}
# 등락률이 아니라 차이(포인트)로 읽는 것 — 금리는 4.83%에서 4.87%로 "0.04%p 올랐다"고 말한다.
POINT_TICKERS = {"^TNX", "^TYX", "^VIX"}


def _kst_today() -> dt.date:
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=9)).date()


def latest_price_file(market: str, on_or_before: dt.date, data_dir: Path | None = None) -> Path | None:
    """`on_or_before`까지의 가장 최근 시세 파일."""
    folder = data_dir or DATA
    best: tuple[str, Path] | None = None
    for path in folder.glob(f"price_{market}_*.json"):
        m = re.search(r"_(\d{4}-\d{2}-\d{2})\.json$", path.name)
        if not m or m.group(1) > on_or_before.isoformat():
            continue
        if best is None or m.group(1) > best[0]:
            best = (m.group(1), path)
    return best[1] if best else None


def week_bounds(trading_date: dt.date) -> tuple[dt.date, dt.date]:
    """그 거래일이 속한 주의 월요일과 금요일."""
    monday = trading_date - dt.timedelta(days=trading_date.weekday())
    return monday, monday + dt.timedelta(days=4)


def _history(entry: dict) -> list[tuple[str, float]]:
    history = entry.get("history") or {}
    dates = [str(d) for d in (history.get("dates") or [])]
    closes = history.get("close") or []
    if len(dates) != len(closes):
        return []
    return [(d, float(c)) for d, c in zip(dates, closes) if c is not None]


def _week_of(entry: dict, monday: dt.date, end: dt.date) -> dict | None:
    """한 항목의 주간 숫자. 전주 종가나 이번 주 종가가 이력에 없으면 None."""
    rows = _history(entry)
    start, stop = monday.isoformat(), end.isoformat()
    before = [c for d, c in rows if d < start]
    inside = [(d, c) for d, c in rows if start <= d <= stop]
    if not before or not inside:
        return None
    prev_close = before[-1]
    last_date, last_close = inside[-1]
    path = []
    ref = prev_close
    for day, close in inside:
        path.append({"date": day, "close": close,
                     "pct": round((close / ref - 1) * 100, 2) if ref else None})
        ref = close
    highs = max(c for _, c in inside)
    lows = min(c for _, c in inside)
    ticker = str(entry.get("ticker") or "")
    return {
        "ticker": ticker, "name": str(entry.get("name") or ticker),
        "sector": entry.get("sector"), "source": entry.get("source"),
        "unit": entry.get("unit") or "",
        "prev_close": prev_close, "last_close": last_close, "last_date": last_date,
        "week_pct": round((last_close / prev_close - 1) * 100, 2) if prev_close else None,
        "week_diff": round(last_close - prev_close, 4),
        "week_high": highs, "week_low": lows,
        "path": path,
        "points": ticker in POINT_TICKERS,
    }


def compute(price_data: dict, market: str) -> dict:
    """시세 파일 하나에서 그 주의 결산 숫자를 만든다."""
    trading_date = dt.date.fromisoformat(str(price_data["trading_date"]))
    monday, friday = week_bounds(trading_date)
    end = min(friday, trading_date)
    index_ticker = INDEX_OF.get(market)
    macro = [_week_of(e, monday, end) for e in (price_data.get("macro") or {}).values()]
    macro = [m for m in macro if m]
    index_row = next((m for m in macro if m["ticker"] == index_ticker), macro[0] if macro else None)
    trading_days = [p["date"] for p in index_row["path"]] if index_row else []
    stocks = [_week_of(e, monday, end) for e in (price_data.get("watchlist") or {}).values()]
    stocks = [s for s in stocks if s and s["week_pct"] is not None]
    ranked = sorted(stocks, key=lambda s: s["week_pct"], reverse=True)
    sectors: dict[str, list[dict]] = {}
    for s in stocks:
        if s.get("sector") and s.get("source", "core") == "core":
            sectors.setdefault(str(s["sector"]), []).append(s)
    sector_rows = []
    for name, rows in sectors.items():
        avg = sum(r["week_pct"] for r in rows) / len(rows)
        sector_rows.append({"name": name, "avg_pct": round(avg, 2),
                            "up": sum(1 for r in rows if r["week_pct"] > 0),
                            "down": sum(1 for r in rows if r["week_pct"] < 0),
                            "stocks": [r["name"] for r in rows]})
    sector_rows.sort(key=lambda r: r["avg_pct"], reverse=True)
    return {
        "market": market, "trading_date": trading_date.isoformat(),
        "week": {"start": monday.isoformat(), "end": end.isoformat()},
        "trading_days": trading_days,
        "thin": len(trading_days) < MIN_TRADING_DAYS,
        "macro": macro,
        "top_up": [s for s in ranked[:5] if s["week_pct"] > 0],
        "top_down": [s for s in ranked[::-1][:5] if s["week_pct"] < 0],
        "sectors": sector_rows,
        "stocks": ranked,
        "breadth": {"up": sum(1 for s in stocks if s["week_pct"] > 0),
                    "down": sum(1 for s in stocks if s["week_pct"] < 0),
                    "total": len(stocks)},
    }


def _fmt_value(value: float, unit: str, points: bool = False) -> str:
    if points:
        return f"{value:,.2f}"
    if unit == "원" or abs(value) >= 10000:
        return f"{value:,.0f}{unit}"
    return f"{value:,.2f}{unit}"


def _kdate(day: str) -> str:
    d = dt.date.fromisoformat(day)
    return f"{d.month}월 {d.day}일"


def render_text(result: dict) -> str:
    market = result["market"].upper()
    week = result["week"]
    lines = [f"[주간 결산] {market} · {_kdate(week['start'])}~{_kdate(week['end'])} "
             f"({week['start']} ~ {week['end']}) · 거래일 {len(result['trading_days'])}일"
             + (" · ⚠ 거래일이 3일 미만이라 결산을 쓰지 않습니다" if result["thin"] else "")]
    lines.append("  지수·환율 (주간 = 전주 마지막 종가 대비)")
    for m in result["macro"]:
        change = (f"{m['week_diff']:+.2f}p" if m["points"] else f"{m['week_pct']:+.2f}%")
        days = " ".join(f"{_kdate(p['date'])[-3:].strip()} {p['pct']:+.2f}%" for p in m["path"]) if not m["points"] else ""
        lines.append(f"    {m['name']:<10} {_fmt_value(m['last_close'], m['unit'], m['points']):>12}  주간 {change:>8}  "
                     f"전주 {_fmt_value(m['prev_close'], m['unit'], m['points'])} → 주중 최고 "
                     f"{_fmt_value(m['week_high'], m['unit'], m['points'])} 최저 {_fmt_value(m['week_low'], m['unit'], m['points'])}")
        if days:
            lines.append(f"    {'':<10} 날짜별 {days}")
    b = result["breadth"]
    lines.append(f"  종목 폭: 오른 종목 {b['up']} / 내린 종목 {b['down']} (전체 {b['total']})")
    if result["sectors"]:
        lines.append("  업종(코어 종목 평균)")
        for s in result["sectors"]:
            lines.append(f"    {s['name']:<8} {s['avg_pct']:+.2f}%  오른 종목 {s['up']}/{s['up'] + s['down']}  ({', '.join(s['stocks'])})")
    lines.append("  주간 상승 상위")
    for s in result["top_up"]:
        lines.append(f"    {s['name']:<12} {s['week_pct']:+.2f}%  {_fmt_value(s['last_close'], s['unit'])}"
                     + ("  (동적 편입)" if s.get("source") == "dynamic" else ""))
    lines.append("  주간 하락 상위")
    for s in result["top_down"]:
        lines.append(f"    {s['name']:<12} {s['week_pct']:+.2f}%  {_fmt_value(s['last_close'], s['unit'])}"
                     + ("  (동적 편입)" if s.get("source") == "dynamic" else ""))
    lines.append("  전체 (주간 등락 순)")
    for s in result["stocks"]:
        lines.append(f"    {s['name']:<12} {s['week_pct']:+.2f}%")
    return "\n".join(lines)


def augment_from_daily_files(price_data: dict, market: str, data_dir: Path | None = None) -> list[str]:
    """3개월 이력(`history`)이 없는 항목(원/달러 환율처럼 실시간 호가로 받는 것)에, 우리가 날마다 커밋한
    시세 파일들의 종가를 이력으로 붙인다. 첫 실행(2026-09-12)에서 루틴이 환율 주간 변화를 못 받아
    날짜별 파일을 손으로 뒤졌다 — 같은 자료를 여기서 미리 이어 붙인다. 붙인 항목 이름을 돌려준다."""
    folder = data_dir or DATA
    files = []
    for path in folder.glob(f"price_{market}_*.json"):
        m = re.search(r"_(\d{4}-\d{2}-\d{2})\.json$", path.name)
        if m and m.group(1) <= str(price_data.get("trading_date", "")):
            files.append((m.group(1), path))
    files.sort()
    targets = [(g, k, e) for g in ("macro", "watchlist") for k, e in (price_data.get(g) or {}).items()
               if not _history(e) and e.get("price") is not None]
    if not targets or not files:
        return []
    daily: dict[str, dict] = {}
    for day, path in files:
        try:
            daily[day] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
    added = []
    for group, key, entry in targets:
        dates, closes = [], []
        for day in sorted(daily):
            other = (daily[day].get(group) or {}).get(key)
            if other and other.get("price") is not None:
                dates.append(str(other.get("trading_date") or day)); closes.append(float(other["price"]))
        if len(closes) >= 2:
            entry["history"] = {"dates": dates, "close": closes, "source": "daily_files"}
            added.append(str(entry.get("name") or key))
    return added


def run(markets: list[str], on_or_before: dt.date, data_dir: Path | None = None) -> dict[str, dict]:
    results = {}
    for market in markets:
        path = latest_price_file(market, on_or_before, data_dir)
        if path is None:
            raise FileNotFoundError(f"{market}: {on_or_before}까지의 시세 파일이 없습니다.")
        price_data = json.loads(path.read_text(encoding="utf-8"))
        augmented = augment_from_daily_files(price_data, market, data_dir)
        result = compute(price_data, market)
        result["history_from_daily_files"] = augmented
        result["price_file"] = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
        results[market] = result
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--market", choices=["kr", "us"], action="append",
                        help="기본은 두 시장 모두")
    parser.add_argument("--date", help="이 날짜(KST)까지의 가장 최근 시세 파일로 (기본: 오늘)")
    parser.add_argument("--json", type=Path, help="결과 JSON을 이 경로에 남긴다")
    parser.add_argument("--allow-thin", action="store_true", help="거래일 3일 미만이어도 멈추지 않는다(시험용)")
    args = parser.parse_args(argv)
    on_or_before = dt.date.fromisoformat(args.date) if args.date else _kst_today()
    results = run(args.market or ["kr", "us"], on_or_before)
    for result in results.values():
        print(render_text(result))
        print(f"  시세 파일: {result['price_file']}")
        print()
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"JSON: {args.json}")
    thin = [m for m, r in results.items() if r["thin"]]
    if thin and not args.allow_thin:
        print(f"⚠ 거래일이 {MIN_TRADING_DAYS}일 미만인 시장: {', '.join(thin)} — 이번 주 결산은 쓰지 않습니다.")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
