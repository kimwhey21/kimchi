"""스레드 자동 게시(2026-09-12, 홍보 2번) — 텔레그램과 같은 원칙: 한국어 새 글만, 실패해도 발행은 성공."""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from src import notify_threads
from tests.test_notify_telegram import DOC

ROOT = Path(__file__).resolve().parent.parent


class ComposeTest(unittest.TestCase):
    def test_text_has_title_take_and_link_within_500_chars(self) -> None:
        text = notify_threads.compose(DOC, DOC["ko"]["title"], "https://fermata.it.kr/x/")
        self.assertTrue(text.startswith("코스피 마감 시황 · 코스피 1.76% 하락"))
        self.assertIn("우리는 유가를 봅니다. 다음은 CPI입니다.", text)
        self.assertTrue(text.endswith("https://fermata.it.kr/x/"))
        long_doc = {"series": "가이드", "ko": {"title": "제목", "narrative": [], "closing": {"body": "가 " * 400}}}
        self.assertLessEqual(len(notify_threads.compose(long_doc, "제목", "https://fermata.it.kr/y/")), 500)


class PublishFlowTest(unittest.TestCase):
    def test_container_then_publish(self) -> None:
        env = {"THREADS_ACCESS_TOKEN": "t", "THREADS_USER_ID": "99"}
        calls = []
        def fake_post(path, params):
            calls.append((path, params)); return {"id": "c1" if path.endswith("/threads") else "p1"}
        with mock.patch.dict("os.environ", env), mock.patch.object(notify_threads, "_post", side_effect=fake_post), \
             mock.patch.object(notify_threads, "_container_ready", return_value=True), mock.patch.object(notify_threads.time, "sleep"):
            self.assertEqual(notify_threads.publish("본문", "https://fermata.it.kr/c.png"), "p1")
        self.assertEqual(calls[0][0], "99/threads")
        self.assertEqual(calls[0][1]["media_type"], "IMAGE")
        self.assertEqual(calls[1], ("99/threads_publish", {"creation_id": "c1"}))

    def test_notify_skips_and_never_raises(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=False):
            for key in ("THREADS_ACCESS_TOKEN", "THREADS_USER_ID"):
                notify_threads.os.environ.pop(key, None)
            self.assertFalse(notify_threads.notify_post("https://x", 1, "t", DOC))
        env = {"THREADS_ACCESS_TOKEN": "t", "THREADS_USER_ID": "99"}
        info = {"link": "https://fermata.it.kr/x/", "image_url": "https://fermata.it.kr/c.png", "status": "publish",
                "date_gmt": "2026-09-12T06:05:00", "modified_gmt": "2026-09-12T06:06:00"}
        with mock.patch.dict("os.environ", env), mock.patch.object(notify_threads.notify_telegram, "post_info", return_value=info), \
             mock.patch.object(notify_threads, "publish", return_value="p9") as pub:
            self.assertTrue(notify_threads.notify_post("https://x", 1, "t", DOC))
            self.assertEqual(pub.call_args[0][1], "https://fermata.it.kr/c.png")
        with mock.patch.dict("os.environ", env), mock.patch.object(notify_threads.notify_telegram, "post_info", side_effect=RuntimeError("down")):
            self.assertFalse(notify_threads.notify_post("https://x", 1, "t", DOC))
        self.assertFalse(notify_threads.notify_post("https://x", 1, "t", {"lang": "en", "ko": {}}))


class WorkflowTest(unittest.TestCase):
    def test_every_publish_workflow_passes_the_threads_token(self) -> None:
        for name in ("editorial_publish.yml", "feature_draft.yml", "guide_publish.yml", "preview_publish.yml", "weekly_publish.yml"):
            text = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
            with self.subTest(workflow=name):
                self.assertIn("THREADS_ACCESS_TOKEN: ${{ secrets.THREADS_ACCESS_TOKEN }}", text)


if __name__ == "__main__":
    unittest.main()
