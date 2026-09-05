"""글감 엔진 테스트.

외부 호출(야후·SEC)은 전부 mock으로 막습니다. 발행이 자동인데 테스트가 수동이면
의미가 없다는 저장소 원칙에 따라 `tests.yml`에서 그대로 돌아야 합니다.
"""
from __future__ import annotations

import datetime as dt
import json
import unittest
from unittest import mock

from src import story_engines


class ValuationTest(unittest.TestCase):
    def _run_with(self, infos: dict) -> dict:
        def fake_resolve(entry, market):
            info = infos.get(entry["ticker"])
            if info is None:
                return None, None
            ticker = mock.Mock()
            ticker.info = info
            return entry["ticker"], ticker

        with mock.patch.object(story_engines, "_resolve_yahoo", fake_resolve), \
             mock.patch.object(story_engines, "core_watchlist",
                               return_value=[{"ticker": t, "name": t} for t in infos]):
            return story_engines.valuation("us")

    def test_sorts_cheapest_first_and_computes_upside(self) -> None:
        result = self._run_with({
            "AAA": {"currentPrice": 100, "forwardPE": 20.0, "targetMeanPrice": 120,
                    "fiftyTwoWeekHigh": 200, "numberOfAnalystOpinions": 5},
            "BBB": {"currentPrice": 50, "forwardPE": 8.0, "targetMeanPrice": 40,
                    "fiftyTwoWeekHigh": 50, "numberOfAnalystOpinions": 3},
        })
        self.assertEqual([r["name"] for r in result["rows"]], ["BBB", "AAA"])
        self.assertEqual(result["rows"][1]["upside_pct"], 20.0)
        self.assertEqual(result["rows"][0]["off_52w_high_pct"], 0.0)
        self.assertEqual(result["median_forward_pe"], 14.0)

    def test_loss_making_is_not_the_cheapest_stock(self) -> None:
        """FWD PER이 음수인 종목이 '가장 싼 종목'으로 맨 위에 오면 안 됩니다."""
        result = self._run_with({
            "LOSS": {"currentPrice": 10, "forwardPE": -31.7, "targetMeanPrice": 8,
                     "fiftyTwoWeekHigh": 20, "numberOfAnalystOpinions": 4},
            "OKAY": {"currentPrice": 10, "forwardPE": 12.0, "targetMeanPrice": 12,
                     "fiftyTwoWeekHigh": 12, "numberOfAnalystOpinions": 4},
        })
        self.assertEqual([r["name"] for r in result["rows"]], ["OKAY"])
        self.assertEqual(result["loss_making"], ["LOSS"])

    def test_missing_estimate_is_reported_not_dropped(self) -> None:
        result = self._run_with({
            "ETF": {"currentPrice": 100, "forwardPE": None, "targetMeanPrice": None,
                    "fiftyTwoWeekHigh": 110},
        })
        self.assertEqual(result["rows"], [])
        self.assertEqual(result["no_estimate"], ["ETF"])


class RatingsTest(unittest.TestCase):
    def test_reiterations_are_counted_but_not_listed(self) -> None:
        """`Buy → Buy` 유지가 한 주에 수십 건 나오는데 그건 이야기가 아닙니다."""
        import pandas as pd

        frame = pd.DataFrame(
            [{"Firm": "A", "FromGrade": "Buy", "ToGrade": "Buy", "Action": "main"},
             {"Firm": "B", "FromGrade": "Neutral", "ToGrade": "Sell", "Action": "down"},
             {"Firm": "C", "FromGrade": "", "ToGrade": "Buy", "Action": "init"}],
            index=pd.to_datetime(["2026-09-03", "2026-09-03", "2026-09-02"]))
        ticker = mock.Mock()
        ticker.upgrades_downgrades = frame

        with mock.patch.object(story_engines, "_resolve_yahoo",
                               lambda entry, market: ("XYZ", ticker)), \
             mock.patch.object(story_engines, "core_watchlist",
                               return_value=[{"ticker": "XYZ", "name": "테스트"}]):
            result = story_engines.ratings("us", days=3650)

        self.assertEqual(result["reiterations"], 1)
        self.assertEqual([c["action"] for c in result["changes"]], ["down", "init"])
        self.assertEqual(result["downgrade_count"], 1)


