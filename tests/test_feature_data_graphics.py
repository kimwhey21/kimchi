"""기준표·프리뷰 원고에서 시황용 데이터 그래픽을 `price_file`로 쓰는 경로(2026-09-08).

사용자가 "오늘 밤 프리뷰에는 적용이 안 되는가"라고 물었다. 프리뷰는 기준표 파이프라인을
쓰므로 시세가 원고에 없다 — 그래서 그래픽 지정에 시세 파일 경로를 적게 했다.
소제목 32자 상한도 기준표·프리뷰에 같이 건다.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import data_graphics, feature_checks, publish_feature

HISTORY = {"dates": [f"2026-08-{d:02d}" for d in range(1, 29)] + ["2026-09-03", "2026-09-04"],
           "close": [7500 + i * 5 for i in range(30)]}
PRICE = {"macro": {"^GSPC": {"ticker": "^GSPC", "name": "S&P500", "price": 7718.6,
                             "change_pct": -0.38, "unit": "", "history": HISTORY}},
         "watchlist": {}, "trading_date": "2026-09-04"}


@unittest.skipUnless(data_graphics.has_korean_font(), "한글 폰트가 없어 렌더를 건너뜁니다")
class PriceFileGraphicsTest(unittest.TestCase):
    def _doc(self, spec: dict) -> dict:
        return {"kind": "feature", "series": "프리뷰", "graphics": [spec]}

    def test_data_graphic_renders_from_price_file(self) -> None:
        price_path = Path(tempfile.mkdtemp()) / "price_us_2026-09-04.json"
        price_path.write_text(json.dumps(PRICE), encoding="utf-8")
        spec = {"kind": "price_history", "section": 1, "price_file": str(price_path),
                "args": {"ticker": "^GSPC", "title": "S&P500, 최근 3개월"}, "alt": "S&P500 3개월"}
        with patch.object(publish_feature, "ROOT", Path("/")):
            images, figures, cover = publish_feature._build_graphics(self._doc(spec), Path(tempfile.mkdtemp()))
        self.assertEqual(len(images), 1)
        self.assertIn(1, figures)
        self.assertTrue(Path(images[0]["local_path"]).exists())

    def test_data_graphic_without_price_file_is_rejected(self) -> None:
        spec = {"kind": "price_history", "section": 1, "args": {"ticker": "^GSPC"}}
        with self.assertRaises(ValueError) as caught:
            publish_feature._build_graphics(self._doc(spec), Path(tempfile.mkdtemp()))
        self.assertIn("price_file", str(caught.exception))


class FeatureHeadingLengthTest(unittest.TestCase):
    def test_long_heading_is_reported(self) -> None:
        doc = {"kind": "feature", "series": "프리뷰",
               "ko": {"title": "오늘 밤 미국장, 유가 6주 최고치가 반도체 랠리를 흔들까?",
                      "narrative": [{"heading": "1. 오늘 밤 일정 — 예정된 지표보다 이미 벌어진 사건, 그리고 그 뒤에 남은 것", "body": "9월 8일."},
                                    {"heading": "2. 가격대", "body": "b"}, {"heading": "3. 확인할 것 셋", "body": "c"}],
                      "closing": {"body": ""}}}
        issues = feature_checks.collect_issues(doc, graphics=3)
        self.assertTrue(any("소제목 1" in i and "32자" in i for i in issues), issues)

    def test_preview_needs_three_visuals(self) -> None:
        doc = {"kind": "feature", "series": "프리뷰",
               "ko": {"title": "t", "narrative": [{"heading": f"{i}. 절", "body": "9월 8일."} for i in range(1, 4)],
                      "closing": {"body": ""}}}
        self.assertTrue(any("시각자료" in i for i in feature_checks.collect_issues(doc, graphics=2)))
        self.assertFalse(any("시각자료" in i for i in feature_checks.collect_issues(doc, graphics=3)))


if __name__ == "__main__":
    unittest.main()
