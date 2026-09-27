"""IndexNow — 본진의 새·바뀐·지운 주소를 빙(과 IndexNow를 받는 검색엔진)에 바로 알린다 (2026-09-28, 사장님 "둘 다 진행해").

    python -m src.indexnow --sitemap          # 사이트맵의 모든 주소를 한 번에(처음 한 번)
    python -m src.indexnow <주소> [<주소>…]    # 몇 개만

빙은 챗GPT 검색·덕덕고가 쓰는 색인이다. 구글은 IndexNow를 받지 않는다(구글은 사이트맵과 서치콘솔 요청).
열쇠는 공개해도 되는 값이다 — 사이트 주인임을 보이려고 https://fermata.it.kr/<열쇠>.txt에 그대로 내놓는다
(templates/wp_stock_db.php가 그 주소에 답한다). 알리기는 곁가지다 — 실패해도 발행·수집을 멈추지 않고 `[IndexNow 실패]`로만 찍는다.
자동으로 부르는 곳: 영어 글 공개 직후(publish_editorial·publish_feature), 종목 목록에 새로 들어오거나 빠진 종목(stock_db.push).
"""
from __future__ import annotations

import re
import sys

import requests

KEY = "f388cd4cbbadc90870c3c0fb1dfdc730"
HOST = "fermata.it.kr"
ENDPOINT = "https://api.indexnow.org/indexnow"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"}


def submit(urls: list[str]) -> bool:
    """주소를 알린다. 200·202면 True. 예외를 올리지 않는다(곁가지)."""
    urls = [u for u in dict.fromkeys(urls) if u and HOST in u]
    if not urls:
        return True
    ok = True
    for i in range(0, len(urls), 10_000):                 # 한 번에 1만 개까지
        body = {"host": HOST, "key": KEY, "keyLocation": f"https://{HOST}/{KEY}.txt", "urlList": urls[i:i + 10_000]}
        try:
            r = requests.post(ENDPOINT, json=body, headers={"Content-Type": "application/json; charset=utf-8"}, timeout=60)
            if r.status_code in (200, 202):
                print(f"IndexNow: {len(body['urlList'])}개 알림 (HTTP {r.status_code})")
            else:
                ok = False
                print(f"[IndexNow 실패] HTTP {r.status_code} {r.text[:200]}")
        except requests.RequestException as error:
            ok = False
            print(f"[IndexNow 실패] {error!r}")
    return ok


def sitemap_urls() -> list[str]:
    r = requests.get(f"https://{HOST}/wp-sitemap.xml", headers=UA, timeout=60, allow_redirects=False)
    if r.status_code != 200:   # 2026-09-28: Rank Math가 켜져 다른 사이트맵으로 돌려보냈는데 모르고 73개만 보냈다
        raise SystemExit(f"/wp-sitemap.xml이 HTTP {r.status_code}입니다(돌려보내기 {r.headers.get('Location')}) — 사이트맵부터 고치십시오.")
    index = r.text
    out: list[str] = []
    for sub in re.findall(r"<loc>([^<]+)</loc>", index):
        out += re.findall(r"<loc>([^<]+)</loc>", requests.get(sub, headers=UA, timeout=60).text)
    return out


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    urls = sitemap_urls() if args == ["--sitemap"] else args
    print(f"알릴 주소 {len(urls)}개")
    return 0 if submit(urls) else 1


if __name__ == "__main__":
    sys.exit(main())
