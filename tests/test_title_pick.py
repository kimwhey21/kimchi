"""관문을 거르는 문에서 고르는 문으로 (2026-09-18, 사장님 "a진행").

지적 다섯 번의 공통 원인: 쓰는 쪽은 관문을 넘는 최소를 찾는다. 그래서 후보 셋 이상을 축을 달리해 적게 하고,
관문이 독자 피드와의 거리 점수가 가장 높은 후보를 제목으로 요구한다. 여기서는 (1) 2026-09-18의 실제 후보 셋에서
점수가 사장님이 고른 1번을 뽑는 것, (2) 후보가 없거나 셋 미만이거나 축이 같으면 막는 것, (3) 제목이 최고점
후보가 아니면 막는 것, (4) 가이드는 해당 없음, (5) CLI가 같은 답을 내는 것을 고정한다.
"""
from __future__ import annotations

import unittest

from scripts import title_pick
from src import editorial_title
from src.editorial_title import candidate_issues, collect_issues, title_distance

FEED = [   # 2026-09-18 아침, 미국장 9/17 글 바로 위 네 편(실측)
    "오늘 밤 FOMC가 3년 2개월 만의 금리 인상을 결정합니다",
    "다우 1.21% 하락, 이유는 금리 인상에 흔들린 은행주입니다",
    "3년 2개월 만의 금리 인상, 코스피는 오히려 잠잠했습니다",
    "오늘 밤 필라델피아 지수가 은행주 사흘째를 정합니다",
]
OLD = "반도체는 일제히 웃었는데, 은행주는 왜 못 웃었을까요"
PICK = "인텔 7.67% 급등, 이 반등에서 확인할 것 하나"          # 사장님 "1번제목으로 가고"
OTHER = "연준이 올린 다음 날, 반도체는 왜 뛰었을까"
LOWER = "코스피 반등 이틀째, 내일 아침 이것 하나만 보세요"   # 통과는 하지만 '코스피'가 겹쳐 점수가 낮은 후보
PRICE = {"watchlist": {"INTC": {"name": "인텔", "change_pct": 7.67}}}


class DistanceTest(unittest.TestCase):
    def test_the_owner_pick_scores_highest_on_the_real_feed(self) -> None:
        scores = {t: title_distance(t, FEED)[0] for t in (OLD, PICK, OTHER, LOWER)}
        self.assertGreaterEqual(scores[PICK], scores[OTHER])   # 둘 다 빈 축을 하나씩 채운다 — 동점이면 어느 쪽이든 된다
        self.assertGreater(scores[PICK], scores[LOWER])
        self.assertGreater(scores[LOWER], scores[OLD])

    def test_filling_a_missing_axis_and_new_subject_score_up(self) -> None:
        score, why = title_distance(PICK, FEED)
        joined = " ".join(why)
        self.assertIn("독자 축", joined)
        self.assertIn("없던 주인공", joined)
        self.assertGreaterEqual(score, 4)

    def test_repeating_subject_and_contrast_score_down(self) -> None:
        score, why = title_distance(OLD, FEED)
        joined = " ".join(why)
        self.assertIn("'은행주'", joined)
        self.assertIn("대비 꼴", joined)

    def test_rare_axis_is_rewarded_once_in_ten(self) -> None:
        score, why = title_distance("우리가 오늘 반도체를 사지 않는 이유", FEED)
        self.assertTrue(any("1인칭" in w for w in why), why)
        self.assertTrue(any("감춤 이유" in w for w in why), why)

    def test_a_count_word_is_not_a_question(self) -> None:
        self.assertEqual(editorial_title.heading_shape(PICK), "이름표")          # '…하나'는 질문이 아니다
        self.assertNotIn("질문", editorial_title.title_axes_all(PICK))
        self.assertIn("질문", editorial_title.title_axes_all("물가 발표 하루 전, 외국인은 무엇을 샀나"))


class CandidateGateTest(unittest.TestCase):
    def _doc(self, title, candidates=None):
        ko = {"title": title, "narrative": [{"heading": f"{i}. 소제목 {i}입니다", "body": "b"} for i in range(1, 12)]}
        if candidates is not None:
            ko["title_candidates"] = candidates
        return ko

    def test_missing_candidates_block_daily_and_preview_but_not_guides(self) -> None:
        for kind in ("시황", "프리뷰", "기준표"):
            issues = candidate_issues(self._doc(PICK), FEED, PRICE, kind)
            self.assertTrue(any("제목 후보가 없습니다" in i for i in issues), (kind, issues))
        self.assertEqual(candidate_issues(self._doc(PICK), FEED, PRICE, "가이드"), [])
        self.assertEqual(candidate_issues(self._doc(PICK), FEED, PRICE, None), [])

    def test_owner_pick_with_three_candidates_passes(self) -> None:
        ko = self._doc(PICK, [OLD, PICK, OTHER])
        self.assertEqual(candidate_issues(ko, FEED, PRICE, "시황"), [])
        self.assertEqual([i for i in collect_issues(ko, PRICE, kind="시황", recent_titles=FEED) if "후보" in i], [])

    def test_choosing_a_closer_candidate_is_blocked(self) -> None:
        issues = candidate_issues(self._doc(LOWER, [OLD, PICK, LOWER]), FEED, PRICE, "시황")
        self.assertTrue(any("가장 먼 후보는" in i and PICK in i for i in issues), issues)
        # 동점(둘 다 빈 축을 채움)은 어느 쪽을 골라도 막지 않는다
        self.assertEqual(candidate_issues(self._doc(OTHER, [OLD, PICK, OTHER]), FEED, PRICE, "시황"), [])

    def test_title_must_be_one_of_the_candidates(self) -> None:
        issues = candidate_issues(self._doc("금리 하나가 바꾼 하루", [OLD, PICK, OTHER]), FEED, PRICE, "시황")
        self.assertTrue(any("후보에 없습니다" in i for i in issues), issues)

    def test_too_few_or_same_axis_candidates_are_blocked(self) -> None:
        issues = candidate_issues(self._doc(PICK, [PICK, OTHER]), FEED, PRICE, "시황")
        self.assertTrue(any("2개입니다" in i for i in issues), issues)
        same = ["이 반등, 내일도 이어질까?", "반도체 랠리, 다음 주도 이어질까?", "인텔 급등, 오늘 밤도 이어질까?"]
        issues = candidate_issues(self._doc(same[0], same), FEED, PRICE, "시황")
        self.assertTrue(any("축이 모두 같습니다" in i for i in issues), issues)

    def test_a_candidate_breaking_single_title_rules_is_reported(self) -> None:
        bad = "인텔 7.67% 급등, 마이크론 5.5% 급등, 반도체의 날"   # 등락률 둘
        issues = candidate_issues(self._doc(PICK, [PICK, OTHER, bad]), FEED, PRICE, "시황")
        self.assertTrue(any("제목 규칙에 걸립니다" in i and "등락률" in i for i in issues), issues)


class CliTest(unittest.TestCase):
    def test_cli_names_the_same_winner_as_the_gate(self) -> None:
        out = title_pick.render([OLD, PICK, LOWER], FEED, PRICE, "시황", chosen=LOWER)
        self.assertIn(f"고를 것: 「{PICK}」", out)
        self.assertIn("관문이", out)          # 지금 제목이 1등이 아니면 그렇게 말한다
        self.assertIn("[막힘", out)           # 옛 제목은 막힘으로 표시된다


if __name__ == "__main__":
    unittest.main()
