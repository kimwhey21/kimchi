"""숫자 대조의 네 구멍 (2026-09-26 점검) — 방향, 남의 숫자, 문장을 넘는 건너뛰기, 낱말 속 이름.

점검 때 9/23 원고에 넣어 본 틀린 문장이 전부 통과했다. 지난 원고 87편에 다시 돌려 새로 막히는 맞는 글이 없는 것도
확인했다(새로 걸린 1건은 9/23 프리뷰가 옛 기준 1.36%를 인용한 실제 불일치). '확실할 때만 막는다'는 원칙은 그대로다.
"""
import copy
import json
import unittest
from pathlib import Path

from src import editorial_facts as ef

ROOT = Path(__file__).resolve().parent.parent
KR = json.loads((ROOT / "editorial" / "kr_2026-09-23.json").read_text(encoding="utf-8"))   # 삼성전자 +2.70, SK하이닉스 +1.36
US = json.loads((ROOT / "editorial" / "us_2026-09-25.json").read_text(encoding="utf-8"))
KR0904 = json.loads((ROOT / "editorial" / "kr_2026-09-04.json").read_text(encoding="utf-8"))


def _new_issues(doc: dict, sentence: str, lang: str = "ko", at_start: bool = False) -> list[str]:
    part = copy.deepcopy(doc[lang])
    base = ef.collect_issues(doc[lang], doc["price_data"], lang)
    body = part["narrative"][0]["body"]
    part["narrative"][0]["body"] = (sentence + "\n\n" + body) if at_start else (body + "\n\n" + sentence)
    return [i for i in ef.collect_issues(part, doc["price_data"], lang) if i not in base]


class DirectionTest(unittest.TestCase):
    def test_rise_written_as_fall_is_caught(self) -> None:
        self.assertTrue(any("방향이 반대" in i for i in _new_issues(KR, "삼성전자는 2.70% 하락했습니다.")))
        self.assertTrue(any("방향이 반대" in i for i in _new_issues(KR, "삼성전자(-2.70%)가 밀렸습니다.")))

    def test_correct_direction_passes(self) -> None:
        self.assertEqual(_new_issues(KR, "삼성전자는 2.70% 올랐습니다."), [])

    def test_an_up_inside_a_word_is_not_a_direction(self) -> None:
        # 'KB Financial Group 3.32%'의 Group 끝 'up'을 상승으로 읽었었다.
        self.assertEqual(_new_issues(KR0904, "Shinhan Financial Group fell 3.67% and KB Financial Group 3.32%.", "en"), [])


class BorrowedNumberTest(unittest.TestCase):
    def test_swapped_numbers_are_caught(self) -> None:
        issues = _new_issues(KR, "삼성전자가 1.36% 올랐고 SK하이닉스는 2.70% 올랐습니다.")
        self.assertEqual(len(issues), 2, issues)

    def test_respectively_structures_still_pass(self) -> None:
        self.assertEqual(_new_issues(KR, "삼성전자와 SK하이닉스는 각각 2.70%, 1.36% 올랐습니다."), [])

    def test_same_company_shares_share_numbers(self) -> None:
        doc = json.loads((ROOT / "editorial" / "us_2026-09-14.json").read_text(encoding="utf-8"))
        self.assertEqual(_new_issues(doc, "Alphabet rose 3.22% today.", "en"), [])


class WindowTest(unittest.TestCase):
    def test_intraday_word_in_the_next_paragraph_does_not_switch_the_check_off(self) -> None:
        issues = _new_issues(KR, "삼성전자는 7.77% 올랐습니다.", at_start=True)     # 다음 문단에 '장중'이 있다
        self.assertTrue(any("7.77%" in i for i in issues), issues)

    def test_market_cap_is_not_an_opening_price(self) -> None:
        self.assertTrue(_new_issues(KR, "시가총액 1위 삼성전자가 7.77% 올랐습니다."))


class NameBoundaryTest(unittest.TestCase):
    def test_a_name_inside_another_word_is_not_that_stock(self) -> None:
        self.assertEqual(_new_issues(US, "소셜미디어 업종은 3.37% 올랐습니다."), [])

    def test_lead_mover_is_not_covered_by_a_word_that_contains_its_name(self) -> None:
        self.assertFalse(ef._mentions("소셜미디어 업종", "디어"))
        self.assertTrue(ef._mentions("디어가 올랐다", "디어"))
        self.assertFalse(ef._mentions("Metaverse names", "Meta"))


if __name__ == "__main__":
    unittest.main()
