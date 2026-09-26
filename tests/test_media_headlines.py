"""`scripts/media_headlines` — 검색 도구에 막힌 시황 매체를 헤드라인 피드로 본다 (2026-09-26).

9/26 실측: 루틴의 검색 도구는 `allowed_domains`에 Anthropic 로봇을 막은 매체가 하나라도 섞이면 검색 전체를
400으로 거절한다. Reuters·WSJ·Barron's·연합뉴스·매일경제가 그랬다. 여기서 고정하는 것 — 막힌 매체는 검색
주소에서 빠지고, 받는 길(`feeds`)이 반드시 있고, 헤드라인은 짧게 줄고, 실패는 센다. 네트워크는 쓰지 않는다.
"""
from __future__ import annotations

import datetime as dt
import unittest
from unittest import mock

from scripts import magazine_radar as mr
from scripts import media_headlines as mh

NOW = dt.datetime(2026, 9, 23, 7, 25, tzinfo=dt.timezone.utc)   # KST 16:25


def _rfc(hours_ago: float) -> str:
    return (NOW - dt.timedelta(hours=hours_ago)).strftime("%a, %d %b %Y %H:%M:%S +0000")


def _rss(*items: tuple[str, float, str]) -> str:
    body = "".join(f"<item><title><![CDATA[{t}]]></title><link>https://x/{i}</link><pubDate>{_rfc(h)}</pubDate>"
                   f"<description><![CDATA[{d}]]></description></item>" for i, (t, h, d) in enumerate(items))
    return f"<rss><channel><title>Feed</title>{body}</channel></rss>"


class _Resp:
    def __init__(self, text: str, status: int = 200) -> None:
        self.text, self.status_code, self.encoding = text, status, "utf-8"

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class ConfigTest(unittest.TestCase):
    """받는 길은 `config/magazine_feeds.yaml`의 `market_media` 한곳이다."""

    BLOCKED = {"kr": {"연합뉴스", "매일경제"}, "us": {"Reuters", "WSJ", "Barron's"}}

    def test_blocked_outlets_are_marked_and_have_feeds(self) -> None:
        for market, names in self.BLOCKED.items():
            with self.subTest(market=market):
                self.assertEqual({o["name"] for o in mh.feed_outlets(market)}, names)
                for o in mh.feed_outlets(market):
                    self.assertTrue(o["feeds"], o["name"])

    def test_search_domains_never_include_blocked_ones(self) -> None:
        """하나라도 섞이면 검색 전체가 400이다 — 9/26 실측으로 막힌 주소를 박는다."""
        blocked = {"reuters.com", "wsj.com", "barrons.com", "yna.co.kr", "mk.co.kr"}
        for market in ("kr", "us"):
            with self.subTest(market=market):
                domains = mh.search_domains(market)
                self.assertTrue(domains)
                self.assertFalse(blocked & set(domains), domains)
        self.assertEqual(mh.search_domains("us"), ["cnbc.com", "bloomberg.com", "finance.yahoo.com", "investing.com"])

    def test_blocked_outlet_without_feeds_fails_loudly(self) -> None:
        conf = {"market_media": {"kr": [{"name": "막힌곳", "domain": "x.kr", "search": False}]}}
        with mock.patch.object(mr, "config", return_value=conf):
            with self.assertRaises(ValueError):
                mh.outlets("kr")

    def test_old_wsj_feed_is_not_used(self) -> None:
        """feeds.a.dj.com은 200인데 2025년 1월 기사에서 멈춰 있었다(9/26 실측) — 되돌아오면 옛 기사를 읽는다."""
        urls = [u for o in mh.feed_outlets("us") for u in o["feeds"]]
        self.assertFalse(any("feeds.a.dj.com" in u for u in urls), urls)

    def test_user_agent_is_not_a_browser(self) -> None:
        """매체가 AI 접근을 막은 것이다 — 브라우저인 척하지 않는다."""
        ua = mh.UA["User-Agent"]
        self.assertNotIn("Chrome", ua)
        self.assertNotIn("Safari", ua)
        self.assertIn("Fermata", ua)


