"""원고 숫자를 시세와 대조하는 검사입니다.

형식 검사(editorial_quality)가 통과시킨 두 가지를 여기서 잡습니다 — 시세와
다른 등락률, 그리고 그날 가장 크게 움직인 종목을 아예 다루지 않은 원고.
"""
from __future__ import annotations

import unittest

from src.editorial_facts import EditorialFactError, collect_issues, validate

PRICE_DATA = {
    "macro": {
        "KS11": {"ticker": "KS11", "name": "코스피", "name_en": "KOSPI",
                  "price": 6687.21, "change_pct": 1.64, "unit": ""},
        "KQ11": {"ticker": "KQ11", "name": "코스닥", "name_en": "KOSDAQ",
                  "price": 813.5, "change_pct": -1.71, "unit": ""},
        "USD/KRW": {"ticker": "USD/KRW", "name": "원/달러 환율", "name_en": "USD/KRW",
                     "price": 1351.3, "change_pct": -0.53, "unit": "원"},
        "^TNX": {"ticker": "^TNX", "name": "美 10년물 금리", "name_en": "US 10-Year Treasury Yield",
                  "price": 4.761, "change_pct": -0.71, "unit": "%"},
    },
    "watchlist": {
        "010140": {"ticker": "010140", "name": "삼성중공업", "name_en": "Samsung Heavy Industries",
                    "price": 21650.0, "change_pct": 8.58, "source": "dynamic"},
        "005930": {"ticker": "005930", "name": "삼성전자", "name_en": "Samsung Electronics",
                    "price": 250000.0, "change_pct": -0.2, "source": "core"},
        "086520": {"ticker": "086520", "name": "에코프로", "name_en": "Ecopro",
                    "price": 81700.0, "change_pct": -0.37, "source": "core"},
        "247540": {"ticker": "247540", "name": "에코프로비엠", "name_en": "Ecopro BM",
                    "price": 106500.0, "change_pct": 0.19, "source": "core"},
    }
}


def _doc(body: str, **extra) -> dict:
    doc = {
        "title": "삼성중공업이 8.58% 올랐습니다",
        "narrative": [{"heading": "소제목", "body": body}],
        "stock_section": {"featured_tickers": ["010140"], "commentary": ""},
    }
    doc.update(extra)
    return doc


class QuotedNumberTest(unittest.TestCase):
    def test_matching_numbers_pass(self) -> None:
        doc = _doc("삼성중공업이 8.58% 올라 21,650원으로 마감했습니다. 삼성전자는 0.20% 내렸습니다.")
        self.assertEqual(collect_issues(doc, PRICE_DATA), [])

    def test_wrong_number_fails(self) -> None:
        doc = _doc("삼성중공업이 12.34% 올라 마감했습니다.")
        issues = collect_issues(doc, PRICE_DATA)
        self.assertEqual(len(issues), 1)
        self.assertIn("12.34", issues[0])
        self.assertIn("8.58", issues[0])
        with self.assertRaises(EditorialFactError):
            validate(doc, PRICE_DATA)

    def test_intraday_quote_is_allowed(self) -> None:
        """장중 인용은 종가와 달라야 정상입니다 — 이걸 막으면 검사가 쓸모없어집니다."""
        doc = _doc(
            "CBC뉴스는 오전 9시 44분 기준으로 삼성중공업 1.55% 상승을 전했습니다. "
            "다만 같은 시각의 수치이고 종가는 다릅니다."
        )
        self.assertEqual(collect_issues(doc, PRICE_DATA), [])

    def test_ownership_ratio_is_not_a_move(self) -> None:
        doc = _doc("삼성중공업이 8.58% 올랐습니다. 삼성전자 외국인 보유율은 46.69%입니다.")
        self.assertEqual(collect_issues(doc, PRICE_DATA), [])

    def test_rounded_figure_is_skipped(self) -> None:
        """'5%대 상승' 같은 어림수는 원고에서 정상입니다."""
        doc = _doc("삼성중공업이 8.58% 올랐고 삼성전자는 1%대 하락했습니다.")
        self.assertEqual(collect_issues(doc, PRICE_DATA), [])

    def test_longer_name_wins(self) -> None:
        """'에코프로비엠'을 '에코프로'로 읽으면 멀쩡한 원고가 실패합니다."""
        doc = _doc("삼성중공업이 8.58% 올랐습니다. 에코프로비엠은 0.19% 오르고 에코프로는 0.37% 내렸습니다.")
        self.assertEqual(collect_issues(doc, PRICE_DATA), [])

    def test_does_not_borrow_a_number_from_the_next_sentence(self) -> None:
        """이름 뒤 창이 다음 문장까지 넘어가면 남의 숫자를 가져옵니다."""
        doc = _doc(
            "삼성중공업이 8.58% 올랐다. 에코프로와 삼성전자가 뒤를 이었다. "
            "코스닥 장비주도 심텍 4.78% 하락으로 밀렸다."
        )
        self.assertEqual(collect_issues(doc, PRICE_DATA), [])

    def test_does_not_borrow_a_number_from_the_next_stock(self) -> None:
        doc = _doc("삼성중공업이 8.58% 올랐고 삼성전자와 에코프로비엠은 0.19% 상승했다.")
        # '삼성전자' 뒤 숫자는 '에코프로비엠'의 것이므로 삼성전자에 붙이지 않습니다.
        self.assertEqual(collect_issues(doc, PRICE_DATA), [])

    def test_previous_day_quote_is_allowed(self) -> None:
        """이틀을 비교하는 서술은 오늘 종가와 달라야 정상입니다."""
        doc = _doc(
            "삼성중공업이 8.58% 올랐습니다. 삼성전자는 어제 3.45% 올랐다가 오늘 0.20% 내렸습니다."
        )
        self.assertEqual(collect_issues(doc, PRICE_DATA), [])

    def test_english_names_are_checked(self) -> None:
        doc = {
            "title": "Samsung Heavy Industries rose 8.58%",
            "narrative": [{"heading": "h", "body": "Samsung Electronics fell 9.99% on the day."}],
            "stock_section": {"featured_tickers": ["010140"], "commentary": ""},
        }
        issues = collect_issues(doc, PRICE_DATA, lang="en")
        self.assertEqual(len(issues), 1)
        self.assertIn("9.99", issues[0])


