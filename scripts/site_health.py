"""본진 매일 점검 — 사이트맵·핵심 페이지·데이터 날짜 (2026-09-28).

    python -m scripts.site_health          # 문제가 있으면 줄마다 적고 1로 끝난다(워크플로가 텔레그램으로 알린다)

publish_check.yml이 평일 19:00(17:05 종목 수집 뒤)과 다음 날 10:00(07:50 수급 수집 뒤)에 돌린다. 카페24는 동시 요청에 약해
한 장씩 차례로 연다. 보는 것:
  1. /wp-sitemap.xml이 돌려보내기 없이 200이고 종목 묶음이 있는가 — Rank Math 사이트맵이 켜지면 종목 사이트맵이 404가 된다
  2. 종목 사이트맵에 종목 2,000개 이상·순위표·외국인 수급 주소가 있는가
  3. 홈·목록·종목·순위표·외국인 수급·Daily·ads.txt·IndexNow 열쇠가 열리는가
  4. 홈의 KOSPI 날짜가 우리가 커밋한 마지막 한국장 시세 날짜와 같은가, 외국인 수급 날짜가 밀리지 않았는가
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
    elif got != dates[-1]:
        out.append(f"홈의 KOSPI 날짜 {got} ≠ 마지막 한국장 시세 {dates[-1]} — 17:05 종목 수집이 안 돌았을 수 있습니다")
    fd = flows_date(flows)
    # 종목별 수급은 다음 날 아침 07:50에 들어온다 — 오전 점검은 마지막 거래일, 저녁 점검은 그 전 거래일까지면 된다
    need = dates[-1] if now.hour < 15 else (dates[-2] if len(dates) > 1 else dates[-1])
    if fd is None:
        out.append("외국인 수급 페이지에서 날짜를 못 찾았습니다")
    elif fd < need:
        out.append(f"외국인 수급 날짜 {fd} < 기대 {need} — 07:50 수급 수집이 안 돌았을 수 있습니다")
    return out


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
    return issues


def main() -> int:
    issues = check()
    for line in issues:
        print(f"[본진 점검] {line}")
    print(f"본진 점검: 문제 {len(issues)}건")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
