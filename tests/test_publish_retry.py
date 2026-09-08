"""워드프레스 요청의 5xx 재시도 (2026-09-08).

옛 글 재작성 두 편이 4분 간격으로 발행되던 중 미디어 조회가 503을 받아 한 편의 발행
전체가 죽었다. 잠깐 바쁜 서버에는 몇 초 뒤 한 번 더 묻고, 4xx에는 다시 묻지 않는다.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

import requests

from src import publish_wordpress


class _Response:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class RetryTest(unittest.TestCase):
    def setUp(self) -> None:
        patcher = patch.object(publish_wordpress, "RETRY_BACKOFF_SECONDS", (0, 0))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_503_then_200_returns_the_200(self) -> None:
        with patch.object(publish_wordpress.requests, "get",
                          side_effect=[_Response(503), _Response(200)]) as get:
            response = publish_wordpress._request("get", "https://x/wp-json/wp/v2/media/1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(get.call_count, 2)

    def test_404_is_not_retried(self) -> None:
        with patch.object(publish_wordpress.requests, "get", return_value=_Response(404)) as get:
            response = publish_wordpress._request("get", "https://x")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(get.call_count, 1)

    def test_gives_up_after_the_backoff_and_returns_the_last_answer(self) -> None:
        with patch.object(publish_wordpress.requests, "post", return_value=_Response(503)) as post:
            response = publish_wordpress._request("post", "https://x", json={})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(post.call_count, 3)

    def test_connection_error_is_retried_then_raised(self) -> None:
        with patch.object(publish_wordpress.requests, "get",
                          side_effect=requests.exceptions.ConnectionError("reset")) as get:
            with self.assertRaises(requests.exceptions.ConnectionError):
                publish_wordpress._request("get", "https://x")
        self.assertEqual(get.call_count, 3)


if __name__ == "__main__":
    unittest.main()
