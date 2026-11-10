"""scripts.phrase_size — 검색되는 말의 경쟁 글 수·띠·순위. 바깥 호출은 전부 가짜로 막는다."""
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


def _fake(totals=None, pages=None, tool=None):
    """블로그 검색: query → total, (query, start) → items. 키워드 도구: tool = [(relKeyword, pc, mobile)]."""
    def opener(req, timeout=0):
        from urllib.parse import parse_qs, urlparse
        u = urlparse(req.full_url)
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


if __name__ == "__main__":
    unittest.main()
