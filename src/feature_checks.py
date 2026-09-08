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


# 제목 후킹 장치. 벤치마크 100편에서 추린 다섯 유형입니다(docs/feature-style.md 1절).
HOOKS = {
    # 접속사만 보다가 `반대로 갔다`를 반전으로 못 읽었습니다. 코퍼스에서
    # `반대로` 224회, `오히려` 141회로 그쪽이 가장 자주 쓰는 반전 표현입니다.
    "약속+반전": (r"그러나|하지만|그런데|인데도|했는데|지만,|아니다|아닙니다"
                r"|반대로|정반대|오히려|~?만 무너|만 빠|만 올|만 하락"),
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

# 시리즈별 하한. 기준표는 위 기본값이고, 밤 10시 미국장 프리뷰(2026-09-08)는 600~900자
# 짜리 짧은 글이라 절 3개·시각자료 2장이면 된다 — 같은 파이프라인(관문·렌더·발행)을
# 쓰되 문턱만 다르다. 새 시리즈를 만들면 여기에 한 줄 더한다.
SERIES_LIMITS = {"프리뷰": {"graphics": 2, "sections": 3}}

# 설명 없이 지나가면 초보자가 문장을 못 따라가는 말들. 벤치마크는 이런 말이
# 나올 때마다 `초보자용 설명` 블록을 따로 답니다(100편 중 30%).
#
# 30%라는 숫자는 "열 편 중 세 편에 넣어라"는 뜻이 아닙니다. **이런 말이 나온 글에는
# 넣고, 안 나온 글에는 안 넣은 결과**가 30%입니다. 그래서 개수가 아니라
# 글 안에 실제로 그런 말이 있는지로 봅니다.
JARGON_IN_BODY = (
    "PER", "EPS", "FWD", "밸류에이션", "컨센서스", "가이던스", "CAPEX",
    "HBM", "D램", "낸드", "계약가", "현물가", "매출총이익률", "영업이익률",
    "이동평균", "50일선", "200일선", "볼린저", "순매수", "순매도", "공매도",
    "듀레이션", "베이시스", "bp", "선물시장", "패시브", "ETF",
)


def collect_issues(doc: dict, graphics: int | None = None,
                   notes_out: list[str] | None = None) -> list[str]:
    """막을 것만 돌려줍니다.

    **드문 것과 틀린 것을 구분합니다.** 벤치마크에서 드물 뿐인 어법(존댓말 제목,
    지표 용어, 초보자 설명 생략)을 차단으로 바꿨더니 쓸 수 있는 글이 좁아지고
    통계에 맞추는 글이 나왔습니다. 그런 항목은 `notes_out`으로 알려만 줍니다.
    """
    ko = doc.get("ko") or doc
    issues: list[str] = []
    notes: list[str] = notes_out if notes_out is not None else []

    title = ko.get("title") or ""
    if not title:
        return ["제목이 없습니다."]

    found = [name for name, pattern in HOOKS.items() if re.search(pattern, title)]
    if not found:
        issues.append(
            f"제목에 후킹 장치가 없습니다: {title!r} — 다섯 유형 중 하나는 써야 합니다"
            f"({', '.join(HOOKS)}). docs/feature-style.md 1절.")

    # 지표 용어는 **막지 않고 알려만 줍니다.** 벤치마크에도 예외가 있습니다
    # (`저평가 반도체 주식은? 8개 FWD PER 분석`). 드문 것을 금지로 바꾸면
    # 쓸 수 있는 제목이 좁아집니다.
    for word in JARGON:
        if word in title:
            notes.append(
                f"제목에 지표 용어 {word!r}가 있습니다. 벤치마크 100편 중 1편만 "
                f"이렇게 씁니다 — 누구나 아는 말로 바꿀 수 있는지 한 번 보십시오.")
            break

    limits = SERIES_LIMITS.get(str(doc.get("series") or ""), {})
    min_sections = limits.get("sections", MIN_SECTIONS)
    min_graphics = limits.get("graphics", MIN_GRAPHICS)

    sections = ko.get("narrative") or []
    if len(sections) < min_sections:
        issues.append(f"절이 {len(sections)}개입니다 — {min_sections}개 이상 씁니다.")

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

    # 초보자 설명: 무조건 요구하지도, 그냥 넘기지도 않습니다. **글에 설명이 필요한
    # 말이 실제로 들어 있는지**를 보고 정합니다. 매번 요구하면 필요 없는 자리에도
    # 들어가고, 그냥 넘기면 PER·HBM·계약가가 설명 없이 지나갑니다.
    used = [word for word in JARGON_IN_BODY if word in body]
    if "초보자" not in body:
        if len(used) >= 3:
            issues.append(
                f"초보자 설명이 없는데 설명이 필요한 말이 {len(used)}개 나옵니다: "
                f"{', '.join(used[:8])}. 이 중 이 글의 논지에 꼭 필요한 것 하나는 "
                f"풀어 쓰십시오. docs/feature-style.md 0절.")
        elif used:
            notes.append(f"설명이 필요할 수 있는 말: {', '.join(used)}. "
                         f"독자가 모르면 논지를 못 따라가는지 보십시오.")

    # 우리는 종목을 들고 있지 않습니다. 1인칭 포지션 화법을 흉내 내면 거짓말이 됩니다.
    for phrase in ("제가 매수", "제가 매도", "저는 매수", "저는 매도", "제 계좌",
                   "보유 물량", "익절했"):
        if phrase in body:
            issues.append(f"본문에 포지션 화법 {phrase!r}이 있습니다 — 우리는 종목을 "
                          f"들고 있지 않습니다. docs/feature-style.md 0절.")
            break

    if graphics is not None and graphics < min_graphics:
        issues.append(f"시각자료가 {graphics}장입니다 — 최소 {min_graphics}장. "
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
    notes: list[str] = []
    issues = collect_issues(doc, args.graphics, notes_out=notes)
    title = (doc.get("ko") or doc).get("title", "")
    hooks = [name for name, pattern in HOOKS.items() if re.search(pattern, title)]
    print(f"제목: {title} ({len(title)}자)")
    print(f"후킹 장치: {', '.join(hooks) or '없음'}")
    for note in notes:
        print(f"  (참고) {note}")
    if not issues:
        print("가이드 검사 통과")
        return 0
    print("어긋난 항목:")
    for issue in issues:
        print(f"  - {issue}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
