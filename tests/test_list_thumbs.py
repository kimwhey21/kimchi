"""본진 홈·목록 토스피드 3색 판 + 목록용 정사각 썸네일(2026-09-27, 사장님 "썸네일 4번 3색판으로 가자")."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from src import feature_graphics, featured_image, publish_editorial, publish_feature, publish_wordpress

ROOT = Path(__file__).resolve().parent.parent


class SquareThumbTest(unittest.TestCase):
    def test_daily_square_follows_the_cover_layout(self):
        # 가로 표지와 네모 썸네일이 다른 종목을 말하면 안 된다 — 같은 choose_layout을 쓴다.
        for name in ("us_2026-09-22", "kr_2026-09-23"):
            doc = json.loads((ROOT / "editorial" / f"{name}.json").read_text(encoding="utf-8"))
            market, date_str = name[:2], name[3:]
            with tempfile.TemporaryDirectory() as tmp:
                meta = featured_image.create_square(market, date_str, doc["price_data"], Path(tmp) / "s.png",
                                                    doc["ko"], lang="en")
                with Image.open(meta["local_path"]) as image:
                    self.assertEqual(image.size, (600, 600))
            self.assertEqual(meta["layout"], featured_image.choose_layout(doc["price_data"], doc["ko"], date_str))
            self.assertIn("[en, square]", meta["alt"])

    def test_guide_square_uses_the_same_cover_arguments(self):
        doc = json.loads((ROOT / "editorial" / "guides" / "en_korea-market-holidays-2026.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            square = publish_feature._square_thumb(doc, Path(tmp))
            self.assertIsNotNone(square)
            with Image.open(square["local_path"]) as image:
                self.assertEqual(image.size, (600, 600))
        self.assertEqual(set(feature_graphics.SQUARE_OF), {"cover", "guide_cover"})

    def test_korean_documents_get_no_square(self):
        # 한국어 글은 본진에 올라가지 않는다 — 네모 그림도 그리지 않는다.
        self.assertIsNone(publish_feature._square_thumb({"lang": "ko", "graphics": [{"kind": "cover", "featured": True}]},
                                                        Path("/nonexistent")))


class CategoryTest(unittest.TestCase):
    def test_daily_keeps_daily_and_adds_the_market(self):
        # Daily(121)를 빼면 /daily/ 목록·탭·색인 요청 순서가 깨진다.
        self.assertEqual(publish_editorial.DAILY_CATEGORY_ID, 121)
        self.assertEqual(publish_editorial.MARKET_CATEGORY_IDS, {"kr": 684, "us": 685})

    def test_category_list_of_ids_is_not_looked_up(self):
        with mock.patch.object(publish_wordpress, "_get_or_create_term_id") as lookup:
            self.assertEqual(publish_wordpress._category_ids("https://x", ("u", "p"), [121, 684, 121], "en"), [121, 684])
        lookup.assert_not_called()

    def test_square_meta_not_saved_is_an_error(self):
        # 조각 14번이 꺼져 있으면 REST가 메타를 조용히 버린다 — 성공처럼 넘기지 않는다.
        response = mock.Mock(json=lambda: {"meta": {}}, raise_for_status=lambda: None)
        env = {"WORDPRESS_URL": "https://x", "WORDPRESS_USERNAME": "u", "WORDPRESS_APP_PASSWORD": "p"}
        with mock.patch.dict("os.environ", env), \
                mock.patch.object(publish_wordpress, "upload_featured_image", return_value=9), \
                mock.patch.object(publish_wordpress, "_request", return_value=response):
            with self.assertRaises(publish_wordpress.WordPressPublishError):
                publish_wordpress.set_square_thumb(1, {"local_path": "x.png"})


class ListStyleSourceTest(unittest.TestCase):
    SOURCE = (ROOT / "templates" / "wp_list_toss.php").read_text(encoding="utf-8")

    def test_three_colours_and_the_daily_chip_hidden_under_a_market(self):
        for needle in ("li.category-korea-close", "li.category-wall-street-close", "li.category-guides",
                       'a[href$="/category/daily/"]', "register_post_meta", "fermata_square_thumb",
                       "has-fm-sq", "is_page( array( 76, 77, 105 ) )"):
            self.assertIn(needle, self.SOURCE, needle)

    def test_tab_row_still_wraps_on_phones(self):
        # 모바일에서 탭 줄이 두 줄로 접혀야 가로가 넘치지 않는다(CLAUDE.md) — 스타일이 flex-wrap을 덮어쓰면 안 된다.
        self.assertNotIn("flex-wrap:nowrap", self.SOURCE.replace(" ", ""))


if __name__ == "__main__":
    unittest.main()
