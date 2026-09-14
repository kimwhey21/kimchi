"""아침 레이더(2026-09-13) — 네트워크 없이 파서·신선도·묶음 고르기만 본다.

2026-09-14에 세 가지가 붙었다. 매체 목록이 `config/magazine_feeds.yaml` 한곳으로 모이고
(시황 매체까지), 레이더가 묶음(`--set`)을 받고, 가이드·Checkpoint 지시문이 레이더를 부른다.
여기서 고정하는 것은 **붙어 있다는 사실**이다 — 지시문에서 한 줄이 사라지면 루틴은 조용히
옛 방식으로 돌아가고, 아무 화면도 빨개지지 않는다.
"""
from __future__ import annotations

import datetime as dt
import unittest
from unittest import mock

import yaml

from scripts import magazine_radar as mr

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent

RSS = """<rss><channel><title>Feed</title>
<item><title><![CDATA[Fresh one]]></title><link>https://a/1</link><pubDate>{fresh}</pubDate></item>
<item><title>Stale one</title><link>https://a/2</link><pubDate>{stale}</pubDate></item>
<item><title>Undated one</title><link>https://a/3</link></item>
</channel></rss>"""
ATOM = """<feed xmlns="http://www.w3.org/2005/Atom"><title>Atom</title>
<entry><title>Atom fresh</title><link href="https://b/1"/><updated>{fresh_iso}</updated></entry></feed>"""


def _rfc(delta_h: float) -> str:
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=delta_h)).strftime("%a, %d %b %Y %H:%M:%S +0000")


class ParseTest(unittest.TestCase):
    def test_rss_and_atom_both_parse_with_cdata_and_missing_dates(self) -> None:
        rows = mr.parse(RSS.format(fresh=_rfc(2), stale=_rfc(80)))
        self.assertEqual([r["title"] for r in rows], ["Fresh one", "Stale one", "Undated one"])
        self.assertEqual(rows[0]["link"], "https://a/1")
        self.assertIsNone(rows[2]["at"])
        atom = mr.parse(ATOM.format(fresh_iso=(dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)).isoformat()))
        self.assertEqual(atom[0]["link"], "https://b/1")
        self.assertIsNotNone(atom[0]["at"])


class RadarTest(unittest.TestCase):
    def test_freshness_filter_keeps_undated_and_reports_failed_feeds(self) -> None:
        feeds = [{"name": "A", "url": "https://a/rss", "column": "과학"}, {"name": "B", "url": "https://b/rss", "column": "시장 읽기", "paid": True}]

        class R:
            def __init__(self, text): self.text = text
            def raise_for_status(self): pass

        def fake_get(url, **kw):
            if url == "https://a/rss":
                return R(RSS.format(fresh=_rfc(2), stale=_rfc(80)))
            raise ConnectionError("down")
        with mock.patch.object(mr.requests, "get", side_effect=fake_get):
            rows, failed = mr.radar(36, feeds)
        self.assertEqual(sorted(r["title"] for r in rows), ["Fresh one", "Undated one"])
        self.assertEqual(failed, ["B: ConnectionError"])
        self.assertTrue(all(r["column"] == "과학" and r["paid"] is False for r in rows))

    def test_the_feed_config_lists_the_reference_blogs_main_outlets(self) -> None:
        names = [f["name"] for f in mr.config()["sets"]["magazine"]]
        for must in ("Yahoo Finance", "MarketWatch", "The Motley Fool", "Visual Capitalist", "Fortune"):
            self.assertTrue(any(must in n for n in names), must)
        self.assertTrue(any("클레멘트" in n for n in names))   # 투자 블로거도 있다

    def test_mojibake_feeds_are_re_decoded(self) -> None:
        """charset을 안 알려 주는 서버는 requests가 ISO-8859-1로 읽어 제목이 깨진다.

        깨진 제목은 예외를 내지 않는다 — 사람이 읽을 때까지 조용하다. 한겨레에서 실제로 겪었다.
        """
        xml = RSS.format(fresh=_rfc(1), stale=_rfc(80)).replace("Fresh one", "코스피 급락")

        class R:
            content = xml.encode("utf-8")
            encoding = "ISO-8859-1"
            apparent_encoding = "utf-8"
            text = xml.encode("utf-8").decode("iso-8859-1")   # requests가 주는 깨진 문자열

        self.assertIn("코스피 급락", mr.body(R()))
        self.assertNotIn("코스피", R.text)                     # 고치지 않으면 이 꼴이다


