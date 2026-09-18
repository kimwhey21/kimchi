"""영어 가이드 주제 큐(2026-09-14) — 검색어 데이터를 "오늘 무엇을 할지"로 바꾸는 부분만 본다.

왜 이 도구인가: 영어 가이드의 주제를 **뉴스**로 고르려 했던 것이 틀린 전제였다. 영어 가이드는 상시
검색 글이라 순위를 정하는 것이 검색 수요·경쟁·페이지 신뢰도이지 오늘 기사가 아니다. 2026-09-14 실측이
그 값을 보여 준다 — `kospi trading hours`는 노출 6에 게재순위 **66위**였고, 그 주제의 글을 이미
갖고 있었다. 새 글을 한 편 더 쓰는 것보다 그 글을 고치는 것이 먼저다.
"""
from __future__ import annotations

import unittest

from src import search_queue as sq

POSTS = [
    {"slug": "kospi-vs-kosdaq-what-the-board-a-korean-stock-trades-on-actually-tells-you",
     "title": {"rendered": "KOSPI vs KOSDAQ: What the Board a Korean Stock Trades On Tells You"}},
    {"slug": "koreas-trading-day-just-doubled-hours-price-limits-and-halts-foreign-investors-should-know",
     "title": {"rendered": "Korea Stock Market Hours 2026: Sessions, Price Limits, Halts"}},
    {"slug": "kospi-etf-for-us-investors", "title": {"rendered": "KOSPI ETFs for US Investors"}},
]


def _data(*queries):
    return {"date": "2026-09-14", "window": "3개월", "queries": list(queries)}


class QueueTest(unittest.TestCase):
    def test_a_page_that_exists_but_ranks_far_down_is_a_repair_job(self) -> None:
        """이 줄이 이 도구를 만든 이유다 — 전용 글이 있는데 66위면 새 글보다 그 글이 먼저다."""
        row = sq.build(_data({"query": "kospi trading hours", "impressions": 6, "clicks": 0, "position": 66.0}), POSTS)[0]
        self.assertIn("koreas-trading-day", row["post"])
        self.assertIn("순위가 밀렸습니다", row["action"])

    def test_striking_distance_beats_a_far_away_query_with_the_same_impressions(self) -> None:
        """5위는 한 계단이면 1페이지 위쪽이고, 80위는 글을 새로 써야 한다.

        클릭 차이만 세면 80위가 늘 이긴다(3위까지 올리면 더 많이 얻으니까). 그래서 **올리기 쉬운
        정도**를 곱한다. 이걸 빼면 큐가 매일 "가장 먼 검색어"를 1순위로 내민다 — 처음에 그랬다.
        """
        rows = sq.build(_data({"query": "kospi vs kosdaq", "impressions": 5, "clicks": 0, "position": 5.7},
                              {"query": "korea market entry rules", "impressions": 5, "clicks": 0, "position": 80.0}),
                        POSTS)
        self.assertEqual(rows[0]["query"], "kospi vs kosdaq")
        self.assertGreater(rows[0]["gain"], rows[1]["gain"])

    def test_a_one_word_query_is_never_claimed_as_matched(self) -> None:
        """실측: `what is kospi`가 ETF 글에 짝지어졌는데 맞는 글은 `kospi vs kosdaq`이었다.
        낱말이 하나면 그 낱말이 든 아무 글에나 붙는다 — 단정하지 말고 확인하게 넘긴다."""
        row = sq.build(_data({"query": "what is kospi", "impressions": 3, "clicks": 0, "position": 81.3}), POSTS)[0]
        self.assertLess(row["sure"], 1.0)
        self.assertIn("먼저 확인", row["action"])

    def test_action_intent_outranks_definition_at_the_same_numbers(self) -> None:
        """2026-09-18 '행동 의도로 재편': 같은 노출·같은 순위면 `how to buy …`가 `what is …`보다 앞이다 —
        정의형은 AI 개요가 답을 먼저 보여 줘 클릭이 적고, 행동형은 제휴가 붙는 자리다."""
        self.assertEqual(sq.intent("how to buy korean stocks in canada"), "행동")
        self.assertEqual(sq.intent("what is kosdaq"), "정의")
        self.assertEqual(sq.intent("kospi vs kosdaq"), "정의")
        self.assertEqual(sq.intent("ewy vs koru"), "행동")          # ETF 비교는 사는 사람의 검색이다
        self.assertEqual(sq.intent("englishdart"), "중립")
        rows = sq.build(_data({"query": "what is kospi", "impressions": 8, "clicks": 0, "position": 30.0},
                              {"query": "how to buy korean stocks", "impressions": 8, "clicks": 0, "position": 30.0}), [])
        self.assertEqual(rows[0]["query"], "how to buy korean stocks")
        self.assertEqual(rows[0]["intent"], "행동")

    def test_a_query_with_no_page_is_a_new_post(self) -> None:
        row = sq.build(_data({"query": "korea dividend withholding tax rate", "impressions": 4,
                              "clicks": 0, "position": 45.0}), POSTS)[0]
        self.assertIsNone(row["post"])
        self.assertIn("새 글", row["action"])

    def test_the_ctr_curve_only_ever_helps_going_up(self) -> None:
        """이미 3위 안쪽인 검색어에 '올리면 는다'를 붙이면 큐가 거짓말을 한다."""
        row = sq.build(_data({"query": "kospi vs kosdaq", "impressions": 100, "clicks": 20, "position": 1.2}), POSTS)[0]
        self.assertEqual(row["gain"], 0.0)


class RoutineDocTest(unittest.TestCase):
    def test_the_english_guide_doc_picks_topics_from_the_queue(self) -> None:
        """지시문에서 이 줄이 빠지면 루틴은 조용히 옛 방식(목록 순서)으로 돌아간다."""
        from pathlib import Path
        text = (Path(__file__).resolve().parent.parent / "docs" / "routine_guide_en.md").read_text(encoding="utf-8")
        self.assertIn("src.search_queue", text)
        self.assertIn("data/search_queries.json", text)


if __name__ == "__main__":
    unittest.main()
