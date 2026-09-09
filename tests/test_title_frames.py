"""같은 틀 반복을 막는다 (2026-09-09, 사용자 네 번째 지적 "여전히 제목과 소제목은 똑같구나").

낱개 규칙을 다 지키고도 매일 같은 틀이 나왔다 — 제목은 대비형('…했는데 …는 오히려')
아니면 '…, N월 N일에 갈린다', 소제목은 열에 아홉이 '~습니다' 문장. 최근 글과 대조해 막는다.
"""
from __future__ import annotations

import unittest

from src import editorial_title
from src.editorial_title import collect_issues, frame_issues, heading_mix_issues


class TitleFrameTest(unittest.TestCase):
    def test_checkpoint_list_that_the_user_saw_is_blocked(self) -> None:
        recent = ["SK하이닉스 지금 사도 될까? 10월 27일에 갈린다",
                  "금리는 올랐는데 은행주만 무너진 이유, 9월 11일에 갈린다"]
        issues = frame_issues("트랙터 회사가 사상 최고가, 바닥은 11월 25일에 갈린다", recent)
        self.assertTrue(any("갈린다" in i for i in issues), issues)

    def test_synonym_endings_count_as_the_same(self) -> None:
        issues = frame_issues("두산에너빌리티 급등에 외국인은 팔았다, 9월 8일 회담이 가른다",
                              ["마이크론을 던진 펀드들과 코튜, 9월 30일에 갈린다"])
        self.assertTrue(issues, "가른다=갈린다")

    def test_contrast_frame_only_once_in_five(self) -> None:
        recent = ["고용지표에 지수는 하락했는데 메모리 반도체만 오른 이유"]
        issues = frame_issues("중동 리스크에 뉴욕증시는 하락했는데, 반도체는 오히려 갈렸습니다", recent)
        self.assertTrue(any("대비" in i for i in issues), issues)

    def test_different_frames_pass(self) -> None:
        recent = ["고용지표에 지수는 하락했는데 메모리 반도체만 오른 이유",
                  "금리 인상 확률이 내려오자 뉴욕증시는 3거래일 만에 반등했다",
                  "델 15.81% 급등의 이유, AI 서버 주문잔고 950억 달러"]
        self.assertEqual(frame_issues("유가 급등에 다우가 밀린 날, 반도체 안에서는 승자가 바뀌었습니다", recent), [])

    def test_no_recent_titles_means_no_frame_check(self) -> None:
        self.assertEqual(frame_issues("트랙터 회사가 사상 최고가, 바닥은 11월 25일에 갈린다", []), [])

    def test_collect_issues_passes_recent_titles_through(self) -> None:
        doc = {"title": "트랙터 회사가 사상 최고가, 바닥은 11월 25일에 갈린다",
               "narrative": [{"heading": f"{i}. 오늘 볼 것 {i}", "body": "b"} for i in range(1, 6)]}
        blocked = collect_issues(doc, kind="기준표", recent_titles=["SK하이닉스 지금 사도 될까? 10월 27일에 갈린다"])
        self.assertTrue(any("갈린다" in i for i in blocked), blocked)
        self.assertEqual(collect_issues(doc, kind="기준표"), [])


