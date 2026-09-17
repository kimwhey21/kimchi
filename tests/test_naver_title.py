"""네이버 제목은 본진 제목 그대로다 (2026-09-17, 사장님: "날짜 시황 제목 앞에 쓰는거 삭제").

이력: 2026-09-13에 "왜 네이버에서 검색해도 안 나오냐"는 조사 끝에 검색어·날짜를 앞에
붙였다(`코스피 마감 시황 9월 16일: …`). 2026-09-17에 상위 블로그 제목 450개를 읽어 보니
앞자리는 훅이 차지해야 하고(김무무·경제현미경은 앞 15자가 독자 목소리인데도 검색 1·2위),
검색어는 제목 어딘가에 있으면 됐다. 사장님이 앞머리를 없애라고 했고, 꼬리표도 같이 뺐다 —
네이버에는 본진 글을 똑같이 옮긴다(2026-09-16)는 원칙과도 맞는다.
"""
from __future__ import annotations

import unittest

from scripts.naver_post import naver_title

CASES = (
    ("네 마녀의 날: 코스피가 6,900선에서 버틴 이유", "코스피 마감 시황 9월 10일", None, "9월 10일"),
    ("뉴욕증시 나흘째 하락, 원인은 치솟은 국채금리에 있습니다", "미국증시 마감 9월 10일", None, "9월 10일"),
    ("오늘 밤 미국장, 오라클 실적이 반도체 랠리를 결정합니다", "오늘 밤 미국장 프리뷰 9월 10일", "프리뷰", "9월 10일"),
    ("디어 사상 최고가, 11월 25일 실적이 답한다", "투자 체크포인트", "기준표", "9월 12일"),
    ("9월 FOMC, 17일 새벽 3시에 무엇을 확인할까", "증시 이벤트 9월 17일", "이벤트", "9월 17일"),
    ("코스피 주간 3.33%, 그런데 뉴욕증시는 유가·금리에 흔들렸다", "주간 증시 결산 9월 7일~11일", "주간 결산", "9월 12일"),
    ("미국주식 양도세 250만원: 신고 안 하면 생기는 일", "", "가이드", "9월 13일"),
)


class NaverTitleTest(unittest.TestCase):
    def test_every_series_keeps_the_original_title(self) -> None:
        for base, prefix, series, kdate in CASES:
            with self.subTest(series=series or "시황"):
                self.assertEqual(naver_title(base, prefix, series, kdate), base)

    def test_no_head_no_tail_ever(self) -> None:
        """머리(`코스피 마감 시황 …:`)도 꼬리(`| 투자 체크포인트`)도 돌아오면 안 된다."""
        got = naver_title("디어 사상 최고가, 11월 25일 실적이 답한다", "투자 체크포인트", "기준표", "9월 12일")
        self.assertNotIn("|", got)
        self.assertFalse(got.startswith(("코스피 마감", "미국증시 마감", "오늘 밤 미국장 프리뷰", "투자 체크포인트")), got)

    def test_whitespace_is_trimmed_only(self) -> None:
        self.assertEqual(naver_title("  금리 하나가 바꾼 하루 ", "코스피 마감 시황 9월 1일", None, "9월 1일"), "금리 하나가 바꾼 하루")


if __name__ == "__main__":
    unittest.main()
