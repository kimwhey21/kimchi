"""기준표의 독자용 이름 Checkpoint (2026-09-09, 사용자 결정 "이름은 체크포인트로, 영어로 표기").

라벨은 제목 글자가 아니라 이름표 자리(분류·탭·머리말·표지 kicker)에 두고, 제목에는 확인
날짜를 넣는다. 머리말의 날짜는 원고 최상위 `deadline`에서 오고 관문이 그 값을 확인한다.
"""
from __future__ import annotations

import unittest

from src import editorial_title, feature_checks, publish_feature


class KickerTest(unittest.TestCase):
    def test_checkpoint_kicker_carries_the_deadline(self) -> None:
        doc = {"series": "기준표", "date": "2026-09-08", "deadline": "2026-09-30"}
        self.assertEqual(publish_feature._kicker(doc), "Checkpoint · 9월 30일까지 확인할 것")

    def test_checkpoint_without_deadline_still_shows_the_name(self) -> None:
        self.assertEqual(publish_feature._kicker({"series": "기준표", "date": "2026-09-08"}), "Checkpoint")

    def test_preview_kicker_is_unchanged(self) -> None:
        self.assertEqual(publish_feature._kicker({"series": "프리뷰", "date": "2026-09-08"}), "프리뷰")


class DeadlineTest(unittest.TestCase):
    def test_missing_deadline_is_reported(self) -> None:
        self.assertIn("deadline", feature_checks.deadline_issue({"series": "기준표", "date": "2026-09-08"}) or "")

    def test_deadline_must_be_after_the_post_date(self) -> None:
        self.assertIn("이전", feature_checks.deadline_issue({"date": "2026-09-08", "deadline": "2026-09-08"}) or "")
        self.assertIsNone(feature_checks.deadline_issue({"date": "2026-09-08", "deadline": "2026-09-30"}))

    def test_bad_format_is_reported(self) -> None:
        self.assertIn("YYYY-MM-DD", feature_checks.deadline_issue({"date": "2026-09-08", "deadline": "9월 30일"}) or "")


class TitleDateNoteTest(unittest.TestCase):
    def _doc(self, title: str) -> dict:
        return {"title": title, "narrative": [{"heading": f"{i}. 절 {i}입니다", "body": "b"} for i in range(1, 6)]}

    def test_checkpoint_title_without_a_date_gets_a_note_not_a_block(self) -> None:
        notes: list[str] = []
        issues = editorial_title.collect_issues(self._doc("외국인이 넉 달 만에 돌아왔습니다, 그런데 파는 종목도 있습니다"),
                                                kind="기준표", notes_out=notes)
        self.assertEqual(issues, [])
        self.assertTrue(any("확인 날짜" in n for n in notes), notes)

    def test_dated_title_has_no_note(self) -> None:
        notes: list[str] = []
        editorial_title.collect_issues(self._doc("SK하이닉스 지금 사도 될까? 10월 27일에 갈린다"), kind="기준표", notes_out=notes)
        self.assertFalse(any("확인 날짜" in n for n in notes), notes)

    def test_daily_titles_are_not_nagged(self) -> None:
        notes: list[str] = []
        editorial_title.collect_issues(self._doc("외국인이 넉 달 만에 돌아왔습니다, 그런데 파는 종목도 있습니다"),
                                       kind="시황", min_sections=1, notes_out=notes)
        self.assertFalse(any("확인 날짜" in n for n in notes), notes)


if __name__ == "__main__":
    unittest.main()
