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



class KrxCloseForStocksTest(unittest.TestCase):
    """종목 가격·등락률은 KRX 정규장 확정 종가(네이버 폴링 nv/cr/pcv)로 쓴다(2026-09-25).

    16:20~16:40에 세 번 받은 9/23 일봉은 27종목 중 14종목이 서로 달랐고(NXT 애프터마켓이 20:00까지 움직인다),
    발행된 삼성전자 등락률 2.70%는 KRX 기준 3.62%도 NXT 확정 3.24%도 아니었다.
    """
    TODAY = fetch_kr.dt.date.today().isoformat()

    def _entry(self, date=None):
        return {"ticker": "005930", "name": "삼성전자", "price": 285000.0, "change_pct": 2.7, "trading_date": date or self.TODAY,
                "series": [277500.0, 285000.0], "history": {"dates": ["2026-09-22", self.TODAY], "close": [277500.0, 285000.0]},
                "source": "core"}

    def test_close_and_change_come_from_the_polling_quote(self) -> None:
        quote = {"cd": "005930", "nv": 286500, "cv": 10000, "cr": 3.62, "pcv": 276500, "ms": "CLOSE"}
        out = fetch_kr._apply_krx_close(self._entry(), quote, self.TODAY)
        self.assertEqual(out["price"], 286500.0)
        self.assertEqual(out["change_pct"], 3.62)
        self.assertEqual(out["prev_close_krx"], 276500.0)
        self.assertEqual(out["series"][-1], 286500.0)
        self.assertEqual(out["history"]["close"][-1], 286500.0)
        self.assertIn("KRX", out["data_source"])

    def test_polling_cr_is_unsigned_so_the_sign_comes_from_the_prices(self) -> None:
        """KB금융 9/23 실제 응답: nv 174,100 · pcv 175,700 · cr 0.91 · rf '5'(하락) — cr을 그대로 쓰면 +0.91%가 된다."""
        entry = {**self._entry(), "ticker": "105560", "price": 174100.0, "series": [175700.0, 174100.0],
                 "history": {"dates": ["2026-09-22", self.TODAY], "close": [175700.0, 174100.0]}}
        out = fetch_kr._apply_krx_close(entry, {"nv": 174100, "cv": 1600, "cr": 0.91, "pcv": 175700, "ms": "CLOSE", "rf": "5"}, self.TODAY)
        self.assertEqual(out["change_pct"], -0.91)
        with self.assertRaises(ValueError):   # cr 크기가 계산값과 다르면 응답 형식이 바뀐 것
            fetch_kr._apply_krx_close(entry, {"nv": 174100, "cr": 5.0, "pcv": 175700, "ms": "CLOSE"}, self.TODAY)

    def test_change_is_against_the_adjusted_base_price(self):
        """2026-10-02 삼성바이오로직스 실제 사진: 기준가(sv)가 전일 종가(pcv)와 다른 날 — 거래소 등락률은 기준가 대비 −4.51%."""
        entry = {**self._entry(), "ticker": "207940", "price": 1354000}
        quote = {"cr": 4.51, "cv": 64000, "ms": "CLOSE", "nv": 1354000, "pcv": 1429000, "rf": "5", "sv": 1418000}
        out = fetch_kr._apply_krx_close(entry, quote, self.TODAY)
        self.assertEqual(out["change_pct"], -4.51)
        self.assertEqual(out["prev_close_krx"], 1418000)

    def test_without_sv_the_previous_close_is_the_base(self):
        out = fetch_kr._apply_krx_close(self._entry(), {"nv": 286500, "cr": 3.62, "pcv": 276500, "ms": "CLOSE"}, self.TODAY)
        self.assertEqual(out["change_pct"], 3.62)

    def test_not_today_is_left_alone(self) -> None:
        entry = self._entry(date="2026-09-23")
        self.assertEqual(fetch_kr._apply_krx_close(entry, None, self.TODAY), entry)

    def test_snapshot_is_never_published_as_a_close(self) -> None:
        with self.assertRaises(ValueError):
            fetch_kr._apply_krx_close(self._entry(), {"nv": 285000, "cr": 2.7, "pcv": 276500, "ms": "OPEN"}, self.TODAY)
        with self.assertRaises(ValueError):
            fetch_kr._apply_krx_close(self._entry(), None, self.TODAY)

    def test_wildly_different_quote_means_a_wrong_code(self) -> None:
        with self.assertRaises(ValueError):
            fetch_kr._apply_krx_close(self._entry(), {"nv": 100000, "cr": 1.0, "pcv": 99000, "ms": "CLOSE"}, self.TODAY)

    def test_core_failure_stops_and_dynamic_failure_drops(self) -> None:
        from unittest.mock import patch
        wl = {"005930": self._entry(), "999999": {**self._entry(), "ticker": "999999", "name": "편입", "source": "dynamic"}}
        quotes = {"005930": {"nv": 286500, "cr": 3.62, "pcv": 276500, "ms": "CLOSE"}}
        # 저장소의 실제 사진(data/krx_close/<오늘>.json)을 읽지 않게 — 사진이 커밋된 날에만 실패했다(2026-09-30)
        nosnap = patch.object(fetch_kr, "_krx_close_snapshot", return_value={})
        nosnap.start(); self.addCleanup(nosnap.stop)
        with patch.object(fetch_kr, "_fetch_naver_item_quotes", return_value=quotes):
            out = fetch_kr._apply_krx_closes(wl, self.TODAY)
        self.assertEqual(set(out), {"005930"})                        # 편입 종목은 조용히 빠진다
        with patch.object(fetch_kr, "_fetch_naver_item_quotes", return_value={}):
            with self.assertRaises(ValueError):
                fetch_kr._apply_krx_closes({"005930": self._entry()}, self.TODAY)   # 코어는 멈춘다
        self.assertEqual(fetch_kr._apply_krx_closes(wl, "2026-09-23"), wl)          # 오늘 거래일이 아니면 그대로


