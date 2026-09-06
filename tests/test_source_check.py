"""외부 출처 개수 검사.

2026-09-06에 공개한 가이드 글은 밖에서 가져온 사실이 0곳이었습니다. 같은 주제
벤치마크 글은 7곳이었고, 두 글을 가른 것은 문장이 아니라 그 차이였습니다.
"""
from __future__ import annotations

import unittest

from src import source_check


def _doc(body: str) -> dict:
    return {"ko": {"title": "제목", "narrative": [{"heading": "1.", "body": body}],
                   "closing": {"heading": "Take", "body": ""}}}


class SourceCheckTest(unittest.TestCase):
    def test_no_source_is_blocked(self) -> None:
        issues = source_check.collect_issues(_doc("주가가 3.20% 올랐습니다."))
        self.assertTrue(issues)
        self.assertIn("재료", issues[0])

    def test_three_distinct_sources_pass(self) -> None:
        body = ("트렌드포스는 계약가 상승을 전망했습니다. "
                "모건스탠리가 투자의견을 상향했습니다. "
                "관세청 수출 통계도 같은 방향입니다.")
        self.assertEqual(source_check.collect_issues(_doc(body)), [])

    def test_same_source_repeated_counts_once(self) -> None:
        """같은 곳을 열 번 인용해도 하나입니다."""
        body = "블룸버그 " * 10
        self.assertEqual(source_check.collect(_doc(body))["distinct"], 1)

    def test_engine_material_counts_as_a_source(self) -> None:
        """우리 엔진이 뽑은 자료도 밖에서 가져온 사실입니다."""
        body = ("내부자 매수가 나왔습니다. 13F 기관 보유가 늘었습니다. "
                "10월 27일 실적이 남아 있습니다.")
        found = source_check.collect(_doc(body))["found"]
        self.assertIn("우리 엔진 자료", found)
        self.assertEqual(source_check.collect_issues(_doc(body)), [])

    def test_published_article_would_have_been_blocked(self) -> None:
        """실제로 공개한 글이 이 검사에 걸리는지 확인합니다."""
        import json
        from pathlib import Path
        path = (Path(__file__).resolve().parent.parent
                / "editorial/features/kr_2026-09-06_hynix_per.json")
        if not path.exists():
            self.skipTest("원고 파일이 없습니다")
        doc = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(source_check.collect_issues(doc),
                        "출처가 부족한 글이 통과하면 검사가 무의미합니다")


if __name__ == "__main__":
    unittest.main()
