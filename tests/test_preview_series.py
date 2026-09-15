"""밤 10시 미국장 프리뷰(시리즈 '프리뷰')를 기준표 파이프라인 위에 고정한다.

새 파이프라인을 만들지 않고 관문·렌더·발행을 그대로 쓰되 문턱만 다르다:
절 3개·시각자료 2장·출처 2곳. 기준표의 문턱(5·6·3)은 그대로여야 한다.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from src import editorial_title, feature_checks, source_check

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "preview_publish.yml"
DOC = ROOT / "docs" / "routine_preview.md"


def _doc(series: str) -> dict:
    body = "9월 8일 밤 8월 소비자물가가 나옵니다. DART와 한국거래소 자료를 함께 봅니다."
    return {"kind": "feature", "series": series,
            "ko": {"title": "오늘 밤 확인할 세 가지 — 물가와 국채금리",
                   "narrative": [{"heading": f"{i}. 절", "body": body} for i in range(1, 4)],
                   "closing": {"heading": "Fermata's Take", "body": "짧게."}}}


class PreviewThresholdsTest(unittest.TestCase):
    def test_preview_accepts_three_sections_and_two_graphics(self) -> None:
        issues = feature_checks.collect_issues(_doc("프리뷰"), graphics=3)   # 표지 + 본문 둘 (2026-09-08)
        self.assertFalse([i for i in issues if "절이" in i or "시각자료" in i], issues)

    def test_feature_thresholds_are_unchanged(self) -> None:
        issues = (editorial_title.collect_issues(_doc("기준표"), kind="기준표")
                  + feature_checks.collect_issues(_doc("기준표"), graphics=2))
        self.assertTrue(any("절이 3개" in i for i in issues), issues)
        self.assertTrue(any("시각자료가 2장" in i for i in issues), issues)

    def test_preview_needs_two_sources_and_feature_three(self) -> None:
        self.assertEqual(source_check.collect_issues(_doc("프리뷰")), [])
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


class PreviewPrivateTest(unittest.TestCase):
    """프리뷰는 본진에 **비공개**로만 올린다(2026-09-15, 사용자 지시).

    네이버에 본문 전문이 나가는데 본진에도 같은 글을 공개해 두면 네이버가 유사문서로 걸러 낼 수
    있다. 시황은 본진에 아예 안 올리는 쪽을 골랐고, 프리뷰는 글을 남기되 사이트에 보이지 않게 한다 —
    워드프레스 `private`는 주소·분류를 그대로 두고 사이트맵·목록·피드에서만 뺀다.
    """

    def test_only_the_preview_series_goes_out_private(self) -> None:
        """2026-09-15 저녁에 Checkpoint(`기준표`)도 같은 처리로 들어왔다(사용자: "체크포인트는 2번").

        **가이드는 일부러 빠져 있다**(같은 결정의 "가이드는 3번") — 구글 유입이 거기서만 나오므로
        본진에 공개로 남겨야 한다. 이 목록에 가이드를 더하지 말 것.
        """
        from src import publish_feature
        for series in ("프리뷰", "기준표"):
            with self.subTest(series=series):
                self.assertEqual(publish_feature._live_status({"series": series}), "private")
        for series in ("가이드", "Guide", "주간 결산", "다음 주 일정", "이벤트"):
            with self.subTest(series=series):
                self.assertEqual(publish_feature._live_status({"series": series}), "publish")

    def test_a_private_post_is_not_announced_with_a_dead_link(self) -> None:
        """비공개 글의 본진 주소는 독자에게 404다 — 그 링크로 텔레그램·스레드에 알리면 안 된다.

        알림은 맥의 동기화가 네이버에 올린 뒤 네이버 주소로 보낸다(scripts/notify_naver_post.py).
        """
        import inspect

        from src import publish_feature
        source = inspect.getsource(publish_feature.publish)
        self.assertIn('if live and wanted == "publish":', source)
