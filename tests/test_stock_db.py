"""본진 종목 데이터베이스(src/stock_db.py + templates/wp_stock_db.php)를 고정한다 (2026-09-27).

영어 사이트라 종목 이름은 DART 영문명을 다듬어 쓴다 — 대문자뿐인 이름, 붙여 쓴 이름, 잘린 꼬리가 실제로 나왔다
('Korea Zinc'가 'Korea Z'로, 'KT&G'가 'KT & G'로). 매일 올리는 양은 카페24가 큰 요청을 502로 끊어서(224KB) 글자 수로 자른다.
"""
from __future__ import annotations

import datetime as dt
import json
import unittest
from pathlib import Path
from unittest import mock

from src import stock_db as sdb

ROOT = Path(__file__).resolve().parent.parent
PHP = (ROOT / "templates" / "wp_stock_db.php").read_text(encoding="utf-8")


def _row(code, mcap, pct=0.0, value=1e10, market="KOSPI", date="2026-09-23"):
    return {"code": code, "market": market, "name_ko": "가", "close": 1000.0, "chg": 0.0, "pct": pct, "volume": 1.0,
            "value": value, "mcap": mcap, "date": date, "trading": True}


class NamesTest(unittest.TestCase):
    def test_clean_name_cases(self):
        cases = {
            "SAMSUNG ELECTRONICS CO,.LTD": "Samsung Electronics Co., Ltd.",
            "KT&G Corporation": "KT&G Corporation",
            "HANWHA INVESTMENT&amp;SECURITIES": "Hanwha Investment & Securities",
            "AMOREPACIFIC Holdings": "Amorepacific Holdings",
            "CJ ENM CO., Ltd.": "CJ ENM Co., Ltd.",
            "POSCO HOLDINGS INC.": "POSCO Holdings Inc.",
            "EugeneTechnologyCo.,Ltd.": "Eugene Technology Co., Ltd.",
            "SK D & D Co., Ltd.": "SK D&D Co., Ltd.",
        }
        for raw, want in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(sdb.clean_name(raw), want)

    def test_short_name_does_not_eat_word_endings(self):
        # 'Zinc'의 'inc'를 회사 꼬리로 떼던 버그(2026-09-27)
        self.assertEqual(sdb.short_name("Korea Zinc Inc."), "Korea Zinc")
        self.assertEqual(sdb.short_name("Woori Technology, Incorporation"), "Woori Technology")
        self.assertEqual(sdb.short_name("Joyworks & Co., Ltd."), "Joyworks")

    def test_preferred_classes_get_distinct_names(self):
        meta = {"005387": {"name": "Hyundai Motor (Pref.)", "pref": True},
                "005935": {"name": "Samsung Electronics (Pref.)", "pref": True}}
        self.assertEqual(sdb.display_name("005387", "현대차2우B", meta), "Hyundai Motor (Pref. 2B)")
        self.assertEqual(sdb.display_name("005935", "삼성전자우", meta), "Samsung Electronics (Pref.)")

    def test_meta_refresh_keeps_existing_names(self):
        from unittest import mock
        xml = ("<result><list><corp_code>1</corp_code><corp_eng_name>SAMSUNG PHARMACEUTICAL.CO.,LTD</corp_eng_name>"
               "<stock_code>001360</stock_code></list></result>")
        import io, zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("CORPCODE.xml", xml)
        resp = mock.Mock(content=buf.getvalue())
        existing = {"001360": {"name": "Samsung Pharmaceutical", "en": "Samsung Pharmaceutical Co., Ltd.", "industry": "x"}}
        with mock.patch.object(sdb, "_get", return_value=resp):
            meta = sdb.build_meta(mock.Mock(), ["001360"], existing, "k")
        self.assertEqual(meta["001360"]["name"], "Samsung Pharmaceutical")

    def test_committed_meta_is_english(self):
        meta = json.loads(sdb.META.read_text(encoding="utf-8"))
        self.assertGreater(len(meta), 2500)
        self.assertEqual(sdb.hangul_problems(meta), [])
        self.assertEqual(meta["000660"]["name"], "SK Hynix")
        self.assertFalse([c for c, v in meta.items() if "&amp;" in v.get("name", "")])


