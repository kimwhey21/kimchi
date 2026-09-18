"""영어 가이드의 **주제 큐** — 서치콘솔 검색어를 "오늘 무엇을 할지"로 바꾼다 (2026-09-14).

    python -m src.search_queue                  # 워드프레스에서 영어 글 목록을 받아 큐를 찍는다
    python -m src.search_queue --posts p.json   # 받아 둔 목록으로(오프라인)

왜 이것인가: 영어 가이드는 **상시 검색 글**이다. 순위를 정하는 것은 검색 수요·경쟁·페이지 신뢰도이지
오늘 뉴스가 아니다. 그래서 주제를 뉴스(아침 레이더)로 고르려던 것을 접고, **이미 우리에게 오고 있는
노출**에서 고른다. 2026-09-14 실측이 그 이유를 그대로 보여 준다 — `kospi trading hours`는 노출 6인데
게재순위 **66위**였다. 그 주제의 글을 이미 갖고 있는데도 그렇다. 새 글 한 편을 더 쓰는 것보다
그 글을 고치는 것이 먼저다.

숫자는 `data/search_queries.json`(이 맥의 `~/.market-brief-google/gsc_queries.py`가 주 1회 커밋한다).
루틴은 서치콘솔에 로그인할 수 없으므로 파일로 건넨다 — `data/benchmark_stats.json`과 같은 방식이다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUERIES = ROOT / "data" / "search_queries.json"
POSTS_URL = "https://fermata.it.kr/wp-json/wp/v2/posts?categories=153&per_page=100&_fields=title,slug,link"

# 순위별 대략적인 클릭률. 업계 통용값이고 **우리 사이트에서 잰 값이 아니다** — 순서를 매기는 데만 쓰고
# "이만큼 는다"고 글에 적지 않는다. 우리 CTR은 아직 0.6%라 자체 곡선을 만들 표본이 없다.
CTR_CURVE = ((1, 0.28), (2, 0.15), (3, 0.10), (5, 0.07), (10, 0.03), (20, 0.012), (10**9, 0.003))
TARGET_POSITION = 3
# 클릭 차이만 보면 **80위짜리가 늘 이긴다** — 3위까지 올리면 얻는 것이 크니까. 그런데 80위에서 3위로
# 가는 것과 6위에서 3위로 가는 것은 드는 일이 다르다. 그래서 "올리기 쉬운 정도"를 곱한다.
# 전용 글이 있는데 20위 밖인 경우를 따로 높게 본다 — 색인도 됐고 글도 있으니 어려운 부분은 이미 끝났고,
# 보통 제목·첫 절에 그 검색어가 없어서 밀린 것이다(실측: `kospi trading hours` 66위, 전용 글 있음).
# 이 값은 **판단이지 우리가 잰 수가 아니다.** 순서를 매기는 데만 쓰고 글에 적지 않는다.
def feasibility(position: float, has_post: bool) -> float:
    if position <= 10:
        return 1.0
    if position <= 20:
        return 0.6
    return 0.5 if has_post else 0.15
STOP = {"vs", "the", "a", "an", "to", "in", "of", "for", "is", "how", "what", "and", "or",
        "on", "at", "do", "does", "can", "are", "with", "my", "you", "your", "it", "site"}

# 검색 의도(2026-09-18, 사장님 "2번 진행" — 행동 의도 검색어로 재편). '정의형'(what is·meaning·difference)은
# 구글 AI 개요가 답을 화면에 먼저 써 줘서 1위여도 클릭이 적고, '행동형'(how to·buy·broker·account·etf·tax·hours·
# holiday)은 사람이 결국 페이지를 열어야 하며 제휴가 붙는 자리다. 둘 다 걸리면 행동형으로 본다.
# 이 값도 판단이지 잰 수가 아니다 — 순서를 매기는 데만 쓴다.
INTENT_ACTION = re.compile(r"how to|buy|broker|account|etf|tax|fee|cost|hours|open time|holiday|calendar|"
                           r"schedule|dividend|withholding|record date|ticker|\b(ewy|flkr|koru)\b")
INTENT_DEFINE = re.compile(r"^what is|meaning|difference|explained|\bvs\b")
INTENT_WEIGHT = {"행동": 1.3, "정의": 0.7, "중립": 1.0}


def intent(query: str) -> str:
    q = query.lower()
    if INTENT_ACTION.search(q):
        return "행동"
    if INTENT_DEFINE.search(q):
        return "정의"
    return "중립"


def ctr_at(position: float) -> float:
    for edge, value in CTR_CURVE:
        if position <= edge:
            return value
    return CTR_CURVE[-1][1]


def tokens(text: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", text.lower()) if len(w) > 1 and w not in STOP}


def covering_post(query: str, posts: list[dict]) -> tuple[dict | None, float]:
    """이 검색어를 이미 다루는 글이 있는가 — 제목과 slug의 낱말로 본다. (글, 확신도)를 돌려준다.

    낱말 겹침이라 완벽하지 않다. 그래서 **찾은 글을 함께 찍고 확신도까지 넘겨** 루틴이 판단하게 한다.
    "있다/없다"만 돌려주면 틀렸을 때 알아챌 방법이 없다.
    """
    want = tokens(query)
    if not want:
        return None, 0.0
    best, best_score = None, 0.0
    for post in posts:
        have = tokens(str(post.get("slug", "")) + " " + str((post.get("title") or {}).get("rendered", post.get("title", ""))))
        score = len(want & have) / len(want)
        if score > best_score:
            best, best_score = post, score
    if best_score < 0.6:
        return None, best_score
    # 낱말이 하나뿐인 검색어(`what is kospi` → `kospi`)는 그 낱말이 든 아무 글에나 붙는다.
    # 실측: `what is kospi`가 ETF 글로 짝지어졌는데 맞는 글은 `kospi vs kosdaq`이었다.
    # 그래서 **짝지었다고 단정하지 않고 "확인 필요"로 넘긴다** — 틀린 짝을 사실로 넘기면 루틴이 엉뚱한 글을 고친다.
    return best, (1.0 if len(want) >= 2 else 0.5)


def build(data: dict, posts: list[dict]) -> list[dict]:
    rows = []
    for row in data.get("queries", []):
        position = float(row.get("position") or 0) or 999.0
        impressions = int(row.get("impressions") or 0)
        post, sure = covering_post(row["query"], posts)
        kind = intent(row["query"])
        gain = (impressions * max(0.0, ctr_at(TARGET_POSITION) - ctr_at(position))
                * feasibility(position, post is not None) * INTENT_WEIGHT[kind])
        if post and sure < 1.0:
            action = "먼저 확인 — 낱말이 하나뿐이라 짝이 맞는지 글을 열어 보십시오"
        elif post and position > 20:
            action = "글 고치기 — 전용 글이 있는데 순위가 밀렸습니다"
        elif post:
            action = "글 고치기 — 한 계단만 올리면 1페이지 위쪽입니다"
        elif position <= 20:
            action = "새 글 — 전용 글 없이도 이만큼 왔습니다"
        else:
            action = "새 글 — 수요는 있는데 우리 글이 없습니다"
        rows.append({**row, "position": position, "gain": round(gain, 2), "intent": kind,
                     "post": (post or {}).get("slug"), "sure": sure, "action": action})
    return sorted(rows, key=lambda r: -r["gain"])


def _posts(path: Path | None) -> list[dict]:
    if path:
        return json.loads(path.read_text(encoding="utf-8"))
    import requests                                   # 루틴·이 맥 둘 다 네트워크가 열려 있다
    response = requests.get(POSTS_URL, timeout=20)
    response.raise_for_status()
    return response.json()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--posts", type=Path, help="영어 글 목록 JSON(없으면 워드프레스에서 받는다)")
    ap.add_argument("--top", type=int, default=12)
    a = ap.parse_args(argv)
    if not QUERIES.exists():
        raise SystemExit(f"{QUERIES}가 없습니다 — 이 맥에서 `python3 ~/.market-brief-google/gsc_queries.py`를 먼저 돌리십시오.")
    data = json.loads(QUERIES.read_text(encoding="utf-8"))
    rows = build(data, _posts(a.posts))
    print(f"검색어 큐 — {data['date']} 수집, 검색어 {len(data['queries'])}개, 창 {data.get('window') or '기본'} "
          f"(총 노출 {data.get('total_impressions')}, 클릭 {data.get('total_clicks')})")
    print(f"위에서부터 고릅니다. gain은 '3위까지 올렸을 때 {data.get('window') or '이 창'} 동안 늘어날 클릭'의 어림치입니다"
          f" — 올리기 쉬운 정도를 곱한 값입니다. 업계 CTR 곡선과 판단이지 우리가 잰 수가 아니니 순서를 매기는 데만 씁니다.\n")
    for row in rows[:a.top]:
        page = (f"→ /{row['post']}/" + ("  [짝 확인 필요]" if row["sure"] < 1.0 else "")) if row["post"] else "→ (없음)"
        print(f"  gain {row['gain']:5.2f}  노출 {row['impressions']:3d}  {row['position']:5.1f}위  {row['intent']}  "
              f"{row['query']:44s} {page}")
        print(f"        {row['action']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
