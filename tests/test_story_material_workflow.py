"""주말 기준표 재료를 Actions가 미리 커밋하는 워크플로를 고정한다.

루틴 샌드박스는 야후 파이낸스에 연결하지 못해(2026-09-07 실측) 미국장 재료가
비었다. Actions 러너는 되므로 토·일 아침 루틴보다 먼저 두 시장의 엔진 출력을
data/engines_<market>_<날짜>.txt로 남긴다.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "story_material.yml"
DOC = ROOT / "docs" / "routine_feature.md"


class StoryMaterialWorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_runs_before_the_routines(self) -> None:
        """주말 루틴은 토·일 00:00 UTC, 프리뷰 루틴은 평일 12:30 UTC. 재료는 그보다 앞선다.

        평일 재료는 **11:40 UTC**(2026-09-25) — GitHub 예약이 실측 18~22분 늦게 떠서 12:10 예약은 12:28~12:32에
        커밋됐고, 프리뷰 루틴(12:30 예약, 실측 12:31~35 시작)과 경주가 됐다(9/14 실제 발생). 12:00 UTC보다 앞이어야 한다.
        """
        crons = re.findall(r'- cron: "([^"]+)"', self.text)
        parsed = {(c.split()[1], c.split()[4]): int(c.split()[0]) for c in crons}
        self.assertIn(("23", "5,6"), parsed)
        self.assertIn(("11", "1-5"), parsed, "평일 재료 예약은 12시(UTC) 전이어야 합니다 — 예약 지연 20분을 견디게")
        self.assertNotIn(("12", "1-5"), parsed, "12:10 UTC 예약은 프리뷰 루틴과 경주가 됩니다(2026-09-14 실제 발생)")
        self.assertLess(parsed[("23", "5,6")], 40, "주말 루틴이 뜨기 전에 커밋이 끝나야 합니다")
        self.assertGreaterEqual(parsed[("11", "1-5")], 30, "너무 이르면 미국장 프리마켓 전 데이터가 얕습니다")

    def test_covers_both_markets_and_keeps_failures_visible(self) -> None:
        self.assertIn("for m in us kr", self.text)
        self.assertIn("python -m src.story_engines all --market", self.text)
        self.assertIn("|| true", self.text, "엔진 하나가 죽어도 나머지 재료는 남겨야 합니다")
        self.assertIn("data/engines_", self.text)

    def test_has_only_free_data_keys_and_no_wordpress_secrets(self) -> None:
        for name in ("FRED_API_KEY", "ECOS_API_KEY"):
            self.assertIn(f"secrets.{name}", self.text)
        for name in ("WORDPRESS", "ANTHROPIC", "OPENAI", "UNSPLASH"):
            self.assertNotIn(name, self.text)

    def test_routine_doc_reads_the_material_file_first(self) -> None:
        text = re.sub(r"\s+", " ", DOC.read_text(encoding="utf-8"))
        self.assertIn("data/engines_", text)
        self.assertIn("story_material.yml", text)


if __name__ == "__main__":
    unittest.main()
