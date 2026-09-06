"""수사·단위 어법 검사.

2026-09-06에 `실적일까지 일곱 주`라고 썼습니다. 벤치마크 100편에 `일곱`은 0회이고
주 단위 58회가 전부 숫자였습니다.
"""
from __future__ import annotations

import unittest

from scripts import check_against_benchmark as cab


def _doc(text: str) -> dict:
    return {"ko": {"title": "제목", "narrative": [{"heading": "1.", "body": text}],
                   "closing": {"heading": "Take", "body": ""}}}


class NumeralUnitTest(unittest.TestCase):
    def test_native_numeral_with_week_is_caught(self) -> None:
        issues = cab.check(_doc("실적일까지 일곱 주가 남았습니다."))
        self.assertTrue(issues)
        self.assertIn("일곱 주", issues[0])

    def test_digit_form_passes(self) -> None:
        self.assertEqual(cab.check(_doc("실적일까지 7주가 남았습니다.")), [])

    def test_han_ju_is_an_idiom(self) -> None:
        """`한 주`는 벤치마크에 18회 나오는 관용입니다."""
        self.assertEqual(cab.check(_doc("한 주 동안 이어졌습니다.")), [])

    def test_units_that_take_native_numerals_are_not_flagged(self) -> None:
        """`가지`·`번`·`달`은 벤치마크가 고유어로 씁니다."""
        for phrase in ("확인할 다섯 가지", "두 번 반복됐습니다", "두 달 만에"):
            with self.subTest(phrase=phrase):
                self.assertEqual(cab.check(_doc(phrase)), [])

    def test_other_numeric_units(self) -> None:
        for phrase in ("세 개월 만에", "다섯 달러 올랐습니다", "두 년"):
            with self.subTest(phrase=phrase):
                self.assertTrue(cab.check(_doc(phrase)), phrase)

    def test_units_that_look_numeric_but_are_not(self) -> None:
        """`분기`·`개`는 고유어도 실제로 씁니다.

        처음에는 이것도 잡았는데 벤치마크에 `두 분기 연속`, `세 개 이상`이
        실제로 있었습니다. 오탐 하나가 검사 전체를 못 믿게 만듭니다.
        """
        for phrase in ("두 분기 연속 하락한다면", "세 개 이상이 겹치면", "두 명이 샀습니다"):
            with self.subTest(phrase=phrase):
                self.assertEqual(cab.check(_doc(phrase)), [])

    def test_adjective_ending_is_not_a_numeral(self) -> None:
        """`강한 달러`의 `한`은 수사가 아니라 어미입니다."""
        for phrase in ("강한 달러 강세가 이어집니다", "막대한 달러 자금이 생겼습니다"):
            with self.subTest(phrase=phrase):
                self.assertEqual(cab.check(_doc(phrase)), [])

    def test_normal_prose_produces_no_noise(self) -> None:
        """정상 문장에서 지적이 쏟아지면 아무도 안 봅니다.

        옛 판은 낱말을 통째로 대조해 평범한 문장에서도 30개씩 뱉었습니다.
        """
        body = ("SK하이닉스가 9월 4일 3.20% 올랐습니다. 52주 고점에서 44.9% "
                "내려온 자리이고, 증권사 38곳의 평균 목표주가는 두 배에 가깝습니다.")
        self.assertEqual(cab.check(_doc(body)), [])


if __name__ == "__main__":
    unittest.main()
