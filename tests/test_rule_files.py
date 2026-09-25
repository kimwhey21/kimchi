"""규칙 파일이 실제 저장소와 어긋나면 잡습니다.

왜 필요한가
-----------
2026-09-06에 규칙 파일 두 개를 대조해 봤더니 이랬습니다.

    CLAUDE.md에만    자동 발행·워치리스트·사진 출처 규칙 15개
    AGENTS.md에만    "디버깅할 때 원인을 추측만으로 단정하지 말 것" 외 24개

머리말은 "내용은 거의 동일"이라고 적혀 있었습니다. **그 '거의'가 문제입니다** —
Codex가 AGENTS.md를 읽고 Claude가 CLAUDE.md를 읽는데 둘이 다르면, 한쪽이 이미
배운 교훈을 다른 쪽이 그대로 다시 겪습니다.

같은 날 더 나쁜 것도 찾았습니다. 그날 만든 도구 여섯 개(`publish_feature`,
`feature_gate`, `source_check`, `photo_search`, `title_helper`, `bench_watch`)가
규칙 파일에 **0회** 나왔습니다. 도구를 만들어 놓고 규칙에 적지 않으면 다음
세션은 그 도구가 있는 줄도 모르고 처음부터 헤맵니다.

그래서 세 가지를 확인합니다.

1. 공유하는 네 절은 두 파일이 글자까지 같을 것
2. 규칙이 이름을 댄 모듈·스크립트가 실제로 있을 것
3. 발행 도구를 규칙이 실제로 가리킬 것
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLAUDE = ROOT / "CLAUDE.md"
AGENTS = ROOT / "AGENTS.md"

# 두 파일이 **글자까지** 같아야 하는 절.
#
# 2026-09-06에는 앞의 두 절(「검증 규칙」·「비용/자동 발행 원칙」)을 일부러 뺐습니다 — AGENTS.md가
# 도구를 특정하지 않으려고 표현만 달리 써 두었고, 틀리게 우는 검사는 곧 무시당하기 때문입니다.
# 2026-09-25에 내력을 docs/decisions.md로 갈라 내며 두 파일의 네 절을 같은 문장으로 통일했습니다
# (AGENTS.md에만 있던 규칙 둘 — "예문을 늘린다"·featured_tickers 편성 — 은 CLAUDE.md에 합쳤습니다).
# 이제 네 절 전부를 글자 대조합니다. 도구 이름(`Read` 툴·WebSearch)은 AGENTS.md 머리말이
# "같은 일을 하는 자기 도구로 읽는다"로 풀어 둡니다.
_SHARED = ("## 검증 규칙 (반드시 지킬 것)", "## 비용/자동 발행 원칙", "## 기준표(feature) 글", "## 발행 워크플로우")


def _section(text: str, heading: str) -> str:
    start = text.index(heading)
    nxt = text.find("\n## ", start + len(heading))
    return text[start:nxt if nxt != -1 else len(text)].strip()


class SharedSectionsTest(unittest.TestCase):
    def test_shared_sections_are_identical(self) -> None:
        claude, agents = CLAUDE.read_text(encoding="utf-8"), AGENTS.read_text(encoding="utf-8")
        for heading in _SHARED:
            with self.subTest(section=heading):
                self.assertIn(heading, claude)
                self.assertIn(heading, agents)
                self.assertEqual(
                    _section(claude, heading), _section(agents, heading),
                    f"{heading} 절이 두 파일에서 다릅니다. 한쪽만 고치면 다른 도구가 "
                    f"옛 규칙을 읽습니다 — 양쪽에 같이 반영하십시오.")


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
        for path in (CLAUDE, AGENTS):
            text = path.read_text(encoding="utf-8")
            for named in sorted(set(self._PATH.findall(text))):
                if "<" in named or "*" in named:
                    continue                    # `editorial/*.json` 같은 자리표시자
                with self.subTest(rule_file=path.name, named=named):
                    self.assertTrue((ROOT / named).exists(),
                                    f"{path.name}이 {named}을 가리키는데 파일이 없습니다.")

    def test_named_modules_import(self) -> None:
        import importlib
        for path in (CLAUDE, AGENTS):
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
        for path in (CLAUDE, AGENTS):
            text = path.read_text(encoding="utf-8")
            for tool in self._MUST_APPEAR:
                with self.subTest(rule_file=path.name, tool=tool):
                    self.assertIn(tool, text,
                                  f"{path.name}에 {tool}이 없습니다. 도구를 만들었으면 "
                                  f"규칙에 적으십시오 — 적지 않으면 없는 것과 같습니다.")


if __name__ == "__main__":
    unittest.main()
