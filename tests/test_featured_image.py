"""대표 이미지 — 레이아웃 선택과 이름 표기를 봅니다.

2026-09-05까지 레이아웃은 하나였고 색만 다섯 단계로 바뀌었습니다. 목록에서
훑으면 매일 같은 그림으로 보였고, 사용자가 "대표이미지가 지수 그림으로 온통
도배되고 있다"고 지적했습니다. 지금은 그날 이야기의 모양에 따라 둘 중 하나를
그립니다 — 이 파일은 그 갈림길이 흐트러지지 않는지 확인합니다.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from src import data_graphics, featured_image
from src.featured_image import choose_layout, create, lead_watchlist_entry

MACRO = {
    "KS11": {"name": "코스피", "name_en": "KOSPI", "price": 6687.21, "change_pct": 1.64},
    "KQ11": {"name": "코스닥", "name_en": "KOSDAQ", "price": 813.5, "change_pct": 2.95},
    "USD/KRW": {"name": "원/달러 환율", "name_en": "USD/KRW", "price": 1351.3,
                 "change_pct": -0.53, "unit": "원"},
}


def _stock(name, name_en, change, price=100000.0, source="core") -> dict:
    return {"name": name, "name_en": name_en, "change_pct": change,
            "price": price, "source": source}


def _data(*stocks) -> dict:
    return {"macro": dict(MACRO),
            "watchlist": {str(i): s for i, s in enumerate(stocks)}}


SOLO = _data(                       # 1위가 2위를 2.72배 앞선 날 (2026-09-02 미국장)
    _stock("델 테크놀로지스", "Dell Technologies", 15.81),
    _stock("팔란티어", "Palantir", -5.81),
    _stock("디어", "Deere", 3.30),
)
CROWD = _data(                      # 2차전지가 통째로 밀린 날 (2026-09-02 한국장)
    _stock("에코프로비엠", "Ecopro BM", -7.06),
    _stock("에코프로", "Ecopro", -5.96),
    _stock("LG에너지솔루션", "LG Energy Solution", -5.31),
)


class LayoutChoiceTest(unittest.TestCase):
    def test_title_naming_one_stock_gives_single(self) -> None:
        doc = {"title": "에코프로비엠 7.06% 급락! 2차전지가 무너진 이유."}
        self.assertEqual(choose_layout(CROWD, doc), "single")

    def test_title_naming_two_stocks_gives_trio(self) -> None:
        """제목이 종목 둘을 부르면 그날은 한 종목의 날이 아닙니다."""
        doc = {"title": "델 테크놀로지스 15.81%, 팔란티어 5.81% 급락. 갈린 하루."}
        self.assertEqual(choose_layout(SOLO, doc), "trio")

    def test_no_stock_in_title_falls_back_to_the_numbers(self) -> None:
        """지수·정책이 주인공인 날은 1위와 2위의 간격으로 정합니다."""
        doc = {"title": "국채 금리 20개월 만의 최고에 3대 지수 모두 하락했습니다"}
        self.assertEqual(choose_layout(SOLO, doc), "single")   # 2.72배
        self.assertEqual(choose_layout(CROWD, doc), "trio")    # 1.18배

    def test_no_doc_at_all_still_decides(self) -> None:
        """main.py의 규칙 기반 초안에는 원고가 없습니다."""
        self.assertEqual(choose_layout(SOLO), "single")
        self.assertEqual(choose_layout(CROWD), "trio")

    def test_fewer_than_three_stocks_gives_single(self) -> None:
        """셋을 나열할 수 없으면 빈 타일을 그리지 않고 하나짜리로 갑니다."""
        thin = _data(_stock("삼성전자", "Samsung Electronics", 1.2))
        self.assertEqual(choose_layout(thin), "single")


class RenderTest(unittest.TestCase):
    def _create(self, price_data, doc=None, market="kr"):
        directory = tempfile.mkdtemp()
        output = Path(directory) / "featured.png"
        return create(market, "2026-09-04", price_data, output, doc), output

    def test_creates_wordpress_ready_png(self) -> None:
        for price_data in (SOLO, CROWD):
            with self.subTest(layout=choose_layout(price_data)):
                metadata, output = self._create(price_data)
                with Image.open(output) as image:
                    self.assertEqual(image.size, (1200, 630))
                    self.assertEqual(image.format, "PNG")
                self.assertEqual(metadata["local_path"], str(output))

    def test_single_draws_the_stock_the_title_named(self) -> None:
        """1위가 아니어도, 그날 글이 다룬 종목이 대문에 섭니다."""
        doc = {"title": "팔란티어 5.81% 급락. 방산 소프트웨어가 흔들린 이유."}
        metadata, _ = self._create(SOLO, doc, market="us")
        self.assertEqual(metadata["layout"], "single")
        self.assertIn("Palantir", metadata["alt"])
        self.assertNotIn("Dell", metadata["alt"])

    def test_trio_alt_lists_all_three(self) -> None:
        metadata, _ = self._create(CROWD)
        self.assertEqual(metadata["layout"], "trio")
        for name in ("Ecopro BM", "Ecopro", "LG Energy Solution"):
            self.assertIn(name, metadata["alt"])

    def test_alt_changes_when_the_drawn_stock_changes(self) -> None:
        """alt가 같으면 publish_wordpress가 옛 이미지를 그대로 재사용합니다.

        2026-09-03에 실제로 그렇게 됐습니다 — 대문 종목이 바뀌었는데 지수
        숫자가 같아 alt가 동일했고, 제목은 삼성중공업인데 대표 이미지는
        알테오젠인 글이 공개됐습니다.
        """
        one, _ = self._create(SOLO, {"title": "델 테크놀로지스 15.81% 급등!"})
        two, _ = self._create(SOLO, {"title": "팔란티어 5.81% 급락!"})
        self.assertNotEqual(one["alt"], two["alt"])

    def test_layout_change_alone_changes_alt(self) -> None:
        one, _ = self._create(SOLO, {"title": "델 테크놀로지스 15.81% 급등!"})
        two, _ = self._create(SOLO, {"title": "델 테크놀로지스와 팔란티어가 갈린 날"})
        self.assertNotEqual(one["layout"], two["layout"])
        self.assertNotEqual(one["alt"], two["alt"])


class NameTest(unittest.TestCase):
    def test_dynamic_tier_can_take_the_front(self) -> None:
        """거래대금으로 편입된 종목도 대문 후보입니다.

        데이터에서 텍스트를 그리는 것이라 엉뚱한 그림이 붙을 위험이 없습니다.
        """
        price_data = _data(
            _stock("KB금융", "KB Financial Group", 5.2),
            _stock("삼성중공업", "삼성중공업", 8.58, source="dynamic"),
        )
        self.assertEqual(lead_watchlist_entry(price_data)["name"], "삼성중공업")

    def test_korean_name_is_used_when_the_font_exists(self) -> None:
        with mock.patch.object(data_graphics, "has_korean_font", return_value=True):
            self.assertEqual(featured_image._name(_stock("원익홀딩스", "Wonik Holdings", 29.91)),
                             "원익홀딩스")

    def test_english_edition_uses_english_names(self) -> None:
        """영어 글에 한글 이름이 박힌 그림이 붙으면 무슨 종목인지 알 수 없습니다."""
        entry = _stock("원익홀딩스", "Wonik Holdings", 29.91)
        with mock.patch.object(data_graphics, "has_korean_font", return_value=True):
            self.assertEqual(featured_image._name(entry, "en"), "Wonik Holdings")

    def test_english_edition_shortens_long_index_names(self) -> None:
        """'Dow Jones Industrial Average'를 그대로 쓰면 카드를 넘칩니다."""
        entry = {"name": "다우존스", "name_en": "Dow Jones Industrial Average",
                 "price": 53414.25, "change_pct": -0.51}
        self.assertEqual(featured_image._name(entry, "en"), "Dow Jones")

    def test_english_edition_labels_and_currency(self) -> None:
        self.assertTrue(featured_image._market_line("kr", "2026-09-04", "en")
                        .startswith("Korea Market Close"))
        won = {"name": "원/달러 환율", "name_en": "USD/KRW", "price": 1351.3, "unit": "원"}
        self.assertEqual(featured_image._price(won, "en"), "1,351.3 KRW")
        self.assertEqual(featured_image._price(won, "ko"), "1,351.3원")

    def test_two_languages_get_different_alt(self) -> None:
        """alt가 같으면 영어 글에 한국어 그림이 그대로 재사용됩니다."""
        directory = Path(tempfile.mkdtemp())
        ko = create("kr", "2026-09-04", CROWD, directory / "ko.png", None, lang="ko")
        en = create("kr", "2026-09-04", CROWD, directory / "en.png", None, lang="en")
        self.assertNotEqual(ko["alt"], en["alt"])
        self.assertEqual(ko["layout"], en["layout"])

    def test_falls_back_to_english_without_a_korean_font(self) -> None:
        """우분투 러너에 fonts-nanum이 없으면 한글이 두부(□□□)로 찍힙니다.

        2026-09-04에 실제로 그런 그림이 사이트에 올라갔습니다. 깨진 글자보다
        영문 표기가 낫습니다.
        """
        with mock.patch.object(data_graphics, "has_korean_font", return_value=False):
            self.assertEqual(featured_image._name(_stock("원익홀딩스", "Wonik Holdings", 29.91)),
                             "Wonik Holdings")


if __name__ == "__main__":
    unittest.main()
