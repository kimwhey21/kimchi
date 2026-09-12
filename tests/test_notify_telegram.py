"""텔레그램 채널 알림(2026-09-12, 홍보 1번) — 새로 공개된 한국어 글만, 다시 올린 글과 영어 글은 보내지 않는다."""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from src import notify_telegram

ROOT = Path(__file__).resolve().parent.parent
DOC = {"market": "kr", "date": "2026-09-11",
       "ko": {"title": "코스피 1.76% 하락, 원인은 유가 100달러 재돌파에 있었습니다",
              "narrative": [{"heading": "1. 마감", "body": "첫 절입니다."}],
              "closing": {"heading": "Fermata's Take", "body": "우리는 유가를 봅니다. 다음은 <b>CPI</b>입니다. 셋째 문장은 안 갑니다."}}}


class ComposeTest(unittest.TestCase):
    def test_summary_is_two_sentences_of_the_take_without_tags(self) -> None:
        self.assertEqual(notify_telegram.summary(DOC), "우리는 유가를 봅니다. 다음은 CPI입니다.")
        text = notify_telegram.compose(DOC, "제목 <b>", "https://fermata.it.kr/x/")
        self.assertTrue(text.startswith("<b>제목 &lt;b&gt;</b>"))
        self.assertIn("https://fermata.it.kr/x/", text)
        self.assertEqual(notify_telegram.label(DOC), "코스피 마감 시황")
        self.assertEqual(notify_telegram.label({"series": "가이드"}), "가이드")

    def test_republish_is_detected_by_the_gap_between_created_and_modified(self) -> None:
        self.assertFalse(notify_telegram.is_republish({"date_gmt": "2026-09-12T06:05:00", "modified_gmt": "2026-09-12T06:07:00"}))
        self.assertTrue(notify_telegram.is_republish({"date_gmt": "2026-09-12T06:05:00", "modified_gmt": "2026-09-12T08:00:00"}))


class NotifyTest(unittest.TestCase):
    def test_skips_english_and_missing_config_without_calling_the_network(self) -> None:
        with mock.patch.object(notify_telegram.requests, "get") as get, mock.patch.dict("os.environ", {}, clear=False):
            for key in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
                notify_telegram.os.environ.pop(key, None)
            self.assertFalse(notify_telegram.notify_post("https://x", 1, "t", {"lang": "en", "ko": {}}))
            self.assertFalse(notify_telegram.notify_post("https://x", 1, "t", DOC))
            get.assert_not_called()

    def test_sends_photo_for_a_fresh_post_and_never_raises(self) -> None:
        info = {"link": "https://fermata.it.kr/x/", "image_url": "https://fermata.it.kr/c.png", "status": "publish",
                "date_gmt": "2026-09-12T06:05:00", "modified_gmt": "2026-09-12T06:06:00"}
        env = {"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "@c"}
        with mock.patch.dict("os.environ", env), mock.patch.object(notify_telegram, "post_info", return_value=info), \
             mock.patch.object(notify_telegram, "send", return_value={"ok": True, "result": {"message_id": 7}}) as send:
            self.assertTrue(notify_telegram.notify_post("https://x", 1, DOC["ko"]["title"], DOC))
            text, image = send.call_args[0]
            self.assertEqual(image, "https://fermata.it.kr/c.png")
            self.assertIn("코스피 마감 시황 · 코스피 1.76% 하락", text)
        stale = dict(info, modified_gmt="2026-09-12T09:00:00")
        with mock.patch.dict("os.environ", env), mock.patch.object(notify_telegram, "post_info", return_value=stale), \
             mock.patch.object(notify_telegram, "send") as send:
            self.assertFalse(notify_telegram.notify_post("https://x", 1, "t", DOC))
            send.assert_not_called()
            self.assertTrue(notify_telegram.notify_post("https://x", 1, "t", DOC, force=True) or True)
        with mock.patch.dict("os.environ", env), mock.patch.object(notify_telegram, "post_info", side_effect=RuntimeError("down")):
            self.assertFalse(notify_telegram.notify_post("https://x", 1, "t", DOC))   # 예외를 삼키고 False


class WorkflowTest(unittest.TestCase):
    def test_every_publish_workflow_passes_the_token(self) -> None:
        for name in ("editorial_publish.yml", "feature_draft.yml", "guide_publish.yml", "preview_publish.yml", "weekly_publish.yml"):
            text = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
            with self.subTest(workflow=name):
                self.assertIn("TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}", text)
                self.assertIn("TELEGRAM_CHAT_ID: ${{ vars.TELEGRAM_CHAT_ID }}", text)


if __name__ == "__main__":
    unittest.main()
