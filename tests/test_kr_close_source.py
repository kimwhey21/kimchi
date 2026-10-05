"""코스피·코스닥 원천 교체(2026-10-05)와 지수 대조를 고정합니다.

지수 원천이던 FinanceDataReader KS11/KQ11은 개인 개발자의 깃허브 사본이었고 9/17 낮부터 멈춰 있었다 — 그 사본의 9/17 값은
장중 값(6,724.34, 확정 6,715.41)이었다. 우리는 빈 날을 메워 글을 냈지만 원천이 멈춘 것을 2주 넘게 몰랐고, 발행 점검
(`check_publication`)도 같은 원천으로 "마지막 거래일"을 물어 한국장 수집이 빠진 날을 잡지 못하는 상태였다.
지금은 네이버 지수 일별 목록이 원천이고, `close_check`가 목록의 정체와 ECOS와의 차이를 운영 대화로 알린다.
"""
from __future__ import annotations

import unittest
from unittest import mock

import requests

from src import check_publication, close_check, fetch_kr


def _rows(dates_closes):
    return [{"localTradedAt": d, "closePrice": f"{c:,.2f}"} for d, c in dates_closes]


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class NaverDailyListTest(unittest.TestCase):
    def test_seventy_days_come_in_two_pages_of_35(self) -> None:
        """한 쪽에 70줄은 빈 응답이다(2026-10-05 실측) — 35줄 두 쪽으로 받는다."""
        calls = []

        def fake_get(url, params=None, **kw):
            calls.append(params)
            start = (params["page"] - 1) * params["pageSize"]
            days = [(f"2026-07-{d:02d}", 7000.0 + d) for d in range(1, 31)] + \
                   [(f"2026-08-{d:02d}", 7100.0 + d) for d in range(1, 31)] + \
                   [(f"2026-09-{d:02d}", 7200.0 + d) for d in range(1, 11)]
            newest_first = list(reversed(days))
            return _Resp(_rows(newest_first[start:start + params["pageSize"]]))

        with mock.patch.object(fetch_kr.requests, "get", side_effect=fake_get):
            rows = fetch_kr._fetch_naver_index_daily("KOSPI", rows=70)
        self.assertEqual([c["pageSize"] for c in calls], [35, 35])
        self.assertEqual(len(rows), 70)
        self.assertEqual(rows[0][0], "2026-07-01")      # 오래된 것부터
        self.assertEqual(rows[-1], ("2026-09-10", 7210.0))


class FetchIndexTest(unittest.TestCase):
    ROWS = [("2026-09-16", 6717.97), ("2026-09-17", 6715.41), ("2026-09-18", 6800.0)]

    def test_entry_comes_from_the_naver_list_not_financedatareader(self) -> None:
        with mock.patch.object(fetch_kr, "_fetch_naver_index_daily", return_value=self.ROWS), \
                mock.patch.object(fetch_kr.fdr, "DataReader", side_effect=AssertionError("지수에 FDR을 부르면 안 된다")):
            entry = fetch_kr._fetch_index("KS11", "코스피", "KOSPI")
        self.assertEqual(entry["trading_date"], "2026-09-18")
        self.assertEqual(entry["price"], 6800.0)
        self.assertEqual(entry["change_pct"], 1.26)
        self.assertEqual(entry["history"]["close"][1], 6715.41)    # 확정 종가(그 사본의 장중 값 6,724.34가 아니다)
        self.assertEqual(entry["series"], [6717.97, 6715.41, 6800.0])

    def test_list_failure_falls_back_to_our_committed_file(self) -> None:
        prior = {"ticker": "KS11", "price": 7003.74, "change_pct": 0.46, "trading_date": "2026-10-02",
                 "series": [6971.35, 7003.74], "history": {"dates": ["2026-10-01", "2026-10-02"], "close": [6971.35, 7003.74]}}
        with mock.patch.object(fetch_kr, "_fetch_naver_index_daily", side_effect=requests.ConnectionError("down")), \
                mock.patch.object(fetch_kr, "_latest_committed_index", return_value=prior):
            entry = fetch_kr._fetch_index("KS11", "코스피", "KOSPI")
        self.assertEqual(entry["trading_date"], "2026-10-02")
        self.assertIn("unavailable", entry["data_source"])

    def test_list_failure_without_our_file_stops(self) -> None:
        with mock.patch.object(fetch_kr, "_fetch_naver_index_daily", side_effect=requests.ConnectionError("down")), \
                mock.patch.object(fetch_kr, "_latest_committed_index", return_value=None):
            with self.assertRaises(ValueError):
                fetch_kr._fetch_index("KS11", "코스피", "KOSPI")


