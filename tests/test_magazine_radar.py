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
        self.assertEqual([f["name"] for f in mr.feeds_for("magazine")], [f["name"] for f in sets["magazine"]])
        self.assertEqual(len(mr.feeds_for("ko,magazine")), len(sets["ko"]) + len(sets["magazine"]))
        self.assertEqual(len(mr.feeds_for("all")), sum(len(v) for v in sets.values()))
        with self.assertRaises(SystemExit):
            mr.feeds_for("korean")          # 있는 것은 ko다 — 빈 목록으로 넘어가면 "화제 없음"으로 보인다

    def test_the_fold_flag_rides_on_each_feed_so_mixed_sets_stay_right(self) -> None:
        """묶음을 섞어 부를 수 있다(Checkpoint는 `ko,magazine`). 접기를 전체에 켜고 끄면 한쪽이 틀린다 —
        한국 기사는 접고 잡지 기사는 남겨야 한다. 그래서 피드마다 표를 달아 둔다."""
        mixed = {f["name"]: f["fold_tape"] for f in mr.feeds_for("ko,magazine")}
        self.assertTrue(any(v for v in mixed.values()))
        self.assertTrue(any(not v for v in mixed.values()))
        self.assertTrue(all(f["fold_tape"] for f in mr.feeds_for("en_kr")))
        self.assertTrue(all(not f["fold_tape"] for f in mr.feeds_for("magazine")))

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
        # 2026-09-26부터 매체마다 받는 길(domain·search·feeds)이 붙었다 — 이름은 그대로다.
        self.assertEqual([m["name"] for m in media["kr"]], ["연합뉴스", "한국경제", "아시아경제", "이데일리",
                                                            "머니투데이", "서울경제", "매일경제"])
        self.assertEqual([m["name"] for m in media["us"]], ["Reuters", "CNBC", "Bloomberg", "Yahoo Finance",
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
        with mock.patch.object(mr.requests, "get", side_effect=boom), \
                mock.patch("sys.stdout", new_callable=__import__("io").StringIO) as out:
            self.assertEqual(mr.main(["--media", "kr"]), 0)
        text = out.getvalue()
        self.assertIn("연합뉴스(헤드라인 피드)", text)       # 막힌 매체는 받는 길을 밝힌다
        self.assertIn("allowed_domains: hankyung.com", text)
        self.assertNotIn("yna.co.kr", text.split("allowed_domains:")[1])


class RoutinesUseTheRadarTest(unittest.TestCase):
    """레이더를 붙인 세 지시문이 실제로 부르는지 본다(2026-09-14).

    한 줄이 사라져도 글은 그대로 나온다 — 주제만 어제 목록 순서로 돌아간다. 조용한 실패다.
    """

    _EXPECTED = {
        "routine_feature.md": "--set ko,magazine",       # 주말 Checkpoint: 한국·해외 함께
        "routine_guide_ko.md": "--set ko",               # 한국어 가이드: 한국 매체로 주제 순서를 바꾼다
        "routine_guide_en.md": "--set en_kr",            # 영어 가이드: **주제가 아니라 상시 글이 낡았는지** 본다
    }

    def test_each_doc_calls_the_radar_with_its_set(self) -> None:
        for doc, flag in self._EXPECTED.items():
            text = (ROOT / "docs" / doc).read_text(encoding="utf-8")
            with self.subTest(doc=doc):
                self.assertIn("scripts.magazine_radar", text)
                self.assertIn(flag, text)

    def test_every_radar_doc_asks_for_the_origin_line(self) -> None:
        """레이더를 붙인 네 시리즈는 원고에 출처를 남긴다 — 없으면 효과를 셀 수 없다(2026-09-14)."""
        for doc in ("routine_feature.md", "routine_guide_ko.md", "routine_guide_en.md", "routine_magazine.md"):
            text = (ROOT / "docs" / doc).read_text(encoding="utf-8")
            with self.subTest(doc=doc):
                self.assertIn("radar_origin", text)

    def test_the_korean_guide_keeps_the_variety_rule_above_the_radar(self) -> None:
        """레이더는 주제를 만들지 않는다 — 갈래 안에서 순서만 바꾼다.

        이 단서가 빠지면 뉴스가 몰린 갈래로 한 주가 쏠리고, 콘텐츠 농장처럼 보인다.
        """
        text = (ROOT / "docs" / "routine_guide_ko.md").read_text(encoding="utf-8")
        self.assertIn("어제와 다른 갈래", text)
        self.assertIn("갈래", text.split("--set")[1][:400])

    def test_the_english_guide_uses_the_radar_for_staleness_not_for_topics(self) -> None:
        """2026-09-14에 전제를 바꿨다 — 영어 가이드는 상시 검색 글이라 뉴스 시의성이 거의 안 듣는다.

        같은 날 실측: 잡지 묶음 78줄에 한국 기사가 0줄. 주제는 서치콘솔 검색어 큐가 정하고,
        레이더는 **이미 올라간 상시 글이 낡았는지** 보는 자리로만 남긴다. 이 구분이 문서에서
        사라지면 다음 세션이 다시 뉴스로 주제를 고르게 만든다.
        """
        text = (ROOT / "docs" / "routine_guide_en.md").read_text(encoding="utf-8")
        self.assertIn("src.search_queue", text)
        self.assertNotIn("--set magazine", text)
        head = text.split("--set en_kr")[0][-600:]
        self.assertIn("낡", head)              # "규칙이 바뀌었는가"를 보는 자리라고 적혀 있어야 한다


class ScreenQualityTest(unittest.TestCase):
    """주제를 고를 수 있는 화면인지 본다(2026-09-14, 사용자: "일 대충하지 마").

    한국 매체를 열두 곳까지 넣은 첫 판은 14시간에 118줄이었고, 증시 갈래 96줄 가운데 서른 줄
    넘게가 같은 지수 마감 기사였다. 줄 수가 아니라 **고를 수 있는지**가 이 도구의 품질이다.
    """

    def test_korean_index_tape_is_folded_but_real_stories_survive(self) -> None:
        for tape in ("[속보]코스피, 3.14% 내린 6692.61…코스닥은 806.27",
                     "코스피 하락 마감, 6,684.37P (-3.26%)",
                     "[개장시황] 코스피, FOMC 앞두고 3%대 급락…6600선 후퇴"):
            self.assertTrue(mr.is_tape(tape), tape)
        for story in ("[단독] 정부 ISA 개편안 오락가락 행보에… 계좌 해지 3배 늘었다",
                      "대신증권, 29일 자사주 627억원 소각…“주주환원 본격화”",
                      "코스피 7,000 시대에 PER은 어떻게 읽나",          # 지수 이름 + 숫자지만 시세가 아니다
                      "KRX, 애프터마켓 개장 첫날부터 ‘널뛰기 장세’"):
            self.assertFalse(mr.is_tape(story), story)

    def test_english_headlines_are_never_folded(self) -> None:
        """잡지의 「시장 읽기」는 이 기사로 글을 쓴다 — 접으면 그 코너의 재료가 사라진다."""
        self.assertFalse(mr.is_tape("Dow Jones Futures: Techs Tumble As Anthropic Leads Call For AI Slowdown"))
        self.assertFalse(mr.is_tape("S&P 500 closes 1.2% lower as yields climb"))

    def test_only_bulletin_board_tags_count_as_noise(self) -> None:
        self.assertTrue(mr.is_noise("[부고] 이동훈(미래에셋자산운용 홍보 팀장)씨 형제상"))
        self.assertTrue(mr.is_noise("[인사] 신한투자증권"))
        self.assertFalse(mr.is_noise("[단독] 정부 ISA 개편안 오락가락 행보에… 계좌 해지 3배"))
        self.assertFalse(mr.is_noise("인사 개편이 증권가에 남긴 것"))     # 꼬리표가 아니면 기사다

    def test_the_same_story_merges_across_feeds_and_never_within_one(self) -> None:
        """`+N곳`은 **다른 피드가 같은 기사를 썼다**는 뜻이다. 라벨은 사실이어야 한다.

        같은 피드의 닮은 제목은 대개 같은 기사가 아니라 같은 틀의 다른 공시다 — 회사만 다른
        전환사채 발행 넷을 묶으면 `+3곳`이 거짓말이 된다(2026-09-14 실측).
        """
        rows = [
            {"title": "국민연금, 신임 기금이사에 이규홍 전 사학연금 CIO", "source": "연합인포맥스", "column": "증시", "at": None, "paid": False},
            {"title": "국민연금 투자사령탑에 이규홍 前사학연금 CIO", "source": "매일경제", "column": "증시", "at": None, "paid": False},
            {"title": "링크솔루션, 300억 원 규모 전환사채 발행", "source": "매일경제", "column": "증시", "at": None, "paid": False},
            {"title": "HLB글로벌, 50억 원 규모 전환사채 발행", "source": "매일경제", "column": "증시", "at": None, "paid": False},
        ]
        kept, counts = mr.group(rows)
        self.assertEqual([k["title"] for k in kept],
                         ["국민연금, 신임 기금이사에 이규홍 전 사학연금 CIO",
                          "링크솔루션, 300억 원 규모 전환사채 발행",
                          "HLB글로벌, 50억 원 규모 전환사채 발행"])
        self.assertEqual(kept[0]["also"], ["매일경제"])
        self.assertEqual(counts["merged"], 1)

    def test_every_fold_is_counted(self) -> None:
        """센 수를 찍지 않으면 접는 것이 곧 조용한 실패다 — 없는 날과 접은 날이 같아 보인다."""
        rows = [   # fold_tape는 묶음이 정한다(ko·en_kr만 켜짐) — 잡지 묶음에서는 지수 기사가 재료다
            {"title": "코스피 3.26% 급락해 6,600선 마감", "source": "A", "column": "증시", "at": None, "paid": False, "fold_tape": True},
            {"title": "[부고] 아무개씨 부친상", "source": "A", "column": "증시", "at": None, "paid": False, "fold_tape": True},
            {"title": "대신증권, 자사주 627억원 소각", "source": "A", "column": "증시", "at": None, "paid": False, "fold_tape": True},
        ]
        kept, counts = mr.group(rows)
        self.assertEqual(len(kept), 1)
        self.assertEqual((counts["tape"], counts["noise"], counts["merged"]), (1, 1, 0))

    def test_double_escaped_titles_are_unescaped(self) -> None:
        """실측: 연합인포맥스 제목이 화면에 `&quot;채권자 협의&quot;`로 그대로 찍혔다."""
        xml = "<rss><channel><item><title>제이알리츠, &amp;quot;협의 구체화&amp;quot;</title></item></channel></rss>"
        self.assertEqual(mr.parse(xml)[0]["title"], '제이알리츠, "협의 구체화"')


class BlockedFeedsTest(unittest.TestCase):
    """RSS가 막힌 매체를 버리지 않는다(2026-09-14, 사용자: "rss가 안되면 직접 찾아보고 조사하면 안되니?").

    한국경제(403)·이데일리(연결 거부)·서울경제(404)는 구글뉴스 `site:` 우회로 되살렸다. 같은 날 실측으로
    셋 다 100건·날짜 전부 읽힘. 이 셋이 목록에서 사라지면 "RSS가 죽었으니 어쩔 수 없다"로 되돌아간 것이다.
    """

    def test_the_three_blocked_majors_are_in_the_korean_set_via_proxy(self) -> None:
        feeds = {f["name"]: f["url"] for f in mr.config()["sets"]["ko"]}
        for outlet, site in (("한국경제", "hankyung.com"), ("이데일리", "edaily.co.kr"), ("서울경제", "sedaily.com")):
            row = [(n, u) for n, u in feeds.items() if n.startswith(outlet)]
            with self.subTest(outlet=outlet):
                self.assertEqual(len(row), 1, f"{outlet}이 ko 묶음에 없습니다")
                self.assertIn("news.google.com", row[0][1])
                self.assertIn(site, __import__("urllib.parse", fromlist=["unquote"]).unquote(row[0][1]))

    def test_the_docs_tell_the_routine_to_search_when_a_feed_is_down(self) -> None:
        # 영어 가이드는 빠졌다 — 거기서 레이더는 주제를 고르는 도구가 아니라 상시 글이 낡았는지 보는
        # 도구라, 피드가 조용한 날 WebSearch로 메울 것이 없다(주제는 검색어 큐에서 온다).
        for doc in ("routine_guide_ko.md", "routine_feature.md"):
            text = (ROOT / "docs" / doc).read_text(encoding="utf-8")
            with self.subTest(doc=doc):
                self.assertIn("WebSearch", text)
                self.assertIn("못 읽은 피드", text)


if __name__ == "__main__":
    unittest.main()
