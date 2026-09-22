"""성적표 주소를 네이버 글로 채우고 갈아 끼우는 규칙 (2026-09-15).

두 가지 일을 한다. 새로 만든 항목은 주소가 비어 있으니 `key`로 채우고, 본진 글을 비공개로
돌린 갈래(시황·프리뷰·Checkpoint)는 이미 적힌 fermata.it.kr 주소를 네이버 주소로 바꾼다.
바꾸지 않으면 `publish_scoreboard.only_live`가 404를 보고 그 항목을 통째로 뺀다 — 판정을
지우지 않겠다고 만든 성적표에서 글이 사라진다.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts import scoreboard_naver_urls as mod


class NaverUrlsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(self.enterContext(__import__("tempfile").TemporaryDirectory()))
        (self.root / "editorial" / "features").mkdir(parents=True)
        (self.root / "editorial" / "guides").mkdir(parents=True)
        (self.root / "editorial" / "kr_2026-09-15.json").write_text(
            json.dumps({"market": "kr", "date": "2026-09-15"}), encoding="utf-8")
        (self.root / "editorial" / "features" / "kr_2026-09-13_kospi_per_range.json").write_text(
            json.dumps({"series": "기준표", "slug": "kr-2026-09-13-kospi-per-range"}), encoding="utf-8")
        (self.root / "editorial" / "guides" / "ko_isa-vs-pension-accounts.json").write_text(
            json.dumps({"series": "가이드", "slug": "isa-vs-pension-accounts"}), encoding="utf-8")
        self.posted = {
            "editorial/kr_2026-09-15.json": {"logNo": "111"},
            "editorial/features/kr_2026-09-13_kospi_per_range.json": {"logNo": "222"},
            "editorial/guides/ko_isa-vs-pension-accounts.json": {"logNo": "333"},
        }

    def test_guides_are_naver_only_too(self) -> None:
        """2026-09-22부터 가이드도 본진 비공개·네이버 전문이다 — 주소를 네이버로 바꾼다(2026-09-15에는 그대로 뒀었다)."""
        keys, slugs = mod.naver_urls(self.posted, root=self.root)
        self.assertEqual(slugs["isa-vs-pension-accounts"], "https://blog.naver.com/fermata49/333")
        self.assertIn("kr-2026-09-13-kospi-per-range", slugs)
        self.assertEqual(keys["kr_2026-09-15"], "https://blog.naver.com/fermata49/111")
        self.assertEqual(slugs["editorial-kr-2026-09-15-ko"], "https://blog.naver.com/fermata49/111")

    def test_empty_url_is_filled_by_key(self) -> None:
        keys, slugs = mod.naver_urls(self.posted, root=self.root)
        rows = [{"key": "kr_2026-09-15", "url": ""}]
        mod.fill(rows, keys, slugs)
        self.assertEqual(rows[0]["url"], "https://blog.naver.com/fermata49/111")

    def test_private_wordpress_url_is_swapped_for_the_naver_one(self) -> None:
        keys, slugs = mod.naver_urls(self.posted, root=self.root)
        rows = [
            {"url": "https://fermata.it.kr/kr-2026-09-13-kospi-per-range/"},
            {"url": "https://fermata.it.kr/editorial-kr-2026-09-15-ko/"},
            {"url": "https://fermata.it.kr/isa-vs-pension-accounts/"},          # 가이드 — 2026-09-22부터 바꾼다
            {"url": "https://blog.naver.com/fermata49/999"},                    # 이미 네이버 — 그대로
        ]
        mod.fill(rows, keys, slugs)
        self.assertEqual(rows[0]["url"], "https://blog.naver.com/fermata49/222")
        self.assertEqual(rows[1]["url"], "https://blog.naver.com/fermata49/111")
        self.assertEqual(rows[2]["url"], "https://blog.naver.com/fermata49/333")
        self.assertEqual(rows[3]["url"], "https://blog.naver.com/fermata49/999")


if __name__ == "__main__":
    unittest.main()
