"""독자가 보는 한 줄로 제목을 대조한다 (2026-09-18, 사장님: "제목 상태 왜 이래 적용안된거같은데").

관문은 규칙을 다 돌렸고 통과했다 — 목록별(한국장·미국장·프리뷰 따로)로. 네이버 피드에는 '은행주'가
셋, '3년 2개월 만의 금리 인상'이 둘, 대비 꼴이 둘 나란히 있었다. 여기서는 (1) 피드의 순서가 올라가는
시각(미국장 D는 한국 D+1 아침)인 것, (2) 가이드·잡지는 빠지는 것, (3) 그날 실제 제목 다섯 편이 이 규칙으로
막히는 것을 고정한다.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from src import editorial_title, feature_gate, title_feed

FEED_0918 = [   # 2026-09-18 아침 네이버 fermata49 피드(오래된 것부터) — 실측
    "오늘 밤 FOMC가 3년 2개월 만의 금리 인상을 결정합니다",         # 프리뷰 09-16 21:30
    "다우 1.21% 하락, 이유는 금리 인상에 흔들린 은행주입니다",       # 미국장 09-16 → 09-17 07:20
    "3년 2개월 만의 금리 인상, 코스피는 오히려 잠잠했습니다",        # 한국장 09-17 16:20
    "오늘 밤 필라델피아 지수가 은행주 사흘째를 정합니다",            # 프리뷰 09-17 21:30
]
US_0917 = "반도체는 일제히 웃었는데, 은행주는 왜 못 웃었을까요"      # 미국장 09-17 → 09-18 07:20


def _write(folder: Path, name: str, doc: dict) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")


class SlotOrderTest(unittest.TestCase):
    def test_us_daily_comes_after_that_days_preview_and_kr_daily(self) -> None:
        kr = title_feed.slot_of({"market": "kr", "date": "2026-09-17", "price_data": {}})
        pv = title_feed.slot_of({"series": "프리뷰", "date": "2026-09-17"})
        us = title_feed.slot_of({"market": "us", "date": "2026-09-17", "price_data": {}})
        self.assertEqual(kr, datetime(2026, 9, 17, 16, 20))
        self.assertEqual(pv, datetime(2026, 9, 17, 21, 30))
        self.assertEqual(us, datetime(2026, 9, 18, 7, 20))   # 미국 거래일 9/17 글은 한국 9/18 아침에 나간다
        self.assertLess(kr, pv)
        self.assertLess(pv, us)

    def test_guides_and_magazine_are_outside_the_feed(self) -> None:
        self.assertIsNone(title_feed.slot_of({"series": "가이드", "date": "2026-09-17"}))
        self.assertIsNone(title_feed.slot_of({"series": "매거진", "date": "2026-09-17"}))
        self.assertIsNone(title_feed.series_of({"series": "Guide", "lang": "en"}))

    def test_date_falls_back_to_the_file_name(self) -> None:
        slot = title_feed.slot_of({"series": "기준표"}, Path("editorial/features/kr_2026-09-13_kospi_per_range.json"))
        self.assertEqual(slot, datetime(2026, 9, 13, 9, 0))


class FeedTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        ed = self.root / "editorial"
        _write(ed, "kr_2026-09-16.json", {"market": "kr", "date": "2026-09-16", "price_data": {}, "ko": {"title": "한국장 16일"}})
        _write(ed / "previews", "us_2026-09-16.json", {"series": "프리뷰", "date": "2026-09-16", "ko": {"title": "프리뷰 16일"}})
        _write(ed, "us_2026-09-16.json", {"market": "us", "date": "2026-09-16", "price_data": {}, "ko": {"title": "미국장 16일"}})
        _write(ed / "guides", "ko_something.json", {"series": "가이드", "date": "2026-09-16", "ko": {"title": "가이드 글"}})
        _write(ed / "magazine", "2026-09-16_x.json", {"series": "매거진", "date": "2026-09-16", "ko": {"title": "잡지 글"}})
        _write(ed, "kr_2026-09-17.json", {"market": "kr", "date": "2026-09-17", "price_data": {}, "ko": {"title": "한국장 17일"}})
        _write(ed / "previews", "us_2026-09-17.json", {"series": "프리뷰", "date": "2026-09-17", "ko": {"title": "프리뷰 17일"}})
        _write(ed, "us_2026-09-17.json", {"market": "us", "date": "2026-09-17", "price_data": {}, "ko": {"title": "미국장 17일"}})

    def test_feed_is_in_publish_order_without_guides_or_magazine(self) -> None:
        titles = title_feed.feed_titles(count=10, root=self.root)
        self.assertEqual(titles, ["한국장 16일", "프리뷰 16일", "미국장 16일", "한국장 17일", "프리뷰 17일", "미국장 17일"])

    def test_a_manuscript_sees_only_what_was_published_above_it(self) -> None:
        path = self.root / "editorial" / "us_2026-09-17.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(title_feed.feed_titles(doc, path, root=self.root),
                         ["한국장 16일", "프리뷰 16일", "미국장 16일", "한국장 17일", "프리뷰 17일"])   # 자기 자신은 빠진다
        pv = self.root / "editorial" / "previews" / "us_2026-09-17.json"
        self.assertEqual(title_feed.feed_titles(json.loads(pv.read_text(encoding="utf-8")), pv, root=self.root),
                         ["한국장 16일", "프리뷰 16일", "미국장 16일", "한국장 17일"])

    def test_feature_gate_uses_the_feed_for_previews(self) -> None:
        original = feature_gate.ROOT
        try:
            feature_gate.ROOT = self.root
            titles = feature_gate.recent_titles({"series": "프리뷰", "date": "2026-09-17"})
        finally:
            feature_gate.ROOT = original
        self.assertEqual(titles, ["한국장 16일", "프리뷰 16일", "미국장 16일", "한국장 17일"])


class SubjectAndPhraseTest(unittest.TestCase):
    def test_the_titles_the_owner_saw_are_blocked_by_the_feed(self) -> None:
        issues = editorial_title.frame_issues(US_0917, FEED_0918)
        joined = "\n".join(issues)
        self.assertIn("'은행주'", joined)          # 프리뷰 9/17·미국장 9/16에 이미 둘 → 셋째는 막는다
        self.assertIn("대비 꼴", joined)           # 한국장 9/17 '오히려'와 겹친다
        kr_0917 = "3년 2개월 만의 금리 인상, 코스피는 오히려 잠잠했습니다"
        issues = editorial_title.frame_issues(kr_0917, FEED_0918[:2])
        self.assertTrue(any("3년 2개월 만의 금리 인상" in i for i in issues), issues)   # 전날 프리뷰의 어구 그대로

    def test_same_subject_twice_is_fine_three_times_is_not(self) -> None:
        recent = ["은행주가 이틀째 밀렸습니다", "코스피 1.37% 반등: 변수는 내일 새벽 FOMC입니다"]
        self.assertFalse(any("'은행주'" in i for i in editorial_title.subject_issues("은행주, 오늘 밤 사흘째를 정합니다", recent)))
        recent.append("오늘 밤 필라델피아 지수가 은행주 사흘째를 정합니다")
        self.assertTrue(any("'은행주'" in i for i in editorial_title.subject_issues("은행주는 왜 못 웃었을까요", recent)))

    def test_short_shared_words_and_numbers_are_not_phrases(self) -> None:
        recent = ["오늘 밤 FOMC가 3년 2개월 만의 금리 인상을 결정합니다"]
        self.assertEqual(editorial_title.subject_issues("오늘 밤 미국장, 이 종목 셋만 보세요", recent), [])   # '오늘 밤'(3자)
        self.assertEqual(editorial_title.shared_phrase("2026년 9월 17일", "2026년 9월 18일"), "2026년 9월 1")
        self.assertEqual(editorial_title.subject_issues("코스피 7,000 재돌파할까? 이번 주 확인할 것", ["코스피 7,000선 앞에서 멈춘 이유"]), [])

    def test_subjects_are_names_not_particles(self) -> None:
        self.assertEqual(editorial_title.title_subjects("다우 1.21% 하락, 이유는 금리 인상에 흔들린 은행주입니다"), ["다우", "금리", "은행주"])
        self.assertEqual(editorial_title.title_subjects("오늘 밤 FOMC가 3년 2개월 만의 금리 인상을 결정합니다"), ["FOMC", "금리"])
        self.assertNotIn("금리", editorial_title.title_subjects("10년물 국채금리, 오늘 밤 5%를 넘어설까"))   # '국채금리' 하나로 센다

    def test_recent_titles_script_shows_the_feed_and_crowded_subjects(self) -> None:
        from scripts import recent_titles
        out = recent_titles.render("kr")
        self.assertIn("독자가 보는 최근", out)
        self.assertIn("주인공 반복", out)
        self.assertEqual(recent_titles.render("kr"), recent_titles.render("us"))   # 어느 이름으로 불러도 같은 한 줄


if __name__ == "__main__":
    unittest.main()
