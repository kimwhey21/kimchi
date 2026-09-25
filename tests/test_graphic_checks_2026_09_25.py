"""그래픽 검사 확장(2026-09-25) — 눈으로만 잡히던 오류 넷을 코드가 잡는다.

2026-09-25 감사·검증에서 눈으로만 잡힌 오류 7건 중 6건은 코드가 판정할 수 있었다: ① sector_bars 제목은
'반도체만 웃었습니다'인데 다른 업종 막대도 빨갛다 ② price_history·stock_spotlight 제목은 '신고가를 씁니다'인데
마지막 값이 이력 최대값이 아니다 ③ movers_list가 그린 종목이 그 절 본문에 없다 ④ fact_table 셀 글자가 열 폭을
넘어 이웃 셀과 겹친다(프리뷰 9/22·23·24 사흘 연속). 렌더러(`data_graphics`)와 검사(`graphic_checks`)가 같은
행 계산·같은 기하를 쓰는지도 여기서 고정한다.
"""
from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src import data_graphics, graphic_checks

ROOT = Path(__file__).resolve().parent.parent


def _entry(ticker: str, name: str, closes: list[float], change: float = 1.0, sector: str | None = None,
           name_en: str | None = None, dates: list[str] | None = None) -> dict:
    entry = {"ticker": ticker, "name": name, "price": closes[-1], "change_pct": change,
             "history": {"dates": dates or [f"2026-09-{i + 1:02d}" for i in range(len(closes))],
                         "close": list(closes)}}
    if sector:
        entry["sector"] = sector
    if name_en:
        entry["name_en"] = name_en
    return entry


def _kr_price_data() -> dict:
    """반도체만 오른 것이 **아닌** 날 — 소비재도 올랐다(2026-09-23 실제 구성을 본뜸)."""
    return {
        "trading_date": "2026-09-05",
        "macro": {"KS11": _entry("KS11", "코스피", [6900, 6950, 7000, 7080, 7050], 0.9)},
        "watchlist": {
            "005930": _entry("005930", "삼성전자", [270000, 275000, 280000, 286500, 286500], 3.24, "반도체", "Samsung Electronics"),
            "000660": _entry("000660", "SK하이닉스", [1000, 1010, 1020, 1030, 1030], 1.2, "반도체", "SK Hynix"),
            "105560": _entry("105560", "KB금융", [100, 101, 102, 100, 99], -1.19, "금융", "KB Financial"),
            "005380": _entry("005380", "현대차", [200, 201, 202, 200, 197], -1.38, "자동차", "Hyundai Motor"),
            "278470": _entry("278470", "에이피알", [50, 51, 52, 53, 54], 1.93, "소비재", "APR"),
            "034020": _entry("034020", "두산에너빌리티", [70, 72, 71, 70, 67], -4.5, "발전·원전", "Doosan Enerbility"),
            "047040": _entry("047040", "대우건설", [10, 10, 10, 10, 9.4], -6.4, None, "Daewoo E&C"),
        },
    }


class SectorBarsExclusiveTitleTest(unittest.TestCase):
    """① 제목이 '하나만'을 말하면 같은 방향 막대는 하나여야 한다."""

    def test_only_claim_with_two_rising_sectors_fails(self) -> None:
        issues = graphic_checks.collect_spec_issues("sector_bars", {"title": "반도체만 웃었습니다"},
                                                    price_data=_kr_price_data())
        self.assertEqual(len(issues), 1, issues)
        self.assertIn("소비재", issues[0])

    def test_only_claim_holds_when_it_is_the_sole_riser(self) -> None:
        data = _kr_price_data()
        data["watchlist"]["278470"]["change_pct"] = -0.5   # 소비재도 내리면 반도체만 오른 것이 맞다
        issues = graphic_checks.collect_spec_issues("sector_bars", {"title": "반도체만 웃었습니다"}, price_data=data)
        self.assertEqual(issues, [])

    def test_negative_side_is_symmetric(self) -> None:
        issues = graphic_checks.collect_spec_issues("sector_bars", {"title": "금융만 내렸습니다"},
                                                    price_data=_kr_price_data())
        self.assertEqual(len(issues), 1, issues)
        self.assertIn("자동차", issues[0])

    def test_english_only_and_korean_유일(self) -> None:
        data = _kr_price_data()
        self.assertTrue(graphic_checks.collect_spec_issues("sector_bars", {"title": "Chips were the only sector up"},
                                                           price_data=data))
        self.assertTrue(graphic_checks.collect_spec_issues("sector_bars", {"title": "유일하게 오른 반도체"},
                                                           price_data=data))

    def test_plain_만_in_other_words_is_not_a_claim(self) -> None:
        """'만원'·'만에'·'2만 명'의 '만'은 하나만이라는 뜻이 아니다."""
        data = _kr_price_data()
        for title in ("코스피 3년 2개월 만에 최대 낙폭", "시총 300만원 시대", "거래대금 2만 억원", "업종별 등락"):
            self.assertEqual(graphic_checks.collect_spec_issues("sector_bars", {"title": title}, price_data=data),
                             [], title)

    def test_without_price_data_the_check_is_skipped(self) -> None:
        self.assertEqual(graphic_checks.collect_spec_issues("sector_bars", {"title": "반도체만 웃었습니다"}), [])


