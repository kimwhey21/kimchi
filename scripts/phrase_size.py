"""검색되는 말 후보의 크기를 잰다 — 그 말로 쓴 블로그 글이 몇 편인지(경쟁)와, 좁은 말인지 넓은 말인지.

    python -m scripts.phrase_size "후보1" "후보2" "후보3"      # 좁은 말부터 차례로
    python -m scripts.phrase_size --json "후보1" "후보2"

쓰는 자리: 「실험」 절의 검색되는 말 고르기(`docs/routine_magazine.md`·`routine_column.md`·`routine_guide_ko.md`).
넓은 말(글이 십만 편 안팎부터)로는 새 글이 앞에 서지 못한다 — 같은 이야기라도 더 좁힌 말(이름+사건, 이름+제도)을 찾는다.
원천은 NAVER API HUB 블로그 검색(공식, 화면을 긁지 않는다). 열쇠는 환경변수 `NAVER_CLIENT_ID`·`NAVER_CLIENT_SECRET`,
이 맥에서는 `~/.market-brief-naver/naver_api.env`. 열쇠 값은 어디에도 찍지 않는다.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://naverapihub.apigw.ntruss.com/search/v1/blog"
KEY_FILE = Path.home() / ".market-brief-naver" / "naver_api.env"
# 띠의 문턱(경쟁 글 수). 실측으로 정했다 — 내력은 비공개 기록. 바꿀 때는 그 뒤 올린 글의 순위를 다시 보고 바꾼다.
NARROW, MIDDLE = 15_000, 60_000
BANDS = ("좁음", "보통", "넓음")
# 한 번에 받는 건수. **30을 넘기지 않는다** — 100건을 한 번에 받으면 맨 앞 30건이 31~60번째로 밀려 나와 순위가 30씩 틀린다
# (2026-11-10 실측: 10건씩 세 쪽과 30건 한 쪽은 순서가 같고, 100건 한 번은 다르다).
PAGE = 30


class NoKeys(RuntimeError):
    """열쇠가 없다 — 조용히 넘어가지 않고 알린다."""


def load_keys() -> tuple[str, str]:
    cid, sec = os.environ.get("NAVER_CLIENT_ID", ""), os.environ.get("NAVER_CLIENT_SECRET", "")
    if not (cid and sec) and KEY_FILE.exists():
        env = dict(line.strip().split("=", 1) for line in KEY_FILE.read_text(encoding="utf-8").splitlines() if "=" in line)
        cid, sec = env.get("NAVER_CLIENT_ID", ""), env.get("NAVER_CLIENT_SECRET", "")
    if not (cid and sec):
        raise NoKeys("NAVER_CLIENT_ID·NAVER_CLIENT_SECRET가 없습니다 — 환경변수(루틴) 또는 ~/.market-brief-naver/naver_api.env(맥)")
    return cid, sec


def search(query: str, start: int = 1, display: int = PAGE, keys: tuple[str, str] | None = None) -> dict:
    """블로그 검색 한 쪽(관련도순). 실패는 예외로 올린다. display는 PAGE 이하로만 쓴다(위 PAGE 설명)."""
    cid, sec = keys or load_keys()
    url = API + "?" + urllib.parse.urlencode({"query": query, "display": display, "start": start, "sort": "sim"})
    req = urllib.request.Request(url, headers={"X-NCP-APIGW-API-KEY-ID": cid, "X-NCP-APIGW-API-KEY": sec})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def band(total: int) -> str:
    return BANDS[0] if total <= NARROW else BANDS[1] if total <= MIDDLE else BANDS[2]


def size(query: str, keys: tuple[str, str] | None = None) -> dict:
    """그 말의 경쟁 글 수와 띠."""
    total = int(search(query, display=1, keys=keys).get("total") or 0)
    return {"phrase": query, "total": total, "band": band(total)}


def rank(query: str, blog_pattern: str, depth: int = 300, keys: tuple[str, str] | None = None) -> dict:
    """그 말로 검색했을 때 `blog_pattern`(정규식, 블로그 주소에 대조)에 맞는 첫 글의 순위. depth 안에 없으면 rank는 None."""
    keys = keys or load_keys()
    pat, total = re.compile(blog_pattern), 0
    for start in range(1, depth + 1, PAGE):
        page = search(query, start=start, display=PAGE, keys=keys)
        total = int(page.get("total") or 0)
        items = page.get("items") or []
        for i, it in enumerate(items):
            if pat.search(str(it.get("link", ""))) or pat.search(str(it.get("bloggerlink", ""))):
                return {"phrase": query, "total": total, "band": band(total), "rank": start + i,
                        "title": re.sub(r"<[^>]+>", "", str(it.get("title", ""))), "link": str(it.get("link", ""))}
        if len(items) < PAGE:
            break
        time.sleep(0.15)
    return {"phrase": query, "total": total, "band": band(total), "rank": None, "title": "", "link": ""}


def main(argv: list[str]) -> int:
    as_json = "--json" in argv
    phrases = [a for a in argv if not a.startswith("--")]
    if not phrases:
        print(__doc__.strip())
        return 2
    try:
        keys = load_keys()
    except NoKeys as e:
        print(f"⚠ {e}", file=sys.stderr)
        return 2
    rows, failed = [], []
    for p in phrases:
        try:
            rows.append(size(p, keys))
        except (urllib.error.URLError, ValueError, TimeoutError) as e:
            failed.append((p, f"{type(e).__name__}: {e}"))
    rows.sort(key=lambda r: r["total"])
    if as_json:
        print(json.dumps({"rows": rows, "failed": [p for p, _ in failed]}, ensure_ascii=False))
    else:
        for r in rows:
            print(f"{r['band']}  경쟁 글 {r['total']:>9,}편  {r['phrase']}")
        if rows and rows[0]["band"] != BANDS[0]:
            print("→ 좁은 말이 없습니다. 같은 이야기의 더 좁힌 말(이름+사건, 이름+제도, 낯선 고유명사)을 두세 개 더 재 보십시오.")
        elif rows:
            print(f"→ 좁은 말: {', '.join(r['phrase'] for r in rows if r['band'] == BANDS[0])}")
    for p, why in failed:
        print(f"⚠ 받지 못했습니다: {p} ({why})", file=sys.stderr)
    return 3 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
