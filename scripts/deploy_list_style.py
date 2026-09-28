"""본진 홈·목록 스타일과 정사각 썸네일 장치(templates/wp_list_toss.php)를 Code Snippets에 올린다 (2026-09-27).

    python -m scripts.deploy_list_style          # 바뀌었으면 올리고 캐시를 지운다
    python -m scripts.deploy_list_style --dry    # 올릴 내용의 길이와 대상 조각만 본다

조각 이름으로 찾아 있으면 갱신, 없으면 만든다. 조각이 코드 오류를 내면 Code Snippets가 조각을 끄므로
응답의 code_error를 보고 예외로 멈춘다(조용한 실패 금지).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "templates" / "wp_list_toss.php"
NAME = "홈·목록 토스피드 3색 + 정사각 썸네일"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"}


def code(source: Path = SOURCE) -> str:
    text = source.read_text(encoding="utf-8")
    return text.split("<?php", 1)[1].lstrip("\n") if text.startswith("<?php") else text


def main(argv: list[str] | None = None) -> int:
    dry = "--dry" in (argv if argv is not None else sys.argv[1:])
    return deploy(SOURCE, NAME, "templates/wp_list_toss.php가 원본. scripts/deploy_list_style.py로 올린다.", dry=dry)


def deploy(source: Path, name: str, desc: str, *, dry: bool = False, scope: str = "global", active: bool = True) -> int:
    """조각 하나를 이름으로 찾아 올린다 — 종목 데이터베이스 조각(scripts/deploy_stock_db.py)도 이 함수를 쓴다."""
    load_dotenv(ROOT / ".env")
    base = os.environ["WORDPRESS_URL"].rstrip("/")
    auth = (os.environ["WORDPRESS_USERNAME"], os.environ["WORDPRESS_APP_PASSWORD"])
    body = code(source)
    snippets = requests.get(f"{base}/wp-json/code-snippets/v1/snippets", auth=auth, headers=UA, timeout=60)
    snippets.raise_for_status()
    mine = [s for s in snippets.json() if s.get("name") == name]
    print(f"조각: {'#' + str(mine[0]['id']) if mine else '새로 만듦'} · 코드 {len(body)}자")
    if dry:
        return 0
    if mine and mine[0].get("code", "").strip() == body.strip() and bool(mine[0].get("active")) == active:
        print("바뀐 것 없음 — 올리지 않음")
        return 0
    payload = {"name": name, "code": body, "scope": scope, "active": active, "priority": 10, "desc": desc}
    url = f"{base}/wp-json/code-snippets/v1/snippets" + (f"/{mine[0]['id']}" if mine else "")
    response = requests.post(url, json=payload, auth=auth, headers=UA, timeout=90)
    response.raise_for_status()
    got = response.json()
    if got.get("code_error") or bool(got.get("active")) != active:
        raise RuntimeError(f"조각 상태가 기대({'켜짐' if active else '꺼짐'})와 다릅니다: {got.get('code_error')}")
    print(f"조각 #{got['id']} {'갱신' if mine else '생성'} · {'켜짐' if active else '꺼짐'}")
    requests.post(f"{base}/wp-json/wp-super-cache/v1/cache", json={"delete_cache": True}, auth=auth, headers=UA, timeout=60)
    print("캐시 지움")
    from src.cloudflare import purge_all
    purge_all()
    return 0


if __name__ == "__main__":
    sys.exit(main())
