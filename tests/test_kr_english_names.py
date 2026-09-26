"""동적 편입 한국 종목의 영어 이름 (2026-09-26).

name_en_map에 없는 종목은 한글 이름이 영어판에 그대로 나갔다(9/17 "Sphere (스피어)", 9/18 가온전선, 9/21 SFA반도체).
야후 회사명으로 채우되, 시장 접미어가 틀리면 다른 회사가 나오므로(347700.KS) 시장을 모르면 찾지 않는다.
"""
import unittest
from unittest import mock

from src import fetch_kr


class CleanNameTest(unittest.TestCase):
    def test_corporate_tails_and_all_caps(self) -> None:
        self.assertEqual(fetch_kr.clean_english_name("GAON CABLE Co., Ltd."), "Gaon Cable")
        self.assertEqual(fetch_kr.clean_english_name("Sphere Corp."), "Sphere")
        self.assertEqual(fetch_kr.clean_english_name("SFA Semicon Co.,Ltd."), "SFA Semicon")
        self.assertEqual(fetch_kr.clean_english_name("LG Energy Solution, Ltd."), "LG Energy Solution")

    def test_non_latin_is_rejected(self) -> None:
        self.assertIsNone(fetch_kr.clean_english_name("삼성전자"))
        self.assertIsNone(fetch_kr.clean_english_name(""))


class EnglishNameTest(unittest.TestCase):
    def test_uses_the_market_suffix(self) -> None:
        fake = mock.MagicMock()
        fake.Ticker.return_value.info = {"longName": "Sphere Corp."}
        with mock.patch.dict("sys.modules", {"yfinance": fake}):
            self.assertEqual(fetch_kr.english_name("347700", "KOSDAQ"), "Sphere")
        fake.Ticker.assert_called_once_with("347700.KQ")

    def test_unknown_market_does_not_guess(self) -> None:
        fake = mock.MagicMock()
        with mock.patch.dict("sys.modules", {"yfinance": fake}):
            self.assertIsNone(fetch_kr.english_name("347700", None))
        fake.Ticker.assert_not_called()

    def test_lookup_failure_falls_back_to_none(self) -> None:
        fake = mock.MagicMock()
        fake.Ticker.side_effect = RuntimeError("blocked")
        with mock.patch.dict("sys.modules", {"yfinance": fake}):
            self.assertIsNone(fetch_kr.english_name("000500", "KOSPI"))


if __name__ == "__main__":
    unittest.main()
