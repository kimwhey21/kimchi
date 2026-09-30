"""점검용 브라우저에서 구글 태그(애널리틱스·애드센스)를 막는다 (2026-09-30).

화면·버튼 점검(`scripts/site_ui_audit`)과 메뉴 점검(`scripts/nav_check`)이 실제 브라우저로 화면을 열면 GA4 태그와 애드센스
스크립트까지 실행돼 방문자로 잡혔다 — 9/27~28 이틀에 1,600명이 '한국·Direct·참여 1초'로 쌓였고 404 시험 주소
`/no-such-page-xyz/`가 59회 조회됐다. 심사 중인 애드센스에는 무효 트래픽으로 보일 수 있다. 그래서 점검 브라우저는 태그
요청을 아예 보내지 않는다. 화면 검사에는 영향이 없다 — 태그가 실려 있는지는 `scripts/site_health.py`가 HTML로 본다.

    page = browser.new_page(...); block_trackers(page)
    page.on("console", lambda m: ... if not is_tracker_console(m) ...)
"""
from __future__ import annotations

from urllib.parse import urlsplit

TRACKER_HOSTS = (
    "googletagmanager.com", "google-analytics.com", "analytics.google.com",
    "googlesyndication.com", "googleadservices.com", "doubleclick.net",
    "adtrafficquality.google", "fundingchoicesmessages.google.com",
)
TRACKER_PATHS = ("google.com/pagead/", "google.com/ads/")


def is_tracker(url: str) -> bool:
    """방문자 집계·광고로 가는 주소인가."""
    try:
        host = urlsplit(url).hostname or ""
    except ValueError:
        return False
    if any(host == h or host.endswith("." + h) for h in TRACKER_HOSTS):
        return True
    return any(p in url for p in TRACKER_PATHS)


def block_trackers(target) -> None:
    """Playwright Page 또는 BrowserContext의 요청 가운데 태그·광고만 끊는다."""
    def handler(route, request):
        if is_tracker(request.url):
            route.abort()
        else:
            route.continue_()
    target.route("**/*", handler)


def is_tracker_console(message) -> bool:
    """끊은 요청 때문에 브라우저가 적는 콘솔 오류인가 — 점검의 '문제'로 세지 않는다."""
    loc = getattr(message, "location", None) or {}
    url = loc.get("url", "") if isinstance(loc, dict) else ""
    if url and is_tracker(url):
        return True
    text = getattr(message, "text", "") or ""
    return any(h in text for h in TRACKER_HOSTS)
