"""글에 '누가·무엇으로 확인했나'를 싣는다 (2026-09-15, 사용자 승인 "1번 2번 3번 진행").

왜 필요한가
-----------
2026-09-15에 우리 글을 1페이지 경쟁 글과 나란히 읽고 세 가지가 드러났다.

1. `sources`를 원고에 모으고 `source_check`가 개수를 세는데 **화면에는 한 번도 안 실렸다** —
   조사해 놓고 인용을 버리는 꼴이었고, 금융 글에서 구글이 가장 크게 보는 신호를 스스로 지웠다.
2. 언제 기준인지 본문에만 있고 글 어디에도 고정된 자리가 없었다. 상시 글은 그 한 줄이 수명이다.
3. 영어 가이드의 표에도 각주가 `자료: … · Fermata 작성`으로 **한글**로 찍혔다. 관문은 제목·본문만
   보고 그림 속 글자는 못 본다 — `Read`로 그림을 열어 보고서야 찾았다.
"""
from __future__ import annotations

import inspect
import re
import unittest
from pathlib import Path

from src import data_graphics
from src.render_feature import render

ROOT = Path(__file__).resolve().parent.parent

DOC = {
    "checked": "2026-09-15",
    "sources": [{"name": "Interactive Brokers", "title": "KRX Exchange",
                 "url": "https://www.interactivebrokers.com/en/trading/krx-exchange.php"},
                {"name": "Financial Services Commission", "title": "2026 rule change"},
                {"title": "이름 없는 출처는 싣지 않는다"}],
    "ko": {"title": "T", "narrative": [{"heading": "H", "body": "B"}],
           "closing": {"heading": "The takeaway", "body": "C"}},
}


class MethodBlockTest(unittest.TestCase):
    def test_sources_reach_the_page_as_links(self) -> None:
        html = render(DOC, "Investor Guide", lang="en")
        self.assertIn('href="https://www.interactivebrokers.com/en/trading/krx-exchange.php"', html)
        self.assertIn("Financial Services Commission", html)      # 주소 없는 출처도 이름은 싣는다
        self.assertNotIn("이름 없는 출처", html)                    # name이 없으면 뺀다

    def test_the_checked_date_has_a_fixed_place(self) -> None:
        self.assertIn("2026-09-15", render(DOC, "Investor Guide", lang="en"))
        self.assertIn("2026-09-15", render(DOC, "가이드", lang="ko"))

    def test_the_block_speaks_the_language_of_the_article(self) -> None:
        self.assertIn("How we checked", render(DOC, "Investor Guide", lang="en"))
        self.assertIn("확인한 것", render(DOC, "가이드", lang="ko"))

    def test_a_byline_is_always_present_and_can_be_overridden(self) -> None:
        self.assertIn("Fermata", render(DOC, "Investor Guide", lang="en"))
        self.assertIn("Someone Else", render({**DOC, "byline": "Someone Else"}, "가이드", lang="ko"))


class GraphicCreditLanguageTest(unittest.TestCase):
    """그림 각주도 글의 언어를 따라간다. 관문이 못 보는 자리라 여기서 고정한다."""

    def test_credit_switches_language(self) -> None:
        self.assertEqual(data_graphics._credit("KRX", "ko"), "자료: KRX · Fermata 작성")
        self.assertEqual(data_graphics._credit("KRX", "en"), "Source: KRX · Fermata")
        self.assertIn("자료", data_graphics._credit("KRX", "zz"))   # 모르는 언어는 한국어로

    def test_builders_that_write_a_footer_accept_lang(self) -> None:
        for kind in ("fact_table", "number_cards", "price_history", "investor_flows"):
            with self.subTest(kind=kind):
                self.assertIn("lang", inspect.signature(data_graphics.BUILDERS[kind]).parameters)

    def test_build_does_not_pass_lang_to_builders_that_reject_it(self) -> None:
        """넘기면 TypeError로 그날 발행이 통째로 죽는다 — 받는 빌더에만 넘겨야 한다."""
        without = [k for k, fn in data_graphics.BUILDERS.items()
                   if "lang" not in inspect.signature(fn).parameters]
        self.assertTrue(without, "각주 없는 빌더가 하나는 있어야 이 검사가 뜻이 있다")
        source = inspect.getsource(data_graphics.build)
        self.assertIn("signature", source)


class GuideRulesTest(unittest.TestCase):
    """지시문에서 이 두 줄이 빠지면 글이 조용히 옛 꼴로 돌아간다."""

    def test_both_guides_require_a_comparison_table_instead_of_hiding_names(self) -> None:
        for doc in ("routine_guide_ko.md", "routine_guide_en.md"):
            text = (ROOT / "docs" / doc).read_text(encoding="utf-8")
            with self.subTest(doc=doc):
                self.assertIn("비교표는 반드시", text)
                self.assertNotIn("특정 증권사·상품을 추천하지 않습니다.\n", text)

    def test_both_guides_forbid_inventing_first_hand_experience(self) -> None:
        """"직접 확인한 것"은 실제로 연 화면만 쓴다 — 없는 경험을 지어내면 그건 거짓말이다."""
        ko = (ROOT / "docs" / "routine_guide_ko.md").read_text(encoding="utf-8")
        en = (ROOT / "docs" / "routine_guide_en.md").read_text(encoding="utf-8")
        self.assertIn("지어내지 않습니다", ko)
        self.assertIn("없는 경험", ko)
        self.assertIn("지어내지 않습니다", en)


if __name__ == "__main__":
    unittest.main()
