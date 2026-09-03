"""그날 거래대금 상위 종목 편입과, 그에 딸린 가드 3개를 확인합니다.

가드가 필요한 이유는 워치리스트가 21개 코어 + 그날 편입 종목으로 늘어났기
때문입니다. 늘어난 목록이 그대로 흘러가면 외국인 표가 30줄이 되고, 처음 보는
종목 이름으로 사진을 찾게 되고, 대표 이미지에 매일 다른 종목이 걸립니다.
"""
from __future__ import annotations

import unittest
from unittest import mock

from src import fetch_movers, publish_editorial, render_html


def _naver_item(code: str, name: str, value: int, cap: int, end_type: str = "stock") -> dict:
    return {
        "itemCode": code,
        "stockName": name,
        "stockEndType": end_type,
        "accumulatedTradingValueRaw": f"{value}",
        "marketValueRaw": f"{cap}",
    }


class TopTurnoverTest(unittest.TestCase):
    def _fetch(self, items: list[dict], **kwargs) -> list[dict]:
        with mock.patch.object(fetch_movers, "_universe", return_value=items):
            return fetch_movers.fetch_top_turnover(
                exclude_tickers=kwargs.pop("exclude", set()),
                markets=("KOSPI",),
                **kwargs,
            )

    def test_ranks_by_trading_value_not_by_change(self) -> None:
        picked = self._fetch(
            [
                _naver_item("105560", "KB금융", 270_000_000_000, 30_000_000_000_000),
                _naver_item("034020", "두산에너빌리티", 253_000_000_000, 40_000_000_000_000),
            ],
            count=2,
        )
        self.assertEqual([row["name"] for row in picked], ["KB금융", "두산에너빌리티"])

    def test_drops_etf_preferred_and_small_caps(self) -> None:
        picked = self._fetch(
            [
                # 거래대금 1위지만 ETF라 시황에서 개별 종목으로 다룰 대상이 아님
                _naver_item("069500", "KODEX 200", 2_497_000_000_000, 9e15, end_type="etf"),
                # 우선주는 본주와 같은 이야기를 두 번 하게 됨
                _naver_item("005935", "삼성전자우", 348_000_000_000, 40_000_000_000_000),
                # 시가총액 하한 미달
                _naver_item("123450", "소형주", 900_000_000_000, 500_000_000_000),
                _naver_item("105560", "KB금융", 270_000_000_000, 30_000_000_000_000),
            ],
            count=4,
        )
        self.assertEqual([row["name"] for row in picked], ["KB금융"])

    def test_excludes_core_watchlist_tickers(self) -> None:
        picked = self._fetch(
            [
                _naver_item("005930", "삼성전자", 3_444_000_000_000, 1_400_000_000_000_000),
                _naver_item("402340", "SK스퀘어", 344_000_000_000, 30_000_000_000_000),
            ],
            count=2,
            exclude={"005930"},
        )
        self.assertEqual([row["name"] for row in picked], ["SK스퀘어"])

    def test_network_failure_returns_empty_list(self) -> None:
        """조회에 실패해도 코어 워치리스트만으로 글이 나가야 합니다."""
        with mock.patch.object(fetch_movers, "_universe", side_effect=OSError("boom")):
            self.assertEqual(
                fetch_movers.fetch_top_turnover(set(), markets=("KOSPI",)), []
            )


def _nasdaq_row(symbol: str, name: str, price: str, volume: str, cap: str) -> dict:
    return {
        "symbol": symbol,
        "name": name,
        "lastsale": price,
        "volume": volume,
        "marketCap": cap,
        "sector": "Technology",
    }


