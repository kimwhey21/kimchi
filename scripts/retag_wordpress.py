"""이미 올라간 워드프레스 한국어 글의 태그를 글에서 뽑은 것으로 바꾼다 (2026-09-12, 사용자: "이미 올라간 글도 고쳐").

    python -m scripts.retag_wordpress            # 무엇을 어떻게 바꿀지 보여만 준다
    python -m scripts.retag_wordpress --apply    # 실제로 바꾼다 (본문·상태는 건드리지 않는다)

대상: editorial/*.json(한국어 시황), editorial/features, editorial/previews, editorial/weekly.
영어 글은 그대로 둔다. 글은 slug로 찾고, 없으면 건너뛴다(만들지 않는다).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

from src import post_tags, publish_wordpress

ROOT = Path(__file__).resolve().parent.parent


def _slug_of(doc: dict, path: Path) -> str:
    if doc.get("market") in ("kr", "us"):
        return f"editorial-{doc['market']}-{doc['date']}-ko"
    if doc.get("slug"):
        return str(doc["slug"])
    if doc.get("series") == "프리뷰":
        return f"us-{doc['date']}-preview"
    return path.stem.replace("_", "-", 1).replace("_", "-")


def manuscripts() -> list[Path]:
    paths = []
    for pattern in ("editorial/*.json", "editorial/features/*.json", "editorial/previews/*.json", "editorial/weekly/*.json"):
        paths += [Path(p) for p in glob.glob(str(ROOT / pattern))]
    return sorted(paths)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    load_dotenv(dotenv_path=ROOT / ".env")
    base = os.environ["WORDPRESS_URL"].rstrip("/")
    auth = (os.environ["WORDPRESS_USERNAME"], os.environ["WORDPRESS_APP_PASSWORD"])
    changed = skipped = 0
    for path in manuscripts():
        doc = json.loads(path.read_text(encoding="utf-8"))
        slug = _slug_of(doc, path)
        found = requests.get(f"{base}/wp-json/wp/v2/posts", auth=auth, timeout=30,
                             params={"slug": slug, "status": "any", "_fields": "id,status,tags,title"}).json()
        if not found:
            print(f"건너뜀 (글 없음): {path.name} → {slug}")
            skipped += 1
            continue
        post = found[0]
        tags = post_tags.build_tags(doc)
        print(f"{post['id']:>5} {post['status']:<8} {path.name}: {len(post['tags'])}개 → {len(tags)}개 {tags}")
        if args.apply:
            ids = publish_wordpress._get_or_create_tag_ids(base, auth, tags)
            r = requests.post(f"{base}/wp-json/wp/v2/posts/{post['id']}", auth=auth, json={"tags": ids}, timeout=60)
            r.raise_for_status()
            back = requests.get(f"{base}/wp-json/wp/v2/posts/{post['id']}", auth=auth,
                                params={"_fields": "id,tags,status"}, timeout=30).json()
            if sorted(back["tags"]) != sorted(ids) or back["status"] != post["status"]:
                raise SystemExit(f"되읽기 불일치: {post['id']} tags={back['tags']} status={back['status']}")
            changed += 1
    print(f"{'바꿈' if args.apply else '바꿀 것'} {changed if args.apply else '-'} · 건너뜀 {skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
