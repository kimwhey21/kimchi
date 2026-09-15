"""네이버용 원고 — 2026-09-10 사용자 결정을 고정한다.

2026-09-15에 시황이 갈라졌다. 기준표·가이드는 그대로 **요약 + 그림 셋 + 링크**지만, 한국어 시황은
네이버가 유일한 공개처가 되면서 **본문 전문, 링크 없음**이다. 본진에 쌍둥이가 없으니 겹칠 일도,
가리킬 글도 없다.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from scripts import naver_post


class BuildTest(unittest.TestCase):
    def test_daily_post_is_the_full_article_with_no_link(self) -> None:
        """시황은 네이버가 유일한 공개처다(2026-09-15, 사용자 결정) — 축약본이 아니라 본문 전문이다.

        링크를 넣지 않는 이유는 둘이다. 가리킬 본진 글이 없고, 네이버는 밖으로 나가는 링크가 붙은
        글을 좋게 보지 않는다. 이 검사가 풀리면 요약본 시절로 조용히 되돌아간다.
        """
        post = naver_post.build(Path("editorial/kr_2026-09-10.json"), Path("output/gate/kr_2026-09-10"))
        self.assertTrue(post["title"].startswith("코스피 마감 시황 9월 10일"))
        self.assertEqual(post["category"], "시황")
        self.assertEqual(post["url"], "")
        heads = [b[1] for b in post["blocks"] if b[0] == "h"]
        self.assertEqual(heads[0], "Fermata's Take")
        self.assertGreater(len(heads), 5)                       # 전문이라 절이 다 들어온다
        self.assertFalse(any("fermata.it.kr" in b[1] for b in post["blocks"]), post["blocks"][-4:])
        self.assertFalse(any("페르마타 블로그" in b[1] for b in post["blocks"]))
        self.assertIn("코스피", post["tags"])
        self.assertGreater(post["chars"], 2600)

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
        # 본진 링크가 없어진 뒤에도 텔레그램 안내는 남아야 한다(2026-09-15) — 우리 채널이지
        # 남의 글로 보내는 링크가 아니다. 전에는 `if url:` 안에 들어 있어 같이 사라졌다.
        self.assertEqual(post["url"], "")
        self.assertEqual(post["blocks"][-1], ("p", "https://t.me/fermata_kr"))
        self.assertIn("텔레그램", post["blocks"][-2][1])

