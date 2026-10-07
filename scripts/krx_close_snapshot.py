"""KRX 정규장 종가 '사진' — 15:31~15:59 KST에 네이버 폴링을 받아 data/krx_close/<날짜>.json에 남긴다 (2026-09-28).

    python -m scripts.krx_close_snapshot        # 창 밖이면 찍지 않고 이유를 찍는다(종료 코드 0)

왜: 폴링의 nv는 15:30 정규장 종가로 멈췄다가 **16:00부터 KRX 애프터마켓(2026-09-14부터 16~20시 실시간 거래, 그전에는 시간외 단일가)**를 따라 다시 움직인다.
넥스트레이드 애프터마켓(~20:00) 때문에 ms도 OPEN으로 남는다. 그래서 16:20 수집(fetch_kr)은 정규장 종가를 확인할 수 없었다
(2026-09-28 첫 실전에서 세 번 모두 멈춤; 카카오 nv가 17:40에 33,950→34,000으로 바뀌는 것을 확인). 정규장 종가를 읽을 수 있는
때는 15:30~16:00뿐이라 그때 찍어 두고, fetch_kr가 그 파일을 쓴다. 대상: 코어 워치리스트 + 편입 후보(두 시장 시가총액 상위 universe).
krx_close.yml이 15:32·15:40·15:48에 돌리고, 이미 찍었으면 건너뛴다.

2026-10-05부터 **전 종목**(코스피·코스닥 주식 2,700여 개)의 종가·기준가를 `close`에 함께 남긴다 — 본진 종목 페이지(stock_db)가
다음 금융 일별 시세와 대조하는 두 번째 원천이다(전에는 종목 페이지가 넥스트레이드까지 합친 값을 '거래소 종가'로 보여 줬다).
`quotes`(코어+편입 후보, 폴링 필드 그대로)는 fetch_kr가 쓰고, `close`는 {코드: [종가, 기준가]}로 짧게 적는다.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import requests
import yaml

from src import fetch_kr, fetch_movers

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "data" / "krx_close"
KST = dt.timezone(dt.timedelta(hours=9))
KEEP = ("nv", "pcv", "cv", "cr", "rf", "ms", "sv")
FULL_MARKET = 2000   # 전 종목 사진이 이보다 적으면(목록을 못 받은 실행) 다음 예약이 다시 찍는다


def in_window(now: dt.datetime) -> bool:
    # 휴장일엔 폴링이 전 거래일 값을 그대로 줘서 그 값이 오늘 날짜 파일로 남는다(2026-10-05 대체 휴일 시험) — 찍지 않는다
    from src.stock_db import KRX_HOLIDAYS, close_window
    start, end = close_window(now.date())     # 수능일은 16:31~16:59 (2026-10-05)
    return now.weekday() < 5 and now.date().isoformat() not in KRX_HOLIDAYS and start <= now.time() < end


def codes() -> list[str]:
    config = yaml.safe_load((ROOT / "config" / "watchlist_kr.yaml").read_text(encoding="utf-8")) or {}
    core = [str(w["ticker"]) for w in config.get("watchlist") or []]
    settings = config.get("dynamic") or {}
    extra: list[str] = []
    for market in settings.get("markets") or ("KOSPI", "KOSDAQ"):
        try:
            extra += [str(r.get("itemCode")) for r in fetch_movers._universe(market, settings.get("universe_size", 100)) if r.get("itemCode")]
        except Exception as error:   # noqa: BLE001 — 편입 후보를 못 받아도 코어는 찍는다. 이유는 찍는다
            print(f"[경고] {market} 편입 후보 목록을 못 받았습니다: {error!r}")
    return list(dict.fromkeys(core + extra))


def all_codes() -> list[str]:
    """코스피·코스닥 전 종목(주식만) — stock_db와 같은 목록. 못 받으면 빈 목록(코어·편입 후보 사진은 그대로 찍는다)."""
    import requests
    from src import stock_db
    session = requests.Session()
    session.headers.update(stock_db.UA)
    try:
        return [r["code"] for r in stock_db.list_market(session, "KOSPI") + stock_db.list_market(session, "KOSDAQ")]
    except Exception as error:   # noqa: BLE001 — 전 종목을 못 받아도 코어 사진은 찍는다. 이유는 찍고, stock_db가 사진 없음을 알린다
        print(f"[경고] 전 종목 목록을 못 받았습니다 — 종목 페이지 대조용 사진은 빠집니다: {error!r}")
        return []


LOCK_FROM, LOCK_UNTIL = dt.timedelta(minutes=21), dt.timedelta(minutes=49)   # 마감 뒤 21~49분(보통 15:51~16:19)
LOCK_AGREE = 0.99   # 잠그는 값이 15시 반 사진과 이만큼 같아야 한다 — 아직 장중(20분 늦은) 값이면 크게 다르다


def lock_window(now: dt.datetime) -> bool:
    """거래소 정보데이터시스템·야후가 정규장 종가를 주는 때(2026-10-07 실측) — 20분 늦게 오므로 마감 21분 뒤부터, 16:00에 시작하는
    시간외 거래가 20분 늦게 비치기 전(마감 49분 뒤)까지."""
    from src.stock_db import KRX_HOLIDAYS, krx_hours
    if now.weekday() >= 5 or now.date().isoformat() in KRX_HOLIDAYS:
        return False
    close = dt.datetime.combine(now.date(), krx_hours(now.date())[1], tzinfo=KST)
    return close + LOCK_FROM <= now < close + LOCK_UNTIL


def _agree(got: dict[str, float], snap: dict[str, float]) -> float:
    both = [c for c in got if c in snap]
    return sum(abs(got[c] - snap[c]) < 0.5 for c in both) / len(both) if both else 0.0


def lock(now: dt.datetime) -> int:
    """15:53 — 거래소 공식 전 종목 시세와 야후 종가를 받아 그날 사진 파일에 잠근다(`krx`·`yahoo`). 16:20 수집과 저녁 종목 DB는
    살아 있는 야후·네이버·거래소에 다시 묻지 않고 이 값을 쓴다(그때는 시간외 가격이 '종가' 칸에 들어온다)."""
    from src import stock_db
    day = now.date().isoformat()
    path = DIR / f"{day}.json"
    if not path.exists():
        print(f"[경고] {path.name} 사진이 없어 종가를 잠그지 못합니다")
        return 1
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("krx") and doc.get("yahoo"):
        print(f"{path.name}: 이미 잠갔습니다({doc.get('locked_at')})")
        return 0
    snap = {c: float(v[0]) for c, v in (doc.get("close") or {}).items()}
    out: dict = {}
    krx = stock_db.KrxOfficial(allow_today=True)
    table = krx.table(day)
    rate = _agree({c: v[0] for c, v in table.items()}, snap)
    if table and rate >= LOCK_AGREE:
        out["krx"] = {c: [cl, b] for c, (cl, b) in table.items()}
    else:
        print(f"[경고] 거래소 공식 시세를 잠그지 않습니다 — {krx.error or f'사진과 같은 비율 {rate:.1%}'}")
    session = requests.Session()
    session.headers.update(stock_db.UA)
    listing = stock_db.list_market(session, "KOSPI") + stock_db.list_market(session, "KOSDAQ")
    yahoo = stock_db.yahoo_bulk([(r["code"], r["market"], day) for r in listing], allow_today=True)
    yv = {c: v for (c, _), v in yahoo.items()}
    rate_y = _agree(yv, snap)
    if yv and rate_y >= LOCK_AGREE:
        out["yahoo"] = yv
    else:
        print(f"[경고] 야후 종가를 잠그지 않습니다 — 받은 종목 {len(yv)}개, 사진과 같은 비율 {rate_y:.1%}")
    if not lock_window(dt.datetime.now(KST)):
        print("[경고] 받는 사이 잠그는 창이 닫혀 버립니다(시간외 가격이 섞일 수 있다)")
        return 1
    if not out:
        return 1
    doc.update(out, locked_at=dt.datetime.now(KST).isoformat(timespec="seconds"))
    path.write_text(json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{path.name}: 종가 잠금 — 거래소 {len(out.get('krx', {}))}종목(사진과 {rate:.1%} 같음), 야후 {len(out.get('yahoo', {}))}종목(사진과 {rate_y:.1%} 같음)")
    return 0


def main(now: dt.datetime | None = None) -> int:
    now = now or dt.datetime.now(KST)
    if lock_window(now) and not in_window(now):
        return lock(now)
    rc = snap(now)
    if rc == 0 and lock_window(now):
        return lock(now)
    return rc


def snap(now: dt.datetime) -> int:
    if not in_window(now):
        print(f"{now:%Y-%m-%d %H:%M} — 정규장 종가를 읽을 수 있는 창(보통 15:31~15:59, 수능일 16:31~16:59, 평일·휴장일 제외) 밖이라 찍지 않습니다.")
        return 0
    path = DIR / f"{now.date().isoformat()}.json"
    before = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    if before and len(before.get("close") or {}) >= FULL_MARKET:
        print(f"{path.name} 이미 있음(전 종목 {len(before['close'])}개) — 건너뜁니다.")
        return 0
    wanted = codes()
    everything = list(dict.fromkeys(wanted + all_codes()))
    # 코어·편입 후보를 먼저 따로 받는다 — 이것은 반드시 남아야 한다(실패하면 예외로 멈추고 다음 예약이 다시 찍는다).
    # 나머지 전 종목은 묶음이 실패해도 세고 넘어간다(2026-10-06: 전에는 한 묶음 실패로 코어 사진까지 사라졌다).
    quotes = fetch_kr._fetch_naver_item_quotes(wanted)
    failed: list[str] = []
    rest = [c for c in everything if c not in quotes]
    quotes = {**fetch_kr._fetch_naver_item_quotes(rest, failed=failed), **quotes}
    if failed:
        print(f"[경고] 전 종목 사진 중 {len(failed)}종목(묶음 {len(failed) // 20 + 1}개 안팎)을 받지 못했습니다 — 다음 예약이 다시 찍습니다")
    from src.stock_db import close_window
    if dt.datetime.now(KST).time() >= close_window(now.date())[1]:   # 받는 사이 창이 닫혔으면 시간외 값이 섞일 수 있다
        print("받는 사이 사진 창이 닫혀 버립니다.")
        return 1
    rows = {c: {k: quotes[c].get(k) for k in KEEP} for c in wanted if (quotes.get(c) or {}).get("nv")}
    close = {c: [q["nv"], q.get("sv") or q.get("pcv")] for c, q in quotes.items() if q.get("nv") and (q.get("sv") or q.get("pcv"))}
    if before and len(before.get("close") or {}) >= len(close):
        print(f"{path.name}: 앞 사진(전 종목 {len(before.get('close') or {})}개)이 이번({len(close)}개)보다 많아 그대로 둡니다.")
        return 0
    DIR.mkdir(parents=True, exist_ok=True)
    body = json.dumps({"at": dt.datetime.now(KST).isoformat(timespec="seconds"), "quotes": rows},
                      ensure_ascii=False, indent=0, sort_keys=True)
    body = body[:-1] + ',\n"close":' + json.dumps(close, separators=(",", ":"), sort_keys=True) + "\n}"
    path.write_text(body + "\n", encoding="utf-8")
    print(f"{path.name}: 코어·편입 후보 {len(rows)}/{len(wanted)}종목, 전 종목 {len(close)}/{len(everything)}종목 정규장 종가를 남겼습니다.")
    return 0 if rows else 1


if __name__ == "__main__":
    sys.exit(main())
