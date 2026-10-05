"""값 수준·판단 낱말·금리 %p 대조(2026-10-06, 감사 F-031·F-035) — 지난 원고 전부에 돌려 맞는 글은 9/1 환율 하나만 걸렸다."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from src import data_graphics, editorial_facts as ef

PD = {"macro": {"CL=F": {"name": "WTI 원유", "price": 91.11, "change_pct": -1.9},
                "^DJI": {"name": "다우존스", "price": 51176.96, "change_pct": -0.68},
                "^TNX": {"name": "美 10년물 금리", "price": 5.11, "change_pct": 3.04, "unit": "%"}},
      "watchlist": {"INTC": {"name": "인텔", "price": 116.19, "change_pct": -2.63}}}


def _doc(body: str) -> dict:
    return {"title": "t", "narrative": [{"heading": "h", "body": body}]}


class LevelTest(unittest.TestCase):
    def test_wrong_levels_are_caught(self) -> None:
        bad = _doc("WTI 원유는 1.73% 하락한 배럴당 91.26달러였습니다. 다우존스는 1.03% 하락한 51,511.59로 마감했습니다.")
        self.assertEqual(len(ef.level_issues(bad, PD)), 2)

    def test_right_or_other_numbers_pass(self) -> None:
        ok = _doc("WTI 원유는 1.90% 하락한 배럴당 91.11달러였습니다. 다우존스는 0.68% 하락한 51,176.96로 마감했습니다. "
                  "국제유가가 배럴당 100달러를 넘었던 지난주와 다릅니다. 10년물 금리는 장중 5.34%까지 올랐습니다. "
                  "10년물 금리가 5.18%를 넘어 더 오르는지 봅니다. 미 10년물 국채금리도 5.28%에서 5.11%로 더 올랐습니다.")   # 10/6 오탐
        self.assertEqual(ef.level_issues(ok, PD), [])

    def test_judgment_words(self) -> None:
        self.assertEqual(len(ef.judgment_word_issues(_doc("인텔은 급등했습니다."), PD)), 1)
        self.assertEqual(ef.judgment_word_issues(_doc("인텔은 급락했습니다. 인텔은 최근 며칠 급등 뒤 되돌림을 겪었습니다."), PD), [])

    def test_yield_change_must_be_points(self) -> None:
        self.assertEqual(len(ef.yield_change_issues(_doc("10년물 국채금리는 3.04% 올라 5.11%를 기록했습니다."), PD)), 1)
        self.assertEqual(ef.yield_change_issues(_doc("10년물 국채금리는 0.15%p 올라 5.11%를 기록했습니다."), PD), [])
        en = {"title": "t", "narrative": [{"heading": "h", "body": "the 10-year yield climbed to 5.11% as WTI crude jumped 3.16%"}]}
        self.assertEqual(ef.yield_change_issues(en, PD, "en"), [])

    def test_cards_show_points_for_yields(self) -> None:
        self.assertEqual(data_graphics.change_label({"unit": "%", "price": 5.11, "change_pct": 3.04}), "+0.15%p")
        self.assertEqual(data_graphics.change_label({"price": 51176.96, "change_pct": -0.68}), "-0.68%")

    def test_internal_names_are_blocked(self) -> None:
        self.assertEqual(len(ef.internal_name_issues(_doc("story_engines 계절성 엔진에 따르면 9월은 평균 0.30% 올랐습니다."))), 2)
        self.assertEqual(ef.internal_name_issues(_doc("야후 파이낸스 월봉으로 세면 9월은 평균 0.40% 올랐습니다.")), [])

    def test_past_manuscripts_only_flag_real_mismatches(self) -> None:
        """지난 시황 원고 전부: 값 수준·판단 낱말은 9/1 원/달러(1,372.70원 vs 시세 1,373.4원) 두 자리만 걸린다."""
        root = Path(__file__).resolve().parents[1] / "editorial"
        found = []
        for path in sorted(list(root.glob("kr_2026-*.json")) + list(root.glob("us_2026-*.json"))):
            doc = json.loads(path.read_text(encoding="utf-8"))
            if "price_data" not in doc or path.stem > "us_2026-10-05" and path.stem.startswith("us") or path.stem > "kr_2026-10-05" and path.stem.startswith("kr"):
                continue   # 10/6부터는 관문이 막는다 — 고정 대상은 그전 원고
            for lang in ("ko", "en"):
                if doc.get(lang):
                    found += [(path.stem, x) for x in ef.level_issues(doc[lang], doc["price_data"], lang)
                              + ef.judgment_word_issues(doc[lang], doc["price_data"], lang)]
        self.assertEqual({stem for stem, _ in found}, {"kr_2026-09-01"}, found)


if __name__ == "__main__":
    unittest.main()
