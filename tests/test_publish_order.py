"""영어판을 한국어판보다 먼저 올린다 (2026-09-09, 사용자 승인).

홈·전체 목록의 히어로(맨 위 큰 자리)는 가장 최근 글이다. 한국어판 몇 초 뒤에 나가던
영어판이 그 자리를 차지했다(2026-09-08 /all/ 실측). 영어판이 먼저 나가면 한국어판이
늘 최신 글이 된다. 두 발행은 서로의 결과를 쓰지 않으므로 순서만 고정한다.
"""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from src import publish_editorial, publish_wordpress

ROOT = Path(__file__).resolve().parent.parent
MANUSCRIPT = ROOT / "editorial" / "kr_2026-09-08.json"


class PublishOrderTest(unittest.TestCase):
    @patch.object(publish_editorial, "KO_DAILY_TO_WORDPRESS", True)   # 스위치를 켰을 때의 순서(2026-09-26부터 기본은 꺼짐)
    def test_english_goes_out_before_korean(self) -> None:
        calls: list[dict] = []

        def fake_publish_draft(title, html, **kwargs):
            calls.append({"title": title, **kwargs})
            return {"id": len(calls), "link": f"https://example.com/{kwargs.get('slug')}/"}

        env = {"WORDPRESS_URL": "https://example.com", "WORDPRESS_USERNAME": "u",
               "WORDPRESS_APP_PASSWORD": "p"}
        with patch.dict(os.environ, env), \
             patch.object(publish_wordpress, "publish_draft", side_effect=fake_publish_draft), \
             patch.object(publish_wordpress, "verify_published"), \
             patch.object(publish_wordpress, "upload_image_url", return_value="https://example.com/g.png"), \
             patch.object(publish_wordpress, "_find_existing_post_by_slug", return_value=None):
            publish_editorial.publish(MANUSCRIPT, publish_live=True)

        # 2026-09-16부터 한국어 시황도 다시 본진에 올라간다 — 단 **비공개**로(사용자 지시).
        # 영어가 먼저, 한국어가 나중이라야 한국어판이 늘 최신 글이 된다.
        self.assertEqual(len(calls), 2, calls)
        self.assertEqual(calls[0].get("lang"), "en")
        self.assertEqual(calls[0].get("status"), "publish")
        self.assertTrue(calls[0]["slug"].endswith("-en"), calls[0]["slug"])
        self.assertTrue(calls[1]["slug"].endswith("-ko"), calls[1]["slug"])
        self.assertEqual(calls[1].get("status"), "private")


class KoreanOffWordPressTest(unittest.TestCase):
    """2026-09-26부터 한국어 글은 본진에 올리지 않는다(사장님: "워드프레스에 비공개로 올라가는 한국어 컨탠츠를 지워도 되냐?" →
    "확인못한거 확인하고 문제없으면 둘다 진행해"). 비공개로 두던 이유(9/16, 네이버 사본이 세 절을 빠뜨림)는 네이버가 원고를
    빠짐없이 옮기게 되며 사라졌다. 영어 시황은 그대로 공개로 올라가야 한다."""

    def test_default_is_off_and_english_still_goes_out(self) -> None:
        self.assertFalse(publish_editorial.KO_DAILY_TO_WORDPRESS)
        calls: list[dict] = []

        def fake_publish_draft(title, html, **kwargs):
            calls.append({"title": title, **kwargs})
            return {"id": len(calls), "link": f"https://example.com/{kwargs.get('slug')}/"}

        env = {"WORDPRESS_URL": "https://example.com", "WORDPRESS_USERNAME": "u", "WORDPRESS_APP_PASSWORD": "p"}
        with patch.dict(os.environ, env), \
             patch.object(publish_wordpress, "publish_draft", side_effect=fake_publish_draft), \
             patch.object(publish_wordpress, "verify_published"), \
             patch.object(publish_wordpress, "upload_image_url", return_value="https://example.com/g.png") as upload, \
             patch.object(publish_wordpress, "_find_existing_post_by_slug", return_value=None):
            publish_editorial.publish(ROOT / "editorial" / "kr_2026-09-22.json", publish_live=True)   # 영어 그림이 있는 원고
        self.assertEqual([c["slug"] for c in calls], ["editorial-kr-2026-09-22-en"])
        self.assertEqual(calls[0].get("status"), "publish")
        captions = [c.args[0].get("caption", "") for c in upload.call_args_list if c.args]
        self.assertTrue(any("Data graphic" in x for x in captions), captions)                  # 영어 그림은 올린다
        self.assertFalse([x for x in captions if "데이터 그래픽" in x], captions)              # 한국어 그림은 안 올린다

    def test_feature_series_in_korean_skip_wordpress(self) -> None:
        from src import publish_feature
        self.assertFalse(publish_feature.KO_TO_WORDPRESS)
        for series in ("프리뷰", "기준표", "가이드", "주간 결산", "다음 주 일정", "이벤트"):
            self.assertTrue(publish_feature._skips_wordpress({"series": series}), series)
        self.assertFalse(publish_feature._skips_wordpress({"series": "Guide", "lang": "en"}))   # 영어 가이드는 공개 그대로
        with patch.object(publish_feature, "KO_TO_WORDPRESS", True):
            self.assertFalse(publish_feature._skips_wordpress({"series": "기준표"}))


class KoreanDailySwitchTest(unittest.TestCase):
    """한국어 시황은 본진에 **비공개**로 올라간다(2026-09-16, 사용자 지시).

    2026-09-15에 아예 안 올리게 껐다가 하루 만에 되돌렸다. 끄고 보니 본진에만 있던
    `outlook`·`insight_section`·`sources`가 아무 데도 실리지 않았다 — 네이버로 옮기는 코드가
    그 셋을 처음부터 집어 가지 않았는데, 본진이 공개였을 때는 거기서 읽혀 손해가 안 보였다.
    비공개로 두는 이유는 네이버에 전문이 올라가기 때문이다(두 곳 공개 = 유사문서 위험).
    """

    def test_korean_daily_goes_to_wordpress_as_private(self) -> None:
        # 스위치를 다시 켜면 비공개로 올라가야 한다(2026-09-26부터 기본은 꺼짐 — KoreanOffWordPressTest).
        self.assertEqual(publish_editorial.KO_DAILY_STATUS, "private")
        self.assertEqual(publish_editorial.ko_daily_status(True), "private")
        # 수동 실행은 종전대로 임시저장이다 — 이 기본값을 바꾸지 말 것.
        self.assertEqual(publish_editorial.ko_daily_status(False), "draft")


if __name__ == "__main__":
    unittest.main()
