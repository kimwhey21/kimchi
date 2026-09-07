"""카테고리·태그를 이름으로 찾을 때 같은 이름이 둘이면 멈추는지 확인합니다.

2026-09-07까지 fermata.it.kr에는 "Daily" 카테고리가 둘 있었다(121·123 — 123은
Polylang이 켜져 있던 시절 영어 글용으로 생긴 잔재). 발행 코드는 이름으로 검색해
첫 번째를 골랐고, 그래서 영어 시황이 날마다 다른 카테고리에 들어갔는데 아무도
몰랐다. 이제 같은 이름이 둘이면 첫 번째를 고르는 대신 예외로 멈춘다.
"""
from __future__ import annotations

import unittest
from unittest import mock

from src import publish_wordpress
from src.publish_wordpress import WordPressPublishError, _get_or_create_term_id


class _Response:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = ""

    def json(self):
        return self._payload


class TermLookupTest(unittest.TestCase):
    def test_two_terms_with_the_same_name_stop_publishing(self) -> None:
        two = [{"id": 121, "name": "Daily"}, {"id": 123, "name": "Daily"}]
        with mock.patch.object(publish_wordpress.requests, "get", return_value=_Response(two)):
            with self.assertRaises(WordPressPublishError) as ctx:
                _get_or_create_term_id("https://x", ("u", "p"), "categories", "Daily")
        self.assertIn("2개", str(ctx.exception))
        self.assertIn("121", str(ctx.exception))

    def test_single_match_returns_its_id(self) -> None:
        one = [{"id": 121, "name": "Daily"}, {"id": 153, "name": "Daily Guides"}]
        with mock.patch.object(publish_wordpress.requests, "get", return_value=_Response(one)):
            self.assertEqual(_get_or_create_term_id("https://x", ("u", "p"), "categories", "Daily"), 121)

    def test_no_match_creates_the_term(self) -> None:
        with mock.patch.object(publish_wordpress.requests, "get", return_value=_Response([])), \
                mock.patch.object(publish_wordpress.requests, "post",
                                  return_value=_Response({"id": 900}, 201)) as post:
            self.assertEqual(_get_or_create_term_id("https://x", ("u", "p"), "categories", "Daily"), 900)
        self.assertTrue(post.called)


if __name__ == "__main__":
    unittest.main()
