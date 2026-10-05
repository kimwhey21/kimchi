import unittest
from unittest import mock
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
        ), patch.object(fetch_kr, "_daum_fx", return_value=None):
            result = fetch_kr._fetch_usdkrw_reference(
                "USD/KRW", "원/달러 환율", name_en="USD/KRW", unit="원"
            )

        self.assertEqual(result["price"], 1373.3)
        self.assertEqual(result["change_pct"], 0.28)
        self.assertEqual(result["series"], [1381.0, 1369.5, 1373.3])
        self.assertEqual(result["as_of_label"], "16:25 하나은행 고시")
        self.assertEqual(result["reference_label_en"], "2026-09-01 16:25 Hana Bank notice")
        self.assertEqual(result["quote_type"], "reference_rate")


class UsdKrwSecondSourceTest(unittest.TestCase):
    """원/달러 두 번째 원천(2026-10-05): 다음 금융의 같은 하나은행 고시(회차 번호)."""
    KST = fetch_kr.KST

    def _run(self, detail_count, detail_price, rows, daum):
        detail = MagicMock(); detail.json.return_value = {"exchangeInfo": {
            "priceDataType": "NOTICE_ROUND", "localTradedAt": "2026-10-06T15:31:00+09:00", "closePrice": detail_price,
            "fluctuationsRatio": "-1.03", "degreeCount": detail_count}}
        prices = MagicMock(); prices.json.return_value = rows
        with patch.object(fetch_kr.requests, "get", side_effect=[detail, prices]), \
                patch.object(fetch_kr, "_daum_fx", return_value=daum), patch("builtins.print"):
            return fetch_kr._fetch_usdkrw_reference("USD/KRW", "원/달러 환율", name_en="USD/KRW", unit="원")

    ROWS = [{"localTradedAt": "2026-10-06T16:18:00+09:00", "closePrice": "1,346.50"},
            {"localTradedAt": "2026-10-05T21:30:00+09:00", "closePrice": "1,359.50"},
            {"localTradedAt": "2026-10-02T21:30:00+09:00", "closePrice": "1,358.00"}]

    def test_same_notice_agrees_and_keeps_the_naver_notice_time(self):
        """다음의 날짜 칸은 영업일 기준이다(10/5 휴장일 새 고시도 '10/2 21:30') — 고시 시각은 네이버 상세 것."""
        stale = fetch_kr.dt.datetime(2026, 10, 2, 21, 30, tzinfo=self.KST)
        got = self._run(2672, "1,345.50", self.ROWS, (2672, stale, 1345.5))
        self.assertEqual((got["price"], got["close_sources"], got["as_of_label"]), (1345.5, ["daum", "naver"], "15:31 하나은행 고시"))

    def test_different_notices_are_asked_again(self):
        """회차나 값이 다르면 예외 — _retry가 다시 묻는다(어느 고시의 시각인지 댈 수 없는 값은 쓰지 않는다)."""
        when = fetch_kr.dt.datetime(2026, 10, 2, 21, 30, tzinfo=self.KST)
        for daum in ((2665, when, 1346.5), (2663, when, 1347.0)):
            with self.assertRaises(ValueError):
                self._run(2663, "1,345.50", self.ROWS, daum)

    def test_daum_down_is_naver_only_and_tagged(self):
        got = self._run(2665, "1,346.50", self.ROWS, None)
        self.assertEqual(got["close_sources"], ["naver"])


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



class _YahooAgrees(float):
    """시험용: 야후가 '하나 남은 원천'과 같은 값을 준 것으로 친다(어떤 값과 빼도 0)."""
    def __sub__(self, other): return 0.0
    def __rsub__(self, other): return 0.0


def _agreeing_yahoo(test: unittest.TestCase) -> None:
    patcher = patch.object(fetch_kr, "yahoo_close", return_value=_YahooAgrees(0))
    patcher.start()
    test.addCleanup(patcher.stop)


