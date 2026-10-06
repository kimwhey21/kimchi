"""`scripts/commit_push.py` — 루틴의 커밋·푸시를 한 턴으로 (2026-10-05)."""
from __future__ import annotations

import unittest
from unittest import mock

from scripts import commit_push


class _Run:
    """git 호출을 흉내 낸다 — (args 튜플 → returncode, stdout, stderr)."""

    def __init__(self, table):
        self.table, self.calls = table, []

    def __call__(self, cmd, cwd=None, text=None, capture_output=None, env=None):
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


class GuardTest(unittest.TestCase):
    """공개 저장소 지키기(감사 F-113·F-114·F-163)."""

    def test_owner_quote_in_message_is_refused(self) -> None:
        with self.assertRaises(SystemExit):
            commit_push.main(["고침(" + "사장" + '님: "이렇게")', "editorial/kr_x.json"])   # 이 파일이 시험에 걸리지 않게 나눠 적는다

    def test_code_commit_runs_the_tests_first(self) -> None:
        calls = []

        def run(cmd, **kw):
            calls.append(cmd)
            return mock.Mock(returncode=1, stdout="", stderr="FAIL: test_x (t.T)\n")
        with mock.patch.object(commit_push.subprocess, "run", run):
            with self.assertRaises(SystemExit) as ctx:
                commit_push.main(["고침", "src/x.py"])
        self.assertIn("시험이 통과하지 않아", str(ctx.exception))
        self.assertIn("unittest", calls[0])

    def test_commit_uses_the_noreply_address(self) -> None:
        seen = []

        def run(cmd, **kw):
            seen.append(cmd)
            rc = 1 if cmd[:3] == ["git", "diff", "--cached"] else 0
            return mock.Mock(returncode=rc, stdout="abc\n", stderr="")
        with mock.patch.object(commit_push.subprocess, "run", run), mock.patch("builtins.print"):
            commit_push.main(["원고", "editorial/kr_x.json"])
        commit = next(c for c in seen if "commit" in c)
        self.assertIn(f"user.email={commit_push.NOREPLY}", commit)