class DailyRunTest(unittest.TestCase):
    def test_detail_targets_top_plus_rotation(self):
        listing = [_row(f"{i:06d}", mcap=10_000 - i) for i in range(1, 1001)]
        day = dt.date(2026, 9, 28)
        got = sdb.detail_targets(listing, day, False, top=100)
        self.assertEqual(got[:100], [f"{i:06d}" for i in range(1, 101)])
        week = set()
        for k in range(7):
            week |= set(sdb.detail_targets(listing, day + dt.timedelta(days=k), False, top=100))
        self.assertEqual(len(week), 1000, "일주일이면 모든 종목의 상세가 한 번은 새로 와야 한다")
        self.assertEqual(len(sdb.detail_targets(listing, day, True)), 1000)

    def test_template_reads_day_range_and_skhy_source_from_daily_values(self):
        php = (Path(__file__).resolve().parent.parent / "templates" / "wp_stock_db.php").read_text(encoding="utf-8")
        self.assertIn("fs_krw( $q['dlow'] ) . ' – ' . fs_krw( $q['dhigh'] )", php)
        self.assertNotIn("fs_krw( $r['low'] ) . ' – ' . fs_krw( $r['high'] )", php)   # 상세의 고가·저가는 넥스트레이드 합산
        self.assertIn("USD/KRW is the Hana Bank rate near the Seoul close", php)
        self.assertNotIn("SK Hynix closing prices via Naver Finance", php)

    def test_rotation_turn_does_not_move_when_the_ranking_changes(self):
        """감사 F-034: 차례가 '300위 밖 목록에서의 순번'이면 경계가 한 종목만 움직여도 뒤 종목이 모두 밀려 319종목이 12일째 안 돌았다."""
        listing = [_row(f"{i:06d}", mcap=10_000 - i) for i in range(1, 1001)]
        day = dt.date(2026, 10, 6)
        before = set(sdb.detail_targets(listing, day, False, top=100)[100:])
        moved = [dict(r) for r in listing]
        moved[150]["mcap"] = 20_000                                        # 151위가 1위로 — 경계가 움직인다
        after = set(sdb.detail_targets(moved, day, False, top=100)[100:])
        self.assertEqual(before - {"000151", "000100"}, after - {"000151", "000100"})

    def test_assemble_merges_quote_only_items(self):
        listing = [_row("000660", 2e15), _row("123450", 1e11), _row("005930", 3e15)]
        items, index, _ = sdb.assemble(listing, {"000660": {"r": {}, "peers": ["005930", "069500"]}},
                                       {"000660": {"name": "SK Hynix"}, "005930": {"name": "Samsung Electronics"}})
        by = {i["code"]: i for i in items}
        self.assertFalse(by["000660"]["merge"])                     # 상세가 있으면 통째로 바꾼다
        self.assertTrue(by["123450"]["merge"])                      # 시세만이면 서버에서 합친다 — 상세를 지우지 않게
        self.assertEqual(set(by["123450"]["data"]), {"code", "market", "name", "en", "industry", "founded", "web", "pref", "q"})
        self.assertEqual(by["000660"]["data"]["peers"], [{"code": "005930", "name": "Samsung Electronics"}])
        self.assertEqual(index[1][:3], ["000660", "SK Hynix", "KOSPI"])

    def test_market_summary_filters_illiquid_and_uses_latest_flow_day(self):
        listing = [_row("000001", 5e12, pct=29.9, value=1e8), _row("000002", 4e12, pct=5.0), _row("000003", 3e12, pct=-3.0)]
        flow = lambda d, f: {"flows": [{"d": d, "foreign": f, "close": 1000.0}]}  # noqa: E731
        details = {"000002": flow("2026-09-22", 100), "000003": flow("2026-09-22", -50)}
        m = sdb.market_summary(listing, details, {}, {}, None, None)
        self.assertEqual([g["code"] for g in m["gainers"]][:1], ["000002"], "거래대금 50억 미만 잡주는 상승 순위에서 뺀다")
        self.assertEqual(m["flow_date"], "2026-09-22", "마감 직후엔 그날 수급이 없다 — 가장 최근 수급 날을 쓴다")
        self.assertEqual([f["code"] for f in m["foreign_buy"]], ["000002"])
        self.assertEqual([f["code"] for f in m["foreign_sell"]], ["000003"])

    def test_website_check_prefers_http_and_falls_back_to_root(self):
        from unittest import mock
        codes = {"http://www.a.com": 200, "http://www.b.com/kor/x": 404, "https://www.b.com/kor/x": 404, "http://www.b.com": 200}
        with mock.patch.object(sdb, "_curl_status", side_effect=lambda u: codes.get(u, 0)):
            self.assertEqual(sdb.web_alive("www.a.com"), "www.a.com")
            self.assertEqual(sdb.web_alive("www.b.com/kor/x"), "www.b.com", "깊은 주소가 죽고 도메인이 살면 도메인으로")
            self.assertIsNone(sdb.web_alive("www.dead.com"))

    def test_first_day_listing_is_flagged(self):
        details = {"000003": {"hist": {"c": [6090.0] * 50 + [202.0]}}}
        m = sdb.market_summary([_row("000001", 5e12, pct=280.83), _row("000002", 4e12, pct=5.0), _row("000003", 3e12, pct=-96.68)],
                               details, {}, {}, None, None)
        self.assertTrue(m["gainers"][0].get("ipo"), "이력이 하루뿐이고 30%를 넘으면 상장 첫날")
        self.assertNotIn("ipo", m["gainers"][1])
        self.assertTrue(m["losers"][0].get("nolimit"), "이력이 긴데 30%를 넘으면 정리매매 등 — New listing이 아니다")
        self.assertNotIn("ipo", m["losers"][0])

    def test_krx_session_guard(self):
        kst = sdb.KST
        self.assertTrue(sdb.in_krx_session(dt.datetime(2026, 9, 28, 10, 0, tzinfo=kst)))     # 월 10:00 장중
        self.assertFalse(sdb.in_krx_session(dt.datetime(2026, 9, 28, 17, 5, tzinfo=kst)))    # 17:05 정규 실행
        self.assertFalse(sdb.in_krx_session(dt.datetime(2026, 9, 29, 7, 50, tzinfo=kst)))    # 07:50 정규 실행
        self.assertFalse(sdb.in_krx_session(dt.datetime(2026, 9, 27, 11, 0, tzinfo=kst)))    # 일요일
        self.assertTrue(sdb.in_krx_session(dt.datetime(2026, 11, 19, 16, 0, tzinfo=kst)))    # 수능일은 16:30 마감
        self.assertFalse(sdb.in_krx_session(dt.datetime(2026, 11, 19, 9, 30, tzinfo=kst)))   # 수능일은 10:00 개장
        self.assertEqual(sdb.close_window(dt.date(2026, 10, 6)), (dt.time(15, 31), dt.time(16, 0)))
        self.assertEqual(sdb.close_window(dt.date(2026, 11, 19)), (dt.time(16, 31), dt.time(17, 0)))

    def test_short_listing_is_retried_then_refused(self):
        from unittest import mock
        short = [_row(f"{i:06d}", 1e9) for i in range(2490)]
        full = short + [_row(f"9{i:05d}", 1e9) for i in range(273)]
        with mock.patch.object(sdb, "list_market", side_effect=[short, [], full, []]), mock.patch.object(sdb.time, "sleep"):
            self.assertEqual(len(sdb.list_all(mock.Mock(), 2763)), 2763, "모자라면 다시 받아 정상 목록을 쓴다")
        with mock.patch.object(sdb, "list_market", side_effect=[short, []] * 3), mock.patch.object(sdb.time, "sleep"):
            with self.assertRaises(sdb.StockDBError):
                sdb.list_all(mock.Mock(), 2763)

    def test_missing_stock_still_on_naver_is_not_deleted(self):
        from unittest import mock
        ok = mock.Mock(status_code=200); ok.json.return_value = {"stockName": "송원산업"}
        gone = mock.Mock(status_code=404)
        sess = mock.Mock(); sess.get.side_effect = [ok, gone]
        self.assertTrue(sdb.still_listed(sess, "004430"))
        self.assertFalse(sdb.still_listed(sess, "999990"))

    def test_dividends_come_from_filings_with_facts_flagged(self):
        # 2026-09-28 — DART 공시값, 반기 결산은 두 번 합, 튄 배당·이익보다 많은 배당은 사실로 표시
        reit = [{"stlm_dt": "2025-07-31", "se": "주당 현금배당금(원)", "stock_knd": "보통주", "thstrm": "170", "frmtrm": "180", "lwfr": "170"},
                {"stlm_dt": "2026-01-31", "se": "주당 현금배당금(원)", "stock_knd": "보통주", "thstrm": "170", "frmtrm": "170", "lwfr": "180"}]
        self.assertEqual(sdb.parse_dividends(reit)["ttm"], 340.0)
        self.assertIsNone(sdb.parse_dividends([{"stlm_dt": "2025-12-31", "se": "현금배당성향(%)", "thstrm": "30"}]), "배당금 줄이 없으면 싣지 않는다")
        listing = [_row("017800", 2.9e12), _row("005930", 1.6e15), _row("999990", 5e10)]
        listing[0]["close"] = 74000.0
        listing[1]["close"] = 286500.0
        divs = {"017800": {"ttm": 14010.0, "prev": 5500.0, "payout": 193.0, "periods": 1, "end": "2025-12-31"},
                "005930": {"ttm": 1668.0, "prev": 1446.0, "payout": 25.1, "periods": 1, "end": "2025-12-31"},
                "999990": {"ttm": 500.0, "prev": 500.0, "payout": 50.0, "periods": 1}}
        meta = {"017800": {"name": "Hyundai Elevator"}, "005930": {"name": "Samsung Electronics"}, "999990": {"name": "Tiny"}}
        lists = sdb.build_lists(listing, {}, divs, meta, "2026-09-23")
        rows = lists["highest-dividend-yield"]["rows"]
        self.assertEqual([r["code"] for r in rows], ["017800", "005930"], "시가총액 1,000억 미만은 뺀다")
        self.assertEqual(rows[0]["yld"], round(14010 / 74000 * 100, 2))
        self.assertIn("Dividend 2.5× the year before", rows[0]["flags"])
        self.assertIn("Paid out 193% of earnings", rows[0]["flags"])
        self.assertEqual(rows[1]["flags"], [])

    def test_foreign_list_uses_real_ownership(self):
        listing = [_row("030200", 1.3e13), _row("000660", 1.3e15)]
        metrics = {"030200": {"fown": 49.0, "fused": 100.0}, "000660": {"fown": 50.15, "fused": 50.15}}
        rows = sdb.build_lists(listing, metrics, {}, {}, "2026-09-23")["most-foreign-owned"]["rows"]
        self.assertEqual([(r["code"], r["fown"]) for r in rows], [("000660", 50.15), ("030200", 49.0)])

    def test_hangul_is_caught_except_korean_name_field(self):
        self.assertEqual(sdb.hangul_problems({"name_ko": "삼성전자", "q": {}}), [])
        self.assertTrue(sdb.hangul_problems({"industry": "반도체"}))

    def test_batches_stay_under_limit(self):
        rows = [{"code": f"{i:06d}", "blob": "x" * 900} for i in range(200)]
        parts = sdb.batches(rows, limit=10_000)
        self.assertEqual(sum(len(p) for p in parts), 200)
        for part in parts:
            self.assertLessEqual(len(json.dumps(part)), 10_000 + 200)

    def test_next_holiday(self):
        self.assertEqual(sdb.next_holiday(dt.date(2026, 9, 27))["date"], "2026-10-05")


