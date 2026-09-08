"""기준표 발행기의 `--publish`와 URL 표지 사진(루틴 경로)을 외부 호출 없이 고정한다.

주말 기준표 루틴(docs/routine_feature.md)은 워드프레스를 만질 수 없다. 원고를
커밋하면 feature_draft.yml이 임시저장으로 올리고, 공개는 사람이 "발행"이라고 한 뒤
`--publish`로 한다. 루틴이 눈으로 보고 고른 표지 사진은 파일이 아니라 URL로 온다.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src import publish_feature


def _doc(photo: dict | None = None) -> dict:
    doc = {"kind": "feature", "slug": "test-feature", "category_id": 153,
           "ko": {"title": "SK하이닉스 지금 사도 될까? 10월 27일에 갈린다",
                  "narrative": [], "closing": {"body": ""}}}
    if photo:
        doc["featured_photo"] = photo
    return doc


class FeaturePublishLiveTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "feature.json"
        self.env = patch.dict(os.environ, {"WORDPRESS_URL": "https://example.com",
                                            "WORDPRESS_USERNAME": "u",
                                            "WORDPRESS_APP_PASSWORD": "p"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(self.tmp.cleanup)

    def _run(self, doc: dict, existing: dict | None, live: bool):
        self.path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        with patch.multiple(publish_feature,
                            _build_graphics=Mock(return_value=([{}] * 6, {}, None)),
                            run_gate=Mock(return_value={}),
                            render=Mock(return_value="<html><body>x</body></html>")), \
                patch("src.publish_wordpress.is_configured", return_value=True), \
                patch("src.publish_wordpress._find_existing_post_by_slug", return_value=existing), \
                patch("src.publish_wordpress.upload_featured_image", return_value=91) as upload, \
                patch("src.publish_wordpress.update_draft", return_value={"id": 44}) as update, \
                patch("src.publish_wordpress.publish_draft", return_value={"id": 45}) as create, \
                patch("src.publish_wordpress.verify_published") as verify:
            publish_feature.publish(self.path, live=live)
        return upload, update, create, verify

    def test_default_is_draft_for_a_new_post(self) -> None:
        _, _, create, verify = self._run(_doc(), existing=None, live=False)
        self.assertEqual(create.call_args.kwargs["status"], "draft")
        self.assertEqual(verify.call_args.kwargs["expected_status"], "draft")

    def test_publish_flag_goes_live_for_a_new_post(self) -> None:
        _, _, create, verify = self._run(_doc(), existing=None, live=True)
        self.assertEqual(create.call_args.kwargs["status"], "publish")
        self.assertEqual(verify.call_args.kwargs["expected_status"], "publish")

    def test_publish_flag_goes_live_for_an_existing_draft(self) -> None:
        _, update, _, verify = self._run(_doc(), existing={"id": 44, "status": "draft"}, live=True)
        self.assertEqual(update.call_args.kwargs["status"], "publish")
        self.assertEqual(verify.call_args.kwargs["expected_status"], "publish")

    def test_existing_post_keeps_its_status_without_the_flag(self) -> None:
        _, update, _, verify = self._run(_doc(), existing={"id": 44, "status": "publish"}, live=False)
        self.assertIsNone(update.call_args.kwargs["status"])
        self.assertEqual(verify.call_args.kwargs["expected_status"], "publish")

    def test_url_cover_photo_is_uploaded_by_url(self) -> None:
        """루틴이 보고 고른 사진은 파일이 아니라 URL로 온다. 러너가 그 URL로 받는다."""
        photo = {"url": "https://images.unsplash.com/photo-1", "alt": "트랙터",
                 "credit": "사진: Someone / Unsplash", "credit_url": "https://unsplash.com/photos/x"}
        upload, _, create, _ = self._run(_doc(photo), existing=None, live=False)
        image = upload.call_args.args[2]
        self.assertEqual(image["url"], photo["url"])
        self.assertEqual(image["caption"], photo["credit"])
        self.assertNotIn("local_path", image)
        self.assertEqual(create.call_args.kwargs["featured_media_id"], 91)

    def test_cover_photo_without_file_or_url_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._run(_doc({"alt": "x"}), existing=None, live=False)

    def test_excerpt_is_the_first_paragraph_without_tags(self) -> None:
        """excerpt를 안 적으면 첫 절 첫 문단이 요약이 된다 — 표식·제목·소제목이 아니라."""
        ko = {"title": "t", "narrative": [{"heading": "1. 절", "body": "첫 <b>문단</b>입니다.\n\n둘째 문단."}]}
        self.assertEqual(publish_feature._excerpt(ko), "첫 문단입니다.")
        self.assertEqual(publish_feature._excerpt({"excerpt": "손으로 쓴 요약", **ko}), "손으로 쓴 요약")
        long = {"narrative": [{"body": "가 " * 200}]}
        self.assertTrue(publish_feature._excerpt(long).endswith("…"))
        self.assertLessEqual(len(publish_feature._excerpt(long)), 202)

    def test_cli_has_a_publish_flag(self) -> None:
        with patch.object(publish_feature, "publish", return_value={}) as pub:
            publish_feature.main([str(self.path), "--publish"])
        self.assertTrue(pub.call_args.kwargs["live"])
        self.assertTrue(pub.call_args.kwargs["upload"])


if __name__ == "__main__":
    unittest.main()
