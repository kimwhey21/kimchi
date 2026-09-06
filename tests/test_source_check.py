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
        """2026-09-06에 실제로 나갔던 원문 발췌(출처 2곳: 실적 일정·밸류에이션)로
        고정해 둡니다. 이 글(kr_2026-09-06_hynix_per.json)은 그 뒤 출처를 3곳으로
        보강해 정상적으로 통과하게 됐으므로, 살아있는 파일을 계속 가리키면 원고가
        나아질 때마다 이 회귀 테스트가 거짓으로 깨집니다. 그래서 그날 나갔던
        문장을 그대로 박제해 검사기 자체가 여전히 이런 글을 막는지만 봅니다."""
        body = (
            "SK하이닉스가 9월 4일 3.20% 올랐습니다. 52주 고점 대비 44.9% 내려온 "
            "자리입니다. 내년 예상 이익 기준 FWD PER은 3.50배입니다.\n\n"
            "SK하이닉스는 10월 27일에 3분기 실적을 발표합니다. 삼성전자는 "
            "10월 28일, 마이크론은 그보다 앞선 10월 1일입니다."
        )
        issues = source_check.collect_issues(_doc(body))
        self.assertTrue(issues, "출처가 부족한 글이 통과하면 검사가 무의미합니다")


if __name__ == "__main__":
    unittest.main()
