import unittest

from src.generate_free import _select_diverse_headlines


class NewsSelectionTests(unittest.TestCase):
    def test_rejects_broad_business_words_and_korean_substring_false_positive(self):
        news = [
            {"source": "A", "title": "중소·중견기업 산학협력 지원"},
            {"source": "B", "title": "스타트업 투자 상담 행사 개막"},
            {"source": "C", "title": "핵심광물 재자원화 산업 통계 발표"},
        ]

        self.assertEqual(_select_diverse_headlines(news, market="kr"), [])

    def test_keeps_direct_market_news_and_rotates_publishers(self):
        news = [
            {"source": "연합뉴스", "title": "원·달러 환율 소폭 상승"},
            {"source": "연합뉴스", "title": "삼성전자 소폭 상승 마감"},
            {"source": "이데일리", "title": "빚투 늘며 신용융자 증가"},
            {"source": "이데일리", "title": "스팩 줄상폐 임박"},
            {"source": "한국경제", "title": "코스피 강보합 마감"},
            {"source": "한국경제", "title": "반도체 ETF 투자자 관심"},
        ]

        selected = _select_diverse_headlines(news, market="kr")

        self.assertEqual(
            [item["source"] for item in selected],
            ["연합뉴스", "이데일리", "한국경제", "연합뉴스", "이데일리", "한국경제"],
        )
        self.assertTrue(all("산학협력" not in item["title"] for item in selected))

    def test_ascii_terms_require_word_boundaries(self):
        news = [
            {"source": "A", "title": "Chairman discusses a separate business unit"},
            {"source": "B", "title": "Fed rate outlook moves the stock market"},
        ]

        selected = _select_diverse_headlines(news, market="us")

        self.assertEqual([item["source"] for item in selected], ["B"])


if __name__ == "__main__":
    unittest.main()
