"""scripts.phrase_size — 검색되는 말의 경쟁 글 수·띠·순위. 바깥 호출은 전부 가짜로 막는다."""
import datetime as dt
import io
import json
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from scripts import phrase_size as ps


class _Resp:
    def __init__(self, body): self._b = json.dumps(body).encode()
    def read(self): return self._b
    def __enter__(self): return self
    def __exit__(self, *a): return False


NOW = dt.datetime(2026, 11, 14, 3, 0, tzinfo=dt.timezone.utc)   # 한국 시간 11월 14일 낮 12시


def _fake(totals=None, pages=None, tool=None, trend=None, news=None, docs=None):
    """블로그 검색: query → total, (query, start) → items. 키워드 도구: tool = [(relKeyword, pc, mobile)].
    검색어 트렌드: trend = {말: {기간: 비율}}. 뉴스: news = {말: ([몇 시간 전, …], 전체 건수)}. 웹문서: docs = {말: [(주소, 제목)]}."""
    def opener(req, timeout=0):
        from email.utils import format_datetime
        from urllib.parse import parse_qs, urlparse
        u = urlparse(req.full_url)
        if u.path == "/search-trend/v1/search":
            assert req.get_header("X-ncp-apigw-api-key-id") == "id" and req.get_header("Content-type") == "application/json"
            body = json.loads(req.data)
            assert 1 <= len(body["keywordGroups"]) <= 5
            return _Resp({"results": [{"title": g["groupName"], "data": [{"period": k, "ratio": v} for k, v in (trend or {}).get(g["groupName"], {}).items()]}
                                      for g in body["keywordGroups"]]})
        if u.path in ("/search/v1/news", "/search/v1/webkr"):
            assert req.get_header("X-ncp-apigw-api-key-id") == "nid" and req.get_header("X-ncp-apigw-api-key") == "nsec"
            query = parse_qs(u.query)["query"][0]
            if u.path.endswith("webkr"):
                return _Resp({"items": [{"link": link, "title": title, "description": "설명"} for link, title in (docs or {}).get(query, [])]})
            hours, total = (news or {}).get(query, ([], 0))
            return _Resp({"total": total, "items": [{"title": f"<b>{query}</b> 기사 {i}", "originallink": f"https://www.press{i}.co.kr/a", "link": "https://n.news.naver.com/x",
                                                    "pubDate": format_datetime(NOW - dt.timedelta(hours=h))} for i, h in enumerate(hours)]})
        if u.netloc == "api.searchad.naver.com":
            assert u.path == "/keywordstool" and req.get_header("X-customer") == "cust" and req.get_header("X-api-key") == "lic"
            assert req.get_header("X-signature") and req.get_header("X-timestamp")
            return _Resp({"keywordList": [{"relKeyword": k, "monthlyPcQcCnt": pc, "monthlyMobileQcCnt": mo} for k, pc, mo in (tool or [])]})
        q = parse_qs(u.query)
        query, start = q["query"][0], int(q["start"][0])
        assert req.get_header("X-ncp-apigw-api-key-id") == "id" and req.get_header("X-ncp-apigw-api-key") == "sec"
        return _Resp({"total": (totals or {}).get(query, 0), "items": (pages or {}).get((query, start), [])})
    return opener


