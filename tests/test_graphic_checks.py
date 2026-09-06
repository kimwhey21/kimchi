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


class BuilderNameCollisionTest(unittest.TestCase):
    """`feature_graphics`와 `data_graphics.BUILDERS`에 같은 이름을 두지 않습니다.

    `publish_feature._build_graphics`가 feature_graphics를 먼저 봅니다. 이름이
    겹치면 일간 시황이 부르는 그래픽이 조용히 다른 함수로 바뀝니다 — 인자 규약이
    달라 죽거나, 더 나쁘게는 엉뚱한 그림이 나갑니다. 실제로 `sector_bars`가
    그랬습니다(2026-09-07).
    """

    def test_no_shared_builder_names(self) -> None:
        from src import data_graphics, feature_graphics
        shared = sorted(set(dir(feature_graphics)) & set(data_graphics.BUILDERS))
        self.assertEqual(shared, [], f"이름이 겹칩니다: {shared}")
