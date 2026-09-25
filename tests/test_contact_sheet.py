"""그림 모음판(`src/contact_sheet.py`) — 원본 크기를 줄이지 않고 판 높이 안에서 채우는지, 옛 판을 지우는지."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from src import contact_sheet


def _png(folder: Path, name: str, size: tuple[int, int]) -> Path:
    path = folder / name
    Image.new("RGB", size, "#FFFFFF").save(path)
    return path


class ContactSheetTest(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp())

    def test_packs_native_size_within_height(self) -> None:
        files = [_png(self.dir, f"{i:02d}-g.png", (1000, 456)) for i in range(1, 5)]
        sheets = contact_sheet.build(files, self.dir / "sheets", max_height=1500)
        # 456+26 = 482씩, 셋이면 482*3+14*2 = 1474 ≤ 1500, 넷째는 넘친다 → 두 판
        self.assertEqual([names for _, names in sheets],
                         [["01-g.png", "02-g.png", "03-g.png"], ["04-g.png"]])
        first = Image.open(sheets[0][0])
        self.assertEqual(first.width, 1000)          # 폭은 원본 그대로
        self.assertEqual(first.height, 1474)
        self.assertLessEqual(first.height, 1500)

    def test_wide_photo_is_capped_and_old_sheets_removed(self) -> None:
        stale = self.dir / "sheets" / "sheet-07.png"
        stale.parent.mkdir(parents=True)
        stale.write_bytes(b"old")
        files = [_png(self.dir, "05-photo.jpg", (4000, 3000)), _png(self.dir, "06-g.png", (1000, 300))]
        sheets = contact_sheet.build(files, self.dir / "sheets")
        self.assertFalse(stale.exists())
        # 4000×3000 사진은 1200×900으로 줄고, 900+26 + 14 + 300+26 = 1266 ≤ 1500이라 둘이 한 판에 든다.
        self.assertEqual([names for _, names in sheets], [["05-photo.jpg", "06-g.png"]])
        sheet = Image.open(sheets[0][0])
        self.assertEqual((sheet.width, sheet.height), (1200, 1266))

    def test_gather_skips_subfolder_and_describe_lists_files(self) -> None:
        _png(self.dir, "01-g.png", (100, 100))
        (self.dir / "sheets").mkdir()
        _png(self.dir / "sheets", "sheet-01.png", (100, 100))
        (self.dir / "note.txt").write_text("x")
        self.assertEqual([p.name for p in contact_sheet.gather(self.dir)], ["01-g.png"])
        sheets = contact_sheet.build(contact_sheet.gather(self.dir), self.dir / "sheets")
        lines = contact_sheet.describe(sheets)
        self.assertIn("이 파일만", lines[0])
        self.assertIn("01-g.png", lines[1])


if __name__ == "__main__":
    unittest.main()