class SnippetTest(unittest.TestCase):
    def test_no_literal_script_tag(self):
        # 글자로 script 태그를 쓰면 NinjaFirewall이 조각 저장을 403으로 막는다(2026-09-27)
        self.assertNotIn("<script", PHP.lower())

    def test_stock_page_links_only_to_things_that_exist(self):
        # 2026-09-27 전수 점검: 없는 칸으로 가는 이동 버튼 14종목, 목록 밖 동종 종목 링크 9곳(404), https를 붙여 인증서 오류
        self.assertIn("if ( $peers ) { $tabs['peers'] = 'Peers'; }", PHP)
        self.assertIn("if ( ! empty( $s['fin']['cols'] ) ) { $tabs['financials']", PHP)
        self.assertIn("isset( $index_by_code[ $p['code'] ] )", PHP)
        self.assertIn(": 'http://' . $s['web']", PHP)
        self.assertNotIn("href=\"/stocks/'+", PHP, "검색 결과 링크를 글자로 조립하면 검색엔진이 가짜 주소로 읽는다")

    def test_preferred_shares_do_not_compare_common_targets(self):
        # 우선주 화면에 보통주 목표주가를 우선주 값과 비교해 +290.77%가 나왔다(2026-09-27, 005387)
        self.assertIn("$pref_of ? array( 'Price target', 'See <a", PHP)

    def test_search_list_is_a_static_file_and_waits_for_it(self):
        # REST로 받으면 첫 검색이 비고, 목록이 오기 전 화살표를 누르면 스크립트 오류가 났다(2026-09-27 버튼 점검)
        self.assertIn("function fs_index_write(", PHP)
        self.assertIn("$out['index_file'] = fs_index_write( $next )", PHP)
        self.assertIn("if(!data){note('Loading…');return}", PHP)
        self.assertIn("if(e.key==='Escape'){res.hidden=true;return}if(!data)return;", PHP)

    def test_foreign_ownership_is_not_the_limit_usage(self):
        # 2026-09-28: 외인소진율(한도 대비)을 지분율로 보여 KT가 100%였다(실제 49.0%)
        self.assertIn("array( 'Foreign ownership <span class=\"fs-kr\">KR</span>', fs_foreign_cell( $s ) )", PHP)
        self.assertIn("$fr = fs_foreign_own( $s );", PHP)
        self.assertIn("of foreign limit used", PHP)

    def test_rewrite_only_takes_krx_codes(self):
        # 숫자로 시작하는 6자리만 — 'nvidia' 같은 옛 영어 주소는 13번 조각의 301로 가야 한다
        self.assertIn("^stocks/([0-9][0-9A-Za-z]{5})/?$", PHP)

    def test_index_swaps_only_when_complete(self):
        self.assertIn("index_total", PHP)
        self.assertIn("fm_stock_index_next", PHP)

    def test_content_filter_runs_after_wpautop(self):
        self.assertIn("}, 99 );   // wpautop(10) 뒤", PHP)

    def test_page_is_widened_not_shifted(self):
        # left:50%+translateX(-50%)로 넓히면 테마의 auto 여백과 겹쳐 1280px보다 넓은 화면에서 오른쪽으로 밀렸다(2026-09-27)
        self.assertNotIn("translateX(-50%)", PHP)
        self.assertIn(".fs-page{max-width:1200px!important", PHP)   # 다른 목록 페이지와 같은 폭

    def test_stocks_page_gets_the_list_style(self):
        # 목록 스타일(흰 배경·글꼴·메뉴 높이)이 Stocks에도 걸려야 네 메뉴 화면이 같다(2026-09-27 크림 배경·319px로 달랐다)
        toss = (ROOT / "templates" / "wp_list_toss.php").read_text(encoding="utf-8")
        self.assertIn("is_page( array( 76, 77, 105, 'stocks' ) )", toss)
        self.assertNotIn(".fs-navwrap div>a{", PHP, "메뉴 버튼 모양은 14번 조각 한 곳에서만 정한다")

    def test_nav_has_one_source(self):
        # 메뉴 네 화면은 같은 틀에서 [fermata_nav] 하나로 그린다(2026-09-27 구조 통일) — 여백 덧대기 규칙이 되살아나면 안 된다
        toss = (ROOT / "templates" / "wp_list_toss.php").read_text(encoding="utf-8")
        self.assertNotIn("body.page main>.wp-block-group.alignfull", toss)
        self.assertNotIn(".page-id-77", toss)
        self.assertIn("function fs_nav( $active = '' )", PHP)
        self.assertIn("is_page( 'stocks' ) ? 'stocks'", PHP)
        self.assertNotIn("fs_nav( 'stocks' )", PHP, "종목 페이지 안에 메뉴를 따로 넣지 않는다 — 틀이 넣는다")

    def test_every_template_calls_the_one_nav(self):
        # 2026-09-28 템플릿 통일 — 모든 블록 템플릿이 메뉴를 [fermata_nav] 한 줄로 부른다. 손으로 쓴 메뉴 줄이 되살아나면 다시 어긋난다
        import re
        files = sorted((ROOT / "templates" / "wp_site").glob("*.html"))
        self.assertGreaterEqual(len(files), 10)
        for f in files:
            text = f.read_text(encoding="utf-8")
            with self.subTest(template=f.name):
                self.assertEqual(text.count("[fermata_nav]"), 1)
                self.assertNotIn('<a href="/stocks/" style="white-space:nowrap', text, "메뉴를 템플릿에 손으로 쓰지 않는다")
                self.assertFalse(re.search(r"[가-힣]", re.sub(r'"(name|description)":"[^"]*"', "", text)), "영어 사이트 템플릿에 한글")
        toss = (ROOT / "templates" / "wp_list_toss.php").read_text(encoding="utf-8")
        self.assertIn("const FERMATA_BASE_CSS", toss)

    def test_stock_name_links_are_guarded(self):
        # 2026-09-28 글 속 종목 이름 연결 — 영어 낱말과 같은 이름(Russell 2000의 Russell·Solid·Union)과 그룹 이름은 잇지 않는다
        for word in ("'russell'", "'solid'", "'union'", "'lotte'", "'hanwha'", "'doosan'"):
            self.assertIn(word, PHP)
        self.assertIn("(?! Group\\\\b)", PHP, "Hyundai Motor Group 같은 그룹 표현은 잇지 않는다")
        self.assertIn("$rank >= 300", PHP)
        self.assertIn("in_category( array( 121, 684, 685, 153 ) )", PHP)
        self.assertIn("delete_transient( 'fs_link_v1' )", PHP, "목록이 바뀌면 연결 표를 다시 만든다")

    def test_list_pages_are_wired(self):
        self.assertIn("'^stocks/lists/([a-z0-9-]+)/?$'", PHP)
        self.assertIn("if ( $slug = fs_current_list() ) { return fs_list_html(", PHP)
        self.assertIn("home_url( '/stocks/lists/' . $k . '/' )", PHP, "순위표도 사이트맵에")
        self.assertIn("$bad_list = ( get_query_var( 'fm_list' ) && ! fs_current_list() ) || ( fs_is_flows() && ! fs_flows() ) || ( fs_is_skhy() && ! fs_skhy() );", PHP, "없는 순위표는 404")

    def test_nav_keeps_flex_wrap(self):
        self.assertIn("display:flex;flex-wrap:wrap;gap:12px 20px", PHP)


