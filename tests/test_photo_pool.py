"""승인된 사진 보관함과 사진 표지.

왜 이런 검사가 필요한가
-----------------------
시황 표지는 **사람 검수 없이** 자동 공개됩니다. 그래서 이 경로에서 사진이
잘못 붙으면 아무도 막지 못합니다. 저장소에는 이미 실측 사고 기록이 있습니다 —
`korean won banknote`에 중국 위안화, `korean bank`에 삼청빌라, 위키데이터
신한은행 대표 이미지가 숭례문.

그래서 설계가 이렇습니다. **검색은 사람이 미리 하고 자동 실행은 고르기만
합니다.** 아래 검사는 그 경계가 무너지지 않았는지 봅니다.
"""
from __future__ import annotations

import unittest
from pathlib import Path

import yaml

from src import photo_pool

ROOT = Path(__file__).resolve().parent.parent


class ManifestTest(unittest.TestCase):
    def test_every_photo_file_exists(self) -> None:
        for photo in photo_pool.load():
            with self.subTest(photo=photo["id"]):
                self.assertTrue((ROOT / photo["file"]).exists())

    def test_no_noncommercial_or_noderivatives(self) -> None:
        """NC(비상업)·ND(변형금지)는 블로그에 쓸 수 없습니다.

        워드프레스가 썸네일을 만들며 크기를 바꾸므로 ND는 특히 곤란합니다.
        """
        for photo in photo_pool.load():
            code = photo["license"].lower().split()[0]
            with self.subTest(photo=photo["id"], license=photo["license"]):
                self.assertNotIn("nc", code.split("-"))
                self.assertNotIn("nd", code.split("-"))

    def test_every_photo_carries_a_credit(self) -> None:
        """CC BY 계열은 저작자 표시가 **의무**입니다."""
        for photo in photo_pool.load():
            with self.subTest(photo=photo["id"]):
                self.assertTrue(photo.get("credit", "").strip())
                self.assertTrue(photo.get("source_page", "").strip())

    def test_every_photo_says_what_is_actually_in_it(self) -> None:
        """`seen`은 검색어가 아니라 **사진에 보이는 것**입니다.

        이 저장소는 검색어를 믿지 않습니다. 사람이 한 장씩 보고 적었다는 흔적이
        없으면 승인된 사진이라고 할 수 없습니다.
        """
        for photo in photo_pool.load():
            with self.subTest(photo=photo["id"]):
                self.assertGreaterEqual(len(photo.get("seen", "")), 10)

    def test_manifest_is_not_silently_empty(self) -> None:
        """없는 파일을 가리키면 조용히 넘어가지 않고 예외로 올립니다."""
        broken = ROOT / "tests" / "_broken_pool.yaml"
        broken.write_text(yaml.safe_dump({"photos": []}, allow_unicode=True), encoding="utf-8")
        try:
            with self.assertRaises(photo_pool.PhotoPoolError):
                photo_pool.load(broken)
        finally:
            broken.unlink()


class SelectionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.photos = photo_pool.load()

    def test_picks_by_sector(self) -> None:
        entry = {"ticker": "105560", "name": "KB금융", "sector": "금융"}
        picked = photo_pool.pick(entry, "2026-09-06", self.photos)
        self.assertIsNotNone(picked)
        self.assertEqual(picked["sector"], "금융")

    def test_rotates_so_consecutive_days_differ(self) -> None:
        """같은 종목이 사흘 연속 주인공이어도 표지는 달라야 합니다.

        목록에서 어제 글과 구분되게 하는 것이 이 기능의 목적이라, 회전이 없으면
        사진을 붙이는 의미가 절반 사라집니다.
        """
        entry = {"ticker": "005930", "name": "삼성전자", "sector": "반도체"}
        picks = [photo_pool.pick(entry, d, self.photos)["id"]
                 for d in ("2026-09-06", "2026-09-07", "2026-09-08")]
        self.assertEqual(len(set(picks)), 3, f"사흘이 같은 사진입니다: {picks}")

    def test_same_day_is_stable(self) -> None:
        """같은 날 다시 돌리면 같은 사진 — 아니면 미디어가 중복으로 쌓입니다."""
        entry = {"ticker": "005930", "name": "삼성전자", "sector": "반도체"}
        first = photo_pool.pick(entry, "2026-09-06", self.photos)
        self.assertEqual(first["id"], photo_pool.pick(entry, "2026-09-06", self.photos)["id"])

    def test_dynamic_tier_never_gets_a_photo(self) -> None:
        """그날 거래대금으로 편입된 종목에는 사진을 붙이지 않습니다."""
        entry = {"ticker": "005930", "name": "삼성전자", "sector": "반도체",
                 "source": "dynamic"}
        self.assertIsNone(photo_pool.pick(entry, "2026-09-06", self.photos))

    def test_unknown_sector_falls_back_to_graphic(self) -> None:
        """맞는 사진이 없으면 억지로 붙이지 않고 None — 그래픽으로 갑니다."""
        entry = {"ticker": "278470", "name": "에이피알", "sector": "소비재"}
        self.assertIsNone(photo_pool.pick(entry, "2026-09-06", self.photos))

    def test_no_entry_means_no_photo(self) -> None:
        self.assertIsNone(photo_pool.pick(None, "2026-09-06", self.photos))


if __name__ == "__main__":
    unittest.main()
