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

    def test_past_why_question_is_allowed_now(self) -> None:
        """2026-09-09 사장님이 `코스피는 왜 오늘 300포인트나 올랐을까`를 골랐다 — 옛 '과거형 퀴즈 금지'는 없앴다."""
        self.assertEqual(collect_issues({"title": "코스피는 왜 오늘 300포인트나 올랐을까"}), [])

    def test_polite_ending_is_allowed(self) -> None:
        """존댓말 제목을 막지 않습니다.

        전에는 "시황 제목의 존댓말 어미는 4%뿐"이라는 옛 표본을 근거로 막았습니다.
        2026-09-06에 최근 시황 46편을 다시 세니 15%가 존댓말로 끝났습니다 —
        `내일 고용보고서가 결정합니다` 같은 것이 벤치마크의 실제 제목입니다.
        드문 것과 틀린 것은 다릅니다.
        """
        self.assertEqual(
            collect_issues({"title": "코스피 1.64% 상승, 반도체가 이끌었습니다"}), [])
        self.assertEqual(
            collect_issues({"title": "미국 증시 반등 시작? 내일 고용보고서가 결정합니다"}), [])

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
        doc = {"title": "원익홀딩스 29.91% 급등, 금리 전망 하나가 바꾼 하루"}
        self.assertEqual(collect_issues(doc, PRICE_DATA), [])

    def test_benchmark_titles_pass(self) -> None:
        for title in (
            "AMD 8.8% 급등! 반도체 주식들이 상승한 이유.",
            "인텔 7% 급등! 테슬라가 막판 하락한 이유.",
            "50일선이 깨진 미국 주식. 반등할 수 있을까?",
            "또 하락한 미국 주식 시장. 어떻게 대응해야 할까?",
            # 2026-09-08: 등락률 둘을 나열한 옛 제목은 이제 막는다 — 최근 104편에는 0개다.
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
        doc = {"title": "원익홀딩스 30%대 급등, 이유는 반도체 장비"}
        self.assertEqual(collect_issues(doc, PRICE_DATA), [])

    def test_exact_figure_passes(self) -> None:
        doc = {"title": "한미반도체 9.26% 급등! 외국인이 반도체를 산 이유."}
        self.assertEqual(collect_issues(doc, PRICE_DATA), [])

    def test_number_belongs_to_the_next_stock(self) -> None:
        """'테슬라 -6%, 나스닥 -2%'에서 -2%는 나스닥의 것입니다.

        등락률 둘 나열은 별도 규칙이 막지만, 어림수 검사가 남의 숫자를 끌어오지는
        않아야 합니다.
        """
        doc = {"title": "원익홀딩스 29.91%, 한미반도체 9.26% 급등"}
        issues = collect_issues(doc, PRICE_DATA)
        self.assertFalse([i for i in issues if "어림수" in i], issues)
        self.assertTrue(any("등락률이 둘 이상" in i for i in issues))

    def test_two_percentages_in_a_title_are_rejected(self) -> None:
        """9/7·9/8 이틀 연속 낸 '숫자 나열' 제목. 최근 벤치마크 104편에 0개다."""
        doc = {"title": "대우건설 8.47% 급등, 삼성전기 5.78% 급락. 코스피가 0.58% 하락한 이유."}
        self.assertTrue(any("등락률이 둘 이상" in i for i in collect_issues(doc)))
        self.assertEqual(collect_issues({"title": "반도체 주식 급락, 고점 신호일까?"}), [])
        self.assertEqual(collect_issues({"title": "반도체가 5% 폭락한 이유, 고금리가 AI 랠리를 흔들었습니다"}), [])

    def test_empty_title_is_not_an_error(self) -> None:
        self.assertEqual(collect_issues({}, PRICE_DATA), [])


if __name__ == "__main__":
    unittest.main()


class UniversalRulesTest(unittest.TestCase):
    """제목·소제목 규칙은 블로그의 모든 글에 같다(2026-09-08).

    사용자: "따로 나뉘어 있으면 매번 수정을 해야 한다." 후킹 장치·절 수·소제목 길이가
    feature_checks(기준표)와 editorial_quality(시황)에 따로 있던 것을 여기로 모았다.
    """

    def test_plain_announcement_is_not_in_the_example_book(self) -> None:
        issues = collect_issues({"title": "코스피는 오늘 하락했고 반도체 업종도 함께 하락했습니다"})
        self.assertTrue(any("예문집" in i or "버린 꼴" in i for i in issues), issues)

    def test_every_owner_pick_passes_and_every_reject_fails(self) -> None:
        """2026-09-09 사장님이 고른 35개는 전부 통과, 버린 꼴 예문은 전부 막힌다."""
        from src import editorial_title
        for title in editorial_title.OWNER_PICKS:
            self.assertEqual(collect_issues({"title": title}), [], title)
        for title in editorial_title.OWNER_REJECTS:
            self.assertTrue(collect_issues({"title": title}), title)

    def test_our_rewritten_titles_pass(self) -> None:
        for title in ("코스피는 왜 7,000선을 넘지 못했을까",
                      "외국인 5조 매수: 7,000선을 앞두고 알아야 할 것",
                      "고용지표에 지수는 내렸는데 메모리 반도체만 오른 이유",
                      "오늘 밤 미국장, 유가 6주 최고치가 반도체 랠리를 흔들까?",
                      "SK하이닉스 밸류에이션 점검: 10월 27일 실적 전에 볼 다섯 가지"):
            self.assertEqual(collect_issues({"title": title}), [], title)

    def test_section_floor_depends_only_on_kind(self) -> None:
        from src import editorial_title
        sections = [{"heading": f"{i}. 오늘 밤 일정", "body": "b"} for i in range(1, 4)]
        doc = {"title": "오늘 밤 미국장, 유가가 반도체를 흔들까?", "narrative": sections}
        self.assertEqual(collect_issues(doc, kind="프리뷰"), [])
        self.assertTrue(any("8개 이상" in i for i in collect_issues(doc, kind="시황")))
        self.assertTrue(any("5개 이상" in i for i in collect_issues(doc, kind="기준표")))
        self.assertEqual(editorial_title.SECTION_FLOORS["가이드"], 5)

    def test_heading_length_applies_to_every_kind(self) -> None:
        long = "1. 오늘 밤 일정 — 예정된 지표보다 이미 벌어진 사건, 그리고 그 뒤에 남은 것"
        doc = {"title": "오늘 밤 미국장, 유가가 반도체를 흔들까?",
               "narrative": [{"heading": long, "body": "b"}] * 3}
        for kind in ("시황", "기준표", "프리뷰", "가이드", None):
            self.assertTrue(any("32자" in i for i in collect_issues(doc, kind=kind)), kind)

    def test_block_label_heading_is_blocked(self) -> None:
        """`초보자 설명: …`은 본문 문단의 라벨이지 소제목이 아니다(2026-09-08 기준표 시험 실행).

        `라벨: 내용` 꼴 자체는 재테크농부도 쓴다(`실적 성적표: 무엇이 예상을 넘었나`) —
        막는 것은 초보자 설명·요약·참고 같은 블록 라벨뿐이다.
        """
        title = "오늘 밤 미국장, 유가가 반도체를 흔들까?"
        def doc(heading: str) -> dict:
            others = ["2. 오늘 투자심리", "3. 외국인 수급", "4. 다음 확인 지점", "5. 남은 질문은 하나"]
            return {"title": title, "narrative": [{"heading": h, "body": "b"} for h in [heading] + others]}
        self.assertTrue(any("라벨" in i for i in collect_issues(doc("2. 초보자 설명: 순매수는 지수를 이렇게 움직입니다"), kind="기준표")))
        self.assertTrue(any("라벨" in i for i in collect_issues(doc("요약: 외국인은 돌아왔습니다"), kind="기준표")))
        for heading in ("2. 순매수는 지수를 이렇게 움직입니다", "2. 오후 2:30 이후 반등했습니다",
                        "실적 성적표: 무엇이 예상을 넘었나"):
            self.assertEqual(collect_issues(doc(heading), kind="기준표"), [], heading)

    def test_short_label_is_a_note_not_a_block(self) -> None:
        notes: list[str] = []
        doc = {"title": "오늘 밤 미국장, 유가가 반도체를 흔들까?",
               "narrative": [{"heading": "1. 지금 숫자", "body": "b"}] * 3}
        self.assertEqual(collect_issues(doc, kind="프리뷰", notes_out=notes), [])
        self.assertTrue(any("명사 토막" in n for n in notes), notes)
