"""외국인·기관 수급은 네이버 증권 JSON(trend)에서 온다 (2026-09-18).

옛 HTML 표(finance.naver.com/item/frgn.naver)가 Npay 증권 자바스크립트 페이지로 302 리다이렉트되어
9/17·9/18 시세 파일의 수급이 전부 비었다(0/27) — 경고만 찍히는 조용한 실패였다. 여기서는 (1) API 한 행을
우리 형식으로 바꾸는 것, (2) 응답이 비면 None, (3) 전 종목이 비면 한 줄로 드러나는 것을 고정한다.
"""
from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr
from unittest import mock

from src import fetch_foreign_flows as f

ROW = {"itemCode": "005930", "bizdate": "20260917", "foreignerPureBuyQuant": "-2,170,687",
       "foreignerHoldRatio": "46.48%", "organPureBuyQuant": "+196,838", "individualPureBuyQuant": "-39,299",
       "closePrice": "256,000"}


class _Resp:
    def __init__(self, payload, status=200):
        self._payload, self.status_code = payload, status
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")
    def json(self):
        return self._payload


class ForeignFlowsTest(unittest.TestCase):
    def test_api_row_becomes_our_shape(self) -> None:
        self.assertEqual(f._parse_row(ROW), {"date": "2026.09.17", "institution_net": 196838,
                                             "foreign_net": -2170687, "foreign_ratio": 46.48})

    def test_fetch_one_uses_the_trend_api(self) -> None:
        with mock.patch.object(f.requests, "get", return_value=_Resp([ROW])) as get:
            self.assertEqual(f.fetch_one("005930")["foreign_net"], -2170687)
        self.assertIn("/api/stock/005930/trend", get.call_args.args[0])

    def test_empty_or_broken_response_is_none_not_zero(self) -> None:
        with mock.patch.object(f.requests, "get", return_value=_Resp([])), redirect_stderr(io.StringIO()):
            self.assertIsNone(f.fetch_one("005930"))
        with mock.patch.object(f.requests, "get", return_value=_Resp("<html>", 200)), redirect_stderr(io.StringIO()):
            self.assertIsNone(f.fetch_one("005930"))

    def test_all_stocks_empty_is_reported_once(self) -> None:
        err = io.StringIO()
        with mock.patch.object(f, "fetch_one", return_value=None), redirect_stderr(err):
            f.attach_foreign_flows({"005930": {}, "000660": {}})
        self.assertIn("한 종목도 받지 못했습니다", err.getvalue())


if __name__ == "__main__":
    unittest.main()
