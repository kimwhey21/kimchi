from __future__ import annotations

import unittest
from unittest.mock import patch

from src import feature_gate


class FeatureGateWiringTest(unittest.TestCase):
    def test_all_named_checks_run(self) -> None:
        # 출처 검사는 mock으로 막지 않습니다 — 이 검사가 게이트에 실제로 걸려
        # 있는지가 이 테스트의 관심사이기도 합니다. 그래서 본문에 출처를 넣어
        # 통과시키고, 빠졌을 때 막는지는 아래 테스트가 봅니다.
        doc = {"ko": {"title": "제목",
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
