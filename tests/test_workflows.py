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


class MarketBriefIsFetchOnlyTest(unittest.TestCase):
    """예약 시세 수집은 시세만 커밋하고 루틴을 깨웁니다 — 초안을 만들지 않습니다.

    2026-09-07에 단순화한 구조입니다. 그 전에는 같은 워크플로가 규칙 기반 초안을
    워드프레스 draft로 매일 올렸는데, 규칙상 절대 공개되지 않는 부산물이 관리자
    화면 맨 위에 쌓여 "데이터만 나열한 글"로 오인됐고, 초안 검사가 죽으면 시세
    커밋까지 같이 죽었습니다(2026-09-04). 누가 편의상 `--fetch-only`를 빼거나
    워드프레스 시크릿을 다시 넘기면 여기서 걸립니다.
    """

    def setUp(self) -> None:
        root = Path(__file__).resolve().parent.parent / ".github" / "workflows"
        self.market_brief = (root / "market_brief.yml").read_text(encoding="utf-8")
        self.publish_check = (root / "publish_check.yml").read_text(encoding="utf-8")

    def test_scheduled_fetch_is_fetch_only(self) -> None:
        self.assertIn("--fetch-only", self.market_brief)

    def test_fetch_job_has_no_wordpress_secrets(self) -> None:
        """시세 수집에 워드프레스 비밀번호가 필요 없습니다. 최소 권한."""
        self.assertNotIn("WORDPRESS_APP_PASSWORD", self.market_brief)

    def test_fetch_job_fires_the_routine(self) -> None:
        """시세 커밋 직후 루틴을 API 트리거로 깨웁니다 — 예약 지연(2026-09-07,
        2시간 8분)과 무관하게 글이 나가게 하는 장치입니다."""
        self.assertIn("ROUTINE_KR_FIRE_TOKEN", self.market_brief)
        self.assertIn("/fire", self.market_brief)
        # 호출 실패가 워크플로를 실패시키면 안 됩니다 — 예비 예약이 대신 돕습니다.
        self.assertIn("루틴 자체 예약이 대신 돕니다", self.market_brief)

    def test_publish_check_runs_after_the_fallback_routine(self) -> None:
        """검사는 예비 예약(17:40/08:40 KST)까지 끝난 뒤에 돌아야 헛경보가 없습니다.
        2026-09-07에 17:35 검사가 실패 메일을 보냈는데 글은 19:05에 정상 공개됐습니다."""
        self.assertIn('cron: "0 10 * * 1-5"', self.publish_check)   # 19:00 KST
        self.assertIn('cron: "0 1 * * 2-6"', self.publish_check)    # 10:00 KST 다음날
        self.assertNotIn('cron: "20 8 * * 1-5"', self.publish_check)


if __name__ == "__main__":
    unittest.main()
