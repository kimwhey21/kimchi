"""본진 블록 템플릿(templates/wp_site/*.html)을 워드프레스에 올린다 (2026-09-28 템플릿 통일).

    python -m scripts.deploy_templates              # 바뀐 템플릿만 올리고 되읽어 확인, 캐시 지움
    python -m scripts.deploy_templates --dry        # 무엇이 바뀌는지만

이 폴더가 원본이다 — 관리 화면(사이트 편집기)에서 고치면 다음 배포가 덮어쓴다. 모든 템플릿이 메뉴 줄을
`[fermata_nav]`(templates/wp_stock_db.php의 fs_nav) 한 줄로 부른다 — 메뉴를 템플릿에 손으로 쓰지 말 것.
카페24 때문에 한 장씩 3초 간격으로 올린다.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "templates" / "wp_site"
THEME = "twentytwentyfive"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"}


def main(argv: list[str] | None = None) -> int:
    load_dotenv(ROOT / ".env")
    dry = "--dry" in (argv if argv is not None else sys.argv[1:])
    base = os.environ["WORDPRESS_URL"].rstrip("/")
    auth = (os.environ["WORDPRESS_USERNAME"], os.environ["WORDPRESS_APP_PASSWORD"])
    changed = 0
    for path in sorted(SRC.glob("*.html")):
        slug = path.stem
        want = path.read_text(encoding="utf-8")
        if want.count("[fermata_nav]") != 1:
            raise SystemExit(f"{path.name}: 메뉴 줄 [fermata_nav]가 정확히 한 번 있어야 합니다.")
        url = f"{base}/wp-json/wp/v2/templates/{THEME}//{slug}"
        cur = requests.get(url, params={"context": "edit"}, auth=auth, headers=UA, timeout=60)
        cur.raise_for_status()
        if cur.json()["content"]["raw"].strip() == want.strip():
            print(f"{slug}: 같음")
            continue
        changed += 1
        print(f"{slug}: {'바뀜(올리지 않음)' if dry else '올림'}")
        if dry:
            continue
        time.sleep(3)
        r = requests.post(url, json={"content": want}, auth=auth, headers=UA, timeout=60)
        r.raise_for_status()
        if r.json()["content"]["raw"].strip() != want.strip():
            raise SystemExit(f"{slug}: 올렸는데 되읽은 내용이 다릅니다.")
    if changed and not dry:
        requests.post(f"{base}/wp-json/wp-super-cache/v1/cache", json={"delete_cache": True}, auth=auth, headers=UA, timeout=60)
        print("캐시 지움")
        from src.cloudflare import purge_all
        purge_all()
    return 0


if __name__ == "__main__":
    sys.exit(main())