class ExtremeClaimTest(unittest.TestCase):
    """② '신고가·최고·record·high'는 마지막 값이 이력의 최대여야 한다('최저' 대칭)."""

    def test_price_history_record_claim_fails_when_last_is_not_max(self) -> None:
        data = _kr_price_data()   # 코스피 이력 최대 7080, 마지막 7050
        issues = graphic_checks.collect_spec_issues("price_history", {"ticker": "KS11", "title": "코스피, 신고가를 씁니다"},
                                                    price_data=data)
        self.assertEqual(len(issues), 1, issues)
        self.assertIn("7,050", issues[0])

    def test_price_history_record_claim_passes_at_max(self) -> None:
        data = _kr_price_data()
        data["macro"]["KS11"]["history"]["close"][-1] = 7100.0
        issues = graphic_checks.collect_spec_issues("price_history", {"ticker": "KS11", "title": "코스피, 사상 최고치를 다시 썼습니다"},
                                                    price_data=data)
        self.assertEqual(issues, [])

    def test_hedged_titles_are_not_judged(self) -> None:
        data = _kr_price_data()
        for title in ("코스피, 최고치 근처", "코스피, 3개월 최고 대비 -1%", "알파벳, 3개월 최고가에서 밀려났습니다",
                      "10-year yield near a 2007 high"):
            self.assertEqual(graphic_checks.collect_spec_issues("price_history", {"ticker": "KS11", "title": title},
                                                                price_data=data), [], title)

    def test_low_claim_is_symmetric(self) -> None:
        data = _kr_price_data()
        self.assertTrue(graphic_checks.collect_spec_issues("price_history", {"ticker": "KS11", "title": "코스피, 신저가"},
                                                           price_data=data))
        data["macro"]["KS11"]["history"]["close"][-1] = 6800.0
        self.assertEqual(graphic_checks.collect_spec_issues("price_history", {"ticker": "KS11", "title": "코스피, 최저치"},
                                                            price_data=data), [])

    def test_rounded_price_within_tolerance_is_not_a_lie(self) -> None:
        """시세 파일의 price는 반올림(5.11), 이력은 아니다(5.114) — 딱 같음을 요구하면 참인 제목이 걸린다(실측 ^TNX)."""
        data = {"trading_date": "2026-09-24", "macro": {"^TNX": _entry("^TNX", "10년물", [4.9, 5.0, 5.114], 1.0)}, "watchlist": {}}
        data["macro"]["^TNX"]["price"] = 5.11
        data["macro"]["^TNX"]["history"]["dates"][-1] = "2026-09-23"   # 일봉이 하루 늦는 날 — 현재값은 price
        issues = graphic_checks.collect_spec_issues("number_cards", {"tickers": ["^TNX"], "title": "국채금리, 2007년 이후 최고치로"},
                                                    price_data=data)
        self.assertEqual(issues, [])

    def test_stock_spotlight_uses_default_biggest_mover(self) -> None:
        data = _kr_price_data()   # 등락 폭 1위는 대우건설(-6.4), 이력 최대 10, 마지막 9.4
        issues = graphic_checks.collect_spec_issues("stock_spotlight", {"title": "오늘의 주인공, 신고가"}, price_data=data)
        self.assertEqual(len(issues), 1, issues)
        self.assertIn("대우건설", issues[0])

    def test_number_cards_pass_if_any_card_is_at_its_high(self) -> None:
        data = _kr_price_data()
        issues = graphic_checks.collect_spec_issues("number_cards", {"tickers": ["KS11", "005930"], "title": "삼성전자는 최고치, 코스피는 밀렸습니다"},
                                                    price_data=data)
        self.assertEqual(issues, [])   # 삼성전자 이력 마지막 == 최대
        issues = graphic_checks.collect_spec_issues("number_cards", {"tickers": ["KS11", "105560"], "title": "최고치를 다시 썼습니다"},
                                                    price_data=data)
        self.assertEqual(len(issues), 1, issues)

    def test_english_wording(self) -> None:
        data = _kr_price_data()
        self.assertTrue(graphic_checks.collect_spec_issues("price_history", {"ticker": "KS11", "title": "KOSPI hit a fresh record"},
                                                           price_data=data))
        self.assertTrue(graphic_checks.collect_spec_issues("price_history", {"ticker": "KS11", "title": "KOSPI: highest since June"},
                                                           price_data=data))
        # 'higher'·'below'는 최고·최저 주장이 아니다
        self.assertEqual(graphic_checks.collect_spec_issues("price_history", {"ticker": "KS11", "title": "KOSPI edged higher, still below 7,100"},
                                                            price_data=data), [])

    def test_unknown_ticker_is_reported_not_swallowed(self) -> None:
        issues = graphic_checks.collect_spec_issues("price_history", {"ticker": "NOPE", "title": "신고가"}, price_data=_kr_price_data())
        self.assertTrue(issues and "NOPE" in issues[0], issues)


