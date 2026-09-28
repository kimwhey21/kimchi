"""본진(fermata.it.kr) 전수 점검 — 사이트 안의 모든 주소를 한 장씩 열어 링크·그림·글자·검색 정보를 본다 (2026-09-27).

    python -m scripts.site_crawl                     # 전부(종목 2,765쪽 포함, 1시간 안팎) → output/site_crawl/
    python -m scripts.site_crawl --limit 200         # 앞 200쪽만(빠른 점검)
    python -m scripts.site_crawl --external          # 바깥 링크(회사 홈페이지 등)도 연다

왜: 모든 버튼·링크를 눌러 봐야 한다 — 누를 수 있는 것이 종목 페이지로 수천 개가 됐다.
카페24 공유 호스팅은 동시 요청에 약하다 — **우리 사이트는 한 장씩 차례로** 연다(바깥 사이트만 동시에).

한 장마다 보는 것: 상태(404·5xx·돌려보내기), 영어 사이트에 섞인 한글, 깨진 글자(`&#8217;`·`&amp;amp;`), PHP 오류 문구,
빈 그림 주소, 제목·설명·대표 주소(canonical), 같은 쪽 안 이동(#id) 목적지, 메뉴 줄 개수. 링크와 그림은 주소마다 한 번씩 상태를 본다.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import html
import json
import re
import sys
import time
from collections import defaultdict, deque
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests

SITE = "https://fermata.it.kr"
HOST = "fermata.it.kr"
OUT = Path(__file__).resolve().parent.parent / "output" / "site_crawl"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"}
PAUSE = 0.25
SKIP = re.compile(r"/wp-admin|/wp-login|/xmlrpc|/wp-json/|/feed/?$|/comments/feed|\?replytocom=|/wp-content/|/wp-includes/")
HANGUL_OK = {"/about/", "/contact/", "/privacy-policy/"}   # 남겨 둔 한국어 소개·연락처·개인정보(697·698·226, 검색 제외·lang="ko")
PHP_ERR = re.compile(r"(Fatal error|Parse error|Warning</b>:|Notice</b>:|Deprecated</b>:|Uncaught |on line <b>\d+)")


def norm(url: str) -> str:
    s = urlsplit(url)
    path = s.path or "/"
    return urlunsplit((s.scheme or "https", s.netloc.lower(), path, s.query, ""))


def internal(url: str) -> bool:
    return urlsplit(url).netloc.lower() in (HOST, "www." + HOST)


def visible_text(page: str) -> str:
    page = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", page)
    page = re.sub(r"(?s)<!--.*?-->", " ", page)
    body = re.search(r"(?is)<body[^>]*>(.*)</body>", page)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body.group(1) if body else page))


def page_checks(url: str, text: str) -> list[str]:
    issues = []
    path = urlsplit(url).path
    vis = visible_text(text)
    raw_vis = html.unescape(vis)
    if path not in HANGUL_OK:
        found = re.findall(r"[가-힣][가-힣\s]{0,20}", raw_vis)
        if found:
            issues.append(f"한글 {len(found)}곳: {found[0][:20]}")
    # 원문의 &#8217;는 화면에서 ’로 보인다 — 한 번 풀고도 &#…;·&amp; 꼴이 남으면(두 번 이스케이프) 화면에 글자 그대로 보인다
    leftover = re.findall(r"&(?:#\d+|#x[0-9a-f]+|[a-z]{2,8});", raw_vis, re.I)
    if leftover:
        issues.append(f"깨진 글자 {leftover[0]} ({len(leftover)}곳)")
    for bad in ("undefined", "NaN", "Array", "{{", "}}"):
        if re.search(rf"(?<![\w-]){re.escape(bad)}(?![\w-])", raw_vis):
            issues.append(f"이상한 값 '{bad}'")
    if PHP_ERR.search(text):
        issues.append("PHP 오류 문구")
    if re.search(r'<img[^>]+src=""', text):
        issues.append("빈 그림 주소")
    title = re.search(r"(?is)<title>(.*?)</title>", text)
    if not title or not title.group(1).strip():
        issues.append("제목 없음")
    desc = re.search(r'<meta name="description" content="([^"]*)"', text)
    robots = re.search(r'<meta name="robots" content="([^"]*)"', text)
    noindex = bool(robots and "noindex" in robots.group(1))
    if not noindex and not (desc and desc.group(1).strip()):
        issues.append("설명(description) 없음")
    canon = re.search(r'<link rel="canonical" href="([^"]+)"', text)
    if not noindex:
        if not canon:
            issues.append("대표 주소(canonical) 없음")
        elif "?" not in url and norm(canon.group(1)).rstrip("/") != norm(url).rstrip("/"):
            issues.append(f"대표 주소가 다름: {canon.group(1)}")
    ids = set(re.findall(r'\sid="([^"]+)"', text))
    for frag in set(re.findall(r'href="#([^"]+)"', text)):
        if frag not in ids:
            issues.append(f"쪽 안 이동 목적지 없음 #{frag}")
    navs = text.count('class="fs-navwrap"')
    if navs > 1:
        issues.append(f"메뉴 줄이 {navs}개")
    return issues


def links(url: str, text: str) -> tuple[set[str], set[str]]:
    pages, assets = set(), set()
    for href in re.findall(r'<a\s[^>]*href="([^"]+)"', text):
        href = html.unescape(href)
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        pages.add(norm(urljoin(url, href)))
    for src in re.findall(r'<(?:img|script|source)\s[^>]*src="([^"]+)"', text) + \
            re.findall(r'<link\s[^>]*rel="stylesheet"[^>]*href="([^"]+)"', text):
        assets.add(norm(urljoin(url, html.unescape(src))))
    return pages, assets


def sitemap_urls(session: requests.Session) -> list[str]:
    out = []
    r = session.get(f"{SITE}/wp-sitemap.xml", timeout=30, allow_redirects=False)
    if r.status_code != 200 or "wp-sitemap-stocks-" not in r.text:   # Rank Math 사이트맵이 켜지면 돌려보낸다(2026-09-28)
        raise SystemExit(f"/wp-sitemap.xml 이상: HTTP {r.status_code} {r.headers.get('Location', '')} — 종목 사이트맵이 없습니다.")
    index = r.text
    for sub in re.findall(r"<loc>([^<]+)</loc>", index):
        time.sleep(PAUSE)
        out += re.findall(r"<loc>([^<]+)</loc>", session.get(sub, timeout=60).text)
    return [norm(u) for u in out]


def check_status(session: requests.Session, url: str) -> int | str:
    try:
        r = session.head(url, timeout=15, allow_redirects=True)
        if r.status_code in (403, 405, 400, 404, 501) or r.status_code >= 500:
            r = session.get(url, timeout=20, allow_redirects=True, stream=True)
            r.close()
        return r.status_code
    except Exception as error:  # noqa: BLE001 — 깨진 돌려보내기 주소(UnicodeDecodeError)로 점검 전체가 죽었다(2026-09-27). 세어서 보고한다
        return type(error).__name__


def external_status(url: str) -> int | str:
    """바깥 링크는 curl로 — 파이썬 SSL은 브라우저가 여는 옛 사이트를 못 연다(gabia.com). 봇 차단(401·403·429·999)은 사람에겐 열린다."""
    from src.stock_db import _curl_status
    code = _curl_status(url)
    return 200 if (200 <= code < 400 or code in (401, 403, 405, 429, 999)) else (code or "안 열림")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--external", action="store_true")
    a = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers.update(UA)
    seeds = [norm(SITE + "/")] + sitemap_urls(s)
    print(f"사이트맵 {len(seeds) - 1}개 + 홈에서 시작", flush=True)
    queue, seen = deque(seeds), set(seeds)
    status: dict[str, int | str] = {}
    issues: dict[str, list[str]] = {}
    linked_from: dict[str, set[str]] = defaultdict(set)
    assets: dict[str, set[str]] = defaultdict(set)
    external: dict[str, set[str]] = defaultdict(set)
    n = 0
    while queue and (not a.limit or n < a.limit):
        url = queue.popleft()
        n += 1
        time.sleep(PAUSE)
        try:
            r = s.get(url, timeout=60, allow_redirects=False)
        except requests.RequestException as error:
            status[url] = type(error).__name__
            continue
        status[url] = r.status_code
        if r.status_code in (301, 302, 307, 308):
            target = norm(urljoin(url, r.headers.get("Location", "")))
            status[url] = f"{r.status_code}→{target}"
            if internal(target) and target not in seen and not SKIP.search(target):
                seen.add(target)
                queue.append(target)
            continue
        if r.status_code != 200 or "text/html" not in r.headers.get("Content-Type", ""):
            continue
        found = page_checks(url, r.text)
        if found:
            issues[url] = found
        pages, srcs = links(url, r.text)
        for p in pages:
            if internal(p):
                linked_from[p].add(url)
                if p not in seen and not SKIP.search(p):
                    seen.add(p)
                    queue.append(p)
            else:
                external[p].add(url)
        for src in srcs:
            assets[src].add(url)
        if n % 200 == 0:
            print(f"  {n}쪽 (대기 {len(queue)}) 문제 {len(issues)}쪽", flush=True)
    print(f"안쪽 {n}쪽 다 봄 — 이제 그림·스크립트 {len(assets)}개", flush=True)
    asset_status = {}
    for src in sorted(assets):
        if internal(src):
            time.sleep(PAUSE)
        asset_status[src] = check_status(s, src)
        if asset_status[src] != 200:          # 카페24가 가끔 502를 낸다(2026-09-28 그림 21개, 다시 열면 정상) — 5초 뒤 한 번 더
            time.sleep(5)
            asset_status[src] = check_status(s, src)
    ext_status = {}
    if a.external:
        print(f"바깥 링크 {len(external)}개(동시 16)", flush=True)
        with cf.ThreadPoolExecutor(16) as pool:
            for url, st in zip(external, pool.map(external_status, external)):
                ext_status[url] = st
    bad_links = {u: st for u, st in status.items() if not (st == 200 or str(st).startswith(("301", "302", "308")))}
    bad_assets = {u: st for u, st in asset_status.items() if st != 200}
    bad_ext = {u: st for u, st in ext_status.items() if st != 200}
    report = {
        "pages_checked": n, "unvisited": len(queue),
        "bad_pages": {u: {"status": st, "linked_from": sorted(linked_from.get(u, []))[:5]} for u, st in bad_links.items()},
        "page_issues": issues,
        "bad_assets": {u: {"status": st, "on": sorted(assets[u])[:3]} for u, st in bad_assets.items()},
        "redirects": {u: st for u, st in status.items() if str(st).startswith(("301", "302", "308"))},
        "external_checked": len(ext_status),
        "bad_external": {u: {"status": st, "on": sorted(external[u])[:3]} for u, st in bad_ext.items()},
    }
    (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    kinds = defaultdict(int)
    for found in issues.values():
        for f in found:
            kinds[re.sub(r"[:#].*", "", f)] += 1
    print(f"\n안쪽 {n}쪽 · 안 열리는 주소 {len(bad_links)} · 문제 있는 쪽 {len(issues)} · 깨진 그림/스크립트 {len(bad_assets)}"
          f" · 돌려보내기 {len(report['redirects'])} · 바깥 {len(ext_status)}개 중 안 열림 {len(bad_ext)}")
    for k, v in sorted(kinds.items(), key=lambda kv: -kv[1]):
        print(f"  {k}: {v}쪽")
    print(f"자세한 것: {OUT / 'report.json'}")
    return 1 if (bad_links or issues or bad_assets) else 0


if __name__ == "__main__":
    sys.exit(main())
