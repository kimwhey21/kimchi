"""피우스형 시험(2026-10-01, 사장님: "피우스처럼 가보자 테스트로 … 3편만 해보고 다시 고민해보자 가독성 부분 특히 신경쓰고").

참고 블로그 실측(10/1 최근 6편): 2,400~4,900자, 문단 44~68개(한두 문장), 📌 간단 브리핑 3~5줄, 소제목 없음, 사진 1장.
`form: pius`를 적은 잡지 원고만 이 꼴로 본다. 번역은 여전히 하지 않는다(출처 둘 이상 종합).
"""
import copy
import json
import unittest
from pathlib import Path

from scripts import naver_post
from src import feature_checks

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "magazine_sample.json"


def _sentences(n: int) -> list[str]:
    base = ["로마 병사는 소금으로 급여의 일부를 받았다고 전해집니다", "브리태니커 백과사전은 이 설이 후대의 해석일 수 있다고 적습니다",
            "미국 지질조사국은 소금이 지금도 도로 제설과 화학 공업에 가장 많이 쓰인다고 집계합니다", "마크 쿨란스키는 소금이 도시의 자리를 정했다고 씁니다",
            "소금 교역로는 사하라를 가로질러 금과 맞바꾸는 길이었습니다", "오늘날 소금 1톤은 수십 달러면 살 수 있습니다"]
    return [base[i % len(base)] + "." for i in range(n)]


def _pius_doc() -> dict:
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    doc["form"] = "pius"
    doc["brief"] = ["소금 급여 : 로마 병사가 소금으로 급여를 받았다는 설은 후대 해석일 수 있습니다.",
                    "교역로 : 사하라 소금길은 금과 소금을 맞바꾸는 길이었습니다.",
                    "지금 : 소금은 제설과 화학 공업에 가장 많이 쓰입니다."]
    # 본문 3,400자 안팎을 한두 문장 문단으로 — 피우스 호흡
    sents = _sentences(100)
    paras = [" ".join(sents[i:i + 2]) for i in range(0, len(sents), 2)]
    per = len(paras) // 5
    doc["ko"]["narrative"] = [{"heading": "", "body": "\n".join(paras[i * per:(i + 1) * per])} for i in range(5)]
    return doc


class PiusForm(unittest.TestCase):
    def test_a_good_pius_piece_passes(self) -> None:
        doc = _pius_doc()
        body = " ".join(s["body"] for s in doc["ko"]["narrative"])
        self.assertGreaterEqual(len(body), feature_checks.PIUS_CHARS[0])
        self.assertEqual(feature_checks.magazine_issues(doc), [])

    def test_ordinary_magazine_is_untouched(self) -> None:
        doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(feature_checks.magazine_issues(doc), [])     # 2,000자대·소제목 있음·브리핑 없음 그대로 통과

    def test_brief_is_required_three_to_five_lines(self) -> None:
        doc = _pius_doc(); doc["brief"] = doc["brief"][:2]
        self.assertTrue(any("브리핑" in i for i in feature_checks.magazine_issues(doc)))
        doc = _pius_doc(); doc["brief"] = ["핵심어 없이 그냥 문장만 있습니다."] * 3
        self.assertTrue(any("핵심어 : 한 문장" in i for i in feature_checks.magazine_issues(doc)))

    def test_headings_must_be_empty_and_paragraphs_short(self) -> None:
        doc = _pius_doc(); doc["ko"]["narrative"][0]["heading"] = "소제목"
        self.assertTrue(any("소제목" in i for i in feature_checks.magazine_issues(doc)))
        doc = _pius_doc(); doc["ko"]["narrative"][0]["body"] = " ".join(_sentences(5))     # 다섯 문장 한 덩어리
        issues = feature_checks.magazine_issues(doc)
        self.assertTrue(any("세 문장 이상" in i for i in issues) and any("자를 넘는 문단" in i for i in issues))

    def test_length_floor_is_higher_than_the_ordinary_magazine(self) -> None:
        doc = _pius_doc(); doc["ko"]["narrative"] = doc["ko"]["narrative"][:2]
        self.assertTrue(any("3,200" in i for i in feature_checks.magazine_issues(doc)))

    def test_naver_post_renders_brief_then_paragraphs_without_headings(self) -> None:
        doc = _pius_doc()
        tmp = ROOT / "output" / "_pius_test.json"; tmp.parent.mkdir(exist_ok=True)
        tmp.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        try:
            post = naver_post.build(tmp)
        finally:
            tmp.unlink()
        kinds = [k for k, _ in post["blocks"]]
        quotes = [t for k, t in post["blocks"] if k == "q"]
        self.assertEqual(len(quotes), 1)
        self.assertTrue(quotes[0].startswith("📌 간단 브리핑\n소금 급여 :"))
        self.assertLess(kinds.index("q"), kinds.index("p"))                      # 브리핑이 본문 앞
        heads = [t for k, t in post["blocks"] if k == "h"]
        self.assertEqual(heads, ["자료 출처"])                                     # 본문 소제목은 하나도 없다
        paras = [t for k, t in post["blocks"] if k == "p"]
        self.assertTrue(all(len(p) <= 170 for p in paras[:-3]))                  # 출처 줄 제외
        self.assertGreaterEqual(len(paras), 40)                                   # 한두 문장씩 많은 문단

    def test_ordinary_magazine_post_still_has_no_brief(self) -> None:
        post = naver_post.build(FIXTURE)
        self.assertNotIn("q", [k for k, _ in post["blocks"]])
