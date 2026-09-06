"""한글 폰트 가드.

2026-09-06에 구멍을 찾았습니다. `korean_font()`는 한글 폰트가 없으면 조용히
기본 폰트로 넘어가고, 그러면 한글이 두부(□)로 찍히는데 **예외가 안 나서 테스트도
통과합니다.** 렌더러를 `build()` 없이 직접 부르면 `ensure_korean_font()`를
건너뛰게 되어 이 경로로 들어갑니다.
"""
from __future__ import annotations

import unittest
from unittest import mock

from src import data_graphics


class FontGuardTest(unittest.TestCase):
    def test_ci_has_a_korean_font(self) -> None:
        """CI에도 한글 폰트가 있어야 가드가 의미를 가집니다.

        `tests.yml`이 fonts-nanum을 설치합니다. 이 테스트가 깨지면 그 단계가
        빠진 것이고, 그림 테스트는 전부 두부(□)를 그리며 통과하게 됩니다.
        """
        self.assertTrue(data_graphics.has_korean_font(),
                        "한글 폰트가 없습니다. 우분투라면 fonts-nanum을 설치하세요.")

    def test_renderers_stop_without_a_font(self) -> None:
        """폰트가 없으면 깨진 그림을 내놓지 않고 멈춥니다.

        `flow_compare`처럼 `build()`를 거치지 않고 직접 부르는 경로에도
        가드가 있어야 합니다.
        """
        price = {"watchlist": {"a": {"name": "가", "ticker": "1", "change_pct": 1.0,
                                     "foreign_net": -10, "institution_net": 10}}}
        import tempfile
        from pathlib import Path
        with mock.patch.object(data_graphics, "_KO_REGULAR", ()), \
             mock.patch.object(data_graphics, "_KO_BOLD", ()), \
             tempfile.TemporaryDirectory() as tmp:
            for name, args in (("flow_compare", (price, Path(tmp) / "a.png")),
                               ("movers_list", (price, Path(tmp) / "b.png")),
                               ("stock_spotlight", (price, Path(tmp) / "c.png"))):
                with self.subTest(renderer=name):
                    with self.assertRaises(ValueError):
                        getattr(data_graphics, name)(*args)


if __name__ == "__main__":
    unittest.main()