class HeadingMixTest(unittest.TestCase):
    US_0908 = ["위험과 로테이션이 같은 하루에 겹쳤습니다", "숫자로 본 오늘", "지난 거래일 확인 지점, 오늘은 어땠나",
               "중동이 다시 유가를 밀어 올렸습니다", "캐나다도 관세로 맞받았습니다", "다우와 나스닥, 등락률이 세 배 갈렸습니다",
               "인텔, 상향과 가격 인상 소식에 올랐습니다", "오늘 크게 움직인 반도체·AI 인프라 종목들",
               "루멘텀, 실적과 가이던스가 함께 왔습니다", "블룸에너지는 S&P500 편입 소식에 올랐습니다",
               "마이크론과 엔비디아는 반대로 눌렸습니다", "테슬라, 인텔과 예상 밖의 연결고리",
               "유가가 국채금리를 다시 밀어 올렸습니다", "다음 한국장으로 넘어갈 연결고리"]

    @staticmethod
    def _sections(headings):
        return [{"heading": f"{i}. {h}", "body": "b"} for i, h in enumerate(headings, 1)]

    def test_all_polite_sentences_are_blocked(self) -> None:
        heads = [f"코스피는 {i}포인트 올랐습니다" for i in range(10)]
        issues = heading_mix_issues(self._sections(heads))
        self.assertTrue(any("문장입니다" in i for i in issues), issues)

    def test_todays_us_post_is_caught(self) -> None:
        issues = heading_mix_issues(self._sections(self.US_0908))
        self.assertTrue(any("문장입니다" in i for i in issues) and any("이름, …" in i for i in issues), issues)

    def test_benchmark_like_mix_passes(self) -> None:
        heads = ["오늘 투자심리", "프리장 주요 종목", "호르무즈 협상이 다시 교착 상태에 빠졌습니다",
                 "시장은 어떻게 받아들였나", "반도체주가 다시 흔들린 이유", "이번 주 반드시 확인할 일정",
                 "유가 상승도 여전히 부담", "엔비디아는 전력 회사를 샀습니다", "외국인 수급", "다음 거래일에 볼 것"]
        self.assertEqual(heading_mix_issues(self._sections(heads)), [])

    def test_short_posts_are_not_measured(self) -> None:
        self.assertEqual(heading_mix_issues(self._sections(["코스피는 올랐습니다"] * 4)), [])

    def test_shape_classifier(self) -> None:
        self.assertEqual(editorial_title.heading_shape("숫자로 본 오늘"), "이름표")
        self.assertEqual(editorial_title.heading_shape("시장은 어떻게 받아들였나"), "질문")
        self.assertEqual(editorial_title.heading_shape("유가 상승도 여전히 부담"), "이름표")
        self.assertEqual(editorial_title.heading_shape("금리는 반대로 갔다"), "반말 문장")


if __name__ == "__main__":
    unittest.main()


class GateWiringTest(unittest.TestCase):
    """관문이 실제로 최근 글을 넘기는지 — 이 배선이 빠지면 규칙은 있어도 아무것도 막지 않는다."""

    def test_feature_gate_recent_titles_excludes_itself(self) -> None:
        import json
        from pathlib import Path
        from src import feature_gate
        path = Path("editorial/features/kr_2026-09-06_hynix_per.json")
        doc = json.loads(path.read_text(encoding="utf-8"))
        titles = feature_gate.recent_titles(doc, path)
        self.assertTrue(titles)
        self.assertNotIn(doc["ko"]["title"], titles)
        self.assertLessEqual(len(titles), 5)

    def test_daily_gate_passes_previous_titles(self) -> None:
        from unittest.mock import patch
        from src import editorial_gate, editorial_judgment
        seen: dict = {}
        real = editorial_title.collect_issues

        def spy(doc, price_data=None, **kwargs):
            seen["recent"] = kwargs.get("recent_titles")
            return real(doc, price_data, **kwargs)

        previous = [{"ko": {"title": "고용지표에 지수는 하락했는데 메모리 반도체만 오른 이유"}}]
        with patch.object(editorial_judgment, "previous_manuscripts", return_value=previous), \
             patch.object(editorial_judgment, "previous_manuscript", return_value=None), \
             patch.object(editorial_gate.editorial_title, "collect_issues", side_effect=spy):
            try:
                editorial_gate.run(__import__("pathlib").Path("editorial/kr_2026-09-08.json"))
            except Exception:  # noqa: BLE001 - 렌더 실패 여부는 이 테스트의 관심이 아니다
                pass
        self.assertEqual(seen.get("recent"), ["고용지표에 지수는 하락했는데 메모리 반도체만 오른 이유"])

    def test_recent_titles_script_lists_what_to_avoid(self) -> None:
        from scripts import recent_titles
        out = recent_titles.render("checkpoint")
        self.assertIn("피할 것", out)
        self.assertIn("끝내지 않기", out)
