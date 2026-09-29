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

    def test_every_scheduled_workflow_is_covered(self):
        watched = {(j["workflow"], j["due"], j["days"]) for j in JOBS["watch"]}
        for path in (ROOT / ".github" / "workflows").glob("*.yml"):
            for due, dow in crons(path.name):
                if path.name == "krx_close.yml":
                    continue
                if any(w == dow and 0 < minutes(due) - minutes(d) <= 30 for d, w in crons(path.name)):
                    continue   # 30분 안의 재시도(:27/:34)는 첫 예약 하나로 본다
                with self.subTest(workflow=path.name, due=due):
                    self.assertIn((path.name, due, dow), watched)

    def test_krx_direct_inside_close_window(self):
        job = JOBS["direct"][0]
        self.assertEqual(job["workflow"], "krx_close.yml")
        for t in job["utc"]:
            kst = minutes(t) + 9 * 60
            # 러너가 뜨는 데 1~2분 — 15:31~15:59 KST 창 안에서 끝나야 한다
            self.assertTrue(15 * 60 + 31 <= kst <= 15 * 60 + 50, t)

    def test_market_inputs(self):
        for job in JOBS["watch"]:
            if job["workflow"] == "market_brief.yml":
                self.assertEqual(job["inputs"]["market"], "us" if job["due"].startswith("22") else "kr")

    def test_worker_has_placeholder_and_no_secrets(self):
        src = (ROOT / "cloudflare" / "backup_cron" / "worker.js").read_text(encoding="utf-8")
        self.assertIn("const JOBS = __JOBS__;", src)
        self.assertNotRegex(src, r"github_pat_|ghp_|\d{9,}:[A-Za-z0-9_-]{30,}")


if __name__ == "__main__":
    unittest.main()
