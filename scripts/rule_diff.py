"""문서·지시문을 다시 쓸 때 **사라진 규칙 줄**을 찾아낸다 (2026-09-17, 사장님: "니맘대로 누락이 되고 생략하고").

    python -m scripts.rule_diff docs/routine_preview.md            # 작업 사본 vs HEAD
    python -m scripts.rule_diff docs/routine_preview.md --ref 91d4b24^

왜 필요한가: 2026-09-17에 `docs/routine_preview.md`를 12절로 다시 쓰면서 「`ko.title`: 앞을 보는 제목 —
오늘 밤 무엇이 무엇을 정하는지」 한 줄이 빠졌다. 그날 밤 루틴은 지시문을 그대로 따랐고, 없는 규칙은 따를 수
없어 어젯밤 요약형 제목이 나갔다. 사람이 긴 문서를 다시 쓰면 무엇이 빠졌는지 스스로 알 수 없다 — 그래서
**바꾸기 전 판과 뒤 판의 규칙 줄을 기계로 대조**한다. 결과는 "빠진 줄 목록"이고, 커밋 전에 그 목록의 줄마다
'일부러 뺐다'고 말할 수 있어야 한다. 말할 수 없는 줄은 도로 넣는다.

무엇을 규칙 줄로 보나: 명령·금지·수치가 든 줄. `않습니다|금지|필수|반드시|막습니다|이상|이하|까지|N절|N장|N곳|
N자|`백틱 필드`|**굵게**`. 설명문은 세지 않는다 — 다 세면 목록이 길어져 아무도 안 읽는다.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULE = re.compile(r"않습니다|않는다|금지|필수|반드시|막습니다|막는다|늘 |이상|이하|까지|\d+절|\d+장|\d+곳|\d+자|"
                  r"`[^`]+`|\*\*[^*]+\*\*|해야|하지 마|말 것|말라|지 말|씁니다|쓴다|요구")


def rule_lines(text: str) -> list[str]:
    """규칙으로 볼 줄 — 앞뒤 공백·번호·불릿을 떼고 비교한다."""
    out = []
    for raw in text.splitlines():
        line = re.sub(r"^\s*(?:[-*]|\d+\.|\|)\s*", "", raw).strip()
        if len(line) >= 12 and RULE.search(line):
            out.append(line)
    return out


def _key(line: str) -> str:
    """같은 규칙인지 볼 열쇠 — 문장부호·공백을 빼고 앞 40자."""
    return re.sub(r"[\s`*·—\-,.:;()（）\"'「」]", "", line)[:40]


def removed_rules(old: str, new: str) -> list[str]:
    new_keys = {_key(l) for l in rule_lines(new)}
    new_blob = re.sub(r"\s+", "", new)
    gone = []
    for line in rule_lines(old):
        k = _key(line)
        if k in new_keys:
            continue
        # 문장이 다른 줄로 옮겨져 살아 있으면 빠진 것이 아니다 — 앞 24자, 또는 첫 문장(마침표 앞)이
        # 새 문서 어딘가에 그대로 있으면 산 것으로 본다. "예측하지 않습니다. 조건으로 씁니다."가
        # "예측하지 않습니다. 시나리오 표와 …"로 바뀐 것은 고쳐 쓴 것이지 뺀 것이 아니다.
        first = re.sub(r"[\s`*·—\-,:;()（）\"'「」]", "", re.split(r"[.!?]", line)[0])
        if (k[:24] and k[:24] in new_blob) or (len(first) >= 8 and first in new_blob):
            continue
        gone.append(line)
    return gone


def _norm(text: str) -> str:
    return re.sub(r"[\s`*·—\-,.:;()（）\"'「」]", "", text)


def shortened_rules(old: str, new: str) -> list[str]:
    """앞부분은 새 판에 있는데 **줄 전체는 없는** 규칙 줄 — 고쳐 썼거나, 뒷부분이 잘렸다(2026-09-26).

    `removed_rules`는 고쳐 쓴 줄을 빠진 것으로 세지 않으려고 앞 24자·첫 문장만 본다. 그래서 "예약 시각을 마감 정각으로
    되돌리지 말 것. 16:00/07:00 정각은 … 20분 뒤다."를 첫 문장만 남기고 잘라도 아무 말이 없었다. 이 목록은 그런 줄을
    따로 보여 준다 — 사람이 "고쳐 썼다"인지 "뒷부분을 뺐다"인지 말해야 한다.
    """
    new_norm = _norm(new)
    gone = set(removed_rules(old, new))
    return [line for line in rule_lines(old) if line not in gone and _norm(line) not in new_norm]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("path")
    ap.add_argument("--ref", default="HEAD", help="비교할 옛 판 (기본 HEAD)")
    a = ap.parse_args(argv)
    rel = str(Path(a.path).resolve().relative_to(ROOT))
    try:
        old = subprocess.run(["git", "show", f"{a.ref}:{rel}"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except subprocess.CalledProcessError:
        print(f"{a.ref}에 {rel}이 없습니다 — 새 파일이면 대조할 것이 없습니다.")
        return 0
    new = (ROOT / rel).read_text(encoding="utf-8")
    gone = removed_rules(old, new)
    short = shortened_rules(old, new)
    if not gone and not short:
        print(f"{rel}: {a.ref} 대비 사라진 규칙 줄 없음.")
        return 0
    if gone:
        print(f"{rel}: {a.ref} 대비 사라진 규칙 줄 {len(gone)}개 — 하나씩 '일부러 뺐다'고 말할 수 있어야 합니다.")
        for line in gone:
            print("  -", line[:120])
    if short:
        print(f"{rel}: 앞부분만 남은 규칙 줄 {len(short)}개 — 고쳐 쓴 것인지, 뒷부분을 뺀 것인지 줄마다 말하십시오.")
        for line in short:
            print("  ~", line[:120])
    return 1


if __name__ == "__main__":
    sys.exit(main())
