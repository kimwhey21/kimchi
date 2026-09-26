"""네이버용 원고 — 2026-09-10 사용자 결정을 고정한다.

2026-09-15에 시황이 먼저 **본문 전문, 링크 없음**이 됐고(본진 비공개), 2026-09-22에 가이드·주간·이벤트까지
같은 꼴이 됐다(사장님: "워드프레스 링크가 붙는 컨텐츠에 링크를 모두 빼고 본문을 공개하고, 본진에서는 비공개
처리해라"). 이제 한국어 글은 전부 본진 글 그대로이고 본진 링크는 어디에도 없다. 잡지는 원래부터 그랬다.
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
        # 네이버 제목은 본진 제목 그대로다(2026-09-17, 사장님: "날짜 시황 제목 앞에 쓰는거 삭제").
        import json as _json
        self.assertEqual(post["title"], _json.loads(Path("editorial/kr_2026-09-10.json").read_text(encoding="utf-8"))["ko"]["title"])
        self.assertEqual(post["category"], "시황")
        self.assertEqual(post["url"], "")
        heads = [b[1] for b in post["blocks"] if b[0] == "h"]
        # 전문을 싣는 글은 본진(`templates/post.html.j2`)과 같은 차례다 — Fermata's Take가 맨 아래,
        # 그 뒤가 다음 확인 지점이다(2026-09-15, 사용자: "본문 형식으로 바꾸면 테이크가 맨 아래로 가는거 아니었니").
        # 맨 위로 올리면 요약본 꼴로 되돌아간다.
        self.assertNotEqual(heads[0], "Fermata's Take")
        # 본진 `templates/post.html.j2`와 같은 차례다(2026-09-16, 사용자: "본진 글을 똑같이 옮기기만 해라").
        self.assertEqual(heads[-3:], ["Fermata's Take", "다음 확인 지점", "자료 확인"])
        self.assertGreater(len(heads), 5)                       # 전문이라 절이 다 들어온다
        self.assertFalse(any("fermata.it.kr" in b[1] for b in post["blocks"]), post["blocks"][-4:])
        self.assertFalse(any("페르마타 블로그" in b[1] for b in post["blocks"]))
        self.assertIn("코스피", post["tags"])
        self.assertGreater(post["chars"], 2600)

    def test_paragraphs_are_short_and_guides_are_full_body_too(self) -> None:
        """2026-09-12: 모바일에서 문단이 벽처럼 읽혀 2~3문장으로 자른다.

        인용구(q) Take는 요약본 시절의 규칙이었다. 2026-09-22부터 가이드·주간·이벤트도 전문이라 인용구 Take가
        없고, Fermata's Take는 본진 차례대로 맨 아래다(사장님: "링크를 모두 빼고 본문을 공개").
        """
        post = naver_post.build(Path("editorial/guides/ko_isa-vs-pension-accounts.json"))
        kinds = [b[0] for b in post["blocks"]]
        self.assertNotIn("q", kinds)
        heads = [b[1] for b in post["blocks"] if b[0] == "h"]
        self.assertIn("Fermata's Take", heads)
        self.assertGreater(heads.index("Fermata's Take"), 3)          # 절들 뒤에 온다
        self.assertEqual(post["url"], "")
        self.assertFalse(any("fermata.it.kr" in b[1] for b in post["blocks"]))
        self.assertFalse(any("페르마타 블로그" in b[1] for b in post["blocks"]))
        daily = naver_post.build(Path("editorial/kr_2026-09-10.json"), Path("output/gate/kr_2026-09-10"))
        for kind, text in daily["blocks"]:
            if kind == "p":
                self.assertLessEqual(len(naver_post._SENTENCE.split(text)), 3, text)
                self.assertLessEqual(len(text), 300, text)
        self.assertNotIn("q", [b[0] for b in daily["blocks"]])   # 전문에는 인용구 Take가 없다
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
        import json as _json
        base = _json.loads(Path("editorial/features/kr_2026-09-08_foreign_buying_reversal.json").read_text(encoding="utf-8"))["ko"]["title"]
        self.assertEqual(post["title"], base)          # 꼬리표 `| 투자 체크포인트`를 붙이지 않는다(2026-09-17)
        # Checkpoint도 2026-09-15부터 본문 전문·링크 없음이다(사용자: "체크포인트는 2번") — 본진 글을
        # 비공개로 돌렸으니 가리킬 공개 주소가 없다. 2026-09-22부터 텔레그램 안내도 없다 — 외부 링크 0.
        self.assertEqual(post["url"], "")
        self.assertFalse(any("fermata.it.kr" in b[1] for b in post["blocks"]), post["blocks"][-4:])
        heads = [b[1] for b in post["blocks"] if b[0] == "h"]
        self.assertEqual(heads[-1], "Fermata's Take")
        self.assertFalse(any("t.me" in b[1] for b in post["blocks"]))


    def test_preview_goes_to_daily_with_a_dated_prefix(self) -> None:
        post = naver_post.build(Path("editorial/previews/us_2026-09-10.json"))
        self.assertEqual(post["category"], "시황")
        import json as _json
        self.assertEqual(post["title"], _json.loads(Path("editorial/previews/us_2026-09-10.json").read_text(encoding="utf-8"))["ko"]["title"])
        # 2026-09-15부터 프리뷰도 링크 없이 본문 전문으로 나간다(사용자 지시) — 옛 규칙은
        # 마지막에서 세 번째 블록이 본진 주소였다. 지금은 텔레그램 안내 둘로 끝난다.
        self.assertEqual(post["url"], "")
        self.assertFalse(any("fermata.it.kr" in b[1] for b in post["blocks"]))


class PreviewFullBodyTest(unittest.TestCase):
    """프리뷰도 네이버에는 본문 전문을 싣고 본진 링크를 빼 준다(2026-09-15, 사용자 지시).

    시황과 같은 처리다. 다만 프리뷰는 본진에도 그대로 올라가므로 **같은 글이 두 곳에 남는다** —
    네이버가 유사문서로 걸러 낼 위험이 시황 때와 같은 자리에 생긴다. 그 판단은 사용자 몫이고,
    여기서는 지시대로 링크가 빠지고 전문이 실리는 것만 고정한다.
    """

    def _post(self):
        import json
        import tempfile
        doc = {"kind": "feature", "series": "프리뷰", "date": "2026-09-11",
               "slug": "us-2026-09-11-preview",
               "ko": {"title": "오늘 밤 확인할 세 가지",
                      "narrative": [{"heading": f"{i}. 절", "body": "본문입니다."} for i in range(1, 6)],
                      "closing": {"heading": "Fermata's Take", "body": "판단입니다."}}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "us_2026-09-11.json"
            path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            return naver_post.build(path)

    def test_no_link_and_no_dangling_pointer_to_the_main_site(self) -> None:
        post = self._post()
        self.assertEqual(post["url"], "")
        self.assertFalse(any("fermata.it.kr" in b[1] for b in post["blocks"]), post["blocks"][-4:])
        self.assertFalse(any("페르마타 블로그" in b[1] for b in post["blocks"]))

    def test_the_whole_body_goes_out_not_a_summary(self) -> None:
        heads = [b[1] for b in self._post()["blocks"] if b[0] == "h"]
        self.assertGreaterEqual(len([h for h in heads if h.endswith("절")]), 5)

    def test_no_external_link_at_all(self) -> None:
        """2026-09-22 "a b 진행해": 텔레그램 안내도 뺐다 — 네이버 글에 외부 링크가 하나도 없어야 한다.

        2026-09-15에는 본진 링크를 빼면서 텔레그램은 남겼다. 9/22 조사에서 52편 전부가 같은 문장 + t.me 링크로
        끝나는 것이 잡지(외부 링크 0, 검색됨)와 다른 점이라 뺐다.
        """
        post = self._post()
        self.assertFalse(any("http" in b[1] for b in post["blocks"] if b[0] == "p"), post["blocks"][-3:])
        self.assertFalse(any("텔레그램" in b[1] for b in post["blocks"]))


if __name__ == "__main__":
    unittest.main()


class NoFooterLinkTest(unittest.TestCase):
    def test_a_post_ends_with_its_own_content_not_a_link(self) -> None:
        import json
        import tempfile
        doc = {"market": "kr", "date": "2026-09-11", "ko": {"title": "제목", "narrative": [{"heading": "1. 절", "body": "본문."}],
                                                        "closing": {"heading": "Fermata's Take", "body": "판단."}}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "kr_2026-09-11.json"
            path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            post = naver_post.build(path)
        # 2026-09-22: 본진 링크도 텔레그램 링크도 없다. 마지막 블록은 글 자체(Take·확인 지점·자료 확인)다.
        self.assertEqual(post["url"], "")
        self.assertFalse(any("t.me" in b[1] or "fermata.it.kr" in b[1] for b in post["blocks"]))
        self.assertEqual(post["blocks"][-1][0], "p")
        self.assertIn("판단", post["blocks"][-1][1])



class PhotoCoverTest(unittest.TestCase):
    """원고의 Unsplash 사진(`00-photo-cover.jpg`, naver_sync.render가 내려받는다)이 cover 그래픽보다 앞이다(2026-09-26)."""

    def test_photo_cover_beats_graphic_cover(self) -> None:
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        for name in ("00-photo-cover.jpg", "01-cover.png", "02-number_cards.png"):
            (tmp / name).write_bytes(b"x")
        post = naver_post.build(Path("editorial/features/kr_2026-09-08_foreign_buying_reversal.json"), tmp)
        imgs = [b[1] for b in post["blocks"] if b[0] == "img"]
        self.assertEqual(imgs[0], str(tmp / "00-photo-cover.jpg"))
        self.assertEqual(imgs[1], str(tmp / "01-cover.png"))       # 남색·베이지 틀은 사진 다음에 그대로 간다(사장님 2026-09-26)
        self.assertEqual(imgs.count(str(tmp / "01-cover.png")), 1)
