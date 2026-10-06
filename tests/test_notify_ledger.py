"""채널 알림: 같은 글을 두 번 보내지 않고(감사 F-169), 미국장이 열린 뒤에는 프리뷰를 알리지 않는다(F-170)."""
from __future__ import annotations

import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import notify_blogger_post
from src import notify_telegram


class LedgerTest(unittest.TestCase):
    def test_same_post_is_sent_once_across_channels(self) -> None:
        ledger = Path(tempfile.mkdtemp()) / "sent.json"
        doc = {"series": "가이드", "date": "2026-10-06", "slug": "x", "ko": {"title": "t"}}
        with mock.patch.object(notify_telegram, "SENT_LEDGER", ledger), \
                mock.patch.object(notify_telegram, "configured", return_value=True), \
                mock.patch.object(notify_telegram, "send", return_value={"ok": True}) as send:
            self.assertTrue(notify_telegram.notify_naver(doc, "t", "https://blog.naver.com/a/1"))
            self.assertFalse(notify_telegram.notify_naver(doc, "t", "https://fermata49.blogspot.com/x"))
        self.assertEqual(send.call_count, 1)


class PreviewTimingTest(unittest.TestCase):
    def test_preview_after_the_us_open_is_not_announced(self) -> None:
        doc = {"series": "프리뷰", "date": "2026-10-06", "ko": {"title": "오늘 밤 미국장"}}
        link = notify_blogger_post.BLOGSPOT + "x"
        before = dt.datetime(2026, 10, 6, 13, 0, tzinfo=dt.timezone.utc)    # 22:00 KST
        after = dt.datetime(2026, 10, 6, 14, 0, tzinfo=dt.timezone.utc)     # 23:00 KST, 뉴욕 10:00
        self.assertEqual(notify_blogger_post.skip_reason(Path("p.json"), doc, link, dt.date(2026, 10, 6), now=before), "")
        self.assertIn("미국장이 이미 열렸습니다", notify_blogger_post.skip_reason(Path("p.json"), doc, link, dt.date(2026, 10, 6), now=after))


if __name__ == "__main__":
    unittest.main()
