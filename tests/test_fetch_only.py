"""`python -m src.main --fetch-only`가 시세 파일까지만 만들고 멈추는지 봅니다.

왜 필요한가
-----------
2026-09-07에 예약 수집(market_brief.yml)을 "시세만 커밋하고 루틴을 깨운다"로
단순화했습니다. 그 전에는 같은 실행이 규칙 기반 초안을 만들어 워드프레스에
draft로 올렸고, 그 초안이 매일 관리자 화면에 쌓여 "데이터만 나열한 글"로
오인됐습니다. 이 플래그가 어느 날 초안 생성이나 업로드까지 다시 타면 같은
일이 조용히 되살아납니다 — 그래서 초안 생성기와 업로더에 손이 가면 바로
터지게 해 두고, 시세 파일은 실제로 남는지 확인합니다.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src import main as main_module


class FetchOnlyTest(unittest.TestCase):
    def test_fetch_only_writes_price_file_and_stops(self) -> None:
        price = {"trading_date": "2026-09-07", "macro": {}, "watchlist": {}}
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            with mock.patch.object(main_module, "DATA_DIR", data_dir), \
                 mock.patch("src.fetch_kr.fetch_all", return_value=price), \
                 mock.patch.object(main_module.data_quality, "validate_trading_dates"), \
                 mock.patch.object(main_module.generate_free, "generate",
                                   side_effect=AssertionError("초안을 만들면 안 됩니다")), \
                 mock.patch.object(main_module.featured_image, "create",
                                   side_effect=AssertionError("대표 이미지를 만들면 안 됩니다")), \
                 mock.patch.object(main_module.publish_wordpress, "publish_draft",
                                   side_effect=AssertionError("워드프레스에 올리면 안 됩니다")):
                result = main_module.run("kr", fetch_only=True)

            expected = data_dir / "price_kr_2026-09-07.json"
            self.assertEqual(result, expected)
            self.assertTrue(expected.exists(), "시세 파일이 남아야 루틴이 읽습니다")
            self.assertEqual(json.loads(expected.read_text(encoding="utf-8"))["trading_date"],
                             "2026-09-07")


if __name__ == "__main__":
    unittest.main()
