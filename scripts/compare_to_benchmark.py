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

# **하드코딩된 기준값을 버렸습니다(2026-09-06).**
#
# 여기에는 "본문 60편을 세어 나온 값"이 상수로 박혀 있었습니다. 그중
# `소제목 길이 14자`가 2026-09-06에 `1. 지금 숫자`(5자) 같은 소제목을 만든
# 직접 원인이었습니다. 그 값은 소제목을 **글자 크기**로 찾아 나온 것이라 애초에
# 틀렸습니다 — 벤치마크 편집기는 소제목에 큰 글씨를 주지 않습니다.
#
# 같은 날 코퍼스 100편으로 다시 세니 일곱 항목이 **전부** 어긋났습니다.
#
#     문장 수 38→74 · 글자 수 2835→5971 · 문장 길이 30→58
#     습니다 45→52 · 한 문장 문단 20→82 · 소제목 수 7→14 · 소제목 길이 14→23
#
# 그런데 재측정도 못 믿습니다. `한 문장 문단 82%`는 그쪽 편집기가 여러 문단을
# 한 블록으로 묶어 내보내서 생긴 허수입니다. 표본 구성도 다릅니다(시황만 vs 전체).
#
# **두 숫자가 다 못 믿을 것이면 더 정확한 숫자를 만들 게 아니라, 이 표가 목표로
# 쓰이지 않게 해야 합니다.** 그래서 상수를 없애고, 코퍼스가 있으면 그 자리에서
# 다시 세어 나란히 찍고, 없으면 우리 원고 수치만 보여줍니다. 어느 쪽이든
# **맞춰야 할 기준이 아닙니다.**
CORPUS = Path.home() / ".market-brief-bench" / "posts"

# 문단 경계는 신뢰할 수 없어 뺐습니다(위 참조).
_UNTRUSTED = ("한 문장짜리 문단",)

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


def _corpus_stats() -> dict[str, tuple[float, float, float]] | None:
    """코퍼스가 있으면 그 자리에서 다시 셉니다. 없으면 None."""
    if not CORPUS.exists():
        return None
    samples: dict[str, list[float]] = {}
    for path in CORPUS.glob("*.json"):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        blocks = [b for b in doc.get("blocks", []) if b.get("t") == "p"]
        heads, paras = [], []
        for block in blocks:
            text = (block.get("text") or "").strip()
            if not text or text == "\u200b":
                continue
            if "\n" not in text and len(text) <= 45:
                heads.append(text)
            else:
                paras += [x.strip() for x in text.split("\n")
                          if x.strip() and x.strip() != "\u200b"]
        measured = measure({"narrative": [{"heading": h, "body": ""} for h in heads]
                            + [{"heading": "", "body": "\n\n".join(paras)}]})
        for key, value in measured.items():
            samples.setdefault(key, []).append(value)
    if not samples:
        return None
    out = {}
    for key, values in samples.items():
        values = sorted(values)
        out[key] = (statistics.median(values),
                    values[len(values) // 4], values[3 * len(values) // 4])
    return out


def report(path: Path) -> int:
    doc = json.loads(path.read_text(encoding="utf-8"))
    ko = doc.get("ko") or doc
    mine = measure(ko)
    if not mine:
        print(f"{path.name} — 잴 문장이 없습니다")
        return 0
    print(f"\n{path.name}  —  {ko.get('title', '')}")
    corpus = _corpus_stats()
    if corpus:
        print(f"  {'항목':<20}{'우리':>8}{'벤치마크':>10}   (코퍼스 실측, 목표 아님)")
    else:
        print(f"  {'항목':<20}{'우리':>8}   (벤치마크 코퍼스 없음 — 우리 수치만)")
    for key, value in mine.items():
        if key in _UNTRUSTED:
            continue
        if corpus and key in corpus:
            median, low, high = corpus[key]
            print(f"  {key:<20}{value:>8}{median:>10.0f}   p25 {low:.0f} · p75 {high:.0f}")
        else:
            print(f"  {key:<20}{value:>8}")
    print("  이 수치는 **맞춰야 할 기준이 아닙니다.** 범위 밖이라고 고치지 마십시오 —")
    print("  왜 다른지만 보십시오. 2026-09-06에 이 표를 맞추다 `1. 지금 숫자`가 나왔습니다.")
    return 0


def main(argv: list[str]) -> int:
    paths = [Path(a) for a in argv[1:]] or sorted(EDITORIAL_DIR.glob("*.json"))
    for path in paths:
        report(path)
    # 이 스크립트는 보고만 합니다. 발행을 막지 않으므로 항상 0으로 끝냅니다.
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
