"""판단(Fermata's Take + 확인 지점)·어제 판정·초보자 설명 검사 (2026-09-08)."""
from __future__ import annotations

import unittest

from src import editorial_judgment

GOOD_CLOSING = {"heading": "Fermata's Take",
                "body": "우리는 이번 하락을 추세 전환이 아니라 숨 고르기로 봅니다. 외국인이 닷새째 순매수인데 지수가 밀린 것은 개인의 차익 실현 때문이었습니다. 9월 10일 종가가 7,000선을 넘는지로 확인하겠습니다.",
                "check": {"due": "2026-09-10", "what": "코스피 종가가 7,000선을 넘는지, 외국인 순매수가 이어지는지"}}


def _doc(closing=None, review=None, headings=("1. 오늘 시장", "2. 어제 본 것, 오늘은 어땠나", "3. 업종")):
    doc = {"market": "kr", "date": "2026-09-08",
           "ko": {"title": "코스피, 7,000선을 넘지 못했습니다",
                  "narrative": [{"heading": h, "body": ("NH투자증권은 목표주가를 올렸습니다. " if i == 0 else "") + "본문입니다."}
                                for i, h in enumerate(headings)],
                  "closing": closing if closing is not None else GOOD_CLOSING}}
    if review:
        doc["review"] = review
    return doc


class JudgmentTest(unittest.TestCase):
    def test_thin_take_and_missing_check_are_caught(self) -> None:
        issues, _ = editorial_judgment.collect_issues(_doc(closing={"body": "짧습니다."}))
        joined = "\n".join(issues)
        self.assertIn("세 문장 이상", joined)
        self.assertIn("closing.check", joined)

    def test_good_take_passes_without_previous(self) -> None:
        issues, _ = editorial_judgment.collect_issues(_doc(), previous=None)
        self.assertEqual(issues, [], issues)

    def test_due_must_be_after_the_post(self) -> None:
        closing = dict(GOOD_CLOSING, check={"due": "2026-09-08", "what": "코스피 종가가 7,000선을 넘는지"})
        issues, _ = editorial_judgment.collect_issues(_doc(closing=closing))
        self.assertTrue(any("이후가 아닙니다" in i for i in issues), issues)

    def test_review_required_when_previous_has_a_check(self) -> None:
        previous = {"market": "kr", "date": "2026-09-07", "ko": {"closing": GOOD_CLOSING}}
        issues, _ = editorial_judgment.collect_issues(_doc(), previous=previous)
        self.assertTrue(any("review가 없습니다" in i for i in issues), issues)
        ok = _doc(review={"of_date": "2026-09-07", "verdict": "hit", "result": "코스피 6,954.52로 7,000선 아래 마감, 외국인 6,482억 순매수"})
        issues, _ = editorial_judgment.collect_issues(ok, previous=previous)
        self.assertEqual(issues, [], issues)
        no_section = _doc(review={"of_date": "2026-09-07", "verdict": "hit", "result": "코스피 6,954.52로 마감했습니다"},
                          headings=("1. 오늘 시장", "2. 업종", "3. 수급"))
        issues, _ = editorial_judgment.collect_issues(no_section, previous=previous)
        self.assertTrue(any("어제 본 것" in i for i in issues), issues)

    def test_old_previous_without_check_is_only_a_note(self) -> None:
        previous = {"market": "kr", "date": "2026-09-07", "ko": {"closing": {"body": "옛 형식."}}}
        issues, notes = editorial_judgment.collect_issues(_doc(), previous=previous)
        self.assertEqual(issues, []); self.assertTrue(notes)

    def test_institution_view_and_repeats(self) -> None:
        base = _doc()
        for s in base["ko"]["narrative"]:
            s["body"] = "코스피는 0.58% 하락했습니다. 외국인은 닷새째 순매수했습니다."
        issues, notes = editorial_judgment.collect_issues(base)
        self.assertTrue(any("증권사·기관" in i for i in issues), issues)
        cited = _doc(); cited["ko"]["narrative"][0]["body"] = "NH투자증권은 목표주가를 8,000으로 올렸습니다. 근거는 반도체 이익입니다."
        issues, _ = editorial_judgment.collect_issues(cited)
        self.assertFalse(any("증권사·기관" in i for i in issues), issues)
        rewrite = dict(base, rewritten="2026-09-08")
        issues, notes = editorial_judgment.collect_issues(rewrite)
        self.assertFalse(any("증권사·기관" in i for i in issues)); self.assertTrue(any("증권사·기관" in n for n in notes))
        prev = {"date": "2026-09-07", "ko": {"narrative": [{"body": "코스피는 0.58% 하락했습니다. 외국인은 닷새째 순매수했습니다."}]}}
        issues, _ = editorial_judgment.collect_issues(cited if False else base, previous_docs=[prev])
        self.assertTrue(any("같은 문장" in i for i in issues), issues)

    def test_position_talk_is_blocked(self) -> None:
        doc = _doc(); doc["ko"]["narrative"][0]["body"] = "저는 매수했습니다."
        issues, _ = editorial_judgment.collect_issues(doc)
        self.assertTrue(any("포지션 화법" in i for i in issues), issues)


if __name__ == "__main__":
    unittest.main()