class ParseTest(unittest.TestCase):
    def test_strips_google_tail_and_yonhap_byline(self) -> None:
        xml = _rss(("Wall Street ends higher as investors buy AI stocks - Reuters", 1, "<a>Wall Street</a> Reuters"),
                   ("코스피 7,080 마감", 1, "(서울=연합뉴스) 김유아 기자 = 코스피는 23일 7천선을 지켰다."))
        rows = mh.parse(xml)
        self.assertEqual(rows[0]["title"], "Wall Street ends higher as investors buy AI stocks")
        self.assertEqual(rows[1]["summary"], "코스피는 23일 7천선을 지켰다.")
        self.assertIsNotNone(rows[0]["at"])

    def test_google_summary_that_repeats_the_title_is_dropped(self) -> None:
        self.assertEqual(mh._useful_summary("Battered bonds draw support", "Battered bonds draw support Reuters"), "")
        self.assertEqual(mh._useful_summary("Stocks rise", "The Dow snaps its losing streak."),
                         "The Dow snaps its losing streak.")


class CollectTest(unittest.TestCase):
    def _run(self, feeds: dict[str, str | Exception], market: str = "kr", **kw):
        def fake_get(url, headers=None, timeout=None):
            got = feeds[url]
            if isinstance(got, Exception):
                raise got
            return _Resp(got)
        conf = {"market_media": {market: [
            {"name": "가", "domain": "a.kr", "search": False, "feeds": ["https://a/rss"]},
            {"name": "나", "domain": "b.kr", "search": False, "feeds": ["https://b/rss"]},
            {"name": "다", "domain": "c.kr"},
        ]}}
        with mock.patch.object(mr, "config", return_value=conf), \
                mock.patch.object(mh.requests, "get", side_effect=fake_get):
            return mh.render(market, now=NOW, **kw), mh

    def test_window_dedup_noise_and_topic(self) -> None:
        a = _rss(("삼성전자, 3%대 급등 마감", 0.5, "먼저 나온 기사"),
                 ("삼성전자 3%대 급등 마감(종합)", 0.4, "요약"),          # 같은 매체 같은 기사 → 새것 한 줄
                 ("[표] 코스닥 외국인 순매수 상위", 0.3, ""),               # 게시물
                 ("서울 아파트값 85주 연속 상승", 0.2, ""),                 # 시장 낱말 있음(상승) → 남는다
                 ("원·달러 환율 반등", 0.15, ""),
                 ("주말 날씨 맑음", 0.1, ""),                               # 시장 제목이 셋 이상이면 빠진다
                 ("코스피 7천선 지켜", 30, ""))                             # 18시간 밖
        b = _rss(("삼성전자, 3%대 급등 마감", 0.6, ""),                    # 다른 매체 같은 기사 → +나
                 ("환율 1,360원선", 1, ""), ("외국인 순매도 전환", 2, ""), ("금리 동결", 3, ""))
        text, _ = self._run({"https://a/rss": a, "https://b/rss": b}, names=["삼성전자"])
        self.assertIn("allowed_domains`에는 이것만: c.kr", text)
        self.assertIn("삼성전자 3%대 급등 마감(종합) — 요약", text)
        self.assertNotIn("먼저 나온 기사", text)
        self.assertNotIn("[표]", text)
        self.assertNotIn("날씨", text)
        self.assertNotIn("7천선", text)
        self.assertIn("+나", text)
        self.assertIn("[가] 3줄 (받은 것 7건 · 최근 18시간)", text)
        # 우리 종목 이름이 든 제목이 맨 앞
        self.assertLess(text.index("삼성전자 3%대"), text.index("아파트값"))

    def test_per_outlet_cap(self) -> None:
        words = ["반도체", "조선", "방산", "은행", "보험", "화학", "철강", "건설", "게임", "바이오", "자동차", "항공"]
        many = _rss(*[(f"{w}주 {i}일째 강세", i * 0.1, "") for i, w in enumerate(words)])
        text, _ = self._run({"https://a/rss": many, "https://b/rss": _rss()}, market="kr")
        self.assertIn(f"[가] {mh.PER_OUTLET['kr']}줄", text)

    def test_partial_failure_is_counted(self) -> None:
        text, _ = self._run({"https://a/rss": _rss(("코스피 상승", 1, "")), "https://b/rss": RuntimeError("403")})
        self.assertIn("⚠ 1건을 받지 못했습니다: 나: RuntimeError", text)
        self.assertIn("[나] 0줄", text)

    def test_all_feeds_failing_raises(self) -> None:
        """전부 실패하면 '오늘 기사가 없다'와 구별되지 않는다 — 예외로 올려 precheck가 센다."""
        with self.assertRaises(RuntimeError):
            self._run({"https://a/rss": RuntimeError("x"), "https://b/rss": RuntimeError("y")})


if __name__ == "__main__":
    unittest.main()