class FeedSetTest(unittest.TestCase):
    """`--set`이 묶음을 고른다. 이름을 잘못 적으면 조용히 빈손으로 끝나지 않고 멈춘다."""

    def test_named_sets_flatten_and_unknown_names_stop_the_run(self) -> None:
        sets = mr.config()["sets"]
        self.assertEqual(mr.feeds_for("magazine"), sets["magazine"])
        self.assertEqual(len(mr.feeds_for("ko,magazine")), len(sets["ko"]) + len(sets["magazine"]))
        self.assertEqual(len(mr.feeds_for("all")), sum(len(v) for v in sets.values()))
        with self.assertRaises(SystemExit):
            mr.feeds_for("korean")          # 있는 것은 ko다 — 빈 목록으로 넘어가면 "화제 없음"으로 보인다

    def test_every_feed_has_a_name_url_and_column(self) -> None:
        for name, feeds in mr.config()["sets"].items():
            for feed in feeds:
                with self.subTest(set=name, feed=feed.get("name")):
                    self.assertTrue(feed.get("name") and feed.get("column"))
                    self.assertTrue(str(feed.get("url", "")).startswith("https://"))

    def test_korean_set_covers_the_markets_and_the_guide_subjects(self) -> None:
        """가이드가 고를 것은 증시뿐이 아니다 — 제도·세금·금리 갈래가 있어야 주제 순서를 바꿀 수 있다."""
        columns = {f["column"] for f in mr.config()["sets"]["ko"]}
        for must in ("증시", "제도·세금", "금리·환율"):
            self.assertIn(must, columns)


class MarketMediaTest(unittest.TestCase):
    """시황 매체 목록은 이 파일 하나다(2026-09-14). 레이더는 돌리지 않고 이름만 쓴다.

    옮길 때 글자 그대로 옮겼다. 목록이 줄면 시황 글의 근거가 줄어드는데, 지시문에서
    목록을 지운 뒤라 어디서도 티가 나지 않는다 — 그래서 여기서 센다.
    """

    def test_both_markets_keep_the_outlets_the_editorial_routines_used(self) -> None:
        media = mr.config()["market_media"]
        self.assertEqual(media["kr"], ["연합뉴스", "한국경제", "아시아경제", "이데일리",
                                       "머니투데이", "서울경제", "매일경제"])
        self.assertEqual(media["us"], ["Reuters", "CNBC", "Bloomberg", "Yahoo Finance",
                                       "Investing.com", "Barron's", "WSJ"])

    def test_the_editorial_docs_point_at_the_config_and_skip_the_radar(self) -> None:
        for doc, key in (("routine_kr.md", "market_media.kr"), ("routine_us.md", "market_media.us")):
            text = (ROOT / "docs" / doc).read_text(encoding="utf-8")
            with self.subTest(doc=doc):
                self.assertIn(key, text)
                self.assertIn("레이더를 붙이지 않습니다", text)   # 마감 직후의 급한 글이다

    def test_the_media_flag_prints_names_without_touching_the_network(self) -> None:
        def boom(*a, **k):
            raise AssertionError("--media는 피드를 읽지 않는다")
        with mock.patch.object(mr.requests, "get", side_effect=boom):
            self.assertEqual(mr.main(["--media", "kr"]), 0)


class RoutinesUseTheRadarTest(unittest.TestCase):
    """레이더를 붙인 세 지시문이 실제로 부르는지 본다(2026-09-14).

    한 줄이 사라져도 글은 그대로 나온다 — 주제만 어제 목록 순서로 돌아간다. 조용한 실패다.
    """

    _EXPECTED = {
        "routine_feature.md": "--set ko,magazine",       # 주말 Checkpoint: 한국·해외 함께
        "routine_guide_ko.md": "--set ko",               # 한국어 가이드: 한국 매체
        "routine_guide_en.md": "--set magazine",         # 영어 가이드: 잡지 묶음 그대로
    }

    def test_each_doc_calls_the_radar_with_its_set(self) -> None:
        for doc, flag in self._EXPECTED.items():
            text = (ROOT / "docs" / doc).read_text(encoding="utf-8")
            with self.subTest(doc=doc):
                self.assertIn("scripts.magazine_radar", text)
                self.assertIn(flag, text)

    def test_guides_keep_the_variety_rule_above_the_radar(self) -> None:
        """레이더는 주제를 만들지 않는다 — 갈래 안에서 순서만 바꾼다.

        이 단서가 빠지면 뉴스가 몰린 갈래로 한 주가 쏠리고, 콘텐츠 농장처럼 보인다.
        """
        for doc in ("routine_guide_ko.md", "routine_guide_en.md"):
            text = (ROOT / "docs" / doc).read_text(encoding="utf-8")
            with self.subTest(doc=doc):
                self.assertIn("어제와 다른 갈래", text)
                self.assertIn("갈래", text.split("--set")[1][:400])


if __name__ == "__main__":
    unittest.main()
