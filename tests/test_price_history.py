"""시세 파일의 3개월 이력(`history`)과 그것으로 그리는 그래픽(2026-09-08).

본문 그래픽이 8거래일 스파크라인뿐이라 흐름이 안 보인다는 지적에서 나왔다.
이력은 수집기가 시세와 같은 소스에서 함께 받고, 지수 일봉이 늦는 날의 보완
(네이버 확정 종가 덧붙이기)도 이력에 같이 반영돼야 그림의 마지막 점이 맞는다.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from PIL import Image

from src import data_graphics, fetch_kr, price_history

DATES = pd.bdate_range("2026-05-20", periods=80)
FRAME = pd.DataFrame({"Close": [6000.0 + i for i in range(80)]}, index=DATES)


class HistoryModuleTest(unittest.TestCase):
    def test_from_frame_keeps_the_last_days_with_dates(self) -> None:
        history = price_history.from_frame(FRAME)
        self.assertEqual(len(history["close"]), price_history.DAYS)
        self.assertEqual(len(history["dates"]), price_history.DAYS)
        self.assertEqual(history["dates"][-1], DATES[-1].date().isoformat())
        self.assertEqual(history["close"][-1], 6079.0)

    def test_append_and_replace(self) -> None:
        history = {"dates": ["2026-09-04", "2026-09-07"], "close": [6687.21, 6995.39]}
        added = price_history.append(history, "2026-09-08", 6954.52)
        self.assertEqual(added["dates"][-1], "2026-09-08")
        self.assertEqual(added["close"][-1], 6954.52)
        self.assertEqual(len(added["close"]), 3)
        again = price_history.append(added, "2026-09-08", 6960.0)   # 같은 날 두 번이면 교체
        self.assertEqual(len(again["close"]), 3)
        self.assertEqual(again["close"][-1], 6960.0)
        self.assertEqual(price_history.replace_last(history, 7000.0)["close"][-1], 7000.0)
        self.assertIsNone(price_history.replace_last(None, 1.0))


class FetchCarriesHistoryTest(unittest.TestCase):
    def test_kr_fetch_one_includes_history(self) -> None:
        with patch.object(fetch_kr.fdr, "DataReader", return_value=FRAME):
            result = fetch_kr._fetch_one("005930", "삼성전자")
        self.assertEqual(len(result["series"]), 8)             # 스파크라인은 그대로
        self.assertEqual(len(result["history"]["close"]), price_history.DAYS)

    def test_lagging_index_append_reaches_history(self) -> None:
        yesterday = (fetch_kr.dt.date.today() - fetch_kr.dt.timedelta(days=1)).isoformat()
        entry = {"ticker": "KS11", "price": 6995.39, "change_pct": 4.61,
                 "series": [6687.21, 6995.39], "trading_date": yesterday,
                 "history": {"dates": ["2026-09-04", yesterday], "close": [6687.21, 6995.39]}}
        quote = {"ms": "CLOSE", "nv": 695452, "cv": -4087, "cr": -0.58, "cd": "KOSPI"}
        result = fetch_kr._apply_final_index_quote(entry, "KS11", quote)
        self.assertEqual(result["history"]["close"][-1], 6954.52)
        self.assertEqual(result["history"]["dates"][-1], fetch_kr.dt.date.today().isoformat())


@unittest.skipUnless(data_graphics.has_korean_font(), "한글 폰트가 없어 렌더를 건너뜁니다")
class NewBuildersTest(unittest.TestCase):
    PRICE = {
        "macro": {"KS11": {"ticker": "KS11", "name": "코스피", "price": 6954.52, "change_pct": -0.58,
                           "unit": "", "history": price_history.from_frame(FRAME)},
                  "USD/KRW": {"ticker": "USD/KRW", "name": "원/달러 환율", "price": 1344.6,
                              "change_pct": -0.18, "unit": "원"}},
        "watchlist": {"005930": {"ticker": "005930", "name": "삼성전자", "price": 269500,
                                 "change_pct": -0.19, "history": price_history.from_frame(FRAME)},
                      "000660": {"ticker": "000660", "name": "SK하이닉스", "price": 300000,
                                 "change_pct": 1.0, "series": [290000, 300000]}},
    }

    def _out(self) -> Path:
        return Path(tempfile.mkdtemp()) / "g.png"

    def test_price_history_draws_index_and_stock(self) -> None:
        out = self._out()
        data_graphics.price_history(self.PRICE, out, ticker="KS11", guide=7000, guide_label="7,000선")
        with Image.open(out) as image:
            self.assertEqual(image.size, (data_graphics.W, 600))
        data_graphics.price_history(self.PRICE, self._out(), ticker="005930", title="삼성전자 3개월")

    def test_price_history_without_history_raises(self) -> None:
        with self.assertRaises(ValueError):
            data_graphics.price_history(self.PRICE, self._out(), ticker="000660")
        with self.assertRaises(ValueError):
            data_graphics.price_history(self.PRICE, self._out(), ticker="999999")

    def test_investor_flows_requires_source(self) -> None:
        with self.assertRaises(ValueError):
            data_graphics.investor_flows(self.PRICE, self._out(), values={"외국인": 1}, source="")
        out = self._out()
        data_graphics.investor_flows(self.PRICE, out, values={"외국인": 6482, "기관": 6428, "개인": -13333},
                                     source="아시아경제 마감 집계")
        self.assertTrue(out.exists())

    def test_number_cards_mixes_tickers_and_items(self) -> None:
        out = self._out()
        data_graphics.number_cards(self.PRICE, out, tickers=["KS11", "USD/KRW"],
                                   items=[{"label": "WTI", "value": "93.10달러", "change": "+1.8%"}],
                                   note="장중 7,171까지 올랐다가 밀렸습니다.")
        self.assertTrue(out.exists())
        with self.assertRaises(ValueError):
            data_graphics.number_cards(self.PRICE, self._out(), tickers=["KS11"])   # 카드 하나는 안 됨


if __name__ == "__main__":
    unittest.main()
