"""2026-09-25 검증에서 나온 세 구멍을 고정합니다.

① `ko.title_candidates`의 숫자가 대조되지 않아 'SK스퀘어가 … 5% 넘게 오른 이유'(실제 3.88%)가
   통과했다 — 후보도 제목과 같은 자리로 보고, 제목류에 한해 어림수 경계("5% 넘게"·"5%대")를 본다.
② 프리뷰에는 숫자 대조가 없었고, 그대로 붙이면 밸류에이션 문장(목표주가 대비·52주 고점 대비·PER·
   프리마켓·%포인트)이 걸렸다(9/22 8건·9/23 4건 실측) — 그 문맥은 창 안에서 건너뛴다.
③ 프리뷰 진입점 `collect_issues_for_preview`: 미국장 전일 파일은 1위 종목까지, 한국장 당일 파일은
   숫자만. 프리뷰의 "어제"는 미국장 파일의 날이라 건너뛰지 않는다.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.editorial_facts import (
    EditorialFactError,
    collect_issues,
    collect_issues_for_preview,
    preview_price_files,
    validate_preview,
)


def _entry(ticker, name, name_en, pct, source="core", unit=""):
    return {"ticker": ticker, "name": name, "name_en": name_en, "price": 100.0,
            "change_pct": pct, "source": source, "unit": unit}


PRICE_US = {
    "trading_date": "2026-09-16",
    "macro": {
        "^GSPC": _entry("^GSPC", "S&P500", "S&P 500", 0.50),
        "^TNX": _entry("^TNX", "美 10년물 금리", "US 10-Year Treasury Yield", -0.71, unit="%"),
    },
    "watchlist": {
        "DE": _entry("DE", "디어", "Deere", -2.13),
        "INTC": _entry("INTC", "인텔", "Intel", 12.14),
        "MU": _entry("MU", "마이크론", "Micron", 2.77),
        "NVDA": _entry("NVDA", "엔비디아", "NVIDIA", 2.30),
        "AAPL": _entry("AAPL", "애플", "Apple", 0.85),
        "CL=F": _entry("CL=F", "WTI 원유", "WTI Crude Oil", 8.25),
        # 이 표본에서 1위 종목은 Lumentum이어야 합니다(인텔 12.14보다 큰 값).
        "LITE": _entry("LITE", "Lumentum", "Lumentum", 13.20, source="dynamic"),
    },
}

PRICE_KR = {
    "trading_date": "2026-09-17",
    "macro": {"KS11": _entry("KS11", "코스피", "KOSPI", 0.90)},
    "watchlist": {
        "402340": _entry("402340", "SK스퀘어", "SK Square", 3.88, source="dynamic"),
        "005930": _entry("005930", "삼성전자", "Samsung Electronics", 3.24),
        "347700": _entry("347700", "스피어", "스피어", 16.95, source="dynamic"),
    },
}


def _ko(body: str = "삼성전자가 3.24% 올랐고 스피어는 16.95% 뛰었습니다.", **extra) -> dict:
    doc = {"title": "코스피, 장중 7,153까지 올랐다가 왜 밀렸을까요",
           "narrative": [{"heading": "소제목", "body": body}]}
    doc.update(extra)
    return doc


class TitleCandidateTest(unittest.TestCase):
    """① 후보의 숫자도 독자에게 나갈 수 있는 숫자입니다."""

    def test_candidate_with_wrong_floor_bound_is_flagged(self) -> None:
        doc = _ko(title_candidates=["코스피, 장중 7,153까지 올랐다가 왜 밀렸을까요",
                                    "SK스퀘어가 특별한 재료 없이 5% 넘게 오른 진짜 이유"])
        issues = collect_issues(doc, PRICE_KR)
        self.assertEqual(len(issues), 1, issues)
        self.assertIn("제목 후보 2", issues[0])
        self.assertIn("5% 넘게", issues[0])
        self.assertIn("3.88", issues[0])

    def test_candidate_with_true_bounds_passes(self) -> None:
        for phrase in ("3%대 오른", "3% 넘게 오른", "3% 이상 오른", "2%대 넘게 오른"):
            doc = _ko(title_candidates=[f"SK스퀘어가 특별한 재료 없이 {phrase} 진짜 이유"])
            self.assertEqual(collect_issues(doc, PRICE_KR), [], phrase)

    def test_wrong_band_is_flagged(self) -> None:
        doc = _ko(title_candidates=["SK스퀘어가 특별한 재료 없이 5%대 오른 진짜 이유"])
        issues = collect_issues(doc, PRICE_KR)
        self.assertEqual(len(issues), 1, issues)
        self.assertIn("5%대", issues[0])

    def test_band_followed_by_floor_word_means_floor(self) -> None:
        """'5%대 넘게'는 글쓴이 뜻이 '5 초과'입니다 — 7.4%면 맞고 3.88%면 틀립니다."""
        seven = {**PRICE_KR, "watchlist": {"402340": _entry("402340", "SK스퀘어", "SK Square", 7.40)}}
        doc = _ko("SK스퀘어가 크게 올랐고 스피어도 뛰었습니다.",   # 두 표본 모두 1위 종목이 본문에 있게
                  title_candidates=["SK스퀘어가 5%대 넘게 오른 이유"])
        self.assertEqual(collect_issues(doc, seven), [])
        self.assertEqual(len(collect_issues(doc, PRICE_KR)), 1)

    def test_range_end_is_not_a_band(self) -> None:
        """'3~5%대'의 5는 범위의 끝이지 '5%대'가 아닙니다."""
        doc = _ko(title_candidates=["SK스퀘어가 3~5%대로 오른 이유"])
        self.assertEqual(collect_issues(doc, PRICE_KR), [])

    def test_candidate_decimal_is_checked_like_a_title(self) -> None:
        doc = _ko(title_candidates=["SK스퀘어 4.14% 급등, 재료는 없었습니다"])
        issues = collect_issues(doc, PRICE_KR)
        self.assertEqual(len(issues), 1, issues)
        self.assertIn("4.14", issues[0])

    def test_heading_bound_is_checked(self) -> None:
        """소제목도 제목류입니다 — '뛰었나'를 등락 낱말로 읽습니다."""
        doc = _ko()
        doc["narrative"][0]["heading"] = "SK스퀘어는 왜 5% 넘게 뛰었나"
        issues = collect_issues(doc, PRICE_KR)
        self.assertEqual(len(issues), 1, issues)
        self.assertIn("본문 소제목 1", issues[0])

    def test_body_bounds_are_not_checked(self) -> None:
        """본문의 어림수는 일부러 보지 않습니다 — 원고 120곳 가운데 기간 등락·고점 대비가 많았습니다."""
        doc = _ko("SK스퀘어가 5% 넘게 올랐습니다. 삼성전자가 3.24% 올랐고 스피어는 16.95% 뛰었습니다.")
        self.assertEqual(collect_issues(doc, PRICE_KR), [])

    def test_lead_counts_alias_abbreviation_and_ticker(self) -> None:
        """9/09·9/17 프리뷰의 '루멘텀', 9/11의 'WTI는'이 1위 누락으로 잡혔습니다 — 이름 글자만 찾았기 때문."""
        us = {"watchlist": {"LITE": _entry("LITE", "Lumentum", "Lumentum", 13.20, source="dynamic")}}
        for body in ("루멘텀이 크게 뛰었습니다.", "LITE가 크게 뛰었습니다.", "Lumentum이 크게 뛰었습니다."):
            self.assertEqual(collect_issues({"title": "t", "narrative": [{"heading": "h", "body": body}]}, us), [], body)
        self.assertEqual(len(collect_issues({"title": "t", "narrative": [{"heading": "h", "body": "POLITE한 장이었습니다."}]}, us)), 1)
        wti = {"watchlist": {"CL=F": _entry("CL=F", "WTI 원유", "WTI Crude Oil", 8.25)}}
        self.assertEqual(collect_issues({"title": "t", "narrative": [{"heading": "h", "body": "WTI는 어제 배럴당 103.97달러였습니다."}]}, wti), [])
        deere = {"watchlist": {"DE": _entry("DE", "디어", "Deere", -5.00)}}   # 두 글자 티커는 세지 않습니다
        self.assertEqual(len(collect_issues({"title": "t", "narrative": [{"heading": "h", "body": "DE 티커만 적었습니다."}]}, deere)), 1)

    def test_lead_only_in_rejected_candidate_is_still_missing(self) -> None:
        """버려진 후보에만 1위 종목 이름이 있는 것은 다룬 것이 아닙니다."""
        doc = _ko("삼성전자가 3.24% 올랐습니다.", title_candidates=["스피어가 오늘 시장을 흔든 이유"])
        issues = collect_issues(doc, PRICE_KR)
        self.assertEqual(len(issues), 1, issues)
        self.assertIn("스피어", issues[0])


class ValuationContextTest(unittest.TestCase):
    """② 프리뷰 밸류에이션 문장은 등락률이 아닙니다 — 9/17·9/22·9/23 실측 문장 그대로."""

    def _us(self, body: str) -> list[str]:
        doc = {"title": "오늘 밤 FOMC", "narrative": [{"heading": "h", "body": body + " Lumentum도 올랐습니다."}]}
        return collect_issues(doc, PRICE_US)

    def test_target_price_gap_next_to_per_is_skipped(self) -> None:
        """9/17: 디어(-2.13%)는 대조하고, '목표주가 대비 2.8%'는 건너뜁니다."""
        self.assertEqual(self._us(
            "하락한 쪽에서는 디어(-2.13%)가 두드러졌습니다. 디어는 FWD PER 29.5배로 목표주가 대비로는 "
            "2.8%밖에 안 남아, 시장이 이미 그 가격을 상당 부분 인정하고 있다는 뜻입니다."), [])
        # 2026-09-25에는 창(뒤 45자)이 다음 문장의 'PER·목표주가'까지 닿아 앞 괄호의 틀린 -9.99%를 놓쳤다. 2026-09-26부터
        # 건너뛰기 판정을 **그 문장 안**에서만 하므로, 다른 문장의 밸류에이션 낱말은 앞 문장의 숫자를 끄지 않는다 — 잡는다.
        caught = self._us("하락한 쪽에서는 디어(-9.99%)가 두드러졌습니다. 디어는 FWD PER 29.5배로 목표주가 대비로는 2.8%밖에 안 남았습니다.")
        self.assertEqual(len(caught), 1, caught)
        self.assertIn("9.99%", caught[0])

    def test_target_price_chain_in_parentheses_is_skipped(self) -> None:
        """9/22 본문 9: 앞 괄호의 '목표주가까지'가 뒤 종목의 괄호 숫자까지 설명합니다."""
        self.assertEqual(self._us(
            "밸류에이션으로 여지가 남아 있는 종목은 마이크론(목표주가까지 +45.1%)과 엔비디아(+44.1%)입니다. "
            "애플은 오히려 목표주가보다 3.2% 낮게 거래되고 있어 가장 비싸게 평가받는 종목입니다."), [])

    def test_52_week_high_gap_is_skipped(self) -> None:
        self.assertEqual(self._us(
            "목표주가까지는 아직 45.1% 남아 있습니다. 52주 고점 대비로도 -16.8%로 인텔(-14.5%)과 비슷한 수준입니다."), [])

    def test_premarket_move_is_skipped(self) -> None:
        self.assertEqual(self._us(
            "인텔의 프리마켓 상승분(+5.09%)이 정규장까지 유지되는지 — 맞았습니다."), [])

    def test_percentage_point_is_skipped(self) -> None:
        """9/22 본문 1: 'WTI 원유는 8%대 급락 … 0.70%포인트 하락'의 0.70은 금리 변화폭입니다."""
        self.assertEqual(self._us(
            "WTI 원유는 8%대 급락하며 인플레이션 부담을 낮췄고, 10년물 국채금리는 0.70%포인트 하락한 4.96%로 내려왔습니다."), [])

    def test_percentage_point_cut_by_the_window_is_still_skipped(self) -> None:
        """창(45자)이 '0.70%포인트'를 '0.70%'로 자르면 원문에서 단위를 한 번 더 봅니다."""
        text = "급등한 인텔" + "은 " + "가" * 38 + "0.70%포인트 올랐습니다."
        self.assertEqual(self._us(text), [])

    def test_valuation_words_only_count_inside_the_window(self) -> None:
        """멀리 있는 '목표주가'가 틀린 숫자를 구해 주지 않습니다."""
        issues = self._us("인텔이 9.99% 올랐습니다. " + "가" * 40 + " 목표주가는 아직 멀었습니다.")
        self.assertEqual(len(issues), 1, issues)
        self.assertIn("9.99", issues[0])

    def test_english_yesterday_is_another_day(self) -> None:
        """kr 9/09 영어판: 'jumped'를 등락 낱말에 더하자 'jumped 8.47% yesterday'가 걸렸습니다."""
        price = {"watchlist": {"047040": _entry("047040", "대우건설", "Daewoo E&C", -2.60)}}
        past = {"title": "t", "narrative": [{"heading": "h", "body": "Daewoo E&C, which jumped 8.47% yesterday, fell back."}]}
        self.assertEqual(collect_issues(past, price, lang="en"), [])
        today = {"title": "t", "narrative": [{"heading": "h", "body": "Daewoo E&C jumped 8.47% on the day."}]}
        self.assertEqual(len(collect_issues(today, price, lang="en")), 1)


class PreviewEntryPointTest(unittest.TestCase):
    """③ 프리뷰는 시세 파일 둘과 대조합니다."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "data").mkdir()
        self._write("price_us_2026-09-15.json", {**PRICE_US, "trading_date": "2026-09-15"})
        self._write("price_us_2026-09-16.json", PRICE_US)
        self._write("price_kr_2026-09-17.json", PRICE_KR)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write(self, name: str, data: dict) -> Path:
        path = self.root / "data" / name
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path

    def _doc(self, body: str, date: str = "2026-09-17", graphics: list | None = None) -> dict:
        return {"kind": "feature", "series": "프리뷰", "date": date,
                "ko": {"title": "오늘 밤 FOMC", "narrative": [{"heading": "h", "body": body}]},
                "graphics": graphics or []}

    def _files(self) -> dict:
        return {"us": self.root / "data" / "price_us_2026-09-16.json",
                "kr": self.root / "data" / "price_kr_2026-09-17.json"}

    # --- 파일 찾기 ---
    def test_files_come_from_graphics_first(self) -> None:
        doc = self._doc("", graphics=[{"kind": "number_cards", "price_file": "data/price_us_2026-09-15.json"},
                                      {"kind": "price_history", "price_file": "data/price_kr_2026-09-17.json"}])
        files = preview_price_files(doc, root=self.root)
        self.assertEqual(files["us"].name, "price_us_2026-09-15.json")
        self.assertEqual(files["kr"].name, "price_kr_2026-09-17.json")

    def test_files_fall_back_to_the_date_rule(self) -> None:
        """미국장은 원고 날짜 앞의 가장 최근 파일, 한국장은 같은 날짜 파일."""
        files = preview_price_files(self._doc(""), root=self.root)
        self.assertEqual(files["us"].name, "price_us_2026-09-16.json")
        self.assertEqual(files["kr"].name, "price_kr_2026-09-17.json")

    def test_missing_kr_file_is_none(self) -> None:
        files = preview_price_files(self._doc("", date="2026-09-18"), root=self.root)
        self.assertEqual(files["us"].name, "price_us_2026-09-16.json")
        self.assertIsNone(files["kr"])

    def test_missing_us_file_raises(self) -> None:
        with self.assertRaises(ValueError):
            preview_price_files(self._doc("", date="2026-09-01"), root=self.root)

    def test_two_us_dates_in_graphics_raise(self) -> None:
        doc = self._doc("", graphics=[{"kind": "a", "price_file": "data/price_us_2026-09-15.json"},
                                      {"kind": "b", "price_file": "data/price_us_2026-09-16.json"}])
        with self.assertRaises(ValueError):
            preview_price_files(doc, root=self.root)

    # --- 대조 ---
    def test_us_lead_missing_is_flagged_with_file_name(self) -> None:
        issues = collect_issues_for_preview(self._doc("인텔이 12.14% 올랐습니다."), self._files())
        self.assertEqual(len(issues), 1, issues)
        self.assertTrue(issues[0].startswith("[price_us_2026-09-16]"), issues[0])
        self.assertIn("Lumentum", issues[0])

    def test_kr_lead_is_not_required(self) -> None:
        """10절은 장세 요약이지 종목 순위가 아닙니다 — 스피어(+16.95%)를 요구하지 않습니다."""
        issues = collect_issues_for_preview(self._doc("Lumentum이 13.20% 뛰었습니다."), self._files())
        self.assertEqual(issues, [])

    def test_yesterday_numbers_are_checked_against_the_us_file(self) -> None:
        """프리뷰의 '어제'는 미국장 파일의 날입니다 — 시황 규칙으로 보면 전부 빠집니다."""
        body = "어제 가장 크게 움직인 것은 인텔(+9.99%)과 Lumentum(+13.20%)이었습니다."
        issues = collect_issues_for_preview(self._doc(body), self._files())
        self.assertEqual(len(issues), 1, issues)
        self.assertIn("9.99", issues[0])
        self.assertEqual(collect_issues(self._doc(body)["ko"], PRICE_US), [])   # 시황 규칙: '어제'는 다른 날

    def test_today_in_us_pass_is_not_the_file_day(self) -> None:
        """'오늘 프리마켓'·'오늘 밤'의 숫자는 아직 열리지 않은 장의 것입니다."""
        body = "오늘 인텔이 9.99% 오른 채 시작할 수 있습니다. Lumentum은 13.20% 뛰었습니다."
        self.assertEqual(collect_issues_for_preview(self._doc(body), self._files()), [])

    def test_kr_numbers_are_checked_for_today_only(self) -> None:
        today = collect_issues_for_preview(
            self._doc("Lumentum이 13.20% 뛰었습니다. 오늘 한국장에서 삼성전자가 9.99% 올랐습니다."), self._files())
        self.assertEqual(len(today), 1, today)
        self.assertTrue(today[0].startswith("[price_kr_2026-09-17]"), today[0])
        yesterday = collect_issues_for_preview(
            self._doc("Lumentum이 13.20% 뛰었습니다. 어제 한국장에서 삼성전자가 9.99% 올랐습니다."), self._files())
        self.assertEqual(yesterday, [])

    def test_other_date_earlier_in_the_paragraph_is_skipped(self) -> None:
        """9/08 프리뷰: 앞 문장의 '9월 7일'이 창 밖에 있어 9/07 숫자를 9/08 파일과 대조했습니다."""
        other = "미국이 노동절로 쉰 9월 7일, 서울은 같은 이야기를 이어받았습니다. 삼성전자가 9.99% 올랐습니다."
        self.assertEqual(collect_issues_for_preview(
            self._doc("Lumentum이 13.20% 뛰었습니다.\n\n" + other), self._files()), [])
        own = "9월 17일 서울에서는 삼성전자가 9.99% 올랐습니다."   # 파일 자신의 날짜는 다른 날이 아닙니다
        issues = collect_issues_for_preview(self._doc("Lumentum이 13.20% 뛰었습니다.\n\n" + own), self._files())
        self.assertEqual(len(issues), 1, issues)
        self.assertIn("삼성전자", issues[0])

    def test_missing_kr_file_leaves_a_note(self) -> None:
        notes: list[str] = []
        issues = collect_issues_for_preview(
            self._doc("Lumentum이 13.20% 뛰었습니다. 삼성전자가 9.99% 올랐습니다."),
            {"us": self._files()["us"], "kr": None}, notes_out=notes)
        self.assertEqual(issues, [])
        self.assertEqual(len(notes), 1, notes)
        self.assertIn("한국장", notes[0])

    def test_list_of_paths_is_accepted(self) -> None:
        issues = collect_issues_for_preview(self._doc("인텔이 12.14% 올랐습니다."), list(self._files().values()))
        self.assertEqual(len(issues), 1, issues)

    def test_without_us_file_raises(self) -> None:
        with self.assertRaises(ValueError):
            collect_issues_for_preview(self._doc(""), {"kr": self._files()["kr"]})

    def test_validate_preview_raises(self) -> None:
        with self.assertRaises(EditorialFactError):
            validate_preview(self._doc("인텔이 9.99% 올랐습니다."), self._files())


if __name__ == "__main__":
    unittest.main()
