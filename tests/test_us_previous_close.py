"""미국장 등락률의 분모(직전 종가) 고르기 (2026-09-26).

메타데이터 previousClose는 일봉에서 직전 거래일이 빠진 날을 메워 주지만, 그 사이 장이 없었던 날(채권만 쉬는 날,
휴장 뒤 재실행)에는 마지막 종가와 같은 값을 줘서 등락률을 0.00%로 만든다. 9/04 파일의 ^TNX가 그 예다.
"""
import unittest

from src import fetch_us


class PreviousCloseTest(unittest.TestCase):
    def test_metadata_fills_a_missing_daily_row(self) -> None:
        # 2026-08-31: 일봉에 8/28이 빠져 8/27(=historical)과 비교될 뻔했다. 메타데이터가 실제 8/28 종가를 준다.
        meta = {"regularMarketPrice": 100.0, "previousClose": 99.0}
        self.assertEqual(fetch_us.previous_close(97.0, 100.0, meta), 99.0)

    def test_no_session_day_keeps_the_daily_history(self) -> None:
        # 9/04 ^TNX: 일봉 4.762→4.784인데 메타데이터 직전 종가가 4.784라 0.00%가 찍혔다.
        meta = {"regularMarketPrice": 4.784, "previousClose": 4.784}
        prev = fetch_us.previous_close(4.762, 4.784, meta)
        self.assertEqual(prev, 4.762)
        self.assertAlmostEqual((4.784 - prev) / prev * 100, 0.46, places=2)

    def test_truly_flat_day_stays_flat(self) -> None:
        meta = {"regularMarketPrice": 50.0, "previousClose": 50.0}
        self.assertEqual(fetch_us.previous_close(50.0, 50.0, meta), 50.0)

    def test_metadata_for_another_price_is_ignored(self) -> None:
        # 메타데이터 가격이 마지막 일봉과 다르면(장중 값 등) 일봉을 쓴다.
        meta = {"regularMarketPrice": 105.0, "previousClose": 99.0}
        self.assertEqual(fetch_us.previous_close(97.0, 100.0, meta), 97.0)

    def test_missing_metadata_falls_back(self) -> None:
        self.assertEqual(fetch_us.previous_close(97.0, 100.0, {}), 97.0)
        self.assertEqual(fetch_us.previous_close(97.0, 100.0, None), 97.0)


if __name__ == "__main__":
    unittest.main()
