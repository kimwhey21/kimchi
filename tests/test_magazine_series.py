"""매거진 시리즈 — 두 번째 네이버 블로그(2026-09-13, 사용자: "jeunkim처럼 다양한 분야의 글을 잡지처럼").

참고 블로그(피우스의 책도둑 & 매거진) 실측: 제목 → 📌 간단 브리핑(3~5줄) → 본문 3,700자 안팎 → 자료 출처.
그쪽 엔진은 외국 기사 전문 번역이라 따라 하지 않는다 — 꼴만 가져오고 본문은 출처 둘 이상을 종합해 우리 문장으로 쓴다.
이 글은 워드프레스에 가지 않고 두 번째 블로그에만 간다.
"""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts import naver_post, recent_titles
from src import editorial_title, feature_checks, feature_gate, source_check

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "magazine_sample.json"


def _doc() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class RegistryTest(unittest.TestCase):
    def test_the_series_is_registered_in_every_table(self) -> None:
        self.assertEqual(feature_checks.SERIES_LIMITS["매거진"], {"graphics": 0})
        self.assertEqual(editorial_title.SECTION_FLOORS["매거진"], 4)
        self.assertEqual(source_check.SERIES_MIN_SOURCES["매거진"], 2)
        self.assertEqual(feature_gate.SERIES_FOLDER["매거진"], "magazine")
        self.assertEqual(recent_titles.LISTS["magazine"], "editorial/magazine/*.json")

    def test_no_naver_twin_body_is_demanded_because_the_body_is_the_naver_body(self) -> None:
        self.assertIsNone(feature_checks.naver_spec({"series": "매거진", "date": "2026-09-14"}))


class MagazineIssuesTest(unittest.TestCase):
    def test_the_fixture_passes(self) -> None:
        self.assertEqual(feature_checks.magazine_issues(_doc()), [])

    def test_a_brief_is_neither_required_nor_checked(self) -> None:
        # 간단 브리핑은 2026-09-13 저녁 사용자 결정으로 뺐다 — 있어도 없어도 검사에 걸리지 않는다.
        doc = _doc(); doc.pop("brief", None)
        self.assertEqual(feature_checks.magazine_issues(doc), [])

    def test_group_must_be_one_of_the_six_columns(self) -> None:
        doc = _doc(); doc["group"] = "연예"
        self.assertTrue(any("코너" in i for i in feature_checks.magazine_issues(doc)))

    def test_a_translation_opening_and_a_missing_photo_block(self) -> None:
        doc = _doc()
        doc["ko"]["narrative"][0]["body"] = "이 글은 Fortune의 기사를 번역해 옮긴 것으로 " + doc["ko"]["narrative"][0]["body"]
        doc.pop("featured_photo")
        joined = "\n".join(feature_checks.magazine_issues(doc))
        self.assertIn("번역", joined)
        self.assertIn("표지 사진", joined)

    def test_the_checkpoint_date_rule_does_not_apply(self) -> None:
        # 소금의 역사에 '확인 날짜'가 있을 리 없다 — 기준표 규칙은 잡지에 걸리지 않는다.
        issues = feature_checks.collect_issues(_doc(), graphics=0)
        self.assertFalse(any("확인 날짜" in i for i in issues), issues)


class SourceTest(unittest.TestCase):
    def test_declared_sources_count_only_when_named_in_the_body(self) -> None:
        doc = _doc()
        result = source_check.collect(doc)
        self.assertGreaterEqual(result["distinct"], 2)
        doc["sources"].append({"name": "본문에 없는 기관", "title": "x"})
        result = source_check.collect(doc)
        self.assertIn("본문에 없는 기관", result["found"]["목록에만 있고 본문에 없는 출처"])
        self.assertNotIn("본문에 없는 기관", result["found"]["출처(본문에 이름이 나온 것)"])

    def test_a_single_source_article_is_blocked(self) -> None:
        doc = _doc(); doc["sources"] = doc["sources"][:1]
        self.assertTrue(source_check.collect_issues(doc))


class PosterTest(unittest.TestCase):
    def test_the_naver_post_has_body_and_sources_only(self) -> None:
        post = naver_post.build(FIXTURE)
        kinds = [k for k, _ in post["blocks"]]
        heads = [t for k, t in post["blocks"] if k == "h"]
        self.assertNotIn("📌 간단 브리핑", heads)   # 브리핑도 Take도 없다(2026-09-13 사용자 결정) — 본문 절 → 자료 출처
        self.assertNotIn("Fermata's Take", heads)
        self.assertEqual(heads[-1], "자료 출처")
        self.assertEqual(post["category"], "시장의 역사")
        self.assertEqual(post["url"], "")
        joined = "\n".join(t for _, t in post["blocks"])
        self.assertNotIn("fermata.it.kr", joined)
        self.assertNotIn("t.me/", joined)
        self.assertIn("페르마타매거진", post["tags"])
        self.assertIn("브리태니커 백과사전, Salt", joined)
        self.assertEqual(kinds.count("h"), len(_doc()["ko"]["narrative"]) + 1)   # 절 + 출처

    def test_the_title_is_left_as_written(self) -> None:
        post = naver_post.build(FIXTURE)
        self.assertEqual(post["title"], _doc()["ko"]["title"])


class GateTest(unittest.TestCase):
    def test_the_fixture_passes_the_whole_feature_gate(self) -> None:
        result = feature_gate.run(copy.deepcopy(_doc()), graphics=0, path=FIXTURE)
        self.assertEqual(result["blocking"], [])


if __name__ == "__main__":
    unittest.main()