class KrxCloseForStocksTest(unittest.TestCase):
    """종목 가격·등락률은 KRX 정규장 확정 종가 — 네이버 사진과 다음, 두 원천이 같아야 쓴다(2026-10-05).

    16:20~16:40에 세 번 받은 9/23 일봉은 27종목 중 14종목이 서로 달랐고(NXT 애프터마켓이 20:00까지 움직인다),
    발행된 삼성전자 등락률 2.70%는 KRX 기준 3.62%도 NXT 확정 3.24%도 아니었다. 2026-10-05부터는 못 받은 종목을 빼지 않는다.
    """
    TODAY = fetch_kr.dt.date.today().isoformat()

    def setUp(self) -> None:   # 원천이 하나만 남은 경우 야후가 같은 값을 준다고 친다(2026-10-06부터 야후 확인이 필요하다)
        _agreeing_yahoo(self)

    def _entry(self, date=None):
        return {"ticker": "005930", "name": "삼성전자", "price": 285000.0, "change_pct": 2.7, "trading_date": date or self.TODAY,
                "series": [277500.0, 285000.0], "history": {"dates": ["2026-09-22", self.TODAY], "close": [277500.0, 285000.0]},
                "source": "core"}

    def _daum(self, close, base, date=None):
        return {"date": date or self.TODAY, "close": close, "base": base}

    def test_both_sources_agree(self) -> None:
        naver = {"nv": 286500, "cr": 3.62, "pcv": 276500}
        resolved = fetch_kr._resolve_krx_close("005930", self.TODAY, naver, self._daum(286500.0, 276500.0))
        self.assertEqual(resolved["sources"], ["daum", "naver_snapshot"])
        out = fetch_kr._apply_krx_close(self._entry(), resolved, self.TODAY)
        self.assertEqual(out["price"], 286500.0)
        self.assertEqual(out["change_pct"], 3.62)
        self.assertEqual(out["prev_close_krx"], 276500.0)
        self.assertEqual(out["series"][-1], 286500.0)
        self.assertEqual(out["history"]["close"][-1], 286500.0)
        self.assertIn("KRX", out["data_source"])

    def test_sources_disagree_and_yahoo_cannot_tell_stops(self) -> None:
        from unittest.mock import patch
        for third in (None, 285000.0):        # 야후 값이 없거나, 어느 쪽과도 다르면 멈춘다
            with patch.object(fetch_kr, "yahoo_close", return_value=third), self.assertRaises(ValueError) as ctx:
                fetch_kr._resolve_krx_close("005930", self.TODAY, {"nv": 286500, "cr": 3.62, "pcv": 276500},
                                            self._daum(286000.0, 276500.0))
            self.assertIn("두 원천", str(ctx.exception))

    def test_yahoo_breaks_the_tie(self) -> None:
        """2026-10-05 사장님: 옛 값이 아니라 정확한 값 — 셋 중 둘이 같은 값을 쓴다(야후 한국 종가 = KRX 정규장, 10/2 296/296)."""
        from unittest.mock import patch
        with patch.object(fetch_kr, "yahoo_close", return_value=286000.0) as asked, patch("builtins.print"):
            got = fetch_kr._resolve_krx_close("005930", self.TODAY, {"nv": 286500, "cr": 3.62, "pcv": 276500},
                                              self._daum(286000.0, 276500.0))
        asked.assert_called_once_with("005930", self.TODAY)
        self.assertEqual((got["close"], got["base"], got["sources"]), (286000.0, 276500.0, ["daum", "yahoo"]))
        with patch.object(fetch_kr, "yahoo_close", return_value=286500.0), patch("builtins.print"):
            got = fetch_kr._resolve_krx_close("005930", self.TODAY, {"nv": 286500, "cr": 3.62, "pcv": 276500},
                                              self._daum(286000.0, 276500.0))
        self.assertEqual((got["close"], got["sources"]), (286500.0, ["naver_snapshot", "yahoo"]))

    def test_base_only_dispute_on_an_adjusted_day(self) -> None:
        """종가는 같고 기준가만 다른 날(액면병합·배당락): 네이버가 sv 없이 전일 종가(pcv)를 썼으면 다음의 거래소 기준가가 맞다.
        야후에는 묻지 않는다."""
        from unittest.mock import patch
        with patch.object(fetch_kr, "yahoo_close", side_effect=AssertionError("종가가 같으면 묻지 않는다")), patch("builtins.print"):
            got = fetch_kr._resolve_krx_close("084680", self.TODAY, {"nv": 2700, "pcv": 532}, self._daum(2700.0, 2660.0))
        self.assertEqual((got["close"], got["base"]), (2700.0, 2660.0))
        with patch.object(fetch_kr, "yahoo_close", return_value=None), self.assertRaises(ValueError):   # 둘 다 진짜 기준가인데 다르면 멈춘다
            fetch_kr._resolve_krx_close("084680", self.TODAY, {"nv": 2700, "sv": 2650, "pcv": 532}, self._daum(2700.0, 2660.0))

    def test_one_source_needs_yahoo_and_none_stops(self) -> None:
        """2026-10-06: 원천이 하나만 남으면 야후와 맞을 때만 쓴다(두 원천이 된다) — 전에는 하나로 통과했다(감사 F-039)."""
        only_daum = fetch_kr._resolve_krx_close("005930", self.TODAY, None, self._daum(286500.0, 276500.0))
        self.assertEqual(only_daum["sources"], ["daum", "yahoo"])
        only_naver = fetch_kr._resolve_krx_close("005930", self.TODAY, {"nv": 286500, "cr": 3.62, "pcv": 276500},
                                                 self._daum(276500.0, 270000.0, date="2026-01-02"))   # 다음이 옛날 날짜면 안 센다
        self.assertEqual(only_naver["sources"], ["naver_snapshot", "yahoo"])
        with self.assertRaises(ValueError):
            fetch_kr._resolve_krx_close("005930", self.TODAY, None, None)
        for yahoo in (None, 280000.0):        # 야후가 없거나 다르면 쓰지 않는다
            with patch.object(fetch_kr, "yahoo_close", return_value=yahoo), self.assertRaises(ValueError):
                fetch_kr._resolve_krx_close("005930", self.TODAY, None, self._daum(286500.0, 276500.0))

    def test_polling_cr_is_unsigned_so_the_sign_comes_from_the_prices(self) -> None:
        """KB금융 9/23 실제 응답: nv 174,100 · pcv 175,700 · cr 0.91 · rf '5'(하락) — cr을 그대로 쓰면 +0.91%가 된다."""
        entry = {**self._entry(), "ticker": "105560", "price": 174100.0, "series": [175700.0, 174100.0],
                 "history": {"dates": ["2026-09-22", self.TODAY], "close": [175700.0, 174100.0]}}
        resolved = fetch_kr._resolve_krx_close("105560", self.TODAY, {"nv": 174100, "cv": 1600, "cr": 0.91, "pcv": 175700, "rf": "5"}, None)
        self.assertEqual(fetch_kr._apply_krx_close(entry, resolved, self.TODAY)["change_pct"], -0.91)
        with self.assertRaises(ValueError):   # cr 크기가 계산값과 다르면 응답 형식이 바뀐 것
            fetch_kr._resolve_krx_close("105560", self.TODAY, {"nv": 174100, "cr": 5.0, "pcv": 175700}, None)

    def test_change_is_against_the_adjusted_base_price(self):
        """2026-10-02 삼성바이오로직스 실제 값: 기준가가 전일 종가와 다른 날 — 사진(sv 1,418,000)과 다음(basePrice 1,418,000)이 같다."""
        naver = {"cr": 4.51, "cv": 64000, "nv": 1354000, "pcv": 1429000, "rf": "5", "sv": 1418000}
        resolved = fetch_kr._resolve_krx_close("207940", self.TODAY, naver, self._daum(1354000.0, 1418000.0))
        out = fetch_kr._apply_krx_close({**self._entry(), "ticker": "207940"}, resolved, self.TODAY)
        self.assertEqual(out["change_pct"], -4.51)
        self.assertEqual(out["prev_close_krx"], 1418000)

    def test_without_sv_the_previous_close_is_the_base(self):
        resolved = fetch_kr._resolve_krx_close("005930", self.TODAY, {"nv": 286500, "cr": 3.62, "pcv": 276500}, None)
        self.assertEqual(fetch_kr._apply_krx_close(self._entry(), resolved, self.TODAY)["change_pct"], 3.62)

    def test_todays_row_is_appended_when_the_daily_list_is_a_day_late(self) -> None:
        entry = self._entry(date="2026-09-22")
        entry["history"] = {"dates": ["2026-09-21", "2026-09-22"], "close": [270000.0, 276500.0]}
        resolved = fetch_kr._resolve_krx_close("005930", self.TODAY, None, self._daum(286500.0, 276500.0))
        out = fetch_kr._apply_krx_close(entry, resolved, self.TODAY)
        self.assertEqual(out["trading_date"], self.TODAY)
        self.assertEqual(out["history"]["dates"][-1], self.TODAY)
        self.assertEqual(out["history"]["close"][-2:], [276500.0, 286500.0])

    def test_beyond_the_price_limit_means_a_wrong_response(self) -> None:
        with self.assertRaises(ValueError):
            fetch_kr._resolve_krx_close("005930", self.TODAY, None, self._daum(100000.0, 276500.0))

    def _closes(self, wl, snap, daum, prev_day=None):
        from unittest.mock import patch
        with patch.object(fetch_kr, "_krx_close_snapshot", return_value=snap), \
                patch.object(fetch_kr, "_fetch_daum_quote", side_effect=lambda c: daum.get(c) or {"date": "", "close": None, "base": None}), \
                patch.object(fetch_kr, "_fetch_naver_item_quotes", side_effect=AssertionError("창 밖 폴링은 쓰지 않는다")), \
                patch.object(fetch_kr.dt, "datetime", wraps=fetch_kr.dt.datetime) as fake:
            fake.now.return_value = fetch_kr.dt.datetime(2026, 10, 6, 16, 20, tzinfo=fetch_kr.KST)
            return fetch_kr._apply_krx_closes(wl, self.TODAY, prev_day)

    def test_nothing_is_dropped_core_or_dynamic(self) -> None:
        """2026-10-05: 전에는 편입 종목을 조용히 뺐다 — 이제 한 종목이라도 확인하지 못하면 이름을 적고 멈춘다."""
        wl = {"005930": self._entry(), "999999": {**self._entry(), "ticker": "999999", "name": "편입", "source": "dynamic"}}
        snap = {"005930": {"nv": 286500, "cr": 3.62, "pcv": 276500}}
        with self.assertRaises(ValueError) as ctx:
            self._closes(wl, snap, {})
        self.assertIn("편입(999999)", str(ctx.exception))
        both = {**snap, "999999": {"nv": 10000, "cr": 1.0, "pcv": 9900}}
        out = self._closes(wl, both, {"999999": self._daum(10000.0, 9900.0)})
        self.assertEqual(set(out), {"005930", "999999"})
        self.assertEqual(out["999999"]["close_sources"], ["daum", "naver_snapshot"])

    def test_a_stale_daily_list_stops(self) -> None:
        wl = {"005930": self._entry(date="2026-09-18")}
        with self.assertRaises(ValueError) as ctx:
            self._closes(wl, {"005930": {"nv": 286500, "cr": 3.62, "pcv": 276500}}, {}, prev_day="2026-09-22")
        self.assertIn("멈춰", str(ctx.exception))

    def test_not_a_trading_day_is_left_alone(self) -> None:
        wl = {"005930": self._entry(date="2026-09-23")}
        self.assertEqual(fetch_kr._apply_krx_closes(wl, "2026-09-23"), wl)


