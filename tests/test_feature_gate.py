from __future__ import annotations

import unittest
from unittest.mock import patch

from src import feature_gate


class FeatureGateWiringTest(unittest.TestCase):
    def test_all_named_checks_run(self) -> None:
        # 출처 검사는 mock으로 막지 않습니다 — 이 검사가 게이트에 실제로 걸려
        # 있는지가 이 테스트의 관심사이기도 합니다. 그래서 본문에 출처를 넣어
        # 통과시키고, 빠졌을 때 막는지는 아래 테스트가 봅니다.
        doc = {"series": "기준표", "ko": {"title": "제목",
                      "narrative": [{"heading": "1.", "body":
                          "트렌드포스 전망입니다. 모건스탠리가 상향했습니다. "
                          "관세청 통계도 같습니다."}],
                      "closing": {}}}
        with patch("src.feature_gate.editorial_quality.collect_issues", return_value=[] ) as quality, \
             patch("src.feature_gate.editorial_title.collect_issues", return_value=[] ) as title, \
             patch("src.feature_gate.feature_checks.collect_issues", return_value=[] ) as feature, \
             patch("src.feature_gate.check_against_benchmark.CORPUS") as corpus, \
             patch("src.feature_gate.check_against_benchmark.load_corpus", return_value="corpus") as load, \
             patch("src.feature_gate.check_against_benchmark.check", return_value=[] ) as words, \
             patch("src.feature_gate.compare_to_benchmark.measure", return_value={} ) as compare:
            corpus.exists.return_value = True
            feature_gate.run(doc, graphics=6)
        quality.assert_called_once()
        title.assert_called_once()
        feature.assert_called_once()
        load.assert_called_once()
        words.assert_called_once()
        compare.assert_called_once()

    def test_gate_blocks_when_sources_are_missing(self) -> None:
        """재료 없이 쓴 글은 게이트에서 멈춥니다.

        2026-09-06에 출처 0곳짜리 글이 그대로 공개됐고, 사람이 네 번 되돌려
        보내고 나서야 문제가 드러났습니다.
        """
        doc = {"ko": {"title": "제목",
                      "narrative": [{"heading": "1.", "body": "주가가 올랐습니다."}],
                      "closing": {}}}
        with patch("src.feature_gate.editorial_quality.collect_issues", return_value=[]), \
             patch("src.feature_gate.editorial_title.collect_issues", return_value=[]), \
             patch("src.feature_gate.feature_checks.collect_issues", return_value=[]), \
             patch("src.feature_gate.check_against_benchmark.CORPUS") as corpus, \
             patch("src.feature_gate.check_against_benchmark.load_corpus", return_value="c"), \
             patch("src.feature_gate.check_against_benchmark.check", return_value=[]), \
             patch("src.feature_gate.compare_to_benchmark.measure", return_value={}):
            corpus.exists.return_value = True
            with self.assertRaises(feature_gate.FeatureGateError) as caught:
                feature_gate.run(doc, graphics=6)
        self.assertIn("밖에서 가져온 사실", str(caught.exception))


class PlacementTest(unittest.TestCase):
    """그림 자리(2026-10-27): 한 절에 두 장(10/26 칼럼이 네이버에 못 올라감)과 없는 절 번호(그림이 조용히 빠짐)를 막는다."""
    def _doc(self, sections, series="칼럼"):
        return {"series": series, "ko": {"narrative": [{"heading": "h", "body": "b"}] * 5},
                "graphics": [{"kind": "cover", "featured": True}] + [{"kind": "fact_table", "section": s} for s in sections]}

    def test_two_graphics_in_one_section_are_blocked(self) -> None:
        issues = feature_gate.placement_issues(self._doc([4, 4, 4]))
        self.assertEqual(len(issues), 2, issues)
        self.assertIn("한 절에 한 장", issues[0])

    def test_a_section_past_the_last_is_blocked(self) -> None:
        issues = feature_gate.placement_issues(self._doc([1, 5]))
        self.assertTrue(any("없는 절" in i and "0~4" in i for i in issues), issues)

    def test_distinct_sections_pass_and_magazine_is_skipped(self) -> None:
        self.assertEqual(feature_gate.placement_issues(self._doc([0, 2, 4])), [])
        self.assertEqual(feature_gate.placement_issues(self._doc([4, 4], series="매거진")), [])


class GraphicDataTest(unittest.TestCase):
    """그림 데이터(2026-11-16): 발행이 그리기 직전에 멈추는 검사를 관문이 커밋 전에 돌린다.
    그림을 그려 보지 못한 실행이 관문만 통과한 원고를 올려 그날 글이 빠진 일이 있었다."""

    def _doc(self, body: str, price_file: str | None, series: str = "칼럼") -> dict:
        spec = {"kind": "movers_list", "section": 1, "args": {"title": "오늘의 등락"}}
        if price_file:
            spec["price_file"] = price_file
        return {"series": series,
                "ko": {"narrative": [{"heading": "h", "body": "첫 절입니다."}, {"heading": "h", "body": body}]},
                "graphics": [{"kind": "cover", "featured": True, "args": {}}, spec]}

    def _price_file(self) -> str:
        import json
        import tempfile
        from pathlib import Path
        from tests.test_graphic_checks_2026_09_25 import _kr_price_data
        path = Path(tempfile.mkdtemp()) / "price_kr_2026-09-05.json"
        path.write_text(json.dumps(_kr_price_data()), encoding="utf-8")
        return str(path)

    def test_drawn_stocks_missing_from_the_section_are_reported(self) -> None:
        from src import publish_feature
        issues = publish_feature.graphic_data_issues(self._doc("은행주가 무거웠습니다.", self._price_file()))
        self.assertEqual(len(issues), 1, issues)
        self.assertIn("그림 2(movers_list)", issues[0])
        self.assertIn("하나도 없습니다", issues[0])

    def test_section_that_names_the_stocks_passes(self) -> None:
        from src import publish_feature
        body = "대우건설과 두산에너빌리티가 내렸고 삼성전자와 에이피알은 올랐습니다."
        self.assertEqual(publish_feature.graphic_data_issues(self._doc(body, self._price_file())), [])

    def test_missing_price_file_is_an_issue_not_a_crash(self) -> None:
        from src import publish_feature
        issues = publish_feature.graphic_data_issues(self._doc("b", None))
        self.assertTrue(issues and "price_file" in issues[0], issues)
        issues = publish_feature.graphic_data_issues(self._doc("b", "data/price_kr_1999-01-01.json"))
        self.assertTrue(issues and "시세 파일이 없습니다" in issues[0], issues)

    def test_gate_blocks_on_graphic_data_and_skips_the_magazine(self) -> None:
        doc = self._doc("은행주가 무거웠습니다.", self._price_file())
        with self.assertRaises(feature_gate.FeatureGateError) as caught:
            feature_gate.run(doc, graphics=2)
        self.assertIn("그림 데이터 — 그림 2(movers_list)", str(caught.exception))
        magazine = self._doc("은행주가 무거웠습니다.", self._price_file(), series="매거진")
        try:
            feature_gate.run(magazine, graphics=2)
        except feature_gate.FeatureGateError as exc:
            self.assertNotIn("그림 데이터", str(exc))
