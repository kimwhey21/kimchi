"""한국 종목별 외국인·기관 순매매 동향을 가져옵니다 (네이버 금융, 무료·로그인 불필요).

해외 개인투자자(외국인통합계좌로 한국 주식을 직접 사는 사람들)를 겨냥한 차별화
콘텐츠용 데이터입니다. "오늘 외국인이 어느 종목을 순매수/순매도했는지"는 국내
언론에는 흔하지만 영어로 정리해주는 곳이 거의 없어서, 이 도구의 핵심 차별점입니다.

pykrx의 투자자별 매매동향 API는 최근 KRX 로그인(KRX_ID/KRX_PW)을 요구하도록
바뀌어서 무료로 못 씁니다. 대신 네이버 증권의 종목별 투자자 동향 JSON
(m.stock.naver.com/api/stock/<코드>/trend)을 씁니다 — 로그인 없이 외국인·기관
순매매 수량과 외국인 보유율을 줍니다.

2026-09-18: 전에 긁던 HTML 표(finance.naver.com/item/frgn.naver)가 Npay 증권의
자바스크립트 페이지(stock.naver.com/domestic/stock/<코드>/investmentinfo)로 302
리다이렉트되기 시작해 "순매매 거래량 표를 찾을 못함"이 종목마다 찍혔고, 9/17·9/18
시세 파일의 외국인·기관 수급이 전부 비었다(0/27). 조용한 실패였다 — 경고만 남고
파이프라인은 계속 갔다. 그래서 JSON으로 바꿨다. 이것도 공식 API는 아니라 바뀔 수
있으니, 실패는 여전히 종목 하나만 빼고 계속 가되 **모든 종목이 비면** 시세 커밋
로그에 한 줄로 드러난다(attach_foreign_flows).
"""
from __future__ import annotations

import sys

import requests

_URL = "https://m.stock.naver.com/api/stock/{code}/trend?pageSize=1"
_HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def _to_int(s: str) -> int:
    return int(str(s).replace(",", "").replace("+", "").strip() or 0)


def _parse_row(row: dict) -> dict:
    """API 한 행 → {"date": "2026.09.17", "institution_net", "foreign_net", "foreign_ratio"}.
    수량은 순매매 '수량'(양수=순매수, 음수=순매도), 보유율은 %를 뗀 숫자."""
    biz = str(row.get("bizdate") or "")
    if len(biz) != 8 or not biz.isdigit():
        raise ValueError(f"bizdate가 이상함: {biz!r}")
    return {
        "date": f"{biz[:4]}.{biz[4:6]}.{biz[6:]}",
        "institution_net": _to_int(row.get("organPureBuyQuant") or 0),
        "foreign_net": _to_int(row.get("foreignerPureBuyQuant") or 0),
        "foreign_ratio": float(str(row.get("foreignerHoldRatio") or "0").replace("%", "").replace(",", "") or 0),
    }


def fetch_one(code: str) -> dict | None:
    """종목 하나의 가장 최근 거래일 외국인/기관 순매매 동향을 돌려줍니다.

    반환: {"date": "2026.09.17", "institution_net": int, "foreign_net": int,
           "foreign_ratio": float} 또는 실패 시 None.
    (institution_net/foreign_net은 순매매 "수량"이며, 양수=순매수 음수=순매도)
    """
    try:
        response = requests.get(_URL.format(code=code), headers=_HEADERS, timeout=10)
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list) or not rows:
            raise ValueError("투자자 동향 응답이 비어 있음")
        return _parse_row(rows[0])
    except Exception as e:
        print(f"[경고] 외국인 매매동향 조회 실패 (code={code}): {e!r}", file=sys.stderr)
        return None


def attach_foreign_flows(watchlist: dict, trading_date: str | None = None) -> dict:
    """price_data['watchlist']의 각 종목 dict에 외국인 매매 동향 필드를 붙여줍니다.

    watchlist: {ticker: {"ticker":..., "name":..., "price":..., ...}, ...}
    trading_date: 그날 기준일("2026-09-18"). 주면 API 응답의 bizdate와 대조해
    **전 거래일 값을 오늘 값으로 잘못 붙이지 않습니다** — 2026-09-18에 이 API가
    장 마감 직후에는 아직 전날(9/17) 행만 돌려줘서, 기존 코드가 그걸 "가장 최근"으로
    믿고 붙이는 바람에 오늘 시세 파일의 삼성전자·SK하이닉스 수급이 실제로는 어제
    것이었다(실측: 삼성전자 foreignerPureBuyQuant -2,170,687이 9/17 행과 글자까지
    같았다). 날짜가 안 맞으면 "못 받음"과 같게 취급합니다 — 틀린 날짜의 숫자를
    붙이는 것보다 안 붙이는 것이 낫습니다.
    실패한 종목은 그냥 필드 없이 남습니다 (경고만 출력, 파이프라인은 계속됨).
    """
    got = 0
    stale = 0
    for ticker, entry in watchlist.items():
        flow = fetch_one(ticker)
        if not flow:
            continue
        if trading_date and flow["date"].replace(".", "-") != trading_date:
            stale += 1
            continue
        got += 1
        entry["foreign_net"] = flow["foreign_net"]
        entry["institution_net"] = flow["institution_net"]
        entry["foreign_ratio"] = flow["foreign_ratio"]
    if watchlist and not got:
        if stale:
            # 조용한 실패 금지(2026-09-18): "수집이 죽었다"와 "아직 전날 값만 있다"는 다른 문제다.
            print(f"[경고] 외국인·기관 수급이 전부 전 거래일 값입니다({stale}/{len(watchlist)}종목) "
                  "— 네이버가 아직 오늘 행을 안 올렸습니다. 오늘 원고에는 쓰지 마세요.", file=sys.stderr)
        else:
            print(f"[경고] 외국인·기관 수급을 한 종목도 받지 못했습니다({len(watchlist)}종목) — 수집 경로가 죽었는지 보세요.",
                  file=sys.stderr)
    return watchlist
