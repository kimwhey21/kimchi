"""2026-09-26 점검의 작은 구멍들 — 사장님 "9번 제외 모두 고쳐"."""
import unittest
from pathlib import Path
from unittest import mock

from scripts import rule_diff, title_pick
from src import editorial_quality, fetch_movers

ROOT = Path(__file__).resolve().parent.parent


class AdrFilterTest(unittest.TestCase):
    def test_adrs_pass_and_derivatives_do_not(self) -> None:
        ok = fetch_movers._is_us_common_stock
        self.assertTrue(ok("ARM", "Arm Holdings plc American Depositary Shares"))
        self.assertTrue(ok("BTSG", "BrightSpring Health Services, Inc. Common Stock"))      # 'right'가 들어 있다
        self.assertFalse(ok("XP", "Series A Depositary Shares each representing 1/1000th of Preferred"))
        self.assertFalse(ok("XR", "Acme Corp Rights"))
        self.assertFalse(ok("XW", "Acme Corp Warrant"))


class DeclineWordingTest(unittest.TestCase):
    def test_decisions_are_not_price_falls(self) -> None:
        for text in ("연준이 결정을 내렸습니다.", "연준이 내린 결정입니다.", "자료를 내려받아 봤습니다.", "매도 신호를 내렸다."):
            with self.subTest(text=text):
                self.assertEqual(editorial_quality._decline_wording("x", text), [])
        self.assertTrue(editorial_quality._decline_wording("x", "삼성전자가 2% 내렸습니다."))


class RuleDiffTest(unittest.TestCase):
    def test_a_rule_cut_to_its_first_sentence_is_shown(self) -> None:
        old = "- 예약 시각을 마감 정각으로 되돌리지 말 것. 16:00/07:00 정각은 시세가 아직 안 채워져 죽는다 — 두 시장 모두 20분 뒤다.\n"
        new = "- 예약 시각을 마감 정각으로 되돌리지 말 것.\n"
        self.assertEqual(rule_diff.removed_rules(old, new), [])          # 고쳐 쓴 줄은 빠진 줄로 세지 않는다(그대로)
        self.assertEqual(len(rule_diff.shortened_rules(old, new)), 1)    # 대신 '앞부분만 남은 줄'로 보여 준다
        self.assertEqual(rule_diff.shortened_rules(old, "머리\n" + old), [])


class TitlePickWindowTest(unittest.TestCase):
    def test_title_pick_compares_with_the_same_recent_titles_as_the_gate(self) -> None:
        with mock.patch.object(title_pick.title_feed, "feed_titles", return_value=[]) as feed, \
             mock.patch("builtins.print"):
            title_pick.main(["kr", "후보 하나", "후보 둘", "후보 셋"])
        self.assertEqual(feed.call_args.kwargs.get("count", 5), 5)


class NaverAuditScopeTest(unittest.TestCase):
    def test_full_body_series_are_audited(self) -> None:
        text = (ROOT / "scripts" / "naver_audit.py").read_text(encoding="utf-8")
        self.assertNotIn('"/guides/" in rel', text)
        self.assertIn('"/magazine/" in rel', text)


if __name__ == "__main__":
    unittest.main()
