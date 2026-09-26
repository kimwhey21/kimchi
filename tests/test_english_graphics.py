"""영어 시황의 본문 그림 (2026-09-26).

9/9부터 영어 시황 24편의 그림 자리가 전부 `<img src="">`였다 — 발행 코드가 한국어판 그림만 그리고 영어판 절에는
명세만 남겼다. 이제 영어 명세를 영어 모드로 그리고(종목명·업종·단위·고정 글자 영어), 주소가 없으면 태그를 찍지 않는다.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src import data_graphics, publish_editorial, render_html

ROOT = Path(__file__).resolve().parent.parent
DOC = json.loads((ROOT / "editorial" / "kr_2026-09-22.json").read_text(encoding="utf-8"))


class LocalizedTest(unittest.TestCase):
    def test_names_sectors_units_become_english_and_original_is_untouched(self) -> None:
        pd = DOC["price_data"]
        en = data_graphics.localized(pd, "en")
        samsung = en["watchlist"]["005930"]
        self.assertEqual(samsung["name"], "Samsung Electronics")
        self.assertEqual(samsung["sector"], "Semiconductors")
        self.assertEqual(samsung["unit"], " won")
        self.assertEqual(en["macro"]["USD/KRW"]["unit"], " won")
        self.assertEqual(pd["watchlist"]["005930"]["name"], "삼성전자")     # 원본은 그대로
        self.assertIs(data_graphics.localized(pd, "ko"), pd)

    def test_long_index_names_are_shortened(self) -> None:
        pd = {"macro": {"^DJI": {"name": "다우존스", "name_en": "Dow Jones Industrial Average", "price": 1.0,
                                  "change_pct": 0.1}}, "watchlist": {}}
        self.assertEqual(data_graphics.localized(pd, "en")["macro"]["^DJI"]["name"], "Dow Jones")


class BuildTest(unittest.TestCase):
    def test_english_mode_is_switched_back_off(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_graphics.build("sector_bars", DOC["price_data"], Path(tmp) / "a.png", lang="en", title="Sectors")
            self.assertEqual(data_graphics._LANG, "ko")
            self.assertEqual(data_graphics._t("오늘"), "오늘")

    def test_every_english_spec_in_a_real_manuscript_draws(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for i, section in enumerate(DOC["en"]["narrative"], 1):
                spec = section.get("graphic")
                if not spec:
                    continue
                opts = {k: v for k, v in spec.items() if k not in ("kind", "url", "alt", "lang")}
                if spec["kind"] == "two_day_compare":
                    continue
                data_graphics.build(spec["kind"], DOC["price_data"], Path(tmp) / f"{i}.png", lang="en", **opts)


class AttachTest(unittest.TestCase):
    def test_english_sections_get_their_own_graphic_urls(self) -> None:
        en = json.loads(json.dumps(DOC["en"]["narrative"]))
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(publish_editorial, "OUTPUT_DIR", Path(tmp)):
            publish_editorial._attach_section_graphics(en, DOC["price_data"], "kr", "2026-09-22", None,
                                                       upload=False, lang="en")
        drawn = [s["graphic"] for s in en if s.get("graphic")]
        self.assertTrue(drawn)
        for graphic in drawn:
            self.assertTrue(graphic["url"].endswith("_en.png"), graphic)


class TemplateTest(unittest.TestCase):
    def test_a_graphic_without_url_prints_no_image_tag(self) -> None:
        generated = json.loads(json.dumps(DOC["en"]))
        for section in generated["narrative"]:
            section.pop("photo", None)          # 명세만 남은 절(옛 버그의 모양)
        html = render_html.render("kr", "2026-09-22", DOC["price_data"], generated, lang="en")
        self.assertNotIn('class="mb-figure" src=""', html)
        self.assertNotIn('<img class="mb-figure"', html)     # 스타일시트의 .mb-figure는 그대로 있다


class EnglishPhotoTest(unittest.TestCase):
    """us 9/14: 한국어 10절·영어 9절이라 사진 복사가 통째로 건너뛰어 영어 MU 절이 `<img src="">`였다(2026-09-26)."""

    US_0914 = json.loads((ROOT / "editorial" / "us_2026-09-14.json").read_text(encoding="utf-8"))

    def test_unequal_sections_still_resolve_english_photo_specs(self) -> None:
        doc = json.loads(json.dumps(self.US_0914))
        ko, en = doc["ko"]["narrative"], doc["en"]["narrative"]
        self.assertNotEqual(len(ko), len(en))                     # 버그가 난 모양 그대로
        publish_editorial._share_section_photos(ko, en, doc["price_data"], "2026-09-14", upload=False)
        for section in en:
            photo = section.get("photo")
            self.assertTrue(photo is None or photo.get("url"), photo)   # 명세만 남은 절이 없다
        self.assertTrue(any((s.get("photo") or {}).get("url") for s in en), "MU는 코어 종목이라 풀 사진이 있다")

    def test_equal_sections_copy_korean_photos(self) -> None:
        ko = [{"photo": {"id": "p1", "url": "https://x/p1.jpg"}}, {"photo": None}]
        en = [{"photo": {"ticker": "MU"}}, {}]
        with mock.patch.object(publish_editorial, "_attach_section_photos") as attach:
            publish_editorial._share_section_photos(ko, en, {}, "2026-09-14", upload=False)
        self.assertEqual(en[0]["photo"]["url"], "https://x/p1.jpg")
        attach.assert_not_called()

    def test_photo_or_story_image_without_url_prints_no_tag(self) -> None:
        generated = json.loads(json.dumps(self.US_0914["en"]))
        for section in generated["narrative"]:
            section["graphic"] = None
        for story in (generated.get("insight_section") or {}).get("stories") or []:
            story["image"] = {"alt": "no url"}
        html = render_html.render("us", "2026-09-14", self.US_0914["price_data"], generated, lang="en")
        self.assertNotIn('src=""', html)
        self.assertNotIn('<img class="mb-story-photo"', html)


class EnglishCreditTest(unittest.TestCase):
    """풀 사진의 저작자 표시는 한국어로 적혀 있다 — 영어 글에서는 영어로(2026-09-26, us 9/14 'Photo'가 '사진: … / 플리커')."""

    def test_every_pool_credit_converts_without_hangul(self) -> None:
        from src import photo_pool
        for photo in photo_pool.load():
            with self.subTest(photo=photo["id"]):
                converted = photo_pool.credit_en(photo.get("credit", ""))
                self.assertFalse(any("가" <= ch <= "힣" for ch in converted), converted)
        self.assertEqual(photo_pool.credit_en("사진: Un ragazzo chiamato Bi / 플리커 (BY-SA 2.0)"),
                         "Photo: Un ragazzo chiamato Bi / Flickr (BY-SA 2.0)")

    def test_unknown_korean_fails_loudly(self) -> None:
        from src import photo_pool
        with self.assertRaises(ValueError):
            photo_pool.credit_en("사진: 누군가 / 모르는 곳")

    def test_english_render_localizes_credit_and_korean_keeps_it(self) -> None:
        doc = EnglishPhotoTest.US_0914
        photo = {"id": "p", "url": "https://x/p.jpg", "alt": "기판에 얹힌 칩",
                 "credit": "사진: Un ragazzo chiamato Bi / 플리커 (BY-SA 2.0)"}
        story_image = {"url": "https://x/s.jpg", "credit": "사진: naotakem / 플리커 (BY 2.0)"}
        en = json.loads(json.dumps(doc["en"]))
        en["narrative"][0]["photo"] = photo
        for story in (en.get("insight_section") or {}).get("stories") or []:
            story["image"] = story_image
        html = render_html.render("us", "2026-09-14", doc["price_data"], en, lang="en")
        self.assertIn("Photo: Un ragazzo chiamato Bi / Flickr (BY-SA 2.0)", html)
        self.assertNotIn("플리커", html)
        self.assertNotIn("기판에 얹힌 칩", html)                    # 한국어 alt는 영어 소제목으로
        self.assertIn(f'alt="{en["narrative"][0]["heading"]}"', html)
        self.assertEqual(photo["credit"], "사진: Un ragazzo chiamato Bi / 플리커 (BY-SA 2.0)")   # 원본은 그대로
        ko = json.loads(json.dumps(doc["ko"]))
        ko["narrative"][0]["photo"] = photo
        self.assertIn("사진: Un ragazzo chiamato Bi / 플리커", render_html.render("us", "2026-09-14", doc["price_data"], ko))


if __name__ == "__main__":
    unittest.main()