class KrxCloseSnapshotTest(unittest.TestCase):
    """정규장 종가 사진(2026-09-28): 16:00부터 폴링 nv는 시간외 단일가를 따라 움직이고 ms는 넥스트레이드 때문에 OPEN이다."""

    def test_window(self) -> None:
        from scripts import krx_close_snapshot as snap
        kst = snap.KST
        self.assertTrue(snap.in_window(fetch_kr.dt.datetime(2026, 9, 28, 15, 35, tzinfo=kst)))
        self.assertFalse(snap.in_window(fetch_kr.dt.datetime(2026, 9, 28, 16, 0, tzinfo=kst)))     # 시간외 단일가 시작
        self.assertFalse(snap.in_window(fetch_kr.dt.datetime(2026, 9, 28, 15, 29, tzinfo=kst)))    # 정규장 중
        self.assertFalse(snap.in_window(fetch_kr.dt.datetime(2026, 9, 27, 15, 35, tzinfo=kst)))    # 일요일

    def test_snapshot_beats_the_live_quote(self) -> None:
        """카카오 9/28 실제 값: 15:4x 사진 33,950(+1.49%) · 17:40 폴링 34,000(ms OPEN, 시간외 단일가) — 사진을 쓴다."""
        from unittest import mock
        today = fetch_kr.dt.date.today().isoformat()
        entry = {"ticker": "035720", "name": "카카오", "price": 34000.0, "change_pct": 1.64, "trading_date": today,
                 "series": [33450.0, 34000.0], "history": {"dates": ["2026-09-23", today], "close": [33450.0, 34000.0]}, "source": "core"}
        live = {"035720": {"nv": 34000, "pcv": 33450, "cr": 1.64, "ms": "OPEN"}}
        snap = {"035720": {"nv": 33950, "pcv": 33450, "cr": 1.49, "cv": 500, "rf": "2"}}
        with mock.patch.object(fetch_kr, "_fetch_naver_item_quotes", return_value=live), \
                mock.patch.object(fetch_kr, "_krx_close_snapshot", return_value=snap):
            out = fetch_kr._apply_krx_closes({"035720": entry}, today)
        self.assertEqual(out["035720"]["price"], 33950.0)
        self.assertEqual(out["035720"]["change_pct"], 1.49)

    def test_without_snapshot_an_open_quote_still_stops(self) -> None:
        from unittest import mock
        today = fetch_kr.dt.date.today().isoformat()
        entry = {"ticker": "035720", "name": "카카오", "price": 34000.0, "trading_date": today, "source": "core",
                 "series": [34000.0], "history": {"dates": [today], "close": [34000.0]}}
        with mock.patch.object(fetch_kr, "_fetch_naver_item_quotes", return_value={"035720": {"nv": 34000, "pcv": 33450, "cr": 1.64, "ms": "OPEN"}}), \
                mock.patch.object(fetch_kr, "_krx_close_snapshot", return_value={}):
            with self.assertRaises(ValueError):
                fetch_kr._apply_krx_closes({"035720": entry}, today)


class IndexGapFillTest(unittest.TestCase):
    """2026-09-30: 9/28·9/29를 건너뛰어 지수 마지막이 9/23 — 네이버 일별 목록으로 빈 날을 채운다."""
    DAILY = [("2026-09-23", 7080.92), ("2026-09-28", 6889.74), ("2026-09-29", 6870.81), ("2026-09-30", 6838.04)]
    ENTRY = {"trading_date": "2026-09-23", "price": 7080.92, "series": [7000.0, 7080.92],
             "history": {"dates": ["2026-09-22", "2026-09-23"], "close": [7000.0, 7080.92]}}

    def test_fills_missing_days_when_equation_holds(self) -> None:
        out = fetch_kr._fill_gap_from_naver_daily(self.ENTRY, "KOSPI", "2026-09-30", 6838.04, -32.77, self.DAILY)
        self.assertEqual(out["trading_date"], "2026-09-30")
        self.assertEqual(out["history"]["dates"][-4:], ["2026-09-23", "2026-09-28", "2026-09-29", "2026-09-30"])
        self.assertEqual(out["history"]["close"][-1], 6838.04)

    def test_holiday_has_no_today_row(self) -> None:
        daily = self.DAILY[:-1]      # 휴장일 — 목록에 오늘 줄이 없다
        self.assertIsNone(fetch_kr._fill_gap_from_naver_daily(self.ENTRY, "KOSPI", "2026-09-30", 6870.81, -18.93, daily))

    def test_equation_must_hold_against_previous_row(self) -> None:
        self.assertIsNone(fetch_kr._fill_gap_from_naver_daily(self.ENTRY, "KOSPI", "2026-09-30", 6838.04, -10.0, self.DAILY))
