"""인사이트 스토리 사진이 **사람이 본 사진**에서만 오는지 확인합니다.

2026-09-07까지 발행 워크플로가 Unsplash를 실시간 검색해 첫 결과를 그대로
붙였습니다 — 아무도 보지 않는 유일한 사진 경로였고, 'SK Hynix memory chip'에
로고가 나갔습니다. 이제 경로는 둘뿐입니다: 루틴이 직접 보고 고른 사진(원고의
`image`), 아니면 사람이 미리 승인한 풀. 둘 다 없으면 사진 없이 갑니다.
"""
from __future__ import annotations

import unittest
from unittest import mock

from src import publish_editorial

PRICE = {
    "watchlist": {
        "000660": {"ticker": "000660", "name": "SK하이닉스", "name_en": "SK Hynix",
                   "source": "core", "sector": "반도체"},
        "034020": {"ticker": "034020", "name": "두산에너빌리티", "name_en": "Doosan Enerbility",
                   "source": "core", "sector": "발전·원전"},
        "047040": {"ticker": "047040", "name": "대우건설", "name_en": "Daewoo E&C",
                   "source": "dynamic", "sector": "건설"},
    }
}
POOL = [
    {"id": "semi-a", "file": "assets/photos/a.jpg", "sector": "반도체", "tickers": ["000660"],
     "seen": "웨이퍼", "credit": "사진: A / 플리커 (BY 2.0)", "source_page": "https://x/a"},
    {"id": "semi-b", "file": "assets/photos/b.jpg", "sector": "반도체", "tickers": ["000660"],
     "seen": "칩", "credit": "사진: B / 플리커 (BY 2.0)", "source_page": "https://x/b"},
    {"id": "power-a", "file": "assets/photos/p.jpg", "sector": "발전·원전", "tickers": ["034020"],
     "seen": "원전", "credit": "사진: P / 플리커 (BY 2.0)", "source_page": "https://x/p"},
]


def _attach(stories, exclude=None):
    with mock.patch.object(publish_editorial.photo_pool, "load", return_value=POOL):
        return publish_editorial._attach_story_images(
            {"heading": "인사이트", "stories": stories}, PRICE, "2026-09-07",
            upload=False, exclude_ids=exclude,
        )["stories"]


class InsightPhotoTest(unittest.TestCase):
    def test_routine_chosen_photo_is_kept_as_is(self) -> None:
        """루틴이 눈으로 보고 고른 사진은 발행 단계가 건드리지 않습니다."""
        chosen = {"url": "https://images.unsplash.com/photo-1", "photographer": "Someone",
                  "photographer_url": "https://unsplash.com/@someone"}
        [story] = _attach([{"heading": "h", "body": "b", "image": chosen}])
        self.assertEqual(story["image"], chosen)

    def test_core_stock_query_gets_pool_photo_with_credit(self) -> None:
        [story] = _attach([{"heading": "h", "body": "b", "image_query": "SK Hynix memory chip"}])
        self.assertIsNotNone(story["image"])
        self.assertIn(story["image"]["id"], {"semi-a", "semi-b"})
        self.assertIn("플리커", story["image"]["credit"])  # CC BY 계열은 표기가 의무입니다

    def test_dynamic_stock_gets_no_photo(self) -> None:
        """그날 편입된 종목에는 사진을 붙이지 않습니다(저장소 규칙)."""
        [story] = _attach([{"heading": "h", "body": "b", "image_query": "대우건설 construction"}])
        self.assertIsNone(story["image"])

    def test_abstract_query_gets_no_photo(self) -> None:
        [story] = _attach([{"heading": "h", "body": "b", "image_query": "korean won banknote"}])
        self.assertIsNone(story["image"])

    def test_two_stories_same_sector_do_not_share_a_photo(self) -> None:
        a, b = _attach([
            {"heading": "1", "body": "b", "image_query": "SK Hynix HBM"},
            {"heading": "2", "body": "b", "image_query": "SK Hynix DRAM"},
        ])
        self.assertNotEqual(a["image"]["id"], b["image"]["id"])

    def test_cover_photo_is_not_reused_in_body(self) -> None:
        [story] = _attach([{"heading": "h", "body": "b", "image_query": "Doosan Enerbility"}],
                          exclude={"power-a"})
        self.assertIsNone(story["image"], "표지에 쓴 사진을 본문에 또 붙이면 안 됩니다")

    def test_no_live_search_anywhere(self) -> None:
        """발행 단계에 실시간 사진 검색이 다시 붙지 않았는지 — 코드 수준에서 봅니다."""
        import inspect
        source = inspect.getsource(publish_editorial)
        self.assertNotIn("fetch_images", source)


if __name__ == "__main__":
    unittest.main()
