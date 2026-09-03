from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from src import publish_wordpress


class PublishIdempotencyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.env = patch.dict(
            os.environ,
            {
                "WORDPRESS_URL": "https://example.com",
                "WORDPRESS_USERNAME": "tester",
                "WORDPRESS_APP_PASSWORD": "app-pass",
            },
        )
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()

    @patch("src.publish_wordpress.update_draft")
    @patch("src.publish_wordpress._featured_media_matches", return_value=True)
    @patch("src.publish_wordpress._find_existing_post_by_slug")
    def test_updates_existing_draft(
        self, find_existing, media_matches, update_draft
    ) -> None:
        find_existing.return_value = {"id": 42, "status": "draft", "featured_media": 77}
        update_draft.return_value = {"id": 42, "status": "draft"}

        result = publish_wordpress.publish_draft(
            "Title",
            "<html><body>Body</body></html>",
            image={"local_path": "/tmp/new.png"},
            slug="market-brief-kr-date-ko",
        )

        self.assertEqual(result["id"], 42)
        update_draft.assert_called_once()
        self.assertIsNone(update_draft.call_args.kwargs["image"])
        self.assertEqual(update_draft.call_args.kwargs["featured_media_id"], 77)
        media_matches.assert_called_once()

    @patch("src.publish_wordpress.update_draft")
    @patch("src.publish_wordpress._featured_media_matches", return_value=False)
    @patch("src.publish_wordpress._find_existing_post_by_slug")
    def test_replaces_featured_image_when_data_changed(
        self, find_existing, media_matches, update_draft
    ) -> None:
        find_existing.return_value = {"id": 42, "status": "draft", "featured_media": 77}
        update_draft.return_value = {"id": 42, "status": "draft", "featured_media": 88}
        image = {"local_path": "/tmp/new.png", "alt": "new market values"}

        result = publish_wordpress.publish_draft(
            "Title",
            "<html><body>Body</body></html>",
            image=image,
            slug="market-brief-kr-date-ko",
        )

        self.assertEqual(result["featured_media"], 88)
        self.assertEqual(update_draft.call_args.kwargs["image"], image)
        self.assertIsNone(update_draft.call_args.kwargs["featured_media_id"])
        media_matches.assert_called_once()

    @patch("src.publish_wordpress.update_draft")
    @patch("src.publish_wordpress._find_existing_post_by_slug")
    def test_draft_run_does_not_touch_published_post(
        self, find_existing, update_draft
    ) -> None:
        """손으로 돌리는 임시저장 실행이 공개된 글을 건드리면 안 됩니다."""
        find_existing.return_value = {"id": 43, "status": "publish"}

        result = publish_wordpress.publish_draft(
            "Title", "<html><body>Body</body></html>", slug="market-brief-kr-date-en"
        )

        self.assertEqual(result["status"], "publish")
        update_draft.assert_not_called()

    @patch("src.publish_wordpress.update_draft")
    @patch("src.publish_wordpress._featured_media_matches", return_value=True)
    @patch("src.publish_wordpress._find_existing_post_by_slug")
    def test_live_publish_overwrites_published_post(
        self, find_existing, media_matches, update_draft
    ) -> None:
        """같은 거래일 원고를 다시 써서 공개하면 옛 글을 덮어써야 합니다.

        전에는 여기서 그냥 넘어가, 고쳐 쓴 원고가 사이트에 영영 반영되지
        않았습니다.
        """
        find_existing.return_value = {"id": 43, "status": "publish", "featured_media": 77}
        update_draft.return_value = {"id": 43, "status": "publish"}

        result = publish_wordpress.publish_draft(
            "새 제목",
            "<html><body>새 본문</body></html>",
            image={"local_path": "/tmp/new.png"},
            slug="editorial-kr-2026-09-03-ko",
            status="publish",
        )

        self.assertEqual(result["id"], 43)
        update_draft.assert_called_once()
        self.assertEqual(update_draft.call_args.kwargs["status"], "publish")


if __name__ == "__main__":
    unittest.main()
