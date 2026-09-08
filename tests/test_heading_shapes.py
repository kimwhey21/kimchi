"""소제목의 꼴 — 사람이 쓴 것처럼 (2026-09-08).

사용자: "재테크농부의 표현 방법과 말투를 잘 보고 배워야 한다. AI 같은 표현은 안 된다."
벤치마크 소제목 462개에는 없고 우리 소제목에만 있는 세 가지 꼴을 막는다.
코퍼스가 있는 컴퓨터에서는 벤치마크 소제목이 얼마나 걸리는지도 잰다(오탐 가드).
"""
from __future__ import annotations

import json
import pathlib
import re
import unittest

from src import editorial_quality, editorial_title

CORPUS = pathlib.Path.home() / ".market-brief-bench" / "posts"


def _issues(heading: str) -> list[str]:
    return editorial_title.collect_heading_issues([{"heading": heading, "body": "b"}])


class HeadlineShapeTest(unittest.TestCase):
    def test_modifier_plus_name_is_caught(self) -> None:
        for h in ("예상을 넘고도 하락한 브로드컴", "금리 기대가 낮아지자 오른 코인베이스",
                  "좋은 소식에도 5.81% 하락한 팔란티어"):
            self.assertTrue(any("헤드라인 꼴" in i for i in _issues(h)), h)
        # 설정에 없는 이름(스노우플레이크)이나 보통 명사(고용)로 끝나면 막지 않고 알려만 준다
        notes: list[str] = []
        self.assertEqual(editorial_title.collect_heading_issues(
            [{"heading": "가속으로 답한 스노우플레이크"}, {"heading": "예상치의 3배…너무 강했던 고용"}],
            notes_out=notes), [])
        self.assertEqual(len(notes), 2, notes)

    def test_benchmark_style_headings_pass(self) -> None:
        for h in ("호르무즈 협상이 다시 교착 상태에 빠졌습니다", "오늘 투자심리", "프리장 주요 종목",
                  "시장은 어떻게 받아들였나", "반도체주가 다시 흔들린 이유", "내일 고용보고서가 중요한 이유",
                  "유가 상승도 여전히 부담", "실적 성적표: 무엇이 예상을 넘었나", "이번 주 반드시 확인할 일정",
                  "스페이스X 실적이 테슬라에 미치는 영향", "FY27 CAPEX 계획", "브로드컴 실적",
                  "리스크 체크리스트 — 다음 분기에 확인할 것", "오늘 밤 확인할 것 셋"):
            self.assertEqual(_issues(h), [], h)

    def test_dangling_parallel_and_nominalized_endings(self) -> None:
        self.assertTrue(any("대구" in i for i in _issues("메모리는 오르고, 설계는 내리고")))
        self.assertTrue(any("명사절" in i for i in _issues("엔비디아가 산 것")))
        self.assertTrue(any("명사절" in i for i in _issues("주문잔고 950억 달러가 뜻하는 것")))

    def test_words_the_benchmark_never_uses_are_blocked_everywhere(self) -> None:
        doc = {"title": "코스피는 7,000선 앞에서 되밀렸습니다",
               "narrative": [{"heading": "1. 같은 AI 실적, 갈린 반응", "body": "금리 기대가 물러나자 올랐습니다. 돈이 간 곳은 반도체였습니다."}]}
        issues = editorial_quality.collect_issues(doc)
        for word in ("되밀", "갈린 반응", "물러나자", "돈이 간 곳"):
            self.assertTrue(any(word in i for i in issues), word)

    @unittest.skipUnless(CORPUS.exists(), "벤치마크 코퍼스는 이 컴퓨터에만 있습니다")
    def test_false_positive_rate_on_benchmark_headings(self) -> None:
        heads = []
        for path in CORPUS.glob("*.json"):
            for block in json.loads(path.read_text(encoding="utf-8"))["blocks"]:
                text = (block.get("text") or "").strip()
                if re.match(r"^\d{1,2}\.\s", text) and len(text) < 45 and "\n" not in text and "텔레그램" not in text:
                    heads.append(text)
        shape_words = ("헤드라인 꼴", "대구", "명사절")
        flagged = [h for h in heads if any(any(w in i for w in shape_words) for i in _issues(h))]
        rate = len(flagged) / max(1, len(heads))
        self.assertLess(rate, 0.03, f"벤치마크 소제목 {len(heads)}개 중 {len(flagged)}개가 걸립니다: {flagged[:10]}")


if __name__ == "__main__":
    unittest.main()
