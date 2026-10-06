"""마감 지난 결과물 알림(2026-10-06, 감사 F-064·F-112)."""
from __future__ import annotations

import datetime as dt
import unittest
from unittest import mock

from scripts import artifact_watch
from src import daily_proof

KST = daily_proof.KST


class ArtifactWatchTest(unittest.TestCase):
    def test_only_items_whose_due_just_passed(self) -> None:
        self.assertEqual(artifact_watch.due_now(dt.datetime(2026, 10, 6, 22, 40, tzinfo=KST)), {"미국장 프리뷰"})
        self.assertEqual(artifact_watch.due_now(dt.datetime(2026, 10, 6, 9, 40, tzinfo=KST)), {"주간 점검"})   # 09:00 것은 다시 안 본다
        self.assertEqual(artifact_watch.due_now(dt.datetime(2026, 10, 6, 15, 0, tzinfo=KST)), set())

    def test_every_due_has_a_press_ten_minutes_later(self) -> None:
        import json
        from pathlib import Path
        jobs = json.loads((Path(__file__).resolve().parents[1] / "cloudflare" / "backup_cron" / "jobs.json").read_text(encoding="utf-8"))
        presses = next(j["utc"] for j in jobs["direct"] if j["workflow"] == "artifact_watch.yml")
        for name, hhmm in daily_proof.ARTIFACT_DUE.items():
            due = dt.datetime.combine(dt.date(2026, 10, 6), dt.time(*map(int, hhmm.split(":"))), tzinfo=KST)
            covered = any(due <= dt.datetime.combine(dt.date(2026, 10, 6), dt.time(*map(int, p.split(":"))), tzinfo=dt.timezone.utc).astimezone(KST).replace(
                year=2026, month=10, day=6) < due + dt.timedelta(minutes=artifact_watch.WINDOW_MINUTES) for p in presses)
            with self.subTest(name=name):
                self.assertTrue(covered, f"{name}({hhmm}) 마감 뒤 30분 안에 누르는 시각이 없습니다")

    def test_missing_preview_is_reported(self) -> None:
        now = dt.datetime(2026, 10, 6, 22, 40, tzinfo=KST)
        with mock.patch.object(daily_proof, "changed_today", return_value=set()), \
                mock.patch.object(daily_proof, "expected_artifacts",
                                  return_value=[("미국장 프리뷰", False, "editorial/previews/us_2026-10-06.json"), ("잡지 3편", False, "x")]):
            self.assertEqual(artifact_watch.missing(now), ["미국장 프리뷰 — editorial/previews/us_2026-10-06.json"])


if __name__ == "__main__":
    unittest.main()
