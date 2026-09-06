from __future__ import annotations

import unittest
from unittest.mock import patch

from src import feature_gate


class FeatureGateWiringTest(unittest.TestCase):
    def test_all_five_named_checks_run(self) -> None:
        doc = {"ko": {"title": "제목", "narrative": [], "closing": {}}}
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
