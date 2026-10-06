"""인용·숫자 근거 표(2026-10-06) — 출처에 없는 숫자·인용을 막는다. 바깥 접속 없이 가짜 페이지로 본다."""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from src import evidence_check as ec

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "magazine_sample.json"


class EvidenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.page = ec.normalize(" ".join(e["original"] for e in self.doc["evidence"]))

    def check(self, doc, **kw):
        return ec.evidence_issues(doc, fetch=lambda url: self.page, **kw)

    def test_fixture_passes(self) -> None:
        self.assertEqual(self.check(self.doc), [])

    def test_changed_number_in_original_is_caught(self) -> None:
        doc = copy.deepcopy(self.doc)
        doc["evidence"][12]["original"] = doc["evidence"][12]["original"].replace("504", "540")
        self.assertTrue(any("출처 페이지에 없습니다" in i for i in self.check(doc)))

    def test_number_sentence_without_evidence_is_caught(self) -> None:
        doc = copy.deepcopy(self.doc)
        doc["evidence"].pop(0)
        self.assertTrue(any(i.startswith("근거 없음") for i in self.check(doc)))

    def test_unopenable_source_and_missing_url(self) -> None:
        self.assertTrue(any("열 수 없습니다" in i for i in ec.evidence_issues(self.doc, fetch=lambda url: None)))
        doc = copy.deepcopy(self.doc)
        doc["sources"][0]["url"] = ""
        self.assertTrue(any("주소(url)가 없습니다" in i for i in self.check(doc)))

    def test_quotes_only_mode_for_other_series(self) -> None:
        doc = {"ko": {"narrative": [{"body": "코스피는 1.2% 올랐습니다. 그는 “금리가 더 오를 수 있다”고 말했습니다."}]}, "sources": []}
        issues = ec.evidence_issues(doc, fetch=lambda url: "", numbers=False)
        self.assertEqual(len(issues), 1)
        self.assertIn("금리가 더 오를 수", issues[0])


if __name__ == "__main__":
    unittest.main()


class EventClaimTest(unittest.TestCase):
    """일정 글의 사건 문장(감사 F-029: 있지도 않은 셧다운)."""

    def test_event_sentences_need_evidence_only_when_asked(self) -> None:
        doc = {"ko": {"narrative": [{"body": "다음 주 CPI가 나옵니다. 10월 1일부터 이어진 셧다운이 변수입니다."}]}}
        self.assertEqual(ec.needed_claims(doc, numbers=False), [])
        self.assertEqual(ec.needed_claims(doc, numbers=False, events=True), ["10월 1일부터 이어진 셧다운이 변수입니다."])
        issues = ec.evidence_issues(doc, fetch=lambda u: None, numbers=False, events=True)
        self.assertTrue(any("근거 없음" in i for i in issues))
