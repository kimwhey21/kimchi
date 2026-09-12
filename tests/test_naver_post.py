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
        self.assertEqual(post["blocks"][-3][1], "https://fermata.it.kr/editorial-kr-2026-09-10-ko/")   # 마지막 둘은 텔레그램 안내(2026-09-12)
        self.assertIn("코스피", post["tags"])
        self.assertLess(post["chars"], 2600)

    def test_paragraphs_are_short_and_take_is_a_quotation(self) -> None:
        """2026-09-12: 모바일에서 문단이 벽처럼 읽혀 2~3문장으로 자르고, Fermata's Take는 인용구(q)로, 표지는 맨 앞."""
        post = naver_post.build(Path("editorial/kr_2026-09-10.json"), Path("output/gate/kr_2026-09-10"))
        kinds = [b[0] for b in post["blocks"]]
        self.assertIn("q", kinds)
        self.assertLess(kinds.index("h"), kinds.index("q"))
        for kind, text in post["blocks"]:
            if kind == "p":
                self.assertLessEqual(len(naver_post._SENTENCE.split(text)), 3, text)
                self.assertLessEqual(len(text), 300, text)
        self.assertEqual(naver_post._chunks(["하나입니다. 둘입니다. 셋입니다. 넷입니다."]), ["하나입니다. 둘입니다. 셋입니다.", "넷입니다."])

    def test_cover_comes_first_when_present(self) -> None:
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        for name in ("01-cover.png", "02-number_cards.png"):
            (tmp / name).write_bytes(b"png")
        post = naver_post.build(Path("editorial/features/kr_2026-09-08_foreign_buying_reversal.json"), tmp)
        self.assertEqual(post["blocks"][0], ("img", str(tmp / "01-cover.png")))

    def test_checkpoint_post_goes_to_checkpoint_category(self) -> None:
        post = naver_post.build(Path("editorial/features/kr_2026-09-08_foreign_buying_reversal.json"))
        self.assertEqual(post["category"], "Checkpoint")
        self.assertIn("체크포인트", post["title"])
        self.assertEqual(post["title"].count("체크포인트"), 1)
        self.assertEqual(post["blocks"][-3][1], "https://fermata.it.kr/kr-2026-09-08-foreign-buying-reversal/")   # 마지막 둘은 텔레그램 안내(2026-09-12)


    def test_preview_goes_to_daily_with_a_dated_prefix(self) -> None:
        post = naver_post.build(Path("editorial/previews/us_2026-09-10.json"))
        self.assertEqual(post["category"], "시황")
        self.assertIn("9월 10일", post["title"].split("|")[0] if "|" in post["title"] else post["title"].split(":")[0])
        self.assertTrue(post["blocks"][-3][1].endswith("-preview/"))


if __name__ == "__main__":
    unittest.main()


class TelegramFooterTest(unittest.TestCase):
    def test_every_summary_ends_with_the_channel_link(self) -> None:
        import json
        import tempfile
        doc = {"market": "kr", "date": "2026-09-11", "ko": {"title": "제목", "narrative": [{"heading": "1. 절", "body": "본문."}],
                                                        "closing": {"heading": "Fermata's Take", "body": "판단."}}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "kr_2026-09-11.json"
            path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            post = naver_post.build(path)
        self.assertEqual(post["blocks"][-1], ("p", "https://t.me/fermata_kr"))
        self.assertIn("텔레그램", post["blocks"][-2][1])

