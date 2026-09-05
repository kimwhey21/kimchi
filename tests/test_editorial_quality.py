from __future__ import annotations

import unittest

from src import editorial_quality
from src.editorial_quality import (
    EditorialQualityError,
    collect_issues,
    validate_generated,
)


class EditorialQualityTest(unittest.TestCase):
    def test_rejects_translated_month_close_expression(self) -> None:
        with self.assertRaises(EditorialQualityError):
            validate_generated({"title": "뉴욕증시는 8월을 약세로 닫았습니다"})

    def test_rejects_personified_market_expression(self) -> None:
        with self.assertRaises(EditorialQualityError):
            validate_generated({"title": "유가가 오른 날, 뉴욕증시는 물러섰습니다"})

    def test_accepts_direct_market_close_expression(self) -> None:
        validate_generated({"title": "유가 상승에 뉴욕증시는 하락 마감했습니다"})


if __name__ == "__main__":
    unittest.main()


class DeclineWordingTest(unittest.TestCase):
    """등락은 '하락했습니다'로 씁니다.

    벤치마크 본문 60편에서 하락 계열이 523회(하락 425·하락했 72·하락한 26)인데
    내리- 계열은 53회로 10배 차이였습니다. 우리 원고는 반대로 '내렸습니다'가
    기본값이었습니다.
    """

    def test_price_decline_is_blocked(self) -> None:
        for text in ("테슬라는 5.92% 내렸습니다", "3대 지수가 모두 내렸습니다",
                     "2.51% 내린 종목", "가장 크게 내린 종목은 테슬라입니다"):
            with self.subTest(text=text):
                self.assertTrue(collect_issues({"title": "제목", "narrative": [
                    {"heading": "h", "body": text}]}))

    def test_other_senses_are_allowed(self) -> None:
        """'내리다'가 전부 등락은 아닙니다."""
        for text in ("연준이 금리를 0.25%포인트 내렸습니다",
                     "지수를 끌어내린 쪽은 여기입니다",
                     "8만 달러 아래로 내려갔습니다",
                     "유가가 내려오면 부담이 줄어듭니다",
                     "그런 결론을 내렸습니다",
                     "원화 가치가 내려가면 수익률이 깎입니다"):
            with self.subTest(text=text):
                self.assertEqual(collect_issues({"title": "제목", "narrative": [
                    {"heading": "h", "body": text}]}), [])


class JargonTest(unittest.TestCase):
    def test_watchlist_is_blocked(self) -> None:
        """'워치리스트'는 우리 쪽 장치 이름이라 독자에게 뜻이 없습니다."""
        issues = collect_issues({"title": "제목", "narrative": [
            {"heading": "h", "body": "이날 워치리스트에서 가장 큰 상승 폭입니다."}]})
        self.assertEqual(len(issues), 1)
        self.assertIn("워치리스트", issues[0])

    def test_scope_can_still_be_stated(self) -> None:
        self.assertEqual(collect_issues({"title": "제목", "narrative": [
            {"heading": "h", "body": "우리가 보는 종목 가운데 가장 큰 상승 폭입니다."}]}), [])


class InventedWordTest(unittest.TestCase):
    def test_never_used_words_are_blocked(self) -> None:
        """제목에서 걸렀더니 다음 날 소제목에 '반대편'이 나왔습니다."""
        for word in ("반대편", "코앞", "문턱"):
            with self.subTest(word=word):
                self.assertTrue(collect_issues({"title": "제목", "narrative": [
                    {"heading": f"5. {word} – 테슬라와 애플", "body": "본문입니다."}]}))

    def test_benchmark_wording_passes(self) -> None:
        for heading in ("5. 테슬라와 애플의 약세", "3. 반도체 부진", "4. 반대로 오른 종목"):
            with self.subTest(heading=heading):
                self.assertEqual(collect_issues({"title": "제목", "narrative": [
                    {"heading": heading, "body": "본문입니다."}]}), [])


class DeclineVerbExclusionTest(unittest.TestCase):
    """'내려-'로 시작하는 다른 동사를 등락으로 잘못 잡지 않는지 봅니다.

    어미를 하나씩 열거하다 '내려온'을 빠뜨려, "인상 확률이 내려온 자리에서"가
    걸렸습니다(2026-09-05). 지금은 어간 음절 블록 전체를 제외합니다.
    """

    def test_other_verbs_are_not_declines(self) -> None:
        for text in (
            "인상 확률이 내려온 자리에서 스노우플레이크는 올랐다",
            "금리가 내려오면 근거도 약해진다",
            "지수가 6,400선까지 내려갔다",
            "가격이 8만 달러 아래로 내려왔다",
            "짐을 내려놓았다",
            "값을 내려주었다",
            "자리에서 내려섰다",
        ):
            with self.subTest(text=text):
                self.assertEqual(editorial_quality._decline_wording("본문", text), [])

    def test_real_declines_are_still_caught(self) -> None:
        for text in ("코스피가 1.5% 내렸습니다", "7개가 내렸습니다", "두 배 더 내린 이유"):
            with self.subTest(text=text):
                self.assertTrue(editorial_quality._decline_wording("본문", text))

