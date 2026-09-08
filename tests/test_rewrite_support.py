"""옛 글 재작성 지원(2026-09-08): 글 번호로 덮어쓰기.

시황 이전 옛 글은 주소가 한글 slug라 `editorial-<market>-<date>-ko` slug로는 찾지
못한다. 원고의 `wp_post_ids`가 가리키는 글 번호를 그대로 갱신해 주소·글 번호를 지킨다.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from src import publish_wordpress


class PostIdTargetingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.env = patch.dict(os.environ, {"WORDPRESS_URL": "https://example.com",
                                            "WORDPRESS_USERNAME": "u", "WORDPRESS_APP_PASSWORD": "p"})
        self.env.start(); self.addCleanup(self.env.stop)

    def test_publish_overwrites_the_given_post_id(self) -> None:
        with patch.object(publish_wordpress, "_get_post_by_id", return_value={"id": 33, "status": "publish"}) as get, \
             patch.object(publish_wordpress, "_find_existing_post_by_slug") as by_slug, \
             patch.object(publish_wordpress, "update_draft", return_value={"id": 33}) as update:
            result = publish_wordpress.publish_draft("t", "<p>x</p>", slug="editorial-kr-2026-08-28-ko",
                                                     status="publish", post_id=33)
        self.assertEqual(result["id"], 33)
        get.assert_called_once(); by_slug.assert_not_called()
        self.assertEqual(update.call_args.args[0], 33)
        self.assertEqual(update.call_args.kwargs["status"], "publish")

    def test_missing_post_id_is_an_error(self) -> None:
        with patch.object(publish_wordpress, "_get_post_by_id", return_value=None):
            with self.assertRaises(publish_wordpress.WordPressPublishError):
                publish_wordpress.publish_draft("t", "<p>x</p>", status="publish", post_id=999)


if __name__ == "__main__":
    unittest.main()