class LastClosedTradingDayTest(unittest.TestCase):
    ROWS = [("2026-09-30", 6838.04), ("2026-10-01", 6971.35), ("2026-10-02", 7003.74)]

    def _run(self, rows, quote, today):
        with mock.patch.object(fetch_kr, "_fetch_naver_index_daily", return_value=rows), \
                mock.patch.object(fetch_kr, "_fetch_naver_index_quotes", return_value={"KOSPI": quote}):
            return fetch_kr.last_closed_trading_day(today)

    def test_holiday_returns_the_last_trading_day(self) -> None:
        """2026-10-05(개천절 대체 휴일) 실측: ms=CLOSE, nv는 10/2 종가 그대로, 목록에 10/5 줄 없음."""
        self.assertEqual(self._run(self.ROWS, {"ms": "CLOSE", "nv": 700374}, "2026-10-05"), "2026-10-02")

    def test_after_close_with_todays_row(self) -> None:
        rows = self.ROWS + [("2026-10-06", 7050.0)]
        self.assertEqual(self._run(rows, {"ms": "CLOSE", "nv": 705000}, "2026-10-06"), "2026-10-06")

    def test_after_close_before_the_list_has_today(self) -> None:
        self.assertEqual(self._run(self.ROWS, {"ms": "CLOSE", "nv": 705000}, "2026-10-06"), "2026-10-06")

    def test_during_the_session_today_does_not_count(self) -> None:
        """10:00 KST 점검 — 장중에는 오늘을 거래일로 치지 않는다(헛경보 방지)."""
        rows = self.ROWS + [("2026-10-06", 7020.0)]
        self.assertEqual(self._run(rows, {"ms": "OPEN", "nv": 702000}, "2026-10-06"), "2026-10-02")

    def test_publication_check_asks_naver_for_korea(self) -> None:
        with mock.patch.object(fetch_kr, "last_closed_trading_day", return_value="2026-10-02") as last:
            self.assertEqual(check_publication._actual_trading_date("kr"), "2026-10-02")
        last.assert_called_once()


class IndexCheckTest(unittest.TestCase):
    HISTORY = {"2026-09-16": 6717.97, "2026-09-17": 6715.41, "2026-09-18": 6800.0,
               "2026-09-21": 6810.0, "2026-09-22": 6820.0}

    def test_frozen_naver_list_is_reported(self) -> None:
        """그 사본처럼 목록이 멈추면 알린다 — 그날 줄이 아직 없는 하루 늦음은 봐준다."""
        frozen = [("2026-09-16", 6717.97), ("2026-09-17", 6715.41)]
        self.assertTrue(close_check.naver_lag_issues("KS11", self.HISTORY, frozen))
        one_day_late = [(d, c) for d, c in self.HISTORY.items() if d < "2026-09-22"]
        self.assertEqual(close_check.naver_lag_issues("KS11", self.HISTORY, one_day_late), [])

    def test_ecos_mismatch_is_reported(self) -> None:
        """2026-10-05: 우리 10/2 파일 이력의 9/17이 그 사본의 장중 값이었다."""
        ours = {**self.HISTORY, "2026-09-17": 6724.34}
        issues = close_check.ecos_issues("KS11", ours, dict(self.HISTORY))
        self.assertEqual(len(issues), 1)
        self.assertIn("2026-09-17", issues[0])
        self.assertEqual(close_check.ecos_issues("KS11", self.HISTORY, dict(self.HISTORY)), [])

    def test_ecos_one_day_behind_is_fine_but_a_frozen_ecos_is_reported(self) -> None:
        behind_one = {d: c for d, c in self.HISTORY.items() if d < "2026-09-22"}
        self.assertEqual(close_check.ecos_issues("KS11", self.HISTORY, behind_one), [])
        frozen = {"2026-09-16": 6717.97}
        self.assertTrue(any("멈춰" in i for i in close_check.ecos_issues("KS11", self.HISTORY, frozen)))

    def test_ecos_no_data_is_empty_but_other_errors_raise(self) -> None:
        with mock.patch.object(close_check.requests, "get",
                               return_value=_Resp({"RESULT": {"CODE": "INFO-200", "MESSAGE": "해당하는 데이터가 없습니다."}})):
            self.assertEqual(close_check.ecos_rows("k", "KS11", "2026-10-05", "2026-10-05"), {})
        with mock.patch.object(close_check.requests, "get",
                               return_value=_Resp({"RESULT": {"CODE": "INFO-100", "MESSAGE": "인증키가 유효하지 않습니다."}})):
            with self.assertRaises(ValueError):
                close_check.ecos_rows("k", "KS11", "2026-10-05", "2026-10-05")

    def test_issues_go_to_the_ops_chat_and_never_to_a_real_telegram(self) -> None:
        sent = []
        with mock.patch.dict("os.environ", {"ECOS_API_KEY": "k"}), \
                mock.patch.object(close_check, "check", return_value=["KOSPI: 지수 이력이 ECOS와 다릅니다"]), \
                mock.patch.object(close_check, "check_stocks", return_value=[]), \
                mock.patch.object(close_check, "latest_price_file") as latest, \
                mock.patch.object(close_check.alert, "send", side_effect=lambda m, level="info": sent.append((level, m))):
            latest.return_value.read_text.return_value = "{}"
            latest.return_value.name = "price_kr_2026-10-06.json"
            self.assertEqual(close_check.main([]), 1)
        self.assertEqual(sent[0][0], "warn")
        self.assertIn("ECOS와 다릅니다", sent[0][1])

    def test_missing_key_is_reported_not_swallowed(self) -> None:
        sent = []
        with mock.patch.dict("os.environ", {"ECOS_API_KEY": ""}), \
                mock.patch.object(close_check.alert, "send", side_effect=lambda m, level="info": sent.append(m)):
            with self.assertRaises(RuntimeError):
                close_check.main([])
        self.assertIn("ECOS_API_KEY", sent[0])


