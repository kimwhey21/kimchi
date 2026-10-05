"""깃허브 러너는 파이썬 3.11이다 — 이 맥(3.12+)에서만 되는 f-문자열 문법을 미리 잡는다(2026-10-06).

3.12부터 f-문자열 중괄호 안에 역슬래시·같은 따옴표를 쓸 수 있다(PEP 701). 3.11은 그 파일을 아예 못 읽는다(SyntaxError) —
10/6 07:20 수집의 경고 모으기가 그렇게 깃허브에서만 죽었다. `ast.parse(feature_version=(3, 11))`로는 잡히지 않아 토큰을 직접 본다.
"""
from __future__ import annotations

import io
import sys
import tokenize
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def violations(path: Path) -> list[str]:
    out = []
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(path.read_text(encoding="utf-8")).readline))
    except (tokenize.TokenError, SyntaxError) as exc:
        return [f"{path}: 토큰을 읽지 못함 {exc}"]
    stack: list[str] = []          # 열린 f-문자열의 따옴표
    for tok in tokens:
        if tok.type == tokenize.FSTRING_START:
            stack.append(tok.string.lstrip("rRbBfFuU")[:1])
        elif tok.type == tokenize.FSTRING_END:
            stack.pop() if stack else None
        elif stack and tok.type != tokenize.FSTRING_MIDDLE:
            if "\\" in tok.string:
                out.append(f"{path.relative_to(ROOT)}:{tok.start[0]} f-문자열 중괄호 안 역슬래시")
            if tok.type == tokenize.STRING and tok.string.lstrip("rRbBuU")[:1] == stack[-1]:
                out.append(f"{path.relative_to(ROOT)}:{tok.start[0]} f-문자열 중괄호 안에 같은 따옴표")
    return out


@unittest.skipIf(sys.version_info < (3, 12), "3.12 미만은 파일을 읽는 것 자체가 3.11 문법 시험이다")
class Py311SyntaxTest(unittest.TestCase):
    def test_no_312_only_fstrings(self) -> None:
        found = []
        for folder in ("src", "scripts", "tests"):
            for path in sorted((ROOT / folder).rglob("*.py")):
                found += violations(path)
        self.assertEqual(found, [], "\n".join(found))


if __name__ == "__main__":
    unittest.main()
