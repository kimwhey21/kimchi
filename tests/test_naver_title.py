"""네이버 제목 규칙(2026-09-13) — 검색되는 말이 앞, 우리가 지어낸 갈래 이름은 뒤.

사장님이 "왜 네이버에서 검색해도 안 나오냐"고 물어 조사한 결과, 네이버에 올린 18편 중 여덟 편이
"투자 체크포인트:"로 시작하고 있었다. 모바일 검색 결과는 제목을 30자 안팎에서 자르므로 종목 이름이
뒤로 밀리면 검색어와 겹칠 기회가 없다.
"""
from __future__ import annotations

import unittest

from scripts.naver_post import NAVER_TITLE_MAX, naver_title


class NaverTitleTest(unittest.TestCase):
    def test_made_up_series_labels_move_to_the_tail(self) -> None:
        for label in ("투자 체크포인트", "증시 이벤트 9월 17일"):
            got = naver_title("디어 사상 최고가, 11월 25일 실적이 답한다", label, "기준표", "9월 12일")
            self.assertTrue(got.startswith("디어"), got)
            self.assertTrue(got.endswith(label), got)

    def test_a_label_already_in_the_title_is_not_repeated(self) -> None:
        base = "외국인 수급 체크포인트: 9월 30일까지 볼 것"
        self.assertEqual(naver_title(base, "투자 체크포인트", "기준표", "9월 10일"), base)

    def test_the_tail_is_dropped_rather_than_overflowing(self) -> None:
        base = "가" * (NAVER_TITLE_MAX - 3)
        self.assertEqual(naver_title(base, "투자 체크포인트", "기준표", "9월 12일"), base)

    def test_real_search_phrases_stay_at_the_front(self) -> None:
        # "코스피 마감 시황"·"주간 증시 결산"은 사람이 실제로 치는 말이라 머리에 둔다.
        got = naver_title("코스피 1.76% 하락, 원인은 유가에 있었습니다", "코스피 마감 시황 9월 11일", None, "9월 11일")
        self.assertTrue(got.startswith("코스피 마감 시황 9월 11일"), got)

    def test_preview_does_not_say_tonight_twice(self) -> None:
        got = naver_title("오늘 밤 8월 CPI 앞두고 확인할 것 세 가지", "오늘 밤 미국장 프리뷰 9월 11일", "프리뷰", "9월 11일")
        self.assertEqual(got.count("오늘 밤"), 1, got)

    def test_a_guide_title_is_left_alone_because_it_is_already_the_question(self) -> None:
        base = "미국주식 양도세 250만원: 신고 안 하면 생기는 일"
        self.assertEqual(naver_title(base, "", "가이드", "9월 13일"), base)


if __name__ == "__main__":
    unittest.main()
