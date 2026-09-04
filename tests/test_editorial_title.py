"""제목 문법 검사입니다.

2026-09-04에 규칙을 정하고 문서에 적었지만, 그날 재보니 규칙을 전부 어긴 제목이
기존 검사(editorial_quality·editorial_facts)를 그대로 통과했습니다. 검수 없이
공개되는 경로라 기계적으로 잡을 수 있는 것은 여기서 막습니다.

기준은 벤치마크 시황 제목 199개를 세어 나온 것이고, 이 검사를 그 199개에
돌리면 꼬리표(우리가 일부러 금지한 것) 말고 걸리는 것은 1개뿐입니다.
"""
from __future__ import annotations

import unittest

from src.editorial_title import EditorialTitleError, collect_issues, validate

PRICE_DATA = {
    "macro": {
        "KS11": {"ticker": "KS11", "name": "코스피", "name_en": "KOSPI",
                  "price": 6687.21, "change_pct": 1.64, "unit": ""},
    },
    "watchlist": {
        "030530": {"ticker": "030530", "name": "원익홀딩스", "name_en": "Wonik Holdings",
                    "price": 12800.0, "change_pct": 29.91},
        "042700": {"ticker": "042700", "name": "한미반도체", "name_en": "Hanmi Semiconductor",
                    "price": 195000.0, "change_pct": 9.26},
        "010950": {"ticker": "010950", "name": "S-Oil", "name_en": "S-Oil",
                    "price": 71000.0, "change_pct": 6.36},
    },
}


class BlockedTest(unittest.TestCase):
    def test_trailing_tag_is_blocked(self) -> None:
        issues = collect_issues({"title": "원익홀딩스 29.91% 급등! 반도체가 이끈 하루. (시황, 9/4)"})
        self.assertEqual(len(issues), 1)
        self.assertIn("꼬리표", issues[0])

    def test_bracket_tag_is_blocked(self) -> None:
        issues = collect_issues({"title": "브로드컴 9% 폭등. 하지만 시장은 웃지 못한 이유. [시황]"})
        self.assertTrue(any("꼬리표" in i for i in issues))

    def test_past_quiz_question_is_blocked(self) -> None:
        """사용자가 두 번 지적한 형태입니다 — 지나간 일을 퀴즈로 냅니다."""
        issues = collect_issues({"title": "원익홀딩스 29.91% 급등! 어제 오른 은행은 왜 내렸을까?"})
        self.assertEqual(len(issues), 1)
        self.assertIn("퀴즈", issues[0])

    def test_polite_ending_is_blocked(self) -> None:
        issues = collect_issues({"title": "코스피 1.64% 상승, 반도체가 이끌었습니다"})
        self.assertEqual(len(issues), 1)
        self.assertIn("존댓말", issues[0])

    def test_invented_words_are_blocked(self) -> None:
        """코앞·문턱·상한가는 벤치마크 제목 1,089개에 0회입니다."""
        issues = collect_issues({"title": "원익홀딩스 상한가 코앞! 코스피 1.64% 상승"})
        self.assertEqual(len(issues), 2)

    def test_rounded_percent_is_blocked(self) -> None:
        """editorial_facts는 소수점 없는 숫자를 건너뛰므로 제목에서 막습니다."""
        issues = collect_issues({"title": "원익홀딩스 30% 급등! 코스피가 오른 이유."}, PRICE_DATA)
        self.assertEqual(len(issues), 1)
        self.assertIn("29.91", issues[0])

    def test_validate_raises(self) -> None:
        with self.assertRaises(EditorialTitleError):
            validate({"title": "코스피가 1.64% 올랐습니다 (시황, 9/4)"}, PRICE_DATA)


class AllowedTest(unittest.TestCase):
    """벤치마크의 실제 제목과 우리가 쓴 제목이 걸리면 검사가 쓸모없어집니다."""

    def test_our_published_title_passes(self) -> None:
        doc = {"title": "원익홀딩스 29.91% 급등! 금리 전망 하나가 업종을 통째로 뒤집었다"}
        self.assertEqual(collect_issues(doc, PRICE_DATA), [])

    def test_benchmark_titles_pass(self) -> None:
        for title in (
            "AMD 8.8% 급등! 반도체 주식들이 상승한 이유.",
            "인텔 7% 급등! 테슬라가 막판 하락한 이유.",
            "50일선이 깨진 미국 주식. 반등할 수 있을까?",
            "또 하락한 미국 주식 시장. 어떻게 대응해야 할까?",
            "엔비디아 5% 급등, 아이온큐는 9% 급락. 반도체 과열 신호 발생!",
            "AI 시대는 끝나지 않았다. 오라클 27% 급등.",
        ):
            with self.subTest(title=title):
                self.assertEqual(collect_issues({"title": title}, PRICE_DATA), [])

    def test_forward_question_is_allowed(self) -> None:
        """물음표 자체는 시황 제목의 34%입니다 — 앞을 보는 질문은 막지 않습니다."""
        doc = {"title": "원익홀딩스 29.91% 급등! 오늘 밤 고용보고서가 다 뒤집나?"}
        self.assertEqual(collect_issues(doc, PRICE_DATA), [])

    def test_rounded_figure_of_unknown_stock_is_not_flagged(self) -> None:
        """시세에 없는 종목의 숫자에 남의 등락률을 붙이면 안 됩니다.

        '인텔 7% 급등'에 (워치리스트에 있는) S-Oil의 6.36%가 붙는 오탐이 실제로
        났습니다. 이름 바로 뒤에 붙은 숫자만 봅니다.
        """
        doc = {"title": "인텔 7% 급등! 테슬라가 막판 하락한 이유."}
        self.assertEqual(collect_issues(doc, PRICE_DATA), [])

    def test_explicit_approximation_is_allowed(self) -> None:
        doc = {"title": "원익홀딩스 30%대 급등, 반도체 장비가 이끌었다"}
        self.assertEqual(collect_issues(doc, PRICE_DATA), [])

    def test_exact_figure_passes(self) -> None:
        doc = {"title": "한미반도체 9.26% 급등! 외국인이 반도체를 산 이유."}
        self.assertEqual(collect_issues(doc, PRICE_DATA), [])

    def test_number_belongs_to_the_next_stock(self) -> None:
        """'테슬라 -6%, 나스닥 -2%'에서 -2%는 나스닥의 것입니다."""
        doc = {"title": "원익홀딩스 29.91%, 한미반도체 9.26% 급등"}
        self.assertEqual(collect_issues(doc, PRICE_DATA), [])

    def test_empty_title_is_not_an_error(self) -> None:
        self.assertEqual(collect_issues({}, PRICE_DATA), [])


if __name__ == "__main__":
    unittest.main()
