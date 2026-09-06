"""자동 실행 워크플로가 실패를 숨기지 않는지 봅니다.

왜 필요한가
-----------
자동화에서 가장 나쁜 실패는 **초록 체크로 끝나는 실패**입니다. 2026-09-03
아침에 워크플로가 성공으로 끝났는데 한국장 글은 올라가지 않았고, 알아챈 것은
사람이 사이트를 열어봤기 때문이었습니다.

2026-09-06에 그 침묵의 원인을 하나 더 찾았습니다 — `publish_editorial`이
워드프레스 설정이 없으면 "업로드를 건너뜁니다"라고만 찍고 정상 종료했습니다.
이제는 예외로 멈추고, `--render-only`를 붙일 때만 조용히 끝냅니다.

그래서 **자동 실행에는 그 깃발이 절대 붙으면 안 됩니다.** 붙는 순간 설정
누락이 다시 성공으로 보입니다. 사람이 기억하는 대신 여기서 막습니다.
"""
from __future__ import annotations

import unittest
from pathlib import Path

WORKFLOWS = sorted((Path(__file__).resolve().parent.parent / ".github" / "workflows").glob("*.yml"))


class WorkflowsDoNotSilenceFailuresTest(unittest.TestCase):
    def test_workflows_exist(self) -> None:
        self.assertTrue(WORKFLOWS, ".github/workflows에 워크플로가 없습니다.")

    def test_no_render_only_in_automation(self) -> None:
        for path in WORKFLOWS:
            with self.subTest(workflow=path.name):
                self.assertNotIn(
                    "--render-only", path.read_text(encoding="utf-8"),
                    f"{path.name}에 --render-only가 있습니다. 이 깃발은 워드프레스 "
                    f"설정이 없어도 조용히 성공으로 끝냅니다 — 자동 실행에 붙이면 "
                    f"발행 실패가 초록 체크로 보입니다.")

    def test_tests_workflow_installs_a_korean_font(self) -> None:
        """그림 테스트가 두부(□)를 그리고도 통과하지 않게 합니다."""
        tests_yml = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "tests.yml"
        self.assertIn("fonts-nanum", tests_yml.read_text(encoding="utf-8"),
                      "tests.yml에 한글 폰트 설치가 없습니다. 폰트가 없으면 "
                      "data_graphics가 한글을 두부로 그리는데 예외가 나지 않습니다.")

    def test_no_paid_api_keys_reach_actions(self) -> None:
        """유료 생성 경로를 자동 실행에 다시 연결하지 않습니다(CLAUDE.md 규칙)."""
        for path in WORKFLOWS:
            text = path.read_text(encoding="utf-8")
            for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
                with self.subTest(workflow=path.name, key=key):
                    self.assertNotIn(key, text,
                                     f"{path.name}에 {key}가 있습니다. 유료 생성 경로는 "
                                     f"자동 실행에 연결하지 않습니다.")


if __name__ == "__main__":
    unittest.main()
