"""발행 확인(`src/check_publication.py`)이 주말·휴장 다음 아침에 헛경보를 내지 않는지.

2026-09-07(월)은 미국 노동절 휴장이었다. 화요일 01:00 UTC 검사 시점에 최신 시세
파일과 지수의 실제 마지막 거래일은 둘 다 9/4로 같고, 9/4 글은 9/5 12:53 UTC에
마지막으로 수정돼 있다. 옛 기준("36시간 안에 수정")으로는 60시간이라 실패 메일이
갔을 상황이다. 새 기준은 "거래일보다 앞서 수정된 글"만 옛 글로 본다.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src import check_publication as cp

DOC = {"ko": {"title": "제목"}, "en": {"title": "Title"}}


class CheckPublicationTest(unittest.TestCase):
    def _check(self, actual_trading_date: str, post: dict | None) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "data"
            editorial = Path(tmp) / "editorial"
            data.mkdir()
            editorial.mkdir()
            (data / "price_us_2026-09-04.json").write_text("{}", encoding="utf-8")
            (editorial / "us_2026-09-04.json").write_text(json.dumps(DOC), encoding="utf-8")
            with mock.patch.object(cp, "DATA_DIR", data), \
                    mock.patch.object(cp, "EDITORIAL_DIR", editorial), \
                    mock.patch.object(cp, "_actual_trading_date", return_value=actual_trading_date), \
                    mock.patch.object(cp, "_wordpress_post", return_value=post):
                return cp.check_market("us", check_site=True)

    def test_holiday_morning_is_not_an_alarm(self) -> None:
        """휴장 다음 아침: 새 거래일 없음, 글은 거래일 뒤에 수정됨 → 문제 없음."""
        post = {"id": 1, "status": "publish", "modified_gmt": "2026-09-05T12:53:52"}
        self.assertEqual(self._check("2026-09-04", post), [])

    def test_post_modified_before_trading_date_is_stale(self) -> None:
        post = {"id": 1, "status": "publish", "modified_gmt": "2026-09-03T10:00:00"}
        problems = self._check("2026-09-04", post)
        self.assertEqual(len(problems), 2)  # ko·en
        self.assertIn("옛 글", problems[0])

    def test_newer_trading_day_without_price_file_is_reported(self) -> None:
        post = {"id": 1, "status": "publish", "modified_gmt": "2026-09-05T12:53:52"}
        problems = self._check("2026-09-08", post)
        self.assertTrue(any("시세 수집이 실패" in p for p in problems), problems)

    def test_post_missing_from_sitemap_is_reported(self) -> None:
        """사이트맵이 멈추면(2026-09-08·09-12) 공개된 글이 사이트맵에 없다 — 발행 확인이 그날 잡는다."""
        post = {"id": 1, "status": "publish", "modified_gmt": "2026-09-05T12:53:52",
                "link": "https://fermata.it.kr/editorial-us-2026-09-04-ko/"}
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "data"; editorial = Path(tmp) / "editorial"; data.mkdir(); editorial.mkdir()
            (data / "price_us_2026-09-04.json").write_text("{}", encoding="utf-8")
            (editorial / "us_2026-09-04.json").write_text(json.dumps({"ko": {"title": "제목"}}), encoding="utf-8")
            with mock.patch.object(cp, "DATA_DIR", data), mock.patch.object(cp, "EDITORIAL_DIR", editorial), \
                    mock.patch.object(cp, "_actual_trading_date", return_value="2026-09-04"), \
                    mock.patch.object(cp, "_wordpress_post", return_value=post):
                stale = cp.check_market("us", check_site=True, sitemap_urls={"https://fermata.it.kr/other/"})
                fresh = cp.check_market("us", check_site=True, sitemap_urls={"https://fermata.it.kr/editorial-us-2026-09-04-ko"})
                skipped = cp.check_market("us", check_site=True, sitemap_urls=None)
        self.assertTrue(any("사이트맵" in p for p in stale), stale)
        self.assertEqual(fresh, [])
        self.assertEqual(skipped, [])

    def test_missing_post_is_reported(self) -> None:
        problems = self._check("2026-09-04", None)
        self.assertTrue(any("사이트에 글이 없습니다" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main()
