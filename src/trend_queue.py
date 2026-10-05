"""영어 가이드의 **트렌드 큐** — 우리 분야 안에서 새로 뜨는 검색어를 "오늘 쓸 것"으로 (2026-09-27).

    python -m src.trend_queue                    # 오늘의 트렌드 큐(루틴이 읽는다)
    python -m src.trend_queue --week             # 이번 주 트렌드 몫(새 글 2 + 고치기 1)을 얼마나 썼나
    python -m src.trend_queue collect [--trends t.json] [--no-autocomplete]   # 신호를 모아 data/trend_signals.json에 쌓는다

왜: 사장님 "최신 트렌드 인기 급상승 검색어를 추적해서 검색이나 유입을 많이 늘릴수 있는 그에 관한 글을 쓸수 있을까?"
`search_queue`는 **이미 우리에게 오는 노출**에서 고른다 — 새로 뜨는 질문은 우리 글이 없으면 거기 나타나지 않는다.
그래서 세 신호를 따로 모은다.

- 구글 자동완성(`suggestqueries`, 브라우저 없이): 씨앗마다 **어제 없던 제안**이 곧 새로 생긴 질문이다.
  첫 수집은 기준선이라 "새것"으로 치지 않는다(`baseline`).
- 구글 트렌드 급상승 관련 검색어: 이 맥이 로그인 브라우저로 받아 `--trends`로 넘긴다(`~/.market-brief-google/trend_collect.py`).
- 서치콘솔: `data/search_queries.json`에 **처음 나타난** 검색어.

분야 밖(스포츠·연예·일반 뉴스, 게임 모드 같은 잡음)은 `config/trend_seeds.yaml`의 `niche`·`exclude`로 거른다.
점수는 순서를 매기는 데만 쓴다 — 검색량이 아니다. 글에 적지 않는다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import re
import sys
import time
from pathlib import Path

import yaml

from src import search_queue

ROOT = Path(__file__).resolve().parent.parent
SEEDS = ROOT / "config" / "trend_seeds.yaml"
SIGNALS = ROOT / "data" / "trend_signals.json"
GUIDES = ROOT / "editorial" / "guides"
SUGGEST_URL = "https://suggestqueries.google.com/complete/search"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"}
FRESH_DAYS = 14          # 처음 본 지 이만큼 안 된 자동완성·서치콘솔 검색어만 "새것"
TRENDS_DAYS = 7          # 트렌드 급상승은 일주일
WEEK_QUOTA = {"new": 2, "update": 1}   # 주 7편 가운데 트렌드 몫(2026-09-27)


def load_seeds(path: Path = SEEDS) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def relevant(query: str, seeds: dict) -> bool:
    q = query.lower()
    if any(word in q for word in seeds.get("exclude") or []):
        return False
    return any(re.search(r"(?<![a-z])" + re.escape(word) + r"(?![a-z])", q) for word in seeds.get("niche") or [])


def autocomplete(query: str, get=None) -> list[str]:
    get = get or __import__("requests").get
    response = get(SUGGEST_URL, params={"client": "firefox", "hl": "en", "gl": "us", "q": query}, headers=UA, timeout=20)
    response.raise_for_status()
    data = response.json()
    return [str(s).strip().lower() for s in (data[1] if len(data) > 1 else []) if str(s).strip()]


def _record(queries: dict, query: str, today: str, source: str, seed: str, baseline: bool, rising: str | None = None) -> None:
    row = queries.get(query)
    if row is None:
        row = queries[query] = {"first_seen": today, "last_seen": today, "sources": [], "seed": seed, "days": 0}
        if baseline:
            row["baseline"] = True
    if row["last_seen"] != today:
        row["days"] = int(row.get("days") or 0) + 1
    row["last_seen"] = today
    if source not in row["sources"]:
        row["sources"].append(source)
    if rising:
        row["rising"] = rising
        row["rising_seen"] = today


def collect(signals: dict, today: str, seeds: dict, *, trends: dict | None = None, gsc: dict | None = None,
            suggest=autocomplete, pause: float = 0.8) -> dict:
    """신호를 쌓는다. 자동완성은 씨앗×접두어마다 한 번. 실패는 세어서 남긴다(조용한 실패 금지)."""
    queries = signals.setdefault("queries", {})
    first_autocomplete = not any("autocomplete" in r.get("sources", []) for r in queries.values())
    failed = 0
    if suggest is not None:
        for seed in seeds.get("autocomplete") or []:
            for prefix in seeds.get("prefixes") or [""]:
                try:
                    for s in suggest(prefix + seed):
                        _record(queries, s, today, "autocomplete", seed, baseline=first_autocomplete)
                except Exception as error:  # noqa: BLE001 — 세어서 남긴다
                    failed += 1
                    print(f"[경고] 자동완성 실패 {prefix + seed!r}: {error}")
                if pause:
                    time.sleep(pause)
    for seed, rows in (trends or {}).items():
        for row in rows:
            _record(queries, str(row["query"]).strip().lower(), today, "trends", seed, baseline=False, rising=str(row.get("value") or ""))
    first_gsc = not any("gsc" in r.get("sources", []) for r in queries.values())
    for row in (gsc or {}).get("queries") or []:
        _record(queries, str(row["query"]).strip().lower(), today, "gsc", "search console", baseline=first_gsc)
        queries[str(row["query"]).strip().lower()]["gsc"] = {k: row.get(k) for k in ("impressions", "clicks", "position")}
    signals["updated"] = today
    signals.setdefault("runs", []).append({"date": today, "autocomplete_failed": failed,
                                           "trends_seeds": len(trends or {}), "gsc": len((gsc or {}).get("queries") or [])})
    signals["runs"] = signals["runs"][-60:]
    return signals


def _age(day: str, today: str) -> int:
    return (dt.date.fromisoformat(today) - dt.date.fromisoformat(day)).days


def score(row: dict, today: str) -> float:
    s = 0.0
    if row.get("rising") and _age(row.get("rising_seen", today), today) <= TRENDS_DAYS:
        value = row["rising"]
        m = re.search(r"\+?([\d,]+)%", value)
        s += 3.0 if value.lower() == "breakout" else min(3.0, 1.0 + (int(m.group(1).replace(",", "")) / 100 if m else 0))
    if not row.get("baseline") and _age(row["first_seen"], today) <= FRESH_DAYS:
        if "autocomplete" in row.get("sources", []):
            s += 2.0 if _age(row["first_seen"], today) <= 3 else 1.0
        if "gsc" in row.get("sources", []):
            s += 1.0 + min(2.0, int((row.get("gsc") or {}).get("impressions") or 0) / 10)
    return s


def build(signals: dict, today: str, seeds: dict, posts: list[dict]) -> list[dict]:
    out = []
    for query, row in (signals.get("queries") or {}).items():
        if not relevant(query, seeds):
            continue
        base = score(row, today)
        if base <= 0:
            continue
        kind = search_queue.intent(query)
        post, sure = search_queue.covering_post(query, posts)
        action = ("기존 글 고치기 — 이 검색어를 제목·첫 소제목·첫 문장에" if post and sure >= 1.0 else
                  "먼저 확인 — 짝지은 글이 맞는지 열어 보십시오" if post else "새 글 — 첫 줄부터 이 질문에 답하는 글")
        out.append({"query": query, "score": round(base * search_queue.INTENT_WEIGHT[kind], 2), "intent": kind,
                    "signals": row.get("sources"), "rising": row.get("rising"), "first_seen": row["first_seen"],
                    "seed": row.get("seed"), "post": (post or {}).get("slug"), "action": action})
    return sorted(out, key=lambda r: (-r["score"], r["query"]))


def week_usage(today: str, guides_dir: Path = GUIDES) -> dict:
    """이번 주(월~일)에 트렌드 큐로 쓴 몫 — 원고 최상위 `trend_origin`({query, date, kind: new|update})을 센다."""
    day = dt.date.fromisoformat(today)
    start = (day - dt.timedelta(days=day.weekday())).isoformat()
    used = {"new": [], "update": []}
    for path in sorted(glob.glob(str(guides_dir / "en_*.json"))):
        try:
            origin = json.loads(Path(path).read_text(encoding="utf-8")).get("trend_origin") or {}
        except ValueError:
            continue
        if origin.get("kind") in used and start <= str(origin.get("date") or "") <= today:
            used[origin["kind"]].append(f"{origin.get('query')} ({Path(path).name})")
    return used


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("command", nargs="?", default="queue", choices=["queue", "collect"])
    ap.add_argument("--week", action="store_true")
    ap.add_argument("--trends", type=Path, help="이 맥이 받은 트렌드 급상승 JSON {씨앗: [{query, value}]}")
    ap.add_argument("--no-autocomplete", action="store_true")
    ap.add_argument("--posts", type=Path)
    ap.add_argument("--top", type=int, default=10)
    a = ap.parse_args(argv)
    today = dt.date.today().isoformat()
    seeds = load_seeds()
    signals = json.loads(SIGNALS.read_text(encoding="utf-8")) if SIGNALS.exists() else {}
    if a.command == "collect":
        trends = json.loads(a.trends.read_text(encoding="utf-8")) if a.trends else None
        gsc = json.loads(search_queue.QUERIES.read_text(encoding="utf-8")) if search_queue.QUERIES.exists() else None
        collect(signals, today, seeds, trends=trends, gsc=gsc, suggest=None if a.no_autocomplete else autocomplete)
        SIGNALS.parent.mkdir(parents=True, exist_ok=True)
        SIGNALS.write_text(json.dumps(signals, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        run = signals["runs"][-1]
        print(f"트렌드 신호 {len(signals['queries'])}개 저장 — 자동완성 실패 {run['autocomplete_failed']}, "
              f"트렌드 씨앗 {run['trends_seeds']}, 서치콘솔 {run['gsc']}")
        return 0
    used = week_usage(today)
    left = {k: WEEK_QUOTA[k] - len(v) for k, v in used.items()}
    print(f"이번 주 트렌드 몫: 새 글 {len(used['new'])}/{WEEK_QUOTA['new']}, 고치기 {len(used['update'])}/{WEEK_QUOTA['update']}")
    for kind, rows in used.items():
        for row in rows:
            print(f"  - {kind}: {row}")
    if a.week:
        return 0
    if not signals:
        print("트렌드 신호 파일이 없습니다 — 이 맥의 trend_collect가 아직 안 돌았습니다. 검색어 큐(search_queue)로 고르십시오.")
        return 0
    stale = _age(signals.get("updated", "2000-01-01"), today)
    if stale > 2:
        print(f"[주의] 신호가 {stale}일 전 것입니다 — 이 맥의 수집이 멈췄을 수 있습니다.")
    rows = build(signals, today, seeds, search_queue._posts(a.posts))
    if not rows:
        print("오늘은 우리 분야의 새 급상승 검색어가 없습니다 — 검색어 큐(search_queue)로 고르십시오.")
        return 0
    if left["new"] <= 0 and left["update"] <= 0:
        print("이번 주 트렌드 몫을 다 썼습니다 — 검색어 큐(search_queue)로 고르십시오.")
    print(f"\n트렌드 큐 — 신호 {signals.get('updated')} (점수는 순서용, 검색량 아님)")
    for row in rows[:a.top]:
        page = f"→ /{row['post']}/" if row["post"] else "→ (없음)"
        rising = f" 급상승 {row['rising']}" if row.get("rising") else ""
        print(f"  {row['score']:4.1f}  {row['intent']}  {row['query']:48s} {page}  [{','.join(row['signals'])}{rising}, 처음 {row['first_seen']}]")
        print(f"        {row['action']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
