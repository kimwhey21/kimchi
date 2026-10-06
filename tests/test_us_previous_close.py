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


class RequiredTradingDateTest(unittest.TestCase):
    """미국장 기준일은 필수 지수 셋에서 — 서로 다르면 무작위로 하나를 고르지 않고 멈춘다(2026-09-26)."""

    def test_agreeing_indexes_give_the_date(self) -> None:
        macro = {t: {"trading_date": "2026-09-25"} for t in ("^DJI", "^GSPC", "^IXIC")}
        self.assertEqual(fetch_us.required_trading_date(macro), "2026-09-25")

    def test_a_lagging_index_stops_the_run(self) -> None:
        macro = {"^DJI": {"trading_date": "2026-09-25"}, "^GSPC": {"trading_date": "2026-09-25"},
                 "^IXIC": {"trading_date": "2026-09-24"}}
        with self.assertRaises(ValueError):
            fetch_us.required_trading_date(macro)


if __name__ == "__main__":
    unittest.main()


class UsRecheckTest(unittest.TestCase):
    """밤 증명서가 미국장 값 전부를 공식 원천으로 다시 맞춘다(2026-10-06, 감사 F-147·F-177)."""

    def test_every_value_goes_to_its_official_source(self) -> None:
        from unittest import mock
        from src import close_check, fetch_us
        doc = {"trading_date": "2026-10-05",
               "macro": {"^GSPC": {"ticker": "^GSPC", "name": "S&P500", "price": 7773.95},
                         "^VIX": {"ticker": "^VIX", "name": "VIX", "price": 15.52},
                         "^TNX": {"ticker": "^TNX", "name": "10년물", "price": 5.31, "unit": "%"},
                         "GC=F": {"ticker": "GC=F", "name": "금", "price": 4156.8}},
               "watchlist": {"NVDA": {"ticker": "NVDA", "name": "엔비디아", "price": 190.0, "close_sources": ["yahoo", "cnbc"]},
                             "AAPL": {"ticker": "AAPL", "name": "애플", "price": 250.0}}}
        cboe = {"^GSPC": {"2026-10-05": 7773.95}, "^VIX": {"2026-10-05": 15.52}, "^TNX": {"2026-10-05": 5.312}}
        with mock.patch.object(fetch_us, "cboe_closes", side_effect=lambda t: cboe[t]), \
                mock.patch.object(fetch_us, "nasdaq_closes", side_effect=lambda t, d: {"NVDA": {d: 191.0}}.get(t, {})):
            wrong, checked, missing = close_check.us_recheck(doc)
        self.assertEqual(checked, 4)                       # S&P·VIX(전에는 FRED에 없어 건너뛰며 셌다)·10년물·엔비디아
        self.assertEqual(missing, ["애플"])                 # 공식 값을 못 받으면 '못 맞춤'
        self.assertEqual(len(wrong), 1)                    # CNBC로만 확인했던 엔비디아 190 / 공식 191
        self.assertIn("엔비디아", wrong[0])
