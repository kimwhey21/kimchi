"""주말 기준표 루틴 경로를 고정한다: 워크플로는 임시저장까지만, 지시문은 실제 도구만 가리킨다."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "feature_draft.yml"
DOC = ROOT / "docs" / "routine_feature.md"


class FeatureDraftWorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_triggers_on_feature_manuscripts_only(self) -> None:
        self.assertIn('- "editorial/features/*.json"', self.text)
        daily = (ROOT / ".github" / "workflows" / "editorial_publish.yml").read_text(encoding="utf-8")
        paths = re.findall(r'^\s+- "(editorial/[^"]+)"', daily, re.M)
        self.assertEqual(paths, ["editorial/*.json"],
                         "일간 발행 워크플로가 기준표까지 집어 가면 검수 없이 공개된다")

    def test_publishes_as_draft_by_default(self) -> None:
        self.assertIn("python -m src.publish_feature", self.text)
        self.assertNotIn("--render-only", self.text)
        # --publish는 수동 실행의 publish_live 또는 자동화 스위치(저장소 변수)가 true일 때만 붙는다.
        self.assertRegex(self.text, r'publish_live }}" = "true" \] \|\| \\\s+\[ "\$\{\{ vars\.FERMATA_AUTO_PUBLISH }}" = "true" \]; then\s+FLAG="--publish"')

    def test_has_wordpress_secrets_and_korean_font(self) -> None:
        for name in ("WORDPRESS_URL", "WORDPRESS_USERNAME", "WORDPRESS_APP_PASSWORD"):
            self.assertIn(f"secrets.{name}", self.text)
        self.assertIn("fonts-nanum", self.text)


class FeatureRoutineDocTest(unittest.TestCase):
    def test_every_command_in_the_doc_points_at_a_real_module(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        modules = set(re.findall(r"python -m ((?:src|scripts)\.[a-z_]+)", text))
        self.assertTrue(modules, "지시문에 실행할 명령이 없다")
        for module in modules:
            path = ROOT / (module.replace(".", "/") + ".py")
            self.assertTrue(path.exists(), f"{module} → {path} 없음")

    def test_doc_forbids_publishing_and_names_the_gate(self) -> None:
        text = re.sub(r"\s+", " ", DOC.read_text(encoding="utf-8"))
        self.assertIn("--publish", text)
        self.assertIn("공개는 사람이 합니다", text)
        self.assertIn("src.feature_gate", text)
        self.assertIn("--source unsplash", text)
        self.assertIn("featured_photo", text)

    def test_example_manuscript_named_in_the_doc_exists(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        for rel in re.findall(r"editorial/features/[a-z_0-9-]+\.json", text):
            if "<" in rel:
                continue
            self.assertTrue((ROOT / rel).exists(), rel)


if __name__ == "__main__":
    unittest.main()
