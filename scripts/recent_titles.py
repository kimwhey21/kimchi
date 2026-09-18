"""쓰기 전에 읽는 "최근 글의 틀" 한 장 (2026-09-09, 사용자: "앞으로 두 번 수정하지 않게").

관문(editorial_gate·feature_gate)은 최근 글과 뼈대·주인공·어구가 겹치면 막는다. 막힌 뒤에 고치는 것보다
쓰기 전에 보는 것이 싸다 — 이 명령이 최근 다섯 편 제목과 소제목의 꼴을 보여 준다.

**2026-09-18부터 시황·프리뷰·기준표·주간·이벤트는 "같은 목록"이 아니라 독자가 보는 한 줄을 본다**
(`src/title_feed.py` — 한국장·미국장·프리뷰·기준표·주간·이벤트가 올라가는 순서로 섞인 것). 사장님
"제목 상태 왜 이래 적용안된거같은데": 목록별로는 다 통과했는데 피드에는 '은행주'가 셋, '3년 2개월 만의
금리 인상'이 둘이었다. kr·us·preview 어느 이름으로 불러도 같은 한 줄이 나온다. 가이드·잡지는 같은 시리즈.

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

from src import editorial_title, title_feed

ROOT = Path(__file__).resolve().parent.parent
LISTS = {
    "kr": "editorial/kr_*.json", "us": "editorial/us_*.json",
    "checkpoint": "editorial/features/*.json", "preview": "editorial/previews/*.json",
    "weekly": "editorial/weekly/review_*.json",      # 토요일 주간 결산 (2026-09-12)
    "weekahead": "editorial/weekly/ahead_*.json",    # 일요일 다음 주 일정 (2026-09-12)
    "guide": "editorial/guides/ko_*.json",           # 한국어 상시 가이드 (2026-09-12, 유입 편성)
    "guide_en": "editorial/guides/en_*.json",        # 영어 가이드
    "event": "editorial/events/*.json",              # 정기 이벤트 글
    "magazine": "editorial/magazine/*.json",         # 두 번째 네이버 블로그 잡지 글 (2026-09-13)
}
# 독자 피드 한 줄로 보는 이름들 — 어느 이름으로 불러도 같은 목록이다(2026-09-18).
FEED_LISTS = {"kr", "us", "checkpoint", "preview", "weekly", "weekahead", "event"}


def load(which: str, count: int = 5) -> list[dict]:
    if which in FEED_LISTS:
        # 독자가 보는 한 줄 — 올라가는 시각 순. 다음 글(아직 없는 글) 바로 위에 보일 다섯 편이다.
        return [{"file": r["path"].name, "date": r["slot"].strftime("%m-%d %H:%M ") + r["series"], "doc": r["doc"]}
                for r in title_feed.rows_before(count=count)]
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
    if which in FEED_LISTS:
        lines = [f"== 독자가 보는 최근 {len(rows)}편(한국장·미국장·프리뷰·기준표·주간 한 줄, 올라간 순서) — "
                 "이 글들과 뼈대·주인공·어구가 겹치면 관문이 막습니다 ==", ""]
    else:
        lines = [f"== {which} 최근 {len(rows)}편 — 이 글들과 뼈대가 겹치면 관문이 막습니다 ==", ""]
    for row in rows:
        ko = row["doc"].get("ko") or {}
        frame = editorial_title.title_frame(str(ko.get("title", "")))
        tags = [t for t, on in (("대비", frame["contrast"]), ("날짜", frame["date"])) if on]
        lines.append(f"[{row['date']}] {ko.get('title', '')}")
        axes = "·".join(frame["axes"]) or "없음"
        lines.append(f"    꼴: {frame['ending']} · 끝말 '{frame['last']}' · 축: {axes}"
                     + (" · 답 노출형" if frame["revealed"] else "") + (f" · {'·'.join(tags)}" if tags else ""))
        heads = [str(s.get("heading", "")) for s in ko.get("narrative") or []]
        shapes = [editorial_title.heading_shape(h) for h in heads]
        lines.append(f"    소제목 {len(heads)}개: 문장 {sum(1 for s in shapes if s.endswith('문장'))} · "
                     f"이름표 {shapes.count('이름표')} · 질문 {shapes.count('질문')}")
    last = editorial_title.last_word(str((rows[-1]["doc"].get("ko") or {}).get("title", "")))
    contrast_used = any(editorial_title.title_frame(str((r["doc"].get("ko") or {}).get("title", "")))["contrast"] for r in rows)
    # 축 분포(2026-09-17): 관문(axis_issues)이 최근 네 편 + 이 제목에서 본다.
    last4 = [str((r["doc"].get("ko") or {}).get("title", "")) for r in rows[-4:]]
    missing = [a for a in editorial_title._AXIS if not any(editorial_title._AXIS[a].search(t) for t in last4)]
    revealed_used = any(editorial_title.revealed_reason(t) for t in last4)
    # 주인공 반복(2026-09-18): 최근 네 편에 이미 둘이면 이번 제목에 쓸 수 없다(다섯 편에 셋).
    counts: dict[str, int] = {}
    for t in last4:
        for name in editorial_title.title_subjects(t):
            counts[name] = counts.get(name, 0) + 1
    crowded = [f"'{n}'({c}번)" for n, c in sorted(counts.items(), key=lambda kv: -kv[1]) if c >= 2]
    lines += ["", "이번 글에서 피할 것:",
              f"- '{last}'로 끝내지 않기(바로 앞 글의 끝말)",
              "- 대비 꼴('…했는데 …는 오히려') " + ("쓰지 않기 — 최근 다섯 편에 이미 있음" if contrast_used else "은 가능(최근 다섯 편에 없음)"),
              "- 답 노출형('…, 이유는 B입니다') " + ("쓰지 않기 — 최근 네 편에 이미 있음" if revealed_used else "은 가능(한 번)"),
              "- 주인공 반복: " + (", ".join(crowded) + " — 최근 네 편에 이미 둘, 이번 제목에 쓰면 관문이 막습니다"
                               if crowded else "최근 네 편에 두 번 나온 주인공 없음"),
              "- 이미 쓴 어구(공백 빼고 7자 이상)를 그대로 다시 쓰지 않기 — `3년 2개월 만의 금리 인상`이 이틀 연속 나갔음",
              "- 소제목은 문장 열에 여섯까지, 이름표 둘 이상, '이름, …' 꼴 둘까지, 같은 말로 끝나는 문장 둘까지",
              "", "이번 제목에 넣을 것(시황·프리뷰는 관문이 막습니다):"]
    if missing:
        for a in missing:
            lines.append(f"- {a} 축 (최근 네 편에 없음) — 예: `{editorial_title.AXIS_PICKS[a][0]}`")
    else:
        lines.append("- 시간·질문·독자 축이 다 있음 — 어느 축이든 됩니다. 1인칭·내 돈·인용 축도 예문집에 있습니다.")
    if which in FEED_LISTS:
        # 2026-09-18 "a진행": 관문은 거르는 문이 아니라 고르는 문 — 후보 셋 중 피드와 가장 먼 것을 제목으로 요구한다.
        lines.append(f"- **후보 셋 이상을 축을 달리해 쓰고** `python -m scripts.title_pick {which} \"후보1\" \"후보2\" \"후보3\"`로 "
                     "점수를 본 뒤, 가장 높은 것을 `ko.title`에·셋 다 `ko.title_candidates`에 적습니다(관문이 같은 계산으로 확인합니다).")
    if which == "preview":
        # 2026-09-17 밤: "어느 축이든 됩니다"를 읽은 루틴이 어젯밤 요약 제목을 냈다. 프리뷰는 늘 앞을 본다.
        lines.append("- **프리뷰는 시간 축(오늘 밤·내일·새벽) 또는 독자 축(보세요·볼 것)이 필수입니다** — 관문이 막습니다. "
                     "어젯밤을 요약하는 제목(`…급락, …는 오히려 …했습니다`)은 시황 제목이지 프리뷰 제목이 아닙니다.")
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
