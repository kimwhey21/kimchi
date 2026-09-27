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

    def test_nav_keeps_flex_wrap(self):
        self.assertIn("display:flex;flex-wrap:wrap;gap:12px 20px", PHP)


if __name__ == "__main__":
    unittest.main()
