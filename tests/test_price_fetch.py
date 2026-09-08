import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from src import fetch_kr, fetch_us


class KoreanPriceFetchTests(unittest.TestCase):
    def test_ignores_missing_close_and_uses_last_valid_date(self):
        frame = pd.DataFrame(
            {"Close": [1350.0, float("nan"), 1363.5, float("nan")]},
            index=pd.to_datetime(
                ["2026-08-28", "2026-08-29", "2026-08-31", "2026-09-01"]
            ),
        )

        with patch.object(fetch_kr.fdr, "DataReader", return_value=frame):
            result = fetch_kr._fetch_one("USD/KRW", "원/달러 환율")

        self.assertEqual(result["series"], [1350.0, 1363.5])
        self.assertEqual(result["price"], 1363.5)
        self.assertEqual(result["change_pct"], 1.0)
        self.assertEqual(result["trading_date"], "2026-08-31")

    def test_replaces_partial_index_row_with_confirmed_close(self):
        entry = {
            "price": 6779.87,
            "change_pct": -0.59,
            "series": [6820.02, 6779.87],
            "trading_date": fetch_kr.dt.date.today().isoformat(),
        }
        quote = {"cd": "KOSPI", "ms": "CLOSE", "nv": 683580, "cr": 0.23}

        result = fetch_kr._apply_final_index_quote(entry, "KS11", quote)

        self.assertEqual(result["price"], 6835.8)
        self.assertEqual(result["change_pct"], 0.23)
        self.assertEqual(result["series"], [6820.02, 6835.8])

    def test_rejects_current_index_without_close_state(self):
        entry = {
            "series": [6820.02, 6779.87],
            "trading_date": fetch_kr.dt.date.today().isoformat(),
        }

        with self.assertRaisesRegex(ValueError, "ms=CLOSE"):
            fetch_kr._apply_final_index_quote(
                entry, "KS11", {"cd": "KOSPI", "ms": "OPEN", "nv": 677987, "cr": -0.59}
            )

    def test_uses_timestamped_hana_bank_reference_rate(self):
        detail_response = MagicMock()
        detail_response.json.return_value = {
            "exchangeInfo": {
                "priceDataType": "NOTICE_ROUND",
                "localTradedAt": "2026-09-01T16:25:13+09:00",
                "closePrice": "1,373.30",
                "fluctuationsRatio": "0.28",
            }
        }
        prices_response = MagicMock()
        prices_response.json.return_value = [
            {"closePrice": "1,373.30"},
            {"closePrice": "1,369.50"},
            {"closePrice": "1,381.00"},
        ]

        with patch.object(
            fetch_kr.requests, "get", side_effect=[detail_response, prices_response]
        ):
            result = fetch_kr._fetch_usdkrw_reference(
                "USD/KRW", "원/달러 환율", name_en="USD/KRW", unit="원"
            )

        self.assertEqual(result["price"], 1373.3)
        self.assertEqual(result["change_pct"], 0.28)
        self.assertEqual(result["series"], [1381.0, 1369.5, 1373.3])
        self.assertEqual(result["as_of_label"], "16:25 하나은행 고시")
        self.assertEqual(result["reference_label_en"], "2026-09-01 16:25 Hana Bank notice")
        self.assertEqual(result["quote_type"], "reference_rate")


class USPriceFetchTests(unittest.TestCase):
    def test_ignores_missing_close_and_uses_last_valid_date(self):
        frame = pd.DataFrame(
            {"Close": [100.0, float("nan"), 102.0]},
            index=pd.to_datetime(["2026-08-27", "2026-08-28", "2026-08-31"]),
        )
        ticker_client = MagicMock()
        ticker_client.get_history_metadata.return_value = {}
        ticker_client.history.return_value = frame

        with patch.object(fetch_us.yf, "Ticker", return_value=ticker_client):
            result = fetch_us._fetch_one("TEST", "Test")

        self.assertEqual(result["series"], [100.0, 102.0])
        self.assertEqual(result["change_pct"], 2.0)
        self.assertEqual(result["trading_date"], "2026-08-31")


if __name__ == "__main__":
    unittest.main()


class LaggingIndexDailyBarTest(unittest.TestCase):
    """지수 일봉이 종목보다 늦게 나오는 날 — 2026-09-08 한국장 글이 빠진 이유.

    코스피·코스닥 일봉(KRX 집계)은 18:30 KST까지도 전날에 머물렀고, 개별 종목은
    이미 그날 종가였다. 워크플로 3회와 예비 루틴이 전부 "기준일 불일치"로 멈췄다.
    네이버 실시간 응답은 그때 이미 ms=CLOSE였으므로, **전일 종가 + 등락폭 = 확정
    종가** 등식이 맞을 때만 그 값을 오늘 행으로 덧붙인다.
    """

    def _yesterday_entry(self) -> dict:
        yesterday = (fetch_kr.dt.date.today() - fetch_kr.dt.timedelta(days=1)).isoformat()
        return {"ticker": "KS11", "price": 6995.39, "change_pct": 4.61,
                "series": [6562.72, 6579.48, 6687.21, 6995.39], "trading_date": yesterday}

    def test_appends_todays_close_when_the_daily_bar_lags(self) -> None:
        quote = {"ms": "CLOSE", "nv": 695452, "cv": -4087, "cr": -0.58, "cd": "KOSPI"}
        result = fetch_kr._apply_final_index_quote(self._yesterday_entry(), "KS11", quote)
        self.assertEqual(result["trading_date"], fetch_kr.dt.date.today().isoformat())
        self.assertEqual(result["price"], 6954.52)
        self.assertEqual(result["change_pct"], -0.58)
        self.assertEqual(result["series"], [6579.48, 6687.21, 6995.39, 6954.52])
        self.assertIn("daily bar", result["data_source"])

    def test_holiday_does_not_get_a_fake_row(self) -> None:
        """휴장일엔 네이버 확정값이 곧 일봉 마지막 행이라 등식이 안 맞는다 — 그대로 둔다."""
        entry = self._yesterday_entry()
        quote = {"ms": "CLOSE", "nv": 699539, "cv": 30818, "cr": 4.61, "cd": "KOSPI"}
        self.assertEqual(fetch_kr._apply_final_index_quote(entry, "KS11", quote), entry)

    def test_intraday_quote_is_not_appended(self) -> None:
        entry = self._yesterday_entry()
        quote = {"ms": "OPEN", "nv": 695452, "cv": -4087, "cr": -0.58, "cd": "KOSPI"}
        self.assertEqual(fetch_kr._apply_final_index_quote(entry, "KS11", quote), entry)

    def test_mismatched_arithmetic_is_not_appended(self) -> None:
        entry = self._yesterday_entry()
        quote = {"ms": "CLOSE", "nv": 695452, "cv": -1000, "cr": -0.14, "cd": "KOSPI"}
        self.assertEqual(fetch_kr._apply_final_index_quote(entry, "KS11", quote), entry)
