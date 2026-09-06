"""표지 사진 검색.

2026-09-07에 경로를 하나씩 두드려 본 결과 라이선스가 확인되는 곳은 위키미디어와
Openverse뿐이었습니다. 네이버·구글 이미지는 라이선스 필터가 없어 결과를 그대로
쓰면 저작권 침해가 됩니다.
"""
from __future__ import annotations

import unittest
from unittest import mock

from src import photo_search


def _item(license_code: str, version: str = "4.0", **extra) -> dict:
    base = {"title": "제목", "license": license_code, "license_version": version,
            "creator": "촬영자", "source": "wikimedia",
            "url": "https://example.test/a.jpg",
            "foreign_landing_url": "https://example.test/page",
            # 실제 사진 크기입니다. 100×100으로 두면 아이콘 필터에 걸립니다.
            "width": 1600, "height": 1200}
    base.update(extra)
    return base


class LicenseFilterTest(unittest.TestCase):
    def _search(self, items, **kwargs):
        response = mock.Mock(status_code=200)
        response.raise_for_status = lambda: None
        response.json = lambda: {"results": items}
        with mock.patch.object(photo_search.requests, "get",
                               lambda *a, **k: response):
            return photo_search.search("q", **kwargs)

    def test_non_commercial_is_dropped(self) -> None:
        """블로그는 상업적 이용으로 볼 여지가 있어 NC를 뺍니다."""
        rows = self._search([_item("by-nc-sa", "2.0"), _item("cc0", "1.0")])
        self.assertEqual([r["license"] for r in rows], ["CC0 1.0"])

    def test_no_derivatives_is_dropped(self) -> None:
        """워드프레스가 썸네일을 만들며 크기를 바꿉니다 — ND는 못 씁니다."""
        rows = self._search([_item("by-nd", "2.0"), _item("by-sa", "4.0")])
        self.assertEqual([r["license"] for r in rows], ["BY-SA 4.0"])

    def test_all_licenses_keeps_everything(self) -> None:
        rows = self._search([_item("by-nc-sa", "2.0")], commercial_only=False)
        self.assertEqual(len(rows), 1)

    def test_credit_names_creator_and_license(self) -> None:
        """CC BY 계열은 저작자 표시가 의무입니다."""
        row = self._search([_item("by-sa", "4.0")])[0]
        line = photo_search.credit(row)
        self.assertIn("촬영자", line)
        self.assertIn("위키미디어 공용", line)
        self.assertIn("BY-SA 4.0", line)

    def test_missing_creator_does_not_crash(self) -> None:
        row = self._search([_item("cc0", "1.0", creator=None)])[0]
        self.assertIn("작자 미상", photo_search.credit(row))


class NotAPhotoFilterTest(LicenseFilterTest):
    """사진이 아닌 결과를 거릅니다.

    2026-09-06에 `power plant industrial`을 돌렸더니 대조표 12칸 중 2칸이
    **지도 마커 아이콘**이었습니다. 표지로 쓸 수 없는데 자리를 차지해, 한 판에
    12장을 펼쳐 놓는다는 이 도구의 목적을 그대로 깎아먹습니다.
    """

    def test_icons_and_logos_are_dropped(self) -> None:
        rows = self._search([
            _item("by-sa", "3.0", title="Map marker icon - Nicolas Mollet"),
            _item("by", "2.0", title="Coat of arms of Seoul"),
            _item("by", "2.0", title="Nuclear power plant at dusk"),
        ])
        self.assertEqual([r["title"] for r in rows], ["Nuclear power plant at dusk"])

    def test_svg_is_dropped(self) -> None:
        rows = self._search([
            _item("by", "2.0", title="발전소", url="https://example.test/a.svg"),
            _item("by", "2.0", title="발전소", url="https://example.test/b.jpg"),
        ])
        self.assertEqual([r["url"] for r in rows], ["https://example.test/b.jpg"])

    def test_tiny_images_are_dropped(self) -> None:
        """1200×630 표지에 쓸 그림입니다. 작은 것은 늘리면 뭉갭니다."""
        rows = self._search([
            _item("by", "2.0", title="발전소", width=120, height=120),
            _item("by", "2.0", title="발전소", width=2000, height=1400),
        ])
        self.assertEqual([r["width"] for r in rows], [2000])

    def test_unknown_size_is_kept(self) -> None:
        """크기를 안 알려주는 출처도 있습니다. 모른다고 버리지 않습니다."""
        rows = self._search([_item("by", "2.0", title="발전소", width=None, height=None)])
        self.assertEqual(len(rows), 1)
