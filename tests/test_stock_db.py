"""본진 종목 데이터베이스(src/stock_db.py + templates/wp_stock_db.php)를 고정한다 (2026-09-27).

영어 사이트라 종목 이름은 DART 영문명을 다듬어 쓴다 — 대문자뿐인 이름, 붙여 쓴 이름, 잘린 꼬리가 실제로 나왔다
('Korea Zinc'가 'Korea Z'로, 'KT&G'가 'KT & G'로). 매일 올리는 양은 카페24가 큰 요청을 502로 끊어서(224KB) 글자 수로 자른다.
"""
from __future__ import annotations

import datetime as dt
import json
import unittest
from pathlib import Path

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
        self.assertIn("$bad_list = ( get_query_var( 'fm_list' ) && ! fs_current_list() ) || ( fs_is_flows() && ! fs_flows() );", PHP, "없는 순위표는 404")

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
        for needle in ("'^stocks/foreign-flows/?$'", "fm_flows", "home_url( '/stocks/foreign-flows/' )", "fs_list_cards( $lists, $flows )",
                       "href=\"/stocks/foreign-flows/\">See all", "fs_flows_html( $f )", "fm_stock_rewrite' ) !== '5'"):
            self.assertIn(needle, PHP)
        self.assertIn("flows_page", Path(ROOT / "src" / "stock_db.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
