"""종목 허브 페이지(2026-09-12, 유입 편성 3번, 사용자 승인) — 숫자는 시세 파일에서만, 판단은 루틴 노트에서만.

워드프레스는 부르지 않는다. 통계·노트 검사·관련 글·렌더·워크플로 계약만 본다.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src import stock_pages

ROOT = Path(__file__).resolve().parent.parent

DATES = [f"2026-0{m}-{d:02d}" for m in (6, 7, 8) for d in range(1, 29) if d % 7 not in (0, 6)][:60] + \
        ["2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04", "2026-09-07", "2026-09-08", "2026-09-09", "2026-09-10", "2026-09-11"]
CLOSES = [200000 + i * 1000 for i in range(len(DATES) - 6)] + [270000, 269500, 269500, 269000, 259500, 262000]
ENTRY = {"ticker": "005930", "name": "삼성전자", "price": CLOSES[-1], "change_pct": 0.96, "unit": "",
         "history": {"dates": DATES, "close": CLOSES}, "source": "core", "sector": "반도체"}


class ConfigTest(unittest.TestCase):
    def test_every_core_stock_has_a_page_with_a_blurb(self) -> None:
        items = stock_pages.load_config()
        self.assertEqual(len(items), 37)   # 코어 21 + 16
        for item in items:
            self.assertTrue(item["blurb"], item["ticker"])
            self.assertRegex(item["slug"], r"^[a-z0-9-]+$")
            self.assertTrue(item["name"])
            for banned in ("추천", "매수하", "오를 것"):
                self.assertNotIn(banned, item["blurb"], f"{item['name']} 소개에 전망·추천이 있습니다")


class StatsTest(unittest.TestCase):
    def test_changes_come_from_the_history_only(self) -> None:
        s = stock_pages.stats(ENTRY, "2026-09-11")
        self.assertEqual(s["close"], "262,000")
        self.assertEqual(s["pct_1d"], "+0.96%")
        # 1주: 이번 주(9/7~) 첫 거래일 전 종가(9/4 = 270,000) 대비
        self.assertEqual(s["pct_1w"], f"{(262000 / 270000 - 1) * 100:+.2f}%")
        self.assertEqual(s["pct_1m"], f"{(262000 / CLOSES[-22] - 1) * 100:+.2f}%")
        self.assertEqual(s["pct_3m"], f"{(262000 / CLOSES[0] - 1) * 100:+.2f}%")
        self.assertEqual(s["high_3m"], "270,000")
        self.assertIn("고점", s["position_text"])
        self.assertEqual(s["w_class"], "down")

    def test_short_history_is_an_error_not_a_blank(self) -> None:
        with self.assertRaises(stock_pages.StockPagesError):
            stock_pages.stats({"ticker": "X", "history": {"dates": DATES[:3], "close": CLOSES[:3]}}, "2026-09-11")


class NotesTest(unittest.TestCase):
    def test_notes_must_cover_every_stock_and_avoid_position_talk(self) -> None:
        items = stock_pages.load_config()
        notes = {i["ticker"]: "지난달 우리 시황에 주인공으로 나온 날은 없었습니다. 3개월 고점 아래에서 한 달을 보냈고, 다음 확인 지점은 10월 실적입니다." for i in items}
        doc = {"month": "2026-10", "checked": "2026-10-01", "notes": notes}
        self.assertEqual(stock_pages.validate_notes(doc, items), [])
        doc["notes"]["NVDA"] = "제가 매수한 뒤로 오를 것이다. **강추**"
        del doc["notes"]["005930"]
        issues = stock_pages.validate_notes(doc, items)
        joined = "\n".join(issues)
        self.assertIn("삼성전자(005930) 노트가 없습니다", joined)
        self.assertIn("포지션 화법", joined)
        self.assertIn("예측", joined)
        self.assertIn("볼드", joined)


class RelatedPostsTest(unittest.TestCase):
    def test_only_word_boundary_mentions_in_titles_or_headings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "features").mkdir()
            (base / "kr_2026-09-10.json").write_text(json.dumps({"market": "kr", "date": "2026-09-10",
                "ko": {"title": "네 마녀의 날: 코스피가 6,900선에서 버틴 이유", "narrative": [{"heading": "삼성전자가 지수를 받쳤다"}]}}), encoding="utf-8")
            (base / "kr_2026-09-11.json").write_text(json.dumps({"market": "kr", "date": "2026-09-11",
                "ko": {"title": "코스피 1.76% 하락, 원인은 유가", "narrative": [{"heading": "삼성전기 급락"}]}}), encoding="utf-8")
            (base / "features" / "kr_2026-09-06_x.json").write_text(json.dumps({"kind": "feature", "date": "2026-09-06", "slug": "samsung-per",
                "ko": {"title": "삼성전자 PER, 지금 숫자로", "narrative": []}}), encoding="utf-8")
            (base / "features" / "en_x.json").write_text(json.dumps({"kind": "feature", "lang": "en", "date": "2026-09-08", "slug": "en",
                "ko": {"title": "Samsung Electronics 삼성전자", "narrative": []}}), encoding="utf-8")
            naver = {"editorial/kr_2026-09-10.json": "https://blog.naver.com/fermata49/1",
                     "editorial/kr_2026-09-11.json": "https://blog.naver.com/fermata49/2",
                     "editorial/features/kr_2026-09-06_x.json": "https://blog.naver.com/fermata49/3"}
            rows = stock_pages.related_posts("삼성전자", editorial_dir=base, naver=naver)
        self.assertEqual([r["date"] for r in rows], ["2026-09-10", "2026-09-06"])   # 삼성전기 ≠ 삼성전자, 영어 제외
        # 한국어 글은 본진에서 비공개(404)라 네이버 주소로 잇는다(2026-09-26).
        self.assertEqual(rows[0]["url"], "https://blog.naver.com/fermata49/1")
        self.assertEqual(rows[1]["url"], "https://blog.naver.com/fermata49/3")

    def test_body_mentions_come_after_title_mentions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "kr_2026-09-11.json").write_text(json.dumps({"market": "kr", "date": "2026-09-11",
                "ko": {"title": "코스피 하락", "narrative": [{"heading": "반도체", "body": "삼성전자가 3.53% 내렸습니다."}]}}), encoding="utf-8")
            (base / "kr_2026-09-01.json").write_text(json.dumps({"market": "kr", "date": "2026-09-01",
                "ko": {"title": "삼성전자 급등", "narrative": []}}), encoding="utf-8")
            naver = {"editorial/kr_2026-09-11.json": "https://blog.naver.com/fermata49/11",
                     "editorial/kr_2026-09-01.json": "https://blog.naver.com/fermata49/1"}
            rows = stock_pages.related_posts("삼성전자", editorial_dir=base, naver=naver)
        self.assertEqual([r["date"] for r in rows], ["2026-09-01", "2026-09-11"])

    def test_only_posts_readers_can_open_and_never_the_magazine(self) -> None:
        """네이버 주소표에 없는 한국어 글은 싣지 않는다(본진은 비공개라 404). 잡지는 퍼플썸이라 잇지 않는다."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "magazine").mkdir()
            (base / "kr_2026-09-11.json").write_text(json.dumps({"market": "kr", "date": "2026-09-11",
                "ko": {"title": "삼성전자 급락", "narrative": []}}), encoding="utf-8")
            (base / "kr_2026-09-12.json").write_text(json.dumps({"market": "kr", "date": "2026-09-12",
                "ko": {"title": "삼성전자 반등", "narrative": []}}), encoding="utf-8")
            (base / "magazine" / "2026-09-13_x.json").write_text(json.dumps({"series": "매거진", "date": "2026-09-13",
                "ko": {"title": "삼성전자의 역사", "narrative": []}}), encoding="utf-8")
            naver = {"editorial/kr_2026-09-11.json": "https://blog.naver.com/fermata49/11",
                     "editorial/magazine/2026-09-13_x.json": "https://blog.naver.com/puplesum_/13"}
            rows = stock_pages.related_posts("삼성전자", editorial_dir=base, naver=naver)
        self.assertEqual([r["url"] for r in rows], ["https://blog.naver.com/fermata49/11"])

    def test_missing_naver_table_stops_instead_of_emptying_pages(self) -> None:
        with self.assertRaises(FileNotFoundError):
            stock_pages.naver_posts(Path(tempfile.mkdtemp()) / "none.json")

    def test_committed_naver_table_has_no_magazine_and_only_naver_urls(self) -> None:
        table = stock_pages.naver_posts()
        self.assertTrue(table)
        self.assertFalse([k for k in table if "/magazine/" in k])
        self.assertTrue(all(v.startswith("https://blog.naver.com/fermata49/") for v in table.values()))


