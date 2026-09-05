"""기준표(feature) 원고가 `docs/feature-style.md`를 지켰는지 기계로 봅니다.

왜 필요한가
-----------
2026-09-06 첫 편에서 네 번을 고쳤습니다. 제목이 설명적이었고(41자, 지표 용어),
시각자료가 0장이었습니다. 둘 다 **어디에도 적혀 있지 않아서** 벌어진 일입니다.

문서에만 적어 두면 지켜지지 않는다는 것은 이미 겪었습니다 — `editorial-style.md`에
"소제목에 종결 어미를 붙이지 않는다"고 적어 뒀는데 다음 원고의 소제목 6개 중
4개가 `~했습니다`로 끝났습니다. 그래서 검사로 옮깁니다.

무엇을 하지 않는가
------------------
**말맛을 기계로 재려 하지 않습니다.** "결론을 제목에 넣지 않았는가"는 사람만
판단할 수 있습니다. 여기서 보는 것은 세어서 틀렸다고 말할 수 있는 것뿐입니다 —
후킹 장치가 하나라도 있는지, 그림이 최소 개수를 넘는지, 확인 날짜가 박혔는지.

`editorial_quality`·`editorial_title` 검사는 별도로 통과해야 합니다. 이 파일은
그 위에 기준표 글에만 해당하는 것을 더합니다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from src.editorial_title import _POLITE_ENDING

# 제목 후킹 장치. 벤치마크 100편에서 추린 다섯 유형입니다(docs/feature-style.md 1절).
HOOKS = {
    "약속+반전": r"그러나|하지만|그런데|인데도|했는데|지만,|아니다|아닙니다",
    "미해결 질문": r"\?|할까|될까|일까|갈린다|갈립니다",
    # 한글 숫자를 빼면 `확인할 다섯 가지`를 "후킹 없음"으로 잡습니다. 그 제목의
    # 진짜 문제는 지표 용어와 길이였지, 장치가 없는 것이 아니었습니다.
    "범위 축소": r"\d\s*가지|[한두세네]\s*가지|다섯 가지|여섯 가지|딱 \d|가지만|하나만|둘만",
    "시한 압박": r"\d+분 뒤|오늘 밤|내일|이번 ?주|다음 ?주|\d+월 \d+일|지금",
    "권위+반전": r"증권사|월가|기관|헤지펀드|CEO|내부자|외국인|개미",
}

# 제목에 쓰면 안 되는 지표 용어. 벤치마크 100편 제목 중 PER이 든 것은 1편뿐이고
# 그것도 '저평가'라는 쉬운 말을 앞에 뒀습니다.
JARGON = ("FWD PER", "PER", "EPS", "PBR", "ROE", "밸류에이션", "컨센서스",
          "가이던스", "CAPEX", "FWD")

MIN_GRAPHICS = 6          # 벤치마크 이미지 p25
MIN_SECTIONS = 5


def collect_issues(doc: dict, graphics: int | None = None) -> list[str]:
    ko = doc.get("ko") or doc
    issues: list[str] = []

    title = ko.get("title") or ""
    if not title:
        return ["제목이 없습니다."]

    found = [name for name, pattern in HOOKS.items() if re.search(pattern, title)]
    if not found:
        issues.append(
            f"제목에 후킹 장치가 없습니다: {title!r} — 다섯 유형 중 하나는 써야 합니다"
            f"({', '.join(HOOKS)}). docs/feature-style.md 1절.")

    for word in JARGON:
        if word in title:
            issues.append(
                f"제목에 지표 용어 {word!r}가 있습니다 — 지표는 본문에, 제목에는 "
                f"누구나 아는 말을 씁니다. 벤치마크 100편 중 1편만 예외였습니다.")
            break

    # 존댓말 판정은 `editorial_title`의 것을 그대로 씁니다. 검사를 두 벌 두면
    # 한쪽만 고쳐져 서로 다른 답을 내놓습니다.
    if _POLITE_ENDING.search(title):
        issues.append("제목이 존댓말로 끝납니다 — 명사형으로 끊거나 반말로 단정합니다.")

    sections = ko.get("narrative") or []
    if len(sections) < MIN_SECTIONS:
        issues.append(f"절이 {len(sections)}개입니다 — {MIN_SECTIONS}개 이상 씁니다.")

    body = " ".join(s.get("body", "") for s in sections) + (
        ko.get("closing", {}).get("body", ""))

    # 6절(확인 지점)이 이 글 형식의 존재 이유입니다. 날짜가 없으면 그냥 시황입니다.
    if not re.search(r"\d+월 \d+일", body):
        issues.append("본문에 확인 날짜(`N월 N일`)가 없습니다 — 기준표 글은 날짜를 "
                      "박아야 글의 수명이 그날까지 갑니다. docs/feature-style.md 4절.")

    # 제목이 약속한 것을 본문이 답하는지 (제목 원칙 7)
    dates_in_title = re.findall(r"\d+월 \d+일", title)
    for date in dates_in_title:
        if date not in body:
            issues.append(f"제목의 {date}이 본문에 없습니다 — 제목이 약속한 것을 "
                          f"본문이 다뤄야 합니다.")

    if "초보자" not in body:
        issues.append("초보자 설명이 없습니다 — 벤치마크 30%가 본문에 끼워 넣습니다.")

    # 우리는 종목을 들고 있지 않습니다. 1인칭 포지션 화법을 흉내 내면 거짓말이 됩니다.
    for phrase in ("제가 매수", "제가 매도", "저는 매수", "저는 매도", "제 계좌",
                   "보유 물량", "익절했"):
        if phrase in body:
            issues.append(f"본문에 포지션 화법 {phrase!r}이 있습니다 — 우리는 종목을 "
                          f"들고 있지 않습니다. docs/feature-style.md 0절.")
            break

    if graphics is not None and graphics < MIN_GRAPHICS:
        issues.append(f"시각자료가 {graphics}장입니다 — 최소 {MIN_GRAPHICS}장. "
                      f"벤치마크는 편당 중앙값 10장입니다.")

    return issues


def validate(doc: dict, graphics: int | None = None) -> None:
    issues = collect_issues(doc, graphics)
    if issues:
        raise ValueError("기준표 기준 검사 실패:\n- " + "\n- ".join(issues))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--graphics", type=int,
                        help="본문에 넣을 그림 장수(알면 함께 검사)")
    args = parser.parse_args()

    doc = json.loads(Path(args.path).read_text(encoding="utf-8"))
    issues = collect_issues(doc, args.graphics)
    title = (doc.get("ko") or doc).get("title", "")
    hooks = [name for name, pattern in HOOKS.items() if re.search(pattern, title)]
    print(f"제목: {title} ({len(title)}자)")
    print(f"후킹 장치: {', '.join(hooks) or '없음'}")
    if not issues:
        print("기준표 검사 통과")
        return 0
    print("어긋난 항목:")
    for issue in issues:
        print(f"  - {issue}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