class PhraseSizeTest(unittest.TestCase):
    def test_band_thresholds(self):
        self.assertEqual([ps.band(n) for n in (0, ps.NARROW, ps.NARROW + 1, ps.MIDDLE, ps.MIDDLE + 1)],
                         ["좁음", "좁음", "보통", "보통", "넓음"])

    def test_no_keys_is_loud_not_silent(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(ps, "KEY_FILE", ps.Path("/nonexistent/x.env")):
            with self.assertRaises(ps.NoKeys):
                ps.load_keys()
            err = io.StringIO()
            with redirect_stderr(err):
                self.assertEqual(ps.main(["아무 말"]), 2)
            self.assertIn("NAVER_CLIENT_ID", err.getvalue())

    AD = {"NAVER_CLIENT_ID": "id", "NAVER_CLIENT_SECRET": "sec", "SEARCHAD_CUSTOMER_ID": "cust", "SEARCHAD_API_KEY": "lic", "SEARCHAD_SECRET": "c2VjcmV0"}

    def _run(self, argv, **fake):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, self.AD, clear=True), mock.patch.object(ps, "KEY_FILE", ps.Path("/nonexistent/x.env")), \
                mock.patch.object(ps.urllib.request, "urlopen", _fake(**fake)), mock.patch.object(ps.time, "sleep", lambda s: None), \
                redirect_stdout(out), redirect_stderr(err):
            rc = ps.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def test_pick_prefers_narrow_band_with_most_searches(self):
        """좁음 띠에서 검색 수가 가장 많은 말. 검색이 많아도 넓음은 안 고르고, 좁음에 있으면 보통의 큰 말도 안 고른다."""
        rc, out, _ = self._run(["큰 말", "중간 말", "좁은 말", "sk 좁은 말", "아무도 안 찾는 말"],
                               totals={"큰 말": 900_000, "중간 말": 40_000, "좁은 말": 9_000, "sk 좁은 말": 5_000, "아무도 안 찾는 말": 30},
                               tool=[("큰말", 9000, 30000), ("중간말", 20000, 90000), ("좁은말", 60, 220), ("SK좁은말", 700, 3000), ("아무도안찾는말", "< 10", "< 10")])
        self.assertEqual(rc, 0)
        self.assertIn("→ 고를 말: sk 좁은 말 (월 검색 3,700회 · 경쟁 글 5,000편 · 좁음)", out)
        self.assertTrue(out.splitlines()[0].startswith("좁음") and out.splitlines()[-2].startswith("넓음"))
        for secret in ("lic", "c2VjcmV0", "cust"):
            self.assertNotIn(secret, out)

    def test_pick_falls_back_to_middle_band(self):
        rc, out, _ = self._run(["중간 말", "조용한 말"], totals={"중간 말": 40_000, "조용한 말": 100}, tool=[("중간말", 100, 400), ("조용한말", "< 10", 20)])
        self.assertIn("→ 고를 말: 중간 말", out)

    def test_no_pick_when_only_wide_or_unsearched(self):
        rc, out, _ = self._run(["큰 말", "조용한 말"], totals={"큰 말": 900_000, "조용한 말": 100}, tool=[("큰말", 9000, 30000), ("조용한말", "< 10", 20)])
        self.assertIn("→ 고를 말이 없습니다", out)

    def test_without_ad_keys_says_volume_was_not_measured(self):
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"NAVER_CLIENT_ID": "id", "NAVER_CLIENT_SECRET": "sec"}, clear=True), mock.patch.object(ps, "KEY_FILE", ps.Path("/nonexistent/x.env")), \
                mock.patch.object(ps.urllib.request, "urlopen", _fake(totals={"좁힌 말": 1_200})), redirect_stdout(out):
            self.assertEqual(ps.main(["좁힌 말"]), 0)
        self.assertIn("월 검색 수는 재지 못했습니다", out.getvalue())
        self.assertIn("→ 좁은 말: 좁힌 말", out.getvalue())

    def test_related_lists_seed_words_by_volume(self):
        rc, out, _ = self._run(["--related", "연금저축 공제"], totals={"연금저축한도": 8_000, "연금저축": 1_000_000},
                               tool=[("연금저축", 6000, 20000), ("연금저축한도", 300, 900), ("전혀다른말", 5000, 5000), ("공제작은말", 10, 20)])
        self.assertEqual(rc, 0)
        self.assertIn("연금저축한도", out); self.assertNotIn("전혀다른말", out); self.assertNotIn("공제작은말", out)
        self.assertIn("→ 고를 말: 연금저축한도", out)

    def test_related_needs_ad_keys(self):
        err = io.StringIO()
        with mock.patch.dict(os.environ, {"NAVER_CLIENT_ID": "id", "NAVER_CLIENT_SECRET": "sec"}, clear=True), mock.patch.object(ps, "KEY_FILE", ps.Path("/nonexistent/x.env")), redirect_stderr(err):
            self.assertEqual(ps.main(["--related", "씨앗"]), 2)
        self.assertIn("SEARCHAD", err.getvalue())

    def test_main_sorts_narrow_first_and_never_prints_keys(self):
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"NAVER_CLIENT_ID": "id", "NAVER_CLIENT_SECRET": "sec"}, clear=True), mock.patch.object(ps, "KEY_FILE", ps.Path("/nonexistent/x.env")), \
                mock.patch.object(ps.urllib.request, "urlopen", _fake(totals={"넓은 말": 900_000, "좁힌 말": 1_200})), redirect_stdout(out):
            self.assertEqual(ps.main(["넓은 말", "좁힌 말"]), 0)
        lines = out.getvalue().splitlines()
        self.assertTrue(lines[0].startswith("좁음") and "좁힌 말" in lines[0])
        self.assertTrue(lines[1].startswith("넓음"))
        self.assertIn("→ 좁은 말: 좁힌 말", lines[-1])
        self.assertNotIn("sec", out.getvalue())

    def test_main_says_so_when_nothing_is_narrow(self):
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"NAVER_CLIENT_ID": "id", "NAVER_CLIENT_SECRET": "sec"}, clear=True), mock.patch.object(ps, "KEY_FILE", ps.Path("/nonexistent/x.env")), \
                mock.patch.object(ps.urllib.request, "urlopen", _fake(totals={"큰 말": 500_000})), redirect_stdout(out):
            ps.main(["큰 말"])
        self.assertIn("좁은 말이 없습니다", out.getvalue())

    def test_failed_phrase_is_counted_not_swallowed(self):
        def boom(req, timeout=0):
            raise ps.urllib.error.URLError("down")
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, {"NAVER_CLIENT_ID": "id", "NAVER_CLIENT_SECRET": "sec"}, clear=True), mock.patch.object(ps, "KEY_FILE", ps.Path("/nonexistent/x.env")), \
                mock.patch.object(ps.urllib.request, "urlopen", boom), redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(ps.main(["말"]), 3)
        self.assertIn("받지 못했습니다: 말", err.getvalue())

    def test_rank_finds_blog_on_second_page(self):
        other = [{"title": "남의 글", "link": "https://blog.naver.com/someone/1", "bloggerlink": "blog.naver.com/someone"}] * ps.PAGE
        mine = [{"title": "<b>우리</b> 글", "link": "https://blog.naver.com/ourblog/22", "bloggerlink": "blog.naver.com/ourblog"}]
        with mock.patch.object(ps.urllib.request, "urlopen", _fake(totals={"말": 500}, pages={("말", 1): other, ("말", ps.PAGE + 1): other[:6] + mine})), \
                mock.patch.object(ps.time, "sleep", lambda s: None):
            r = ps.rank("말", r"blog\.naver\.com/ourblog(/|$)", keys=("id", "sec"))
        self.assertEqual((r["rank"], r["title"], r["band"]), (ps.PAGE + 7, "우리 글", "좁음"))

    def test_never_asks_for_more_than_a_page(self):
        """100건을 한 번에 받으면 순위가 30씩 틀린다 — 쪽 크기를 넘겨 부르지 않는다."""
        seen = []
        def opener(req, timeout=0):
            from urllib.parse import parse_qs, urlparse
            seen.append(int(parse_qs(urlparse(req.full_url).query)["display"][0]))
            return _Resp({"total": 5, "items": []})
        with mock.patch.object(ps.urllib.request, "urlopen", opener):
            ps.rank("말", "x", keys=("id", "sec")); ps.size("말", keys=("id", "sec"))
        self.assertLessEqual(max(seen), 30)
        self.assertEqual(ps.PAGE, 30)

    def test_rank_none_when_not_within_depth(self):
        other = [{"title": "남", "link": "https://blog.naver.com/someone/1", "bloggerlink": "blog.naver.com/someone"}] * ps.PAGE
        with mock.patch.object(ps.urllib.request, "urlopen", _fake(totals={"말": 90_000}, pages={("말", s): other for s in range(1, 301, ps.PAGE)})), \
                mock.patch.object(ps.time, "sleep", lambda s: None):
            r = ps.rank("말", r"blog\.naver\.com/ourblog(/|$)", keys=("id", "sec"))
        self.assertIsNone(r["rank"])
        self.assertEqual(r["band"], "넓음")


