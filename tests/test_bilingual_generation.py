from __future__ import annotations

import unittest

from src import editorial_quality, editorial_quality_en, generate_free, generate_free_en
from src.render_html import render


def _price_data() -> dict:
    return {
        "trading_date": "2026-09-01",
        "macro": {
            "KS11": {
                "ticker": "KS11",
                "name": "코스피",
                "name_en": "KOSPI",
                "price": 3200.12,
                "change_pct": 0.45,
                "trading_date": "2026-09-01",
            },
            "KQ11": {
                "ticker": "KQ11",
                "name": "코스닥",
                "name_en": "KOSDAQ",
                "price": 810.5,
                "change_pct": -0.31,
                "trading_date": "2026-09-01",
            },
            "USD/KRW": {
                "ticker": "USD/KRW",
                "name": "원/달러 환율",
                "name_en": "USD/KRW",
                "price": 1360.2,
                "change_pct": 0.18,
                "unit": "원",
                "trading_date": "2026-08-31",
            },
        },
        "watchlist": {
            "000660": {
                "ticker": "000660",
                "name": "SK하이닉스",
                "name_en": "SK Hynix",
                "price": 280000,
                "change_pct": 2.6,
            },
            "086520": {
                "ticker": "086520",
                "name": "에코프로",
                "name_en": "Ecopro",
                "price": 95000,
                "change_pct": -3.7,
            },
            "005930": {
                "ticker": "005930",
                "name": "삼성전자",
                "name_en": "Samsung Electronics",
                "price": 85000,
                "change_pct": 0.0,
            },
        },
    }


def _news() -> list[dict]:
    return [
        {"source": "한국경제", "title": "코스피 상승 마감", "link": "https://a.example/1"},
        {"source": "한국경제", "title": "반도체 주식 강세", "link": "https://a.example/2"},
        {"source": "연합뉴스", "title": "원화 환율 하락", "link": "https://b.example/1"},
        {"source": "이데일리", "title": "외국인 수급 점검", "link": "https://c.example/1"},
    ]


class BilingualGenerationTest(unittest.TestCase):
    def test_korean_draft_is_direct_and_source_diverse(self) -> None:
        generated = generate_free.generate("kr", "2026-09-01", _price_data(), _news())
        editorial_quality.validate_generated(generated)

        self.assertEqual(generated["title"], "코스피 0.45% 상승, 에코프로 3.70% 하락")
        self.assertEqual(
            [source["name"] for source in generated["sources"][:3]],
            ["한국경제", "연합뉴스", "이데일리"],
        )
        self.assertNotIn("약세로 닫", str(generated))

    def test_english_draft_is_built_directly_from_same_numbers(self) -> None:
        generated = generate_free_en.generate("2026-09-01", _price_data(), _news())
        editorial_quality_en.validate_generated(generated)

        self.assertEqual(generated["title"], "KOSPI gains 0.45%; Ecopro falls 3.70%")
        self.assertIn("USD/KRW closed at 1,360.2 KRW, up 0.18%", generated["narrative"][0]["body"])
        self.assertEqual(
            [source["name"] for source in generated["sources"][:3]],
            ["The Korea Economic Daily", "Yonhap News Agency", "Edaily"],
        )

        html = render(
            "kr",
            "2026-09-01",
            _price_data(),
            generated,
            lang="en",
            market_label="Korea Market Close",
        )
        self.assertIn('<html lang="en">', html)
        self.assertIn("1,360.2 KRW", html)
        self.assertIn("As of 2026-08-31", html)
        self.assertNotIn("1,360.2원", html)


if __name__ == "__main__":
    unittest.main()
