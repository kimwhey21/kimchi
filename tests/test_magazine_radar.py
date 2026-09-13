"""아침 레이더(2026-09-13) — 네트워크 없이 파서와 신선도 걸러내기만 본다."""
from __future__ import annotations

import datetime as dt
import unittest
from unittest import mock

import yaml

from scripts import magazine_radar as mr

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
        names = [f["name"] for f in yaml.safe_load(mr.CONFIG.read_text(encoding="utf-8"))["feeds"]]
        for must in ("Yahoo Finance", "MarketWatch", "The Motley Fool", "Visual Capitalist", "Fortune"):
            self.assertTrue(any(must in n for n in names), must)
        self.assertTrue(any("클레멘트" in n for n in names))   # 투자 블로거도 있다


if __name__ == "__main__":
    unittest.main()