class ForeignFlowsTest(unittest.TestCase):
    """/stocks/foreign-flows/ (2026-09-28)."""

    def _detail(self, day, foreign, close, fr, pct, pref_hist=None):
        flows = [{"d": day, "close": close, "foreign": foreign, "fratio": fr}] + [
            {"d": f"2026-09-{22 - i:02d}", "close": close * 0.97, "foreign": foreign, "fratio": fr} for i in range(4)]
        dates = [f"2026-{m:02d}-01" for m in range(4, 10)] * 12
        return {"flows": flows, "hist": {"d": sorted(dates), "fr": [fr - 5] + [fr] * (len(dates) - 1)}}

    def setUp(self):
        day = "2026-09-23"
        self.listing = [_row("005930", 3e14, 3.62), _row("005935", 2e14, 4.96), _row("000660", 1e14, 1.25)]
        self.details = {"005930": self._detail(day, 100, 1000.0, 46.6, 3.62), "005935": self._detail(day, 50, 800.0, 75.0, 4.96),
                        "000660": self._detail(day, -300, 2000.0, 50.0, 1.25)}
        self.meta = {"005930": {"name": "Samsung Electronics"}, "005935": {"name": "Samsung Electronics (Pref.)", "pref": True},
                     "000660": {"name": "SK Hynix"}}
        self.idx = {"KOSPI": {"foreign_net_eok": -4942.0, "flow_date": "20260923"}}

    def test_day_change_is_the_exchange_figure(self):
        f = sdb.build_flows(self.listing, self.details, self.meta, self.idx, {})
        self.assertEqual(f["buy"][0]["pct"], 3.62)          # 수급 줄의 종가끼리 나누면 +3.09%가 나온다
        self.assertEqual(f["buy_total"], 100 * 1000 + 50 * 800)
        self.assertEqual(f["sell"][0]["name"], "SK Hynix")
        self.assertEqual(f["kospi_eok"], -4942.0)

    def test_day_change_is_blank_when_listing_is_another_day(self):
        listing = [dict(r, date="2026-09-28") for r in self.listing]
        f = sdb.build_flows(listing, self.details, self.meta, self.idx, {})
        self.assertIsNone(f["buy"][0]["pct"])
        self.assertIn("flows_page if same_day else None", Path(ROOT / "src" / "stock_db.py").read_text(encoding="utf-8"))

    def test_streak_needs_all_five_days(self):
        f = sdb.build_flows(self.listing, self.details, self.meta, self.idx, {})
        self.assertEqual([r["code"] for r in f["streak"]], ["005930", "005935"])

    def test_ownership_change_skips_preferred(self):
        f = sdb.build_flows(self.listing, self.details, self.meta, self.idx, {})
        self.assertNotIn("005935", [r["code"] for r in f["up"] + f["down"]])
        self.assertEqual(f["up"][0]["diff"], 5.0)

    def test_history_merges_by_date(self):
        # 저녁 실행은 지수 수급이 그날, 종목 수급은 전날 — 아침 실행이 적은 전날 코스피 값을 지우면 안 된다
        hist = {"2026-09-23": {"kospi_eok": -4942.0}}
        evening = {"KOSPI": {"foreign_net_eok": 1200.0, "flow_date": "20260924"}}
        f = sdb.build_flows(self.listing, self.details, self.meta, evening, hist)
        self.assertEqual(hist["2026-09-23"]["kospi_eok"], -4942.0)
        self.assertEqual(hist["2026-09-24"], {"kospi_eok": 1200.0})
        self.assertEqual(f["kospi_eok"], -4942.0)
        self.assertEqual([p["d"] for p in f["series"]], ["2026-09-23"])     # 종목 수급 날짜보다 뒤인 날은 그래프에 넣지 않는다

    def test_page_is_wired(self):
        for needle in ("'^stocks/foreign-flows/?$'", "fm_flows", "home_url( '/stocks/foreign-flows/' )", "fs_list_cards( $lists, $flows, $skhy )",
                       "href=\"/stocks/foreign-flows/\">See all", "fs_flows_html( $f )", "fm_stock_rewrite' ) !== '6'"):
            self.assertIn(needle, PHP)
        self.assertIn("flows_page", Path(ROOT / "src" / "stock_db.py").read_text(encoding="utf-8"))


