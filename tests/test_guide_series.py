"""유입 편성(2026-09-12, 사용자 승인 "1번 2번 4번 진행, 3번 5번도 승인") — 상시 가이드·영어 가이드·이벤트 글.

근거: 서치콘솔 실측(2026-09-12) — 구글 노출 710건 중 700건이 영어 가이드 9편에서 나왔고, 한국어 시황 43편은
0건이었다. 그래서 검색 유입을 만드는 세 시리즈를 기준표 파이프라인에 표 한 줄씩으로 더한다 — 새 파이프라인이
아니라 등록이다. 영어 가이드는 한국어 문체·제목 검사 대신 영어 검사를 받는다.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from scripts import naver_post, recent_titles
from src import editorial_title, feature_checks, feature_gate, post_tags, publish_feature, render_feature, source_check

ROOT = Path(__file__).resolve().parent.parent


def _en_doc(**over) -> dict:
    body = ("The Korea Exchange runs two boards. " * 12).strip()
    doc = {
        "kind": "feature", "series": "Guide", "lang": "en", "date": "2026-09-16", "checked": "2026-09-16",
        "slug": "kospi-etf-for-us-investors", "category_id": 153, "tags": ["KOSPI ETF"],
        "ko": {
            "title": "KOSPI ETFs for US Investors: EWY vs FLKR Compared (2026)",
            "narrative": [{"heading": f"Section {i}", "body": body + f" As of September 2026, PwC and MSCI agree. {i}"}
                          for i in range(5)],
            "closing": {"heading": "The takeaway", "body": "Check the expense ratio before you buy."},
        },
        "graphics": [],
    }
    doc.update(over)
    return doc


class SeriesRegistrationTest(unittest.TestCase):
    def test_three_series_are_registered_in_every_table(self) -> None:
        for series in ("가이드", "Guide", "이벤트"):
            with self.subTest(series=series):
                self.assertIn(series, feature_checks.SERIES_LIMITS)
                self.assertIn(series, editorial_title.SECTION_FLOORS)
                self.assertIn(series, source_check.SERIES_MIN_SOURCES)
                self.assertIn(series, feature_gate.SERIES_FOLDER)
        self.assertEqual(feature_gate.SERIES_FOLDER["가이드"], "guides")
        self.assertEqual(feature_gate.SERIES_FOLDER["Guide"], "guides")
        self.assertEqual(feature_gate.SERIES_FOLDER["이벤트"], "events")
        for key in ("guide", "guide_en", "event"):
            self.assertIn(key, recent_titles.LISTS)

    def test_workflows_publish_the_new_folders(self) -> None:
        guide = (ROOT / ".github" / "workflows" / "guide_publish.yml").read_text(encoding="utf-8")
        self.assertIn("editorial/guides/*.json", guide)
        self.assertIn("FERMATA_AUTO_PUBLISH", guide, "자동화 스위치는 하나다 — 새 경로도 같은 변수를 읽는다")
        weekly = (ROOT / ".github" / "workflows" / "weekly_publish.yml").read_text(encoding="utf-8")
        self.assertIn("editorial/events/*.json", weekly)
        self.assertIn("(weekly|events)", weekly)


class KickerTest(unittest.TestCase):
    def test_guides_show_the_checked_date_and_events_the_event_date(self) -> None:
        self.assertEqual(publish_feature._kicker({"series": "가이드", "checked": "2026-09-16"}),
                         "가이드 · 2026년 9월 16일 확인")
        self.assertEqual(publish_feature._kicker({"series": "Guide", "checked": "2026-09-16"}),
                         "Investor Guide · Checked September 16, 2026")
        self.assertEqual(publish_feature._kicker({"series": "이벤트", "event_date": "2026-09-17"}),
                         "이벤트 · 9월 17일")
        self.assertTrue(publish_feature._seo_lead({"series": "이벤트", "event_date": "2026-09-17",
                                                   "event_name": "9월 FOMC"}).startswith("9월 17일 9월 FOMC"))


class EnglishGateTest(unittest.TestCase):
    def test_english_guide_passes_without_korean_checks(self) -> None:
        result = feature_gate.run(_en_doc(), graphics=2)
        self.assertEqual(result["blocking"], [])
        self.assertEqual(result["sources"]["distinct"], 3)   # Korea Exchange · PwC · MSCI

    def test_english_guide_is_blocked_on_short_title_missing_year_or_hangul(self) -> None:
        doc = _en_doc()
        doc["ko"]["title"] = "KOSPI ETFs"
        for section in doc["ko"]["narrative"]:
            section["body"] = section["body"].replace("As of September 2026", "As of this year 코스피")
        with self.assertRaises(feature_gate.FeatureGateError) as ctx:
            feature_gate.run(doc, graphics=2)
        message = str(ctx.exception)
        self.assertIn("characters", message)
        self.assertIn("year", message)
        self.assertIn("Hangul", message)

    def test_english_guide_needs_two_named_sources(self) -> None:
        doc = _en_doc()
        for section in doc["ko"]["narrative"]:
            section["body"] = section["body"].replace("The Korea Exchange", "The exchange").replace("PwC and MSCI", "everyone")
        with self.assertRaises(feature_gate.FeatureGateError):
            feature_gate.run(doc, graphics=2)

    def test_english_tags_and_template(self) -> None:
        doc = _en_doc()
        doc["ko"]["narrative"][0]["body"] += " Samsung Electronics dominates the index."
        tags = post_tags.build_tags(doc)
        self.assertEqual(tags[:3], ["Korean stocks", "KOSPI", "foreign investors"])
        self.assertIn("KOSPI ETF", tags)
        self.assertIn("Samsung Electronics", tags)
        self.assertFalse(any("가" <= ch <= "힣" for tag in tags for ch in tag))
        html = render_feature.render(doc, "Investor Guide", lang="en")
        self.assertIn('<html lang="en">', html)
        self.assertIn("is not a recommendation", html)
        self.assertNotIn('mb-related-label">관련 글', html)
        ko_html = render_feature.render({"ko": {"title": "제목", "narrative": [], "closing": {}}}, "가이드")
        self.assertIn('<html lang="ko">', ko_html)
        self.assertIn("권유하지 않습니다", ko_html)


class NaverSummaryTest(unittest.TestCase):
    def test_guide_keeps_its_title_and_goes_to_the_guide_category(self) -> None:
        import json
        import tempfile
        doc = {"kind": "feature", "series": "가이드", "date": "2026-09-15", "checked": "2026-09-15",
               "slug": "kospi-kosdaq-difference", "category_id": 153,
               "ko": {"title": "코스피와 코스닥, 무엇이 다른가", "narrative": [{"heading": "1. 두 시장", "body": "코스피는 큰 회사, 코스닥은 성장 회사가 모인 시장입니다."}],
                      "closing": {"heading": "Fermata's Take", "body": "둘 다 봅니다."}}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ko_kospi_kosdaq_difference.json"
            path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            post = naver_post.build(path)
        self.assertEqual(post["title"], "코스피와 코스닥, 무엇이 다른가")
        self.assertEqual(post["category"], "가이드")
        self.assertEqual(post["url"], "https://fermata.it.kr/kospi-kosdaq-difference/")
        self.assertIn("주식초보", post["tags"])

    def test_event_summary_carries_the_event_date(self) -> None:
        import json
        import tempfile
        doc = {"kind": "feature", "series": "이벤트", "date": "2026-09-13", "event_date": "2026-09-17",
               "event_name": "9월 FOMC", "slug": "fomc-2026-09", "category_id": 433,
               "ko": {"title": "9월 FOMC 결과, 한국시간 새벽 3시에 무엇을 보나", "narrative": [{"heading": "1. 언제", "body": "9월 17일 새벽 3시에 나옵니다."}],
                      "closing": {"heading": "Fermata's Take", "body": "점도표를 봅니다."}}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "2026-09-13_fomc.json"
            path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            post = naver_post.build(path)
        self.assertTrue(post["title"].startswith("증시 이벤트 9월 17일"))
        self.assertEqual(post["category"], "Weekly")


if __name__ == "__main__":
    unittest.main()


class RoutineDocsTest(unittest.TestCase):
    """루틴 프롬프트는 문서를 가리키는 몇 줄뿐이다 — 문서가 없거나 핵심이 빠지면 루틴이 헛돈다."""

    def test_guide_docs_name_the_series_folder_and_gate(self) -> None:
        ko = (ROOT / "docs" / "routine_guide_ko.md").read_text(encoding="utf-8")
        en = (ROOT / "docs" / "routine_guide_en.md").read_text(encoding="utf-8")
        for text, series, prefix in ((ko, '"가이드"', "ko_"), (en, '"Guide"', "en_")):
            self.assertIn(series, text)
            self.assertIn(f"editorial/guides/{prefix}", text)
            self.assertIn("feature_gate", text)
            self.assertIn("category_id", text)
            self.assertIn("153", text)
        self.assertIn('"lang" "en"', en)

    def test_week_ahead_doc_describes_the_event_post(self) -> None:
        text = (ROOT / "docs" / "routine_week_ahead.md").read_text(encoding="utf-8")
        self.assertIn("editorial/events/", text)
        self.assertIn('"이벤트"', text)
        self.assertIn("event_date", text)
        self.assertIn("event_name", text)