class InsidersTest(unittest.TestCase):
    ATOM = ("<feed xmlns='http://www.w3.org/2005/Atom'><entry>"
            "<updated>{when}T00:00:00-04:00</updated>"
            "<link href='https://www.sec.gov/x/index.htm'/></entry></feed>")
    INDEX_HTML = ("<a href=\"/Archives/edgar/data/1/xslF345X06/form4.xml\">보기용</a>"
                  "<a href=\"/Archives/edgar/data/1/form4.xml\">원본</a>")
    FORM4 = """<ownershipDocument>
      <reportingOwner><rptOwnerName>TAN LIP BU</rptOwnerName></reportingOwner>
      <officerTitle>CEO</officerTitle>
      <transactionCode>P</transactionCode>
      <transactionShares><value>1000</value></transactionShares>
      <transactionPricePerShare><value>25.5</value></transactionPricePerShare>
    </ownershipDocument>"""

    def _fake_get(self, url, **kwargs):
        response = mock.Mock(status_code=200)
        response.raise_for_status = lambda: None
        if "browse-edgar" in url:
            when = (dt.date.today() - dt.timedelta(days=1)).isoformat()
            response.text = self.ATOM.format(when=when)
        elif url.endswith("index.htm"):
            response.text = self.INDEX_HTML
        else:
            response.text = self.FORM4
        return response

    def test_picks_raw_xml_not_the_xsl_rendered_copy(self) -> None:
        seen = []

        def recording_get(url, **kwargs):
            seen.append(url)
            return self._fake_get(url, **kwargs)

        with mock.patch.object(story_engines.requests, "get", recording_get), \
             mock.patch.object(story_engines, "core_watchlist",
                               return_value=[{"ticker": "INTC", "name": "인텔"}]):
            result = story_engines.insiders(days=7)

        self.assertTrue(any(u.endswith("/form4.xml") and "/xsl" not in u for u in seen))
        self.assertEqual(len(result["buys"]), 1)
        buy = result["buys"][0]
        self.assertEqual(buy["value_usd"], 25500)
        self.assertEqual(buy["owner"], "TAN LIP BU")
        self.assertEqual(buy["title"], "CEO")

    def test_sales_are_excluded(self) -> None:
        """매도(코드 S)는 세금·자산배분이 섞여 있어 신호로 쓰지 않습니다."""
        def selling_get(url, **kwargs):
            response = self._fake_get(url, **kwargs)
            if not ("browse-edgar" in url or url.endswith("index.htm")):
                response.text = self.FORM4.replace(
                    "<transactionCode>P</transactionCode>",
                    "<transactionCode>S</transactionCode>")
            return response

        with mock.patch.object(story_engines.requests, "get", selling_get), \
             mock.patch.object(story_engines, "core_watchlist",
                               return_value=[{"ticker": "INTC", "name": "인텔"}]):
            result = story_engines.insiders(days=7)
        self.assertEqual(result["buys"], [])


