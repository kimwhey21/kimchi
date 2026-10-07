"""Cloudflare 예비 예약 표(cloudflare/backup_cron/jobs.json)가 깃허브 워크플로의 cron과 맞는지 본다 (2026-09-29).

워크플로 예약 시각을 바꾸고 표를 안 고치면 예비 장치가 엉뚱한 시각에 확인하거나, 멀쩡한 날에도 대신 누른다.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOBS = json.loads((ROOT / "cloudflare" / "backup_cron" / "jobs.json").read_text(encoding="utf-8"))


def crons(workflow: str) -> set[tuple[str, str]]:
    text = (ROOT / ".github" / "workflows" / workflow).read_text(encoding="utf-8")
    out = set()
    for minute, hour, dow in re.findall(r'cron:\s*"(\d+) (\d+) \* \* ([\d,\-]+)"', text):
        out.add((f"{int(hour):02d}:{int(minute):02d}", dow))
    return out


# 종가 사진은 깃허브 예약(:32/:40/:48)보다 1분 일찍 누른다 — 러너가 뜨는 시간까지 15:31~15:59 창 안에 넣으려고
KRX_EARLY = {("06:31", "1-5"), ("06:39", "1-5"), ("06:47", "1-5")}


def minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


class BackupCronTest(unittest.TestCase):
    def test_watch_matches_workflow_cron(self):
        for job in JOBS["watch"]:
            with self.subTest(job=job):
                self.assertIn((job["due"], job["days"]), crons(job["workflow"]))
                gap = minutes(job["check"]) - minutes(job["due"])
                self.assertTrue(15 <= gap <= 40, "확인은 예정 15~40분 뒤 — 깃허브 평소 지연(18~22분)보다 늦고 루틴 예비 예약보다 이르게")

    def test_direct_times_are_workflow_crons(self):
        for job in JOBS["direct"]:
            for t in job["utc"]:
                with self.subTest(workflow=job["workflow"], at=t):
                    self.assertIn((t, job["days"]), crons(job["workflow"]) | KRX_EARLY)

    def test_every_scheduled_workflow_is_pressed_on_time(self):
        pressed = {(j["workflow"], t, j["days"]) for j in JOBS["direct"] for t in j["utc"]}
        pressed |= {(j["workflow"], j["due"], j["days"]) for j in JOBS["watch"]}
        for path in (ROOT / ".github" / "workflows").glob("*.yml"):
            if path.name == "krx_close.yml":
                continue
            for due, dow in crons(path.name):
                if any(w == dow and 0 < minutes(due) - minutes(d) <= 30 for d, w in crons(path.name)):
                    continue   # 30분 안의 재시도(:27/:34)는 깃허브 예약으로만 — 앞 실행이 실패했을 때만 돈다(skip_guard mode success)
                with self.subTest(workflow=path.name, due=due):
                    self.assertIn((path.name, due, dow), pressed)

    def test_scheduled_workflows_skip_when_already_run(self):
        modes = {"market_brief.yml": "success", "publish_check.yml": "any"}
        for path in (ROOT / ".github" / "workflows").glob("*.yml"):
            text = path.read_text(encoding="utf-8")
            if "schedule:" not in text:
                continue
            with self.subTest(workflow=path.name):
                self.assertIn("uses: ./.github/workflows/skip_guard.yml", text)
                self.assertIn("if: needs.guard.outputs.run == 'true'", text)
                self.assertIn(f"mode: {modes.get(path.name, 'active')}", text)

    def test_guard_never_blocks_manual_or_on_lookup_failure(self):
        text = (ROOT / ".github" / "workflows" / "skip_guard.yml").read_text(encoding="utf-8")
        self.assertIn('[ "$EVENT" = "schedule" ] || go true', text)
        self.assertIn('|| go true "최근 실행 조회에 실패해 그대로 돕니다"', text)
        # 몇 시간 늦게 몰려온 예약은 '예약 시각 이후에 같은 작업이 돈 적이 있으면' 건너뛰고, 없으면 늦게라도 돈다(2026-10-06, 감사 F-037)
        self.assertIn('if [ "$late" -gt 120 ]; then', text)
        self.assertIn('since=$(date -u -d "@$((sched - 600))"', text)
        self.assertNotIn('[ "$late" -gt 120 ] && go false', text)
        self.assertIn("CRON: ${{ github.event.schedule }}", text)

    def test_krx_commit_survives_missing_folder(self):
        text = (ROOT / ".github" / "workflows" / "krx_close.yml").read_text(encoding="utf-8")
        self.assertLess(text.index("[ -d data/krx_close ] ||"), text.index("git add data/krx_close"))

    def test_krx_direct_inside_close_window(self):
        job = next(j for j in JOBS["direct"] if j["workflow"] == "krx_close.yml")
        for t in job["utc"]:
            kst = minutes(t) + 9 * 60
            # 러너가 뜨는 데 1~2분 — 사진은 15:31~15:59 KST 창 안에서, 종가 잠그기(15:53)는 15:51~16:19 창 안에서 끝나야 한다
            self.assertTrue(15 * 60 + 31 <= kst <= 15 * 60 + 50 or 15 * 60 + 51 <= kst <= 15 * 60 + 55, t)

    def test_late_close_presses(self):
        """수능일(16:30 마감)용: 종가 사진 16:35·16:45 KST(창 16:31~16:59 안), 한국장 수집 16:50 KST는 late_close_only로."""
        late = [j for j in JOBS["direct"] if j["workflow"] == "krx_close.yml"][1]
        self.assertTrue(all(16 * 60 + 31 <= minutes(t) + 9 * 60 <= 16 * 60 + 55 for t in late["utc"]))   # 16:53은 수능일 종가 잠그기
        job = next(j for j in JOBS["direct"] if j["workflow"] == "market_brief.yml" and "07:50" in j["utc"])
        self.assertEqual(job["inputs"].get("late_close_only"), "true")

    def test_market_inputs(self):
        for job in JOBS["direct"] + JOBS["watch"]:
            if job["workflow"] == "market_brief.yml":
                first = (job.get("utc") or [job.get("due")])[0]
                self.assertEqual(job["inputs"]["market"], "us" if first.startswith("22") else "kr")

    def test_worker_has_placeholder_and_no_secrets(self):
        src = (ROOT / "cloudflare" / "backup_cron" / "worker.js").read_text(encoding="utf-8")
        self.assertIn("const JOBS = __JOBS__;", src)
        self.assertNotRegex(src, r"github_pat_|ghp_|\d{9,}:[A-Za-z0-9_-]{30,}")


if __name__ == "__main__":
    unittest.main()
