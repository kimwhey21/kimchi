from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from src.featured_image import create


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


if __name__ == "__main__":
    unittest.main()
