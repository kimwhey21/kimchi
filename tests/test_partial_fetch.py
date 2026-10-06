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
            "change_pct": 1.01, "series": [99.0, 100.0], "unit": "",
            "history": {"dates": ["2026-09-03", date], "close": [99.0, 100.0]},
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
             mock.patch.object(fetch_us, "second_series", side_effect=lambda t, d: {d: 100.0}), \
             mock.patch.object(fetch_us, "naver_future_closes", return_value={"2026-09-03": 99.0, "2026-09-04": 100.0}), \
             mock.patch.object(fetch_us, "cnbc_settle", return_value=None), \
             mock.patch.object(fetch_us, "_fetch_dynamic_tier", return_value={}):
            return fetch_us.fetch_all()

    def test_macro_failure_stops_instead_of_dropping(self) -> None:
        """2026-10-05: 미국장도 빼지 않는다 — 전에는 지수 셋만 필수였고 금·VIX·종목은 빠진 채 글이 나갈 수 있었다."""
        with self.assertRaises(ValueError) as ctx:
            self._run({"GC=F"})
        self.assertIn("국제 금(GC=F)", str(ctx.exception))

    def test_stock_failure_stops_instead_of_dropping(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            self._run({"TSLA"})
        self.assertIn("테슬라(TSLA)", str(ctx.exception))

    def test_official_close_disagreement_stops(self) -> None:
        def fake_one(ticker, name="", **kw):
            return _entry(ticker, name)
        with mock.patch.object(fetch_us, "_fetch_one", side_effect=fake_one), \
             mock.patch.object(fetch_us.yaml, "safe_load", return_value=self.CONFIG), \
             mock.patch.object(fetch_us, "second_series", side_effect=lambda t, d: {d: 101.0 if t == "NVDA" else 100.0}), \
             mock.patch.object(fetch_us, "naver_future_closes", return_value={"2026-09-03": 99.0, "2026-09-04": 100.0}), \
             mock.patch.object(fetch_us, "cnbc_settle", return_value=None), \
             mock.patch.object(fetch_us, "_fetch_dynamic_tier", return_value={}):
            with self.assertRaises(ValueError) as ctx:
                fetch_us.fetch_all()
        self.assertIn("엔비디아(NVDA)", str(ctx.exception))

    def test_sources_are_recorded(self) -> None:
        def fake_one(ticker, name="", **kw):
            return _entry(ticker, name)
        with mock.patch.object(fetch_us, "_fetch_one", side_effect=fake_one), \
             mock.patch.object(fetch_us.yaml, "safe_load", return_value=self.CONFIG), \
             mock.patch.object(fetch_us, "second_series", side_effect=lambda t, d: {} if t.startswith("GC") else {d: 100.0}), \
             mock.patch.object(fetch_us, "naver_future_closes", return_value={"2026-09-03": 99.0, "2026-09-04": 100.0}), \
             mock.patch.object(fetch_us, "cnbc_settle", return_value=None), \
             mock.patch.object(fetch_us, "_fetch_dynamic_tier", return_value={}):
            data = fetch_us.fetch_all()
        self.assertEqual(data["watchlist"]["NVDA"]["close_sources"], ["yahoo", "nasdaq"])
        self.assertEqual(data["macro"]["^DJI"]["close_sources"], ["yahoo", "fred"])
        self.assertEqual(data["macro"]["GC=F"]["close_sources"], ["naver", "yahoo"])   # 금은 결제가 셋 중 둘(2026-10-05)

    def test_required_index_failure_still_raises(self) -> None:
        """지수까지 없으면 그날 글은 성립하지 않습니다."""
        with self.assertRaises(ValueError):
            self._run({"^DJI"})

    def test_all_stocks_failing_raises(self) -> None:
        with self.assertRaises(ValueError):
            self._run({"NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "META",
                       "MU", "INTC", "COIN", "MRNA"})

    def test_every_missing_name_is_listed(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            self._run({"TSLA", "AAPL", "MSFT"})
        for name in ("테슬라(TSLA)", "애플(AAPL)", "마이크로소프트(MSFT)"):
            self.assertIn(name, str(ctx.exception))

    def test_nothing_missing_reports_empty(self) -> None:
        data = self._run(set())
        self.assertEqual(data["missing"], [])
        self.assertEqual(len(data["watchlist"]), 10)


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
             mock.patch.object(fetch_kr, "_fetch_stock", side_effect=fake_one), \
             mock.patch.object(fetch_kr, "_fetch_index", side_effect=fake_one), \
             mock.patch.object(fetch_kr, "_fetch_usdkrw_reference", side_effect=fake_fx), \
             mock.patch.object(fetch_kr, "_fetch_naver_index_quotes", return_value={}), \
             mock.patch.object(fetch_kr, "_apply_final_index_quote",
                               side_effect=lambda entry, *a, **k: entry), \
             mock.patch.object(fetch_kr.yaml, "safe_load", return_value=self.CONFIG), \
             mock.patch.object(fetch_kr, "_fetch_dynamic_tier", return_value={}), \
             mock.patch.object(fetch_kr.fetch_foreign_flows, "attach_foreign_flows",
                               side_effect=lambda w, *a, **k: None):
            return fetch_kr.fetch_all()

    def test_usdkrw_is_retried_then_stops_instead_of_dropping(self) -> None:
        """2026-10-05: 환율도 빼지 않는다 — 네 번(바로·10·30·60초 뒤) 묻고, 그래도 안 되면 이름을 적고 멈춘다."""
        with mock.patch.object(fetch_kr.time, "sleep"):
            with self.assertRaises(ValueError) as ctx:
                self._run({"USD/KRW"})
        self.assertIn("원/달러 환율(USD/KRW)", str(ctx.exception))

    def test_everything_present_reports_nothing_missing(self) -> None:
        data = self._run(set())
        self.assertEqual(data["missing"], [])
        self.assertEqual(len(data["watchlist"]), 10)
        self.assertEqual(data["trading_date"], "2026-09-04")

    def test_one_core_stock_failure_stops_instead_of_dropping(self) -> None:
        """2026-10-05: 한국장 코어는 하나도 빼지 않는다 — 전에는 80%까지 빠져도 글을 냈다. 못 받은 종목 이름을 적고 멈춘다."""
        with self.assertRaises(ValueError) as ctx:
            self._run({"000660"})
        self.assertIn("SK하이닉스(000660)", str(ctx.exception))

    def test_required_index_failure_still_raises(self) -> None:
        with self.assertRaises(ValueError):
            self._run({"KS11"})

    def test_sector_is_carried(self) -> None:
        data = self._run(set())
        self.assertEqual(data["watchlist"]["005930"]["sector"], "반도체")


class KrDynamicTierNoDropTest(unittest.TestCase):
    """2026-10-05: 그날 거래대금 상위(편입 종목)도 빼지 않는다 — 전에는 조회 실패·기준일 차이면 조용히 뺐다."""
    CONFIG = {"dynamic": {"enabled": True, "count": 2}, "name_en_map": {"편입A": "A", "편입B": "B"}}
    MOVERS = [{"ticker": "111111", "name": "편입A", "market": "KOSPI", "trading_value": 10},
              {"ticker": "222222", "name": "편입B", "market": "KOSDAQ", "trading_value": 9}]

    def test_ranking_failure_retries_then_stops(self) -> None:
        with mock.patch.object(fetch_kr.fetch_movers, "fetch_top_turnover", side_effect=RuntimeError("down")) as top, \
                mock.patch.object(fetch_kr.time, "sleep"):
            with self.assertRaises(ValueError):
                fetch_kr._fetch_dynamic_tier(self.CONFIG, {}, "2026-10-06")
        self.assertEqual(top.call_count, 3)

    def test_one_mover_failure_stops(self) -> None:
        def fake(ticker, name="", **kw):
            if ticker == "222222":
                raise ValueError("다음 실패")
            return _entry(ticker, name, "2026-10-05")
        with mock.patch.object(fetch_kr.fetch_movers, "fetch_top_turnover", return_value=self.MOVERS), \
                mock.patch.object(fetch_kr, "_fetch_stock", side_effect=fake):
            with self.assertRaises(ValueError) as ctx:
                fetch_kr._fetch_dynamic_tier(self.CONFIG, {}, "2026-10-06")
        self.assertIn("편입B(222222)", str(ctx.exception))

    def test_a_day_late_daily_list_is_kept_for_the_close_step(self) -> None:
        """다음 일별 시세에 오늘 줄이 아직 없어도 버리지 않는다 — 오늘 값은 _apply_krx_closes가 두 원천으로 덧붙인다."""
        with mock.patch.object(fetch_kr.fetch_movers, "fetch_top_turnover", return_value=self.MOVERS), \
                mock.patch.object(fetch_kr, "_fetch_stock", side_effect=lambda ticker, name="", **kw: _entry(ticker, name, "2026-10-05")):
            added = fetch_kr._fetch_dynamic_tier(self.CONFIG, {}, "2026-10-06")
        self.assertEqual(set(added), {"111111", "222222"})

class UsSecondSourcesTest(unittest.TestCase):
    """금·원유 결제가 셋 중 둘, Cboe 공식 종가(2026-10-05)."""

    def _gold(self, yahoo=4172.1):
        return {"GC=F": {"name": "국제 금", "price": round(yahoo, 2), "change_pct": 0.0, "trading_date": "2026-10-02",
                         "series": [4202.3, yahoo], "history": {"dates": ["2026-10-01", "2026-10-02"], "close": [4202.3, yahoo]}}}

    def test_yahoo_alone_is_replaced_by_the_settlement(self):
        """10/2 실측: 야후 4,172.1(결제 전 값) · 네이버 4,162.3 · CNBC 결제가 4,162.30 → 4,162.3, -0.95%."""
        entries = self._gold()
        with mock.patch.object(fetch_us, "naver_future_closes", return_value={"2026-10-01": 4202.3, "2026-10-02": 4162.3}), \
                mock.patch.object(fetch_us, "cnbc_settle", return_value=("2026-10-02", 4162.3)), mock.patch("builtins.print"):
            self.assertEqual(fetch_us._settle_futures(entries), [])
        e = entries["GC=F"]
        self.assertEqual((e["price"], e["change_pct"], e["series"][-1], e["history"]["close"][-1]), (4162.3, -0.95, 4162.3, 4162.3))
        self.assertEqual(e["close_sources"], ["cnbc_settle", "naver"])

    def test_agreeing_yahoo_is_kept(self):
        entries = self._gold(4162.3)
        with mock.patch.object(fetch_us, "naver_future_closes", return_value={"2026-10-01": 4202.3, "2026-10-02": 4162.3}), \
                mock.patch.object(fetch_us, "cnbc_settle", return_value=None):
            self.assertEqual(fetch_us._settle_futures(entries), [])
        self.assertEqual(entries["GC=F"]["close_sources"], ["naver", "yahoo"])

    def test_no_agreement_is_a_problem(self):
        for naver, cnbc in (({}, None), ({"2026-10-02": 4150.0}, ("2026-10-02", 4160.0))):
            with mock.patch.object(fetch_us, "naver_future_closes", return_value=naver), \
                    mock.patch.object(fetch_us, "cnbc_settle", return_value=cnbc):
                self.assertEqual(len(fetch_us._settle_futures(self._gold())), 1)

    def test_futures_bar_after_the_index_day_is_brought_back(self):
        """미국 휴장일 저녁: 지수 기준일은 금요일인데 야후 선물 마지막 줄이 다음 거래일 장이면 기준일 값으로 맞춘다."""
        entries = {"GC=F": {"ticker": "GC=F", "name": "국제 금", "price": 4450.0, "change_pct": -0.6, "trading_date": "2026-09-08",
                            "series": [4476.6, 4450.0], "history": {"dates": ["2026-09-03", "2026-09-04", "2026-09-08"],
                                                                    "close": [4440.0, 4476.6, 4450.0]}}}
        with mock.patch.object(fetch_us, "naver_future_closes", return_value={"2026-09-03": 4440.0, "2026-09-04": 4476.6}), \
                mock.patch.object(fetch_us, "cnbc_settle", return_value=("2026-09-04", 4476.6)), mock.patch("builtins.print"):
            self.assertEqual(fetch_us._settle_futures(entries, "2026-09-04"), [])
        e = entries["GC=F"]
        self.assertEqual((e["trading_date"], e["price"], e["change_pct"], e["history"]["dates"][-1]), ("2026-09-04", 4476.6, 0.82, "2026-09-04"))
        self.assertEqual(e["close_sources"], ["cnbc_settle", "naver", "yahoo"])

    def test_missing_official_value_stops(self):
        """공식 원천에 그날 값이 없으면 '야후 하나'로 넘기지 않는다(2026-10-05 재검증: 8/28·8/31 알파벳이 그렇게 통과했다)."""
        entry = {"name": "알파벳", "price": 339.13, "change_pct": -2.09, "trading_date": "2026-08-31"}
        with mock.patch.object(fetch_us, "second_series", return_value={}):
            problems = fetch_us._verify_second_source({"GOOGL": entry})
        self.assertEqual(len(problems), 1); self.assertIn("확인하지 못했습니다", problems[0])
        self.assertNotIn("close_sources", entry)

    def test_change_is_checked_against_the_official_previous_close(self):
        """2026-09-23 실측: 야후 이력에 9/22 줄이 빠져 다우 등락률이 9/21 대비(-1.03%)로 나갔다 — 공식은 -0.68%.
        공식 전일 종가를 우리가 그날 커밋한 파일이 확인해 주면 고치고, 아니면 멈춘다."""
        entry = {"name": "다우존스", "price": 51511.59, "change_pct": -1.03, "trading_date": "2026-09-23"}
        series = {"2026-09-21": 52048.83, "2026-09-22": 51862.87, "2026-09-23": 51511.59}
        with mock.patch.object(fetch_us, "_committed_close", return_value=51862.87), mock.patch("builtins.print"):
            self.assertIsNone(fetch_us._check_change("^DJI", entry, series, "2026-09-23"))
        self.assertEqual(entry["change_pct"], -0.68)
        entry["change_pct"] = -1.03
        with mock.patch.object(fetch_us, "_committed_close", return_value=None):
            self.assertIn("등락률", fetch_us._check_change("^DJI", entry, series, "2026-09-23"))

    def test_futures_need_the_previous_settlement_from_two_places(self):
        entries = self._gold(4162.3)
        with mock.patch.object(fetch_us, "naver_future_closes", return_value={"2026-10-01": 4190.0, "2026-10-02": 4162.3}), \
                mock.patch.object(fetch_us, "cnbc_settle", return_value=None):
            self.assertEqual(len(fetch_us._settle_futures(entries)), 1)    # 네이버 전일 4,190 ≠ 야후 이력 4,202.3

    def test_cnbc_fills_the_day_only_after_the_close(self):
        """2026-10-06: 수집 시각엔 Cboe·FRED·나스닥 공식 일별에 그날 줄이 없다 — CNBC의 그날 종가(16:00 ET 이후 시각)로 채운다."""
        def quote(last, when):
            r = mock.Mock(); r.json.return_value = {"FormattedQuoteResult": {"FormattedQuote": [{"last": last, "last_time": when}]}}
            return r
        with mock.patch.object(fetch_us, "_official_series", return_value={"2026-10-02": 7722.72}), \
                mock.patch.object(fetch_us.requests, "get", return_value=quote("7,773.95", "2026-10-05T16:48:30.000-0400")):
            self.assertEqual(fetch_us.second_series("^GSPC", "2026-10-05"), {"2026-10-02": 7722.72, "2026-10-05": 7773.95})
        with mock.patch.object(fetch_us, "_official_series", return_value={"2026-10-02": 7722.72}), \
                mock.patch.object(fetch_us.requests, "get", return_value=quote("7,760.00", "2026-10-05T14:10:00.000-0400")):
            self.assertNotIn("2026-10-05", fetch_us.second_series("^GSPC", "2026-10-05"))   # 장중 값은 쓰지 않는다

    def test_cboe_indexes_go_to_cboe(self):
        with mock.patch.object(fetch_us, "cboe_closes", return_value={"2026-10-02": 5.277}) as cboe:
            self.assertEqual(fetch_us.second_close("^TNX", "2026-10-02"), 5.277)
        cboe.assert_called_once_with("^TNX")
        self.assertIsNone(fetch_us.second_close("GC=F", "2026-10-02"))


if __name__ == "__main__":
    unittest.main()


class UsAuditFixesTest(unittest.TestCase):
    """2026-10-06 감사 F-021·F-046·F-061·F-178."""

    def test_stale_entry_stops_the_collection(self) -> None:
        def fake_one(ticker, name="", **kw):
            return _entry(ticker, name, "2026-09-03" if ticker == "MU" else "2026-09-04")
        cfg = UsPartialFetchTest.CONFIG
        with mock.patch.object(fetch_us, "_fetch_one", side_effect=fake_one), \
             mock.patch.object(fetch_us.yaml, "safe_load", return_value=cfg), \
             mock.patch.object(fetch_us, "second_series", side_effect=lambda t, d: {d: 100.0}), \
             mock.patch.object(fetch_us, "naver_future_closes", return_value={"2026-09-03": 99.0, "2026-09-04": 100.0}), \
             mock.patch.object(fetch_us, "cnbc_settle", return_value=None), \
             mock.patch.object(fetch_us, "_fetch_dynamic_tier", return_value={}), mock.patch("builtins.print"):
            with self.assertRaises(ValueError) as ctx:
                fetch_us.fetch_all()
        self.assertIn("기준일이 2026-09-03", str(ctx.exception))

    def test_official_series_missing_the_previous_session_is_not_used(self) -> None:
        entry = {"name": "다우존스", "price": 51511.59, "change_pct": -0.68, "trading_date": "2026-09-23"}
        series = {"2026-09-21": 52048.83, "2026-09-23": 51511.59}            # 9/22 줄이 빠졌다
        problem = fetch_us._check_change("^DJI", entry, series, "2026-09-23")
        self.assertIn("전 거래일은 2026-09-22", problem)
        self.assertEqual(entry["change_pct"], -0.68)                        # 이틀치로 덮어쓰지 않는다

    def test_previous_session_skips_weekends_and_holidays(self) -> None:
        self.assertEqual(fetch_us.previous_us_session("2026-09-08"), "2026-09-04")   # 노동절 월요일 건너뜀

    def test_bond_holiday_keeps_yields_flat(self) -> None:
        entries = {"^TNX": {"name": "10년물", "price": 5.33, "change_pct": 0.4, "trading_date": "2026-10-12"}}
        with mock.patch.object(fetch_us, "cboe_closes", return_value={"2026-10-09": 5.31}), mock.patch("builtins.print"):
            fetch_us._bond_holiday(entries, "2026-10-12")
        e = entries["^TNX"]
        self.assertEqual((e["price"], e["change_pct"], e["bond_market_closed"]), (5.31, 0.0, True))

    def test_roll_day_uses_the_change_both_sources_agree_on(self) -> None:
        """월물 교체기: 전일 값이 달라도 각자 월물 기준 등락률이 같으면 그 등락률을 쓴다(전에는 미국장 전체가 멈췄다)."""
        entries = {"CL=F": {"name": "WTI", "price": 90.0, "change_pct": 0.0, "trading_date": "2026-10-02",
                            "series": [88.0, 90.0], "history": {"dates": ["2026-10-01", "2026-10-02"], "close": [88.0, 90.0]}}}
        naver = {"2026-10-01": 89.0, "2026-10-02": 91.0227}   # 다른 월물이지만 등락률은 같다(+2.27%)
        with mock.patch.object(fetch_us, "naver_future_closes", return_value=naver), \
                mock.patch.object(fetch_us, "cnbc_settle", return_value=("2026-10-02", 90.0)), mock.patch("builtins.print"):
            self.assertEqual(fetch_us._settle_futures(entries), [])
        self.assertEqual(entries["CL=F"]["change_pct"], 2.27)
