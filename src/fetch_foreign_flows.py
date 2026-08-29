"""한국 종목별 외국인·기관 순매매 동향을 가져옵니다 (네이버 금융, 무료·로그인 불필요).

해외 개인투자자(외국인통합계좌로 한국 주식을 직접 사는 사람들)를 겨냥한 차별화
콘텐츠용 데이터입니다. "오늘 외국인이 어느 종목을 순매수/순매도했는지"는 국내
언론에는 흔하지만 영어로 정리해주는 곳이 거의 없어서, 이 도구의 핵심 차별점입니다.

pykrx의 투자자별 매매동향 API는 최근 KRX 로그인(KRX_ID/KRX_PW)을 요구하도록
바뀌어서 무료로 못 씁니다. 대신 네이버 금융의 종목별 페이지
(finance.naver.com/item/frgn.naver)는 로그인 없이 같은 정보(외국인 순매매량,
외국인 보유율)를 제공해서 이걸 씁니다.

주의: 이건 공식 API가 아니라 페이지를 파싱하는 방식이라, 네이버가 페이지
구조를 바꾸면 깨질 수 있습니다. 실패해도 파이프라인이 멈추면 안 되므로,
종목 하나가 실패해도 그 종목만 빼고 계속 진행합니다.
"""
from __future__ import annotations

import re
import sys

import requests

_URL = "https://finance.naver.com/item/frgn.naver?code={code}"
_ROW_RE = re.compile(
    r'(\d{4}\.\d{2}\.\d{2}).*?'
    r'<td width="67" class="num"><span class="tah p11">([\d,]+)</span></td>.*?'
    r'<td width="66" class="num"><span class="tah p11[^"]*">([+\-\d,]+)</span></td>.*?'
    r'<td width="80" class="num"><span class="tah p11[^"]*">([+\-\d,]+)</span></td>.*?'
    r'<td width="60" class="num"><span class="tah p11">([\d.]+)%</span></td>',
    re.DOTALL,
)


def _to_int(s: str) -> int:
    return int(s.replace(",", "").replace("+", ""))


def fetch_one(code: str) -> dict | None:
    """종목 하나의 가장 최근 거래일 외국인/기관 순매매 동향을 돌려줍니다.

    반환: {"date": "2026.08.28", "institution_net": int, "foreign_net": int,
           "foreign_ratio": float} 또는 실패 시 None.
    (institution_net/foreign_net은 순매매 "수량"이며, 양수=순매수 음수=순매도)
    """
    try:
        response = requests.get(
            _URL.format(code=code), headers={"User-Agent": "Mozilla/5.0"}, timeout=10
        )
        response.raise_for_status()
        html = response.content.decode("euc-kr", errors="replace")
        table_idx = html.find("외국인 기관 순매매 거래량")
        if table_idx == -1:
            raise ValueError("순매매 거래량 표를 찾을 못함")
        chunk = html[table_idx : table_idx + 3000]
        m = _ROW_RE.search(chunk)
        if not m:
            raise ValueError("표 안의 최신 거래일 행을 파싱 못함")
        date, _close, institution, foreign, ratio = m.groups()
        return {
            "date": date,
            "institution_net": _to_int(institution),
            "foreign_net": _to_int(foreign),
            "foreign_ratio": float(ratio),
        }
    except Exception as e:
        print(f"[경고] 외국인 매매동향 조회 실패 (code={code}): {e!r}", file=sys.stderr)
        return None


def attach_foreign_flows(watchlist: dict) -> dict:
    """price_data['watchlist']의 각 종목 dict에 외국인 매매 동향 필드를 붙여줍니다.

    watchlist: {ticker: {"ticker":..., "name":..., "price":..., ...}, ...}
    실패한 종목은 그냥 필드 없이 남습니다 (경고만 출력, 파이프라인은 계속됨).
    """
    for ticker, entry in watchlist.items():
        flow = fetch_one(ticker)
        if flow:
            entry["foreign_net"] = flow["foreign_net"]
            entry["institution_net"] = flow["institution_net"]
            entry["foreign_ratio"] = flow["foreign_ratio"]
    return watchlist
