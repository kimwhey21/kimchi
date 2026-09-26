import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import notify_blogger_post as nbp

TODAY = dt.date(2026, 9, 28)
LINK = "https://fermata49.blogspot.com/2026/09/kospi.html"


def _write(tmp: str, name: str, doc: dict) -> Path:
    path = Path(tmp) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return path


class NotifyBloggerPostTest(unittest.TestCase):
    def _run(self, name: str, doc: dict, link: str = LINK):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(nbp.notify_telegram, "notify_naver") as sent, \
                mock.patch.object(nbp.notify_threads, "notify_naver") as threads:
            nbp.main([str(_write(tmp, name, doc)), link], today=TODAY)
        self.assertEqual(sent.call_args_list, threads.call_args_list)   # 텔레그램과 스레드는 늘 같은 글·같은 주소
        return sent

    def test_fresh_korean_daily_goes_to_telegram_with_blogspot_link(self):
        sent = self._run("kr_2026-09-28.json", {"market": "kr", "date": "2026-09-28", "ko": {"title": "코스피가 버틴 이유"}})
        sent.assert_called_once()
        self.assertEqual(sent.call_args.args[1:], ("코스피가 버틴 이유", LINK))

    def test_yesterday_manuscript_still_counts_as_fresh(self):
        sent = self._run("us_2026-09-27.json", {"market": "us", "date": "2026-09-27", "ko": {"title": "나스닥"}})
        sent.assert_called_once()

    def test_backlog_is_not_announced(self):
        sent = self._run("ko_guide.json", {"series": "가이드", "date": "2026-09-20", "ko": {"title": "옛 가이드"}})
        sent.assert_not_called()

    def test_magazine_never_goes_to_fermata_channel(self):
        sent = self._run("magazine/2026-09-28_x.json", {"series": "매거진", "date": "2026-09-28", "ko": {"title": "잡지"}})
        sent.assert_not_called()

    def test_english_and_non_blogspot_links_are_skipped(self):
        self._run("en.json", {"lang": "en", "date": "2026-09-28", "ko": {"title": "x"}}).assert_not_called()
        self._run("kr.json", {"market": "kr", "date": "2026-09-28", "ko": {"title": "x"}},
                  link="https://blog.naver.com/fermata49/1").assert_not_called()
        self._run("kr.json", {"market": "kr", "date": "2026-09-28", "ko": {"title": "x"}}, link="").assert_not_called()


if __name__ == "__main__":
    unittest.main()
