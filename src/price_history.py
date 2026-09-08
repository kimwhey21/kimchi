"""시세 파일에 담는 최근 3개월 종가 이력(`history`).

왜 생겼는가 (2026-09-08)
------------------------
본문 그래픽이 8거래일 스파크라인뿐이라 "흐름"이 보이지 않았고, 사용자가 시각자료를
지적했다. 벤치마크(재테크농부) 이미지의 큰 몫은 기간 차트 스크린샷이다. 우리는
시세 파일에 최근 70거래일 종가를 함께 담아 `data_graphics.price_history`가 직접
그린다 — 스크린샷과 달리 원고와 같은 출처라 어긋나지 않는다.

형식: {"dates": ["2026-06-02", ...], "close": [8788.38, ...]} (오래된 것부터).
"""
from __future__ import annotations

DAYS = 70              # 거래일 기준 약 3개월 남짓
CALENDAR_DAYS = 120    # 조회 창. 주말·공휴일을 빼고도 DAYS를 채우도록 넉넉히


def from_frame(frame) -> dict:
    """FinanceDataReader·yfinance 일봉 프레임에서 유효 종가 이력을 뽑습니다."""
    valid = frame["Close"].dropna().tail(DAYS)
    dates: list[str] = []
    for index in valid.index:
        try:
            dates.append(index.date().isoformat())
        except AttributeError:
            dates.append(str(index)[:10])
    return {"dates": dates, "close": [round(float(v), 4) for v in valid.tolist()]}


def replace_last(history: dict | None, price: float) -> dict | None:
    """마지막 행(오늘)의 종가를 확정값으로 바꿉니다."""
    if not history or not history.get("close"):
        return history
    close = list(history["close"])
    close[-1] = round(float(price), 4)
    return {**history, "close": close}


def append(history: dict | None, date: str, price: float) -> dict:
    """오늘 행이 아직 없을 때 덧붙입니다(지수 일봉이 늦는 날)."""
    dates = list((history or {}).get("dates") or [])
    close = list((history or {}).get("close") or [])
    if dates and dates[-1] == date:
        close[-1] = round(float(price), 4)
    else:
        dates.append(date)
        close.append(round(float(price), 4))
    return {"dates": dates[-DAYS:], "close": close[-DAYS:]}
