"""실제 표 그래픽(fact_table)과 주간 점검 스크립트 (2026-09-08, 제안 7·9번)."""
from __future__ import annotations

import datetime as dt
import tempfile
import unittest
from pathlib import Path

from src import data_graphics
from scripts import weekly_review


@unittest.skipUnless(data_graphics.has_korean_font(), "한글 폰트가 없어 렌더를 건너뜁니다")
class FactTableTest(unittest.TestCase):
    def test_renders_rows_and_needs_source(self) -> None:
        out = Path(tempfile.mkdtemp()) / "t.png"
        rows = [["8월 비농업 고용", "16.2만", "5.3만", "+10.9만"], ["실업률", "4.3%", "4.3%", "0"], ["시간당 임금", "+0.3%", "+0.3%", "-"]]
        data_graphics.fact_table({}, out, rows=rows, source="미 노동부, 블룸버그 예상치", title="8월 고용, 예상의 세 배")
        self.assertTrue(out.exists())
        with self.assertRaises(ValueError):
            data_graphics.fact_table({}, out, rows=rows, source="")
        with self.assertRaises(ValueError):
            data_graphics.fact_table({}, out, rows=[], source="x")

    def test_registered_and_priceless(self) -> None:
        self.assertIn("fact_table", data_graphics.BUILDERS)
        self.assertIn("fact_table", data_graphics.PRICELESS_KINDS)


class WeeklyReviewTest(unittest.TestCase):
    def test_report_renders_for_the_current_repo(self) -> None:
        end = dt.date(2026, 9, 6)   # 9/1~9/6 — 원고가 있는 주
        data = weekly_review.collect(end)
        report, summary = weekly_review.render(data)
        self.assertIn("지난 한 주 점검", report)
        self.assertIn("재테크농부", report)
        self.assertTrue(summary.splitlines()[0].startswith("지난 한 주"))
        self.assertGreaterEqual(len(data["daily"]), 4)

    def test_cli_writes_a_file(self) -> None:
        out = Path(tempfile.mkdtemp())
        weekly_review.main(["--week-ending", "2026-09-06", "--out", str(out)])
        self.assertTrue((out / "weekly_2026-09-06.md").exists())


if __name__ == "__main__":
    unittest.main()
