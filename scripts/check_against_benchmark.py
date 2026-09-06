"""원고에 쓴 표현이 벤치마크에 실제로 나오는지 대조합니다.

왜 필요한가
-----------
`docs/editorial-style.md`에 이렇게 적혀 있습니다.

    새 표현을 쓰고 싶으면 먼저 세어 보고, 0회면 쓰지 않는다.

그런데 이 규칙이 문서에만 있어서 세 번 어겼습니다.

    반대편   벤치마크 0회 — 2026-09-04
    코앞·문턱 벤치마크 0회 — 2026-09-05
    일곱 주   벤치마크 0회 — 2026-09-06 (`일곱`이라는 낱말 자체가 0회)

세 번 다 "세어 보면 알 수 있었던 것"을 세지 않고 썼습니다. 사람이 매번 세는
대신 이 스크립트가 셉니다.

무엇을 하는가
-------------
원고에서 뽑은 표현을 `~/.market-brief-bench/posts`의 본문 전체와 대조해
**0회인 것만** 보여줍니다. 0회라고 반드시 틀린 것은 아닙니다 — 종목명이나 그날
고유한 사실은 당연히 0회입니다. 그래서 막지 않고 보여주기만 하며, 숫자·영문·
종목명은 애초에 후보에서 뺍니다.

사용법
------
    python -m scripts.check_against_benchmark editorial/features/<파일>.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = Path.home() / ".market-brief-bench" / "posts"

# 고유어 수사 + 단위. 한국어는 단위마다 붙는 수사가 갈립니다 — `가지`·`곳`은
# 고유어(다섯 가지)가 자연스럽고 `주`·`개월`·`%`는 숫자를 씁니다. 벤치마크에서
# `일곱 주`는 0회, `2주`·`4주`·`5주`는 75회였습니다.
_NATIVE_NUMERAL = r"(한|두|세|네|다섯|여섯|일곱|여덟|아홉|열|스무)"
_UNIT_PATTERNS = [
    (rf"{_NATIVE_NUMERAL}\s*(주|개월|분기|년|달러|퍼센트|포인트|bp)",
     "기간·수치 단위에는 숫자를 씁니다(`7주`, `3개월`). 벤치마크에서 고유어 수사와 "
     "이 단위의 조합은 `한 주` 말고는 나오지 않습니다."),
]

_TAG = re.compile(r"<[^>]+>")
_TOKEN = re.compile(r"[가-힣]{2,}")


def load_corpus() -> str:
    if not CORPUS.exists():
        raise SystemExit(f"벤치마크 본문이 없습니다: {CORPUS}\n"
                         f"`python -m scripts.bench_watch`로 먼저 모으세요.")
    parts = []
    for path in CORPUS.glob("*.json"):
        doc = json.loads(path.read_text(encoding="utf-8"))
        parts.append("\n".join(b["text"] for b in doc["blocks"] if b["t"] == "p"))
    return "\n".join(parts)


def draft_text(doc: dict) -> tuple[str, list[str]]:
    ko = doc.get("ko") or doc
    pieces = [ko.get("title", "")]
    for section in ko.get("narrative") or []:
        pieces.append(section.get("heading", ""))
        pieces.append(section.get("body", ""))
    for key in ("outlook", "closing"):
        block = ko.get(key) or {}
        pieces.append(block.get("heading", ""))
        pieces.append(block.get("body", ""))
    text = _TAG.sub(" ", "\n".join(p for p in pieces if p))
    return text, [p for p in pieces if p]


def check(doc: dict, corpus: str) -> list[str]:
    text, _ = draft_text(doc)
    issues = []

    for pattern, why in _UNIT_PATTERNS:
        for match in re.finditer(pattern, text):
            phrase = match.group(0)
            if phrase.startswith("한 ") or phrase.startswith("한("):
                continue                      # `한 주`는 벤치마크 18회
            count = corpus.count(phrase)
            if count == 0:
                issues.append(f"{phrase!r} — 벤치마크 0회. {why}")

    # 낱말 단위로도 훑습니다. 종목명·고유명사는 0회가 정상이므로 참고용입니다.
    rare = []
    for word in sorted(set(_TOKEN.findall(text))):
        if len(word) < 2 or corpus.count(word):
            continue
        rare.append(word)
    if rare:
        issues.append("벤치마크에 한 번도 없는 낱말(종목명·고유명사면 정상): "
                      + ", ".join(rare[:30]))
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    args = parser.parse_args()
    doc = json.loads(Path(args.path).read_text(encoding="utf-8"))
    corpus = load_corpus()
    issues = check(doc, corpus)
    print(f"벤치마크 본문 {len(list(CORPUS.glob('*.json')))}편과 대조")
    if not issues:
        print("0회인 표현 없음")
        return 0
    for issue in issues:
        print(f"  - {issue}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
