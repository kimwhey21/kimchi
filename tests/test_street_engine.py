"""「월가 리포트」 엔진 (2026-09-17, 사장님: "월가 의견 밀도 재테크농부 만큼 늘리고").

`ratings`는 워치리스트 16종목만 봐서 하루 1~2건이었다. 재테크농부 시황은 매일 18건을 싣는다.
`street`는 MarketBeat 오늘 페이지(시장 전체)를 읽어 등급 전→후·목표가 전→후를 같이 낸다.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from src import story_engines

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "marketbeat_ratings_sample.html"


class StreetParserTest(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = story_engines._street_rows(FIXTURE.read_text(encoding="utf-8"))

    def test_dollar_rows_only_and_actions_classified(self) -> None:
        tickers = [r["ticker"] for r in self.rows]
        self.assertNotIn("GFRD", tickers)                       # 런던(GBX)은 뺀다
        self.assertNotIn("AAPL", tickers)                       # 목표가 없는 '유지'는 이야기가 없다
        self.assertIn("CVX", tickers)                           # 목표가 있는 '유지'는 남긴다
        by = {r["ticker"]: r for r in self.rows}
        self.assertEqual(by["ADSK"]["action"], "up")
        self.assertEqual((by["ADSK"]["from_grade"], by["ADSK"]["to_grade"]), ("Neutral", "Outperform"))
        self.assertEqual(by["BSX"]["action"], "down")
        self.assertEqual(by["ABEO"]["action"], "init")
        self.assertEqual((by["MSFT"]["target_from"], by["MSFT"]["target_to"]), ("$520.00", "$560.00"))
        self.assertEqual(by["ADSK"]["firm"], "The Goldman Sachs Group")   # 'Subscribe to …' 꼬리를 뗀다

    def test_engine_orders_upgrades_first_and_counts(self) -> None:
        import unittest.mock as mock

        class Resp:
            text = FIXTURE.read_text(encoding="utf-8")

            def raise_for_status(self) -> None:
                pass

        calls = []

        def fake_get(url, **kwargs):
            calls.append(url)
            if "page=2" in url:
                r = Resp(); r.text = "<html></html>"; return r
            return Resp()

        with mock.patch.object(story_engines.requests, "get", side_effect=fake_get):
            result = story_engines.street()
        self.assertEqual(result["source"], "marketbeat")
        self.assertEqual([r["action"] for r in result["rows"][:2]], ["up", "down"])
        self.assertEqual(result["counts"]["up"], 1)
        self.assertEqual(result["counts"]["pt_up"], 1)
        self.assertGreaterEqual(result["total"], 5)


if __name__ == "__main__":
    unittest.main()
