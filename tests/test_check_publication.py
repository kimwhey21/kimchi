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
    @staticmethod
    def _posts(modified: str) -> dict:
        """언어별 조회 결과. 한국어 시황은 본진에 비공개로 올라간다(2026-09-16, 사용자 지시)."""
        return {"ko": {"id": 1, "status": "private", "modified_gmt": modified},
                "en": {"id": 2, "status": "publish", "modified_gmt": modified}}

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
                    mock.patch.object(cp, "_wordpress_post",
                                      side_effect=(lambda slug: post.get(slug.rsplit("-", 1)[-1])) if isinstance(post, dict) and "ko" in post else (lambda slug: post)):
                return cp.check_market("us", check_site=True)

    def test_holiday_morning_is_not_an_alarm(self) -> None:
        """휴장 다음 아침: 새 거래일 없음, 글은 거래일 뒤에 수정됨 → 문제 없음.

        한국어판은 `private`, 영어판은 `publish`가 정상이다(2026-09-16). 언어마다 기대
        상태가 다르므로 조회 결과도 언어에 맞춰 돌려준다.
        """
        self.assertEqual(self._check("2026-09-04", self._posts("2026-09-05T12:53:52")), [])

    @mock.patch.object(cp.publish_editorial, "KO_DAILY_TO_WORDPRESS", True)   # 스위치를 켰을 때의 동작(2026-09-26부터 기본은 꺼짐)
    def test_public_korean_daily_is_an_alarm(self) -> None:
        """한국어 시황이 **공개**돼 있으면 잡아야 한다(2026-09-16).

        네이버에 같은 글이 전문으로 올라가므로 본진에도 공개돼 있으면 두 곳에 공개된 상태가
        된다 — 네이버가 유사문서로 거를 위험이 생긴다. 그래서 상태가 틀린 것도 실패다.
        """
        posts = self._posts("2026-09-05T12:53:52")
        posts["ko"] = {**posts["ko"], "status": "publish"}
        problems = self._check("2026-09-04", posts)
        self.assertTrue(any("[ko]" in x and "private" in x for x in problems), problems)

    @mock.patch.object(cp.publish_editorial, "KO_DAILY_TO_WORDPRESS", True)   # 스위치를 켰을 때의 동작(2026-09-26부터 기본은 꺼짐)
    def test_post_modified_before_trading_date_is_stale(self) -> None:
        problems = self._check("2026-09-04", self._posts("2026-09-03T10:00:00"))
        # 두 언어 모두 본진에 올라가므로(2026-09-16) 둘 다 옛 글로 잡힌다.
        self.assertEqual(len(problems), 2, problems)
        self.assertTrue(all("옛 글" in x for x in problems), problems)
        self.assertTrue(any("[ko]" in x for x in problems) and any("[en]" in x for x in problems), problems)

    @mock.patch.object(cp.publish_editorial, "KO_DAILY_TO_WORDPRESS", True)   # 스위치를 켰을 때의 동작(2026-09-26부터 기본은 꺼짐)
    def test_korean_daily_is_looked_for_again(self) -> None:
        """한국어 시황은 다시 본진에 올라간다(2026-09-16, 사용자 지시) — 없으면 잡아야 한다.

        2026-09-15 하루 동안은 이 검사를 꺼 뒀고, 그사이 스위치가 막은 두 편(kr 9/16·us 9/15)이
        본진에 올라가지 않았는데 아무 경보도 울리지 않았다. 검사를 끄면 빠진 것이 안 보인다.
        """
        problems = self._check("2026-09-04", None)
        self.assertTrue(any("[ko]" in p for p in problems), problems)
        self.assertTrue(any("[en]" in p for p in problems), problems)
        with mock.patch.object(cp.publish_editorial, "KO_DAILY_TO_WORDPRESS", False):
            off = self._check("2026-09-04", None)
        self.assertFalse(any("[ko]" in p for p in off), off)

    def test_korean_daily_is_not_on_wordpress_by_default(self) -> None:
        """2026-09-26부터 한국어 시황은 본진에 올리지 않는다(사장님 "둘다 진행해") — 한국어는 찾지 않고 영어만 본다."""
        self.assertFalse(cp.publish_editorial.KO_DAILY_TO_WORDPRESS)
        problems = self._check("2026-09-04", None)
        self.assertFalse(any("[ko]" in p for p in problems), problems)
        self.assertTrue(any("[en]" in p for p in problems), problems)

    def test_newer_trading_day_without_price_file_is_reported(self) -> None:
        problems = self._check("2026-09-08", self._posts("2026-09-05T12:53:52"))
        self.assertTrue(any("시세 수집이 실패" in p for p in problems), problems)

    def test_post_missing_from_sitemap_is_reported(self) -> None:
        """사이트맵이 멈추면(2026-09-08·09-12) 공개된 글이 사이트맵에 없다 — 발행 확인이 그날 잡는다."""
        # 영어판만 사이트맵에 실린다 — 한국어판은 비공개라 워드프레스가 일부러 뺀다(2026-09-16).
        post = {"id": 2, "status": "publish", "modified_gmt": "2026-09-05T12:53:52",
                "link": "https://fermata.it.kr/editorial-us-2026-09-04-en/"}
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "data"; editorial = Path(tmp) / "editorial"; data.mkdir(); editorial.mkdir()
            (data / "price_us_2026-09-04.json").write_text("{}", encoding="utf-8")
            (editorial / "us_2026-09-04.json").write_text(json.dumps({"en": {"title": "Title"}}), encoding="utf-8")
            with mock.patch.object(cp, "DATA_DIR", data), mock.patch.object(cp, "EDITORIAL_DIR", editorial), \
                    mock.patch.object(cp, "_actual_trading_date", return_value="2026-09-04"), \
                    mock.patch.object(cp, "_wordpress_post", return_value=post):
                stale = cp.check_market("us", check_site=True, sitemap_urls={"https://fermata.it.kr/other/"})
                fresh = cp.check_market("us", check_site=True, sitemap_urls={"https://fermata.it.kr/editorial-us-2026-09-04-en"})
                skipped = cp.check_market("us", check_site=True, sitemap_urls=None)
        self.assertTrue(any("사이트맵" in x for x in stale), stale)
        self.assertEqual(fresh, [])
        self.assertEqual(skipped, [])

    def test_missing_post_is_reported(self) -> None:
        problems = self._check("2026-09-04", None)
        self.assertTrue(any("사이트에 글이 없습니다" in p for p in problems), problems)

    def test_missing_manuscript_is_still_the_real_alarm(self) -> None:
        """루틴이 글을 못 쓴 날은 여전히 잡아야 한다 — 이것이 이 워크플로의 존재 이유다."""
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "data"; editorial = Path(tmp) / "editorial"; data.mkdir(); editorial.mkdir()
            (data / "price_us_2026-09-04.json").write_text("{}", encoding="utf-8")
            with mock.patch.object(cp, "DATA_DIR", data), mock.patch.object(cp, "EDITORIAL_DIR", editorial), \
                    mock.patch.object(cp, "_actual_trading_date", return_value="2026-09-04"):
                problems = cp.check_market("us", check_site=True)
        self.assertTrue(any("원고가 없습니다" in p for p in problems), problems)


if __name__ == "__main__":
    unittest.main()
