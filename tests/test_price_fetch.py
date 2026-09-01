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
