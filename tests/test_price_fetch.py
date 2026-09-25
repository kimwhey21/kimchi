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

    def test_naver_basis_differs_from_krx_daily_bar(self) -> None:
        """2026-09-18: 일봉의 9/17 코스피 종가 6,724.34 ≠ 우리 9/17 파일(네이버 확정값) 6,715.41.
        네이버의 오늘 등락폭 +178.82는 6,715.41 기준이라 일봉 기준 등식은 절대 안 맞는다 — 우리 파일 기준으로도 본다."""
        today = fetch_kr.dt.date.today()
        d = lambda n: (today - fetch_kr.dt.timedelta(days=n)).isoformat()
        bar = {"ticker": "KS11", "price": 6724.34, "change_pct": 0.09, "series": [6717.97, 6724.34],
               "trading_date": d(1), "history": {"dates": [d(2), d(1)], "close": [6717.97, 6724.34]}}
        prior = {"ticker": "KS11", "price": 6715.41, "change_pct": -0.04, "series": [6717.97, 6715.41],
                 "trading_date": d(1), "history": {"dates": [d(2), d(1)], "close": [6717.97, 6715.41]}}
        quote = {"ms": "CLOSE", "nv": 689423, "cv": 17882, "cr": 2.66, "cd": "KOSPI"}
        self.assertEqual(fetch_kr._apply_final_index_quote(bar, "KS11", quote), bar)   # 우리 파일 없이는 예전처럼 멈춘다
        result = fetch_kr._apply_final_index_quote(bar, "KS11", quote, prior=prior)
        self.assertEqual(result["trading_date"], today.isoformat())
        self.assertEqual(result["price"], 6894.23)
        self.assertEqual(result["change_pct"], 2.66)
        # 휴장 방어는 그대로: 어제 값(6,715.41 = 6,724.34 - 8.93?)이 아니라 어제의 등락폭이 오면 어느 기준으로도 안 맞는다
        holiday = {"ms": "CLOSE", "nv": 671541, "cv": -256, "cr": -0.04, "cd": "KOSPI"}
        self.assertEqual(fetch_kr._apply_final_index_quote(bar, "KS11", holiday, prior=prior), bar)

    def test_three_day_lag_is_bridged_by_our_own_file(self) -> None:
        """2026-09-10: 일봉은 09-07에 멈췄는데 우리 파일에는 09-09 종가가 있다 — 그 이력으로 메운다."""
        today = fetch_kr.dt.date.today()
        d = lambda n: (today - fetch_kr.dt.timedelta(days=n)).isoformat()
        stale = {"ticker": "KS11", "price": 6995.39, "change_pct": 4.61, "series": [6687.21, 6995.39],
                 "trading_date": d(3), "history": {"dates": [d(4), d(3)], "close": [6687.21, 6995.39]}}
        prior = {"ticker": "KS11", "price": 7051.64, "change_pct": 1.4, "series": [6995.39, 6954.52, 7051.64],
                 "trading_date": d(1), "history": {"dates": [d(3), d(2), d(1)], "close": [6995.39, 6954.52, 7051.64]}}
        quote = {"ms": "CLOSE", "nv": 703392, "cv": -1772, "cr": -0.25, "cd": "KOSPI"}
        result = fetch_kr._apply_final_index_quote(stale, "KS11", quote, prior=prior)
        self.assertEqual(result["trading_date"], today.isoformat())
        self.assertEqual(result["price"], 7033.92)
        self.assertEqual(result["history"]["dates"][-2:], [d(1), today.isoformat()])
        self.assertEqual(result["history"]["close"][-1], 7033.92)

    def test_prior_file_older_than_the_bar_is_ignored(self) -> None:
        entry = self._yesterday_entry()
        prior = {**entry, "trading_date": (fetch_kr.dt.date.today() - fetch_kr.dt.timedelta(days=5)).isoformat(),
                 "history": {"dates": ["x"], "close": [1.0]}}
        quote = {"ms": "CLOSE", "nv": 695452, "cv": -4087, "cr": -0.58, "cd": "KOSPI"}
        self.assertEqual(fetch_kr._apply_final_index_quote(entry, "KS11", quote, prior=prior)["price"], 6954.52)

    def test_mismatched_arithmetic_is_not_appended(self) -> None:
        entry = self._yesterday_entry()
        quote = {"ms": "CLOSE", "nv": 695452, "cv": -1000, "cr": -0.14, "cd": "KOSPI"}
        self.assertEqual(fetch_kr._apply_final_index_quote(entry, "KS11", quote), entry)

class PriorBranchCarriesChangePctTest(unittest.TestCase):
    """휴장일 재수집이 어제 파일을 밑바탕으로 쓸 때 등락률·출처도 옮긴다(2026-09-25).

    9/24 추석 휴장에 9/23 파일을 다시 쓰면서 코스피 등락률이 0.90→0.09로 바뀌어 프리뷰에 그대로 나갔다 —
    prior 분기가 price·이력만 옮기고 change_pct는 FDR 옛 행 값을 남겼기 때문이다.
    """

    def test_change_pct_and_source_come_from_the_prior_file(self) -> None:
        today = fetch_kr.dt.date.today().isoformat()
        stale = {"ticker": "KS11", "price": 7017.91, "change_pct": 0.09, "trading_date": "2026-09-22",
                 "series": [7007.72, 7017.91], "history": {"dates": ["2026-09-21", "2026-09-22"], "close": [7007.72, 7017.91]},
                 "data_source": "FinanceDataReader"}
        prior = {"ticker": "KS11", "price": 7080.92, "change_pct": 0.9, "trading_date": "2026-09-23",
                 "series": [7007.72, 7017.91, 7080.92],
                 "history": {"dates": ["2026-09-21", "2026-09-22", "2026-09-23"], "close": [7007.72, 7017.91, 7080.92]},
                 "data_source": "Naver Finance realtime index"}
        holiday = {"nv": 708092, "cv": 6301, "cr": 0.9, "ms": "CLOSE"}   # 휴장일: 어제 값 그대로 — 등식이 안 맞아 오늘 행을 안 만든다
        if prior["trading_date"] >= today:
            self.skipTest("오늘이 2026-09-23 이전이면 이 시나리오가 성립하지 않습니다")
        result = fetch_kr._apply_final_index_quote(stale, "KS11", holiday, prior=prior)
        self.assertEqual(result["trading_date"], "2026-09-23")
        self.assertEqual(result["change_pct"], 0.9)                 # 0.09가 남으면 안 된다
        self.assertEqual(result["data_source"], "Naver Finance realtime index")

    def test_change_pct_is_derived_from_history_when_the_prior_lacks_it(self) -> None:
        prior = {"price": 844.48, "trading_date": "2026-09-23", "history": {"dates": ["a", "b"], "close": [834.38, 844.48]}}
        self.assertEqual(fetch_kr._prior_change_pct(prior), 1.21)
        self.assertIsNone(fetch_kr._prior_change_pct({"price": 1.0, "trading_date": "x", "history": {"close": [1.0]}}))

