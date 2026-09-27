"""본진 화면·버튼 점검 — 페이지 종류마다 실제 브라우저로 여러 폭에서 열고, 누를 수 있는 것을 눌러 본다 (2026-09-27).

    python -m scripts.site_ui_audit            # → output/site_ui_audit/ (캡처와 report.json), 문제가 있으면 0이 아닌 값

`scripts/site_crawl.py`가 모든 주소·링크의 상태와 글자를 보고, 이것은 사람이 누르는 것을 본다 — 검색창(입력·화살표·Enter·Esc·
'/' 단축키·없는 이름), 메뉴 네 버튼, KOSPI/KOSDAQ 필터, 쪽 넘김, 종목 페이지 안 이동 버튼과 가이드 버튼, 글 목록 쪽 넘김.
폭마다 보는 것: 가로 넘침, 콘솔 오류, 우리 사이트의 실패한 요청(4xx·5xx), 깨진 그림, 메뉴의 '지금 화면' 표시.
카페24 때문에 한 장씩 연다.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

SITE = "https://fermata.it.kr"
OUT = Path(__file__).resolve().parent.parent / "output" / "site_ui_audit"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
WIDTHS = (390, 768, 1024, 1440, 1920)
# (주소, 메뉴에서 칠해져야 할 버튼 — 없으면 None)
PAGES = [
    ("/", "Market"), ("/stocks/", "Stocks"), ("/stocks/?m=kospi", "Stocks"), ("/stocks/?m=kosdaq&pg=5", "Stocks"),
    ("/stocks/000660/", "Stocks"), ("/stocks/005930/", "Stocks"), ("/stocks/005387/", "Stocks"), ("/stocks/0010S0/", "Stocks"),
    ("/daily/", "Daily"), ("/guides/", "Guides"), ("/all/", None), ("/category/daily/", None), ("/category/korea-close/", None),
    ("/category/wall-street-close/", None), ("/category/guides/", None),
    ("/about-en/", None), ("/contact-en/", None), ("/no-such-page-xyz/", None), ("/stocks/999999/", None), ("/?s=samsung", None),
]
PROBE = """() => {
  const imgs = [...document.images].filter(i => i.complete && i.naturalWidth === 0 && i.src && !i.src.startsWith('data:')).map(i => i.src);
  const nav = [...document.querySelectorAll('main div[style*="flex-wrap:wrap"] > a')];
  const on = nav.filter(a => getComputedStyle(a).backgroundColor === 'rgb(25, 31, 40)').map(a => a.textContent.trim());
  const wide = [...document.querySelectorAll('main *')].filter(e => { const r = e.getBoundingClientRect();
      return r.width > 0 && (r.right > innerWidth + 1 || r.left < -1) && !e.closest('.fs-scroll'); }).slice(0, 3)
      .map(e => e.tagName.toLowerCase() + '.' + String(e.className).split(' ')[0]);
  const emptyLinks = [...document.querySelectorAll('a')].filter(a => !a.getAttribute('href') && !a.closest('.wp-block-query-pagination')).length;
  return {overflow: document.documentElement.scrollWidth - innerWidth, broken_img: imgs, nav_on: on, nav_count: nav.length,
          sticking_out: wide, empty_links: emptyLinks, title: document.title};
}"""


def open_page(browser, path, width, problems, errors):
    page = browser.new_page(viewport={"width": width, "height": 900}, user_agent=UA)
    page.on("console", lambda m: m.type == "error" and errors.append(f"콘솔 오류: {m.text[:120]}"))
    page.on("pageerror", lambda e: errors.append(f"스크립트 오류: {str(e)[:120]}"))

    def on_response(r):
        if "fermata.it.kr" in r.url and r.status >= 400 and r.request.resource_type != "document":
            errors.append(f"요청 실패 {r.status} {r.url[:100]}")
    page.on("response", on_response)
    resp = page.goto(SITE + path, wait_until="networkidle", timeout=90000)
    return page, (resp.status if resp else None)


def check_static(browser, problems):
    for path, active in PAGES:
        for w in WIDTHS:
            errors: list[str] = []
            page, status = open_page(browser, path, w, problems, errors)
            got = page.evaluate(PROBE)
            tag = f"{w}px {path}"
            expect_404 = path in ("/no-such-page-xyz/", "/stocks/999999/")
            if (status == 404) != expect_404 or (status not in (200, 404)):
                problems.append(f"{tag}: 상태 {status}")
            if got["overflow"] > 0:
                problems.append(f"{tag}: 가로 넘침 {got['overflow']}px {got['sticking_out']}")
            if got["broken_img"]:
                problems.append(f"{tag}: 깨진 그림 {got['broken_img'][:2]}")
            if got["empty_links"]:
                problems.append(f"{tag}: 주소 없는 링크 {got['empty_links']}개")
            if active and got["nav_on"] != [active]:
                problems.append(f"{tag}: 메뉴 표시 {got['nav_on']} (기대 {active})")
            if path in ("/", "/stocks/", "/daily/", "/guides/") and got["nav_count"] != 4:
                problems.append(f"{tag}: 메뉴 버튼 {got['nav_count']}개")
            problems.extend(f"{tag}: {e}" for e in dict.fromkeys(errors))
            if w in (390, 1440):
                name = re.sub(r"[^a-z0-9]+", "_", path.lower()).strip("_") or "home"
                page.screenshot(path=str(OUT / f"{name}_{w}.png"), full_page=True)
            page.close()
            print(f"  {tag} 상태 {status} 넘침 {got['overflow']} 메뉴 {got['nav_on']}", flush=True)


def check_clicks(browser, problems):
    for w in (1440, 390):
        errors: list[str] = []
        p, _ = open_page(browser, "/", w, problems, errors)
        # 검색창: '/' 단축키 → 입력 → 결과 → 화살표 → Enter
        p.keyboard.press("/")
        if p.evaluate("document.activeElement && document.activeElement.id") != "fs-q":
            problems.append(f"{w}px 홈: '/' 단축키가 검색창으로 안 간다")
        p.fill("#fs-q", "")
        p.keyboard.type("samsung", delay=40)
        p.wait_for_timeout(1200)
        items = p.locator("#fs-res a").count()
        if items < 3:
            problems.append(f"{w}px 홈: 'samsung' 검색 결과 {items}개")
        p.keyboard.press("ArrowDown")
        p.keyboard.press("ArrowDown")
        target = p.locator("#fs-res a.on").get_attribute("href") if p.locator("#fs-res a.on").count() else None
        p.keyboard.press("Enter")
        p.wait_for_load_state("networkidle")
        if not target or not p.url.endswith(target):
            problems.append(f"{w}px 홈: 화살표 두 번 + Enter가 두 번째 결과로 안 간다 ({target} → {p.url})")
        p.goto(SITE + "/", wait_until="networkidle")
        p.fill("#fs-q", "005930")
        p.wait_for_timeout(800)
        if "Samsung Electronics" not in (p.inner_text("#fs-res") or ""):
            problems.append(f"{w}px 홈: 종목 코드 005930 검색이 안 된다")
        p.fill("#fs-q", "zzzzqq")
        p.wait_for_timeout(500)
        if "No match" not in p.inner_text("#fs-res"):
            problems.append(f"{w}px 홈: 없는 이름에 'No match'가 안 나온다")
        p.keyboard.press("Escape")
        if p.locator("#fs-res").is_visible():
            problems.append(f"{w}px 홈: Esc로 결과가 안 닫힌다")
        # 메뉴 네 버튼
        for label, path in (("Stocks", "/stocks/"), ("Daily", "/daily/"), ("Guides", "/guides/"), ("Market", "/")):
            p.locator('main div[style*="flex-wrap:wrap"] > a', has_text=label).first.click()
            p.wait_for_load_state("networkidle")
            if p.url.rstrip("/") != (SITE + path).rstrip("/"):
                problems.append(f"{w}px 메뉴 {label}: {p.url}")
        # 홈 카드의 링크(시가총액·상승·외국인)와 'All →'
        for sel in (".fs-card a.fs-more", ".fs-card table a", ".fs-mv a"):
            href = p.locator(sel).first.get_attribute("href")
            r = p.request.get(SITE + href)
            if r.status != 200:
                problems.append(f"{w}px 홈 카드 링크 {href}: {r.status}")
        # 목록: 필터·쪽 넘김
        p.goto(SITE + "/stocks/", wait_until="networkidle")
        p.locator(".fs-pills a", has_text="KOSDAQ").click()
        p.wait_for_load_state("networkidle")
        markets = set(p.locator(".fs-list tr td:nth-child(3)").all_inner_texts())
        if markets != {"KOSDAQ"}:
            problems.append(f"{w}px 목록 KOSDAQ 필터: {markets}")
        p.locator(".fs-pager a", has_text="Next").click()
        p.wait_for_load_state("networkidle")
        if "pg=2" not in p.url or "m=kosdaq" not in p.url:
            problems.append(f"{w}px 목록 Next: 필터가 풀리거나 안 넘어간다 {p.url}")
        first = p.locator(".fs-list tr td:first-child").nth(0).inner_text()
        if first.strip() != "101":
            problems.append(f"{w}px 목록 2쪽 첫 순위 {first}")
        p.locator(".fs-pager a", has_text="Previous").click()
        p.wait_for_load_state("networkidle")
        if "pg=1" not in p.url:
            problems.append(f"{w}px 목록 Previous: {p.url}")
        last = p.locator(".fs-pager span").inner_text()
        pages = int(re.search(r"of (\d+)", last).group(1))
        p.goto(f"{SITE}/stocks/?m=kosdaq&pg={pages}", wait_until="networkidle")
        if p.locator(".fs-pager a", has_text="Next").count():
            problems.append(f"{w}px 목록 마지막 쪽에 Next가 있다")
        p.goto(f"{SITE}/stocks/?pg=9999", wait_until="networkidle")
        if p.locator(".fs-list tr").count() < 2:
            problems.append(f"{w}px 목록 ?pg=9999가 빈 쪽")
        # 종목 페이지: 이동 버튼·가이드 버튼·동종·경로
        p.goto(SITE + "/stocks/000660/", wait_until="networkidle")
        for tab in p.locator(".fs-tabs a").all():
            href = tab.get_attribute("href")
            tab.click()
            p.wait_for_timeout(300)
            if not p.locator(href).count():
                problems.append(f"{w}px 종목 이동 버튼 {href}: 목적지 없음")
        for sel in (".fs-head .fs-btn", ".fs-cta .fs-btn", "#peers a", ".fs-crumb a", "#about a", ".fs-rel a"):
            for link in p.locator(sel).all()[:6]:
                href = link.get_attribute("href")
                url = href if href.startswith("http") else SITE + href
                if "fermata.it.kr" in url:
                    r = p.request.get(url)
                    if r.status != 200:
                        problems.append(f"{w}px 종목 {sel} {href}: {r.status}")
        # 글 목록 쪽 넘김
        p.goto(SITE + "/daily/", wait_until="networkidle")
        nxt = p.locator(".wp-block-query-pagination-next")
        if nxt.count():
            nxt.first.click()
            p.wait_for_load_state("networkidle")
            if p.locator(".wp-block-post-template > li").count() == 0:
                problems.append(f"{w}px Daily 2쪽이 비었다 {p.url}")
        problems.extend(f"{w}px 누르는 중: {e}" for e in dict.fromkeys(errors))
        p.close()
        print(f"  {w}px 누르기 점검 끝", flush=True)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    problems: list[str] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        check_static(browser, problems)
        check_clicks(browser, problems)
        browser.close()
    (OUT / "report.json").write_text(json.dumps(problems, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n문제 {len(problems)}건" + ("" if not problems else ":"))
    for line in problems:
        print("  -", line)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
