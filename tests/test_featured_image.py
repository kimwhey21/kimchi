from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from src.featured_image import create, lead_watchlist_entry


class FeaturedImageTest(unittest.TestCase):
    def test_creates_wordpress_ready_png(self) -> None:
        price_data = {
            "macro": {
                "KS11": {
                    "name": "코스피",
                    "name_en": "KOSPI",
                    "price": 3200.12,
                    "change_pct": 0.45,
                },
                "KQ11": {
                    "name": "코스닥",
                    "name_en": "KOSDAQ",
                    "price": 810.5,
                    "change_pct": -0.31,
                },
                "USD/KRW": {
                    "name": "원/달러 환율",
                    "name_en": "USD/KRW",
                    "price": 1360.2,
                    "change_pct": 0.18,
                    "unit": "원",
                },
            },
            "watchlist": {
                "086520": {
                    "name": "에코프로",
                    "name_en": "Ecopro",
                    "change_pct": -3.7,
                }
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "featured.png"
            metadata = create("kr", "2026-09-01", price_data, output)
            with Image.open(output) as image:
                self.assertEqual(image.size, (1200, 630))
                self.assertEqual(image.format, "PNG")
            self.assertEqual(metadata["local_path"], str(output))

    def test_largest_move_includes_dynamic_tier(self) -> None:
        """대문에 거는 종목은 편입 종목까지 포함해 그날 등락 폭 1위입니다.

        라벨이 "LARGEST WATCHLIST MOVE"이므로 워치리스트에 더 크게 움직인
        종목이 있는데 다른 종목을 걸면 라벨이 사실과 어긋납니다.
        """
        price_data = {
            "macro": {
                "KS11": {"name": "코스피", "name_en": "KOSPI", "price": 6579.48, "change_pct": 0.26},
            },
            "watchlist": {
                "105560": {
                    "name": "KB금융",
                    "name_en": "KB Financial Group",
                    "change_pct": 5.2,
                    "source": "core",
                },
                "010140": {
                    "name": "삼성중공업",
                    "name_en": "Samsung Heavy Industries",
                    "change_pct": 8.58,
                    "source": "dynamic",
                },
            },
        }
        lead = lead_watchlist_entry(price_data)
        self.assertEqual(lead["name"], "삼성중공업")
        self.assertNotEqual(lead["name_en"], lead["name"])
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "featured.png"
            metadata = create("kr", "2026-09-03", price_data, output)
            self.assertTrue(output.exists())
        # alt에 대문 종목이 들어가야 합니다. publish_wordpress가 이 alt로 기존
        # 대표 이미지를 재사용할지 판단하기 때문에, 빠지면 지수 값이 같은 날
        # 옛 이미지가 그대로 남습니다.
        self.assertIn("Samsung Heavy Industries", metadata["alt"])
        self.assertIn("+8.58%", metadata["alt"])

    def test_skips_stock_without_english_name(self) -> None:
        """영문 표기가 없으면 대문에 두부 상자(□□□□)가 찍힙니다 — 건너뜁니다."""
        price_data = {
            "macro": {},
            "watchlist": {
                "105560": {
                    "name": "KB금융",
                    "name_en": "KB Financial Group",
                    "change_pct": 5.2,
                    "source": "core",
                },
                "010140": {
                    # name_en_map에 없어 한글 이름이 그대로 들어온 편입 종목
                    "name": "삼성중공업",
                    "name_en": "삼성중공업",
                    "change_pct": 8.58,
                    "source": "dynamic",
                },
            },
        }
        self.assertEqual(lead_watchlist_entry(price_data)["name"], "KB금융")


if __name__ == "__main__":
    unittest.main()