class UsTopDollarVolumeTest(unittest.TestCase):
    def _fetch(self, rows: list[dict], **kwargs) -> list[dict]:
        response = mock.Mock()
        response.json.return_value = {"data": {"rows": rows}}
        response.raise_for_status.return_value = None
        with mock.patch.object(fetch_movers.requests, "get", return_value=response):
            return fetch_movers.fetch_top_dollar_volume_us(
                exclude_tickers=kwargs.pop("exclude", set()), **kwargs
            )

    def test_ranks_by_price_times_volume(self) -> None:
        """스크리너는 거래대금을 주지 않으므로 종가 x 거래량으로 계산합니다."""
        picked = self._fetch(
            [
                # 주가가 낮아 거래량은 많지만 거래대금은 작은 종목
                _nasdaq_row("F", "Ford Motor Company", "$12.00", "100000000", "5e10"),
                _nasdaq_row("DELL", "Dell Technologies Inc.", "$180.00", "100000000", "3e11"),
            ],
            count=2,
        )
        self.assertEqual([row["ticker"] for row in picked], ["DELL", "F"])

    def test_cleans_legal_suffixes_from_name(self) -> None:
        picked = self._fetch(
            [_nasdaq_row("PLTR", "Palantir Technologies Inc. Class A", "$170.00", "40000000", "4e11")],
            count=1,
        )
        self.assertEqual(picked[0]["name"], "Palantir Technologies")

    def test_drops_preferred_units_and_small_caps(self) -> None:
        picked = self._fetch(
            [
                _nasdaq_row("ABC^B", "Some Bank Preferred Series B", "$25.00", "90000000", "5e10"),
                _nasdaq_row("XYZU", "Startup Acquisition Unit", "$10.00", "90000000", "5e10"),
                _nasdaq_row("TINY", "Tiny Corp. Common Stock", "$50.00", "90000000", "1e9"),
                _nasdaq_row("AVGO", "Broadcom Inc.", "$350.00", "40000000", "1.7e12"),
            ],
            count=4,
        )
        self.assertEqual([row["ticker"] for row in picked], ["AVGO"])

    def test_network_failure_returns_empty_list(self) -> None:
        with mock.patch.object(fetch_movers.requests, "get", side_effect=OSError("boom")):
            self.assertEqual(fetch_movers.fetch_top_dollar_volume_us(set()), [])


def _price_data(count: int) -> dict:
    """순매수 +N ~ 순매도 -N 종목이 고르게 있는 워치리스트를 만듭니다."""
    watchlist = {}
    for index in range(count):
        watchlist[f"{index:06d}"] = {
            "ticker": f"{index:06d}",
            "name": f"종목{index}",
            "name_en": f"Stock {index}",
            "price": 1000.0,
            "change_pct": 0.5,
            "foreign_net": (count // 2 - index) * 1000,
            "foreign_ratio": 10.0,
            "source": "core",
        }
    return {"macro": {}, "watchlist": watchlist}


class ForeignFlowTableTest(unittest.TestCase):
    def test_caps_long_table_to_top_and_bottom_five(self) -> None:
        rows = render_html._build_foreign_flow_table(_price_data(27), "ko")
        self.assertEqual(len(rows), 10)
        self.assertEqual(rows[0]["foreign_net"], max(r["foreign_net"] for r in rows))
        self.assertEqual(rows[-1]["foreign_net"], min(r["foreign_net"] for r in rows))

    def test_keeps_short_table_whole(self) -> None:
        rows = render_html._build_foreign_flow_table(_price_data(8), "ko")
        self.assertEqual(len(rows), 8)


class PhotoGuardTest(unittest.TestCase):
    def setUp(self) -> None:
        self.price_data = {
            "watchlist": {
                "005930": {"name": "삼성전자", "name_en": "Samsung Electronics", "source": "core"},
                "010140": {"name": "삼성중공업", "name_en": "삼성중공업", "source": "dynamic"},
            }
        }

    def test_core_stock_name_passes(self) -> None:
        self.assertEqual(
            publish_editorial._concrete_image_query(
                "Samsung Electronics semiconductor", self.price_data
            ),
            "Samsung Electronics semiconductor",
        )

    def test_dynamic_stock_name_is_rejected(self) -> None:
        """그날 편입된 종목은 사진 대상이 아닙니다 — 검수 없이 공개되는 경로라서."""
        self.assertIsNone(
            publish_editorial._concrete_image_query("삼성중공업 shipyard", self.price_data)
        )


if __name__ == "__main__":
    unittest.main()
