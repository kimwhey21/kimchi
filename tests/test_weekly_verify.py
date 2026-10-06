"""주간 결산 숫자의 바탕 확인(2026-10-06).

주간 결산은 금요일 시세 파일 하나의 이력으로 센다. 10/6 전의 이력은 한국장이 넥스트레이드 합산 일봉,
미국장이 배당 조정 종가였다 — `weekly_stats.verify`가 이력을 날마다 두 원천으로 확인해 커밋한 종가와
대조하고, `editorial_facts.weekly_issues`가 원고의 주간 등락률을 같은 계산과 대조한다.
"""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts import weekly_stats
from src import editorial_facts

DATES = ["2026-10-02", "2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08"]


def _file(day: str, samsung: list[float], sources=("daum", "naver_snapshot")) -> dict:
    dates = [d for d in DATES if d <= day]
    closes = samsung[:len(dates)]
    entry = {"ticker": "005930", "name": "삼성전자", "price": closes[-1], "change_pct": 0.0, "sector": "반도체",
             "source": "core", "history": {"dates": dates, "close": closes}}
    if sources:
        entry["close_sources"] = list(sources)
    return {"trading_date": day, "macro": {}, "watchlist": {"005930": entry}}


class VerifyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        closes = [276000.0, 280000.0, 282000.0, 281000.0, 290000.0]
        for day in DATES[1:]:
            (self.tmp / f"price_kr_{day}.json").write_text(json.dumps(_file(day, closes)), encoding="utf-8")
        self.closes = closes

    def test_history_equal_to_checked_closes_passes(self) -> None:
        latest = _file("2026-10-08", self.closes)
        self.assertEqual(weekly_stats.verify(latest, "kr", self.tmp), [])

    def test_history_that_differs_from_a_checked_close_is_named(self) -> None:
        wrong = list(self.closes)
        wrong[2] = 284000.0   # 10/6 이력이 합산값
        issues = weekly_stats.verify(_file("2026-10-08", wrong), "kr", self.tmp)
        self.assertEqual(len(issues), 1)
        self.assertIn("2026-10-06", issues[0])
        self.assertIn("284000", issues[0])

    def test_file_made_before_two_source_check_is_refused(self) -> None:
        issues = weekly_stats.verify(_file("2026-10-08", self.closes, sources=()), "kr", self.tmp)
        self.assertTrue(any("close_sources" in i for i in issues))

    def test_missing_day_in_history_is_named(self) -> None:
        latest = _file("2026-10-08", self.closes)
        h = latest["watchlist"]["005930"]["history"]
        del h["dates"][2], h["close"][2]
        issues = weekly_stats.verify(latest, "kr", self.tmp)
        self.assertTrue(any("이력에 그날이 없습니다" in i for i in issues))

    def test_cli_stops_with_code_3(self) -> None:
        wrong = list(self.closes)
        wrong[3] = 279000.0
        (self.tmp / "price_kr_2026-10-08.json").write_text(json.dumps(_file("2026-10-08", wrong)), encoding="utf-8")
        results = weekly_stats.run(["kr"], weekly_stats.dt.date(2026, 10, 8), self.tmp)
        self.assertTrue(results["kr"]["unverified"])


class WeeklyIssuesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        (self.root / "data").mkdir()
        closes = [276000.0, 280000.0, 282000.0, 281000.0, 290000.0]   # 주간 +5.07%
        for day in DATES[1:]:
            (self.root / "data" / f"price_kr_{day}.json").write_text(json.dumps(_file(day, closes)), encoding="utf-8")
        self.doc = {"series": "주간 결산", "ko": {"title": "t", "narrative": [
            {"heading": "한국장", "body": "삼성전자가 이번 주 5.07% 올랐습니다. 금요일 하루에는 3.20% 뛰었습니다."}]},
                    "graphics": [{"kind": "movers_list", "price_file": "data/price_kr_2026-10-08.json",
                                  "args": {"period": "week"}}]}

    def test_correct_weekly_number_passes_and_daily_numbers_are_skipped(self) -> None:
        self.assertEqual(editorial_facts.weekly_issues(self.doc, self.root), [])

    def test_wrong_weekly_number_is_caught(self) -> None:
        doc = copy.deepcopy(self.doc)
        doc["ko"]["narrative"][0]["body"] = "삼성전자가 이번 주 4.20% 올랐습니다."
        issues = editorial_facts.weekly_issues(doc, self.root)
        self.assertEqual(len(issues), 1)
        self.assertIn("5.07", issues[0])

    def test_hand_typed_number_card_is_checked(self) -> None:
        doc = copy.deepcopy(self.doc)
        doc["graphics"].append({"kind": "number_cards", "price_file": "data/price_kr_2026-10-08.json",
                                "args": {"period": "week", "items": [{"label": "삼성전자", "change": "+6.10% 상승"}]}})
        self.assertTrue(any("6.10" in i for i in editorial_facts.weekly_issues(doc, self.root)))

    def test_no_price_file_is_refused(self) -> None:
        doc = copy.deepcopy(self.doc)
        doc["graphics"] = []
        self.assertTrue(editorial_facts.weekly_issues(doc, self.root))


if __name__ == "__main__":
    unittest.main()
