"""벤치마크 대조가 코퍼스 없는 곳(클라우드 루틴)에서도 실제로 비교하는지 확인합니다.

코퍼스(재테크농부 글 103편)는 사람 컴퓨터의 `~/.market-brief-bench`에만 있습니다.
2026-09-07까지 루틴은 이 스크립트를 매일 돌렸지만 코퍼스를 못 찾아 "우리 수치만"을
찍었고, 그것이 대조 결과처럼 보고서에 붙었습니다. 이제 코퍼스가 없으면 저장소의
집계 파일(`data/benchmark_stats.json`)을 읽습니다 — 이 파일이 빠지면 대조가 다시
조용히 사라지므로 세 번째 테스트가 파일의 존재를 고정합니다.
"""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from scripts import compare_to_benchmark as cmp

DOC = {"ko": {"title": "제목", "narrative": [
    {"heading": "소제목 하나", "body": "첫 번째 문장입니다. 두 번째 문장이다.\n\n세 번째 문장입니다."},
]}}


class CompareToBenchmarkTest(unittest.TestCase):
    def _report(self, corpus: Path, stats_file: Path) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "kr_2026-09-07.json"
            doc.write_text(json.dumps(DOC, ensure_ascii=False), encoding="utf-8")
            buf = io.StringIO()
            with mock.patch.object(cmp, "CORPUS", corpus), \
                    mock.patch.object(cmp, "STATS_FILE", stats_file), \
                    redirect_stdout(buf):
                cmp.report(doc)
            return buf.getvalue()

    def test_stats_file_replaces_missing_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stats = Path(tmp) / "benchmark_stats.json"
            stats.write_text(json.dumps({"measured_at": "2026-09-07", "posts": 103,
                                         "stats": {"문장 수": [38, 25, 55]}}),
                             encoding="utf-8")
            out = self._report(Path(tmp) / "no-corpus", stats)
        self.assertIn("벤치마크", out)
        self.assertIn("2026-09-07 집계 103편", out)
        self.assertIn("목표 아님", out)

    def test_without_corpus_or_stats_prints_own_numbers_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = self._report(Path(tmp) / "no-corpus", Path(tmp) / "no-stats.json")
        self.assertIn("우리 수치만", out)
        self.assertNotIn("벤치마크 집계", out)

    def test_committed_stats_file_is_present_and_dated(self) -> None:
        """루틴이 읽는 파일이 저장소에 실제로 있어야 합니다."""
        self.assertTrue(cmp.STATS_FILE.exists(), cmp.STATS_FILE)
        payload = json.loads(cmp.STATS_FILE.read_text(encoding="utf-8"))
        self.assertRegex(payload.get("measured_at", ""), r"^\d{4}-\d{2}-\d{2}$")
        self.assertGreater(payload.get("posts", 0), 50)
        self.assertIn("문장 수", payload.get("stats", {}))
        for value in payload["stats"].values():
            self.assertEqual(len(value), 3)  # 중앙값·p25·p75


if __name__ == "__main__":
    unittest.main()