class StockNextMorningTest(unittest.TestCase):
    DOC = {"trading_date": "2026-10-02", "missing": [],
           "watchlist": {"000660": {"name": "SK하이닉스", "price": 1841000.0, "prev_close_krx": 1833000.0},
                         "207940": {"name": "삼성바이오로직스", "price": 1354000.0, "prev_close_krx": 1418000.0}}}

    def test_matches_next_days_previous_close(self) -> None:
        quotes = {"000660": {"pcv": 1841000}, "207940": {"pcv": 1354000}}
        self.assertEqual(close_check.stock_issues(self.DOC, quotes), [])

    def test_combined_price_would_be_caught(self) -> None:
        """10/2 SK하이닉스 통합 종가 1,842,000(넥스트레이드 포함)이 파일에 들어갔다면 잡힌다."""
        doc = {**self.DOC, "watchlist": {"000660": {"name": "SK하이닉스", "price": 1842000.0, "prev_close_krx": 1833000.0}}}
        issues = close_check.stock_issues(doc, {"000660": {"pcv": 1841000}})
        self.assertEqual(len(issues), 1)
        self.assertIn("1,842,000", issues[0])

    def test_unverified_and_unanswered_are_reported(self) -> None:
        doc = {**self.DOC, "watchlist": {"000660": {"name": "SK하이닉스", "price": 1841000.0, "data_source": "FDR"}}}
        issues = close_check.stock_issues(doc, {})
        self.assertEqual(len(issues), 2)

    def test_pcv_points_to_the_day_before_the_last_session(self) -> None:
        """10/5(휴장) 실측: 목록 끝 10/2, 실시간 확정값도 10/2 → pcv는 10/1 종가."""
        rows = [("2026-09-30", 6838.04), ("2026-10-01", 6971.35), ("2026-10-02", 7003.74)]
        with mock.patch.object(close_check.fetch_kr, "_fetch_naver_index_daily", return_value=rows), \
                mock.patch.object(close_check.fetch_kr, "_fetch_naver_index_quotes", return_value={"KOSPI": {"nv": 700374}}):
            self.assertEqual(close_check.pcv_day(), "2026-10-01")
        with mock.patch.object(close_check.fetch_kr, "_fetch_naver_index_daily", return_value=rows), \
                mock.patch.object(close_check.fetch_kr, "_fetch_naver_index_quotes", return_value={"KOSPI": {"nv": 705000}}):
            self.assertIsNone(close_check.pcv_day())   # 목록이 마지막 장을 아직 안 실었다 — 어느 날인지 모른다

    def test_check_stocks_reads_that_days_file(self) -> None:
        import json, tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "data").mkdir()
            (Path(tmp) / "data" / "price_kr_2026-10-01.json").write_text(json.dumps(self.DOC), encoding="utf-8")
            with mock.patch.object(close_check, "pcv_day", return_value="2026-10-01"), \
                    mock.patch.object(close_check.fetch_kr, "_fetch_naver_item_quotes",
                                      return_value={"000660": {"pcv": 1841000}, "207940": {"pcv": 1350000}}):
                issues = close_check.check_stocks(Path(tmp))
            self.assertEqual(len(issues), 1)
            self.assertTrue(issues[0].startswith("[2026-10-01] 삼성바이오로직스"))
            with mock.patch.object(close_check, "pcv_day", return_value="2026-10-02"):
                self.assertIn("파일이 없어", close_check.check_stocks(Path(tmp))[0])

    def test_missing_items_are_reported(self) -> None:
        issues = close_check.check({"trading_date": "2026-10-02", "missing": ["원/달러 환율(USD/KRW)"], "macro": {}}, "k")
        self.assertTrue(issues[0].startswith("빠진 항목"))


class WorkflowRunsTheCheckOnceTest(unittest.TestCase):
    def test_check_runs_in_the_morning_watchdog_and_cannot_block(self) -> None:
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent / ".github/workflows"
        text = (root / "publish_check.yml").read_text(encoding="utf-8")
        at = text.index("python -m src.close_check")
        step = text[at - 900:at + 300]
        self.assertIn("continue-on-error: true", step)
        self.assertIn("-ge 12", step)
        self.assertIn("ECOS_API_KEY", step)
        self.assertNotIn("close_check", (root / "market_brief.yml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