class LeadStockCoverageTest(unittest.TestCase):
    def test_missing_biggest_mover_fails(self) -> None:
        """2026-09-02 미국장 원고가 델(+15.81%)을 빠뜨린 것과 같은 형태입니다."""
        doc = {
            "title": "지수는 소폭 올랐습니다",
            "narrative": [{"heading": "h", "body": "삼성전자는 0.20% 내렸습니다."}],
            "stock_section": {"featured_tickers": ["005930"], "commentary": ""},
        }
        issues = collect_issues(doc, PRICE_DATA)
        self.assertEqual(len(issues), 1)
        self.assertIn("삼성중공업", issues[0])

    def test_ticker_in_cards_counts_as_covered(self) -> None:
        doc = {
            "title": "지수는 소폭 올랐습니다",
            "narrative": [{"heading": "h", "body": "삼성전자는 0.20% 내렸습니다."}],
            "stock_section": {"featured_tickers": ["010140", "005930"], "commentary": ""},
        }
        self.assertEqual(collect_issues(doc, PRICE_DATA), [])

    def test_small_moves_are_not_required(self) -> None:
        """1% 미만이면 그날의 주인공이라 부르기 어렵습니다."""
        quiet = {
            "watchlist": {
                "005930": {"ticker": "005930", "name": "삼성전자", "name_en": "Samsung Electronics",
                            "price": 250000.0, "change_pct": -0.2},
            }
        }
        doc = {"title": "조용한 하루였습니다", "narrative": [{"heading": "h", "body": "지수는 보합이었습니다."}]}
        self.assertEqual(collect_issues(doc, quiet), [])


class MacroNumberTest(unittest.TestCase):
    """지수·환율 등락률도 대조합니다.

    2026-09-04 한국장 원고가 원/달러를 두 군데 모두 -0.58%로 적었는데(시세 -0.53%)
    검사를 통과했습니다. 워치리스트 종목만 보고 있었기 때문입니다.
    """

    def test_wrong_fx_move_fails(self) -> None:
        doc = _doc("삼성중공업이 8.58% 올랐습니다. 원/달러는 0.58% 내린 1,351.3원으로 마감했습니다.")
        issues = collect_issues(doc, PRICE_DATA)
        self.assertEqual(len(issues), 1)
        self.assertIn("원/달러", issues[0])
        self.assertIn("0.53", issues[0])

    def test_correct_fx_move_passes(self) -> None:
        doc = _doc("삼성중공업이 8.58% 올랐습니다. 원/달러는 0.53% 내린 1,351.3원으로 마감했습니다.")
        self.assertEqual(collect_issues(doc, PRICE_DATA), [])

    def test_index_bullet_line_is_checked(self) -> None:
        doc = _doc("삼성중공업이 8.58% 올랐습니다.\n\n코스피 6,687.21 +1.64%")
        self.assertEqual(collect_issues(doc, PRICE_DATA), [])

    def test_index_as_a_modifier_is_not_a_move(self) -> None:
        """'코스닥 장비주도 심텍 4.78%'의 4.78%는 심텍의 것입니다."""
        doc = _doc(
            "삼성중공업이 8.58% 올랐습니다. "
            "코스닥 장비주도 심텍 4.78%, 원익IPS 4.28% 하락으로 나란히 밀렸다."
        )
        self.assertEqual(collect_issues(doc, PRICE_DATA), [])

    def test_yield_level_is_not_read_as_a_move(self) -> None:
        """금리는 수준을 퍼센트로 적습니다 — 등락률로 읽으면 멀쩡한 문장이 걸립니다."""
        doc = _doc("삼성중공업이 8.58% 올랐습니다. 美 10년물 금리는 4.761% 수준으로 내렸습니다.")
        self.assertEqual(collect_issues(doc, PRICE_DATA), [])

    def test_macro_never_becomes_the_lead(self) -> None:
        """지수가 종목보다 크게 움직여도 '그날의 주인공'은 종목입니다."""
        loud = {
            "macro": {"KQ11": {"ticker": "KQ11", "name": "코스닥", "name_en": "KOSDAQ",
                                "price": 813.5, "change_pct": -30.0, "unit": ""}},
            "watchlist": PRICE_DATA["watchlist"],
        }
        doc = _doc("삼성중공업이 8.58% 올랐습니다.")
        self.assertEqual(collect_issues(doc, loud), [])


if __name__ == "__main__":
    unittest.main()
