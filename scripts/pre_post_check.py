"""네이버(와 그 뒤 텔레그램)에 올리기 직전 숫자·사실 검사 (2026-10-06, 감사 F-044·F-074).

맥의 네이버 동기화(`~/.market-brief-naver/naver_sync.py`)는 main에 있는 원고를 그대로 올렸다 — 관문(`editorial_gate`·
`feature_gate`)은 루틴이 커밋 **전에** 돌리는 것이고, 돌리지 않았거나 통과하지 못한 원고도 main에 있으면 나갔다.
한국어 글은 네이버가 유일한 공개처라 여기서 한 번 더 막는다.

    python -m scripts.pre_post_check editorial/kr_2026-10-06.json     # 종료 코드 0 = 올려도 됨, 1 = 막힘(이유를 찍는다)

- 시황(kr/us): 발행 단계와 같은 숫자 검사(`publish_editorial.fact_blockers`) — 문체·제목은 보지 않는다.
- 그 밖의 글(Checkpoint·프리뷰·가이드·주간·이벤트·잡지): 관문 전체(`feature_gate.run`) — 잡지는 근거 표의 원문을 실제 페이지에서 찾는다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def blockers(path: Path) -> list[str]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("market") in ("kr", "us") and "price_data" in doc:
        from src import publish_editorial
        return publish_editorial.fact_blockers(doc)
    from src import feature_gate
    try:
        feature_gate.run(doc, graphics=len(doc.get("graphics") or []), path=path)
    except feature_gate.FeatureGateError as exc:
        return [line[2:] for line in str(exc).splitlines() if line.startswith("- ")] or [str(exc)]
    return []


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("사용법: python -m scripts.pre_post_check <원고.json>")
        return 2
    path = Path(args[0])
    try:
        found = blockers(path)
    except Exception as exc:  # noqa: BLE001 — 검사를 못 돌린 것도 '막힘'이다(통과로 읽지 않는다)
        print(f"막힘: 검사를 돌리지 못했습니다 — {exc!r}")
        return 1
    if found:
        print(f"막힘: {path.name} — {len(found)}건")
        for line in found[:30]:
            print(f"  - {line}")
        return 1
    print(f"통과: {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