class KrxCloseSnapshotTest(unittest.TestCase):
    """정규장 종가 사진(2026-09-28): 16:00부터 폴링 nv는 시간외 단일가를 따라 움직이고 ms는 넥스트레이드 때문에 OPEN이다."""

    def setUp(self) -> None:   # 원천이 하나만 남은 경우 야후가 같은 값을 준다고 친다(2026-10-06부터 야후 확인이 필요하다)
        _agreeing_yahoo(self)

    def test_window(self) -> None:
        from scripts import krx_close_snapshot as snap
        kst = snap.KST
        self.assertTrue(snap.in_window(fetch_kr.dt.datetime(2026, 9, 28, 15, 35, tzinfo=kst)))
        self.assertFalse(snap.in_window(fetch_kr.dt.datetime(2026, 9, 28, 16, 0, tzinfo=kst)))     # 시간외 단일가 시작
        self.assertFalse(snap.in_window(fetch_kr.dt.datetime(2026, 9, 28, 15, 29, tzinfo=kst)))    # 정규장 중
        self.assertFalse(snap.in_window(fetch_kr.dt.datetime(2026, 9, 27, 15, 35, tzinfo=kst)))    # 일요일
        self.assertFalse(snap.in_window(fetch_kr.dt.datetime(2026, 10, 5, 15, 35, tzinfo=kst)))    # 평일 휴장일(대체 휴일)
        self.assertFalse(snap.in_window(fetch_kr.dt.datetime(2026, 11, 19, 15, 35, tzinfo=kst)))   # 수능일 15:35는 장중
        self.assertTrue(snap.in_window(fetch_kr.dt.datetime(2026, 11, 19, 16, 35, tzinfo=kst)))    # 수능일 16:30 마감 뒤

    def test_snapshot_values_were_the_next_days_previous_close(self) -> None:
        """커밋된 사진이 KRX 종가였다는 증거: 9/30·10/1 사진의 nv가 다음 거래일 사진의 pcv(네이버 '전일')와 393건 모두 같았다(2026-10-05)."""
        import json
        from pathlib import Path
        folder = Path(__file__).resolve().parent.parent / "data" / "krx_close"
        a = json.loads((folder / "2026-09-30.json").read_text(encoding="utf-8"))["quotes"]
        b = json.loads((folder / "2026-10-01.json").read_text(encoding="utf-8"))["quotes"]
        common = set(a) & set(b)
        self.assertGreater(len(common), 150)
        self.assertEqual([c for c in common if float(a[c]["nv"]) != float(b[c]["pcv"])], [])

    def test_live_polling_after_four_is_never_a_close(self) -> None:
        """카카오 9/28 실제 값: 17:40 폴링 34,000은 시간외 단일가 — 창 밖에서는 폴링을 아예 묻지 않는다."""
        from unittest import mock
        today = fetch_kr.dt.date.today().isoformat()
        entry = {"ticker": "035720", "name": "카카오", "price": 34000.0, "trading_date": today, "source": "core",
                 "series": [33450.0, 34000.0], "history": {"dates": ["2026-09-23", today], "close": [33450.0, 34000.0]}}
        with mock.patch.object(fetch_kr, "_fetch_naver_item_quotes", side_effect=AssertionError("창 밖 폴링")), \
                mock.patch.object(fetch_kr, "_krx_close_snapshot", return_value={}), \
                mock.patch.object(fetch_kr, "_fetch_daum_quote", return_value={"date": today, "close": 33950.0, "base": 33450.0}), \
                mock.patch.object(fetch_kr.dt, "datetime", wraps=fetch_kr.dt.datetime) as fake:
            fake.now.return_value = fetch_kr.dt.datetime(2026, 9, 28, 17, 40, tzinfo=fetch_kr.KST)
            out = fetch_kr._apply_krx_closes({"035720": entry}, today)
        self.assertEqual(out["035720"]["price"], 33950.0)
        self.assertEqual(out["035720"]["change_pct"], 1.49)

    def test_snapshot_keeps_every_listed_stock_for_the_stock_pages(self) -> None:
        """2026-10-05: 종목 페이지 대조용으로 전 종목 [종가, 기준가]를 `close`에 남긴다. 기준가는 sv(없으면 pcv)."""
        import json, tempfile
        from pathlib import Path
        from scripts import krx_close_snapshot as snap
        quotes = {"005930": {"nv": 276000, "pcv": 276000, "sv": 276000, "cr": 0.0, "ms": "OPEN"},
                  "207940": {"nv": 1354000, "pcv": 1429000, "sv": 1418000, "cr": 4.51, "ms": "OPEN"},
                  "900110": {"nv": 1000, "pcv": 990}}
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(snap, "DIR", Path(tmp)), \
                mock.patch.object(snap, "codes", return_value=["005930"]), \
                mock.patch.object(snap, "all_codes", return_value=["005930", "207940", "900110"]), \
                mock.patch.object(snap.fetch_kr, "_fetch_naver_item_quotes",
                                  side_effect=lambda codes, failed=None: {c: quotes[c] for c in codes if c in quotes}) as got, \
                mock.patch.object(snap.dt, "datetime", wraps=snap.dt.datetime) as fake:
            now = snap.dt.datetime(2026, 10, 6, 15, 32, tzinfo=snap.KST)
            fake.now.return_value = now
            self.assertEqual(snap.main(now), 0)
            doc = json.loads((Path(tmp) / "2026-10-06.json").read_text(encoding="utf-8"))
        self.assertEqual([c[0][0] for c in got.call_args_list], [["005930"], ["207940", "900110"]])   # 코어 먼저, 나머지 따로
        self.assertEqual(set(doc["quotes"]), {"005930"})                       # fetch_kr용은 코어·후보만
        self.assertEqual(doc["close"], {"005930": [276000, 276000], "207940": [1354000, 1418000], "900110": [1000, 990]})

    def test_a_partial_snapshot_is_retaken_but_a_full_one_is_kept(self) -> None:
        import json, tempfile
        from pathlib import Path
        from scripts import krx_close_snapshot as snap
        now = snap.dt.datetime(2026, 10, 6, 15, 40, tzinfo=snap.KST)
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(snap, "DIR", Path(tmp)), mock.patch.object(snap, "FULL_MARKET", 2), \
                mock.patch.object(snap, "codes", return_value=["005930"]), \
                mock.patch.object(snap, "all_codes", return_value=["005930", "000660"]), \
                mock.patch.object(snap.fetch_kr, "_fetch_naver_item_quotes",
                                  side_effect=lambda codes, failed=None: {c: {"005930": {"nv": 1, "pcv": 1}, "000660": {"nv": 2, "pcv": 2}}[c]
                                                                          for c in codes}) as got, \
                mock.patch.object(snap.dt, "datetime", wraps=snap.dt.datetime) as fake:
            fake.now.return_value = now
            (Path(tmp) / "2026-10-06.json").write_text(json.dumps({"quotes": {}, "close": {"005930": [1, 1]}}), encoding="utf-8")
            snap.main(now)                                    # 앞 사진은 전 종목이 모자랐다 — 다시 찍는다
            self.assertEqual(len(json.loads((Path(tmp) / "2026-10-06.json").read_text())["close"]), 2)
            snap.main(now)                                    # 이제 충분하다 — 묻지도 않는다
        self.assertEqual(got.call_count, 2)                   # 첫 실행의 코어·나머지 두 번뿐

    def test_a_failed_chunk_keeps_the_core_snapshot(self) -> None:
        """2026-10-06: 전 종목 묶음 하나가 끝내 실패해도 코어 사진은 남기고 실패 종목을 센다(전에는 통째로 사라졌다)."""
        import json, tempfile
        from pathlib import Path
        from scripts import krx_close_snapshot as snap
        calls = []

        def fake_get(url, params=None, **kw):
            codes = params["query"].split(":")[1].split(",")
            calls.append(codes)
            if "000660" in codes:
                raise fetch_kr.requests.ConnectionError("막힘")
            r = mock.Mock(); r.raise_for_status = lambda: None
            r.json.return_value = {"result": {"areas": [{"datas": [{"cd": c, "nv": 100, "pcv": 99} for c in codes]}]}}
            return r
        now = snap.dt.datetime(2026, 10, 6, 15, 35, tzinfo=snap.KST)
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(snap, "DIR", Path(tmp)), mock.patch.object(snap, "codes", return_value=["005930"]), \
                mock.patch.object(snap, "all_codes", return_value=["005930", "000660"]), \
                mock.patch.object(fetch_kr.requests, "get", side_effect=fake_get), mock.patch.object(fetch_kr.time, "sleep"), \
                mock.patch.object(snap.dt, "datetime", wraps=snap.dt.datetime) as fake, mock.patch("builtins.print"):
            fake.now.return_value = now
            self.assertEqual(snap.main(now), 0)
            doc = json.loads((Path(tmp) / "2026-10-06.json").read_text(encoding="utf-8"))
        self.assertIn("005930", doc["quotes"])
        self.assertNotIn("000660", doc["close"])


