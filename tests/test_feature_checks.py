"""기준표 검사 테스트.

여기 있는 사례는 전부 2026-09-06 첫 편에서 실제로 고친 것들입니다. 검사가
그때의 실수를 다시 잡는지 확인합니다.
"""
from __future__ import annotations

import unittest

from src import feature_checks


def _doc(title: str, sections: int = 7, body_extra: str = "") -> dict:
    return {"ko": {
        "title": title,
        "narrative": [{"heading": f"{i}. 절", "body": "초보자 설명: 본문입니다."}
                      for i in range(1, sections + 1)],
        "closing": {"heading": "Fermata's Take",
                    "body": "10월 27일에 갈립니다. " + body_extra},
    }}


class TitleTest(unittest.TestCase):
    GOOD = "SK하이닉스 지금 사도 될까? 10월 27일에 갈린다"

    def test_good_title_passes(self) -> None:
        self.assertEqual(feature_checks.collect_issues(_doc(self.GOOD), graphics=6), [])

    def test_indicator_jargon_in_title_is_caught(self) -> None:
        """제목에 FWD PER을 넣었다가 지적받았습니다. 벤치마크 100편 중 1편만 예외."""
        issues = feature_checks.collect_issues(
            _doc("SK하이닉스 FWD PER 3.5배. 확인할 다섯 가지"), graphics=6)
        self.assertTrue(any("지표 용어" in i for i in issues), issues)

    def test_korean_numeral_counts_as_a_hook(self) -> None:
        """`확인할 다섯 가지`는 범위 축소 장치입니다.

        한글 숫자를 못 읽어 '후킹 없음'으로 잡으면, 그 제목의 진짜 문제(지표 용어)를
        놓친 채 엉뚱한 이유로 통과시키거나 막게 됩니다.
        """
        issues = feature_checks.collect_issues(
            _doc("반도체 지금 사도 되나. 확인할 다섯 가지"), graphics=6)
        self.assertFalse(any("후킹 장치가 없" in i for i in issues), issues)

    def test_title_without_any_hook_is_caught(self) -> None:
        issues = feature_checks.collect_issues(
            _doc("메모리 반도체 업황 정리"), graphics=6)
        self.assertTrue(any("후킹 장치가 없" in i for i in issues), issues)

    def test_polite_ending_is_caught(self) -> None:
        issues = feature_checks.collect_issues(
            _doc("SK하이닉스 지금 사도 될까? 10월 27일에 갈립니다"), graphics=6)
        self.assertTrue(any("존댓말" in i for i in issues), issues)


class BodyTest(unittest.TestCase):
    def test_missing_graphics_is_caught(self) -> None:
        """첫 편이 0장으로 나갔습니다."""
        issues = feature_checks.collect_issues(_doc(TitleTest.GOOD), graphics=0)
        self.assertTrue(any("시각자료" in i for i in issues), issues)

    def test_graphics_unknown_is_not_a_failure(self) -> None:
        """장수를 모를 때(원고만 검사) 그것 때문에 막지는 않습니다."""
        issues = feature_checks.collect_issues(_doc(TitleTest.GOOD))
        self.assertFalse(any("시각자료" in i for i in issues), issues)

    def test_missing_check_date_is_caught(self) -> None:
        """날짜가 없으면 기준표가 아니라 그냥 시황입니다."""
        doc = _doc(TitleTest.GOOD)
        doc["ko"]["closing"]["body"] = "그렇게 봅니다."
        doc["ko"]["title"] = "SK하이닉스 지금 사도 될까"
        issues = feature_checks.collect_issues(doc, graphics=6)
        self.assertTrue(any("확인 날짜" in i for i in issues), issues)

    def test_title_date_must_appear_in_body(self) -> None:
        doc = _doc("SK하이닉스 지금 사도 될까? 11월 3일에 갈린다")
        issues = feature_checks.collect_issues(doc, graphics=6)
        self.assertTrue(any("11월 3일" in i for i in issues), issues)

    def test_position_voice_is_caught(self) -> None:
        """우리는 종목을 들고 있지 않습니다. 1인칭 포지션 화법은 거짓말이 됩니다."""
        issues = feature_checks.collect_issues(
            _doc(TitleTest.GOOD, body_extra="저는 매도했습니다."), graphics=6)
        self.assertTrue(any("포지션 화법" in i for i in issues), issues)

    def test_missing_beginner_note_is_caught(self) -> None:
        doc = _doc(TitleTest.GOOD)
        for section in doc["ko"]["narrative"]:
            section["body"] = "본문입니다."
        issues = feature_checks.collect_issues(doc, graphics=6)
        self.assertTrue(any("초보자" in i for i in issues), issues)


class RealArticleTest(unittest.TestCase):
    def test_the_published_draft_passes(self) -> None:
        import json
        from pathlib import Path
        path = (Path(__file__).resolve().parent.parent
                / "editorial/features/kr_2026-09-06_hynix_per.json")
        if not path.exists():
            self.skipTest("원고 파일이 없습니다")
        doc = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(feature_checks.collect_issues(doc, graphics=6), [])


if __name__ == "__main__":
    unittest.main()
