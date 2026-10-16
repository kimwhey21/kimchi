"""오늘의 한 편(시리즈 "칼럼", 2026-10-13) — 관문·숫자 대조·네이버 블록·증명서가 같은 시리즈를 같은 뜻으로 읽는지."""
from __future__ import annotations

import copy
import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from scripts import naver_post, title_pick
from src import daily_proof, editorial_title, feature_checks, feature_gate, publish_feature, source_check

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "tests" / "fixtures" / "column_sample.json"


def _doc() -> dict:
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


def _blocking(doc: dict) -> list[str]:
    from unittest import mock
    try:
        # 최근 칼럼 제목과의 대조는 그날 원고에 따라 달라진다 — 견본 시험은 빈 목록과 대조한다
        with mock.patch.object(feature_gate, "recent_titles", return_value=[]):
            feature_gate.run(doc, graphics=len(doc["graphics"]), path=SAMPLE)
    except feature_gate.FeatureGateError as exc:
        return [line[2:] for line in str(exc).splitlines() if line.startswith("- ")]
    return []


class ColumnGateTest(unittest.TestCase):
    def test_sample_passes_the_gate(self) -> None:
        self.assertEqual(_blocking(_doc()), [])

    def test_wrong_move_against_price_file_is_blocked(self) -> None:
        doc = _doc()
        doc["ko"]["narrative"][2]["body"] += "\n오늘 SK하이닉스는 9.09% 하락했습니다."
        self.assertTrue(any(i.startswith("숫자 —") and "SK하이닉스" in i for i in _blocking(doc)))

    def test_missing_price_file_is_blocked(self) -> None:
        doc = _doc()
        doc["date"] = "2027-03-01"   # 한국장·미국장 시세 파일이 모두 없는 날
        self.assertTrue(any("대조할 시세 파일이 없습니다" in i for i in _blocking(doc)))

    def test_us_story_numbers_are_checked_against_last_night(self) -> None:
        """칼럼은 어젯밤 미국장도 다룬다(2026-10-16) — 미국장 숫자는 원고 날짜 전 가장 최근 미국장 시세 파일과 대조한다."""
        kr, us = feature_gate.column_price_files({"date": "2026-10-16"})
        self.assertEqual(us.name, "price_us_2026-10-15.json")
        doc = _doc()
        doc["date"] = "2026-10-16"
        pd = json.loads(us.read_text(encoding="utf-8"))
        nv = next(v for v in pd["watchlist"].values() if v["name"] == "엔비디아")
        wrong = round(abs(nv["change_pct"]) + 1.0, 2)
        doc["ko"]["narrative"][2]["body"] += f"\n어젯밤 뉴욕에서 엔비디아는 {wrong}% 하락했습니다."
        from unittest import mock
        with mock.patch.object(feature_gate, "column_price_files", return_value=(None, us)):   # 미국장 파일만 — 한국장 파일이 생겨도 흔들리지 않게
            self.assertTrue(any("엔비디아" in i and "price_us_2026-10-15" in i for i in _blocking(doc)))
            doc["ko"]["narrative"][2]["body"] = doc["ko"]["narrative"][2]["body"].replace(f"{wrong}%", f"{abs(nv['change_pct']):.2f}%")
            self.assertFalse(any("숫자" in i for i in _blocking(doc)))

    def test_hook_form_applies(self) -> None:
        doc = _doc()
        doc["ko"]["narrative"][0]["heading"] = "도입"
        doc["ko"]["narrative"][0]["body"] += "\n오늘은 세 가지를 보겠습니다."
        issues = _blocking(doc)
        self.assertTrue(any("소제목 없는 도입" in i for i in issues))
        self.assertTrue(any("길안내" in i for i in issues))

    def test_thresholds(self) -> None:
        self.assertEqual(feature_checks.SERIES_LIMITS["칼럼"]["graphics"], 3)
        self.assertEqual(editorial_title.SECTION_FLOORS["칼럼"], 5)
        self.assertEqual(source_check.SERIES_MIN_SOURCES["칼럼"], 3)
        self.assertIn("칼럼", editorial_title.CANDIDATE_KINDS)
        self.assertEqual(feature_gate.SERIES_FOLDER["칼럼"], "columns")
        self.assertEqual(title_pick.KINDS["column"], "칼럼")

    def test_sources_must_be_named_in_body(self) -> None:
        doc = _doc()
        for s in doc["ko"]["narrative"]:
            s["body"] = s["body"].replace("(로이터)", "").replace("(이데일리)", "").replace("(머니투데이)", "")
        result = source_check.collect(doc)
        self.assertLess(result["distinct"], 3)