class DaumSourceTest(unittest.TestCase):
    def test_days_are_parsed_oldest_first(self) -> None:
        body = {"data": [{"date": "2026-10-02 00:00:00", "tradePrice": 1841000.0},
                         {"date": "2026-10-01 00:00:00", "tradePrice": 1833000.0}]}
        with patch.object(fetch_kr, "_daum_get", return_value=body):
            self.assertEqual(fetch_kr._fetch_daum_days("000660"), [("2026-10-01", 1833000.0), ("2026-10-02", 1841000.0)])

    def test_quote_uses_the_regular_session_price_not_the_trade_price(self) -> None:
        """10/2 SK하이닉스: tradePrice 1,842,000(넥스트레이드 포함) · regularTradePrice 1,841,000(KRX 사진과 같음)."""
        body = {"date": "2026-10-02", "tradePrice": 1842000.0, "regularTradePrice": 1841000.0, "basePrice": 1833000.0}
        with patch.object(fetch_kr, "_daum_get", return_value=body):
            self.assertEqual(fetch_kr._fetch_daum_quote("000660"), {"date": "2026-10-02", "close": 1841000.0, "base": 1833000.0})

    def test_daum_retries_then_raises(self) -> None:
        with patch.object(fetch_kr.requests, "get", side_effect=fetch_kr.requests.ConnectionError("x")) as get, \
                patch.object(fetch_kr.time, "sleep"):
            with self.assertRaises(ValueError):
                fetch_kr._fetch_daum_days("000660")
        self.assertEqual(get.call_count, 4)

    def test_daum_outage_falls_back_without_dropping(self) -> None:
        """다음이 막힌 날: 이력은 야후의 조정하지 않은 일별 종가(KRX 정규장)로(표시를 남긴다), 다음은 한 번만 기다린다.
        2026-10-06부터 FinanceDataReader(넥스트레이드 합산)로 채우지 않는다. 야후도 안 되면 멈춘다."""
        fetch_kr._daum_down.clear()
        rows = [("2026-10-05", 276500.0), ("2026-10-06", 286500.0)]
        try:
            with patch.object(fetch_kr.requests, "get", side_effect=fetch_kr.requests.ConnectionError("down")) as get, \
                    patch.object(fetch_kr.time, "sleep"), patch.object(fetch_kr, "_fetch_yahoo_days", return_value=rows), \
                    patch.object(fetch_kr.fdr, "DataReader", side_effect=AssertionError("합산값 원천은 쓰지 않는다")), patch("builtins.print"):
                a = fetch_kr._fetch_stock("005930", "삼성전자")
                b = fetch_kr._fetch_stock("000660", "SK하이닉스")
            self.assertEqual(get.call_count, 4)                     # 첫 종목에서만 네 번 묻고, 그 뒤로는 묻지 않는다
            self.assertIn("Yahoo", a["history_source"]); self.assertIn("Daum unavailable", b["history_source"])
            self.assertEqual((a["price"], a["trading_date"]), (286500.0, "2026-10-06"))
            with patch.object(fetch_kr, "_fetch_yahoo_days", return_value=[]), self.assertRaises(ValueError):
                fetch_kr._fetch_stock("005930", "삼성전자")
        finally:
            fetch_kr._daum_down.clear()


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
