"""네이버 글이 본진 원고를 **빠짐없이** 담는지 (2026-09-16).

왜 이 검사가 있는가
-------------------
2026-09-15에 시황을 "네이버 전용, 본문 전문"으로 바꾸면서 본문을 어디서 가져오는지만
갈아 끼우고 끝냈다. 그 결과 `outlook`·`insight_section`·`sources`가 네이버에 실리지
않은 채로 남았고(그 셋은 **처음부터** 한 번도 실린 적이 없었다), 본진을 비공개로 돌리자
아무 데도 실리지 않게 됐다. 하루 800~1,500자였다.

그때 테스트가 있었지만 전부 "내가 바꾼 것이 바뀌었나"만 물었다 — 링크 없음, Take 위치,
`chars > 2600`. 2,600자는 옛 요약본 상한 아래라 28% 결손을 통과시킨다. 그래서 이 파일은
**원고의 덩어리를 하나씩 세어** 네이버 블록에 들어갔는지 본다. 원고에 새 항목이 생겨도
여기서 걸린다.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from scripts import naver_post

ROOT = Path(__file__).resolve().parent.parent


def squash(value) -> str:
    """태그를 떼고 공백을 전부 없앤 꼴. 문단 나누기·태그 제거 방식 차이를 지운다."""
    return re.sub(r"\s+", "", re.sub(r"<[^>]+>", " ", str(value or "")))


def naver_text(post: dict) -> str:
    return squash(" ".join(str(b[1]) for b in post["blocks"] if b[0] in ("h", "p", "q")))


class DailyCompletenessTest(unittest.TestCase):
    """한국어 시황: 본진 `templates/post.html.j2`가 싣는 것을 네이버도 전부 싣는다."""

    manuscript = ROOT / "editorial" / "kr_2026-09-15.json"

    def setUp(self) -> None:
        self.doc = json.loads(self.manuscript.read_text(encoding="utf-8"))
        self.ko = self.doc["ko"]
        self.post = naver_post.build(self.manuscript)
        self.text = naver_text(self.post)

    def test_every_narrative_section_is_carried(self) -> None:
        for i, section in enumerate(self.ko["narrative"]):
            with self.subTest(section=i):
                self.assertIn(squash(section["body"])[:30], self.text)
                self.assertIn(squash(section["heading"])[:20], self.text)

    def test_outlook_is_carried(self) -> None:
        """「다음 거래일에 확인할 것」 — 독자가 가장 원하는 절인데 2026-09-16 전까지 한 번도 안 갔다."""
        body = (self.ko.get("outlook") or {}).get("body")
        self.assertTrue(body, "표본 원고에 outlook이 없습니다 — 다른 원고로 바꾸십시오")
        self.assertIn(squash(body)[:30], self.text)

    def test_insight_section_is_carried_with_its_table(self) -> None:
        """「이날 눈여겨볼 것」 — 그날 조사가 가장 많이 들어간 부분이고 자체 표를 갖는다."""
        stories = (self.ko.get("insight_section") or {}).get("stories") or []
        self.assertTrue(stories, "표본 원고에 insight_section이 없습니다 — 다른 원고로 바꾸십시오")
        for i, story in enumerate(stories):
            with self.subTest(story=i):
                self.assertIn(squash(story["body"])[:30], self.text)
                for row in story.get("table") or []:
                    self.assertIn(squash(row["label"]), self.text)
                    self.assertIn(squash(row.get("value")), self.text)

    def test_sources_are_carried(self) -> None:
        srcs = self.ko.get("sources") or self.doc.get("sources") or []
        self.assertTrue(srcs, "표본 원고에 sources가 없습니다 — 다른 원고로 바꾸십시오")
        for s in srcs:
            self.assertIn(squash(s["name"]), self.text)

    def test_closing_and_check_are_carried(self) -> None:
        closing = self.ko.get("closing") or {}
        self.assertIn(squash(closing["body"])[:30], self.text)
        self.assertIn(squash((closing.get("check") or {}).get("what"))[:30], self.text)


class GraphicsGoUnderTheirOwnSectionTest(unittest.TestCase):
    """그림은 **그 절 밑**에 붙는다.

    2026-09-15까지는 종류 선호 순서(`GRAPHIC_PREFERENCE`)로 다시 줄을 세워 앞 네 장만 잘라
    0~3번 절에 붙였다. 그래서 「미국 국채금리가 5%를 터치했습니다」 절 밑에 원익홀딩스
    +19.44% 카드가 붙어 있었다(네이버에 올라간 글에서 실제로 확인). 절 번호로 붙이는 규칙을
    되돌리면 이 검사가 잡는다.
    """

    def _placement(self, manuscript: Path, graphics: Path) -> list[tuple[str, str]]:
        post = naver_post.build(manuscript, graphics)
        out, heading = [], "(표지)"
        for kind, value in post["blocks"]:
            if kind == "h":
                heading = value
            elif kind == "img":
                out.append((heading, Path(value).name))
        return out

    def test_daily_graphics_match_their_section(self) -> None:
        manuscript = ROOT / "editorial" / "kr_2026-09-15.json"
        graphics = ROOT / "output" / "gate" / "kr_2026-09-15"
        if not graphics.exists():
            self.skipTest("렌더된 그림이 없습니다 (python -m src.editorial_gate 로 만듭니다)")
        doc = json.loads(manuscript.read_text(encoding="utf-8"))
        sections = doc["ko"]["narrative"]
        for heading, filename in self._placement(manuscript, graphics):
            if heading == "(표지)":
                continue
            number = int(filename[:2])                       # 파일 앞 두 자리 = 절 번호(1부터)
            with self.subTest(file=filename):
                self.assertLessEqual(number, len(sections), filename)
                expected = re.sub(r"^\s*\d{1,2}\.\s*", "", str(sections[number - 1]["heading"]))
                self.assertEqual(heading, expected, f"{filename}이 남의 절에 붙었습니다")

    def test_no_four_image_cap(self) -> None:
        """4장 상한이 되살아나면 잡는다 — 요약본 시절(절 4~6개)의 치수였다."""
        graphics = ROOT / "output" / "gate" / "kr_2026-09-15"
        if not graphics.exists():
            self.skipTest("렌더된 그림이 없습니다")
        drawn = [f for f in graphics.glob("*.*") if "cover" not in f.name]
        placed = self._placement(ROOT / "editorial" / "kr_2026-09-15.json", graphics)
        self.assertEqual(len([p for p in placed if p[0] != "(표지)"]), len(drawn))


class SummaryPostsAreUnchangedTest(unittest.TestCase):
    """가이드도 전문·링크 없음이다(2026-09-22, 사장님: "링크를 모두 빼고 본문을 공개하고 본진에서는 비공개").

    2026-09-15에는 본진에 공개된 쌍둥이가 있어 요약 + 링크로 뒀었다. 본진이 비공개가 되면서 그 이유가 없어졌다.
    """

    def test_guide_is_the_full_body_with_no_link(self) -> None:
        path = ROOT / "editorial" / "guides" / "ko_isa-vs-pension-accounts.json"
        post = naver_post.build(path)
        doc = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(post["url"], "")
        self.assertFalse(any(b[0] == "q" for b in post["blocks"]), "전문에는 인용구 Take가 없다")
        self.assertFalse(any("fermata.it.kr" in b[1] for b in post["blocks"]))
        heads = [b[1] for b in post["blocks"] if b[0] == "h"]
        for section in doc["ko"]["narrative"]:
            self.assertIn(re.sub(r"^\s*\d{1,2}\.\s*", "", section["heading"]), heads)   # 절이 다 실린다


if __name__ == "__main__":
    unittest.main()
