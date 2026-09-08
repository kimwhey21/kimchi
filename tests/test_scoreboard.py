"""기준표 성적표(data/scoreboard.yaml → 페이지)를 외부 호출 없이 고정한다."""
from __future__ import annotations

import datetime as dt
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from src import publish_scoreboard as sb

GOOD = """
- title: "글 하나"
  url: https://fermata.it.kr/one/
  date: 2026-09-06
  summary: "요약"
  checks:
    - due: 2026-09-07
      what: "볼 것"
      verdict: hit
      result: "이렇게 됐다"
      checked: 2026-09-08
    - due: 2026-10-27
      what: "나중에 볼 것"
      verdict: pending
"""


def _write(text: str) -> Path:
    tmp = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False, encoding="utf-8")
    tmp.write(text)
    tmp.close()
    return Path(tmp.name)


class LoadTest(unittest.TestCase):
    def test_good_file_loads(self) -> None:
        self.assertEqual(len(sb.load(_write(GOOD))), 1)

    def test_committed_file_is_valid(self) -> None:
        """실제 data/scoreboard.yaml이 형식을 어기면 워크플로가 페이지를 못 만든다."""
        articles = sb.load(sb.DATA)
        self.assertGreaterEqual(len(articles), 1)

    def test_unknown_verdict_is_rejected(self) -> None:
        with self.assertRaises(sb.ScoreboardError):
            sb.load(_write(GOOD.replace("verdict: hit", "verdict: maybe")))

    def test_verdict_without_result_is_rejected(self) -> None:
        """판정만 적고 근거(결과·확인 날짜)를 안 적으면 막는다."""
        with self.assertRaises(sb.ScoreboardError):
            sb.load(_write(GOOD.replace('      result: "이렇게 됐다"\n', "")))

    def test_foreign_url_is_rejected(self) -> None:
        with self.assertRaises(sb.ScoreboardError):
            sb.load(_write(GOOD.replace("https://fermata.it.kr/one/", "https://example.com/one/")))


class BuildTest(unittest.TestCase):
    def test_tally_and_labels(self) -> None:
        html = sb.build(sb.load(_write(GOOD)), today=dt.date(2026, 9, 8))
        self.assertIn("기준표 성적표", html)
        self.assertIn("적중", html)
        self.assertIn("확인 전", html)
        self.assertIn("9/7", html)
        self.assertIn("10/27", html)
        self.assertIn("2026-09-08", html)
        self.assertIn("<!-- wp:html -->", html)

    def test_unpublished_articles_are_dropped(self) -> None:
        articles = sb.load(_write(GOOD + GOOD.replace("글 하나", "글 둘").replace("/one/", "/two/")))
        kept = sb.only_live(articles, is_live=lambda url: url.endswith("/one/"))
        self.assertEqual([a["title"] for a in kept], ["글 하나"])

    def test_no_live_article_stops(self) -> None:
        with self.assertRaises(sb.ScoreboardError):
            sb.only_live(sb.load(_write(GOOD)), is_live=lambda url: False)


class PublishTest(unittest.TestCase):
    def setUp(self) -> None:
        self.env = patch.dict(os.environ, {"WORDPRESS_URL": "https://example.com",
                                            "WORDPRESS_USERNAME": "u", "WORDPRESS_APP_PASSWORD": "p"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def _response(self, payload, status=200):
        r = Mock()
        r.status_code = status
        r.json.return_value = payload
        r.raise_for_status = Mock()
        r.text = ""
        return r

    def test_existing_page_is_updated_without_touching_status(self) -> None:
        with patch.object(sb, "_find_page", return_value={"id": 9, "status": "publish"}), \
                patch.object(sb.requests, "post", return_value=self._response({"id": 9, "link": "x"})) as post, \
                patch.object(sb.requests, "get", return_value=self._response({"content": {"raw": "기준표 성적표"}})):
            sb.publish("<p>기준표 성적표</p>")
        self.assertEqual(post.call_args.kwargs["json"], {"content": "<p>기준표 성적표</p>"})

    def test_missing_page_is_created_as_draft(self) -> None:
        with patch.object(sb, "_find_page", return_value=None), \
                patch.object(sb.requests, "post", return_value=self._response({"id": 10, "link": "x"})) as post, \
                patch.object(sb.requests, "get", return_value=self._response({"content": {"raw": "기준표 성적표"}})):
            sb.publish("<p>기준표 성적표</p>")
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["status"], "draft")
        self.assertEqual(body["slug"], "scoreboard")
        self.assertEqual(body["template"], "page-no-title")

    def test_auto_publish_switch_creates_the_page_live(self) -> None:
        """저장소 변수 FERMATA_AUTO_PUBLISH=true면 사람 승인 없이 바로 공개한다."""
        with patch.dict(os.environ, {"FERMATA_AUTO_PUBLISH": "true"}), \
                patch.object(sb, "_find_page", return_value=None), \
                patch.object(sb.requests, "post", return_value=self._response({"id": 11, "link": "x"})) as post, \
                patch.object(sb.requests, "get", return_value=self._response({"content": {"raw": "기준표 성적표"}})):
            sb.publish("<p>기준표 성적표</p>")
        self.assertEqual(post.call_args.kwargs["json"]["status"], "publish")

    def test_missing_settings_fail_loudly(self) -> None:
        with patch.dict(os.environ, {"WORDPRESS_URL": ""}):
            with self.assertRaises(sb.ScoreboardError):
                sb.publish("<p>x</p>")


if __name__ == "__main__":
    unittest.main()
