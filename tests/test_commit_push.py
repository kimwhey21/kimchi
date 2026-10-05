"""`scripts/commit_push.py` — 루틴의 커밋·푸시를 한 턴으로 (2026-10-05)."""
from __future__ import annotations

import unittest
from unittest import mock

from scripts import commit_push


class _Run:
    """git 호출을 흉내 낸다 — (args 튜플 → returncode, stdout, stderr)."""

    def __init__(self, table):
        self.table, self.calls = table, []

    def __call__(self, cmd, cwd=None, text=None, capture_output=None):
        args = tuple(cmd[1:])
        self.calls.append(args)
        for key, (rc, out, err) in self.table.items():
            if args[:len(key)] == key:
                return mock.Mock(returncode=rc, stdout=out, stderr=err)
        return mock.Mock(returncode=0, stdout="", stderr="")


class CommitPushTest(unittest.TestCase):
    def test_happy_path_sets_upstream_and_prints_the_hash(self) -> None:
        run = _Run({("diff", "--cached", "--quiet"): (1, "", ""), ("symbolic-ref",): (0, "claude/x\n", ""),
                    ("rev-parse",): (0, "abc1234\n", "")})
        with mock.patch.object(commit_push.subprocess, "run", run), mock.patch("builtins.print") as out:
            self.assertEqual(commit_push.main(["시황 원고: x", "editorial/kr_x.json"]), 0)
        self.assertIn(("add", "--", "editorial/kr_x.json"), run.calls)
        self.assertIn(("push", "-q", "origin", "HEAD:main"), run.calls)
        self.assertIn(("branch", "--set-upstream-to=origin/main", "claude/x"), run.calls)
        self.assertIn("abc1234", out.call_args[0][0])

    def test_rejected_push_is_retried_after_rebase(self) -> None:
        pushes = iter([(1, "", "rejected"), (0, "", "")])
        run = _Run({("diff", "--cached", "--quiet"): (1, "", "")})
        base = run.__call__

        def call(cmd, **kw):
            if tuple(cmd[1:3]) == ("push", "-q"):
                rc, o, e = next(pushes)
                run.calls.append(tuple(cmd[1:]))
                return mock.Mock(returncode=rc, stdout=o, stderr=e)
            return base(cmd, **kw)
        with mock.patch.object(commit_push.subprocess, "run", call), mock.patch.object(commit_push.time, "sleep"), \
                mock.patch("builtins.print"):
            self.assertEqual(commit_push.main(["m", "a.json"]), 0)
        self.assertEqual(sum(1 for c in run.calls if c[:2] == ("push", "-q")), 2)
        self.assertEqual(sum(1 for c in run.calls if c[:1] == ("pull",)), 2)

    def test_nothing_staged_is_fine_and_output_is_refused(self) -> None:
        run = _Run({("diff", "--cached", "--quiet"): (0, "", "")})
        with mock.patch.object(commit_push.subprocess, "run", run), mock.patch("builtins.print"):
            self.assertEqual(commit_push.main(["m", "a.json"]), 0)
        self.assertFalse(any(c[:1] == ("commit",) for c in run.calls))
        with self.assertRaises(SystemExit):
            commit_push.main(["m", "output/x.png"])

    def test_three_failures_end_with_exit_1(self) -> None:
        run = _Run({("diff", "--cached", "--quiet"): (1, "", ""), ("push",): (1, "", "403")})
        with mock.patch.object(commit_push.subprocess, "run", run), mock.patch.object(commit_push.time, "sleep"), \
                mock.patch("builtins.print"):
            self.assertEqual(commit_push.main(["m", "a.json"]), 1)


if __name__ == "__main__":
    unittest.main()
