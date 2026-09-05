"""발행한 원고를 벤치마크 수치와 나란히 찍습니다.

왜 필요한가
-----------
2026-09-05에 이런 일이 있었습니다. 벤치마크 본문 60편을 재서 편집 기준을 고치고,
검사 다섯 개가 통과한 글을 자동 발행하고, "다 됐다"고 보고했습니다. 그런데
사용자가 "말투가 이전과 다르지 않다"고 했고, 재보니 맞았습니다.

  문장 중앙값        30자   ← 맞음
  '습니다'로 끝      57%   ← 벤치마크 45%, 개편 전과 같음
  글 하나당 문장 수   136   ← 벤치마크 38, 개편 전보다 늘어남

측정 → 규칙 → 발행까지는 있는데 **발행된 글을 다시 재는 단계가 없었습니다.**
그래서 규칙이 실제로 먹혔는지 아무도 확인하지 않았습니다. 검사가 통과했다는 것은
"내가 encode한 것을 어기지 않았다"는 뜻이지 "벤치마크에 가까워졌다"는 뜻이
아닙니다 — AGENTS.md가 이미 경고해 둔 것을 그대로 반복했습니다.

무엇을 하지 않는가
------------------
**발행을 막지 않습니다.** 어미 비율이나 분량을 기계로 강제하면 억지로 어미만
바꾼 글이 나옵니다. 이 스크립트는 어긋난 항목을 보여줄 뿐이고, 고칠지는 사람이
판단합니다.

사용법
------
    python -m scripts.compare_to_benchmark editorial/us_2026-09-04.json
    python -m scripts.compare_to_benchmark            # editorial/ 전체
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EDITORIAL_DIR = ROOT / "editorial"

# 재테크농부 시황 본문 60편 + 제목 1,089개를 세어 나온 값입니다(2026-09-04~05).
# 원본은 프리미엄 콘텐츠라 저장소에 담지 않고 결과 수치만 남깁니다.
#
#   (측정값, 허용 하한, 허용 상한, 단위)
# 허용 범위는 벤치마크의 p25~p75입니다. 그 밖이면 "다르다"고만 말하고,
# 무엇이 옳은지는 사람이 정합니다.
BENCHMARK = {
    "문장 수": (38, 31, 50, "개"),
    "글자 수": (2835, 2200, 3297, "자"),
    "문장 길이(중앙값)": (30, 22, 38, "자"),
    "'습니다'로 끝": (45, 30, 55, "%"),
    "한 문장짜리 문단": (20, 10, 32, "%"),
    "소제목 수": (7, 6, 8, "개"),
    "소제목 길이(중앙값)": (14, 10, 20, "자"),
}

# 문장으로 볼 것 — 종결 어미로 끝나는 줄만. 불릿·표 조각을 문장으로 세면
# 길이 중앙값이 실제보다 짧게 나옵니다.
_SENTENCE_END = re.compile(r"(다|요)[.!?]?$")
_TAG = re.compile(r"<[^>]+>")


def _paragraphs(doc: dict) -> list[str]:
    out: list[str] = []
    for section in doc.get("narrative") or []:
        out += [p for p in _TAG.sub("", section.get("body", "")).split("\n\n") if p.strip()]
    for key in ("outlook", "closing"):
        body = (doc.get(key) or {}).get("body", "")
        out += [p for p in _TAG.sub("", body).split("\n\n") if p.strip()]
    for story in (doc.get("insight_section") or {}).get("stories") or []:
        out += [p for p in _TAG.sub("", story.get("body", "")).split("\n\n") if p.strip()]
    return out


def _sentences(paragraphs: list[str]) -> list[str]:
    out: list[str] = []
    for para in paragraphs:
        for piece in re.split(r"(?<=[.!?])\s+|\n", para):
            piece = piece.strip()
            if len(piece) > 6 and _SENTENCE_END.search(piece):
                out.append(piece)
    return out


def _headings(doc: dict) -> list[str]:
    out = [s.get("heading", "") for s in doc.get("narrative") or []]
    for key in ("outlook", "closing"):
        heading = (doc.get(key) or {}).get("heading")
        if heading:
            out.append(heading)
    return [h for h in out if h]


def measure(doc: dict) -> dict[str, float]:
    paragraphs = _paragraphs(doc)
    sentences = _sentences(paragraphs)
    headings = _headings(doc)
    if not sentences:
        return {}

    polite = sum(1 for s in sentences if re.search(r"습니다[.!?]?$", s))
    single = sum(
        1
        for p in paragraphs
        if len([x for x in re.split(r"(?<=[.!?])\s+|\n", p.strip()) if x.strip()]) == 1
    )
    return {
        "문장 수": len(sentences),
        "글자 수": sum(len(p) for p in paragraphs),
        "문장 길이(중앙값)": round(statistics.median(len(s) for s in sentences)),
        "'습니다'로 끝": round(100 * polite / len(sentences)),
        "한 문장짜리 문단": round(100 * single / max(1, len(paragraphs))),
        "소제목 수": len(headings),
        "소제목 길이(중앙값)": round(statistics.median(len(h) for h in headings)) if headings else 0,
    }


def report(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    doc = data.get("ko") or {}
    got = measure(doc)
    if not got:
        print(f"{path.name}: 한국어 본문이 없어 건너뜁니다.")
        return 0

    print(f"\n{path.name}  —  {doc.get('title', '')}")
    print(f"  {'항목':<20}{'우리':>8}{'벤치마크':>10}{'허용 범위':>14}")
    off = 0
    for key, (target, low, high, unit) in BENCHMARK.items():
        value = got[key]
        ok = low <= value <= high
        if not ok:
            off += 1
        mark = " " if ok else "  ← 다름"
        print(f"  {key:<20}{value:>8}{target:>10}{f'{low}~{high}{unit}':>14}{mark}")
    print(f"  벤치마크 범위 밖: {off} / {len(BENCHMARK)}")
    return off


def main(argv: list[str]) -> int:
    paths = [Path(a) for a in argv[1:]] or sorted(EDITORIAL_DIR.glob("*.json"))
    for path in paths:
        report(path)
    # 이 스크립트는 보고만 합니다. 발행을 막지 않으므로 항상 0으로 끝냅니다.
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
