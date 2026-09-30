"""본진 매일 점검 — 사이트맵·핵심 페이지·데이터 날짜 (2026-09-28).

    python -m scripts.site_health          # 문제가 있으면 줄마다 적고 1로 끝난다(워크플로가 텔레그램으로 알린다)

publish_check.yml이 평일 19:00(17:05 종목 수집 뒤)과 다음 날 10:00(07:50 수급 수집 뒤)에 돌린다. 카페24는 동시 요청에 약해
한 장씩 차례로 연다. 보는 것:
  1. /wp-sitemap.xml이 돌려보내기 없이 200이고 종목 묶음이 있는가 — Rank Math 사이트맵이 켜지면 종목 사이트맵이 404가 된다
  2. 종목 사이트맵에 종목 2,000개 이상·순위표·외국인 수급 주소가 있는가
  3. 홈·목록·종목·순위표·외국인 수급·Daily·ads.txt·IndexNow 열쇠가 열리는가
  4. 홈의 KOSPI 날짜가 우리가 커밋한 마지막 한국장 시세 날짜와 같은가, 외국인 수급 날짜가 밀리지 않았는가
  5. 관리자 화면 접근 규칙(2026-09-30): Cloudflare 사용자 지정 규칙 「관리자 화면 한국만」이 /wp-admin·/wp-login.php를
     한국 밖에서 막는다(카페24의 옛 /wp-admin 한국만 규칙은 Cloudflare 경유를 해외로 봐서 사장님까지 막았다 — 그 규칙은 지웠다).
     실행 장소를 /cdn-cgi/trace의 loc으로 읽어, 해외(깃허브 러너)면 로그인 화면이 Cloudflare에 막혀야 하고,
     한국(이 맥)이면 로그인 화면 200·/wp-admin/ 302여야 한다. 403인데 Cloudflare 차단 페이지가 아니면 카페24 규칙이 되살아난 것.
  6. 홈 HTML에 GA4 태그(Site Kit)와 애드센스 스크립트(Code Snippets 9번)가 실려 있는가 — 점검 브라우저는 태그 요청을
     끊으므로(`src/quiet_browser`) 태그가 빠진 것은 여기서만 보인다(2026-09-30).
"""
from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

import requests

from src.indexnow import KEY

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://fermata.it.kr"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"}
LISTS = ("highest-dividend-yield", "most-foreign-owned", "cheapest-by-pb", "largest-kosdaq")
PAGES = ["/", "/stocks/", "/stocks/005930/", "/stocks/foreign-flows/", "/stocks/skhy-premium/", *[f"/stocks/lists/{s}/" for s in LISTS], "/category/daily/"]
KST = dt.timezone(dt.timedelta(hours=9))


def kr_dates(root: Path = ROOT) -> list[str]:
    """커밋된 한국장 시세 파일의 거래일(오래된 순)."""
    return sorted(p.stem[-10:] for p in (root / "data").glob("price_kr_*.json") if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.stem[-10:]))


def home_kospi_date(html: str, year: int) -> str | None:
    m = re.search(r"KOSPI · ([A-Z][a-z]{2}) (\d{1,2}) close", html)
    if not m:
        return None
    return dt.datetime.strptime(f"{m.group(1)} {m.group(2)} {year}", "%b %d %Y").date().isoformat()


def flows_date(html: str) -> str | None:
    m = re.search(r"Latest trading day: [A-Za-z]+, ([A-Z][a-z]{2}) (\d{1,2}), (\d{4})", html)
    return dt.datetime.strptime(" ".join(m.groups()), "%b %d %Y").date().isoformat() if m else None


def date_issues(home: str, flows: str, dates: list[str], now: dt.datetime) -> list[str]:
    if not dates:
        return ["커밋된 한국장 시세 파일이 없습니다"]
    out = []
    got = home_kospi_date(home, int(dates[-1][:4]))
    if got is None:
        out.append("홈에서 KOSPI 날짜를 못 찾았습니다(시장 띠가 비었을 수 있음)")
    elif got < dates[-1]:
        out.append(f"홈의 KOSPI 날짜 {got} < 마지막 한국장 시세 {dates[-1]} — 17:05 종목 수집(stock_db.yml)이 안 돌았을 수 있습니다")
    elif got > dates[-1]:
        out.append(f"홈의 KOSPI 날짜 {got} > 마지막 한국장 시세 {dates[-1]} — 16:20 한국장 시세 수집(market_brief.yml)이 멈춰 "
                   f"한국장 시황이 안 나갔을 수 있습니다(15:32 종가 사진 krx_close.yml부터 확인)")
    fd = flows_date(flows)
    # 종목별 수급은 다음 날 아침 07:50에 들어온다 — 오전 점검은 마지막 거래일, 저녁 점검은 그 전 거래일까지면 된다
    need = dates[-1] if now.hour < 15 else (dates[-2] if len(dates) > 1 else dates[-1])
    if fd is None:
        out.append("외국인 수급 페이지에서 날짜를 못 찾았습니다")
    elif fd < need:
        out.append(f"외국인 수급 날짜 {fd} < 기대 {need} — 07:50 수급 수집이 안 돌았을 수 있습니다")
    return out


