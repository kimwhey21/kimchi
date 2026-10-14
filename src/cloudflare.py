"""Cloudflare 창고 비우기와 다시 채우기 — 본진 페이지를 Cloudflare가 하루 보관하므로 새 글·새 데이터가 들어오면 함께 비운다 (2026-09-28).

    python -m src.cloudflare            # 전부 비우고 사이트맵 주소를 다시 채운다(손으로 고친 뒤)

워드프레스 캐시(WP Super Cache)를 지우는 곳에서 같이 부른다: 종목 데이터 넣기(stock_db), 조각·템플릿 배포, 글 공개 확인
(publish_wordpress.verify_published). 비우기는 곁가지다 — 실패해도 발행·수집을 멈추지 않고 `[Cloudflare 실패]`를 찍고 운영 대화로 알린다
(보관이 2시간이던 때는 저절로 풀렸지만 2026-10-14부터 하루라 낡은 화면이 하루 남을 수 있다). 열쇠는 CLOUDFLARE_API_TOKEN(이 맥 .env·깃허브 비밀), 권한은 이 영역 하나만.

다시 채우기(2026-10-14): 캐시에 없으면 카페24까지 다녀와 2~4초가 걸리고(한국 방문자는 로스앤젤레스를 거친다), 구글은 드물게 와서
늘 그 느린 쪽을 받았다(서치콘솔 평균 응답 2초). 비운 직후 사이트맵 주소(가이드·데이터 페이지, 검색에 열린 것만)를 차례로 한 번씩 불러 둔다.
카페24는 동시 요청에 약해 하나씩, 사이사이 쉰다.
"""
from __future__ import annotations

import os
import re
import sys
import time

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
            warm()
            return True
        _fail(f"{r.get('errors')}")
    except (requests.RequestException, ValueError) as error:
        _fail(f"{error!r}")
    return False


def _fail(why: str) -> None:
    print(f"[Cloudflare 실패] {why}")
    try:
        from src import alert
        alert.send(f"Cloudflare 창고를 비우지 못했습니다 — 본진에 낡은 화면이 최대 하루 남을 수 있습니다: {why[:200]}", "warn")
    except Exception as error:  # noqa: BLE001 — 알림 실패가 발행을 멈추면 안 된다
        print(f"[Cloudflare 알림 실패] {error!r}")


WARM_PAUSE = 0.7
UA = {"User-Agent": "Mozilla/5.0 (fermata cache warm)"}


def sitemap_urls(get=None) -> list[str]:
    """사이트맵에 실린 주소 전부(검색에 열린 화면만 실린다)."""
    get = get or requests.get
    index = get(f"https://{ZONE}/wp-sitemap.xml", headers=UA, timeout=30).text
    urls: list[str] = []
    for part in re.findall(r"<loc>([^<]+)</loc>", index):
        urls += re.findall(r"<loc>([^<]+)</loc>", get(part, headers=UA, timeout=30).text)
    return urls


def warm(get=None, sleep=None, limit: int = 200) -> int:
    """비운 뒤 사이트맵 주소를 한 번씩 불러 Cloudflare에 다시 채운다. 채운 수를 돌려준다(실패는 세고 넘어간다)."""
    get = get or requests.get   # 부를 때 찾는다 — 시험의 가짜 요청이 닿게
    sleep = sleep or time.sleep
    try:
        urls = sitemap_urls(get)[:limit]
    except (requests.RequestException, TypeError) as error:
        print(f"[Cloudflare 채우기 실패] 사이트맵을 못 읽었습니다: {error!r}")
        return 0
    done = failed = 0
    for url in urls:
        try:
            r = get(url, headers=UA, timeout=60)
            done += r.status_code == 200
            failed += r.status_code != 200
        except requests.RequestException:
            failed += 1
        sleep(WARM_PAUSE)
    print(f"Cloudflare 다시 채움 {done}/{len(urls)}" + (f" (실패 {failed})" if failed else ""))
    return done


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
    sys.exit(0 if purge_all() else 1)
