"""점검 브라우저의 구글 태그 차단(src/quiet_browser.py, 2026-09-30) — 점검이 GA4 방문자·애드센스 조회로 잡히지 않는다."""
import unittest
from pathlib import Path

from src import quiet_browser as qb

ROOT = Path(__file__).resolve().parent.parent


class Msg:
    def __init__(self, text, url=""):
        self.text, self.location = text, {"url": url}


class TrackerBlocking(unittest.TestCase):
    def test_tracker_urls(self):
        for u in ["https://www.googletagmanager.com/gtag/js?id=GT-KVMKTFFJ", "https://region1.google-analytics.com/g/collect?v=2",
                  "https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1", "https://stats.g.doubleclick.net/j/collect",
                  "https://www.google.com/pagead/1p-user-list/123", "https://ep1.adtrafficquality.google/sodar"]:
            self.assertTrue(qb.is_tracker(u), u)

    def test_our_site_and_fonts_pass(self):
        for u in ["https://fermata.it.kr/stocks/", "https://fermata.it.kr/wp-content/uploads/a.png", "https://fonts.gstatic.com/x.woff2",
                  "https://cdn.jsdelivr.net/npm/chart.js", "https://www.google.com/recaptcha/api.js"]:
            self.assertFalse(qb.is_tracker(u), u)

    def test_route_aborts_only_trackers(self):
        calls = []

        class Route:
            def abort(self): calls.append("abort")
            def continue_(self): calls.append("continue")

        class Req:
            def __init__(self, url): self.url = url

        class Target:
            def route(self, pattern, handler):
                self.handler = handler

        t = Target(); qb.block_trackers(t)
        t.handler(Route(), Req("https://www.googletagmanager.com/gtag/js?id=GT-1"))
        t.handler(Route(), Req("https://fermata.it.kr/"))
        self.assertEqual(calls, ["abort", "continue"])

    def test_console_noise_from_blocked_tags_is_ignored(self):
        self.assertTrue(qb.is_tracker_console(Msg("Failed to load resource: net::ERR_FAILED", "https://www.googletagmanager.com/gtag/js")))
        self.assertTrue(qb.is_tracker_console(Msg("https://pagead2.googlesyndication.com/x net::ERR_FAILED")))
        self.assertFalse(qb.is_tracker_console(Msg("Failed to load resource: 500", "https://fermata.it.kr/wp-content/x.js")))

    def test_both_browser_audits_block_trackers(self):
        for name in ("scripts/nav_check.py", "scripts/site_ui_audit.py"):
            src = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn("block_trackers(page)", src, name)
        self.assertIn("is_tracker_console", (ROOT / "scripts/site_ui_audit.py").read_text(encoding="utf-8"))
