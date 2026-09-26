"""제목 후보 셋의 점수를 매겨 가장 먼 것을 고른다 (2026-09-18, 사장님 "a진행").

    python -m scripts.title_pick us "후보1" "후보2" "후보3"              # 쓰기 전: 지금 피드 기준
    python -m scripts.title_pick preview "후보1" "후보2" "후보3" --price data/price_us_2026-09-17.json
    python -m scripts.title_pick --doc editorial/us_2026-09-17.json     # 원고의 ko.title_candidates를 관문과 같은 눈으로

왜: 관문은 "안 되는 것"을 거르는 문이라 쓰는 쪽은 늘 그 문을 넘는 최소를 찾았다(9/17: 예문 35개 중 가장 쉬운
하나가 시황 28편 중 11편). 그래서 문을 고르는 문으로 바꿨다 — 후보 셋을 축을 달리해 쓰고, 독자 피드
(`src/title_feed.py`)와의 거리 점수(`editorial_title.title_distance`)가 가장 높은 것을 제목으로 삼는다.
관문(`candidate_issues`)이 같은 계산으로 확인하므로, 여기서 1등인 후보를 `ko.title`에 적으면 관문에서 그
항목으로 막히지 않는다. 점수는 '다름'을 잴 뿐 '좋음'을 재지 않는다 — 후보는 셋 다 나가도 되는 제목이어야 한다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src import editorial_title, title_feed

ROOT = Path(__file__).resolve().parent.parent
KINDS = {"kr": "시황", "us": "시황", "preview": "프리뷰", "checkpoint": "기준표",
         "weekly": "주간 결산", "weekahead": "다음 주 일정", "event": "이벤트"}


def render(candidates: list[str], recent: list[str], price_data: dict | None, kind: str,
           chosen: str | None = None) -> str:
    lines = ["== 독자가 보는 최근 네 편(이 제목 바로 위) =="]
    lines += [f"  {r}" for r in recent[-4:]] or ["  (없음)"]
    ranked = editorial_title.rank_candidates(candidates, recent, price_data, kind)
    lines.append("")
    lines.append(f"== 후보 {len(ranked)}개 — 점수 높은 순 ==")
    for i, r in enumerate(ranked, 1):
        axes = "·".join(sorted(editorial_title.title_axes_all(r["title"]))) or "없음"
        state = "통과" if r["ok"] else "막힘"
        lines.append(f"{i}. [{state} · 점수 {r['score']:+d}] {r['title']}   (축: {axes})")
        for w in r["why"]:
            lines.append(f"      {w}")
        for issue in r["issues"][:2]:
            lines.append(f"      ✗ {issue[:110]}")
    passing = [r for r in ranked if r["ok"]]
    lines.append("")
    if not passing:
        lines.append("고를 것: 없음 — 통과하는 후보가 없습니다. 위 ✗ 이유를 보고 후보를 다시 쓰세요.")
    else:
        best = passing[0]
        lines.append(f"고를 것: 「{best['title']}」 (점수 {best['score']:+d}) → `ko.title`에, 후보 전부를 `ko.title_candidates`에.")
        if chosen is not None and chosen != best["title"]:
            mine = next((r for r in ranked if r["title"] == chosen), None)
            if mine is None:
                lines.append(f"지금 제목 「{chosen}」은 후보에 없습니다 — 관문이 막습니다.")
            elif mine["ok"] and mine["score"] < best["score"]:
                lines.append(f"지금 제목 「{chosen}」은 점수 {mine['score']:+d} — 관문이 「{best['title']}」로 바꾸라고 막습니다.")
    sigs = {frozenset(editorial_title.title_axes_all(c)) for c in candidates}
    if len(candidates) < editorial_title.CANDIDATE_MIN:
        lines.append(f"후보가 {len(candidates)}개 — 셋 이상이어야 관문을 통과합니다.")
    if len(sigs) < 2:
        lines.append("후보의 축이 모두 같습니다 — 둘 이상의 축으로 나눠 쓰세요(관문이 막습니다).")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("which", nargs="?", choices=sorted(KINDS), help="어느 글의 제목인가(피드 기준은 같다)")
    ap.add_argument("candidates", nargs="*", help="제목 후보 셋 이상")
    ap.add_argument("--price", type=Path, help="시세 파일 — 등락률 반올림 검사에 쓴다")
    ap.add_argument("--doc", type=Path, help="원고 파일 — ko.title_candidates·ko.title·시세를 원고에서 읽는다")
    a = ap.parse_args(argv)
    if a.doc:
        doc = json.loads(a.doc.read_text(encoding="utf-8"))
        ko = doc.get("ko") or {}
        series = title_feed.series_of(doc)
        kind = {"한국장": "시황", "미국장": "시황"}.get(series or "", series or "시황")
        recent = title_feed.feed_titles(doc, a.doc)
        candidates = [str(c) for c in (ko.get("title_candidates") or []) if str(c).strip()]
        if not candidates:
            print(f"{a.doc}: `ko.title_candidates`가 없습니다 — 후보 셋 이상을 적으세요.")
            return 1
        print(render(candidates, recent, doc.get("price_data"), kind, chosen=str(ko.get("title") or "")))
        return 0
    if not a.which or not a.candidates:
        ap.error("<kr|us|preview|checkpoint|weekly|weekahead|event> 와 후보를 주거나 --doc <원고>를 주세요.")
    price = json.loads(a.price.read_text(encoding="utf-8")) if a.price else None
    # 관문과 같은 목록(최근 5편, 2026-09-26) — 전에는 10편과 비교해 같은 후보라도 점수가 달라, 여기서 동점인 후보가
    # 관문에서 '가장 먼 후보가 아니다'로 막힐 수 있었다(kr 9/21 관문 [5,2,4] vs 여기 [4,2,4]).
    recent = title_feed.feed_titles()
    print(render([c for c in a.candidates if c.strip()], recent, price, KINDS[a.which]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