class _Clock(dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)


class TimingTest(unittest.TestCase):
    """때를 재는 값(2026-11-14): 기사 24시간·검색 추세·제철. 바깥 호출은 전부 가짜다."""
    ENV = {**PhraseSizeTest.AD, "NAVER_NEWS_CLIENT_ID": "nid", "NAVER_NEWS_CLIENT_SECRET": "nsec"}

    def _run(self, argv, env=None, **fake):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, env or self.ENV, clear=True), mock.patch.object(ps, "KEY_FILE", ps.Path("/nonexistent/x.env")), \
                mock.patch.object(ps.urllib.request, "urlopen", _fake(**fake)), mock.patch.object(ps.time, "sleep", lambda s: None), \
                mock.patch.object(ps.dt, "datetime", _Clock), redirect_stdout(out), redirect_stderr(err):
            rc = ps.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def test_new_event_phrase_is_picked_by_news_when_volume_is_not_there_yet(self):
        """오늘 처음 뜬 이름+사건은 월 검색이 0으로 나온다 — 24시간 기사가 몰렸으면 고른다. 늘 기사가 많은 흔한 말은 아니다."""
        rc, out, err = self._run(["새 사건 이름", "흔한 말", "조용한 말"], totals={"새 사건 이름": 900, "흔한 말": 3_000, "조용한 말": 50},
                                 tool=[("새사건이름", "< 10", "< 10"), ("흔한말", 20, 40), ("조용한말", "< 10", "< 10")],
                                 news={"새 사건 이름": ([1] * 30 + [40] * 20, 1_200), "흔한 말": ([2] * 48 + [30] * 52, 250_000), "조용한 말": ([300], 80)})
        self.assertEqual((rc, err), (0, ""))
        self.assertIn("→ 고를 말: 새 사건 이름 (새로 뜬 말 — 월 검색은 아직 안 잡혔고 지난 24시간 기사 30건 · 경쟁 글 900편 · 좁음)", out)
        self.assertIn("기사 24시간   30건", out)
        self.assertEqual(sum("기사 몰림" in line for line in out.splitlines()), 1)

    def test_measured_volume_still_wins_over_news(self):
        rc, out, _ = self._run(["찾는 말", "기사만 많은 말"], totals={"찾는 말": 5_000, "기사만 많은 말": 800},
                               tool=[("찾는말", 300, 900), ("기사만많은말", "< 10", 20)], news={"기사만 많은 말": ([1] * 40, 500)})
        self.assertIn("→ 고를 말: 찾는 말 (월 검색 1,200회", out)

    def test_news_cap_prints_as_more_than(self):
        rc, out, _ = self._run(["큰 사건"], totals={"큰 사건": 100}, tool=[("큰사건", 5000, 9000)], news={"큰 사건": ([1] * ps.NEWS_CAP, 3_000)})
        self.assertIn(f"기사 24시간 {ps.NEWS_CAP}+건", out)

    def test_without_news_keys_still_picks_and_says_so(self):
        rc, out, err = self._run(["찾는 말"], env=PhraseSizeTest.AD, totals={"찾는 말": 5_000}, tool=[("찾는말", 300, 900)])
        self.assertEqual(rc, 0)
        self.assertIn("→ 고를 말: 찾는 말", out)
        self.assertIn("기사 수는 재지 못했습니다", err)
        self.assertTrue(out.splitlines()[-1].startswith("→"))

    def test_surge_is_yesterday_over_the_fourteen_days_before(self):
        today = dt.date(2026, 11, 14)
        flat = {(today - dt.timedelta(days=i)).isoformat(): 2.0 for i in range(2, 17)}
        self.assertEqual(ps.surge({**flat, "2026-11-13": 6.0}, today), 3.0)
        self.assertEqual(ps.surge(flat, today), 1.0)                       # 새벽이라 어제 값이 아직 없으면 그제 값으로
        self.assertIsNone(ps.surge({"2026-11-01": 5.0}, today))            # 요즘 검색이 없다
        self.assertEqual(ps.surge({"2026-11-13": 4.0}, today), 99.0)       # 전에 없던 말

    def test_rising_needs_enough_searchers_or_a_news_burst(self):
        self.assertFalse(ps.is_rising({"surge": 28.0, "searches": 100}))    # 하루 서너 번 찾는 말의 배수는 우연이다
        self.assertTrue(ps.is_rising({"surge": 2.0, "searches": 5_000}))
        self.assertTrue(ps.is_rising({"surge": 5.8, "searches": 20, "news24": 27, "news_total": 900}))

    def test_trend_groups_five_per_call_and_joins_spaced_and_unspaced(self):
        bodies = []
        def opener(req, timeout=0):
            bodies.append(json.loads(req.data))
            return _Resp({"results": [{"title": g["groupName"], "data": [{"period": "2026-11-13", "ratio": 1.5}]} for g in bodies[-1]["keywordGroups"]]})
        with mock.patch.object(ps.urllib.request, "urlopen", opener), mock.patch.object(ps.time, "sleep", lambda s: None):
            got = ps.trend([f"말 {i}" for i in range(7)], ("id", "sec"), dt.date(2026, 10, 25), dt.date(2026, 11, 14))
        self.assertEqual([len(b["keywordGroups"]) for b in bodies], [5, 2])
        self.assertEqual(bodies[0]["keywordGroups"][0]["keywords"], ["말 0", "말0"])
        self.assertEqual(got["말 6"], {"2026-11-13": 1.5})

    def test_in_season_needs_a_real_peak_near_now(self):
        dec_peak = {m: 5.0 for m in range(1, 13)} | {12: 100.0, 1: 60.0}
        self.assertTrue(ps.in_season(dec_peak, dt.date(2026, 11, 14)))      # 다음 달이 꼭대기
        self.assertTrue(ps.in_season(dec_peak, dt.date(2026, 12, 3)))
        self.assertFalse(ps.in_season(dec_peak, dt.date(2026, 6, 1)))
        self.assertFalse(ps.in_season({m: 90.0 for m in range(1, 13)} | {11: 100.0}, dt.date(2026, 11, 14)))   # 일 년 내내 비슷하면 제철이 없다
        self.assertFalse(ps.in_season({}, dt.date(2026, 11, 14)))

    def test_seasons_asks_for_the_last_twelve_full_months(self):
        seen = {}
        def opener(req, timeout=0):
            seen.update(json.loads(req.data))
            return _Resp({"results": [{"title": "배당락일", "data": [{"period": "2025-12-01", "ratio": 100}, {"period": "2026-10-01", "ratio": 3}]}]})
        with mock.patch.object(ps.urllib.request, "urlopen", opener), mock.patch.object(ps.time, "sleep", lambda s: None):
            got = ps.seasons(["배당락일"], ("id", "sec"), dt.date(2026, 11, 14))
        self.assertEqual((seen["startDate"], seen["endDate"], seen["timeUnit"]), ("2025-11-01", "2026-10-31", "month"))
        self.assertEqual(got["배당락일"], {12: 100.0, 10: 3.0})

    def test_news_mode_lists_latest_and_needs_news_keys(self):
        rc, out, _ = self._run(["--news", "어떤 사건"], news={"어떤 사건": ([2, 5, 30], 77)})
        self.assertEqual(rc, 0)
        self.assertIn("어떤 사건: 지난 24시간 기사 2건 (전체 77건)", out)
        self.assertIn("press0.co.kr", out); self.assertIn("어떤 사건 기사 0", out); self.assertNotIn("<b>", out)
        rc, out, err = self._run(["--news", "어떤 사건"], env=PhraseSizeTest.AD)
        self.assertEqual(rc, 2)
        self.assertIn("NAVER_NEWS_CLIENT_ID", err)

    def test_official_mode_keeps_only_official_hosts(self):
        rc, out, _ = self._run(["--official", "연금저축 세액공제"], docs={"연금저축 세액공제": [
            ("https://www.nts.go.kr/a", "연금계좌 <b>세액공제</b> 안내"), ("https://blog.naver.com/x/1", "블로그 글"), ("https://www.hankyung.com/a", "기사"),
            ("https://open.krx.co.kr/b", "거래소"), ("https://www.fss.or.kr/c", "금감원"), ("https://notfss.or.kr.evil.com/d", "가짜")]})
        self.assertEqual(rc, 0)
        for host in ("nts.go.kr", "open.krx.co.kr", "fss.or.kr"):
            self.assertIn(host + "  ", out)
        for bad in ("blog.naver.com", "hankyung", "evil.com", "<b>"):
            self.assertNotIn(bad, out)

    def test_timing_failure_is_reported_but_does_not_block_the_pick(self):
        base = _fake(totals={"찾는 말": 5_000}, tool=[("찾는말", 300, 900)])
        def opener(req, timeout=0):
            if "/search/v1/news" in req.full_url or "/search-trend/" in req.full_url:
                raise ps.urllib.error.URLError("down")
            return base(req, timeout)
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, self.ENV, clear=True), mock.patch.object(ps, "KEY_FILE", ps.Path("/nonexistent/x.env")), \
                mock.patch.object(ps.urllib.request, "urlopen", opener), mock.patch.object(ps.time, "sleep", lambda s: None), redirect_stdout(out), redirect_stderr(err):
            rc = ps.main(["찾는 말"])
        self.assertEqual(rc, 3)
        self.assertIn("→ 고를 말: 찾는 말", out.getvalue())
        self.assertIn("기사 수: 찾는 말", err.getvalue()); self.assertIn("검색 추세", err.getvalue())

    def test_guide_topics_reads_the_routine_list(self):
        """가이드 지시문의 주제 줄 꼴이 바뀌면 `--guide`가 빈 목록으로 조용히 돌지 않게 — 실제 지시문에서 쉰 개 넘게 읽혀야 한다."""
        topics = ps.guide_topics()
        self.assertGreater(len(topics), 50)
        self.assertEqual(len({t["slug"] for t in topics}), len(topics))
        self.assertTrue(all(t["group"] and t["phrase"] for t in topics))

    def test_guide_orders_rising_then_in_season_then_the_rest(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            doc = ps.Path(d) / "g.md"
            doc.write_text("**A. 세금**\n- `written-one` — 이미 쓴 것 (쓴 말)\n- `plain-one` — 평범한 것 (평범한 말)\n"
                           "**C. 거래 규칙**\n- `season-one` — 제철인 것 (제철 말)\n- `hot-one` — 뜨는 것 (뜨는 말)\n", encoding="utf-8")
            (ps.Path(d) / "ko_written-one.json").write_text("{}", encoding="utf-8")
            months = lambda peak: {f"{2025 + (m < 11)}-{m:02d}-01": (100.0 if m == peak else 5.0) for m in range(1, 13)}   # noqa: E731
            days = {(dt.date(2026, 11, 14) - dt.timedelta(days=i)).isoformat(): 1.0 for i in range(2, 16)}
            def trend_for(body_unit_month):
                return ({"쓴 말": months(12), "평범한 말": months(6), "제철 말": months(12), "뜨는 말": months(6)} if body_unit_month
                        else {"평범한 말": {**days, "2026-11-13": 1.0}, "제철 말": {**days, "2026-11-13": 1.0}, "뜨는 말": {**days, "2026-11-13": 4.0}})
            daily, monthly = _fake(trend=trend_for(False)), _fake(trend=trend_for(True))
            base = _fake(totals={"평범한 말": 2_000, "제철 말": 80_000, "뜨는 말": 90_000},
                         tool=[("쓴말", 500, 500), ("평범한말", 900, 900), ("제철말", 700, 700), ("뜨는말", 800, 800)], news={})
            def opener(req, timeout=0):
                if "/search-trend/" in req.full_url:
                    return (monthly if json.loads(req.data)["timeUnit"] == "month" else daily)(req, timeout)
                return base(req, timeout)
            out, err = io.StringIO(), io.StringIO()
            with mock.patch.dict(os.environ, self.ENV, clear=True), mock.patch.object(ps, "KEY_FILE", ps.Path("/nonexistent/x.env")), \
                    mock.patch.object(ps, "GUIDE_DOC", doc), mock.patch.object(ps, "GUIDES", ps.Path(d)), \
                    mock.patch.object(ps.urllib.request, "urlopen", opener), mock.patch.object(ps.time, "sleep", lambda s: None), \
                    mock.patch.object(ps.dt, "datetime", _Clock), redirect_stdout(out), redirect_stderr(err):
                rc = ps.main(["--guide"])
        self.assertEqual((rc, err.getvalue()), (0, ""))
        lines = out.getvalue().splitlines()
        self.assertIn("남은 주제 3개", lines[0])
        self.assertEqual([line.rsplit("→ ", 1)[1] for line in lines[1:4]], ["hot-one", "season-one", "plain-one"])
        self.assertIn("검색 뜨는 중", lines[1]); self.assertTrue(lines[2].startswith("C 제철"))
        self.assertIn("이미 쓴 주제 가운데 지금이 제철인 것", lines[4]); self.assertIn("쓴 말(12월)", lines[4])


if __name__ == "__main__":
    unittest.main()
