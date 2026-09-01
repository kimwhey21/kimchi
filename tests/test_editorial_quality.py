from __future__ import annotations

import unittest

from src.editorial_quality import EditorialQualityError, validate_generated


class EditorialQualityTest(unittest.TestCase):
    def test_rejects_translated_month_close_expression(self) -> None:
        with self.assertRaises(EditorialQualityError):
            validate_generated({"title": "뉴욕증시는 8월을 약세로 닫았습니다"})

    def test_rejects_personified_market_expression(self) -> None:
        with self.assertRaises(EditorialQualityError):
            validate_generated({"title": "유가가 오른 날, 뉴욕증시는 물러섰습니다"})

    def test_accepts_direct_market_close_expression(self) -> None:
        validate_generated({"title": "유가 상승에 뉴욕증시는 하락 마감했습니다"})


if __name__ == "__main__":
    unittest.main()
