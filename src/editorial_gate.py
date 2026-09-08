"""시황 원고의 **커밋 전 관문**. 루틴은 이것이 "통과"를 찍은 뒤에만 커밋합니다.

왜 생겼는가 (2026-09-08)
------------------------
제목·소제목 지적을 사용자가 세 번(9/4·9/6·9/8) 했다. 규칙은 문서에 있었고 발행
단계에 검사도 있었는데, 발행 단계의 검사는 **루틴이 이미 끝난 뒤**에 돈다. 걸리면
아무도 못 고친 채 그날 글만 빠지고, 안 걸리면 아쉬운 제목이 그대로 나갔다. 그래서
사용자가 말했다 — "발행을 멈추게 하지 말고 제목을 제대로 쓰게 해, 처음부터."

이 관문은 루틴이 **원고를 쓴 직후, 커밋하기 전에** 돌리는 것이다. 걸리면 고치고
다시 돌린다. 발행 단계(`publish_editorial`)는 같은 검사를 경고로만 남기고 글을
막지 않는다(숫자 대조만 막는다).

무엇을 보는가
-------------
1. 문체 — `editorial_quality.collect_issues` (어색한 표현, 지어낸 말)
2. 제목·소제목 — `editorial_title.collect_issues(kind="시황")` (모든 글 공통 규칙: 후킹 장치,
   등락률 둘 이상 금지, 8절 이상, 소제목 32자 이하)
3. 판단·어제·초보자 — `editorial_judgment` (Fermata's Take 세 문장 + 확인 지점, 어제 판정,
   초보자 설명, 포지션 화법 금지, 증권사·기관 견해 한 건, 최근 다섯 편과 같은 문장 금지)
4. 숫자 — `editorial_facts` (원고의 등락률이 시세와 맞는지, 1위 종목을 다뤘는지)
5. 영어판 문체 — `editorial_quality_en`
6. 시각자료 — 본문 `graphic`을 실제로 그려 보고(틀린 티커·없는 이력은 여기서 드러남),
   `photo`가 승인 풀에 있는지 보고, 합계가 최소 개수 이상인지 센다.
   그린 그림은 `output/gate/<market>_<date>/`에 남긴다 — **`Read`로 직접 본다.**

    python -m src.editorial_gate editorial/kr_2026-09-08.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src import (
    data_graphics,
    editorial_facts,
    editorial_judgment,
    editorial_quality,
    editorial_quality_en,
    editorial_title,
    photo_pool,
)

ROOT = Path(__file__).resolve().parent.parent
GATE_DIR = ROOT / "output" / "gate"

# 표지를 뺀 본문 시각자료(그래픽 + 사진 + 인사이트 사진) 최소 개수. 벤치마크 최근
# 104편의 편당 이미지는 중앙값 10(p25 6). 우리 9/8 글은 4였다. 다섯은 하한이지 목표가
# 아니다 — 지수·주인공 종목 3개월 흐름, 숫자 카드, 업종, 종목 목록, 수급, 사진을
# 그날 이야기에 맞게 고르면 저절로 넘는다.
MIN_VISUALS = 5


def _previous_price_data(market: str, date_str: str) -> dict | None:
    files = sorted(
        p for p in (ROOT / "data").glob(f"price_{market}_*.json")
        if p.stem < f"price_{market}_{date_str}"
    )
    return json.loads(files[-1].read_text(encoding="utf-8")) if files else None


def _heading_lines(ko: dict) -> list[str]:
    lines = []
    for index, section in enumerate(ko.get("narrative") or [], start=1):
        heading = str(section.get("heading", "")).strip()
        bare = editorial_title._HEADING_NUMBER.sub("", heading)
        lines.append(f"  {index:>2}. {heading}  ({len(bare)}자)")
    return lines


def run(path: Path, min_visuals: int = MIN_VISUALS,
        render_dir: Path | None = None) -> tuple[list[str], list[str]]:
    """(문제 목록, 요약 줄) — 문제 목록이 비어 있으면 통과."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("kind") == "feature" or "price_data" not in doc:
        raise SystemExit("이 관문은 시황 원고용입니다. 기준표·프리뷰는 `python -m src.feature_gate`.")
    market, date_str = doc["market"], doc["date"]
    price_data = doc["price_data"]
    ko, en = doc["ko"], doc.get("en")
    issues: list[str] = []
    summary: list[str] = []

    issues += [f"문체 — {i}" for i in editorial_quality.collect_issues(ko)]
    notes: list[str] = []
    issues += [f"제목·소제목 — {i}" for i in editorial_title.collect_issues(ko, price_data, kind="시황", notes_out=notes)]
    summary += [f"(참고) {n}" for n in notes]
    j_issues, j_notes = editorial_judgment.collect_issues(
        doc, editorial_judgment.previous_manuscript(market, date_str),
        editorial_judgment.previous_manuscripts(market, date_str))
    issues += [f"판단·어제·초보자 — {i}" for i in j_issues]
    summary += [f"(참고) {n}" for n in j_notes]
    try:
        editorial_facts.validate(ko, price_data, lang="ko")
    except Exception as exc:  # noqa: BLE001 - 종류가 무엇이든 목록에 담는다
        issues.append(f"숫자(한국어) — {exc}")
    if en:
        try:
            editorial_quality_en.validate_generated(en)
        except Exception as exc:  # noqa: BLE001
            issues.append(f"영어 문체 — {exc}")
        try:
            editorial_facts.validate(en, price_data, lang="en")
        except Exception as exc:  # noqa: BLE001
            issues.append(f"숫자(영어) — {exc}")

    # 시각자료: 실제로 그려 본다.
    render_dir = render_dir or (GATE_DIR / f"{market}_{date_str}")
    render_dir.mkdir(parents=True, exist_ok=True)
    graphics, photos, story_photos = 0, 0, 0
    rendered: list[str] = []
    watchlist = price_data.get("watchlist") or {}
    used: set[str] = set()
    for index, section in enumerate(ko.get("narrative") or [], start=1):
        spec = section.get("graphic")
        if isinstance(spec, dict) and spec.get("kind"):
            kind = spec["kind"]
            options = {k: v for k, v in spec.items() if k not in ("kind", "url", "alt")}
            if kind == "two_day_compare":
                options["previous"] = _previous_price_data(market, date_str)
            try:
                out = render_dir / f"{index:02d}-{kind}.png"
                data_graphics.build(kind, price_data, out, **options)
                graphics += 1
                rendered.append(str(out))
            except Exception as exc:  # noqa: BLE001 - 어떤 실패든 목록에 담는다
                issues.append(f"그래픽(본문 {index}, {kind}) — {exc}")
        elif spec:
            issues.append(f"그래픽(본문 {index}) — graphic에 kind가 없습니다: {spec!r}")
        photo = section.get("photo")
        if isinstance(photo, dict):
            if str(photo.get("url", "")).startswith("http"):
                photos += 1
            else:
                ticker = str(photo.get("ticker") or "")
                entry = watchlist.get(ticker)
                picked = None
                if entry:
                    entry = {**entry, "ticker": entry.get("ticker") or ticker}
                    picked = photo_pool.pick(entry, date_str, exclude=used)
                if picked:
                    used.add(picked["id"])
                    photos += 1
                else:
                    issues.append(
                        f"사진(본문 {index}) — '{ticker}'에 맞는 승인 사진이 없습니다. 코어 종목의 "
                        "티커를 쓰거나(동적 편입 종목은 사진을 붙이지 않습니다) photo를 빼십시오.")
        elif photo:
            issues.append(f"사진(본문 {index}) — photo는 {{\"ticker\": ...}} 또는 {{\"url\": ...}}입니다: {photo!r}")
    for story in (ko.get("insight_section") or {}).get("stories") or []:
        image = story.get("image")
        if isinstance(image, dict) and str(image.get("url", "")).startswith("http"):
            story_photos += 1
        elif story.get("image_query"):
            # 발행 단계가 코어 종목명으로 풀에서 고른다. 여기서는 셀 수만 있으면 된다.
            query = str(story["image_query"]).lower()
            for entry in watchlist.values():
                if entry.get("source") == "dynamic":
                    continue
                if str(entry.get("name", "")).lower() in query or str(entry.get("name_en", "")).lower() in query:
                    if photo_pool.pick(entry, date_str, exclude=used):
                        story_photos += 1
                    break
    visuals = graphics + photos + story_photos
    if visuals < min_visuals:
        issues.append(
            f"시각자료 — {visuals}개입니다(본문 그래픽 {graphics}, 본문 사진 {photos}, 인사이트 사진 "
            f"{story_photos}). 최소 {min_visuals}개, 권장 6~10개. price_history(지수·주인공 종목)·"
            "number_cards·sector_bars·movers_list·investor_flows·본문 photo를 그날 이야기에 맞게 "
            "더하십시오 — 장식이 아니라 본문이 설명하는 것에 붙입니다.")

    summary.append(f"제목: {ko.get('title')}")
    summary.append(f"본문 {len(ko.get('narrative') or [])}절:")
    summary += _heading_lines(ko)
    summary.append(f"시각자료 {visuals}개 (본문 그래픽 {graphics} · 본문 사진 {photos} · 인사이트 사진 {story_photos})")
    if rendered:
        summary.append("그린 그림 — Read 툴로 직접 보십시오:")
        summary += [f"  {p}" for p in rendered]
    return issues, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("path", type=Path)
    parser.add_argument("--min-visuals", type=int, default=MIN_VISUALS)
    args = parser.parse_args(argv)
    issues, summary = run(args.path, min_visuals=args.min_visuals)
    print("\n".join(summary))
    if issues:
        print(f"\n관문 실패 — {len(issues)}건. 고쳐서 다시 돌리십시오. 통과 전에는 커밋하지 않습니다.")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("\n관문 통과 — 제목·소제목을 한 번 더 소리 내어 읽고, 그림을 Read로 본 뒤 커밋하십시오.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
