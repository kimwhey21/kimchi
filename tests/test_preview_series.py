"""저녁 「미국장 브리핑」(시리즈 키는 그대로 '프리뷰')을 기준표 파이프라인 위에 고정한다.

2026-09-16에 미국장 시황과 합쳤다(사용자 결정). 전에는 밤 10시 프리뷰(절 3·시각자료 3·출처 2)와
이튿날 아침 시황이 따로였는데, 하루 한 편이 그날 미국장 보도의 전부가 되면서 **문턱을 시황 쪽으로
올렸다** — 절 11·시각자료 8·출처 4. 얇아지면 합칠 이유가 없어지므로 이 문턱이 곧 합친 이유다.
기준표의 문턱(5·6·3)은 그대로여야 한다.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from src import editorial_title, feature_checks, source_check

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "preview_publish.yml"
DOC = ROOT / "docs" / "routine_preview.md"


def _doc(series: str, sections: int = 3) -> dict:
    body = "9월 8일 밤 8월 소비자물가가 나옵니다. DART와 한국거래소 자료를 함께 봅니다."
    return {"kind": "feature", "series": series,
            "ko": {"title": "오늘 밤 확인할 세 가지 — 물가와 국채금리",
                   "narrative": [{"heading": f"{i}. 절", "body": body} for i in range(1, sections + 1)],
                   "closing": {"heading": "Fermata's Take", "body": "짧게."}}}


def _full_doc() -> dict:
    """합친 뒤의 브리핑 — 절 11·시각자료 8·출처 4를 채운 원고."""
    doc = _doc("프리뷰", sections=11)
    doc["ko"]["narrative"][0]["body"] = (
        "9월 8일 밤 8월 소비자물가가 나옵니다. 로이터와 블룸버그가 같은 숫자를 전했고, "
        "한국거래소와 DART 자료로 한국 쪽 연결을 확인했습니다.")
    return doc


class PreviewThresholdsTest(unittest.TestCase):
    def test_a_thin_preview_is_now_blocked(self) -> None:
        """옛 문턱(절 3·시각자료 3)짜리 글은 이제 막힌다 — 그게 합친 이유다."""
        issues = (editorial_title.collect_issues(_doc("프리뷰"), kind="프리뷰")
                  + feature_checks.collect_issues(_doc("프리뷰"), graphics=3))
        self.assertTrue(any("절이 3개" in i for i in issues), issues)
        self.assertTrue(any("시각자료가 3장" in i for i in issues), issues)

    def test_a_full_length_brief_passes(self) -> None:
        issues = (editorial_title.collect_issues(_full_doc(), kind="프리뷰")
                  + feature_checks.collect_issues(_full_doc(), graphics=8))
        self.assertFalse([i for i in issues if "절이" in i or "시각자료" in i], issues)

    def test_feature_thresholds_are_unchanged(self) -> None:
        issues = (editorial_title.collect_issues(_doc("기준표"), kind="기준표")
                  + feature_checks.collect_issues(_doc("기준표"), graphics=2))
        self.assertTrue(any("절이 3개" in i for i in issues), issues)
        self.assertTrue(any("시각자료가 2장" in i for i in issues), issues)

    def test_preview_needs_four_sources_after_the_merge(self) -> None:
        """출처 둘로는 더 이상 통과하지 못한다 — 어젯밤 마감과 오늘 밤 일정을 함께 다루니
        확인해야 할 곳도 늘었다."""
        self.assertTrue(source_check.collect_issues(_doc("프리뷰")))
        self.assertEqual(source_check.collect_issues(_full_doc()), [])
        self.assertTrue(source_check.collect_issues(_doc("기준표")))


class PreviewWorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_publishes_live_on_preview_commits(self) -> None:
        self.assertIn('- "editorial/previews/*.json"', self.text)
        self.assertIn('python -m src.publish_feature "$f" --publish', self.text)
        self.assertNotIn("--render-only", self.text)
        for name in ("WORDPRESS_URL", "WORDPRESS_USERNAME", "WORDPRESS_APP_PASSWORD"):
            self.assertIn(f"secrets.{name}", self.text)
        self.assertIn("fonts-nanum", self.text)

    def test_other_publishers_do_not_pick_previews(self) -> None:
        daily = (ROOT / ".github" / "workflows" / "editorial_publish.yml").read_text(encoding="utf-8")
        feature = (ROOT / ".github" / "workflows" / "feature_draft.yml").read_text(encoding="utf-8")
        self.assertNotIn("previews", daily)
        self.assertNotIn("previews", feature)


class PreviewDocTest(unittest.TestCase):
    def test_commands_point_at_real_modules(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        for module in set(re.findall(r"python -m ((?:src|scripts)\.[a-z_]+)", text)):
            self.assertTrue((ROOT / (module.replace(".", "/") + ".py")).exists(), module)

    def test_doc_names_the_series_and_skip_rules(self) -> None:
        text = re.sub(r"\s+", " ", DOC.read_text(encoding="utf-8"))
        for needle in ('"프리뷰"', "휴장", "--graphics", "category_id` 121", "바로 공개", "예측하지 않습니다"):
            self.assertIn(needle, text, needle)


if __name__ == "__main__":
    unittest.main()
