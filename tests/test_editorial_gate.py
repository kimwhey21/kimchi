"""커밋 전 관문(editorial_gate)과 발행 단계의 경고 전환(2026-09-08).

사용자: "발행을 멈추게 하지 말고 제목을 제대로 쓰게 해, 처음부터." 그래서
- 관문은 문체·구조·제목·숫자·시각자료를 **루틴이 커밋하기 전에** 막고,
- 발행(publish_editorial)은 같은 문체·제목·구조 문제를 경고로만 남기며,
- 숫자 대조(editorial_facts)만 발행에서도 막는다.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import data_graphics, editorial_gate, publish_editorial

HISTORY = {"dates": [f"2026-08-{d:02d}" for d in range(1, 29)] + ["2026-09-01", "2026-09-02"],
           "close": [6500 + i * 10 for i in range(30)]}

PRICE = {
    "macro": {
        "KS11": {"ticker": "KS11", "name": "코스피", "price": 6790.0, "change_pct": -0.58,
                 "unit": "", "series": [6700, 6790], "history": HISTORY},
        "KQ11": {"ticker": "KQ11", "name": "코스닥", "price": 811.88, "change_pct": -1.25,
                 "unit": "", "series": [820, 811.88]},
    },
    "watchlist": {
        "005930": {"ticker": "005930", "name": "삼성전자", "name_en": "Samsung Electronics",
                   "sector": "반도체", "price": 269500, "change_pct": -0.19,
                   "series": [270000, 269500], "history": HISTORY, "source": "core"},
        "047040": {"ticker": "047040", "name": "대우건설", "name_en": "Daewoo E&C",
                   "price": 19970, "change_pct": 8.47, "series": [18410, 19970],
                   "history": HISTORY, "source": "dynamic"},
    },
    "trading_date": "2026-09-08",
}


def _sections(n: int) -> list[dict]:
    return [{"heading": f"{i}. 절 {i}", "body": "본문입니다."} for i in range(1, n + 1)]


def _doc(title: str, sections: list[dict]) -> dict:
    return {"market": "kr", "date": "2026-09-08", "price_data": PRICE,
            "ko": {"title": title, "narrative": sections,
                   "closing": {"heading": "Fermata's Take",
                               "body": "우리는 이번 하락을 숨 고르기로 봅니다. 외국인이 닷새째 순매수인데 지수가 밀린 것은 개인의 차익 실현 때문이었습니다. 9월 10일 종가가 7,000선을 넘는지로 확인하겠습니다.",
                               "check": {"due": "2026-09-10", "what": "코스피 종가가 7,000선을 넘는지, 외국인 순매수가 이어지는지"}}}}


def _write(doc: dict) -> Path:
    path = Path(tempfile.mkdtemp()) / "kr_2026-09-08.json"
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return path


@unittest.skipUnless(data_graphics.has_korean_font(), "한글 폰트가 없어 렌더를 건너뜁니다")
class GateTest(unittest.TestCase):
    def _run(self, doc: dict):
        return editorial_gate.run(_write(doc), render_dir=Path(tempfile.mkdtemp()))

    def test_numbered_title_and_thin_body_fail(self) -> None:
        issues, _ = self._run(_doc("대우건설 8.47% 급등, 삼성전기 5.78% 급락. 코스피가 0.58% 하락한 이유.",
                                   _sections(6)))
        joined = "\n".join(issues)
        self.assertIn("제목·소제목 —", joined)
        self.assertIn("등락률이 둘 이상", joined)
        self.assertIn("절이 6개", joined)
        self.assertIn("시각자료 —", joined)

    def test_good_manuscript_passes_and_renders(self) -> None:
        sections = _sections(10)
        sections[0]["graphic"] = {"kind": "number_cards", "tickers": ["KS11", "KQ11"]}
        sections[1]["graphic"] = {"kind": "price_history", "ticker": "KS11", "guide": 7000, "guide_label": "7,000선"}
        sections[2]["graphic"] = {"kind": "price_history", "ticker": "047040"}
        sections[3]["graphic"] = {"kind": "investor_flows", "values": {"외국인": 6482, "개인": -13333},
                                  "source": "아시아경제 마감 집계"}
        sections[4]["photo"] = {"ticker": "005930"}
        issues, summary = self._run(_doc("대우건설이 이틀째 오른 날, 코스피는 7,000선을 넘지 못했습니다", sections))
        self.assertEqual(issues, [], issues)
        self.assertTrue(any("시각자료 5개" in line for line in summary), summary)

    def test_wrong_ticker_and_dynamic_photo_are_caught(self) -> None:
        sections = _sections(10)
        sections[0]["graphic"] = {"kind": "price_history", "ticker": "999999"}
        sections[1]["photo"] = {"ticker": "047040"}   # 동적 편입 → 풀 사진 없음
        issues, _ = self._run(_doc("코스피, 7,000선을 넘지 못했습니다", sections))
        joined = "\n".join(issues)
        self.assertIn("그래픽(본문 1", joined)
        self.assertIn("사진(본문 2", joined)

    def test_investor_flows_needs_a_source(self) -> None:
        sections = _sections(10)
        sections[0]["graphic"] = {"kind": "investor_flows", "values": {"외국인": 1}}
        issues, _ = self._run(_doc("코스피, 7,000선을 넘지 못했습니다", sections))
        self.assertTrue(any("source" in i for i in issues), issues)


class PublishWarnsInsteadOfBlockingTest(unittest.TestCase):
    """발행 단계: 문체·제목·구조는 경고, 숫자 대조는 차단."""

    def test_style_issues_become_warnings(self) -> None:
        ko = {"title": "대우건설 8.47% 급등, 삼성전기 5.78% 급락. 코스피가 0.58% 하락한 이유.",
              "narrative": _sections(6), "closing": {"body": ""}}
        warnings = publish_editorial._style_warnings(ko, None, PRICE)
        self.assertTrue(any("등락률이 둘 이상" in w for w in warnings))
        self.assertTrue(any("8개 이상" in w for w in warnings))

    def test_section_photo_from_pool_and_dynamic_skip(self) -> None:
        narrative = [{"heading": "1. a", "body": "b", "photo": {"ticker": "005930"}},
                     {"heading": "2. a", "body": "b", "photo": {"ticker": "047040"}},
                     {"heading": "3. a", "body": "b", "photo": {"url": "https://images.unsplash.com/x",
                                                                 "alt": "직접 본 사진"}}]
        with patch("src.publish_wordpress.is_configured", return_value=False):
            used = publish_editorial._attach_section_photos(narrative, PRICE, "2026-09-08", upload=False)
        self.assertTrue(narrative[0]["photo"] and narrative[0]["photo"]["id"] in used)
        self.assertIsNone(narrative[1]["photo"])
        self.assertEqual(narrative[2]["photo"]["url"], "https://images.unsplash.com/x")


if __name__ == "__main__":
    unittest.main()
