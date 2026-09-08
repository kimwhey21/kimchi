"""시황 원고의 절 수·소제목 길이 검사(2026-09-08).

사용자가 9/8 한국장 글을 보고 "제목·소제목이 재테크농부처럼 나왔으면 좋겠다"고 했다.
그 글은 6절, 소제목은 전부 30~35자 문장이었다. 벤치마크 최근 104편은 편당 소제목
중앙값 14개, 길이 중앙값 23자다. 문서에만 적으면 다음 날 또 새므로 검사로 굳힌다.
"""
from __future__ import annotations

import unittest

from src import editorial_quality


def _doc(n: int, heading: str = "업종별 흐름") -> dict:
    return {"title": "t", "narrative": [{"heading": f"{i}. {heading}", "body": "본문."} for i in range(1, n + 1)]}


class DailyStructureTest(unittest.TestCase):
    def test_six_sections_is_too_few(self) -> None:
        issues = editorial_quality.collect_daily_issues(_doc(6))
        self.assertTrue(any("절 이상" in i for i in issues), issues)

    def test_ten_short_sections_pass(self) -> None:
        self.assertEqual(editorial_quality.collect_daily_issues(_doc(10)), [])

    def test_long_heading_is_rejected(self) -> None:
        doc = _doc(10)
        doc["narrative"][0]["heading"] = "1. 대우건설이 오르고 삼성전기가 하락한, 업종 로테이션의 하루였습니다"
        issues = editorial_quality.collect_daily_issues(doc)
        self.assertEqual(len(issues), 1)
        self.assertIn("32자 이하", issues[0])

    def test_number_prefix_does_not_count(self) -> None:
        doc = _doc(10, heading="가" * 32)
        self.assertEqual(editorial_quality.collect_daily_issues(doc), [])

    def test_validate_daily_raises(self) -> None:
        with self.assertRaises(editorial_quality.EditorialQualityError):
            editorial_quality.validate_daily(_doc(3))


if __name__ == "__main__":
    unittest.main()