class MoversBodyTest(unittest.TestCase):
    """③ movers_list가 그린 종목이 본문에 **하나도** 없으면 실패, 절반 넘게 없으면 참고(notes_out)만.
    2026-09-25 실측: 절반 규칙을 막는 검사로 두면 기존 59장 중 30장이 걸린다 — 확실할 때만 막는다.
    이름 대조는 낱말 경계(조사는 붙어도 된다)."""

    def test_none_named_fails(self) -> None:
        body = "오늘은 은행주가 무거웠고 환율이 흔들렸습니다."
        notes: list[str] = []
        issues = graphic_checks.collect_spec_issues("movers_list", {"top_n": 6}, price_data=_kr_price_data(),
                                                    section_body=body, notes_out=notes)
        self.assertEqual(len(issues), 1, issues)
        self.assertIn("하나도 없습니다", issues[0])
        self.assertIn("삼성전자", issues[0])
        self.assertEqual(notes, [])

    def test_more_than_half_missing_is_a_note_not_a_block(self) -> None:
        body = "오늘은 대우건설과 두산에너빌리티가 크게 내렸습니다."
        notes: list[str] = []
        issues = graphic_checks.collect_spec_issues("movers_list", {"top_n": 6}, price_data=_kr_price_data(),
                                                    section_body=body, notes_out=notes)
        self.assertEqual(issues, [])
        self.assertEqual(len(notes), 1, notes)
        self.assertIn("삼성전자", notes[0])

    def test_half_or_less_missing_passes_and_particles_count_as_mention(self) -> None:
        body = "대우건설은 6.4% 내렸고 두산에너빌리티도 밀렸습니다. 삼성전자는 올랐고 에이피알이 뒤를 이었습니다."
        issues = graphic_checks.collect_spec_issues("movers_list", {"top_n": 6}, price_data=_kr_price_data(), section_body=body)
        self.assertEqual(issues, [])

    def test_english_name_counts(self) -> None:
        body = "Daewoo E&C, Doosan Enerbility, Samsung Electronics and APR led the moves."
        issues = graphic_checks.collect_spec_issues("movers_list", {"top_n": 6}, price_data=_kr_price_data(), section_body=body)
        self.assertEqual(issues, [])

    def test_name_inside_another_word_is_not_a_mention(self) -> None:
        """'소비자물가'의 '비자'처럼 앞에 글자가 붙으면 다른 낱말이다 — 별칭·부분 일치는 허용하지 않는다.
        경계 규칙은 `post_tags.mentioned` 그대로다(두 글자 이름은 뒤에 조사만, 긴 이름은 조사·접미가 붙어도 같은 이름)."""
        data = _kr_price_data()
        data["watchlist"] = {"1": _entry("1", "비자", [1, 2], 3.0), "2": _entry("2", "두산", [1, 2], 2.0)}
        issues = graphic_checks.collect_spec_issues("movers_list", {"top_n": 2}, price_data=data,
                                                    section_body="소비자물가와 두산에너빌리티 이야기")   # 둘 다 다른 낱말
        self.assertEqual(len(issues), 1, issues)   # 둘 다 없음 → 하나도 없음 → 실패
        self.assertIn("비자", issues[0])
        self.assertIn("두산", issues[0])

    def test_without_section_body_the_check_is_skipped(self) -> None:
        self.assertEqual(graphic_checks.collect_spec_issues("movers_list", {"top_n": 6}, price_data=_kr_price_data()), [])

    def test_check_and_renderer_pick_the_same_stocks(self) -> None:
        picked = data_graphics.movers_picked(_kr_price_data(), 3)
        self.assertEqual([e["name"] for e in picked], ["삼성전자", "두산에너빌리티", "대우건설"])   # 등락률 내림차순
        with mock.patch.object(data_graphics, "movers_picked", wraps=data_graphics.movers_picked) as spy:
            out = Path(tempfile.mkdtemp()) / "m.png"
            data_graphics.movers_list(_kr_price_data(), out, top_n=3, style="bars")
            self.assertTrue(spy.called)
            self.assertTrue(out.exists())


