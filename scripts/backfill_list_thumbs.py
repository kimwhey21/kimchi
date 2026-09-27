"""이미 올라간 영어 글에 3색 분류와 목록용 정사각 썸네일을 소급한다 (2026-09-27, 사장님 "썸네일 4번 3색판으로 가자").

    python -m scripts.backfill_list_thumbs --dry   # 무엇을 할지만
    python -m scripts.backfill_list_thumbs         # 실제로

- 영어 시황(editorial-<market>-<날짜>-en): 분류를 Daily + Korea Close/Wall Street Close로, 정사각 썸네일을
  원고의 시세·한국어 원고로 그려(발행 때와 같은 `featured_image.create_square`) 메타에 적는다.
- 영어 가이드(editorial/guides/en_*.json): 대표 그래픽이 cover·guide_cover면 정사각 판을 그려 메타에 적는다.
- Daily 분류의 글 가운데 원고와 이어지지 않는 옛 글(8/28·8/31 한국장, 글 34·173)은 분류만 한국장으로.
Cafe24 공유 호스팅이라 요청 사이에 쉰다. 글 본문과 대표 이미지는 건드리지 않는다.
"""
from __future__ import annotations

import glob
import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from src import featured_image, publish_editorial, publish_feature, publish_wordpress  # noqa: E402

OLD_KR = {34, 173}   # 옛 형식 한국장 영어 글(주소가 editorial-…-en이 아니다)
OUT = ROOT / "output" / "list_thumbs"
GAP = 4


def main(argv: list[str] | None = None) -> int:
    dry = "--dry" in (argv if argv is not None else sys.argv[1:])
    base = os.environ["WORDPRESS_URL"].rstrip("/")
    auth = (os.environ["WORDPRESS_USERNAME"], os.environ["WORDPRESS_APP_PASSWORD"])
    ids = publish_editorial.MARKET_CATEGORY_IDS
    done = {"daily_cat": 0, "daily_sq": 0, "guide_sq": 0}
    missed: list[str] = []
    seen_ids: set[int] = set()

    for path in sorted(glob.glob(str(ROOT / "editorial" / "*.json"))):
        name = Path(path).stem
        if not (name.startswith("kr_") or name.startswith("us_")):
            continue
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        if not doc.get("en"):
            continue
        market, date_str = name[:2], name[3:]
        post = publish_wordpress._find_existing_post_by_slug(base, auth, f"editorial-{market}-{date_str}-en")
        time.sleep(GAP)
        if not post or post.get("status") != "publish":
            missed.append(f"{name}: 공개 글 없음")
            continue
        seen_ids.add(post["id"])
        cats = [publish_editorial.DAILY_CATEGORY_ID, ids[market]]
        square = featured_image.create_square(market, date_str, doc.get("price_data") or {},
                                              OUT / f"{name}_square_en.png", doc.get("ko"), lang="en")
        print(f"{name} → 글 {post['id']} · 분류 {cats} · 썸네일 {square['layout']}")
        if dry:
            continue
        r = publish_wordpress._request("post", f"{base}/wp-json/wp/v2/posts/{post['id']}", auth=auth,
                                       json={"categories": cats}, timeout=publish_wordpress.TIMEOUT_SECONDS)
        r.raise_for_status()
        done["daily_cat"] += 1
        time.sleep(GAP)
        publish_wordpress.set_square_thumb(post["id"], square)
        done["daily_sq"] += 1
        time.sleep(GAP)

    for pid in sorted(OLD_KR):
        print(f"옛 한국장 글 {pid} → 분류 {[publish_editorial.DAILY_CATEGORY_ID, ids['kr']]} (썸네일 없음: 원고에 영어판 없음)")
        if not dry:
            r = publish_wordpress._request("post", f"{base}/wp-json/wp/v2/posts/{pid}", auth=auth,
                                           json={"categories": [publish_editorial.DAILY_CATEGORY_ID, ids["kr"]]},
                                           timeout=publish_wordpress.TIMEOUT_SECONDS)
            r.raise_for_status()
            done["daily_cat"] += 1
            time.sleep(GAP)
        seen_ids.add(pid)

    # 같은 글(slug)을 가리키는 원고가 둘이면 확인 날짜(checked, 없으면 date)가 늦은 것 하나만 — 9/27에 KOSPI vs KOSDAQ
    # 옛 원고(9/15)가 이름 순서로 뒤에 와서 9/21에 고친 원고의 썸네일을 덮을 뻔했다.
    latest: dict[str, tuple[str, str]] = {}
    for path in sorted(glob.glob(str(ROOT / "editorial" / "guides" / "en_*.json"))):
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        slug = publish_feature._slug(doc, Path(path))
        stamp = str(doc.get("checked") or doc.get("date") or "")
        if slug not in latest or stamp > latest[slug][0]:
            latest[slug] = (stamp, path)
    for slug, (_, path) in sorted(latest.items()):
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        post = publish_wordpress._find_existing_post_by_slug(base, auth, slug)
        time.sleep(GAP)
        if not post or post.get("status") != "publish":
            missed.append(f"{Path(path).name}: 공개 글 없음({slug})")
            continue
        seen_ids.add(post["id"])
        square = publish_feature._square_thumb(doc, OUT / Path(path).stem)
        if not square:
            missed.append(f"{Path(path).name}: 네모 판 없음")
            continue
        print(f"{Path(path).name} → 글 {post['id']}")
        if dry:
            continue
        publish_wordpress.set_square_thumb(post["id"], square)
        done["guide_sq"] += 1
        time.sleep(GAP)

    # 원고와 이어지지 않은 공개 영어 글(목록은 가로 표지를 틀 안에 넣어 보여 준다)
    others = []
    for cat in (publish_editorial.DAILY_CATEGORY_ID, 153):
        r = requests.get(f"{base}/wp-json/wp/v2/posts", params={"categories": cat, "per_page": 100, "_fields": "id,slug"},
                         auth=auth, timeout=60)
        r.raise_for_status()
        others += [f"{p['id']} {p['slug']}" for p in r.json() if p["id"] not in seen_ids]
        time.sleep(GAP)
    print(f"끝: {done} · 못 한 것 {len(missed)}")
    for line in missed:
        print(f"  - {line}")
    print(f"원고와 이어지지 않은 공개 글 {len(others)}편(네모 썸네일 없음 — 틀 안에 통째로):")
    for line in others:
        print(f"  - {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