class FlowsTest(unittest.TestCase):
    def test_opposed_needs_both_sides_and_ranks_by_overlap(self) -> None:
        payload = {"watchlist": {
            "a": {"name": "반대큼", "ticker": "1", "change_pct": -3.0,
                  "foreign_net": -400, "institution_net": 300},
            "b": {"name": "반대작음", "ticker": "2", "change_pct": 1.0,
                  "foreign_net": -50, "institution_net": 40},
            "c": {"name": "같은방향", "ticker": "3", "change_pct": 2.0,
                  "foreign_net": 100, "institution_net": 100},
            "d": {"name": "결측", "ticker": "4", "change_pct": 0.5,
                  "foreign_net": None, "institution_net": 10},
        }}
        with mock.patch.object(story_engines.Path, "exists", lambda self: True), \
             mock.patch.object(story_engines.Path, "read_text",
                               lambda self, encoding=None: json.dumps(payload)):
            result = story_engines.flows("2026-09-04")

        self.assertEqual([r["name"] for r in result["opposed"]], ["반대큼", "반대작음"])
        self.assertEqual([r["name"] for r in result["aligned"]], ["같은방향"])

    def test_missing_file_reports_instead_of_raising(self) -> None:
        with mock.patch.object(story_engines.Path, "exists", lambda self: False):
            result = story_engines.flows("1999-01-01")
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()


class KrInsidersTest(unittest.TestCase):
    """DART 파싱 테스트.

    실제 응답은 2026-09-06에 받아 확인했습니다(목록 15건, 본문 세부변동내역까지).
    다만 짧은 시간에 30여 번을 두드려 IP가 일시 차단됐으므로, 여기서는 그때 받은
    구조를 그대로 옮겨 mock으로 검증합니다.
    """

    LIST_HTML = """
      <tr><td>1</td><td class="tL"><span class="innerWrap">
        <a href="javascript:openCorpInfoNew('01222867', 'w', '/x.ax');" title="x">SK하이닉스</a>
        </span></td>
        <td class="tL"><a href="/dsaf001/main.do?rcpNo=20260904000539" id="r">보고서</a></td>
        <td class="tL ellipsis" title="홍길동">홍길동</td><td>2026.09.04</td></tr>
    """
    MAIN_JS = """
      node1['text'] = "1. 발행회사에 관한 사항";
      node1['dcmNo'] = "111"; node1['eleId'] = "1";
      node1['offset'] = "1"; node1['length'] = "2"; node1['dtd'] = "dart4.xsd";
      node2['text'] = "3. 특정증권등의 소유상황";
      node2['dcmNo'] = "11568397"; node2['eleId'] = "4";
      node2['offset'] = "11024"; node2['length'] = "17528"; node2['dtd'] = "dart4.xsd";
    """
    BODY = """<table><tr><td>장내매수(+)</td><td>2026.09.02</td><td>보통주</td>
      <td>730,238</td><td>10,000</td><td>740,238</td><td>85,300</td></tr></table>"""
    BODY_LOAN = """<table><tr><td>기타(-)</td><td>2026.09.02</td><td>보통주</td>
      <td>730,238</td><td>-10,000</td><td>720,238</td><td>-</td></tr></table>"""

    def _session(self, body: str):
        def fake(url, params=None, data=None, timeout=None):
            response = mock.Mock(status_code=200)
            response.raise_for_status = lambda: None
            response.apparent_encoding = "utf-8"
            if "detailSearch" in url:
                response.text = self.LIST_HTML
            elif "main.do" in url:
                response.text = self.MAIN_JS
            else:
                response.text = body
            return response

        session = mock.Mock()
        session.get.side_effect = lambda url, **kw: fake(url, **kw)
        session.post.side_effect = lambda url, **kw: fake(url, **kw)
        session.headers = {}
        return session

    def _run(self, body: str) -> dict:
        with mock.patch.object(story_engines.requests, "Session",
                               return_value=self._session(body)), \
             mock.patch.object(story_engines.time, "sleep", lambda *_: None), \
             mock.patch.object(story_engines, "core_watchlist",
                               return_value=[{"ticker": "000660", "name": "SK하이닉스"}]):
            return story_engines.kr_insiders(days=7, scan=5)

    def test_parses_on_market_purchase_and_flags_core_name(self) -> None:
        result = self._run(self.BODY)
        self.assertEqual(len(result["buys"]), 1)
        buy = result["buys"][0]
        self.assertEqual(buy["company"], "SK하이닉스")
        self.assertTrue(buy["is_core"])
        self.assertEqual(buy["shares"], 10000)
        self.assertEqual(buy["price"], 85300)
        self.assertEqual(buy["value_krw"], 853_000_000)
        self.assertEqual(buy["date"], "2026-09-02")

    def test_loan_repayment_is_not_a_purchase(self) -> None:
        """대여주식상환·상속·증여는 본인이 값을 치르고 산 것이 아닙니다."""
        self.assertEqual(self._run(self.BODY_LOAN)["buys"], [])

    def test_fetch_failures_are_counted_not_silently_zero(self) -> None:
        """'매수가 없었다'와 '서버가 끊었다'가 같은 0건으로 보이면 안 됩니다."""
        session = self._session(self.BODY)

        def dying_get(url, **kwargs):
            if "main.do" in url:
                raise story_engines.requests.exceptions.ConnectionError("aborted")
            return session.get.side_effect(url, **kwargs)

        session.get.side_effect = dying_get
        with mock.patch.object(story_engines.requests, "Session", return_value=session), \
             mock.patch.object(story_engines.time, "sleep", lambda *_: None), \
             mock.patch.object(story_engines, "core_watchlist", return_value=[]):
            result = story_engines.kr_insiders(days=7, scan=5)
        self.assertEqual(result["buys"], [])
        self.assertEqual(result["failed"], 1)


