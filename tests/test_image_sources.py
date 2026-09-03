"""사진 출처가 Unsplash -> 위키미디어 순으로 동작하는지 확인합니다.

두 번째 경로는 검색어가 아니라 종목(엔티티)으로 찾습니다. 검색어로 찾으면
저장소가 여러 번 겪은 실패가 재현되기 때문입니다 — 위키데이터에서 '카카오'를
이름으로 검색하면 카카오 열매 항목이 먼저 나오고, 그 항목 사진은 페루 아마존
풍경입니다. 그래서 P31(무엇인가)이 회사인 항목만 통과시킵니다.
"""
from __future__ import annotations

import unittest
from unittest import mock

from src import fetch_images


def _entity_claims(kind_ids: list[str], image: str | None = None) -> dict:
    claims = {"P31": [{"mainsnak": {"datavalue": {"value": {"id": k}}}} for k in kind_ids]}
    if image:
        claims["P18"] = [{"mainsnak": {"datavalue": {"value": image}}}]
    return claims


def _fake_wiki(entities: dict[str, dict], file_info: dict | None = None):
    """wbsearchentities / wbgetentities / commons imageinfo 응답을 흉내 냅니다."""

    def _get(url: str, **params) -> dict:
        if params.get("action") == "wbsearchentities":
            return {"search": [{"id": qid} for qid in entities]}
        if params.get("action") == "wbgetentities":
            qid = params["ids"]
            return {"entities": {qid: {"claims": entities[qid]}}}
        return {"query": {"pages": {"1": {"imageinfo": [file_info or {}]}}}}

    return _get


_GOOD_FILE = {
    "mime": "image/jpeg",
    "thumbwidth": 1200,
    "thumbheight": 800,
    "thumburl": "https://commons.example/thumb.jpg",
    "descriptionurl": "https://commons.example/File:HQ.jpg",
    "extmetadata": {
        "LicenseShortName": {"value": "CC BY-SA 4.0"},
        "Artist": {"value": '<a href="#">Someone</a>'},
    },
}


class WikimediaFallbackTest(unittest.TestCase):
    def setUp(self) -> None:
        # Unsplash는 키가 없어 항상 빈손이라고 가정합니다.
        patcher = mock.patch.object(fetch_images, "_search_unsplash", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_returns_company_photo_with_attribution(self) -> None:
        entities = {"Q1": _entity_claims(["Q4830453"], "HQ.jpg")}
        with mock.patch.object(fetch_images, "_wiki_get", _fake_wiki(entities, _GOOD_FILE)):
            image = fetch_images.search_image("Shinhan bank", entity="Shinhan Financial Group")
        self.assertEqual(image["url"], "https://commons.example/thumb.jpg")
        self.assertIn("Someone", image["credit"])
        self.assertIn("CC BY-SA 4.0", image["credit"])
        self.assertEqual(image["credit_url"], "https://commons.example/File:HQ.jpg")

    def test_rejects_entity_that_is_not_a_company(self) -> None:
        """'카카오'로 검색하면 먼저 나오는 카카오 열매 항목을 거릅니다."""
        entities = {"Q2": _entity_claims(["Q16521"], "Cacao_in_Peru.jpg")}  # Q16521=taxon
        with mock.patch.object(fetch_images, "_wiki_get", _fake_wiki(entities, _GOOD_FILE)):
            self.assertIsNone(fetch_images.search_image("Kakao", entity="Kakao"))

    def test_rejects_logo_file(self) -> None:
        """삼성중공업의 P18은 검은 배경 워드마크였습니다 — 사진이 아닙니다."""
        entities = {"Q3": _entity_claims(["Q891723"], "Samsung Orig Wordmark BLACK RGB.png")}
        with mock.patch.object(fetch_images, "_wiki_get", _fake_wiki(entities, _GOOD_FILE)):
            self.assertIsNone(fetch_images.search_image("shipyard", entity="Samsung Heavy"))

    def test_rejects_non_commercial_license(self) -> None:
        entities = {"Q4": _entity_claims(["Q4830453"], "HQ.jpg")}
        restricted = {**_GOOD_FILE, "extmetadata": {"LicenseShortName": {"value": "CC BY-NC 2.0"}}}
        with mock.patch.object(fetch_images, "_wiki_get", _fake_wiki(entities, restricted)):
            self.assertIsNone(fetch_images.search_image("x", entity="Somebody"))

    def test_rejects_banner_shaped_file(self) -> None:
        entities = {"Q5": _entity_claims(["Q4830453"], "HQ.jpg")}
        banner = {**_GOOD_FILE, "thumbwidth": 1200, "thumbheight": 200}
        with mock.patch.object(fetch_images, "_wiki_get", _fake_wiki(entities, banner)):
            self.assertIsNone(fetch_images.search_image("x", entity="Somebody"))

    def test_skips_photo_already_used_today(self) -> None:
        entities = {"Q6": _entity_claims(["Q4830453"], "HQ.jpg")}
        with mock.patch.object(fetch_images, "_wiki_get", _fake_wiki(entities, _GOOD_FILE)):
            self.assertIsNone(
                fetch_images.search_image(
                    "x", exclude_ids={"wikimedia:HQ.jpg"}, entity="Somebody"
                )
            )

    def test_without_entity_there_is_no_second_lookup(self) -> None:
        with mock.patch.object(fetch_images, "_wiki_get") as wiki:
            self.assertIsNone(fetch_images.search_image("korean won banknote"))
        wiki.assert_not_called()


class UnsplashPreferredTest(unittest.TestCase):
    def test_unsplash_result_wins(self) -> None:
        found = {"id": "abc", "url": "https://unsplash.example/p.jpg"}
        with mock.patch.object(fetch_images, "_search_unsplash", return_value=found):
            with mock.patch.object(fetch_images, "_wiki_get") as wiki:
                image = fetch_images.search_image("Nvidia GPU", entity="NVIDIA")
        self.assertEqual(image["id"], "abc")
        wiki.assert_not_called()


if __name__ == "__main__":
    unittest.main()
