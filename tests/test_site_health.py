"""본진 매일 점검(scripts/site_health.py)의 날짜 판정 (2026-09-28)."""
import datetime as dt
import unittest
from pathlib import Path

from scripts import site_health as sh

ROOT = Path(__file__).resolve().parent.parent
HOME = '<div class="fs-cell"><span>KOSPI · Sep 28 close</span>'
FLOWS = "<p>Latest trading day: Monday, Sep 28, 2026.</p>"
DATES = ["2026-09-23", "2026-09-28"]
KST = dt.timezone(dt.timedelta(hours=9))


class DateTest(unittest.TestCase):
    def test_parsers(self):
        self.assertEqual(sh.home_kospi_date(HOME, 2026), "2026-09-28")
        self.assertEqual(sh.flows_date(FLOWS), "2026-09-28")

    def test_fresh_site_passes(self):
        self.assertEqual(sh.date_issues(HOME, FLOWS, DATES, dt.datetime(2026, 9, 29, 10, tzinfo=KST)), [])

    def test_stale_market_is_reported(self):
        home = HOME.replace("Sep 28", "Sep 23")
        self.assertTrue(any("KOSPI" in x for x in sh.date_issues(home, FLOWS, DATES, dt.datetime(2026, 9, 28, 19, tzinfo=KST))))

    def test_flows_one_day_behind_is_fine_in_the_evening_not_the_morning(self):
        flows = FLOWS.replace("Monday, Sep 28", "Wednesday, Sep 23")
        self.assertEqual(sh.date_issues(HOME, flows, DATES, dt.datetime(2026, 9, 28, 19, tzinfo=KST)), [])
        self.assertTrue(sh.date_issues(HOME, flows, DATES, dt.datetime(2026, 9, 29, 10, tzinfo=KST)))

    def test_wired_into_publish_check_and_saturday_flows(self):
        wf = (ROOT / ".github" / "workflows" / "publish_check.yml").read_text(encoding="utf-8")
        self.assertIn("python -m scripts.site_health", wf)
        self.assertLess(wf.index("scripts.site_health"), wf.index("실패 알림"))
        self.assertIn('cron: "50 22 * * 0-5"', (ROOT / ".github" / "workflows" / "stock_db.yml").read_text(encoding="utf-8"))


class SnippetSourcesTest(unittest.TestCase):
    def test_every_snippet_source_exists_and_has_no_script_tag(self):
        from scripts.deploy_snippets import DIR, SNIPPETS
        for file, _name, scope in SNIPPETS:
            text = (DIR / file).read_text(encoding="utf-8")
            self.assertTrue(text.startswith("<?php"), file)
            self.assertNotIn("<script", text.lower(), file)     # NinjaFirewall이 저장을 403으로 막는다
            self.assertIn(scope, ("global", "front-end"))


if __name__ == "__main__":
    unittest.main()


class MonthlyAuditTest(unittest.TestCase):
    def test_runs_all_three_in_order_and_reports_failures(self):
        import tempfile
        from unittest import mock
        from scripts import monthly_audit as ma
        calls = []

        def fake_run(args, cwd, stdout, stderr, timeout):
            calls.append(args[-1]); stdout.write("끝줄 " + args[-1] + "\n")
            return mock.Mock(returncode=1 if args[-1] == "scripts.site_ui_audit" else 0)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(ma, "OUT", Path(tmp)), \
                mock.patch.object(ma.subprocess, "run", fake_run), mock.patch.object(ma.alert, "send") as send:
            self.assertEqual(ma.main(), 1)
        self.assertEqual(calls, ["scripts.site_crawl", "scripts.site_ui_audit", "scripts.nav_check"])
        text, level = send.call_args[0]
        self.assertEqual(level, "fail")
        self.assertIn("❌ 모든 화면·버튼", text)
