"""한국장 시세 파일의 빈 외국인·기관 수급을 날짜가 맞는 값으로 채운다 (2026-09-26).

    python -m scripts.fill_kr_flows            # 가장 최근 한국장 파일 하나(아침 미국장 수집이 부른다)
    python -m scripts.fill_kr_flows --all      # API가 주는 최근 15거래일 안의 파일 전부(한 번 되채우기용)

왜 필요한가: 네이버 수급 API는 장 마감 직후(16:20)에 아직 전날 줄만 준다. 그래서 그날 시세 파일의 종목별 수급은
날짜 대조에서 버려져 늘 비고(2026-09-18부터 일부러 — 틀린 날짜 값보다 빈 값), "다음 날 재수집이 채운다"는 장치는
거래일이 바뀌면 새 파일을 쓰므로 한 번도 돌지 않았다(9/11~9/22 여덟 파일이 0/27). 다음 날 아침(미국장 수집, 07:20 KST)에는
전날 줄이 반드시 나와 있으므로 여기서 채운다. 가격은 건드리지 않고 **빈 칸만** 채운다(시세 파일은 한 번만 쓴다는 규칙).
한국장 글은 그날 종목별 수급을 쓸 수 없고, 대신 전 거래일 파일의 확정 수급을 '어제'로 쓴다(`docs/routine_kr.md`).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src import fetch_foreign_flows

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
FIELDS = ("foreign_net", "institution_net", "foreign_ratio")
MAX_DAYS = 15                      # API가 한 번에 주는 거래일 수


def _empty(entry: dict) -> bool:
    return any(entry.get(key) in (None, "") for key in FIELDS)


def fill(path: Path, fetch=fetch_foreign_flows.fetch_rows) -> tuple[int, int, int]:
    """파일 하나를 채운다 → (채운 종목, 이미 있던 종목, 못 채운 종목). 바뀐 것이 있을 때만 쓴다."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    trading_date = str(doc.get("trading_date") or path.stem.split("_")[-1])
    filled = kept = missed = 0
    for ticker, entry in (doc.get("watchlist") or {}).items():
        if not _empty(entry):
            kept += 1
            continue
        row = fetch_foreign_flows.row_for(fetch(ticker, MAX_DAYS), trading_date)
        if not row:
            missed += 1
            continue
        for key in FIELDS:
            if entry.get(key) in (None, ""):
                entry[key] = row[key]
        filled += 1
    if filled:
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")   # main.py와 같은 꼴
    return filled, kept, missed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help=f"최근 {MAX_DAYS}거래일 안의 파일 전부")
    args = parser.parse_args(argv)
    files = sorted(DATA.glob("price_kr_*.json"))
    if not files:
        raise SystemExit("한국장 시세 파일이 없습니다.")
    targets = files[-MAX_DAYS:] if args.all else files[-1:]
    total_missed = 0
    cache: dict[str, list | None] = {}

    def cached(ticker: str, size: int):        # 종목마다 한 번만 받는다(15일치 한 번이면 모든 파일에 쓴다)
        if ticker not in cache:
            cache[ticker] = fetch_foreign_flows.fetch_rows(ticker, size)
        return cache[ticker]

    for path in targets:
        filled, kept, missed = fill(path, fetch=cached)
        total_missed += missed
        print(f"{path.name}: 수급 채움 {filled} · 이미 있음 {kept} · 못 채움 {missed}")
    if total_missed:
        # 조용한 실패 금지 — 못 채운 것은 세어 알린다(그날 줄이 아직 없거나 조회 실패).
        print(f"[안내] 수급을 못 채운 종목 {total_missed}개 — 그날 줄이 아직 없거나 조회에 실패했습니다.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
