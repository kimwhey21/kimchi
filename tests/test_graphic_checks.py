from __future__ import annotations

import unittest

from src import graphic_checks


class GraphicSemanticCheckTest(unittest.TestCase):
    def test_dominant_valuation_row_is_blocked(self) -> None:
        issues = graphic_checks.collect_spec_issues("valuation_bars", {"rows": [
            {"name": "메모리", "forward_pe": 3.5},
            {"name": "장비", "forward_pe": 43.59},
        ]})
        self.assertTrue(any("축" in issue for issue in issues), issues)

    def test_reverse_flow_title_requires_opposed_data(self) -> None:
        issues = graphic_checks.collect_spec_issues("flow_compare", {"price_data": {"watchlist": {
            "a": {"foreign_net": 10, "institution_net": 20},
        }}}, "같은 종목에서 반대로")
        self.assertTrue(issues)

    def test_calendar_label_collision_is_blocked(self) -> None:
        issues = graphic_checks.collect_spec_issues("calendar_strip", {"events": [
            {"label": "매우 긴 첫 번째 일정 이름입니다"},
            {"label": "매우 긴 두 번째 일정 이름입니다"},
            {"label": "매우 긴 세 번째 일정 이름입니다"},
            {"label": "매우 긴 네 번째 일정 이름입니다"},
            {"label": "매우 긴 다섯 번째 일정 이름입니다"},
        ]})
        self.assertTrue(issues)
