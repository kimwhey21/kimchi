"""종목 페이지 숫자 카드 — 박스는 카드에만, 안쪽 숫자·라벨에는 씌우지 않는다 (2026-09-14).

사장님이 모바일 화면을 확인해 달라고 해서 열어 보니 카드마다 박스가 이중으로 그려져 있었다.
`.fm-kpi div`가 자손 전체를 잡아 `.n`(숫자)·`.l`(라벨)까지 배경·테두리를 받았다. 데스크톱도 같았다.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "stock.html.j2"


class KpiCssTest(unittest.TestCase):
    def setUp(self) -> None:
        self.css = TEMPLATE.read_text(encoding="utf-8")

    def test_the_card_box_uses_a_direct_child_selector(self) -> None:
        self.assertIn(".fm-page .fm-kpi>div{", self.css)

    def test_no_descendant_selector_paints_the_inner_number_and_label(self) -> None:
        # `.fm-kpi div{...}`(자손 선택자)가 다시 들어오면 이중 박스가 돌아온다.
        self.assertIsNone(re.search(r"\.fm-kpi\s+div\s*\{", self.css), "자손 선택자가 다시 생겼습니다")

    def test_the_grid_still_wraps_on_narrow_screens(self) -> None:
        self.assertIn("repeat(auto-fit,minmax(120px,1fr))", self.css)
