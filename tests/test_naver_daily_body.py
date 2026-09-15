"""시황도 네이버 전용 본문을 쓴다 (2026-09-14부터).

2026-09-13에 네이버에 올라간 글과 본진 글의 겹침을 실측했다 — 시황 21.9~40.9%, 가이드 2.1%, 프리뷰 0.5%.
시황만 `naver.narrative` 규칙에서 빠져 있어 본진 문장을 그대로 옮기고 있었고, 하루 두 번으로 가장 자주
올리는 종류였다. 유사문서로 걸리면 네이버 검색 통로가 통째로 막힌다(네이버는 본진으로는 못 뚫는다).
"""
from __future__ import annotations

import unittest

from src import feature_checks


def _daily(date: str = "2026-09-14", naver: dict | None = None) -> dict:
    doc = {"market": "kr", "date": date,
           "ko": {"title": "코스피 1.76% 하락, 원인은 유가에 있었습니다",
                  "narrative": [{"heading": "1. 마감", "body": "코스피가 유가 100달러 재돌파에 눌려 1.76% 내렸습니다."}],
                  "closing": {"heading": "Fermata's Take", "body": "우리는 유가를 봅니다."}}}
    if naver is not None:
        doc["naver"] = naver
    return doc


SENTENCE = "네이버 독자를 위해 본진과 다른 말로 새로 쓴 문장입니다. "


def _sections(n: int, chars: int) -> dict:
    """문장 경계가 온전한 본문 — 문장 단위로 채운다(잘린 조각은 중복 검사를 헛돌게 한다)."""
    per = max(1, round(chars / n / len(SENTENCE)))
    body = SENTENCE * per
    return {"narrative": [{"heading": f"소제목 {i}", "body": body} for i in range(1, n + 1)]}


class DailySpecTest(unittest.TestCase):
    def test_the_daily_rule_ended_on_the_day_naver_became_the_only_home(self) -> None:
        """시황이 네이버 전용이 된 뒤로는 네이버용 본문을 요구하지 않는다(2026-09-16부터)."""
        self.assertIsNone(feature_checks.naver_spec({"market": "kr", "date": "2026-09-16"}))
        self.assertIsNotNone(feature_checks.naver_spec({"market": "kr", "date": "2026-09-15"}))

    def test_daily_briefs_are_covered_from_the_start_date_only(self) -> None:
        self.assertIsNone(feature_checks.naver_spec(_daily("2026-09-13")))
        self.assertEqual(feature_checks.naver_spec(_daily())[0], "시황")

    def test_the_daily_threshold_is_lighter_than_the_guide_one(self) -> None:
        _, sections, chars = feature_checks.naver_spec(_daily())
        self.assertEqual((sections, chars), (feature_checks.NAVER_DAILY_SECTIONS, feature_checks.NAVER_DAILY_CHARS))
        self.assertLess(chars[0], feature_checks.NAVER_CHARS[0])   # 분량을 늘리는 것이 목적이 아니다
        self.assertLess(sections[0], feature_checks.NAVER_SECTIONS[0])

    def test_a_series_manuscript_is_not_treated_as_a_daily_brief(self) -> None:
        self.assertIsNone(feature_checks.naver_spec({"series": "프리뷰", "market": "us", "date": "2026-09-20"}))


class DailyIssueTest(unittest.TestCase):
    def test_a_missing_naver_body_blocks(self) -> None:
        issues = feature_checks.naver_issues(_daily())
        self.assertEqual(len(issues), 1)
        self.assertIn("시황", issues[0])

    def test_a_proper_naver_body_passes(self) -> None:
        self.assertEqual(feature_checks.naver_issues(_daily(naver=_sections(4, 1400))), [])

    def test_reusing_a_sentence_from_the_main_site_blocks(self) -> None:
        copied = _sections(4, 1400)
        copied["narrative"][0]["body"] += " 코스피가 유가 100달러 재돌파에 눌려 1.76% 내렸습니다."
        joined = "\n".join(feature_checks.naver_issues(_daily(naver=copied)))
        self.assertIn("유사문서", joined)

    def test_too_short_and_too_few_sections_block(self) -> None:
        joined = "\n".join(feature_checks.naver_issues(_daily(naver=_sections(2, 300))))
        self.assertIn("2절", joined)
        self.assertIn("900", joined)


class ClosingBoundaryTest(unittest.TestCase):
    """마무리 문단의 문장도 중복 검사를 받는다 — 2026-09-13까지는 빠져 있었다.

    `main_text`가 본문 마지막 문장과 마무리 첫 문장을 공백 없이 이어 붙여 한 덩어리로 만들었고,
    그래서 그 두 문장만 유사문서 검사를 통과했다. 시황으로 규칙을 넓히다 이 테스트가 찾았다.
    """

    def test_a_sentence_copied_from_the_closing_paragraph_blocks(self) -> None:
        doc = _daily(naver=_sections(4, 1400))
        closing = "우리는 다음 주 유가와 국채금리를 함께 보겠습니다."
        doc["ko"]["closing"]["body"] = closing
        doc["naver"]["narrative"][2]["body"] += " " + closing
        joined = "\n".join(feature_checks.naver_issues(doc))
        self.assertIn("유사문서", joined)


class GateWiringTest(unittest.TestCase):
    def test_the_daily_gate_reports_naver_problems(self) -> None:
        import inspect

        from src import editorial_gate
        source = inspect.getsource(editorial_gate.run)
        self.assertIn("feature_checks.naver_issues(doc)", source)


class RoutineDocTest(unittest.TestCase):
    def test_the_shared_routine_doc_tells_the_routine_to_stop_writing_it(self) -> None:
        """2026-09-15부터 시황은 네이버 전용이라 네이버용 본문을 **쓰지 않는다**(사용자 결정).

        지시문에 옛 규칙이 남아 있으면 루틴은 매일 쓰지 않아도 되는 본문을 계속 쓴다 —
        관문이 요구하지 않으니 아무도 막지 않고, 시간만 두 배로 든다.
        """
        from pathlib import Path
        text = (Path(__file__).resolve().parent.parent / "docs" / "routine_common.md").read_text(encoding="utf-8")
        self.assertIn("원고에 `naver`를 넣지 마십시오", text)
        # 옛 지시("절 3~5개, 본문 합계 900~2,200자")가 남아 있으면 안 된다. 왜 바꿨는지 설명하는
        # 자리에 그 수치가 나오는 것은 기록이라 괜찮다 — 지시문으로 남아 있는지를 본다.
        self.assertNotIn("절 3~5개, 본문 합계 900~2,200자", text)
        # 가이드·주간은 그대로다 — 본진에 쌍둥이가 있다.
        self.assertIn("1,200~3,000자", text)


if __name__ == "__main__":
    unittest.main()
