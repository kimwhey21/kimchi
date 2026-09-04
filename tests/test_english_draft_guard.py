"""영어 초안이 한글 종목명 하나로 죽지 않는지 확인합니다.

2026-09-04 한국장이 이것 때문에 통째로 실패했습니다. 그날 거래대금 상위로
편입된 로보티즈·원익홀딩스가 name_en_map에 없어 name_en에 한글이 들어왔고,
영어 초안 검사가 예외를 냈습니다. 그 예외로 프로세스가 죽으면서 이미 받아 둔
시세 파일까지 커밋되지 못했고, 루틴이 읽을 데이터가 없어 글이 나가지 않았습니다.
"""
from __future__ import annotations

import unittest

from src import editorial_quality_en, generate_free_en

PRICE_DATA = {
    "macro": {
        "KS11": {"ticker": "KS11", "name": "코스피", "name_en": "KOSPI",
                  "price": 6687.21, "change_pct": 1.64, "series": [6579.48, 6687.21]},
    },
    "watchlist": {
        "005930": {"ticker": "005930", "name": "삼성전자", "name_en": "Samsung Electronics",
                    "price": 250000.0, "change_pct": 1.2, "series": [247000.0, 250000.0],
                    "source": "core", "foreign_net": 1000, "foreign_ratio": 46.7},
        "030530": {"ticker": "030530", "name": "원익홀딩스", "name_en": "원익홀딩스",
                    "price": 12000.0, "change_pct": 29.91, "series": [9237.0, 12000.0],
                    "source": "dynamic", "foreign_net": -500, "foreign_ratio": 5.0},
    },
    "trading_date": "2026-09-04",
}


class EnglishDraftGuardTest(unittest.TestCase):
    def test_draft_survives_a_stock_without_an_english_name(self) -> None:
        generated = generate_free_en.generate("2026-09-04", PRICE_DATA, recent_news=[])
        editorial_quality_en.validate_generated(generated)  # 예외가 나면 실패
        self.assertNotIn("원익홀딩스", generated["title"])

    def test_named_stocks_still_appear(self) -> None:
        generated = generate_free_en.generate("2026-09-04", PRICE_DATA, recent_news=[])
        text = generated["title"] + " ".join(
            section.get("body", "") for section in generated["narrative"]
        )
        self.assertIn("Samsung Electronics", text)

    def test_korean_edition_keeps_the_stock(self) -> None:
        """영어판에서 빼는 것이지 데이터에서 지우는 것이 아닙니다."""
        filtered = generate_free_en._english_ready(PRICE_DATA)
        self.assertNotIn("030530", filtered["watchlist"])
        self.assertIn("030530", PRICE_DATA["watchlist"])


if __name__ == "__main__":
    unittest.main()
