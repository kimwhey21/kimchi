"""Cloudflare 다시 채우기(2026-10-14) — 비운 뒤 사이트맵 주소를 하나씩 불러 두고, 비우기 실패는 알린다."""
import unittest
from unittest import mock

from src import cloudflare as cf


def _resp(text="", status=200):
    return mock.Mock(text=text, status_code=status)


class WarmTest(unittest.TestCase):
    def test_warms_every_sitemap_url_one_by_one(self):
        pages = {"https://fermata.it.kr/wp-sitemap.xml": "<loc>https://fermata.it.kr/wp-sitemap-posts-post-1.xml</loc>",
                 "https://fermata.it.kr/wp-sitemap-posts-post-1.xml": "<loc>https://fermata.it.kr/a/</loc><loc>https://fermata.it.kr/b/</loc>"}
        seen = []

        def get(url, **kw):
            seen.append(url)
            return _resp(pages.get(url, "ok"))
        slept = []
        self.assertEqual(cf.warm(get=get, sleep=slept.append), 2)
        self.assertEqual(seen[-2:], ["https://fermata.it.kr/a/", "https://fermata.it.kr/b/"])
        self.assertEqual(len(slept), 2)

    def test_purge_failure_alerts(self):
        with mock.patch.dict("os.environ", {"CLOUDFLARE_API_TOKEN": "t"}), \
                mock.patch.object(cf.requests, "get", return_value=mock.Mock(json=lambda: {"result": [{"id": "z"}]})), \
                mock.patch.object(cf.requests, "post", return_value=mock.Mock(json=lambda: {"success": False, "errors": ["x"]})), \
                mock.patch("src.alert.send") as send:
            self.assertFalse(cf.purge_all())
        send.assert_called_once()


if __name__ == "__main__":
    unittest.main()
