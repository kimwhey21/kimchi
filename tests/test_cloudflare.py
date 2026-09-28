"""Cloudflare 창고 비우기(src/cloudflare.py, 2026-09-28) — 바깥으로 실제 요청을 보내지 않는다(가짜 응답)."""
import os
import unittest
from pathlib import Path
from unittest import mock

from src import cloudflare

ROOT = Path(__file__).resolve().parent.parent


class PurgeTest(unittest.TestCase):
    def test_no_token_does_not_raise(self):
        with mock.patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": ""}), mock.patch.object(cloudflare.requests, "get") as get:
            self.assertFalse(cloudflare.purge_all())
            get.assert_not_called()

    def test_purges_everything_in_our_zone(self):
        zones = mock.Mock(json=lambda: {"result": [{"id": "z1"}]})
        done = mock.Mock(json=lambda: {"success": True})
        with mock.patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "t"}), \
                mock.patch.object(cloudflare.requests, "get", return_value=zones) as get, \
                mock.patch.object(cloudflare.requests, "post", return_value=done) as post:
            self.assertTrue(cloudflare.purge_all())
        self.assertEqual(get.call_args.kwargs["params"], {"name": "fermata.it.kr"})
        self.assertIn("/zones/z1/purge_cache", post.call_args.args[0])
        self.assertEqual(post.call_args.kwargs["json"], {"purge_everything": True})

    def test_network_error_is_swallowed(self):
        with mock.patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "t"}), \
                mock.patch.object(cloudflare.requests, "get", side_effect=cloudflare.requests.ConnectionError("x")):
            self.assertFalse(cloudflare.purge_all())

    def test_wired_where_the_site_cache_is_cleared(self):
        for path in ("src/stock_db.py", "src/publish_wordpress.py", "scripts/deploy_list_style.py", "scripts/deploy_templates.py"):
            self.assertIn("purge_all()", (ROOT / path).read_text(encoding="utf-8"), path)
        self.assertIn('"fermata.it.kr" in base_url', (ROOT / "src" / "publish_wordpress.py").read_text(encoding="utf-8"))   # 테스트 주소에서는 안 부른다
        for wf in ("stock_db", "editorial_publish", "guide_publish", "feature_draft", "weekly_publish"):
            self.assertIn("CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}", (ROOT / ".github" / "workflows" / f"{wf}.yml").read_text(encoding="utf-8"), wf)


if __name__ == "__main__":
    unittest.main()
