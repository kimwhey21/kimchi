"""가이드 발행기의 오늘 회귀 여섯 가지를 외부 호출 없이 고정한다."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src import publish_feature, publish_wordpress


def _doc() -> dict:
    return {"kind": "feature", "slug": "test-feature", "category_id": 31,
            "ko": {"title": "SK하이닉스 지금 사도 될까? 10월 27일에 갈린다",
                   "narrative": [], "closing": {"body": ""}}}


class FeaturePublishRegressionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "feature.json"
        self.path.write_text(json.dumps(_doc()), encoding="utf-8")
        self.env = patch.dict(os.environ, {"WORDPRESS_URL": "https://example.com",
                                            "WORDPRESS_USERNAME": "u",
                                            "WORDPRESS_APP_PASSWORD": "p"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(self.tmp.cleanup)

    def _patches(self, existing):
        return patch.multiple(
            publish_feature,
            _build_graphics=Mock(return_value=([{}] * 6, {}, {"local_path": "/tmp/cover.png"})),
            run_gate=Mock(return_value={}), render=Mock(return_value="<html><body>x</body></html>"),
        ), patch("src.publish_wordpress.is_configured", return_value=True), \
            patch("src.publish_wordpress._find_existing_post_by_slug", return_value=existing), \
            patch("src.publish_wordpress.upload_featured_image", return_value=91), \
            patch("src.publish_wordpress.update_draft", return_value={"id": 44}), \
            patch("src.publish_wordpress.publish_draft", return_value={"id": 45}), \
            patch("src.publish_wordpress.verify_published")

    def test_existing_published_status_is_preserved(self) -> None:
        patches = self._patches({"id": 44, "status": "publish"})
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6] as verify:
            publish_feature.publish(self.path)
        self.assertEqual(verify.call_args.kwargs["expected_status"], "publish")
        self.assertEqual(verify.call_args.kwargs["expected_featured_media"], 91)

    def test_existing_post_uses_update_not_duplicate_create(self) -> None:
        patches = self._patches({"id": 44, "status": "publish"})
        with patches[0], patches[1], patches[2], patches[3] as upload, patches[4] as update, patches[5] as create, patches[6]:
            publish_feature.publish(self.path)
        update.assert_called_once()
        self.assertIsNone(update.call_args.kwargs["status"])
        create.assert_not_called()
        upload.assert_called_once()  # 대표 id는 응답에서 받고 추측하지 않는다.

    def test_new_post_is_explicit_draft(self) -> None:
        patches = self._patches(None)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5] as create, patches[6]:
            publish_feature.publish(self.path)
        self.assertEqual(create.call_args.kwargs["status"], "draft")

    def test_category_is_numeric_id_not_name(self) -> None:
        patches = self._patches(None)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5] as create, patches[6]:
            publish_feature.publish(self.path)
        self.assertEqual(create.call_args.kwargs["category"], 31)

    def test_featured_media_comes_from_upload_response(self) -> None:
        patches = self._patches(None)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5] as create, patches[6]:
            publish_feature.publish(self.path)
        self.assertEqual(create.call_args.kwargs["featured_media_id"], 91)

    def test_all_five_checks_are_entered_through_gate(self) -> None:
        patches = self._patches(None)
        gate = Mock(return_value={})
        with patches[0], patch("src.publish_feature.run_gate", gate), patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
            publish_feature.publish(self.path)
        gate.assert_called_once()
        self.assertEqual(gate.call_args.kwargs["graphics"], 6)


class WordPressSafetyTest(unittest.TestCase):
    def test_existing_mb_post_is_not_wrapped_twice(self) -> None:
        result = publish_wordpress._to_wordpress_content(
            '<html><head></head><body><div class="mb-post">x</div></body></html>'
        )
        self.assertEqual(result.count('class="mb-post"'), 1)

    def test_media_reuse_uses_content_hash_not_file_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "same-name.png"
            path.write_bytes(b"different bytes but same size")
            found = Mock(status_code=200)
            found.json.return_value = [{"id": 77, "description": {"raw": "market-brief-sha256:" + __import__("hashlib").sha256(path.read_bytes()).hexdigest()}}]
            with patch("src.publish_wordpress.requests.get", return_value=found), \
                 patch("src.publish_wordpress.requests.post") as post:
                media_id = publish_wordpress.upload_featured_image("https://x", ("u", "p"), {"local_path": str(path)})
            self.assertEqual(media_id, 77)
            post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
