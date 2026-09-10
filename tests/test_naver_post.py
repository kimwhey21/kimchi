"""네이버용 원고(요약 + 그림 셋 + 링크) — 2026-09-10 사용자 결정을 고정한다."""
from __future__ import annotations

import unittest
from pathlib import Path

from scripts import naver_post


class BuildTest(unittest.TestCase):
    def test_daily_post_has_take_first_five_sections_and_link(self) -> None:
        post = naver_post.build(Path("editorial/kr_2026-09-10.json"), Path("output/gate/kr_2026-09-10"))
        self.assertTrue(post["title"].startswith("코스피 마감 시황 9월 10일"))
        self.assertEqual(post["category"], "시황")
        heads = [b[1] for b in post["blocks"] if b[0] == "h"]
        self.assertEqual(heads[0], "Fermata's Take")
        self.assertLessEqual(len([h for h in heads if h not in ("Fermata's Take", "다음 확인 지점")]), 5)
        self.assertEqual(post["blocks"][-1][1], "https://fermata.it.kr/editorial-kr-2026-09-10-ko/")
        self.assertIn("코스피", post["tags"])
        self.assertLess(post["chars"], 2600)

    def test_checkpoint_post_goes_to_checkpoint_category(self) -> None:
        post = naver_post.build(Path("editorial/features/kr_2026-09-08_foreign_buying_reversal.json"))
        self.assertEqual(post["category"], "Checkpoint")
        self.assertIn("체크포인트", post["title"])
        self.assertEqual(post["title"].count("체크포인트"), 1)
        self.assertEqual(post["blocks"][-1][1], "https://fermata.it.kr/kr-2026-09-08-foreign-buying-reversal/")


    def test_preview_goes_to_daily_with_a_dated_prefix(self) -> None:
        post = naver_post.build(Path("editorial/previews/us_2026-09-10.json"))
        self.assertEqual(post["category"], "시황")
        self.assertIn("9월 10일", post["title"].split("|")[0] if "|" in post["title"] else post["title"].split(":")[0])
        self.assertTrue(post["blocks"][-1][1].endswith("-preview/"))


if __name__ == "__main__":
    unittest.main()