class SectorBodyTest(unittest.TestCase):
    """sector_bars는 업종 전부를 그리므로 '절반' 규칙을 걸면 기존 17장이 전부 걸린다(2026-09-25 실측) —
    업종 이름도 대표 종목 이름도 하나도 없을 때만(엉뚱한 절에 붙었을 때) 실패한다."""

    def test_no_label_in_body_fails(self) -> None:
        issues = graphic_checks.collect_spec_issues("sector_bars", {"title": "업종별 등락"}, price_data=_kr_price_data(),
                                                    section_body="국채금리가 5%에 다가섰습니다.")
        self.assertEqual(len(issues), 1, issues)

    def test_one_sector_named_passes(self) -> None:
        issues = graphic_checks.collect_spec_issues("sector_bars", {"title": "업종별 등락"}, price_data=_kr_price_data(),
                                                    section_body="반도체가 오른 뒤편에서 은행은 반대로 갔습니다.")
        self.assertEqual(issues, [])

    def test_check_and_renderer_share_sector_rows(self) -> None:
        rows = data_graphics.sector_rows(_kr_price_data())
        self.assertEqual([s for s, _, _ in rows][:2], ["반도체", "소비재"])   # 평균 2.22 > 1.93 내림차순
        with mock.patch.object(data_graphics, "sector_rows", wraps=data_graphics.sector_rows) as spy:
            out = Path(tempfile.mkdtemp()) / "s.png"
            data_graphics.sector_bars(_kr_price_data(), out)
            self.assertTrue(spy.called)


