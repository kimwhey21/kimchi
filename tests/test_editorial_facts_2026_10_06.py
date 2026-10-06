"""숫자 대조가 놓치던 꼴 (2026-10-06 감사 F-014·F-054) — 지수·환율 이름 뒤의 낱말, 영어 동사, 대소문자, 판정 문장·그림 설명.

지난 원고 110편(시황 ko·en, 프리뷰)에 다시 돌려 새로 걸린 것은 9/1 원/달러 0.23%(시세 0.28%) 두 곳뿐이고 둘 다 실제 불일치다.
숫자 앞에서만 장중·다른 날 표지를 보게 좁히는 것과 영어 환율 수준 꼴은 맞는 문장을 막아(7곳·2곳) 넣지 않았다.
"""
import copy
import json
import unittest
from pathlib import Path

from src import editorial_facts as ef

ROOT = Path(__file__).resolve().parent.parent
US = json.loads((ROOT / "editorial" / "us_2026-10-05.json").read_text(encoding="utf-8"))   # S&P500 +0.66, 다우 +0.18, 금 -0.13
KR = json.loads((ROOT / "editorial" / "kr_2026-10-02.json").read_text(encoding="utf-8"))   # 코스피 +0.46, 원/달러 -0.92


def _new(doc: dict, sentence: str, lang: str = "ko") -> list[str]:
    part = copy.deepcopy(doc[lang])
    base = ef.collect_issues(part, doc["price_data"], lang)
    part["narrative"][0]["body"] += "\n\n" + sentence
    return [i for i in ef.collect_issues(part, doc["price_data"], lang) if i not in base]


class MacroWordsTest(unittest.TestCase):
    def test_wrong_index_numbers_after_common_words_are_caught(self) -> None:
        for doc, sentence, lang in (
            (US, "The S&P 500 gained 1.95% on the day.", "en"),
            (US, "The Dow Jones Industrial Average rose 3.49%.", "en"),
            (US, "S&P500 지수는 1.95% 상승했습니다.", "ko"),
            (US, "나스닥 종합지수가 3.05% 올랐습니다.", "ko"),
            (US, "다우는 0.95% 올랐습니다.", "ko"),
            (US, "국제 금값도 3.72% 올랐습니다.", "ko"),
            (KR, "코스피 지수는 1.46% 올랐습니다.", "ko"),
            (KR, "원/달러 환율은 서울 외환시장 고시 기준 1.92% 하락했습니다.", "ko"),
            (KR, "원/달러 환율은 1,347원으로 0.23% 내렸습니다.", "ko"),
        ):
            with self.subTest(sentence=sentence):
                self.assertTrue(_new(doc, sentence, lang))

    def test_correct_numbers_pass(self) -> None:
        self.assertEqual(_new(US, "The S&P 500 gained 0.66% on the day.", "en"), [])
        self.assertEqual(_new(KR, "코스피 지수는 0.46% 올랐습니다.", "ko"), [])

    def test_other_words_between_still_mean_someone_elses_number(self) -> None:
        self.assertEqual(_new(KR, "코스닥 장비주도 심텍 4.78% 올랐습니다."), [])
        self.assertEqual(_new(KR, "Wonik IPS, listed on the KOSDAQ, gained 9.33%.", "en"), [])

    def test_period_moves_are_not_the_days_move(self) -> None:
        self.assertEqual(_new(US, "Over the full month, the Dow fell 4.9% and the S&P 500 lost 0.70%.", "en"), [])
        self.assertEqual(_new(KR, "KOSPI fell 191.18 points (2.70%) on the 28th.", "en"), [])
        self.assertEqual(_new(KR, "이번 주 코스피는 3.10% 올랐습니다."), [])

    def test_capitalised_english_name(self) -> None:
        self.assertTrue(_new(US, "Nvidia shares jumped 9.12%.", "en"))

    def test_dau_inside_another_name_is_not_the_dow(self) -> None:
        self.assertEqual(_new(US, "다우데이타는 9.99% 올랐습니다."), [])


class MoreTextsTest(unittest.TestCase):
    def test_review_result_is_checked_against_the_day(self) -> None:
        doc = copy.deepcopy(KR)
        doc["review"] = {"result": "코스피는 오늘 1.46% 오르며 7,000선을 지켰습니다."}
        self.assertTrue(any("어제 판정" in i for i in ef.collect_issues(ef.with_review(doc["ko"], doc), doc["price_data"])))

    def test_graphic_note_is_checked(self) -> None:
        part = copy.deepcopy(KR["ko"])
        part["narrative"][0]["graphic"] = {"kind": "number_cards", "note": "코스피 7,003.74(+1.46%)"}
        self.assertTrue(any("그림" in i for i in ef.collect_issues(part, KR["price_data"])))


if __name__ == "__main__":
    unittest.main()