def tag_issues(home_html: str) -> list[str]:
    """홈에 방문자 집계·광고 태그가 실려 있는가(JS를 실행하지 않고 HTML만 본다)."""
    issues = []
    if not re.search(r"googletagmanager\.com/gtag/js\?id=G[T]?-[A-Z0-9]+", home_html):
        issues.append("홈에 GA4 태그(gtag/js?id=GT-…)가 없습니다 — Site Kit 애널리틱스 스니펫을 보십시오")
    if not re.search(r"adsbygoogle\.js\?client=ca-pub-\d+", home_html):
        issues.append("홈에 애드센스 스크립트(adsbygoogle.js?client=ca-pub-…)가 없습니다 — Code Snippets 9번을 보십시오")
    return issues


def admin_issues(loc: str, login_status: int, login_body: str, admin_status: int) -> list[str]:
    """관리자 화면 접근 규칙 판정. loc은 Cloudflare가 본 실행 장소의 나라 코드."""
    cf_block = "have been blocked" in login_body or "error code: 1020" in login_body
    if loc != "KR":
        if login_status == 403 and cf_block:
            return []
        if login_status == 403:
            return [f"해외에서 /wp-login.php가 Cloudflare가 아니라 서버(카페24)에 막혔습니다 — 카페24 /wp-admin 한국만 규칙이 되살아났는지 보십시오"]
        return [f"해외에서 /wp-login.php가 HTTP {login_status}로 열립니다 — Cloudflare 「관리자 화면 한국만」 규칙이 꺼졌습니다"]
    issues = []
    if login_status != 200:
        issues.append(f"한국에서 /wp-login.php HTTP {login_status}" + (" — Cloudflare 차단 페이지입니다(규칙의 나라 조건을 보십시오)" if cf_block else ""))
    if admin_status == 403:
        issues.append("한국에서 /wp-admin/ HTTP 403 — 카페24 /wp-admin 한국만 규칙이 되살아났습니다(Cloudflare 경유는 해외로 보입니다)")
    elif admin_status not in (200, 302):
        issues.append(f"한국에서 /wp-admin/ HTTP {admin_status}")
    return issues


def check(session: requests.Session | None = None, now: dt.datetime | None = None) -> list[str]:
    s = session or requests.Session()
    now = now or dt.datetime.now(KST)
    get = lambda path, **kw: s.get(BASE + path, headers=UA, timeout=60, **kw)   # noqa: E731
    issues: list[str] = []
    r = get("/wp-sitemap.xml", allow_redirects=False)
    parts = re.findall(r"<loc>(https://fermata\.it\.kr/wp-sitemap-stocks-\d+\.xml)</loc>", r.text) if r.status_code == 200 else []
    if not parts:
        issues.append(f"/wp-sitemap.xml HTTP {r.status_code} {r.headers.get('Location') or ''} — 종목 사이트맵이 빠졌습니다(Rank Math 사이트맵이 켜졌는지 보십시오)")
    else:
        maps = [s.get(u, headers=UA, timeout=60).text for u in parts]
        sm, n = maps[0], sum(m.count("<loc>") for m in maps)
        if n < 2000:
            issues.append(f"종목 사이트맵 주소가 {n}개뿐입니다")
        for path in ["/stocks/foreign-flows/", "/stocks/skhy-premium/", *[f"/stocks/lists/{x}/" for x in LISTS]]:
            if f"{BASE}{path}</loc>" not in sm:
                issues.append(f"종목 사이트맵에 {path}가 없습니다")
    bodies = {}
    for path in PAGES:
        r = get(path)
        bodies[path] = r.text
        if r.status_code != 200:
            issues.append(f"{path} HTTP {r.status_code}")
    r = get("/ads.txt")
    if r.status_code != 200 or not r.text.startswith("google.com, pub-"):
        issues.append(f"/ads.txt HTTP {r.status_code}")
    r = get(f"/{KEY}.txt")
    if r.status_code != 200 or r.text.strip() != KEY:
        issues.append(f"IndexNow 열쇠 파일 HTTP {r.status_code}")
    issues += date_issues(bodies.get("/", ""), bodies.get("/stocks/foreign-flows/", ""), kr_dates(), now)
    issues += tag_issues(bodies.get("/", ""))
    trace = get("/cdn-cgi/trace").text
    loc = (re.search(r"^loc=(\w+)", trace, re.M) or [None, "??"])[1]
    login = get("/wp-login.php", allow_redirects=False)
    admin = get("/wp-admin/", allow_redirects=False)
    issues += admin_issues(loc, login.status_code, login.text, admin.status_code)
    return issues


def main() -> int:
    issues = check()
    for line in issues:
        print(f"[본진 점검] {line}")
    print(f"본진 점검: 문제 {len(issues)}건")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
