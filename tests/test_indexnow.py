"""IndexNow(빙에 새 주소 알리기)와 사이트맵 지킴이 (2026-09-28).

- 열쇠는 두 곳(src/indexnow.py·templates/wp_stock_db.php)이 같아야 빙이 사이트 주인으로 인정한다.
- 알리기는 곁가지다 — 실패해도 예외를 올리지 않아 발행·수집이 멈추지 않는다.
- Rank Math 사이트맵이 다시 켜지면 /wp-sitemap.xml이 다른 곳으로 돌려보내져 종목 사이트맵이 404가 됐다(9/28) — 코드로 늘 끈다.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from src import indexnow

ROOT = Path(__file__).resolve().parent.parent
PHP = (ROOT / "templates" / "wp_stock_db.php").read_text(encoding="utf-8")


class IndexNowTest(unittest.TestCase):
    def test_key_matches_the_file_the_site_serves(self):
        self.assertIn(f"const FS_INDEXNOW_KEY = '{indexnow.KEY}';", PHP)

    def test_failure_does_not_raise(self):
        with mock.patch.object(indexnow.requests, "post", side_effect=indexnow.requests.ConnectionError("x")):
            self.assertFalse(indexnow.submit(["https://fermata.it.kr/stocks/005930/"]))

    def test_only_our_host_is_sent(self):
        with mock.patch.object(indexnow.requests, "post") as post:
            post.return_value.status_code = 202
            indexnow.submit(["https://example.com/a", "https://fermata.it.kr/b/", "https://fermata.it.kr/b/"])
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["urlList"], ["https://fermata.it.kr/b/"])
        self.assertEqual(body["keyLocation"], f"https://fermata.it.kr/{indexnow.KEY}.txt")

    def test_rank_math_sitemap_is_forced_off(self):
        self.assertIn("add_filter( 'option_rank_math_modules'", PHP)
        self.assertIn("array( 'sitemap' )", PHP)


if __name__ == "__main__":
    unittest.main()