class RenderTest(unittest.TestCase):
    def test_page_and_index_render_as_wp_html_blocks(self) -> None:
        item = {"market": "kr", "ticker": "005930", "slug": "samsung-electronics", "name": "삼성전자",
                "name_en": "Samsung Electronics", "sector": "반도체", "blurb": "메모리 회사입니다."}
        s = stock_pages.stats(ENTRY, "2026-09-11")
        html = stock_pages.render_page(item, s, "2026-09-11", "https://x/chart.png", "지난달 흐름입니다.", "2026년 9월 1일 기준",
                                       [{"date": "2026-09-10", "title": "글", "url": "https://fermata.it.kr/a/"}])
        self.assertTrue(html.startswith("<!-- wp:html -->"))
        self.assertIn("삼성전자 주가 (005930)", html)
        self.assertIn("262,000", html)
        self.assertIn("지난달 흐름입니다.", html)
        self.assertIn("메모리 회사입니다.", html)
        self.assertIn("2026년 9월 11일", html)
        without_note = stock_pages.render_page(item, s, "2026-09-11", None, None, None, [])
        self.assertNotIn("최근 흐름", without_note)   # 노트가 없으면 절도 없다 — 없는 판단을 만들지 않는다
        index = stock_pages.render_index([{"market": "kr", "name": "삼성전자", "ticker": "005930", "sector": "반도체",
                                           "url": "/stocks/samsung-electronics/", "close": "262,000", "pct_1w": "-2.60%",
                                           "pct_1m": "+1.00%", "w_class": "down", "m_class": "up"}], {"kr": "2026-09-11"})
        self.assertIn("/stocks/samsung-electronics/", index)
        self.assertIn("종목별 주가 페이지", index)
        self.assertEqual(stock_pages.page_title(item), "삼성전자 주가 (005930)")
        self.assertIn("1주 -", stock_pages.excerpt(item, s, "2026-09-11"))

    def test_note_bold_renders_as_bold_and_other_tags_stay_text(self) -> None:
        """노트 검사는 `**` 대신 `<b>…</b>`를 쓰라고 시킨다 — 페이지에서 태그가 글자로 보이면 안 된다(2026-09-26)."""
        item = {"market": "kr", "ticker": "005930", "slug": "samsung-electronics", "name": "삼성전자",
                "name_en": "Samsung Electronics", "sector": "반도체", "blurb": "메모리 회사입니다."}
        s = stock_pages.stats(ENTRY, "2026-09-11")
        html = stock_pages.render_page(item, s, "2026-09-11", None, "<b>HBM</b> 수요 & <script>x</script>",
                                       "2026년 10월 1일 기준", [])
        self.assertIn("<b>HBM</b>", html)
        self.assertNotIn("&lt;b&gt;", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("수요 &amp;", html)

class WorkflowTest(unittest.TestCase):
    def test_workflow_runs_weekly_and_on_notes_without_llm_keys(self) -> None:
        text = (ROOT / ".github" / "workflows" / "stock_pages.yml").read_text(encoding="utf-8")
        self.assertIn("editorial/stocks/*.json", text)
        self.assertIn("cron:", text)
        self.assertIn("FERMATA_AUTO_PUBLISH", text)
        self.assertIn("fonts-nanum", text)
        self.assertNotIn("ANTHROPIC_API_KEY", text)
        doc = (ROOT / "docs" / "routine_stock_notes.md").read_text(encoding="utf-8")
        self.assertIn("--check-notes", doc)
        self.assertIn("editorial/stocks/notes_", doc)


if __name__ == "__main__":
    unittest.main()
