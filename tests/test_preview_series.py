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


def _doc(series: str, sections: int = 3, chars: int = 0) -> dict:
    body = "9월 8일 밤 8월 소비자물가가 나옵니다. DART와 한국거래소 자료를 함께 봅니다."
    if chars:
        body = (body + " 근거를 하나 더 적습니다. ") * (chars // 40 + 1)
    return {"kind": "feature", "series": series,
            "ko": {"title": "오늘 밤 확인할 세 가지 — 물가와 국채금리",
                   "narrative": [{"heading": f"{i}. 절", "body": body} for i in range(1, sections + 1)],
                   "closing": {"heading": "Fermata's Take", "body": "짧게."}}}


def _preview_full() -> dict:
    """2026-09-17 문턱을 다 채운 프리뷰 — 12절·절당 400자·초보자 설명 둘·그래픽 종류 골고루·출처 넷."""
    doc = _doc("프리뷰", sections=12, chars=420)
    doc["ko"]["narrative"][1]["body"] += " 초보자 설명: bp는 0.01%포인트입니다."
    doc["ko"]["narrative"][4]["body"] += " 초보자 설명: 점도표는 위원들의 금리 전망입니다."
    doc["ko"]["narrative"][6]["body"] += " 로이터와 블룸버그, 골드만삭스와 CME 페드워치가 같은 숫자를 전했습니다."
    doc["graphics"] = [{"kind": "cover"}, {"kind": "calendar_strip", "section": 2}, {"kind": "fact_table", "section": 3},
                       {"kind": "price_history", "section": 4}, {"kind": "number_cards", "section": 0},
                       {"kind": "valuation_bars", "section": 6}, {"kind": "checklist", "section": 10},
                       {"kind": "rate_compare", "section": 5}, {"kind": "movers_list", "section": 8}]
    return doc


class PreviewThresholdsTest(unittest.TestCase):
    """프리뷰는 2026-09-17부터 그날 미국장의 메인 글이다(사장님: "1번2번3번 진행").

    절 10·시각자료 8·출처 4, 그리고 9/15 합본 실험에서 드러난 셋 — 절당 400자, 같은 그래픽 2장,
    초보자 상자 둘. 2026-09-08의 "3절·600~900자" 프리뷰는 표에서 가장 얇은 글이었다.
    """

    def test_the_old_three_section_preview_is_now_too_thin(self) -> None:
        issues = (editorial_title.collect_issues(_doc("프리뷰"), kind="프리뷰")
                  + feature_checks.collect_issues(_doc("프리뷰"), graphics=3))
        self.assertTrue(any("10개 이상" in i for i in issues), issues)
        self.assertTrue(any("시각자료" in i for i in issues), issues)
        self.assertTrue(any("절이 얕습니다" in i for i in issues), issues)
        self.assertTrue(any("초보자 설명이" in i for i in issues), issues)

    def test_a_full_preview_passes_the_volume_rules(self) -> None:
        doc = _preview_full()
        issues = feature_checks.collect_issues(doc, graphics=8)
        self.assertFalse([i for i in issues if "얕습니다" in i or "시각자료" in i or "초보자 설명이" in i or "같은 종류" in i], issues)
        self.assertEqual([i for i in editorial_title.collect_issues(doc, kind="프리뷰") if "개 이상" in i], [])

    def test_same_graphic_kind_is_capped_at_two(self) -> None:
        doc = _preview_full()
        doc["graphics"] += [{"kind": "number_cards", "section": 1}, {"kind": "number_cards", "section": 3}]
        issues = feature_checks.collect_issues(doc, graphics=10)
        self.assertTrue(any("number_cards" in i and "같은 종류" in i for i in issues), issues)

    def test_feature_thresholds_are_unchanged(self) -> None:
        issues = (editorial_title.collect_issues(_doc("기준표"), kind="기준표")
                  + feature_checks.collect_issues(_doc("기준표"), graphics=2))
        self.assertTrue(any("절이 3개" in i for i in issues), issues)
        self.assertTrue(any("시각자료가 2장" in i for i in issues), issues)
        self.assertFalse(any("얕습니다" in i for i in issues), issues)   # 절당 글자 규칙은 프리뷰에만

    def test_preview_needs_four_sources_and_feature_three(self) -> None:
        self.assertTrue(source_check.collect_issues(_doc("프리뷰")))            # 둘로는 모자란다(2026-09-17)
        self.assertEqual(source_check.collect_issues(_preview_full()), [])
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
        # 2026-09-17 밤: 12절 개정 때 「앞을 보는 제목」 줄이 빠져 어젯밤 요약형 제목이 나갔다. 사장님이 정한 규칙
        # 문구는 여기 바늘로 박아 둔다 — 문서를 다시 쓸 때 사라지면 이 테스트가 잡는다(scripts/rule_diff도 같이 쓴다).
        for needle in ('"프리뷰"', "휴장", "--graphics", "category_id` 121", "바로 공개", "예측하지 않습니다",
                       "앞을 보는 제목", "시간 축", "22:00", "절마다 **400자", "초보자 설명 둘 이상", "월가 리포트",
                       "나올 수 있는 결과 셋", "대응 원칙", "핵심 내용", "지어내지 않습니다"):
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
