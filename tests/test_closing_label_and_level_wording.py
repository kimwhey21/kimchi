"""2026-09-07 저녁에 사용자가 짚은 두 가지를 고정합니다.

1. 시황 마무리 절의 소제목은 원고가 아니라 템플릿이 "Fermata's Take"로 찍는다.
   루틴이 날마다 다른 말('정리하면'·'남는 것'·'마무리')을 붙였고, 브랜드 표식이
   '마무리'로 바뀐 것을 사용자가 바로 알아챘다.
2. 가격·수준을 "…한 자리입니다"로 끝내는 문장은 검사가 막는다.
   ("7,000선까지 4.61포인트가 남은 자리입니다" → "7,000선까지는 4.61포인트가 남았습니다")
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from src.editorial_quality import collect_issues

TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "post.html.j2"


class ClosingLabelTest(unittest.TestCase):
    def test_closing_heading_is_fixed_in_template(self) -> None:
        source = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("<h2>Fermata's Take</h2>", source)
        self.assertNotRegex(source, r"<h2>\s*\{\{\s*closing\.heading\s*\}\}\s*</h2>",
                            "마무리 소제목을 원고에서 읽으면 날마다 다른 말이 붙습니다")


class LevelWordingTest(unittest.TestCase):
    def _issues(self, sentence: str) -> list[str]:
        return collect_issues({"title": "제목", "narrative": [{"heading": "h", "body": sentence}]})

    def test_price_level_ending_in_jari_is_rejected(self) -> None:
        for sentence in (
            "7,000선까지 4.61포인트가 남은 자리입니다.",
            "1,340원 부근은 1년 11개월 만의 자리입니다.",
            "8월 14% 급등의 상당 부분을 되돌린 자리입니다.",
            "고점에서 42%를 반납하고도 더 빠진 자리다.",
        ):
            with self.subTest(sentence=sentence):
                issues = self._issues(sentence)
                self.assertTrue(issues, sentence)
                self.assertTrue(any("자리입니다" in i for i in issues), issues)

    def test_position_or_place_jari_is_allowed(self) -> None:
        for sentence in (
            "가진 것은 SK하이닉스 지분 약 20%이고, 최대주주 자리입니다.",
            "그 자리에서 결론이 났습니다.",
            "자리를 잡은 뒤에는 변동성이 줄었습니다.",
        ):
            with self.subTest(sentence=sentence):
                self.assertEqual(self._issues(sentence), [], sentence)

    def test_rewritten_sentences_pass(self) -> None:
        for sentence in (
            "7,000선까지는 4.61포인트가 남았습니다.",
            "1,340원 부근은 1년 11개월 만에 보는 수준입니다.",
        ):
            with self.subTest(sentence=sentence):
                self.assertEqual(self._issues(sentence), [], sentence)


if __name__ == "__main__":
    unittest.main()
