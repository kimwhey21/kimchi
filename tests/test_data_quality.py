from __future__ import annotations

import unittest

from src.data_quality import MarketDataNotReadyError, validate_trading_dates


class TradingDateQualityTest(unittest.TestCase):
    def test_rejects_mixed_korea_index_and_stock_dates(self) -> None:
        price_data = {
            "macro": {
                "KS11": {"trading_date": "2026-08-31"},
                "KQ11": {"trading_date": "2026-08-31"},
                "USD/KRW": {"trading_date": "2026-08-30"},
            },
            "watchlist": {"005930": {"trading_date": "2026-09-01"}},
        }
        with self.assertRaises(MarketDataNotReadyError):
            validate_trading_dates("kr", price_data)

    def test_allows_lagging_fx_date_when_core_market_dates_match(self) -> None:
        price_data = {
            "macro": {
                "KS11": {"trading_date": "2026-09-01"},
                "KQ11": {"trading_date": "2026-09-01"},
                "USD/KRW": {"trading_date": "2026-08-31"},
            },
            "watchlist": {"005930": {"trading_date": "2026-09-01"}},
        }
        validate_trading_dates("kr", price_data)


if __name__ == "__main__":
    unittest.main()