class SkhyTest(unittest.TestCase):
    """/stocks/skhy-premium/ (2026-09-28): 같은 날짜끼리만 짝짓는다."""

    def _run(self, usd_values, official, fx_files=None):
        from unittest import mock
        import pandas as pd
        idx = pd.to_datetime(["2026-09-21", "2026-09-22", "2026-09-23", "2026-09-24", "2026-09-25", "2026-09-18", "2026-09-17", "2026-09-16"])
        usd = pd.Series(list(usd_values) + [150.0], index=idx)
        hours = pd.DatetimeIndex([f"{d} 15:00" for d in ("2026-09-16", "2026-09-17", "2026-09-18", "2026-09-21", "2026-09-22", "2026-09-23")],
                                 tz="Asia/Seoul").append(pd.DatetimeIndex(["2026-09-23 08:00"], tz="Asia/Seoul"))
        fx = pd.Series([1400.0] * 6 + [9999.0], index=hours).tz_convert("UTC")      # 아침 8시 값은 쓰지 않는다
        sym_of = [None]

        def history(period, auto_adjust=True, interval="1d"):
            if sym_of[0] == "SKHY":
                assert auto_adjust is False, "SKHY는 조정하지 않은 종가"
                return pd.DataFrame({"Close": usd})
            return pd.DataFrame({"Close": fx})

        def tick(sym):
            sym_of[0] = sym
            return mock.Mock(history=history)
        # 서울 종가는 다음 일별 시세(KRX 정규장)에서 — 2026-10-05 전에는 네이버 차트(넥스트레이드 합산)였다
        seoul = {"data": [{"date": f"{d} 00:00:00", "tradePrice": 1_400_000.0, "prevClosingPrice": 1_390_000.0}
                          for d in ("2026-09-16", "2026-09-17", "2026-09-18", "2026-09-21", "2026-09-22", "2026-09-23")]}
        fake_yf = mock.Mock(Ticker=tick)
        from src import fetch_us
        with mock.patch.dict("sys.modules", {"yfinance": fake_yf}), mock.patch.object(sdb, "_get", return_value=mock.Mock(json=lambda: seoul)), \
                mock.patch.object(sdb.time, "sleep"), mock.patch.object(fetch_us, "nasdaq_closes", return_value=official):
            return sdb.build_skhy(mock.Mock(), fx_files=fx_files or {})

    def test_pairs_same_day_only_and_uses_ratio(self):
        p = self._run([150.0, 150.0, 150.0, 999.0, 999.0, 150.0, 150.0], {"2026-09-23": 150.0, "2026-09-25": 999.0})
        self.assertEqual([r["d"] for r in p["rows"]], ["2026-09-16", "2026-09-17", "2026-09-18", "2026-09-21", "2026-09-22", "2026-09-23"])  # 서울이 쉰 9/24·25는 빠진다
        self.assertEqual(p["rows"][0]["seoul_usd"], 100.0)          # 1,400,000 ÷ 10 ÷ 1,400(서울 15시 값 — 아침 8시 9,999는 안 쓴다)
        self.assertEqual(p["rows"][0]["prem"], 50.0)

    def test_fx_comes_from_our_daily_file_first(self):
        """감사 F-026: 야후 일봉 '종가'는 아침 8시 값이었다 — 우리 시세 파일의 하나은행 고시(홈 띠와 같은 값)를 먼저 쓴다."""
        p = self._run([150.0] * 7, {"2026-09-25": 150.0}, fx_files={"2026-09-23": 1500.0})
        self.assertEqual(p["rows"][-1]["fx"], 1500.0)
        self.assertEqual(p["rows"][0]["fx"], 1400.0)

    def test_skhy_close_must_match_nasdaq(self):
        self.assertIsNone(self._run([150.0] * 7, {"2026-09-23": 151.0}))   # 야후 150 / 나스닥 151 — 싣지 않는다
        self.assertIsNone(self._run([150.0] * 7, {}))                      # 나스닥을 못 받으면 확인 못 한 것

    def test_days_after_nasdaq_official_are_left_for_the_next_run(self):
        p = self._run([150.0] * 7, {"2026-09-22": 150.0})
        self.assertEqual(p["rows"][-1]["d"], "2026-09-22")

    def test_page_is_wired(self):
        for needle in ("'^stocks/skhy-premium/?$'", "fm_skhy", "home_url( '/stocks/skhy-premium/' )", "fs_skhy_html( $k )",
                       "fm_stock_rewrite' ) !== '6'", "fs_list_cards( $lists, $flows, $skhy )"):
            self.assertIn(needle, PHP)
        src = Path(ROOT / "src" / "stock_db.py").read_text(encoding="utf-8")
        self.assertIn("skhy = {\"usd\": last[\"usd\"], \"date\": last[\"d\"]", src)   # 홈 칸도 페이지와 같은 짝


