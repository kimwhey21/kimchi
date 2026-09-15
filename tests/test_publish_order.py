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

        # 2026-09-15부터 한국어 시황은 워드프레스에 가지 않는다(사용자 결정) — 네이버 블로그 전용이다.
        # 올라가는 것은 영어판뿐이고, 한국어판을 올리려 들면 이 검사가 잡는다.
        self.assertEqual(len(calls), 1, calls)
        self.assertEqual(calls[0].get("lang"), "en")
        self.assertTrue(calls[0]["slug"].endswith("-en"), calls[0]["slug"])
        self.assertFalse(any(str(c.get("slug", "")).endswith("-ko") for c in calls), calls)


class KoreanDailySwitchTest(unittest.TestCase):
    """한국어 시황을 워드프레스에 올릴지는 스위치 하나다(2026-09-15).

    끄는 결정을 코드에서 지우지 않고 스위치로 남긴 이유는, 네이버가 막히거나 생각이 바뀌면
    되돌릴 수 있어야 하기 때문이다. 스위치가 사라지면 되돌리는 길도 사라진다.
    """

    def test_the_switch_exists_and_is_off(self) -> None:
        self.assertFalse(publish_editorial.KO_DAILY_TO_WORDPRESS)


if __name__ == "__main__":
    unittest.main()
