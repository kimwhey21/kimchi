"""쓰기 전에 읽는 "최근 글의 틀" 한 장 (2026-09-09, 사용자: "앞으로 두 번 수정하지 않게").

관문(editorial_gate·feature_gate)은 최근 글과 뼈대가 겹치면 막는다. 막힌 뒤에 고치는 것보다
쓰기 전에 보는 것이 싸다 — 이 명령이 같은 목록의 최근 다섯 편 제목과 소제목의 꼴을 보여 준다.

    python -m scripts.recent_titles kr          # 한국장 시황 최근 5편
    python -m scripts.recent_titles us          # 미국장 시황 최근 5편
    python -m scripts.recent_titles checkpoint  # Checkpoint 목록(기준표) 최근 5편
    python -m scripts.recent_titles preview     # 프리뷰 최근 5편
    python -m scripts.recent_titles weekly      # 토요일 주간 결산 최근 5편
    python -m scripts.recent_titles weekahead   # 일요일 다음 주 일정 최근 5편
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

from src import editorial_title

ROOT = Path(__file__).resolve().parent.parent
LISTS = {
    "kr": "editorial/kr_*.json", "us": "editorial/us_*.json",
    "checkpoint": "editorial/features/*.json", "preview": "editorial/previews/*.json",
    "weekly": "editorial/weekly/review_*.json",      # 토요일 주간 결산 (2026-09-12)
    "weekahead": "editorial/weekly/ahead_*.json",    # 일요일 다음 주 일정 (2026-09-12)
    "guide": "editorial/guides/ko_*.json",           # 한국어 상시 가이드 (2026-09-12, 유입 편성)
    "guide_en": "editorial/guides/en_*.json",        # 영어 가이드
    "event": "editorial/events/*.json",              # 정기 이벤트 글
}


def load(which: str, count: int = 5) -> list[dict]:
    rows = []
    for path in sorted(glob.glob(str(ROOT / LISTS[which]))):
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        rows.append((str(doc.get("date", "")), Path(path).name, doc))
    rows.sort()
    return [{"file": name, "date": date, "doc": doc} for date, name, doc in rows[-count:]]


def render(which: str, count: int = 5) -> str:
    rows = load(which, count)
    if not rows:
        return f"{which}: 원고가 없습니다."
    lines = [f"== {which} 최근 {len(rows)}편 — 이 글들과 뼈대가 겹치면 관문이 막습니다 ==", ""]
    for row in rows:
        ko = row["doc"].get("ko") or {}
        frame = editorial_title.title_frame(str(ko.get("title", "")))
        tags = [t for t, on in (("대비", frame["contrast"]), ("날짜", frame["date"])) if on]
        lines.append(f"[{row['date']}] {ko.get('title', '')}")
        lines.append(f"    꼴: {frame['ending']} · 끝말 '{frame['last']}'" + (f" · {'·'.join(tags)}" if tags else ""))
        heads = [str(s.get("heading", "")) for s in ko.get("narrative") or []]
        shapes = [editorial_title.heading_shape(h) for h in heads]
        lines.append(f"    소제목 {len(heads)}개: 문장 {sum(1 for s in shapes if s.endswith('문장'))} · "
                     f"이름표 {shapes.count('이름표')} · 질문 {shapes.count('질문')}")
    last = editorial_title.last_word(str((rows[-1]["doc"].get("ko") or {}).get("title", "")))
    contrast_used = any(editorial_title.title_frame(str((r["doc"].get("ko") or {}).get("title", "")))["contrast"] for r in rows)
    lines += ["", "이번 글에서 피할 것:",
              f"- '{last}'로 끝내지 않기(바로 앞 글의 끝말)",
              "- 대비 꼴('…했는데 …는 오히려') " + ("쓰지 않기 — 최근 다섯 편에 이미 있음" if contrast_used else "은 가능(최근 다섯 편에 없음)"),
              "- 소제목은 문장 열에 여섯까지, 이름표 둘 이상, '이름, …' 꼴 둘까지, 같은 말로 끝나는 문장 둘까지"]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("which", choices=sorted(LISTS))
    parser.add_argument("--count", type=int, default=5)
    args = parser.parse_args(argv)
    print(render(args.which, args.count))
    return 0


if __name__ == "__main__":
    sys.exit(main())
