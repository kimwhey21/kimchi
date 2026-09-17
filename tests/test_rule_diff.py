"""`scripts/rule_diff.py` — 문서를 다시 쓸 때 사라진 규칙 줄을 찾는다 (2026-09-17).

2026-09-17 12절 개정에서 「`ko.title`: **앞을 보는 제목** — 오늘 밤 무엇이 무엇을 정하는지」가 빠졌고,
그날 밤 루틴이 어젯밤 요약형 제목을 냈다. 이 도구는 옛 판의 규칙 줄이 새 판에 없으면 목록으로 낸다.
사장님 말: "사과를 깎아 달라고 했는데 내 눈에 보이는 부분만 깎아 놓고 나머지는 안 깎은 식" —
보이지 않는 부분(사라진 줄)을 기계가 보이게 만드는 것이 이 도구의 일이다.
"""
from __future__ import annotations

import unittest

from scripts import rule_diff

OLD = """## 절차
- `ko.title`: **앞을 보는 제목** — 오늘 밤 무엇이 무엇을 정하는지.
- 본문 600~900자, 절 3개, 시각자료 3장.
- 예측하지 않습니다. 조건으로 씁니다.
설명일 뿐인 문장은 규칙이 아닙니다.
"""
NEW = """## 절차
- 분량 4,500~6,000자, 12절, 그림 8~10장.
- 예측하지 않습니다. 시나리오 표와 대응 원칙은 조건문입니다.
"""


class RuleDiffTest(unittest.TestCase):
    def test_removed_rule_lines_are_listed(self) -> None:
        gone = rule_diff.removed_rules(OLD, NEW)
        self.assertTrue(any("앞을 보는 제목" in g for g in gone), gone)      # 2026-09-17에 실제로 빠진 줄
        self.assertTrue(any("600~900자" in g for g in gone), gone)          # 일부러 뺀 줄도 목록에 오른다 — 사람이 '일부러'라고 말해야 한다

    def test_kept_or_reworded_rule_is_not_flagged(self) -> None:
        gone = rule_diff.removed_rules(OLD, NEW)
        self.assertFalse(any("예측하지 않습니다" in g for g in gone), gone)   # 앞 24자가 새 판에 있으면 살아 있는 것

    def test_plain_explanation_is_not_a_rule(self) -> None:
        self.assertEqual(rule_diff.rule_lines("설명일 뿐인 문장은 규칙이 아닙니다."), [])
        self.assertEqual(len(rule_diff.rule_lines("- 초보자 설명 둘 이상(관문).")), 1)


if __name__ == "__main__":
    unittest.main()
