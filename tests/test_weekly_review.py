"""주간 점검 보고서의 「검색 성적」 절 (2026-09-12, 사용자 승인 "주간 검색 성적 기록").

구글·네이버 색인 수는 관리자 화면에서만 읽히므로 이 맥의 일요일 작업이 reports/search_<날짜>.md로 남기고,
weekly_review가 가장 최근 것을 보고서에 싣는다. 두 기록이 있으면 변화도 적는다.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import weekly_review


class SearchReportTest(unittest.TestCase):
    def test_latest_search_report_is_included_with_the_change(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        (tmp / "search_2026-09-12.md").write_text("# 검색 성적 2026-09-12\n| 항목 | 값 |\n|---|---|\n| 구글 색인 생성됨 | 11 |\n", encoding="utf-8")
        (tmp / "search_2026-09-12.json").write_text(json.dumps({"date": "2026-09-12", "google_indexed": 11, "naver_indexed": 1}), encoding="utf-8")
        (tmp / "search_2026-09-19.md").write_text("# 검색 성적 2026-09-19\n| 항목 | 값 |\n|---|---|\n| 구글 색인 생성됨 | 30 |\n", encoding="utf-8")
        (tmp / "search_2026-09-19.json").write_text(json.dumps({"date": "2026-09-19", "google_indexed": 30, "naver_indexed": 12}), encoding="utf-8")
        lines = weekly_review.latest_search_report(tmp)
        self.assertEqual(lines[0], "기록일 2026-09-19")
        self.assertIn("| 구글 색인 생성됨 | 30 |", lines)
        self.assertTrue(any("11 → 30" in l and "1 → 12" in l for l in lines), lines)

    def test_no_report_means_an_empty_section(self) -> None:
        self.assertEqual(weekly_review.latest_search_report(Path(tempfile.mkdtemp())), [])


if __name__ == "__main__":
    unittest.main()
