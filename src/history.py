"""날짜마다 독립적으로 생성하다 보니 "쉽지 않은 하루였습니다" 같은 표현이나
소제목 구조가 며칠씩 반복될 수 있습니다. 최근 결과의 제목·소제목만 가볍게
기록해뒀다가, 다음 생성 때 "이건 반복하지 마세요"로 프롬프트에 넣어줍니다.
"""
from __future__ import annotations

import json
from pathlib import Path

STATE_DIR = Path(__file__).resolve().parent.parent / "state"
MAX_HISTORY = 7  # 최근 며칠치까지 기억할지


def _path(market: str) -> Path:
    return STATE_DIR / f"history_{market}.json"


def load_recent_headings(market: str, limit: int = MAX_HISTORY) -> list[str]:
    """최근 결과들의 제목/소제목을 시간순으로 이어붙인 flat 리스트로 반환합니다."""
    path = _path(market)
    if not path.exists():
        return []
    entries = json.loads(path.read_text(encoding="utf-8"))[-limit:]
    return [heading for entry in entries for heading in entry["headings"]]


def already_published(market: str, trading_date: str) -> bool:
    """이 거래일(trading_date)을 이미 발행한 적 있는지 확인합니다.

    실행한 "날짜"(date_str)가 아니라 시세 데이터가 실제로 가리키는 거래일
    기준입니다 — 휴장일(공휴일·주말)에 스케줄이 돌면 데이터 소스가 그 전
    거래일 값을 그대로 돌려주는데, 그 거래일을 이미 다른 실행에서 다뤘다면
    똑같은 내용을 새 글로 또 발행하게 되므로 main.py에서 이 함수로 걸러냅니다.
    """
    path = _path(market)
    if not path.exists():
        return False
    entries = json.loads(path.read_text(encoding="utf-8"))
    return any(e.get("trading_date") == trading_date for e in entries)


def append(market: str, date_str: str, generated: dict, trading_date: str | None = None) -> None:
    """오늘 생성 결과의 제목/소제목을 히스토리에 추가합니다."""
    STATE_DIR.mkdir(exist_ok=True)
    path = _path(market)
    entries = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []

    headings = [generated["title"]]
    headings += [section["heading"] for section in generated.get("narrative", [])]
    for key in ("theme_section", "stock_section", "outlook", "closing", "insight_section"):
        section = generated.get(key)
        if section and section.get("heading"):
            headings.append(section["heading"])

    entries = [e for e in entries if e["date"] != date_str]  # 같은 날 재실행 시 갱신
    entries.append({"date": date_str, "trading_date": trading_date, "headings": headings})
    entries = entries[-MAX_HISTORY:]
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
