"""기준표 검사 테스트.

여기 있는 사례는 전부 2026-09-06 첫 편에서 실제로 고친 것들입니다. 검사가
그때의 실수를 다시 잡는지 확인합니다.
"""
from __future__ import annotations

import unittest

from src import editorial_title, feature_checks


def _check(doc: dict, graphics: int | None = None, notes_out: list[str] | None = None) -> list[str]:
    """feature_gate와 같은 조합 — 제목·소제목(editorial_title, 모든 글 공통) + 기준표 본문."""
    return (editorial_title.collect_issues(doc, kind="기준표", notes_out=notes_out)
            + feature_checks.collect_issues(doc, graphics, notes_out=notes_out))


def _doc(title: str, sections: int = 7, body_extra: str = "") -> dict:
    return {"ko": {
        "title": title,
        "narrative": [{"heading": f"{i}. 절", "body": "초보자 설명: 본문입니다."}
                      for i in range(1, sections + 1)],
        "closing": {"heading": "Fermata's Take",
                    "body": "10월 27일에 갈립니다. " + body_extra},
    }}


class TitleTest(unittest.TestCase):
    GOOD = "SK하이닉스 지금 사도 될까? 10월 27일에 갈린다"

    def test_good_title_passes(self) -> None:
        self.assertEqual(_check(_doc(self.GOOD), graphics=6), [])

    def test_indicator_jargon_is_a_note_not_a_block(self) -> None:
        """지표 용어는 알려만 줍니다.

        벤치마크에도 예외가 있습니다(`저평가 반도체 주식은? 8개 FWD PER 분석`).
        드문 것을 금지로 바꾸면 쓸 수 있는 제목이 좁아집니다.
        """
        notes: list[str] = []
        issues = _check(
            _doc("SK하이닉스 FWD PER 3.5배. 확인할 다섯 가지"), graphics=6, notes_out=notes)
        self.assertFalse(any("지표 용어" in i for i in issues), issues)
        self.assertTrue(any("지표 용어" in n for n in notes), notes)

    def test_korean_numeral_counts_as_a_hook(self) -> None:
        """`확인할 다섯 가지`는 범위 축소 장치입니다.

        한글 숫자를 못 읽어 '후킹 없음'으로 잡으면, 그 제목의 진짜 문제(지표 용어)를
        놓친 채 엉뚱한 이유로 통과시키거나 막게 됩니다.
        """
        issues = _check(
            _doc("반도체 지금 사도 되나. 확인할 다섯 가지"), graphics=6)
        self.assertFalse(any("후킹 장치가 없" in i for i in issues), issues)

    def test_title_without_any_hook_is_caught(self) -> None:
        issues = _check(
            _doc("메모리 반도체 업황 정리"), graphics=6)
        self.assertTrue(any("후킹 장치가 없" in i for i in issues), issues)

    def test_polite_ending_is_allowed(self) -> None:
        """벤치마크 시황 제목의 15%가 존댓말로 끝납니다. 막지 않습니다."""
        self.assertEqual(_check(
            _doc("SK하이닉스 지금 사도 될까? 10월 27일에 갈립니다"), graphics=6), [])


