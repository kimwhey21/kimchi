"""사진 표지가 실제로 읽히는 그림을 내놓는지 봅니다.

왜 렌더까지 검사하는가
----------------------
이 경로는 사람 검수 없이 자동 공개됩니다. "사진을 골랐다"까지만 검사하면
**글자가 사진에 묻힌 표지**가 그대로 나갑니다. 실제로 겪었습니다 — 테슬라 공장
사진(붉은 로봇 팔이 화면을 채움) 위에 붉은 상승률을 쓰니 읽히지 않았습니다.
막을 씌우는 것으로는 못 막습니다. 같은 색끼리 만나는 문제라서요.

그래서 글자 자리의 명암 대비를 실제 픽셀에서 재고, 목록 카드가 잘라 내는
4:3 영역 안에 글자가 남는지도 함께 봅니다.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageStat

from src import data_graphics, featured_image, photo_pool

ROOT = Path(__file__).resolve().parent.parent

PRICE = {
    "macro": {
        "kospi": {"name": "코스피", "name_en": "KOSPI", "price": 6687.21, "change_pct": 1.64},
        "kosdaq": {"name": "코스닥", "name_en": "KOSDAQ", "price": 813.5, "change_pct": 2.95},
        "usdkrw": {"name": "원/달러 환율", "name_en": "USD/KRW", "price": 1351.3, "change_pct": -0.53},
    },
    "watchlist": {
        "005930": {"name": "삼성전자", "name_en": "Samsung Electronics", "ticker": "005930",
                   "sector": "반도체", "price": 92000, "change_pct": 6.20},
        "000660": {"name": "SK하이닉스", "name_en": "SK hynix", "ticker": "000660",
                   "sector": "반도체", "price": 310000, "change_pct": 1.10},
        "105560": {"name": "KB금융", "name_en": "KB Financial", "ticker": "105560",
                   "sector": "금융", "price": 88000, "change_pct": -0.40},
    },
}


@unittest.skipUnless(data_graphics.has_korean_font(), "한글 폰트가 없어 렌더를 건너뜁니다")
class PhotoCoverTest(unittest.TestCase):
    def _render(self, date_str: str = "2026-09-06") -> tuple[Path, dict]:
        tmp = Path(tempfile.mkdtemp()) / "cover.png"
        meta = featured_image.create("kr", date_str, PRICE, tmp,
                                     doc={"title": "삼성전자가 끌어올린 장"})
        return tmp, meta

    def test_uses_a_photo_when_the_sector_has_one(self) -> None:
        _, meta = self._render()
        self.assertEqual(meta["layout"], "photo")
        self.assertTrue(meta["photo_id"])

    def test_credit_reaches_the_caption(self) -> None:
        """CC BY는 저작자 표시가 의무라, 캡션에 실려야 합니다."""
        _, meta = self._render()
        self.assertIn("사진:", meta["caption"])

    def test_alt_changes_with_the_photo(self) -> None:
        """숫자가 같고 사진만 다른 날 옛 미디어가 재사용되면 안 됩니다.

        publish_wordpress가 alt로 "같은 데이터로 만든 이미지인지"를 판단합니다.
        2026-09-03에 alt가 같아 대표 이미지가 어제 것으로 남은 적이 있습니다.
        """
        # 2026-09-26부터 사진은 날짜가 아니라 "그 묶음이 사진을 쓴 횟수"로 바뀐다 — 사이에 반도체 사진 표지가 한 번
        # 나갔다는 원고를 두고 다음 날을 그린다.
        saved = featured_image.EDITORIAL_DIR
        try:
            with tempfile.TemporaryDirectory() as tmp:
                featured_image.EDITORIAL_DIR = Path(tmp)
                _, first = self._render("2026-09-16")
                (Path(tmp) / "kr_2026-09-16.json").write_text(json.dumps(
                    {"market": "kr", "date": "2026-09-16", "price_data": PRICE, "ko": {"title": "삼성전자가 끌어올린 장"}},
                    ensure_ascii=False), encoding="utf-8")
                _, second = self._render("2026-09-17")
        finally:
            featured_image.EDITORIAL_DIR = saved
        self.assertNotEqual(first["photo_id"], second["photo_id"])
        self.assertNotEqual(first["alt"], second["alt"])

    def test_text_stays_readable_on_every_photo(self) -> None:
        """모든 승인 사진에서 큰 글자 자리의 대비가 충분한지 실제 픽셀로 잽니다."""
        lead = PRICE["watchlist"]["005930"]
        for photo in photo_pool.load():
            with self.subTest(photo=photo["id"]):
                canvas = featured_image._cover_crop(photo_pool.resolve(photo))
                featured_image._scrim(canvas)
                featured_image._render_photo(canvas, "kr", "2026-09-06", PRICE, lead, "ko")
                # 종목명·등락률이 놓이는 띠(y 196~430)의 배경이 충분히 어두워야
                # 흰 글자가 읽힙니다. 글자 자체를 피해 왼쪽 여백에서 잽니다.
                band = canvas.crop((featured_image._CONTENT_LEFT - 60, 196,
                                    featured_image._CONTENT_LEFT - 10, 430))
                mean = ImageStat.Stat(band.convert("L")).mean[0]
                self.assertLess(mean, 150,
                                f"{photo['id']}: 글자 자리 배경이 밝아(평균 {mean:.0f}) "
                                f"흰 글자가 묻힙니다.")

    def test_nothing_is_clipped_by_the_four_three_card(self) -> None:
        """목록 카드는 좌우를 180px씩 잘라 냅니다. 글자가 그 안에 있어야 합니다."""
        path, _ = self._render()
        with Image.open(path) as canvas:
            self.assertEqual(canvas.size, (1200, 630))
        self.assertGreaterEqual(featured_image._CONTENT_LEFT, featured_image.SAFE_LEFT)
        self.assertLessEqual(featured_image._CONTENT_RIGHT, featured_image.SAFE_RIGHT)

    def test_falls_back_to_graphic_without_a_photo(self) -> None:
        """사진이 없는 업종이 주인공인 날은 지금까지처럼 그래픽으로 갑니다."""
        price = json.loads(json.dumps(PRICE))
        price["watchlist"] = {"259960": {"name": "크래프톤", "name_en": "Krafton", "ticker": "259960",
                                         "sector": "게임", "price": 310000, "change_pct": 9.10}}
        tmp = Path(tempfile.mkdtemp()) / "cover.png"
        meta = featured_image.create("kr", "2026-09-06", price, tmp,
                                     doc={"title": "크래프톤이 끌어올린 장"})
        self.assertEqual(meta["layout"], "single")
        self.assertIsNone(meta["photo_id"])


if __name__ == "__main__":
    unittest.main()


class MoveColorTest(unittest.TestCase):
    """보합(0.00%)을 상승색으로 칠하지 않습니다.

    목록에서 빨간 `+0.00%`를 보면 오른 날로 읽힙니다. **그림이 사실과 다른 말을
    하는 것**이라, 데이터에서 색을 뽑는다는 이 표지의 성질이 무너집니다.
    """

    def test_zero_is_neither_up_nor_down(self) -> None:
        for dark in (False, True):
            with self.subTest(dark=dark):
                flat = featured_image._move_color(0.0, dark)
                self.assertNotEqual(flat, featured_image._move_color(1.0, dark))
                self.assertNotEqual(flat, featured_image._move_color(-1.0, dark))

    def test_sign_decides_the_color(self) -> None:
        self.assertEqual(featured_image._move_color(0.01), featured_image._UP)
        self.assertEqual(featured_image._move_color(-0.01), featured_image._DOWN)


class CoverTurnTest(unittest.TestCase):
    """표지 돌려쓰기 횟수는 커밋된 시황 원고에서 다시 센다(2026-09-26) — 상태 파일이 없어 러너와 맥이 같은 답을 낸다."""

    def _manuscript(self, folder: Path, market: str, date: str, title: str) -> None:
        doc = {"market": market, "date": date, "price_data": PRICE, "ko": {"title": title}}
        (folder / f"{market}_{date}.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    def test_counts_only_earlier_photo_days_of_the_same_bundle(self) -> None:
        samsung = {"ticker": "005930", "name": "삼성전자", "sector": "반도체"}
        kb = {"ticker": "105560", "name": "KB금융", "sector": "금융"}
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self._manuscript(folder, "kr", "2026-09-16", "삼성전자가 끌어올린 장")      # 반도체 사진 1
            self._manuscript(folder, "us", "2026-09-16", "KB금융이 끌어올린 장")        # 금융 — 다른 묶음
            self._manuscript(folder, "kr", "2026-09-18", "SK하이닉스가 끌어올린 장")    # 반도체 사진 2
            self._manuscript(folder, "kr", "2026-09-10", "삼성전자가 끌어올린 장")      # ROTATION_START 전 — 안 센다
            self._manuscript(folder, "kr", "2026-09-19", "삼성전자와 SK하이닉스가 함께") # 둘 부름 → trio, 안 센다
            self.assertEqual(featured_image.cover_turn(samsung, "kr", "2026-09-20", editorial_dir=folder), 2)
            self.assertEqual(featured_image.cover_turn(kb, "kr", "2026-09-20", editorial_dir=folder), 1)
            # 같은 날짜의 한국장은 미국장보다 앞이다
            self.assertEqual(featured_image.cover_turn(kb, "us", "2026-09-16", editorial_dir=folder), 0)
            self.assertEqual(featured_image.cover_turn(kb, "kr", "2026-09-16", editorial_dir=folder), 0)
            self.assertEqual(featured_image.cover_turn(samsung, "us", "2026-09-16", editorial_dir=folder), 1)

    def test_five_semiconductor_days_get_five_different_covers(self) -> None:
        samsung = {"ticker": "005930", "name": "삼성전자", "sector": "반도체"}
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            picks = []
            for day in ("16", "17", "18", "21", "22"):
                turn = featured_image.cover_turn(samsung, "kr", f"2026-09-{day}", editorial_dir=folder)
                picks.append(photo_pool.pick(samsung, f"2026-09-{day}", turn=turn)["id"])
                self._manuscript(folder, "kr", f"2026-09-{day}", "삼성전자가 끌어올린 장")
            self.assertEqual(len(set(picks)), 5, picks)
