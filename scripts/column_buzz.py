"""칼럼 소재 후보 — 우리가 보는 종목을 국내 매체가 지난 하루 몇 건이나 다뤘나 (2026-10-16).

    python -m scripts.column_buzz                 # 오늘(KST) 한국장·어젯밤 미국장 시세 파일의 종목으로
    python -m scripts.column_buzz --day 2026-10-16

왜: 칼럼은 소재를 등락 폭·거래대금으로 골랐다. 그러면 "모두가 말하는데 주가는 아직 안 움직인 소식"이 보이지 않는다 —
2026-10-16 테슬라 로드스터 공개는 미국 장이 끝난 뒤 저녁에 있었고(전날 종가 -1.29%), 구글 뉴스 한국판 하루치 '테슬라' 기사
100건 가운데 98건이 그 이야기였는데 그날 칼럼은 그것을 몰랐다. 이 도구는 종목마다 구글 뉴스 한국판 검색 RSS(지난 1일)의
기사 수와 제목 세 줄을 보여 준다. 숫자는 여전히 시세 파일에서만 쓴다 — 기사 수는 '무엇을 쓸까'의 근거일 뿐이다.
받지 못한 종목은 세어서 찍고, 셋 중 하나 넘게 못 받으면 예외로 멈춘다(조용히 '화제 없음'으로 보이지 않게).
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parent.parent
KST = dt.timezone(dt.timedelta(hours=9))
RSS = "https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"
UA = {"User-Agent": "Mozilla/5.0 (fermata column buzz)"}
# 이야기를 묶을 때 세지 않는 낱말 — 어느 기사에나 붙는 꼬리표·시세 낱말
STOP = {"주가", "오늘", "속보", "단독", "종합", "뉴스", "기자", "투자", "시장", "종목", "상승", "하락", "급등", "급락", "전망", "분석",
        "증시", "주식", "코스피", "코스닥", "뉴욕", "미국", "한국", "국내", "올해", "내년", "영상", "포토", "사진", "인사", "부고",
        "the", "and", "for", "with", "news", "stock", "shares"}
SKIP = {"코스피", "코스닥", "원/달러 환율", "다우존스", "S&P500", "나스닥종합", "러셀2000", "VIX", "WTI 원유", "금",
        "미국 10년물 국채금리", "미국 30년물 국채금리", "달러인덱스"}


def candidates(day: str, root: Path = ROOT) -> list[dict]:
    """그날 한국장 + 그 전 가장 최근 미국장 시세 파일의 종목(지수·환율·금리·원자재는 뺀다)."""
    out: list[dict] = []
    kr = root / "data" / f"price_kr_{day}.json"
    us = sorted(q for q in (root / "data").glob("price_us_*.json") if q.stem < f"price_us_{day}")
    for market, path in (("한국", kr if kr.exists() else None), ("미국", us[-1] if us else None)):
        if path is None:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for e in (data.get("watchlist") or {}).values():
            name = str(e.get("name") or "")
            if name and name not in SKIP and not any(c["name"] == name for c in out):
                out.append({"name": name, "market": market, "pct": e.get("change_pct"), "file": path.stem})
    if not out:
        raise SystemExit(f"{day}: 대조할 시세 파일이 없습니다 — 칼럼을 쓰지 않는 날입니다")
    return out


_PARTICLE = re.compile(r"(을|를|이|가|은|는|의|에|도|로|과|와|만|서)$")


def _words(text: str) -> set[str]:
    """제목의 낱말 — 끝의 조사를 뗀다('하늘을'·'하늘'은 같은 낱말)."""
    out = set()
    for w in re.findall(r"[가-힣A-Za-z0-9]{2,}", text):
        stem = _PARTICLE.sub("", w) if len(w) > 2 and re.match(r"[가-힣]", w) else w
        out.add(stem)
    return out


def story(name: str, titles: list[str]) -> tuple[str, int, list[str]]:
    """제목들이 한 이야기에 얼마나 몰렸나 — (가장 많이 겹친 낱말, 그 낱말이 든 제목 수, 그 제목 세 줄).
    큰 회사는 하루 기사가 늘 상한(100건)을 채우므로 기사 수로는 가릴 수 없다. 한 사건에 몰린 날만 이 수가 크다."""
    own = _words(name)
    words_of = {title: _words(title) for title in titles}
    df: dict[str, int] = {}
    for title in titles:
        for w in words_of[title]:
            if w not in own and w.lower() not in STOP and not w.isdigit() and not any(w.startswith(o) or o.startswith(w) for o in own):
                df[w] = df.get(w, 0) + 1
    if not df:
        return "", 0, []
    word = max(df, key=lambda w: (df[w], len(w)))
    # 같은 사건을 매체마다 다른 말로 쓴다(로드스터·하늘·날았다·공중회전) — 가장 큰 묶음 안에서 셋 중 하나 넘게 함께 나오는 낱말이 든
    # 제목까지 한 번 넓혀 묶는다(2026-10-16 테슬라: '하늘' 41건 → 넓히면 그 사건 기사 대부분)
    core = [t for t in titles if word in words_of[t]]
    inner: dict[str, int] = {}
    for title in core:
        for w in words_of[title]:
            if w != word and w in df:
                inner[w] = inner.get(w, 0) + 1
    near = {w for w, n in inner.items() if n * 3 > len(core)}
    cluster = [t for t in titles if word in words_of[t] or words_of[t] & near]
    return word, len(cluster), cluster[:3]


def count(name: str, get=requests.get) -> tuple[int, list[str]]:
    r = get(RSS.format(q=quote(f'"{name}" when:1d')), headers=UA, timeout=30)
    r.raise_for_status()
    items = re.findall(r"<item>(.*?)</item>", r.text, re.S)
    titles = [html.unescape(re.sub(r"\s+-\s+[^-]+$", "", m.group(1))) for i in items if (m := re.search(r"<title>(.*?)</title>", i, re.S))]
    return len(items), titles


def rank(day: str, get=requests.get, pause: float = 0.4) -> list[dict]:
    rows, failed = [], []
    cands = candidates(day)
    for c in cands:
        try:
            n, titles = count(c["name"], get)
        except requests.RequestException as e:
            failed.append(f"{c['name']}({type(e).__name__})")
            continue
        word, size, sample = story(c["name"], titles)
        rows.append({**c, "articles": n, "word": word, "story": size, "titles": sample or titles[:3]})
        time.sleep(pause)
    if len(failed) * 3 > len(cands):
        raise SystemExit(f"기사 수를 {len(failed)}/{len(cands)}종목 받지 못했습니다: {', '.join(failed[:8])}")
    if failed:
        print(f"⚠ 기사 수를 받지 못한 종목 {len(failed)}개: {', '.join(failed)}")
    return sorted(rows, key=lambda r: (-r["story"], -r["articles"]))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--day", default=dt.datetime.now(KST).date().isoformat())
    ap.add_argument("--top", type=int, default=10)
    a = ap.parse_args(argv)
    rows = rank(a.day)
    print(f"== {a.day} 국내 매체가 한 이야기에 몰린 종목(구글 뉴스 한국판 지난 하루, 종목당 100건이 상한) ==")
    for r in rows[: a.top]:
        pct = f"{r['pct']:+.2f}%" if isinstance(r.get("pct"), (int, float)) else "?"
        print(f"{r['story']:>4}건 '{r['word']}'  {r['name']} — 기사 {r['articles']}건 ({r['market']}, {r['file'][6:]} {pct})")
        for t in r["titles"]:
            print(f"        · {t[:80]}")
    print("기사 수는 소재를 고르는 근거일 뿐입니다 — 숫자는 시세 파일에서만, 사실은 출처를 열어 확인합니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
