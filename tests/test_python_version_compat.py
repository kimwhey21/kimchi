"""저장소 전체가 워크플로의 파이썬(3.11)에서 파싱되는지 봅니다.

2026-09-06에 f-string 안에 같은 따옴표를 중첩했습니다. 그 문법은 3.12부터라
로컬(3.14)에서는 통과하고 워크플로(3.11)에서만 SyntaxError로 죽었습니다.
푸시하고 CI가 빨간 X를 내고 나서야 알았습니다.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# .github/workflows/tests.yml의 python-version과 맞춥니다.
TARGET = (3, 11)


class PythonVersionCompatTest(unittest.TestCase):
    def test_all_sources_parse_on_workflow_python(self) -> None:
        failures = []
        for folder in ("src", "scripts", "tests"):
            for path in sorted((ROOT / folder).rglob("*.py")):
                try:
                    ast.parse(path.read_text(encoding="utf-8"), feature_version=TARGET)
                except SyntaxError as exc:
                    failures.append(f"{path.relative_to(ROOT)}:{exc.lineno} {exc.msg}")
        self.assertEqual(
            failures, [],
            "파이썬 %d.%d에서 파싱되지 않는 파일이 있습니다:\n  " % TARGET
            + "\n  ".join(failures))


if __name__ == "__main__":
    unittest.main()
