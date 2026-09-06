"""원고의 어법이 벤치마크와 어긋나는지 봅니다.

왜 이렇게 좁은가
----------------
처음에는 원고의 낱말을 벤치마크 본문 전체와 대조해 **0회인 것을 전부** 보여줬습니다.
돌려 보니 이렇게 나왔습니다.

    가격이었기, 갈리는지를, 갈린다, 같아도, 거리라는, 걱정하는지, 계약가가, ...

한국어는 활용이 붙어 표면형이 잘 겹치지 않고, 코퍼스도 100편(70만 자)뿐이라
**정상적인 문장에서 30개씩 쏟아집니다.** 2어절 조합으로 바꿔 봐도 원고 699개 중
503개(71%)가 "없음"으로 나왔습니다. 말뭉치 대조 자체가 이 일에 맞지 않습니다.

**작동하지 않는 검사는 없는 것보다 나쁩니다** — 있으면 통과했다고 믿게 됩니다.
그래서 넓은 대조를 버리고, 코퍼스로 검증한 규칙만 남겼습니다.

무엇을 보는가
-------------
수사와 단위의 짝만 봅니다. 2026-09-06에 `실적일까지 일곱 주`라고 썼는데
벤치마크 100편에 `일곱`은 0회였고 주 단위는 58회가 전부 숫자였습니다.

**한 번 잘못 셌습니다.** 처음 센 표에는 `달러 6회`, `일 2회`, `분기 12회`가
고유어로 잡혔는데, 정규식이 형용사 어미 `-한`을 수사 `한`으로 읽은 것이었습니다 —
"강**한** 달러", "막대**한** 달러 자금", "등장**한** 일". 앞이 한글이면 수사가
아니라는 경계(`(?<![가-힣])`)를 넣고 다시 세니 이렇게 나왔습니다.

**두 번째로 잘못 셌습니다.** 단위 뒤를 `(?![가-힣])`로 막았더니 조사가 붙은
`7주가 남았습니다`가 통째로 빠졌습니다 — 정작 잡아야 할 `일곱 주가`도 안 잡혔습니다.
단위 뒤에 조사·공백·문장부호만 허용하도록 고치고 세 번째로 셌습니다.

    주 3:72 · 개월 0:82 · 년 0:973 · 달러 0:452 · 원 0:51 · 일 0:260
        → 숫자를 쓴다. 고유어를 붙이면 어색하다.
    분기 17:210 · 개 14:160 · 명 10:64
        → 고유어도 실제로 쓴다(`두 분기 연속`, `세 개 이상`). 뺐다.
    달 34:2 · 가지 70:15 · 번 66:55 · 배 33:108 · 곳 3:10
        → 고유어를 쓰거나 둘 다 쓴다. 보지 않는다.

`한 주`는 관용이라 예외입니다(`한 주 만에`, `한 주 데이터만으로`).

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

CORPUS = Path.home() / ".market-brief-bench" / "posts"

# 앞이 한글이면 수사가 아니라 어미입니다("강한 달러"의 `한`).
_NATIVE = r"(?<![가-힣])(한|두|세|네|다섯|여섯|일곱|여덟|아홉|열|스무)"
# 코퍼스에서 고유어가 0~2회뿐인 단위만 남겼습니다. `분기`·`개`는 고유어도 실제로
# 쓰기에 뺐습니다 — 오탐 하나가 검사 전체를 못 믿게 만듭니다.
_NUMERIC_UNITS = ("주", "개월", "년", "달러", "원", "일")
# 단위 뒤에는 조사·공백·문장부호만 옵니다. `(?![가-힣])`로 막으면 `7주가`처럼
# 조사가 붙은 흔한 형태가 통째로 빠집니다.
_AFTER = (r"(?=[\s.,)\]]|$|은|는|이|가|을|를|에|의|도|만|와|과|로|부터|까지|짜리|째|간)")
_TAG = re.compile(r"<[^>]+>")


def _body(doc: dict) -> str:
    ko = doc.get("ko") or doc
    parts = [ko.get("title", "")]
    for section in ko.get("narrative") or []:
        parts += [section.get("heading", ""), section.get("body", "")]
    for key in ("outlook", "closing"):
        block = ko.get(key) or {}
        parts += [block.get("heading", ""), block.get("body", "")]
    return _TAG.sub(" ", "\n".join(p for p in parts if p))


def check(doc: dict, corpus: str | None = None) -> list[str]:
    """`corpus`는 받지만 쓰지 않습니다 — 옛 호출부와의 호환을 위해 남깁니다."""
    text = _body(doc)
    issues = []
    for unit in _NUMERIC_UNITS:
        for match in re.finditer(rf"{_NATIVE}\s*{unit}{_AFTER}", text):
            phrase = match.group(0)
            if phrase.startswith("한 ") and unit == "주":
                continue                       # `한 주`는 벤치마크 18회
            issues.append(
                f"{phrase!r} — `{unit}` 앞에는 숫자를 씁니다. 벤치마크 100편에서 "
                f"이 단위는 대부분 숫자로 나옵니다(예: `7{unit}`).")
    return issues


def load_corpus() -> str:
    """옛 호출부 호환용. 이제 대조에 쓰지 않으므로 빈 문자열을 돌려줍니다."""
    return ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    args = parser.parse_args()
    doc = json.loads(Path(args.path).read_text(encoding="utf-8"))
    issues = check(doc)
    if not issues:
        print("수사·단위 어법 이상 없음")
        return 0
    for issue in issues:
        print(f"  - {issue}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