@unittest.skipUnless(data_graphics.has_korean_font(), "한글 폰트가 없어 렌더를 건너뜁니다")
class FactTableFitTest(unittest.TestCase):
    """④ 셀 폭은 렌더러의 기하로 잰다. 19 → 17 → 15로 줄여 맞는 첫 크기로 그리고, 15에서도 넘치면 검사가 막는다."""

    SHORT = [["8월 고용", "16.2만", "5.3만", "+10.9만"], ["실업률", "4.3%", "4.3%", "0"]]
    # 5열 표 — 열 안쪽 폭 115px. '뱅크오브아메리카'는 19에서 128px, 15에서 104px(프리뷰 9/22 실측 셀).
    STREET = [["엘도라도골드", "뱅크오브아메리카", "상향", "언더퍼폼→매수", "$32→$54"]]
    TOO_LONG = [["금리", "Intraday high 5.04% (highest since 2007), closed 5.00%", "x"]]

    def test_fit_size_shrinks_until_nothing_overflows(self) -> None:
        self.assertEqual(data_graphics.fact_table_fit_size(self.SHORT), 19)
        self.assertEqual(data_graphics.fact_table_fit_size(self.STREET), 15)
        self.assertIsNone(data_graphics.fact_table_fit_size(self.TOO_LONG))

    def test_overflow_report_names_the_cell(self) -> None:
        # 글꼴에 따라 몇 셀이 넘치는지는 달라진다(맥 1셀, CI 리눅스 글꼴 2셀 — 2026-09-25 Tests 실패). 검사가 보장할 것은
        # "가장 긴 셀을 이름으로 지목한다"와 "축소하면 다 들어간다"이지 넘치는 셀의 개수가 아니다.
        over = data_graphics.fact_table_overflows(self.STREET, None, 19)
        self.assertGreaterEqual(len(over), 1, over)
        self.assertTrue(any("뱅크오브아메리카" in x for x in over), over)
        self.assertEqual(data_graphics.fact_table_overflows(self.STREET, None, 15), [])

    def test_geometry_matches_the_renderer(self) -> None:
        """검사가 재는 폭 = 렌더러가 그리는 폭. 첫 열 380, 나머지는 (1000 - 64 - 380)을 균등 분할, 여백 12."""
        first_w, other_w = data_graphics.fact_table_widths(5)
        self.assertEqual(first_w, 380)
        self.assertAlmostEqual(other_w, (data_graphics.W - 64 - 380) / 4)
        self.assertEqual(data_graphics.fact_table_x(0, 5), 32)
        self.assertAlmostEqual(data_graphics.fact_table_x(2, 5), 32 + 380 + other_w)
        self.assertEqual(data_graphics.FACT_TABLE_SIZES, (19, 17, 15))

    def test_renderer_uses_fit_size_and_warns_when_even_15_overflows(self) -> None:
        out = Path(tempfile.mkdtemp()) / "t.png"
        with mock.patch.object(data_graphics, "fact_table_fit_size", wraps=data_graphics.fact_table_fit_size) as spy:
            data_graphics.fact_table({}, out, rows=self.STREET, source="마켓비트")
            self.assertTrue(spy.called)
        self.assertTrue(out.exists())
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            data_graphics.fact_table({}, out, rows=self.TOO_LONG, source="x")
        self.assertIn("[경고] fact_table", err.getvalue())   # 조용히 겹친 그림을 내지 않는다

    def test_spec_check_blocks_only_what_15_cannot_fix(self) -> None:
        self.assertEqual(graphic_checks.collect_spec_issues("fact_table", {"rows": self.STREET, "source": "x"}), [])
        issues = graphic_checks.collect_spec_issues("fact_table", {"rows": self.TOO_LONG, "source": "x"})
        self.assertEqual(len(issues), 1, issues)
        self.assertIn("Intraday", issues[0])

    def test_header_overflow_is_reported(self) -> None:
        rows = [["a", "1", "2"]]
        columns = ["항목", "아주 아주 아주 아주 아주 아주 아주 아주 아주 긴 머리글", "x"]
        self.assertIsNone(data_graphics.fact_table_fit_size(rows, columns))
        self.assertIn("머리글", data_graphics.fact_table_overflows(rows, columns, 19)[0])


class BackwardCompatibilityTest(unittest.TestCase):
    def test_old_three_argument_call_still_works(self) -> None:
        self.assertEqual(graphic_checks.collect_spec_issues("number_cards", {"tickers": ["KS11"]}, "오늘의 숫자"), [])
        self.assertEqual(graphic_checks.collect_spec_issues("fact_table", {"rows": [["a", "b"]]}, ""), [])


@unittest.skipUnless((ROOT / "editorial" / "kr_2026-09-23.json").exists(), "2026-09-23 원고가 없습니다")
class AuditExampleOnRealDataTest(unittest.TestCase):
    """2026-09-25 감사의 예문 제목을 그날 원고에 박힌 시세(관문이 보는 것)에 얹으면 잡힌다."""

    def test_sector_bars_only_claim_on_2026_09_23(self) -> None:
        doc = json.loads((ROOT / "editorial" / "kr_2026-09-23.json").read_text(encoding="utf-8"))
        issues = graphic_checks.collect_spec_issues("sector_bars", {"title": "반도체만 웃었습니다"}, price_data=doc["price_data"])
        self.assertEqual(len(issues), 1, issues)
        self.assertIn("소비재", issues[0])


if __name__ == "__main__":
    unittest.main()
