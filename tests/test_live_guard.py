"""시험 중에는 .env의 진짜 열쇠로 텔레그램·스레드에 보내지 않는다(src/live_guard.py)."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src import alert, live_guard, notify_telegram, notify_threads


class LiveGuardTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.env_file = Path(self.dir.name) / ".env"
        self.env_file.write_text("TELEGRAM_BOT_TOKEN=real-token\nTHREADS_ACCESS_TOKEN=real-threads\n", encoding="utf-8")
        self.patch = mock.patch.object(live_guard, "ENV_FILE", self.env_file)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.dir.cleanup()

    def test_real_key_is_blocked_fake_key_passes(self):
        self.assertTrue(live_guard.under_test())
        with mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "real-token"}), mock.patch("builtins.print"):
            self.assertTrue(live_guard.blocked("TELEGRAM_BOT_TOKEN"))
        with mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "fake"}):
            self.assertFalse(live_guard.blocked("TELEGRAM_BOT_TOKEN"))

    def test_not_under_test_sends(self):
        with mock.patch.object(live_guard, "under_test", return_value=False), \
                mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "real-token"}):
            self.assertFalse(live_guard.blocked("TELEGRAM_BOT_TOKEN"))

    def test_all_three_senders_stop_before_the_network(self):
        env = {"TELEGRAM_BOT_TOKEN": "real-token", "TELEGRAM_ADMIN_CHAT_ID": "1", "TELEGRAM_CHAT_ID": "@c",
               "THREADS_ACCESS_TOKEN": "real-threads", "THREADS_USER_ID": "9"}
        with mock.patch.dict(os.environ, env), mock.patch("builtins.print"), \
                mock.patch("requests.post") as post:
            self.assertFalse(alert.send("x", "warn"))
            self.assertFalse(notify_telegram.send("x").get("ok"))
            with self.assertRaises(RuntimeError):
                notify_threads._post("9/threads", {"text": "x"})
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
