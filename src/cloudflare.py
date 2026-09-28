"""Cloudflare 창고 비우기 — 본진 페이지를 Cloudflare가 2시간 보관하므로 새 글·새 데이터가 들어오면 함께 비운다 (2026-09-28).

    python -m src.cloudflare            # 전부 비운다(손으로 고친 뒤)

워드프레스 캐시(WP Super Cache)를 지우는 곳에서 같이 부른다: 종목 데이터 넣기(stock_db), 조각·템플릿 배포, 글 공개 확인
(publish_wordpress.verify_published). 비우기는 곁가지다 — 실패해도 발행·수집을 멈추지 않고 `[Cloudflare 실패]`로만 찍는다
(보관 규칙이 2시간이라 그 뒤엔 저절로 새로 받는다). 열쇠는 CLOUDFLARE_API_TOKEN(이 맥 .env·깃허브 비밀), 권한은 이 영역 하나만.
"""
from __future__ import annotations

import os
import sys

import requests

API = "https://api.cloudflare.com/client/v4"
ZONE = "fermata.it.kr"


def purge_all() -> bool:
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    if not token:
        print("[Cloudflare 실패] CLOUDFLARE_API_TOKEN이 없어 창고를 비우지 못했습니다(2시간 뒤 저절로 바뀝니다).")
        return False
    head = {"Authorization": f"Bearer {token}"}
    try:
        zones = requests.get(f"{API}/zones", params={"name": ZONE}, headers=head, timeout=30).json().get("result") or []
        if not zones:
            print(f"[Cloudflare 실패] 영역 {ZONE}을 찾지 못했습니다.")
            return False
        r = requests.post(f"{API}/zones/{zones[0]['id']}/purge_cache", json={"purge_everything": True}, headers=head, timeout=30).json()
        if r.get("success"):
            print("Cloudflare 창고 비움")
            return True
        print(f"[Cloudflare 실패] {r.get('errors')}")
    except (requests.RequestException, ValueError) as error:
        print(f"[Cloudflare 실패] {error!r}")
    return False


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
    sys.exit(0 if purge_all() else 1)
