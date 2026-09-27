"""본진 모든 화면(메뉴 네 화면·글·분류·검색·소개·404)의 메뉴가 같은 모양인지 실제 화면에서 잰다 (2026-09-27).

    python -m scripts.nav_check          # 1440·390px에서 재고, 다르면 0이 아닌 값으로 끝난다

왜: 홈은 홈 템플릿, Daily·Guides는 일반 페이지 틀, Stocks는 코드 조각이 그려서 메뉴 줄이 272·319·361px로 제각각이었고
Stocks만 배경이 크림색이었다. 1280px 한 폭만 캡처해서 "됐다"고 했다가 사장님이 눌러 보고 찾았다. 메뉴·목록 스타일
(templates/wp_list_toss.php·wp_stock_db.php)을 고친 뒤에는 이것을 돌린다. 요청은 차례로 한 장씩(카페24).
"""
from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright

SITE = "https://fermata.it.kr"
PAGES = ["/", "/stocks/", "/daily/", "/guides/", "/stocks/000660/",
         # 2026-09-28 템플릿 통일 — 글·분류·검색·작성자·소개·404도 같은 자리에 같은 메뉴
         "/editorial-us-2026-09-24-en/", "/sk-hynix-vs-micron/", "/category/korea-close/", "/category/guides/",
         "/?s=samsung", "/author/kimwhey21/", "/about-en/", "/privacy/", "/no-such-page-xyz/"]
WIDTHS = (1440, 390)
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
JS = """() => {
  const a = [...document.querySelectorAll('a')].find(x => x.textContent.trim() === 'Stocks' && x.getAttribute('href') === '/stocks/');
  if (!a) return null;
  const row = a.parentElement.getBoundingClientRect(), pill = a.getBoundingClientRect();
  return {bg: getComputedStyle(document.body).backgroundColor, font: getComputedStyle(document.body).fontFamily.split(',')[0],
          top: Math.round(row.top + scrollY), left: Math.round(row.left), width: Math.round(row.width), pill: Math.round(pill.height),
          overflow: document.documentElement.scrollWidth - innerWidth};
}"""


def main() -> int:
    bad = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for width in WIDTHS:
            seen = {}
            for path in PAGES:
                page = browser.new_page(viewport={"width": width, "height": 900}, user_agent=UA)
                page.goto(SITE + path, wait_until="networkidle", timeout=60000)
                seen[path] = page.evaluate(JS)
                page.close()
                print(width, path.ljust(16), seen[path])
            base = seen["/"]
            for path, got in seen.items():
                if got is None:
                    print(f"[다름] {width}px {path}: 메뉴 줄을 못 찾았습니다")
                    bad += 1
                    continue
                diff = {k: (base[k], got[k]) for k in ("bg", "font", "top", "left", "width", "pill") if got[k] != base[k]}
                if diff or got["overflow"] > 0:
                    print(f"[다름] {width}px {path}: 홈과 다름 {diff} 가로 넘침 {got['overflow']}px")
                    bad += 1
        browser.close()
    print("메뉴 네 화면 같음" if not bad else f"다른 곳 {bad}군데")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
