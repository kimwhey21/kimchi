"""쓰려는 제목과 **같은 구조**의 실제 벤치마크 제목을 찾아 줍니다.

왜 필요한가
-----------
2026-09-07에 제목을 네 번 고쳤습니다. 매번 낱말 빈도를 세어 골랐는데 계속
어색했습니다. `반대로`가 코퍼스에 224회 나와서 `금리는 반대로 갔다`라고 썼는데,
224회가 **전부 문장 첫머리 접속사**(`반대로 ~하면`)였고 술어로 쓴 예는 1회였습니다.

**빈도는 그 낱말이 어느 자리에 오는지를 알려주지 않습니다.** 그래서 낱말을 세는
대신, 쓰려는 제목과 같은 관계를 가진 **실제 제목 문장**을 찾아 그 어법을 그대로
가져오는 쪽으로 바꿨습니다.

틀을 뽑아 채우는 방법도 시도했다가 버렸습니다 — 제목 100개에서 두 번 이상
반복되는 골격이 **하나도 없었습니다.** 그쪽도 매번 새로 짓습니다.

사용법
------
    python -m scripts.title_helper 대비          # A는 이런데 B는 반대
    python -m scripts.title_helper 원인          # ~한 이유
    python -m scripts.title_helper 질문
    python -m scripts.title_helper 경고
    python -m scripts.title_helper 개수
    python -m scripts.title_helper --search 금리  # 낱말이 든 제목 찾기
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

INDEX = Path.home() / ".market-brief-bench" / "index.json"

# 관계별 표지. 낱말이 아니라 **제목이 하는 일**로 나눕니다.
RELATIONS = {
    "대비": (r"지만|그런데|그러나|인데도|했는데|만 (상승|하락|올|무너|빠)|"
             r"살 때|아니다|아닙니다|안 (됩니다|되는)",
             "A는 이런데 B는 반대 — 두 사실을 부딪치게 놓습니다"),
    "원인": (r"이유|때문", "무엇이 그렇게 만들었나"),
    "질문": (r"\?|할까|될까|일까|하나$|인가", "앞을 보는 질문. 과거를 되묻지 않습니다"),
    "경고": (r"조심|주의|절대|안심|위험|큰일|아닙니다|안 됩니다", "그대로 믿지 말라"),
    "개수": (r"\d\s*가지|[한두세네다섯]\s*가지|딱 \d|가지만|하나만", "범위를 좁혀 준다"),
    "시한": (r"오늘 밤|분 뒤|내일|이번\s?주|다음\s?주|지금|앞두고", "언제까지인지 못 박는다"),
}


def load_titles() -> list[str]:
    if not INDEX.exists():
        raise SystemExit(f"벤치마크 목록이 없습니다: {INDEX}\n"
                         f"`python -m scripts.bench_watch`로 먼저 모으세요.")
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    return [v["title"] for v in index.values() if v.get("fetched") and v.get("title")]


def find(relation: str, titles: list[str]) -> list[str]:
    pattern, _ = RELATIONS[relation]
    return [t for t in titles if re.search(pattern, t)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("relation", nargs="?", choices=list(RELATIONS))
    parser.add_argument("--search", help="이 낱말이 든 제목만")
    parser.add_argument("--limit", type=int, default=15)
    args = parser.parse_args()

    titles = load_titles()
    if args.search:
        hits = [t for t in titles if args.search in t]
        print(f"'{args.search}'이(가) 든 제목 {len(hits)}개")
    elif args.relation:
        hits = find(args.relation, titles)
        print(f"[{args.relation}] {RELATIONS[args.relation][1]}")
        print(f"제목 {len(titles)}개 중 {len(hits)}개\n")
    else:
        for name, (_, why) in RELATIONS.items():
            print(f"  {name:<4} {len(find(name, titles)):>3}개  {why}")
        return 0

    for title in hits[:args.limit]:
        print(f"  {title}")
    print("\n이 문장들의 **어법을 그대로 가져와** 우리 사실로 갈아입히십시오. "
          "낱말을 세어 새로 짓지 마십시오 — 빈도는 그 낱말이 어느 자리에 오는지를 "
          "알려주지 않습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