if __name__ == "__main__":
    unittest.main()


class AboutTest(unittest.TestCase):
    """회사 소개(2026-09-28): 사람이 쓴 문장을 기계가 본다."""

    def test_issues_catch_hangul_invented_numbers_and_name(self):
        src = "동사는 2002년 설립되어 2008년 코스닥에 상장. 매출 비중 95% 이상. 3개의 종속회사"
        ok = "Tes makes chip equipment. Chip tools are more than 95% of sales. Founded in 2002, it listed on the KOSDAQ in 2008 and has 3 subsidiaries."
        self.assertEqual(sdb.about_issues(ok, "Tes", src), [])
        self.assertIn("근거에 없는 숫자 1999", sdb.about_issues(ok.replace("2002", "1999"), "Tes", src))
        self.assertIn("한글", sdb.about_issues(ok + " 반도체", "Tes", src))
        self.assertIn("표시 이름으로 시작하지 않음", sdb.about_issues("The company " + ok, "Tes", src))

    def test_preferred_shares_borrow_the_common_text(self):
        meta = {"005930": {"name": "Samsung Electronics"}, "005935": {"name": "Samsung Electronics (Pref.)", "pref": True}}
        about = {"005930": {"text": "Samsung Electronics makes chips."}}
        self.assertTrue(sdb.about_text("005935", meta, about).startswith("Samsung Electronics makes chips. These are its preferred shares"))
        self.assertIsNone(sdb.about_text("005935", meta, {}))

    def test_committed_abouts_are_clean(self):
        if not sdb.ABOUT.exists():
            self.skipTest("소개 파일 없음")
        meta = json.loads((ROOT / "data" / "stock_meta.json").read_text(encoding="utf-8"))
        for code, row in json.loads(sdb.ABOUT.read_text(encoding="utf-8")).items():
            self.assertFalse(sdb._HANGUL.search(row["text"]), code)
            self.assertTrue(row["text"].startswith(meta[code]["name"]), code)
            self.assertTrue(120 <= len(row["text"]) <= 650, code)


class _Resp:
    def __init__(self, data):
        self.status_code, self._data = 200, data

    def json(self):
        return self._data


class _Session:
    """네이버 지수 주소별 가짜 응답 — 2026-09-30 07:50(장 전) 실측 모양."""
    def __init__(self, basic_date, basic_close, biz, foreign):
        self.basic_date, self.basic_close, self.biz, self.foreign = basic_date, basic_close, biz, foreign

    def get(self, url, params=None, timeout=None):
        if url.endswith("/basic"):
            return _Resp({"localTradedAt": f"{self.basic_date}T07:50:00+09:00", "closePrice": self.basic_close,
                          "compareToPreviousClosePrice": "0.00", "compareToPreviousPrice": {"name": "UNCHANGED"}, "fluctuationsRatio": "0.00"})
        if url.endswith("/price"):
            return _Resp([{"localTradedAt": "2026-09-29", "closePrice": "6,870.81", "compareToPreviousClosePrice": "18.52",
                           "compareToPreviousPrice": {"name": "FALLING"}, "fluctuationsRatio": "-0.27"},
                          {"localTradedAt": "2026-09-28", "closePrice": "6,889.33", "compareToPreviousClosePrice": "10",
                           "compareToPreviousPrice": {"name": "RISING"}, "fluctuationsRatio": "0.15"}])
        if url.endswith("/trend"):
            return _Resp({"bizdate": self.biz, "foreignValue": self.foreign})
        raise AssertionError(url)


