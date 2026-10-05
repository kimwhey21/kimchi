"""넓은 예외 처리(`except Exception`·맨 `except`)가 흔적 없이 넘기지 못하게 한다 (2026-10-05 코드 전수 정리).

9/17 지수 원천이 2주 멈춘 것을 아무도 몰랐던 뿌리는 "실패해도 조용히 넘어가는 자리"였다. 넓은 예외 처리는 다음 중 하나를 해야 한다 —
다시 올린다(raise) · 이유를 찍거나 알린다(print·send·warn) · 목록에 적는다(append·extend·add) · 센다(`+= 1`) · 오류를 돌려준다
(`return` 값, `row["error"] = …`). 이도 저도 아니면 except 줄에 `# 무시:`로 왜 괜찮은지 적어야 한다(다른 후보를 이어서 시도하는 자리 등).
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {"trend_queue.py"}   # 커밋되지 않은 다른 세션의 초안


def _broad(handler: ast.ExceptHandler) -> bool:
    t = handler.type
    if t is None:
        return True
    names = [t] if not isinstance(t, ast.Tuple) else list(t.elts)
    return any(isinstance(n, ast.Name) and n.id in ("Exception", "BaseException") for n in names)


def _leaves_a_trace(body: list[ast.stmt]) -> bool:
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, (ast.Raise, ast.AugAssign)):
            return True
        if isinstance(node, ast.Return) and node.value is not None and not (
                isinstance(node.value, ast.Constant) and node.value.value in (None, False)):
            return True
        if isinstance(node, ast.Call):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
            if name in ("print", "send", "warn", "warning", "error", "exception", "append", "extend", "add", "write"):
                return True
        if isinstance(node, ast.Assign) and any(isinstance(v, ast.JoinedStr) for v in ast.walk(node.value)):
            return True          # 실패 문구를 만들어 담는다(spec_issues = [f"… {exc}"])
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Subscript) for t in node.targets):
            return True          # row["error"] = … 처럼 결과에 실패를 적는다
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ("last", "error", "last_error", "err") for t in node.targets):
            return True          # 재시도 루프가 마지막 오류를 들고 있다가 끝에서 올린다
    return False


class NoSilentExceptTest(unittest.TestCase):
    def test_every_broad_except_leaves_a_trace_or_says_why(self) -> None:
        bad = []
        for path in sorted(list((ROOT / "src").glob("*.py")) + list((ROOT / "scripts").glob("*.py"))):
            if path.name in SKIP:
                continue
            text = path.read_text(encoding="utf-8")
            lines = text.splitlines()
            for node in ast.walk(ast.parse(text)):
                if isinstance(node, ast.ExceptHandler) and _broad(node) and not _leaves_a_trace(node.body):
                    if "# 무시:" not in lines[node.lineno - 1]:
                        bad.append(f"{path.relative_to(ROOT)}:{node.lineno}  {lines[node.lineno - 1].strip()}")
        self.assertEqual(bad, [], "흔적 없이 넘기는 넓은 예외 처리:\n" + "\n".join(bad))


if __name__ == "__main__":
    unittest.main()
