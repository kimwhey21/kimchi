"""샌드박스 준비 명령 — 이미 되어 있으면 아무것도 깔지 않고, 안 되면 무엇이 안 됐는지 적고 1로 끝난다."""
from __future__ import annotations

import contextlib
import io
import unittest
from unittest.mock import patch

from scripts import sandbox_ready


def _main() -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = sandbox_ready.main()
    return code, out.getvalue()


class SandboxReadyTest(unittest.TestCase):
    def test_ready_environment_installs_nothing(self) -> None:
        with patch.object(sandbox_ready, "pillow_works", return_value=True), \
             patch.object(sandbox_ready, "has_font", return_value=True), \
             patch.object(sandbox_ready, "_run") as run:
            code, text = _main()
        self.assertEqual(code, 0)
        self.assertEqual(text.strip(), "준비됨")
        run.assert_not_called()

    def test_broken_pillow_is_reinstalled_with_this_python(self) -> None:
        state = {"ok": False}

        def run(command, timeout=300):
            if "pip" in command:
                self.assertEqual(command[0], sandbox_ready.sys.executable)
                self.assertIn("--ignore-installed", command)
                state["ok"] = True
            return True

        with patch.object(sandbox_ready, "pillow_works", side_effect=lambda: state["ok"]), \
             patch.object(sandbox_ready, "has_font", return_value=True), \
             patch.object(sandbox_ready, "_run", side_effect=run):
            code, text = _main()
        self.assertEqual(code, 0)
        self.assertIn("Pillow 다시 설치", text)
        self.assertTrue(text.strip().endswith("준비됨"))

    def test_font_install_refreshes_the_package_list_when_the_first_try_fails(self) -> None:
        calls = []

        def run(command, timeout=300):
            calls.append(command[:2])
            return command[:2] != ["apt-get", "install"] or ["apt-get", "update"] in calls

        with patch.object(sandbox_ready, "pillow_works", return_value=True), \
             patch.object(sandbox_ready, "has_font", return_value=False), \
             patch.object(sandbox_ready.shutil, "which", return_value="/usr/bin/apt-get"), \
             patch.object(sandbox_ready, "_run", side_effect=run):
            code, text = _main()
        self.assertEqual(calls, [["apt-get", "install"], ["apt-get", "update"], ["apt-get", "install"]])
        self.assertEqual(code, 1)   # 폰트가 끝내 없으면 준비 안 됨
        self.assertIn("한글 폰트가 없습니다", text)
