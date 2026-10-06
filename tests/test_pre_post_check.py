"""게시 직전 검사(2026-10-06, 감사 F-044·F-074) — 관문을 통과 못 한 원고도 main에 있으면 네이버에 올라갔다."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import pre_post_check
from src import feature_gate, publish_editorial

ROOT = Path(__file__).resolve().parent.parent


class PrePostCheckTest(unittest.TestCase):
    def _write(self, doc: dict) -> Path:
        path = Path(tempfile.mkdtemp()) / "m.json"
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return path

    def test_daily_uses_the_same_number_check_as_publishing(self) -> None:
        path = self._write({"market": "kr", "date": "2026-10-02", "price_data": {}, "ko": {}})
        with mock.patch.object(publish_editorial, "fact_blockers", return_value=["등락률(ko): 틀림"]) as fb:
            self.assertEqual(pre_post_check.main([str(path)]), 1)
        fb.assert_called_once()
        with mock.patch.object(publish_editorial, "fact_blockers", return_value=[]):
            self.assertEqual(pre_post_check.main([str(path)]), 0)

    def test_other_series_run_the_whole_feature_gate(self) -> None:
        path = self._write({"series": "매거진", "graphics": [1, 2]})
        with mock.patch.object(feature_gate, "run", side_effect=feature_gate.FeatureGateError("실패:\n- 근거 없음")) as run:
            self.assertEqual(pre_post_check.blockers(path), ["근거 없음"])
        self.assertEqual(run.call_args.kwargs["graphics"], 2)

    def test_a_check_that_cannot_run_counts_as_blocked(self) -> None:
        path = self._write({"market": "us", "date": "2026-10-05", "price_data": {}, "ko": {}})
        with mock.patch.object(publish_editorial, "fact_blockers", side_effect=KeyError("x")):
            self.assertEqual(pre_post_check.main([str(path)]), 1)

    def test_real_committed_daily_passes(self) -> None:
        self.assertEqual(pre_post_check.blockers(ROOT / "editorial" / "kr_2026-10-02.json"), [])


if __name__ == "__main__":
    unittest.main()
