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
    try:
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
        doc["date"] = "2026-10-11"   # 토요일 — 시세 파일이 없다
        self.assertTrue(any("대조할 한국장 시세 파일이 없습니다" in i for i in _blocking(doc)))

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