class ColumnOutputTest(unittest.TestCase):
    def test_private_and_kicker(self) -> None:
        doc = _doc()
        self.assertTrue(publish_feature._skips_wordpress(doc))
        self.assertEqual(publish_feature._kicker(doc), "오늘의 한 편 · 10월 13일 장 마감 뒤")

    def test_naver_blocks(self) -> None:
        post = naver_post.build(SAMPLE, None)
        self.assertEqual(post["title"], "하이닉스는 왜 오늘 10%나 떨어졌을까")
        self.assertEqual(post["category"], "시황")
        blocks = post["blocks"]
        self.assertNotIn(("h", ""), blocks)                                  # 도입은 소제목 없이 문단만
        self.assertEqual(blocks[0][0], "p")
        heads = [b[1] for b in blocks if b[0] == "h"]
        self.assertIn("Fermata의 시선", heads)
        self.assertNotIn("Fermata's Take", heads)
        self.assertEqual(heads[-1], "자료 확인")


class ColumnProofTest(unittest.TestCase):
    def _arts(self, day: dt.date, files: list[str]) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in files:
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_text("{}", encoding="utf-8")
            return {n: ok for n, ok, _ in daily_proof.expected_artifacts(day, set(), root)}

    def test_expected_on_trading_days_from_start(self) -> None:
        self.assertNotIn("오늘의 칼럼", self._arts(dt.date(2026, 10, 13), []))
        self.assertFalse(self._arts(dt.date(2026, 10, 14), [])["오늘의 칼럼"])
        self.assertTrue(self._arts(dt.date(2026, 10, 14), ["editorial/columns/2026-10-14_x.json"])["오늘의 칼럼"])
        self.assertNotIn("오늘의 칼럼", self._arts(dt.date(2026, 10, 17), []))   # 토요일


if __name__ == "__main__":
    unittest.main()


class CoverColourTest(unittest.TestCase):
    """표지 숫자(2026-10-13): 내린 값은 파랑, 오른 값·부호 없는 값은 원래 색."""

    def test_sign_decides_colour(self) -> None:
        from src import feature_graphics as fg
        self.assertEqual(fg._side_colour({"value": "-10.09%"}, fg.UP), fg.DOWN)
        self.assertEqual(fg._side_colour({"value": "−5.46%"}, fg.INK), fg.DOWN)
        self.assertEqual(fg._side_colour({"value": "+4.61%"}, fg.UP), fg.UP)
        self.assertEqual(fg._side_colour({"value": "5.31%"}, fg.INK), fg.INK)
        self.assertEqual(fg._side_colour({"value": "1,200원", "down": True}, fg.UP), fg.DOWN)


class MagazineTitleQuoteTest(unittest.TestCase):
    """잡지 제목의 따옴표 인용(2026-10-14): 외국어에서 옮긴 말은 막고, 한국어 원문이 근거 표에 있으면 둔다."""

    def _doc(self, original: str) -> dict:
        return {"date": "2026-10-15", "ko": {"title": "에콰도르는 왜 ‘화폐 자살’이라던 달러를 끝내 못 버렸을까"},
                "evidence": [{"claim": "화폐 자살", "url": "https://x", "original": original}]}

    def test_translated_quote_blocked(self) -> None:
        self.assertTrue(feature_checks.title_quote_issues(self._doc("he called it “monetary suicide.”")))

    def test_korean_original_allowed(self) -> None:
        self.assertEqual(feature_checks.title_quote_issues(self._doc("그는 이를 ‘화폐 자살’이라 불렀다")), [])

    def test_older_manuscripts_untouched(self) -> None:
        doc = self._doc("monetary suicide")
        doc["date"] = "2026-10-14"
        self.assertEqual(feature_checks.title_quote_issues(doc), [])


class EnglishGuideTwiceWeeklyTest(unittest.TestCase):
    """영어 가이드 주 2편(화·금, 2026-10-15부터) — 증명서는 그 요일에만 기다린다."""

    def _names(self, day: dt.date) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            return [n for n, _, _ in daily_proof.expected_artifacts(day, set(), Path(tmp))]

    def test_only_tuesday_and_friday(self) -> None:
        self.assertIn("영어 가이드", self._names(dt.date(2026, 10, 14)))       # 수 — 바뀌기 전날까지는 매일
        self.assertNotIn("영어 가이드", self._names(dt.date(2026, 10, 15)))    # 목
        self.assertIn("영어 가이드", self._names(dt.date(2026, 10, 16)))       # 금
        self.assertIn("영어 가이드", self._names(dt.date(2026, 10, 20)))       # 화
        self.assertNotIn("영어 가이드", self._names(dt.date(2026, 10, 18)))    # 일
