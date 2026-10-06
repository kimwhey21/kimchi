"""잡지 기본 꼴(2026-10-03~, 피우스형) — 소제목 없이 한두 문장 문단, 사람의 말을 그대로 옮긴 문단, 2,400~4,800자, 같은 문단 반복 금지.

참고 블로그 실측(10/1 최근 6편): 2,400~4,900자, 문단 44~68개(한두 문장), 소제목 없음, 사진 1장.
간단 브리핑은 2026-10-02 사장님 결정으로 뺐다. 옛 꼴(소제목·400자 절)은 `form: classic` 원고만이다.
고정 예시는 tests/fixtures/magazine_sample.json(관문 통과본, 루틴 프롬프트가 이 이름을 읽는다). 옛 꼴은 magazine_sample_classic.json.
"""
import copy
import json
import unittest
from pathlib import Path

from scripts import naver_post
from src import feature_checks, feature_gate

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "magazine_sample.json"
CLASSIC = ROOT / "tests" / "fixtures" / "magazine_sample_classic.json"


def _doc() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _paras(doc: dict) -> list[str]:
    return [p for s in doc["ko"]["narrative"] for p in s["body"].split("\n") if p.strip()]


class DefaultForm(unittest.TestCase):
    def test_the_new_fixture_passes(self) -> None:
        doc = _doc()
        self.assertNotIn("form", doc)                          # 아무것도 적지 않으면 새 꼴이다
        self.assertTrue(feature_checks.is_pius(doc))
        self.assertEqual(feature_checks.magazine_issues(doc), [])

    def test_the_new_fixture_passes_the_whole_gate(self) -> None:
        # 근거 표의 원문은 실제 출처 페이지로 통과를 확인했다(2026-10-06). 시험은 바깥에 접속하지 않으므로 그 원문들을 담은 가짜 페이지로 본다.
        from unittest import mock
        from src import evidence_check
        doc = copy.deepcopy(_doc())
        page = evidence_check.normalize(" ".join(e["original"] for e in doc["evidence"]))
        with mock.patch.object(evidence_check, "page_text", lambda url: page):
            result = feature_gate.run(doc, graphics=0, path=FIXTURE)
        self.assertEqual(result["blocking"], [])

    def test_classic_manuscripts_keep_the_old_form(self) -> None:
        doc = json.loads(CLASSIC.read_text(encoding="utf-8"))
        self.assertFalse(feature_checks.is_pius(doc))
        self.assertEqual(feature_checks.magazine_issues(doc), [])

    def test_a_direct_quote_is_required(self) -> None:
        doc = _doc()
        for s in doc["ko"]["narrative"]:
            s["body"] = "\n".join(p for p in s["body"].split("\n") if not p.startswith("“"))
        self.assertTrue(any("그대로 옮긴 문단" in i for i in feature_checks.magazine_issues(doc)))

    def test_repeated_paragraphs_are_blocked(self) -> None:
        """2026-10-02 핵심광물 편: 분량을 채우려고 같은 문단 세 쌍이 들어간 채 올라갔다."""
        doc = _doc()
        doc["ko"]["narrative"][-1]["body"] += "\n" + _paras(doc)[0]
        self.assertTrue(any("되풀이" in i for i in feature_checks.magazine_issues(doc)))

    def test_headings_and_long_paragraphs_are_blocked(self) -> None:
        doc = _doc(); doc["ko"]["narrative"][0]["heading"] = "소제목"
        self.assertTrue(any("소제목" in i for i in feature_checks.magazine_issues(doc)))
        doc = _doc(); doc["ko"]["narrative"][0]["body"] = " ".join(_paras(_doc())[:6])
        issues = feature_checks.magazine_issues(doc)
        self.assertTrue(any("자를 넘는 문단" in i for i in issues) or any("세 문장 이상" in i for i in issues))

    def test_length_floor_does_not_block_but_the_ceiling_does(self) -> None:
        """2026-10-05: 하한 2,400자가 늘리기를 만들었다(아홉 편 전부 2,394~2,486자, 강조어로 채움) — 참고값으로만 둔다."""
        self.assertEqual(feature_checks.PIUS_CHARS, (2400, 4800))
        doc = _doc(); doc["ko"]["narrative"] = doc["ko"]["narrative"][:2]
        self.assertFalse(any("자입니다" in i for i in feature_checks.magazine_issues(doc)))
        doc = _doc(); doc["ko"]["narrative"][0]["body"] = ("아주 긴 문장입니다. " * 9 + "\n") * 60
        self.assertTrue(any("4,800자 이하" in i for i in feature_checks.magazine_issues(doc)))

    def test_brief_is_not_required_or_rendered(self) -> None:
        """2026-10-02 결정: 잡지에는 간단 브리핑을 싣지 않는다."""
        doc = _doc(); doc["brief"] = ["핵심 : 이런 줄이 있어도", "싣지 : 않습니다", "셋째 : 줄"]
        self.assertEqual(feature_checks.magazine_issues(doc), [])
        tmp = ROOT / "output" / "_pius_test.json"; tmp.parent.mkdir(exist_ok=True)
        tmp.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        try:
            post = naver_post.build(tmp)
        finally:
            tmp.unlink()
        self.assertNotIn("q", [k for k, _ in post["blocks"]])
        self.assertNotIn("간단 브리핑", "\n".join(t for _, t in post["blocks"]))

    def test_naver_post_has_short_paragraphs_and_no_headings(self) -> None:
        post = naver_post.build(FIXTURE)
        heads = [t for k, t in post["blocks"] if k == "h"]
        self.assertEqual(heads, ["자료 출처"])
        body = [t for k, t in post["blocks"] if k == "p"][: -len(_doc()["sources"])]
        self.assertTrue(all(len(p) <= 170 for p in body))
        self.assertGreaterEqual(len(body), 40)
        self.assertTrue(any(p.startswith("“") for p in body))      # 인용 문단이 그대로 따로 실린다