class InstitutionsTest(unittest.TestCase):
    """13F 정보표 파싱.

    실제 응답은 2026-09-06에 버크셔 13F로 확인했습니다 — ALLY 한 종목이 매니저별로
    다섯 줄에 나뉘어 있었습니다.
    """

    TABLE = """<informationTable
      xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
      <infoTable><nameOfIssuer>ALLY FINL INC</nameOfIssuer><titleOfClass>COM</titleOfClass>
        <cusip>02005N100</cusip><value>100</value>
        <shrsOrPrnAmt><sshPrnamt>1000</sshPrnamt></shrsOrPrnAmt></infoTable>
      <infoTable><nameOfIssuer>ALLY FINL INC</nameOfIssuer><titleOfClass>COM</titleOfClass>
        <cusip>02005N100</cusip><value>50</value>
        <shrsOrPrnAmt><sshPrnamt>500</sshPrnamt></shrsOrPrnAmt></infoTable>
      <infoTable><nameOfIssuer>ALPHABET INC</nameOfIssuer><titleOfClass>CAP STK CL A</titleOfClass>
        <cusip>02079K305</cusip><value>900</value>
        <shrsOrPrnAmt><sshPrnamt>300</sshPrnamt></shrsOrPrnAmt></infoTable>
      <infoTable><nameOfIssuer>ALPHABET INC</nameOfIssuer><titleOfClass>CAP STK CL C</titleOfClass>
        <cusip>02079K107</cusip><value>800</value>
        <shrsOrPrnAmt><sshPrnamt>200</sshPrnamt></shrsOrPrnAmt></infoTable>
    </informationTable>"""

    def test_same_issuer_rows_are_summed_by_cusip(self) -> None:
        """한 종목이 매니저별로 쪼개져 나옵니다. 안 합치면 보유량이 몇 분의 일이 됩니다."""
        holdings = story_engines._13f_holdings(self.TABLE)
        self.assertEqual(holdings["02005N100"]["shares"], 1500)
        self.assertEqual(holdings["02005N100"]["value"], 150)

    def test_share_classes_stay_separate(self) -> None:
        """알파벳 A와 C는 이름이 같고 CUSIP이 다릅니다. 합치면 안 됩니다."""
        holdings = story_engines._13f_holdings(self.TABLE)
        self.assertEqual(holdings["02079K305"]["shares"], 300)
        self.assertEqual(holdings["02079K107"]["shares"], 200)
        self.assertEqual(holdings["02079K305"]["klass"], "CAP STK CL A")
