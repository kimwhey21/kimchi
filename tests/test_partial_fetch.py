"""종목 하나가 실패해도 그날 시세 전체를 버리지 않는지 봅니다.

2026-09-01에 원/달러 하나가 결측(NaN)이라 코스피·코스닥과 종목 27개를 통째로
버렸습니다. 그날 한국장 시황은 나가지 못했습니다. 환율 한 줄을 못 쓰는 것과
그날 시황이 통째로 없는 것은 다른 크기의 손해입니다.

그래서 **필수(지수)만 실패시키고 나머지는 빼고 진행**합니다. 이 파일은 그
경계가 흐트러지지 않는지 확인합니다.
"""
from __future__ import annotations

import unittest
from unittest import mock

from src import fetch_kr, fetch_us


def _entry(ticker: str, name: str, date: str = "2026-09-04") -> dict:
    return {"ticker": ticker, "name": name, "name_en": name, "price": 100.0,
            "change_pct": 1.0, "series": [99.0, 100.0], "unit": "",
            "trading_date": date}


class UsPartialFetchTest(unittest.TestCase):
    CONFIG = {
        "macro": [
            {"ticker": "^DJI", "name": "다우존스"},
            {"ticker": "^GSPC", "name": "S&P500"},
            {"ticker": "^IXIC", "name": "나스닥종합"},
            {"ticker": "GC=F", "name": "국제 금"},
        ],
        # 실제 코어는 16종목입니다. 픽스처가 2개면 하나만 빠져도 50%가 되어
        # 커버리지 하한(80%)과 부딪힙니다.
        "watchlist": [
            {"ticker": t, "name": n} for t, n in (
                ("NVDA", "엔비디아"), ("TSLA", "테슬라"), ("AAPL", "애플"),
                ("MSFT", "마이크로소프트"), ("AMZN", "아마존"), ("META", "메타"),
                ("MU", "마이크론"), ("INTC", "인텔"), ("COIN", "코인베이스"),
                ("MRNA", "모더나"),
            )
        ],
    }

    def _run(self, failing: set[str]):
        def fake_one(ticker, name="", **kw):
            if ticker in failing:
                raise ValueError(f"{ticker}: 시세 데이터에 결측값(NaN)이 있습니다.")
            return _entry(ticker, name)

        with mock.patch.object(fetch_us, "_fetch_one", side_effect=fake_one), \
             mock.patch.object(fetch_us.yaml, "safe_load", return_value=self.CONFIG), \
             mock.patch.object(fetch_us, "_fetch_dynamic_tier", return_value={}):
            return fetch_us.fetch_all()

    def test_optional_macro_failure_is_skipped(self) -> None:
        data = self._run({"GC=F"})
        self.assertNotIn("GC=F", data["macro"])
        self.assertEqual(len(data["watchlist"]), 10)
        self.assertEqual(data["trading_date"], "2026-09-04")
        self.assertTrue(any("GC=F" in m for m in data["missing"]))

    def test_optional_stock_failure_is_skipped(self) -> None:
        data = self._run({"TSLA"})
        self.assertIn("NVDA", data["watchlist"])
        self.assertNotIn("TSLA", data["watchlist"])
        self.assertTrue(any("TSLA" in m for m in data["missing"]))

    def test_required_index_failure_still_raises(self) -> None:
        """지수까지 없으면 그날 글은 성립하지 않습니다."""
        with self.assertRaises(ValueError):
            self._run({"^DJI"})

    def test_all_stocks_failing_raises(self) -> None:
        with self.assertRaises(ValueError):
            self._run({"NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "META",
                       "MU", "INTC", "COIN", "MRNA"})

    def test_core_coverage_floor(self) -> None:
        """빠진 종목이 그날 1위였는지 알 수 없으므로 하한 아래면 쓰지 않습니다.

        editorial_facts는 살아남은 종목 중에서 '그날 1위'를 고릅니다. 여기서
        막지 않으면 자료 장애가 '핵심 종목이 빠진 완성된 글'로 조용히 바뀝니다.
        """
        with self.assertRaises(ValueError) as ctx:
            self._run({"TSLA", "AAPL", "MSFT"})   # 10종목 중 3개 = 70% < 80%
        self.assertIn("코어 종목을", str(ctx.exception))

    def test_nothing_missing_reports_empty(self) -> None:
        data = self._run(set())
        self.assertEqual(data["missing"], [])


class KrPartialFetchTest(unittest.TestCase):
    CONFIG = {
        "macro": [
            {"ticker": "KS11", "name": "코스피"},
            {"ticker": "KQ11", "name": "코스닥"},
            {"ticker": "USD/KRW", "name": "원/달러 환율"},
        ],
        "watchlist": [
            {"ticker": t, "name": n, "sector": sec} for t, n, sec in (
                ("005930", "삼성전자", "반도체"), ("000660", "SK하이닉스", "반도체"),
                ("005490", "POSCO홀딩스", "철강"), ("035420", "네이버", "플랫폼"),
                ("035720", "카카오", "플랫폼"), ("051910", "LG화학", "화학"),
                ("006400", "삼성SDI", "2차전지"), ("105560", "KB금융", "금융"),
                ("055550", "신한지주", "금융"), ("005380", "현대차", "자동차"),
            )
        ],
    }

    def _run(self, failing: set[str]):
        def fake_one(ticker, name="", **kw):
            if ticker in failing:
                raise ValueError(f"{ticker}: 시세 데이터에 결측값(NaN)이 있습니다.")
            return _entry(ticker, name)

        def fake_fx(ticker="USD/KRW", name="", **kw):
            if ticker in failing:
                raise ValueError("USD/KRW: 시세 데이터에 결측값(NaN)이 있습니다.")
            return _entry(ticker, name)

        with mock.patch.object(fetch_kr, "_fetch_one", side_effect=fake_one), \
             mock.patch.object(fetch_kr, "_fetch_usdkrw_reference", side_effect=fake_fx), \
             mock.patch.object(fetch_kr, "_fetch_naver_index_quotes", return_value={}), \
             mock.patch.object(fetch_kr, "_apply_final_index_quote",
                               side_effect=lambda entry, *a, **k: entry), \
             mock.patch.object(fetch_kr.yaml, "safe_load", return_value=self.CONFIG), \
             mock.patch.object(fetch_kr, "_fetch_dynamic_tier", return_value={}), \
             mock.patch.object(fetch_kr.fetch_foreign_flows, "attach_foreign_flows",
                               side_effect=lambda w: None):
            return fetch_kr.fetch_all()

    def test_usdkrw_failure_no_longer_loses_the_day(self) -> None:
        """2026-09-01에 실제로 일어난 일입니다."""
        data = self._run({"USD/KRW"})
        self.assertNotIn("USD/KRW", data["macro"])
        self.assertIn("KS11", data["macro"])
        self.assertEqual(len(data["watchlist"]), 10)
        self.assertEqual(data["trading_date"], "2026-09-04")
        self.assertTrue(any("USD/KRW" in m for m in data["missing"]))

    def test_one_core_stock_failure_is_skipped(self) -> None:
        data = self._run({"000660"})
        self.assertIn("005930", data["watchlist"])
        self.assertNotIn("000660", data["watchlist"])

    def test_required_index_failure_still_raises(self) -> None:
        with self.assertRaises(ValueError):
            self._run({"KS11"})

    def test_sector_survives_partial_failure(self) -> None:
        data = self._run({"USD/KRW"})
        self.assertEqual(data["watchlist"]["005930"]["sector"], "반도체")


if __name__ == "__main__":
    unittest.main()
