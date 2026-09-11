"""주말 편성(2026-09-12, 사용자 결정) — 토요일 주간 결산·일요일 다음 주 일정을 고정한다.

숫자는 시세 파일의 3개월 이력에서만 나오고(`scripts.weekly_stats`), 두 시리즈는 기준표
파이프라인에 표 한 줄씩으로 등록되며(`feature_checks`·`editorial_title`·`source_check`·
`feature_gate`), `weekly_publish.yml`이 바로 공개한다. 네이버 요약본은 기간을 머리에 붙인다.
"""
from __future__ import annotations

import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from scripts import naver_post, recent_titles, weekly_stats
from src import data_graphics, editorial_title, feature_checks, feature_gate, publish_feature, source_check

ROOT = Path(__file__).resolve().parent.parent


def _entry(ticker: str, name: str, closes: list[float], dates: list[str], **extra) -> dict:
    return {"ticker": ticker, "name": name, "price": closes[-1],
            "change_pct": round((closes[-1] / closes[-2] - 1) * 100, 2),
            "history": {"dates": dates, "close": closes}, "source": "core", **extra}


# 두 주: 8월 31일(월)~9월 4일(금), 9월 7일(월)~9월 11일(금)
DATES = ["2026-08-31", "2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04",
         "2026-09-07", "2026-09-08", "2026-09-09", "2026-09-10", "2026-09-11"]
PRICE = {
    "trading_date": "2026-09-11",
    "macro": {"KS11": _entry("KS11", "코스피", [6500, 6520, 6550, 6600, 6687.21, 6995, 6954, 7051, 7033, 6909.91], DATES, unit="")},
    "watchlist": {
        "005930": _entry("005930", "삼성전자", [250000, 251000, 252000, 254000, 255500, 270000, 269500, 269500, 269000, 259500], DATES, sector="반도체"),
        "034020": _entry("034020", "두산에너빌리티", [78000, 78500, 79000, 79000, 79200, 85000, 88000, 89000, 90000, 90800], DATES, sector="발전·원전"),
        "035720": _entry("035720", "카카오", [36000, 36100, 36200, 36100, 36200, 35500, 35200, 35000, 34800, 34500], DATES, sector="플랫폼"),
        "999999": {"ticker": "999999", "name": "신규편입", "price": 100.0, "change_pct": 1.0,
                   "history": {"dates": DATES[-2:], "close": [99.0, 100.0]}, "source": "dynamic"},
    },
}


