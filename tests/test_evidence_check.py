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


class NumberMatchTest(unittest.TestCase):
    """근거 구절의 숫자와 원문 숫자(감사 F-088: '39조 달러'의 원문이 '$38.5 trillion')."""

    def test_miscopied_numbers_are_caught(self) -> None:
        self.assertTrue(ec.number_mismatches("부채 39조 달러", "debt of $38.5 trillion"))
        self.assertTrue(ec.number_mismatches("1907년 10월", "in October 1906"))
        self.assertTrue(ec.number_mismatches("S&P500 7,722.72", "closed at 7,773.95"))

    def test_unit_conversions_and_dates_pass(self) -> None:
        for claim, original in (("예금주 1만 7,000명", "17,000 depositors"), ("3,500만 달러", "$35 million"),
                                ("1,000억 개", "capped at 100 billion tokens"), ("10월 8일", "on october 8."),
                                ("9월 27일", "sun, 27/09/2026 - 6:57"), ("2029년까지 60만 달러", "$600,000 by 2029")):
            with self.subTest(claim=claim):
                self.assertEqual(ec.number_mismatches(claim, original), [])

    def test_sample_evidence_has_no_mismatch(self) -> None:
        doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual([e["claim"] for e in doc["evidence"] if ec.number_mismatches(e["claim"], e["original"])], [])


class UnsplashPingTest(unittest.TestCase):
    """Unsplash 열쇠 규칙: 고른 사진마다 '썼음' 신호(2026-10-06 결정)."""

    def test_ids_are_collected_and_missing_ones_are_named(self) -> None:
        from src import unsplash_ping
        doc = {"featured_photo": {"url": "https://images.unsplash.com/photo-1", "unsplash_id": "abc"},
               "ko": {"insight_section": {"stories": [{"image": {"url": "https://images.unsplash.com/photo-2"}}]}}}
        self.assertEqual(unsplash_ping.photo_ids(doc), ["abc"])
        self.assertEqual(len(unsplash_ping.missing_ids(doc)), 1)

    def test_ping_once_per_manuscript_and_photo(self) -> None:
        import tempfile
        from unittest import mock
        from src import unsplash_ping
        ledger = Path(tempfile.mkdtemp()) / "pinged.json"
        get = mock.Mock(return_value=mock.Mock(status_code=200))
        doc = {"featured_photo": {"url": "x", "unsplash_id": "abc"}}
        self.assertEqual(unsplash_ping.ping(doc, "key", name="m.json", ledger=ledger, get=get), (1, []))
        self.assertEqual(unsplash_ping.ping(doc, "key", name="m.json", ledger=ledger, get=get), (0, []))
        self.assertEqual(get.call_count, 1)
        self.assertIn("/photos/abc/download", get.call_args.args[0])


class ChallengePageTest(unittest.TestCase):
    def test_bot_challenge_is_not_page_text_and_browser_is_tried_only_when_allowed(self):
        """2026-10-11: 봇 검사 화면(200 'Just a moment…')을 본문으로 읽어 '인용이 없다'로 막았다 — 못 연 것으로 보고, 이 맥에서만 크롬으로 다시 연다."""
        import os
        from unittest import mock
        from src import evidence_check as ec
        page = mock.Mock(text="<html><title>Just a moment...</title><body>checking</body></html>", raise_for_status=lambda: None)
        with mock.patch.object(ec.requests, "get", return_value=page), mock.patch.object(ec, "_browser_text", return_value="real body") as br:
            ec._CACHE.clear()
            with mock.patch.dict(os.environ, {"EVIDENCE_BROWSER": ""}):
                self.assertIsNone(ec.page_text("https://example.com/a"))
            br.assert_not_called()
            ec._CACHE.clear()
            with mock.patch.dict(os.environ, {"EVIDENCE_BROWSER": "1"}):
                self.assertEqual(ec.page_text("https://example.com/a"), "real body")
        ec._CACHE.clear()


class NoFetchDomainTest(unittest.TestCase):
    def test_sites_the_mac_cannot_open_are_refused_at_writing_time(self):
        """2026-10-11: 루틴이 쓸 때는 열렸지만 맥의 게시 직전 검사가 못 여는 사이트 — 관문에서 미리 막는다(열어 보지도 않는다)."""
        from src import evidence_check as ec
        doc = {"sources": [{"name": "x", "url": "https://www.autoevolution.com/news/a.html"}],
               "evidence": [{"claim": "가", "url": "https://www.autoevolution.com/news/a.html", "original": "a" * 30}]}
        issues = ec.evidence_issues(doc, fetch=lambda u: (_ for _ in ()).throw(AssertionError("열지 않는다")), numbers=False)
        self.assertTrue(any("autoevolution.com" in i and "다른 출처" in i for i in issues), issues)
        self.assertIsNone(ec._blocked_domain("https://theprint.in/x"))
