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


class WriteOnceMergeTest(unittest.TestCase):
    """같은 거래일 시세 파일이 이미 있으면 가격은 다시 쓰지 않고 빈 칸만 채운다(2026-09-25).

    9/24 휴장 재수집이 9/23 파일의 삼성전자 등락률을 2.70→3.24%, 코스피를 0.90→0.09%로 덮어써
    발행된 글과 파일이 어긋났다. 같은 날 :27/:34 재시도도 매번 값을 바꿔 루틴의 push를 거절시켰다.
    """

    def _old(self):
        return {"trading_date": "2026-09-23", "missing": [],
                "macro": {"KS11": {"price": 7080.92, "change_pct": 0.9, "history": {"dates": ["a"], "close": [7080.92]}}},
                "watchlist": {"005930": {"ticker": "005930", "name": "삼성전자", "price": 286500.0, "change_pct": 3.62, "prev_close_krx": 276500.0,
                                         "series": [276500.0, 286500.0], "history": {"dates": ["a", "b"], "close": [276500.0, 286500.0]},
                                         "trading_date": "2026-09-23", "source": "core", "data_source": "Naver Finance realtime item (KRX regular-session close)"}}}

    def test_prices_are_kept_and_empty_flows_are_filled(self) -> None:
        from src import main as main_mod
        fresh = {"trading_date": "2026-09-23", "missing": [],
                 "macro": {"KS11": {"price": 7080.92, "change_pct": 0.09, "history": {"dates": ["a"], "close": [7080.92]}}, "KQ11": {"price": 844.48, "change_pct": 1.21}},
                 "watchlist": {"005930": {"ticker": "005930", "name": "삼성전자", "price": 285000.0, "change_pct": 2.7, "series": [277500.0, 285000.0],
                                          "history": {"dates": ["a", "b"], "close": [277500.0, 285000.0]}, "trading_date": "2026-09-23", "source": "core",
                                          "foreign_net": 4513767, "institution_net": 1346883, "foreign_ratio": 46.63},
                               "402340": {"ticker": "402340", "name": "SK스퀘어", "price": 1178000.0, "change_pct": 3.88, "source": "dynamic", "trading_date": "2026-09-23"}}}
        out = main_mod._merge_price_file(self._old(), fresh)
        s = out["watchlist"]["005930"]
        self.assertEqual(s["price"], 286500.0)                       # 가격은 그대로
        self.assertEqual(s["change_pct"], 3.62)
        self.assertEqual(s["history"]["close"][-1], 286500.0)
        self.assertEqual(s["foreign_net"], 4513767)                   # 빈 칸(수급)은 채움
        self.assertIn("KRX", s["data_source"])
        self.assertEqual(out["macro"]["KS11"]["change_pct"], 0.9)    # 지수도 그대로
        self.assertEqual(out["macro"]["KQ11"]["change_pct"], 1.21)   # 없던 항목은 더함
        self.assertIn("402340", out["watchlist"])                     # 새 편입 종목은 더함

    def test_a_different_trading_date_is_a_new_file(self) -> None:
        from src import main as main_mod
        fresh = {"trading_date": "2026-09-28", "macro": {}, "watchlist": {}}
        self.assertIs(main_mod._merge_price_file(self._old(), fresh), fresh)

    def test_existing_flows_are_not_overwritten(self) -> None:
        from src import main as main_mod
        old = self._old(); old["watchlist"]["005930"]["foreign_net"] = 1; old["watchlist"]["005930"]["institution_net"] = 2; old["watchlist"]["005930"]["foreign_ratio"] = 46.0
        fresh = {"trading_date": "2026-09-23", "macro": {}, "watchlist": {"005930": {"ticker": "005930", "price": 1.0, "change_pct": 0.0, "foreign_net": 9, "institution_net": 9, "foreign_ratio": 1.0}}}
        s = main_mod._merge_price_file(old, fresh)["watchlist"]["005930"]
        self.assertEqual((s["foreign_net"], s["institution_net"], s["foreign_ratio"]), (1, 2, 46.0))
