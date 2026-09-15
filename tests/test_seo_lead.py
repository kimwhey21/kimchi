"""검색 결과 설명문 첫 문장(2026-09-08, 사용자 승인).

제목에 검색어 접미어를 붙이는 안은 보기 싫다는 판단으로 접었다. 대신 설명문(발췌문)의
첫 문장에 날짜와 검색어를 넣는다 — 글 화면 제목은 그대로다.
"""
from __future__ import annotations

import unittest

from src import publish_editorial, publish_feature


class SeoLeadTest(unittest.TestCase):
    def test_daily_lead_names_the_market_and_date(self) -> None:
        self.assertEqual(publish_editorial._seo_lead("kr", "2026-09-08"), "9월 8일 코스피 마감 시황입니다. ")
        self.assertEqual(publish_editorial._seo_lead("us", "2026-09-04"), "9월 4일 뉴욕증시 마감 시황입니다. ")
        self.assertEqual(publish_editorial._seo_lead("kr", "2026-09-08", "en"), "KOSPI close for September 8, 2026. ")

    def test_excerpt_keeps_the_lead_and_truncates_the_body(self) -> None:
        doc = {"narrative": [{"body": "가 " * 300}]}
        text = publish_editorial._excerpt(doc, limit=300, lead=publish_editorial._seo_lead("kr", "2026-09-08"))
        self.assertTrue(text.startswith("9월 8일 코스피 마감 시황입니다. 가"))
        self.assertTrue(text.endswith("…"))
        self.assertLessEqual(len(text), 302)

    def test_preview_lead_only_for_the_preview_series(self) -> None:
        self.assertEqual(publish_feature._seo_lead({"series": "프리뷰", "date": "2026-09-08"}), "9월 8일 밤 미국장 프리뷰입니다. ")
        self.assertEqual(publish_feature._seo_lead({"series": "기준표", "date": "2026-09-06"}), "")
        ko = {"narrative": [{"body": "오늘 밤은 유가입니다."}]}
        self.assertEqual(publish_feature._excerpt(ko, lead="9월 8일 밤 미국장 프리뷰입니다. "), "9월 8일 밤 미국장 프리뷰입니다. 오늘 밤은 유가입니다.")


if __name__ == "__main__":
    unittest.main()
