"""한국장 종목별 수급 되살리기 (2026-09-26).

API는 마감 직후 전날 줄만 줘서 그날 파일은 늘 비었고, "다음 날 재수집"은 거래일이 바뀌면 새 파일을 써서 돌지 않았다
(9/11~9/22 여덟 파일 0/27). 다음 날 아침 날짜가 맞는 줄로 빈 칸만 채우고, 한국장 글은 전 거래일 수급을 그린다.
"""
import json
import tempfile
import unittest
from pathlib import Path

from scripts import fill_kr_flows
from src import data_graphics


def _rows(date: str) -> list[dict]:
    return [{"date": "2026.09.23", "institution_net": 9, "foreign_net": 9, "foreign_ratio": 9.0},
            {"date": date, "institution_net": 1, "foreign_net": 2, "foreign_ratio": 3.0}]


class FillTest(unittest.TestCase):
    def _file(self, folder: Path, entries: dict) -> Path:
        path = folder / "price_kr_2026-09-22.json"
        path.write_text(json.dumps({"trading_date": "2026-09-22", "watchlist": entries}, ensure_ascii=False), encoding="utf-8")
        return path

    def test_fills_only_blanks_with_the_matching_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._file(Path(tmp), {
                "005930": {"price": 100, "change_pct": 1.0},
                "000660": {"price": 200, "change_pct": 2.0, "foreign_net": 5, "institution_net": 6, "foreign_ratio": 7.0},
            })
            filled, kept, missed = fill_kr_flows.fill(path, fetch=lambda t, n: _rows("2026.09.22"))
            doc = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual((filled, kept, missed), (1, 1, 0))
        self.assertEqual(doc["watchlist"]["005930"]["foreign_net"], 2)
        self.assertEqual(doc["watchlist"]["005930"]["price"], 100)            # 가격은 그대로
        self.assertEqual(doc["watchlist"]["000660"]["foreign_net"], 5)        # 있던 값은 그대로

    def test_no_matching_date_is_counted_not_guessed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._file(Path(tmp), {"005930": {"price": 100}})
            before = path.read_text(encoding="utf-8")
            filled, kept, missed = fill_kr_flows.fill(path, fetch=lambda t, n: _rows("2026.09.21"))
            self.assertEqual((filled, missed), (0, 1))
            self.assertEqual(path.read_text(encoding="utf-8"), before)       # 바뀐 게 없으면 쓰지 않는다


class PreviousDayGraphicTest(unittest.TestCase):
    def test_previous_day_spec_draws_from_the_previous_file(self) -> None:
        today, prev = {"watchlist": {}}, {"watchlist": {"a": {"foreign_net": 1}}}
        source, options = data_graphics.graphic_inputs({"kind": "flow_chart", "day": "previous", "title": "t"}, today, prev)
        self.assertIs(source, prev)
        self.assertNotIn("day", options)

    def test_previous_day_is_only_for_flow_graphics_and_needs_a_file(self) -> None:
        with self.assertRaises(ValueError):
            data_graphics.graphic_inputs({"kind": "movers_list", "day": "previous"}, {}, {"watchlist": {}})
        with self.assertRaises(ValueError):
            data_graphics.graphic_inputs({"kind": "flow_chart", "day": "previous"}, {}, None)

    def test_committed_files_have_flows_again(self) -> None:
        root = Path(__file__).resolve().parent.parent / "data"
        for day in ("2026-09-11", "2026-09-17", "2026-09-22"):
            wl = json.loads((root / f"price_kr_{day}.json").read_text(encoding="utf-8"))["watchlist"]
            self.assertTrue(all(e.get("foreign_net") is not None for e in wl.values()), day)


if __name__ == "__main__":
    unittest.main()
