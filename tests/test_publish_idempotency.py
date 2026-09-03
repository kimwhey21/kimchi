from __future__ import annotations

import os
import unittest
import unittest.mock
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


class VerifyPublishedTest(unittest.TestCase):
    """발행이 조용히 실패하는 것을 막는 확인 단계입니다.

    2026-09-03 아침에 워크플로가 초록 체크로 끝났는데 한국장 글은 올라가지
    않았습니다. 스크립트의 "성공"과 사이트의 실제 상태가 달랐고, 알아챈 것은
    사람이 사이트를 열어봤기 때문이었습니다.
    """

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
        self.addCleanup(self.env.stop)

    def _response(self, payload: dict, status_code: int = 200):
        response = unittest.mock.Mock()
        response.status_code = status_code
        response.json.return_value = payload
        return response

    def _post(self, **overrides) -> dict:
        post = {
            "status": "publish",
            "title": {"raw": "삼성중공업 8.58%, KB금융 5.20%"},
            "content": {"raw": "본문" * 400},
        }
        post.update(overrides)
        return post

    def test_passes_when_site_matches(self) -> None:
        with patch("src.publish_wordpress.requests.get", return_value=self._response(self._post())):
            publish_wordpress.verify_published(331, "삼성중공업 8.58%, KB금융 5.20%")

    def test_fails_when_old_title_remains(self) -> None:
        stale = self._post(title={"raw": "예전 제목"})
        with patch("src.publish_wordpress.requests.get", return_value=self._response(stale)):
            with self.assertRaises(publish_wordpress.WordPressPublishError):
                publish_wordpress.verify_published(331, "삼성중공업 8.58%, KB금융 5.20%")

    def test_fails_when_still_draft(self) -> None:
        draft = self._post(status="draft")
        with patch("src.publish_wordpress.requests.get", return_value=self._response(draft)):
            with self.assertRaises(publish_wordpress.WordPressPublishError):
                publish_wordpress.verify_published(331, "삼성중공업 8.58%, KB금융 5.20%")

    def test_fails_when_post_cannot_be_read_back(self) -> None:
        with patch("src.publish_wordpress.requests.get", return_value=self._response({}, 404)):
            with self.assertRaises(publish_wordpress.WordPressPublishError):
                publish_wordpress.verify_published(331, "제목")

    def test_smart_quotes_do_not_fail_the_check(self) -> None:
        """워드프레스가 따옴표·말줄임표를 바꿔 저장해도 같은 제목으로 봅니다."""
        saved = self._post(title={"raw": "델이 15.81% 올랐습니다… ‘AI 서버’"})
        with patch("src.publish_wordpress.requests.get", return_value=self._response(saved)):
            publish_wordpress.verify_published(325, "델이 15.81% 올랐습니다... 'AI 서버'")


if __name__ == "__main__":
    unittest.main()
