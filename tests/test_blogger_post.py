"""블로그스팟 렌더(scripts/blogger_post.py)가 원고를 빠짐없이, 브랜드 규칙대로 HTML로 옮기는지 (2026-09-25)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import blogger_post

ROOT = Path(__file__).resolve().parents[1]
MAGAZINE = ROOT / "tests" / "fixtures" / "magazine_sample.json"


class BloggerPostTest(unittest.TestCase):
    def test_magazine_keeps_every_section_and_uses_purplesum_footer(self):
        doc = json.loads(MAGAZINE.read_text(encoding="utf-8"))
        result = blogger_post.render(MAGAZINE, None, upload=False)
        for section in doc["ko"]["narrative"]:
            self.assertIn(blogger_post._esc(section["heading"]), result["html"])
        self.assertIn(blogger_post.NAVER_MAGAZINE, result["html"])
        self.assertNotIn("페르마타", result["html"])          # 잡지 글 어디에도 페르마타가 나가면 안 된다(2026-09-13)
        self.assertNotIn("fermata", result["html"].lower())
        self.assertEqual(result["labels"][0], "매거진")
        self.assertIn(doc["featured_photo"]["url"].split("?")[0], result["html"])   # 표지는 원본 주소
        self.assertRegex(result["slug"], r"^[a-z0-9-]+$")
        self.assertEqual(result["unresolved"], [])

    def test_guide_gets_fermata_footer_stock_links_and_kicker(self):
        doc = {
            "kind": "feature", "series": "가이드", "date": "2026-09-20", "checked": "2026-09-20",
            "slug": "why-samsung-moves-with-kospi", "tags": [],
            "ko": {"title": "삼성전자는 왜 코스피와 같이 움직일까",
                   "narrative": [{"heading": "1. 비중이 답이다", "body": "삼성전자는 코스피 시가총액 1위입니다. 지수와 같은 방향으로 움직이는 날이 많습니다."},
                                 {"heading": "2. SK하이닉스도 마찬가지", "body": "SK하이닉스는 두 번째로 큽니다. 둘이 합쳐 지수의 큰 몫입니다."}],
                   "closing": {"body": "비중을 먼저 봅니다.", "check": {"what": "다음 달 시가총액 비중"}}},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ko_why-samsung-moves-with-kospi.json"
            path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            result = blogger_post.render(path, None, upload=False)
        self.assertIn("가이드 · 2026년 9월 20일 확인", result["html"])
        self.assertIn(blogger_post.NAVER_FERMATA, result["html"])
        self.assertIn(blogger_post.TELEGRAM, result["html"])
        self.assertIn("/stocks/samsung-electronics/", result["html"])
        self.assertIn("/stocks/sk-hynix/", result["html"])
        self.assertIn("삼성전자", result["labels"])
        self.assertEqual(result["labels"][0], "가이드")
        self.assertIn(blogger_post.DISCLAIMER, result["html"])
        self.assertNotIn("<h2>1. ", result["html"])           # 절 번호는 네이버와 같이 뗀다

    def test_labels_never_carry_commas(self):
        self.assertNotIn(",", "".join(blogger_post.labels({"series": "매거진", "group": "돈의, 상식"}, [])))


if __name__ == "__main__":
    unittest.main()
