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


def _fake(totals=None, pages=None):
    """query → total, 또는 (query, start) → items."""
    def opener(req, timeout=0):
        from urllib.parse import parse_qs, urlparse
        q = parse_qs(urlparse(req.full_url).query)
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

    def test_main_sorts_narrow_first_and_never_prints_keys(self):
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"NAVER_CLIENT_ID": "id", "NAVER_CLIENT_SECRET": "sec"}), \
                mock.patch.object(ps.urllib.request, "urlopen", _fake(totals={"넓은 말": 900_000, "좁힌 말": 1_200})), redirect_stdout(out):
            self.assertEqual(ps.main(["넓은 말", "좁힌 말"]), 0)
        lines = out.getvalue().splitlines()
        self.assertTrue(lines[0].startswith("좁음") and "좁힌 말" in lines[0])
        self.assertTrue(lines[1].startswith("넓음"))
        self.assertIn("→ 좁은 말: 좁힌 말", lines[2])
        self.assertNotIn("sec", out.getvalue())

    def test_main_says_so_when_nothing_is_narrow(self):
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"NAVER_CLIENT_ID": "id", "NAVER_CLIENT_SECRET": "sec"}), \
                mock.patch.object(ps.urllib.request, "urlopen", _fake(totals={"큰 말": 50_000})), redirect_stdout(out):
            ps.main(["큰 말"])
        self.assertIn("좁은 말이 없습니다", out.getvalue())

    def test_failed_phrase_is_counted_not_swallowed(self):
        def boom(req, timeout=0):
            raise ps.urllib.error.URLError("down")
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, {"NAVER_CLIENT_ID": "id", "NAVER_CLIENT_SECRET": "sec"}), \
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