class WeeklyStatsTest(unittest.TestCase):
    def test_week_is_measured_against_the_previous_weeks_last_close(self) -> None:
        result = weekly_stats.compute(PRICE, "kr")
        self.assertEqual(result["week"], {"start": "2026-09-07", "end": "2026-09-11"})
        self.assertEqual(len(result["trading_days"]), 5)
        self.assertFalse(result["thin"])
        kospi = result["macro"][0]
        self.assertEqual(kospi["prev_close"], 6687.21)
        self.assertAlmostEqual(kospi["week_pct"], (6909.91 / 6687.21 - 1) * 100, places=2)
        self.assertEqual([p["date"] for p in kospi["path"]], DATES[5:])
        self.assertEqual(kospi["path"][0]["pct"], round((6995 / 6687.21 - 1) * 100, 2))

    def test_top_lists_and_sectors_come_from_weekly_change_not_daily(self) -> None:
        result = weekly_stats.compute(PRICE, "kr")
        self.assertEqual(result["top_up"][0]["name"], "두산에너빌리티")
        self.assertEqual(result["top_down"][0]["name"], "카카오")
        self.assertNotIn("신규편입", [s["name"] for s in result["stocks"]],
                         "이력이 한 주보다 짧은 종목은 주간 등락을 셀 수 없으므로 뺀다")
        names = {s["name"]: s for s in result["sectors"]}
        self.assertIn("반도체", names)
        self.assertEqual(names["반도체"]["up"], 1)
        self.assertEqual(result["breadth"], {"up": 2, "down": 1, "total": 3})

    def test_thin_week_is_flagged(self) -> None:
        thin = json.loads(json.dumps(PRICE))
        for group in ("macro", "watchlist"):
            for entry in thin[group].values():
                h = entry["history"]
                keep = [i for i, d in enumerate(h["dates"]) if d < "2026-09-07" or d >= "2026-09-10"]
                h["dates"] = [h["dates"][i] for i in keep]
                h["close"] = [h["close"][i] for i in keep]
        result = weekly_stats.compute(thin, "kr")
        self.assertEqual(result["trading_days"], ["2026-09-10", "2026-09-11"])
        self.assertTrue(result["thin"])

    def test_latest_price_file_ignores_files_after_the_date(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        for day in ("2026-09-04", "2026-09-11", "2026-09-18"):
            (tmp / f"price_kr_{day}.json").write_text("{}", encoding="utf-8")
        found = weekly_stats.latest_price_file("kr", dt.date(2026, 9, 12), tmp)
        self.assertEqual(found.name, "price_kr_2026-09-11.json")
        self.assertIsNone(weekly_stats.latest_price_file("us", dt.date(2026, 9, 12), tmp))

    def test_entries_without_history_get_one_from_the_daily_files(self) -> None:
        """원/달러 환율은 실시간 호가라 3개월 이력이 없다 — 날마다 커밋한 파일의 값을 이어 붙인다."""
        tmp = Path(tempfile.mkdtemp())
        for day, fx in (("2026-09-04", 1351.3), ("2026-09-07", 1347.7), ("2026-09-11", 1344.4)):
            (tmp / f"price_kr_{day}.json").write_text(json.dumps(
                {"trading_date": day, "macro": {"USD/KRW": {"ticker": "USD/KRW", "name": "원/달러 환율",
                                                            "price": fx, "unit": "원", "trading_date": day}},
                 "watchlist": {}}), encoding="utf-8")
        latest = json.loads((tmp / "price_kr_2026-09-11.json").read_text(encoding="utf-8"))
        added = weekly_stats.augment_from_daily_files(latest, "kr", tmp)
        self.assertEqual(added, ["원/달러 환율"])
        result = weekly_stats.compute(latest, "kr")
        fx = next(m for m in result["macro"] if m["ticker"] == "USD/KRW")
        self.assertEqual(fx["prev_close"], 1351.3)
        self.assertEqual(fx["last_close"], 1344.4)

    def test_text_rendering_names_the_week_and_trading_days(self) -> None:
        text = weekly_stats.render_text(weekly_stats.compute(PRICE, "kr"))
        self.assertIn("9월 7일~9월 11일", text)
        self.assertIn("거래일 5일", text)
        self.assertIn("두산에너빌리티", text)


class SeriesRegistrationTest(unittest.TestCase):
    """새 시리즈는 새 파이프라인이 아니라 표에 한 줄씩 — 그 줄들이 다 있는지."""

    def test_thresholds_exist_for_both_series(self) -> None:
        self.assertEqual(feature_checks.SERIES_LIMITS["주간 결산"]["graphics"], 4)
        self.assertEqual(feature_checks.SERIES_LIMITS["다음 주 일정"]["graphics"], 3)
        self.assertEqual(editorial_title.SECTION_FLOORS["주간 결산"], 5)
        self.assertEqual(editorial_title.SECTION_FLOORS["다음 주 일정"], 4)
        self.assertEqual(source_check.SERIES_MIN_SOURCES["주간 결산"], 2)
        self.assertEqual(source_check.SERIES_MIN_SOURCES["다음 주 일정"], 2)

    def test_recent_titles_lists_are_series_specific(self) -> None:
        self.assertEqual(feature_gate.SERIES_FOLDER["주간 결산"], "weekly")
        self.assertEqual(feature_gate.SERIES_FOLDER["다음 주 일정"], "weekly")
        self.assertIn("review_", recent_titles.LISTS["weekly"])
        self.assertIn("ahead_", recent_titles.LISTS["weekahead"])

    def test_recent_titles_do_not_mix_the_two_weekend_series(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        folder = tmp / "editorial" / "weekly"
        folder.mkdir(parents=True)
        (folder / "review_2026-09-05.json").write_text(json.dumps(
            {"series": "주간 결산", "date": "2026-09-05", "slug": "weekly-review-2026-09-05",
             "ko": {"title": "지난주 결산 제목"}}, ensure_ascii=False), encoding="utf-8")
        (folder / "ahead_2026-09-06.json").write_text(json.dumps(
            {"series": "다음 주 일정", "date": "2026-09-06", "slug": "week-ahead-2026-09-06",
             "ko": {"title": "지난주 일정 제목"}}, ensure_ascii=False), encoding="utf-8")
        original = feature_gate.ROOT
        try:
            feature_gate.ROOT = tmp
            titles = feature_gate.recent_titles({"series": "주간 결산", "slug": "weekly-review-2026-09-12"})
        finally:
            feature_gate.ROOT = original
        self.assertEqual(titles, ["지난주 결산 제목"])


class KickerTest(unittest.TestCase):
    def test_weekend_kickers_carry_the_period(self) -> None:
        review = {"series": "주간 결산", "period": {"start": "2026-09-07", "end": "2026-09-11"}}
        ahead = {"series": "다음 주 일정", "period": {"start": "2026-09-28", "end": "2026-10-02"}}
        self.assertEqual(publish_feature._kicker(review), "주간 결산 · 9월 7일~11일")
        self.assertEqual(publish_feature._kicker(ahead), "다음 주 일정 · 9월 28일~10월 2일")
        self.assertEqual(publish_feature._kicker({"series": "주간 결산"}), "주간 결산")

    def test_seo_lead_names_the_week(self) -> None:
        review = {"series": "주간 결산", "period": {"start": "2026-09-07", "end": "2026-09-11"}}
        self.assertEqual(publish_feature._seo_lead(review), "9월 7일~11일 주간 증시 결산입니다. ")
        self.assertEqual(publish_feature._seo_lead({"series": "기준표", "date": "2026-09-12"}), "")


class PeriodGraphicsTest(unittest.TestCase):
    """주간 카드·막대는 하루 등락이 아니라 이력에서 센 주간 등락으로 그린다."""

    def test_movers_list_uses_weekly_change_and_never_the_table(self) -> None:
        out = Path(tempfile.mkdtemp()) / "m.png"
        data_graphics.movers_list(PRICE, out, top_n=3, period_days=5, style="table")
        with Image.open(out) as image:
            self.assertEqual(image.width, data_graphics.W)
        rows = data_graphics._period_rows(PRICE, 5)
        by_name = {r["name"]: r["change_pct"] for r in rows}
        self.assertAlmostEqual(by_name["두산에너빌리티"], round((90800 / 79200 - 1) * 100, 2))
        self.assertNotIn("신규편입", by_name)

    def test_calendar_week_ignores_a_holiday_gap(self) -> None:
        """노동절(9/7)로 4거래일뿐인 주: '5거래일 전'은 전주 목요일이라 틀리고, 달력 주간은 전주 금요일 대비다."""
        dates = ["2026-08-31", "2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04",
                 "2026-09-08", "2026-09-09", "2026-09-10", "2026-09-11"]
        closes = [7600, 7620, 7650, 7700, 7718.60, 7674, 7637, 7591.70, 7656.98]
        data = {"trading_date": "2026-09-11",
                "macro": {"^GSPC": {"ticker": "^GSPC", "name": "S&P500", "price": 7656.98, "change_pct": 0.86,
                                    "history": {"dates": dates, "close": closes}, "unit": ""}},
                "watchlist": {"NVDA": {"ticker": "NVDA", "name": "엔비디아", "price": 218.29, "change_pct": -0.03,
                                       "history": {"dates": dates, "close": [230, 231, 232, 233, 230.1, 225, 222, 218.36, 218.29]}}}}
        week = data_graphics._pct_week(data["macro"]["^GSPC"], "2026-09-11")
        self.assertAlmostEqual(week, (7656.98 / 7718.60 - 1) * 100, places=4)
        five = data_graphics._pct_over(data["macro"]["^GSPC"], 5)
        self.assertNotAlmostEqual(week, five, places=2)
        rows = data_graphics._period_rows(data, period="week")
        self.assertAlmostEqual(rows[0]["change_pct"], round((218.29 / 230.1 - 1) * 100, 2))
        out = Path(tempfile.mkdtemp()) / "w.png"
        self.assertTrue(data_graphics.number_cards(data, out, tickers=["^GSPC", "NVDA"], period="week").exists())
        self.assertTrue(data_graphics.movers_list(data, out, period="week").exists())

    def test_number_cards_label_the_period(self) -> None:
        out = Path(tempfile.mkdtemp()) / "n.png"
        self.assertTrue(data_graphics.number_cards(PRICE, out, tickers=["KS11", "005930"], period_days=5).exists())
        with self.assertRaises(ValueError):
            data_graphics.number_cards(PRICE, out, tickers=["999999", "KS11"], period_days=5)


class NaverPostTest(unittest.TestCase):
    def _manuscript(self, series: str, slug: str) -> Path:
        doc = {"kind": "feature", "series": series, "date": "2026-09-12", "slug": slug,
               "period": {"start": "2026-09-07", "end": "2026-09-11"},
               "ko": {"title": "이번 주 증시, 무엇이 올리고 무엇이 막았나",
                      "narrative": [{"heading": "1. 한 주를 숫자로", "body": "코스피는 한 주에 3.33% 올랐습니다."}],
                      "closing": {"heading": "Fermata's Take", "body": "우리는 이렇게 봅니다."}}}
        path = Path(tempfile.mkdtemp()) / f"{slug}.json"
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return path

    def test_weekly_review_gets_a_period_prefix_and_daily_category(self) -> None:
        post = naver_post.build(self._manuscript("주간 결산", "weekly-review-2026-09-12"))
        self.assertTrue(post["title"].startswith("주간 증시 결산 9월 7일~11일: "))
        self.assertEqual(post["category"], "Weekly")
        self.assertEqual(post["blocks"][-1][1], "https://fermata.it.kr/weekly-review-2026-09-12/")
        self.assertIn("주간증시", post["tags"])

    def test_week_ahead_prefix(self) -> None:
        post = naver_post.build(self._manuscript("다음 주 일정", "week-ahead-2026-09-13"))
        self.assertTrue(post["title"].startswith("다음 주 증시 일정 9월 7일~11일: "))
        self.assertIn("증시일정", post["tags"])


class WorkflowTest(unittest.TestCase):
    def test_weekly_publish_workflow_publishes_main_commits_immediately(self) -> None:
        text = (ROOT / ".github" / "workflows" / "weekly_publish.yml").read_text(encoding="utf-8")
        self.assertIn('- "editorial/weekly/*.json"', text)
        self.assertIn("branches: [main]", text)
        self.assertIn("python -m src.publish_feature", text)
        self.assertIn("--publish", text)
        self.assertNotIn("--render-only", text)
        for name in ("WORDPRESS_URL", "WORDPRESS_USERNAME", "WORDPRESS_APP_PASSWORD"):
            self.assertIn(f"secrets.{name}", text)
        self.assertIn("fonts-nanum", text)

    def test_routine_docs_point_at_real_modules(self) -> None:
        import re
        for name in ("routine_week_review.md", "routine_week_ahead.md"):
            text = (ROOT / "docs" / name).read_text(encoding="utf-8")
            modules = set(re.findall(r"python -m ((?:src|scripts)\.[a-z_]+)", text))
            self.assertTrue(modules, name)
            for module in modules:
                self.assertTrue((ROOT / (module.replace(".", "/") + ".py")).exists(), f"{name}: {module}")
            self.assertIn("weekly_publish.yml", text)
            self.assertIn("src.feature_gate", text)


if __name__ == "__main__":
    unittest.main()
