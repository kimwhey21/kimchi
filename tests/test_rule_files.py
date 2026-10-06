"""규칙 파일(CLAUDE.md)이 실제 저장소와 어긋나면 잡습니다.

왜 필요한가
-----------
2026-09-06에 그날 만든 도구 여섯 개(`publish_feature`, `feature_gate`, `source_check`,
`photo_search`, `title_helper`, `bench_watch`)가 규칙 파일에 **0회** 나왔습니다. 도구를 만들어
놓고 규칙에 적지 않으면 다음 세션은 그 도구가 있는 줄도 모르고 처음부터 헤맵니다.

그래서 두 가지를 확인합니다.

1. 규칙이 이름을 댄 모듈·스크립트가 실제로 있을 것
2. 발행 도구를 규칙이 실제로 가리킬 것

(예전에는 다른 도구용 사본과 네 절이 같은지도 봤습니다 — 2026-09-28에 그 도구를 쓰지 않기로 하며 사본을 지웠습니다.)
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLAUDE = ROOT / "CLAUDE.md"
OPS = ROOT / "docs" / "ops.md"   # 운영 규칙(2026-10-05에 CLAUDE.md에서 옮김) — 같은 검사를 받는다


class RulesPointAtRealCodeTest(unittest.TestCase):
    """규칙이 댄 이름이 실제로 있는지 봅니다.

    지운 파일을 가리키는 규칙은 없느니만 못합니다 — 읽는 쪽이 찾다가 시간을
    버리고, 없는 걸 근거로 판단합니다.
    """

    # 백틱 안의 `src/...py`·`scripts/...py`·`docs/...md`·`config/...yaml` 꼴
    _PATH = re.compile(r"`((?:src|scripts|docs|config|tests|state)/[\w./-]+\.(?:py|md|ya?ml|json))`")
    # `python -m src.foo` / `python -m scripts.bar` 꼴
    _MODULE = re.compile(r"python3? -m ((?:src|scripts)\.[\w.]+)")

    def test_named_files_exist(self) -> None:
        for path in (CLAUDE, OPS):
            text = path.read_text(encoding="utf-8")
            for named in sorted(set(self._PATH.findall(text))):
                if "<" in named or "*" in named:
                    continue                    # `editorial/*.json` 같은 자리표시자
                with self.subTest(rule_file=path.name, named=named):
                    self.assertTrue((ROOT / named).exists(),
                                    f"{path.name}이 {named}을 가리키는데 파일이 없습니다.")

    def test_named_modules_import(self) -> None:
        import importlib
        for path in (CLAUDE, OPS):
            text = path.read_text(encoding="utf-8")
            for module in sorted(set(self._MODULE.findall(text))):
                with self.subTest(rule_file=path.name, module=module):
                    try:
                        importlib.import_module(module)
                    except ImportError as error:   # 선택 의존성은 넘어갑니다
                        self.skipTest(f"{module}: {error}")


class TodaysToolsAreDocumentedTest(unittest.TestCase):
    """오늘 만든 도구가 규칙에 적혀 있는지 봅니다.

    2026-09-06에 이 여섯 개가 규칙 파일에 0회였습니다. 도구가 있어도 규칙이
    가리키지 않으면 다음 세션은 없는 것처럼 일합니다 — 사진을 한 장씩 여섯 번
    들이밀고, 제목을 네 번 고치고, 검사를 빼먹습니다. 전부 그날 실제로 한 일입니다.
    """

    _MUST_APPEAR = ("publish_feature", "feature_gate", "source_check",
                    "photo_search", "title_helper", "story_engines")

    def test_publishing_tools_are_named(self) -> None:
        for path in (CLAUDE,):
            text = path.read_text(encoding="utf-8")
            for tool in self._MUST_APPEAR:
                with self.subTest(rule_file=path.name, tool=tool):
                    self.assertIn(tool, text,
                                  f"{path.name}에 {tool}이 없습니다. 도구를 만들었으면 "
                                  f"규칙에 적으십시오 — 적지 않으면 없는 것과 같습니다.")


if __name__ == "__main__":
    unittest.main()


class OpsSplitTest(unittest.TestCase):
    """2026-10-05: 운영 규칙을 docs/ops.md로 옮겼다. 규칙 파일이 그 문서를 가리키고, 세 절의 안내가 남아 있어야 한다."""

    def test_rule_file_points_to_ops(self) -> None:
        text = CLAUDE.read_text(encoding="utf-8")
        self.assertIn("docs/ops.md", text)
        self.assertGreaterEqual(text.count("`docs/ops.md` 「"), 3)
        self.assertLess(len(text), 25000, "규칙 파일이 다시 커졌습니다 — 운영 규칙은 docs/ops.md에 적으십시오")


class NoOwnerQuotesTest(unittest.TestCase):
    """공개 저장소에 사장님 말을 옮기지 않는다(CLAUDE.md 머리말, 감사 F-113) — 호칭 뒤 쌍점이나 따옴표가 오는 꼴을 막는다."""

    def test_public_files_carry_no_owner_quotes(self) -> None:
        import re
        root = Path(__file__).resolve().parents[1]
        quote = re.compile(r"사장님[^\n]{0,2}[:：]|사장님이?\s*[\"“]")
        bad = []
        import subprocess
        tracked = set(subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True).stdout.splitlines())
        for folder in ("src", "scripts", "tests", "docs", "templates", "config", ".github"):
            for path in (root / folder).rglob("*"):
                if path.suffix not in (".py", ".md", ".yml", ".yaml", ".php", ".json", ".html", ".j2") or not path.is_file():
                    continue
                if tracked and str(path.relative_to(root)) not in tracked:
                    continue   # 커밋되지 않은 다른 세션의 초안은 보지 않는다
                for n, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                    if quote.search(line) and "quote = re.compile" not in line:
                        bad.append(f"{path.relative_to(root)}:{n}")
        for n, line in enumerate((root / "CLAUDE.md").read_text(encoding="utf-8").splitlines(), 1):
            if quote.search(line):
                bad.append(f"CLAUDE.md:{n}")
        self.assertEqual(bad, [])