class BodyTest(unittest.TestCase):
    def test_missing_graphics_is_caught(self) -> None:
        """첫 편이 0장으로 나갔습니다."""
        issues = _check(_doc(TitleTest.GOOD), graphics=0)
        self.assertTrue(any("시각자료" in i for i in issues), issues)

    def test_graphics_unknown_is_not_a_failure(self) -> None:
        """장수를 모를 때(원고만 검사) 그것 때문에 막지는 않습니다."""
        issues = _check(_doc(TitleTest.GOOD))
        self.assertFalse(any("시각자료" in i for i in issues), issues)

    def test_missing_check_date_is_caught(self) -> None:
        """날짜가 없으면 기준표가 아니라 그냥 시황입니다."""
        doc = _doc(TitleTest.GOOD)
        doc["ko"]["closing"]["body"] = "그렇게 봅니다."
        doc["ko"]["title"] = "SK하이닉스 지금 사도 될까"
        issues = _check(doc, graphics=6)
        self.assertTrue(any("확인 날짜" in i for i in issues), issues)

    def test_title_date_must_appear_in_body(self) -> None:
        doc = _doc("SK하이닉스 지금 사도 될까? 11월 3일에 갈린다")
        issues = _check(doc, graphics=6)
        self.assertTrue(any("11월 3일" in i for i in issues), issues)

    def test_position_voice_is_caught(self) -> None:
        """우리는 종목을 들고 있지 않습니다. 1인칭 포지션 화법은 거짓말이 됩니다."""
        issues = _check(
            _doc(TitleTest.GOOD, body_extra="저는 매도했습니다."), graphics=6)
        self.assertTrue(any("포지션 화법" in i for i in issues), issues)

    def _with_body(self, body: str) -> dict:
        doc = _doc(TitleTest.GOOD)
        for section in doc["ko"]["narrative"]:
            section["body"] = body
        return doc

    def test_beginner_note_required_when_jargon_piles_up(self) -> None:
        """설명이 필요한 말이 여럿 나오는데 설명이 없으면 막습니다.

        무조건 요구하지도, 그냥 넘기지도 않습니다. 벤치마크의 30%라는 숫자는
        "열 편 중 세 편에 넣어라"가 아니라 **그런 말이 나온 글에는 넣은 결과**입니다.
        """
        issues = _check(
            self._with_body("PER은 3.5배이고 HBM 계약가가 오릅니다."), graphics=6)
        self.assertTrue(any("초보자" in i for i in issues), issues)

    def test_beginner_note_present_passes(self) -> None:
        issues = _check(
            self._with_body("초보자 설명: PER은 …. HBM 계약가가 오릅니다."), graphics=6)
        self.assertEqual(issues, [])

    def test_few_jargon_terms_only_note(self) -> None:
        notes: list[str] = []
        issues = _check(
            self._with_body("순매수가 늘었습니다."), graphics=6, notes_out=notes)
        self.assertFalse(any("초보자" in i for i in issues), issues)
        self.assertTrue(any("설명" in n for n in notes), notes)

    def test_plain_body_needs_nothing(self) -> None:
        """설명할 말이 없는 글에까지 설명을 요구하지 않습니다."""
        notes: list[str] = []
        issues = _check(
            self._with_body("주가가 올랐습니다."), graphics=6, notes_out=notes)
        self.assertEqual(issues, [])
        self.assertEqual([n for n in notes if "설명" in n], [])


class RealArticleTest(unittest.TestCase):
    def test_the_published_draft_passes(self) -> None:
        import json
        from pathlib import Path
        path = (Path(__file__).resolve().parent.parent
                / "editorial/features/kr_2026-09-06_hynix_per.json")
        if not path.exists():
            self.skipTest("원고 파일이 없습니다")
        doc = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(_check(doc, graphics=6), [])


if __name__ == "__main__":
    unittest.main()


class ReversalHookTest(unittest.TestCase):
    """`반대로`·`오히려`는 접속사가 아니지만 반전입니다.

    코퍼스에 `반대로` 224회, `오히려` 141회로 벤치마크가 가장 자주 쓰는 반전
    표현인데, 검사가 접속사만 보고 있어 실제 제목을 막았습니다(2026-09-07).
    """

    def test_bandaero_counts_as_a_hook(self) -> None:
        issues = _check(
            _doc("은행·보험만 무너진 금요일, 그날 밤 금리는 반대로 갔다"), graphics=6)
        self.assertFalse(any("후킹 장치가 없" in i for i in issues), issues)

    def test_ohiryeo_counts_as_a_hook(self) -> None:
        issues = _check(
            _doc("반도체가 밀린 날 오히려 오른 업종"), graphics=6)
        self.assertFalse(any("후킹 장치가 없" in i for i in issues), issues)

    def test_plain_label_still_has_no_hook(self) -> None:
        """느슨하게 만들었다고 아무 제목이나 통과하면 안 됩니다."""
        issues = _check(_doc("메모리 반도체 업황 정리"), graphics=6)
        self.assertTrue(any("후킹 장치가 없" in i for i in issues), issues)
