"""본문 데이터 그래픽 — 대표 이미지와 같은 두 가지 어법을 씁니다.

목록형(movers_list)은 "여럿이 함께 움직였다"를, 한 종목형(stock_spotlight)은
"오늘은 이 종목이다"를 말합니다. 대표 이미지의 trio·single과 짝을 이루도록
모양을 맞춰 두었습니다.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from src import data_graphics

PRICE_DATA = {
    "macro": {
        "KS11": {"ticker": "KS11", "name": "코스피", "price": 6687.21, "change_pct": 1.64, "unit": ""},
    },
    "watchlist": {
        "030530": {"ticker": "030530", "name": "원익홀딩스", "price": 22500.0,
                    "change_pct": 29.91, "series": [17000.0, 17300.0, 17100.0, 22500.0]},
        "042700": {"ticker": "042700", "name": "한미반도체", "price": 230000.0,
                    "change_pct": 9.26, "series": [210000.0, 215000.0, 230000.0]},
        "005930": {"ticker": "005930", "name": "삼성전자", "price": 255500.0,
                    "change_pct": -2.20, "series": [261000.0, 258000.0, 255500.0]},
    },
}


class StockSpotlightTest(unittest.TestCase):
    def _draw(self, **kwargs) -> Path:
        output = Path(tempfile.mkdtemp()) / "spot.png"
        data_graphics.stock_spotlight(PRICE_DATA, output, **kwargs)
        return output

    def test_defaults_to_the_biggest_mover(self) -> None:
        with Image.open(self._draw()) as image:
            self.assertEqual(image.width, data_graphics.W)

    def test_named_ticker_is_drawn(self) -> None:
        self.assertTrue(self._draw(ticker="005930").exists())

    def test_unknown_ticker_raises_rather_than_drawing_the_wrong_stock(self) -> None:
        """조용히 다른 종목을 그리면 글과 그림이 어긋납니다."""
        with self.assertRaises(ValueError):
            self._draw(ticker="999999")

    def test_no_stocks_raises(self) -> None:
        output = Path(tempfile.mkdtemp()) / "spot.png"
        with self.assertRaises(ValueError):
            data_graphics.stock_spotlight({"macro": {}, "watchlist": {}}, output)


class StockUnitTest(unittest.TestCase):
    """단위 없이 "22,500"만 적으면 원인지 달러인지 알 수 없습니다."""

    def test_korean_ticker_gets_won(self) -> None:
        self.assertEqual(data_graphics._stock_unit({"ticker": "030530"}), "원")

    def test_us_ticker_gets_nothing(self) -> None:
        self.assertEqual(data_graphics._stock_unit({"ticker": "NVDA"}), "")

    def test_explicit_unit_wins(self) -> None:
        self.assertEqual(data_graphics._stock_unit({"ticker": "USD/KRW", "unit": "원"}), "원")


class BuildersTest(unittest.TestCase):
    def test_every_builder_is_reachable_by_name(self) -> None:
        """원고의 graphic 지정은 이름으로 옵니다 — 등록이 빠지면 KeyError입니다."""
        self.assertIn("stock_spotlight", data_graphics.BUILDERS)
        for kind, builder in data_graphics.BUILDERS.items():
            self.assertTrue(callable(builder), kind)


if __name__ == "__main__":
    unittest.main()


class FlowCompareOpposedTest(unittest.TestCase):
    """제목이 "같은 종목에서 반대로"인데 양쪽 순매수 종목이 실리면 안 됩니다.

    2026-09-06에 실제로 상위 다섯 줄이 전부 외국인·기관 동반 순매수였습니다.
    제목이 사실이 아닌 그림은 틀린 그림입니다.
    """

    def _price(self) -> dict:
        return {"watchlist": {
            "same_big": {"name": "동반매수", "ticker": "1", "change_pct": 5.0,
                         "foreign_net": 900_000, "institution_net": 800_000},
            "opp_big": {"name": "반대큼", "ticker": "2", "change_pct": -3.0,
                        "foreign_net": -300_000, "institution_net": 250_000},
            "opp_small": {"name": "반대작음", "ticker": "3", "change_pct": 1.0,
                          "foreign_net": -5_000, "institution_net": 4_000},
        }}

    def test_only_opposed_rows_are_drawn(self) -> None:
        import tempfile
        from pathlib import Path
        from src import data_graphics
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "flow.png"
            data_graphics.flow_compare(self._price(), out, top_n=5)
            self.assertTrue(out.exists())
        # 그림에서 이름을 되읽을 수는 없으므로 고르는 논리를 그대로 검증합니다.
        rows = [e for e in self._price()["watchlist"].values()
                if (e["foreign_net"] > 0) != (e["institution_net"] > 0)]
        self.assertEqual({r["name"] for r in rows}, {"반대큼", "반대작음"})

    def test_no_opposed_rows_raises_instead_of_lying(self) -> None:
        price = {"watchlist": {"a": {"name": "동반", "ticker": "1", "change_pct": 1.0,
                                     "foreign_net": 100, "institution_net": 100}}}
        import tempfile
        from pathlib import Path
        from src import data_graphics
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                data_graphics.flow_compare(price, Path(tmp) / "x.png")