class MarketIndexPreOpenTest(unittest.TestCase):
    def setUp(self):
        self._pause, sdb.PAUSE = sdb.PAUSE, 0

    def tearDown(self):
        sdb.PAUSE = self._pause

    def test_pre_open_uses_the_listing_day_and_drops_todays_zero_flow(self):
        idx = sdb.market_index(_Session("2026-09-30", "6,870.81", "20260930", "0"), "2026-09-29")
        self.assertEqual(idx["KOSPI"]["date"], "2026-09-29")
        self.assertEqual(idx["KOSPI"]["close"], 6870.81)
        self.assertEqual(idx["KOSPI"]["chg"], -18.52)
        self.assertEqual(idx["KOSPI"]["pct"], -0.27)
        self.assertIsNone(idx["KOSPI"]["foreign_net_eok"])
        self.assertIsNone(idx["KOSPI"]["flow_date"])

    def test_after_close_uses_basic_and_todays_flow(self):
        idx = sdb.market_index(_Session("2026-09-30", "6,838.04", "20260930", "-20,529"), "2026-09-30")
        self.assertEqual(idx["KOSPI"]["date"], "2026-09-30")
        self.assertEqual(idx["KOSPI"]["close"], 6838.04)
        self.assertEqual(idx["KOSPI"]["foreign_net_eok"], -20529)
        self.assertEqual(idx["KOSPI"]["flow_date"], "20260930")

    def test_missing_day_row_stops_instead_of_mixing_dates(self):
        with mock.patch.object(sdb, "_index_from_price_file", return_value=None), self.assertRaises(sdb.StockDBError):
            sdb.market_index(_Session("2026-09-30", "6,870.81", "20260930", "0"), "2026-09-25")

    def test_pre_open_prefers_our_committed_price_file(self):
        """2026-10-01 07:50: 네이버 일별 목록이 9/17에서 멈춰 '9/30 줄이 없다'로 죽었다 — 커밋한 시세 파일이 먼저다."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root / "data").mkdir()
            (root / "data" / "price_kr_2026-09-30.json").write_text(json.dumps({"trading_date": "2026-09-30", "macro": [
                {"name_en": "KOSPI", "price": 6838.04, "change": None, "change_pct": -0.48},
                {"name_en": "KOSDAQ", "price": 855.91, "change": None, "change_pct": 0.72}]}), encoding="utf-8")
            with mock.patch.object(sdb, "ROOT", root):
                idx = sdb.market_index(_Session("2026-10-01", "6,838.04", "20261001", "0"), "2026-09-30")
        self.assertEqual(idx["KOSPI"]["date"], "2026-09-30")
        self.assertEqual(idx["KOSPI"]["close"], 6838.04)
        self.assertEqual(idx["KOSPI"]["pct"], -0.48)
        self.assertAlmostEqual(idx["KOSPI"]["chg"], -32.98, places=1)
        self.assertEqual(idx["KOSDAQ"]["pct"], 0.72)
        self.assertIsNone(idx["KOSPI"]["foreign_net_eok"])

    def test_real_price_file_has_both_indices(self):
        """실제 커밋된 9/30 파일로 — 가짜 응답만으로 통과하던 것(어제 실수)을 되풀이하지 않는다."""
        for name in ("KOSPI", "KOSDAQ"):
            got = sdb._index_from_price_file(name, "2026-09-30")
            self.assertIsNotNone(got, name)
            self.assertEqual(got["date"], "2026-09-30")


class KrxPricesTest(unittest.TestCase):
    """종목 페이지 가격은 KRX 정규장 값(2026-10-05): 다음 일별 시세 + 15:3x 전 종목 사진. 어긋나면 올리지 않는다.

    전에는 네이버 통합값을 'At close · Korea Exchange'로 보여 줬다 — 10/2 SK하이닉스 ₩1,842,000 +0.49%(거래소 ₩1,841,000 +0.44%).
    """
    ROW = {"code": "000660", "market": "KOSPI", "close": 1842000.0, "chg": 9000.0, "pct": 0.49, "volume": 2893258.0,
           "value": 5.3e12, "mcap": 1345566936330000.0, "date": "2026-10-02", "trading": True}
    DAUM = [{"d": "2026-10-01", "c": 1833000.0, "base": 1776000.0}, {"d": "2026-10-02", "c": 1841000.0, "base": 1833000.0,
             "v": 1938753, "val": 3568590397500, "shares": 730492365}]

    def test_daum_row_becomes_the_page_price(self):
        row = dict(self.ROW)
        problems, notes = sdb.apply_krx([row], {"000660": self.DAUM}, {"2026-10-02": {"000660": [1841000, 1833000]}})
        self.assertEqual((problems, notes), ([], []))
        self.assertEqual((row["close"], row["chg"], row["pct"]), (1841000.0, 8000.0, 0.44))
        self.assertEqual(row["volume"], 1938753.0)                       # 거래소 거래량(네이버 2,893,258은 넥스트레이드 포함)
        self.assertEqual(row["mcap"], 1841000.0 * 730492365)

    def test_day_range_comes_from_the_daum_row(self):
        """감사 F-041: 당일 범위는 상세(네이버 통합·7일에 한 번)가 아니라 매일 받는 다음 일별 시세(KRX 정규장)의 고가·저가."""
        row = dict(self.ROW)
        daum = [self.DAUM[0], {**self.DAUM[1], "h": 1860000, "l": 1801000}]
        sdb.apply_krx([row], {"000660": daum}, {"2026-10-02": {"000660": [1841000, 1833000]}})
        self.assertEqual((sdb.quote(row)["dlow"], sdb.quote(row)["dhigh"]), (1801000.0, 1860000.0))

    def test_snapshot_only_row_drops_naver_volume_and_range(self):
        """사진만으로 간 종목의 거래량·거래대금은 네이버 통합값이라 KRX 값처럼 싣지 않는다(감사 F-050)."""
        row = {**self.ROW, "dlow": 1.0, "dhigh": 2.0}
        problems, _ = sdb.apply_krx([row], {"000660": []}, {"2026-10-02": {"000660": [1841000, 1833000]}}, "2026-10-02",
                                    third=lambda c, d: 1841000.0)
        self.assertEqual(problems, [])
        self.assertFalse({"volume", "value", "dlow", "dhigh"} & set(sdb.quote(row)))

    def test_disagreement_is_settled_by_a_third_source(self):
        """2026-10-05 결정: 옛 값이 아니라 정확한 값 — 사진과 다음이 다르면 야후와 같은 쪽(실제 10/2: 야후 1,841,000 = 다음)."""
        row = dict(self.ROW)
        problems, notes = sdb.apply_krx([row], {"000660": list(self.DAUM)}, {"2026-10-02": {"000660": [1842000, 1833000]}},
                                        third=lambda code, day: 1841000.0)
        self.assertEqual(problems, [])
        self.assertEqual((row["close"], row["pct"], row["date"]), (1841000.0, 0.44, "2026-10-02"))
        self.assertTrue(any("셋째 근거" in n for n in notes))

    def test_unsettled_disagreement_stops(self):
        for third in (lambda c, d: None, lambda c, d: 1800000.0):
            problems, _ = sdb.apply_krx([dict(self.ROW)], {"000660": list(self.DAUM)},
                                        {"2026-10-02": {"000660": [1842000, 1833000]}}, third=third)
            self.assertEqual(len(problems), 1)

    def test_base_only_dispute_uses_the_exchange_base(self):
        """사진 기준가가 전일 종가 그대로(sv 없이 pcv)이고 다음 기준가가 다르면 다음(거래소 기준가)이 맞다 — 10/2 액면병합 종목들."""
        row = {**self.ROW, "code": "084680"}
        rows = [{"d": "2026-10-01", "c": 532.0, "base": 530.0}, {"d": "2026-10-02", "c": 2700.0, "base": 2660.0}]
        problems, _ = sdb.apply_krx([row], {"084680": rows}, {"2026-10-02": {"084680": [2700, 532]}},
                                    third=lambda c, d: (_ for _ in ()).throw(AssertionError("종가가 같으면 묻지 않는다")))
        self.assertEqual(problems, [])
        self.assertEqual(row["pct"], round((2700 / 2660 - 1) * 100, 2))

    def test_many_disagreements_mean_a_broken_source(self):
        rows = [dict(self.ROW, code=f"{i:06d}") for i in range(sdb.DISPUTE_MAX + 1)]
        problems, _ = sdb.apply_krx(rows, {r["code"]: list(self.DAUM) for r in rows},
                                    {"2026-10-02": {r["code"]: [1842000, 1833000] for r in rows}},
                                    third=lambda c, d: (_ for _ in ()).throw(AssertionError("원천 고장이면 묻지 않는다")))
        self.assertEqual(len(problems), sdb.DISPUTE_MAX + 1)

    def test_adjusted_base_price_day(self):
        """10/2 삼성바이오로직스: 기준가 1,418,000(전일 종가 1,429,000) — 거래소 등락률 −4.51%."""
        row = {**self.ROW, "code": "207940"}
        daum = {"207940": [{"d": "2026-10-02", "c": 1354000.0, "base": 1418000.0}]}
        sdb.apply_krx([row], daum, {"2026-10-02": {"207940": [1354000, 1418000]}})
        self.assertEqual(row["pct"], -4.51)

    def test_daum_missing_falls_back_to_the_snapshot_and_says_so(self):
        row = dict(self.ROW)
        problems, notes = sdb.apply_krx([row], {"000660": [], "005930": [{"d": "2026-10-02", "c": 276000.0, "base": 276000.0}]},
                                        {"2026-10-02": {"000660": [1841000, 1833000], "005930": [276000, 276000]}},
                                        third=lambda c, d: 1841000.0)
        self.assertEqual(problems, [])
        self.assertEqual((row["close"], row["pct"]), (1841000.0, 0.44))
        self.assertTrue(any("야후로 확인한 종목 1개" in n for n in notes))
        # 2026-10-06: 하나 남은 원천을 야후가 확인해 주지 않으면 올리지 않는다
        problems, _ = sdb.apply_krx([dict(self.ROW)], {"000660": []}, {"2026-10-02": {"000660": [1841000, 1833000]}},
                                    "2026-10-02", third=lambda c, d: None)
        self.assertEqual(len(problems), 1)

    def test_whole_source_missing_stops(self):
        """원천 하나뿐인 종목이 많으면(다음이 통째로 막혔거나 그날 사진이 없다) 야후에 묻지 않고 올리지 않는다."""
        rows = [dict(self.ROW, code=f"{i:06d}") for i in range(sdb.ONE_SOURCE_MAX + 1)]
        problems, _ = sdb.apply_krx(rows, {r["code"]: list(self.DAUM) for r in rows}, {},
                                    third=lambda c, d: (_ for _ in ()).throw(AssertionError("원천 고장이면 묻지 않는다")))
        self.assertEqual(len(problems), 1)

    def test_daum_without_todays_row_uses_todays_snapshot(self):
        """다음이 오늘 줄을 아직 안 올렸으면 옛 날짜 값이 섞이지 않게 그날 사진을 쓴다(사진이 기준일을 정한다)."""
        row = dict(self.ROW)
        daum = {"000660": self.DAUM[:1]}                                   # 10/1까지만
        problems, notes = sdb.apply_krx([row], daum, {"2026-10-02": {"000660": [1841000, 1833000]}}, "2026-10-02",
                                        third=lambda c, d: 1841000.0)
        self.assertEqual(problems, [])
        self.assertEqual((row["close"], row["date"]), (1841000.0, "2026-10-02"))
        self.assertTrue(any("야후로 확인한 종목 1개" in n for n in notes))

    def test_long_halted_stock_keeps_its_last_day_and_is_counted(self):
        row = dict(self.ROW)
        problems, notes = sdb.apply_krx([row], {"000660": self.DAUM[:1], "005930": [{"d": "2026-10-02", "c": 276000.0, "base": 276000.0}]},
                                        {"2026-10-02": {"005930": [276000, 276000]}}, "2026-10-02",
                                        third=lambda c, d: (_ for _ in ()).throw(AssertionError("거래정지 종목은 야후에 묻지 않는다")))
        self.assertEqual(problems, [])
        self.assertEqual(row["date"], "2026-10-01")
        self.assertTrue(any("마지막 날짜 값으로" in n for n in notes))

    def test_neither_source_stops(self):
        problems, _ = sdb.apply_krx([dict(self.ROW)], {"000660": []}, {}, "2026-10-02")
        self.assertEqual(len(problems), 1)

    def test_detail_chart_and_range_become_krx(self):
        d = {"r": {"high52": 3002000.0, "low52": 400000.0}, "hist": {"d": ["2026-10-01", "2026-10-02"], "c": [1828000, 1842000], "fr": [49.7, 49.8]},
             "flows": [{"d": "2026-10-02", "close": 1842000.0, "foreign": 10}]}
        out = sdb.krx_detail(d, self.DAUM, (403000.4, 2987000.0))
        self.assertEqual(out["hist"]["c"], [1833000.0, 1841000.0])
        self.assertEqual(out["hist"]["fr"], [49.7, 49.8])
        self.assertEqual((out["r"]["low52"], out["r"]["high52"]), (403000.0, 2987000.0))
        self.assertEqual(out["flows"][0]["close"], 1841000.0)

    def test_chart_window_matches_the_ownership_history(self):
        d = {"hist": {"d": ["2026-10-02"], "c": [1842000], "fr": [49.8]}}
        out = sdb.krx_detail(d, self.DAUM, (None, None))
        self.assertEqual(out["hist"], {"d": ["2026-10-02"], "c": [1841000.0], "fr": [49.8]})

    def test_daum_stops_asking_after_repeated_failures(self):
        from unittest import mock
        daum = sdb.Daum(mock.Mock())
        with mock.patch.object(sdb, "_get", side_effect=sdb.StockDBError("403")) as got, mock.patch.object(sdb.time, "sleep"):
            for code in ("1", "2", "3", "4", "5", "6", "7"):
                self.assertEqual(daum.days(code), [])
        self.assertEqual(got.call_count, sdb.DAUM_TRIP)
        self.assertEqual(len(daum.failed), 7)
        self.assertTrue(daum.down)

    def test_holiday_is_not_a_session(self):
        self.assertFalse(sdb.in_krx_session(dt.datetime(2026, 10, 5, 10, 0, tzinfo=sdb.KST)))
        self.assertTrue(sdb.in_krx_session(dt.datetime(2026, 10, 6, 10, 0, tzinfo=sdb.KST)))


class DaumHaltedTest(unittest.TestCase):
    def test_halted_stock_keeps_its_price_at_zero_change(self):
        """2026-10-05: 거래정지 종목은 다음이 기준가를 0으로 준다 — 버리지 않고 가격 그대로·0%로 읽는다."""
        from unittest import mock
        body = {"data": [{"date": "2026-10-02 00:00:00", "tradePrice": 5820.0, "change": "EVEN", "prevClosingPrice": 0.0,
                          "accTradeVolume": 0, "accTradePrice": 0.0, "listedSharesCount": 39139903}]}
        daum = sdb.Daum(mock.Mock())
        with mock.patch.object(sdb, "_get", return_value=mock.Mock(json=lambda: body)), mock.patch.object(sdb.time, "sleep"):
            rows = daum.days("001470")
        self.assertEqual((rows[0]["c"], rows[0]["base"]), (5820.0, 5820.0))
        row = {"code": "001470", "close": 5820.0, "mcap": 1.0}
        sdb.apply_krx([row], {"001470": rows}, {"2026-10-02": {"001470": [5820, 5820]}})
        self.assertEqual((row["pct"], row["chg"], row["volume"]), (0.0, 0.0, 0.0))
