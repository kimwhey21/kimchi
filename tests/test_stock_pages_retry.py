"""종목 페이지 저장의 5xx 재시도 (2026-09-14).

카페24 공유 호스팅이 37개 연속 쓰기를 못 견디고 중간에 502를 냈다(실측: microsoft에서 워크플로 실패).
5xx·연결 오류는 기다렸다 다시 하고, 4xx는 우리 잘못이라 바로 올린다.
"""
from __future__ import annotations

import unittest
from unittest import mock

from src import stock_pages


class R:
    def __init__(self, code): self.status_code = code; self.text = "x"
    def json(self): return {}
    def raise_for_status(self): pass


class RetryTest(unittest.TestCase):
    def test_a_502_is_retried_until_it_succeeds(self) -> None:
        seq = [R(502), R(502), R(200)]
        with mock.patch.object(stock_pages.requests, "request", side_effect=seq) as req, \
             mock.patch.object(stock_pages.time, "sleep") as slept:
            got = stock_pages._request("POST", "https://x/wp-json/wp/v2/pages", json={})
        self.assertEqual(got.status_code, 200)
        self.assertEqual(req.call_count, 3)
        self.assertEqual([c.args[0] for c in slept.call_args_list], list(stock_pages.RETRY_WAITS[:2]))

    def test_a_connection_error_is_retried_too(self) -> None:
        err = stock_pages.requests.RequestException("boom")
        with mock.patch.object(stock_pages.requests, "request", side_effect=[err, R(200)]), \
             mock.patch.object(stock_pages.time, "sleep"):
            self.assertEqual(stock_pages._request("GET", "https://x/a").status_code, 200)

    def test_a_404_comes_straight_back_without_waiting(self) -> None:
        with mock.patch.object(stock_pages.requests, "request", return_value=R(404)) as req, \
             mock.patch.object(stock_pages.time, "sleep") as slept:
            self.assertEqual(stock_pages._request("GET", "https://x/a").status_code, 404)
        self.assertEqual(req.call_count, 1); slept.assert_not_called()

    def test_giving_up_returns_the_last_response_so_the_caller_reports_the_code(self) -> None:
        with mock.patch.object(stock_pages.requests, "request", return_value=R(502)), \
             mock.patch.object(stock_pages.time, "sleep"):
            self.assertEqual(stock_pages._request("POST", "https://x/a").status_code, 502)


if __name__ == "__main__":
    unittest.main()
