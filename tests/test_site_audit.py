"""본진 화면 확인 (2026-09-26) — 영어 시황의 빈 그림, 종목 페이지의 본진 주소 링크."""
import json
import tempfile
import unittest
from pathlib import Path

from scripts import site_audit


class _Resp:
    def __init__(self, text: str, status: int = 200):
        self.text, self.status_code = text, status


class EnglishTest(unittest.TestCase):
    def _root(self, tmp: str) -> Path:
        root = Path(tmp)
        (root / "editorial").mkdir()
        doc = {"market": "us", "date": "2026-09-29", "en": {"narrative": [{"graphic": {"kind": "number_cards"}},
                                                                         {"graphic": {"kind": "price_history"}}]}}
        (root / "editorial" / "us_2026-09-29.json").write_text(json.dumps(doc), encoding="utf-8")
        return root

    def test_empty_figures_are_problems(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            html = '<img class="mb-figure" src="" alt=""><img class="mb-figure" src="" alt="">'
            problems = site_audit.english_problems(self._root(tmp), get=lambda u: _Resp(html))
        self.assertEqual(len(problems), 2, problems)

    def test_drawn_figures_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            html = '<img class="mb-figure" src="https://x/a.png"><img class="mb-figure" src="https://x/b.png">'
            self.assertEqual(site_audit.english_problems(self._root(tmp), get=lambda u: _Resp(html)), [])


class StocksTest(unittest.TestCase):
    def test_links_to_private_posts_are_problems(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            (root / "config" / "stock_pages.yaml").write_text("kr:\n  - {ticker: '005930', slug: samsung-electronics}\n",
                                                              encoding="utf-8")
            bad = '<h2>이 종목이 나온 글</h2><a href="https://fermata.it.kr/editorial-kr-2026-09-23-ko/">x</a>'
            good = '<h2>이 종목이 나온 글</h2><a href="https://blog.naver.com/fermata49/1">x</a><a href="https://fermata.it.kr/stocks/">목록</a>'
            self.assertEqual(len(site_audit.stock_problems(root, get=lambda u: _Resp(bad))), 1)
            self.assertEqual(site_audit.stock_problems(root, get=lambda u: _Resp(good)), [])


if __name__ == "__main__":
    unittest.main()
