"""검색 도구에 막힌 시황 매체의 헤드라인 (2026-09-26).

    python -m scripts.media_headlines kr          # 연합뉴스·매일경제
    python -m scripts.media_headlines us          # Reuters·Barron's·WSJ
    python -m scripts.media_headlines us --hours 30

왜 (2026-09-26): 루틴의 검색 도구(WebSearch)는 매체 조건(`allowed_domains`)에 Anthropic 로봇을 막은 매체가
하나라도 섞이면 검색 전체를 400으로 거절한다. 시황 매체 14곳 가운데 다섯 곳(Reuters·WSJ·Barron's·연합뉴스·
매일경제)이 그랬고, 9/26 미국장 루틴이 이 오류로 두 번 헛돌았다. 다섯 곳 모두 믿을 만한 매체라 버리지 않고
**매체가 공개로 내놓은 RSS**(없으면 구글뉴스 `site:` 검색 RSS)로 제목·시각·요약을 받는다.

- 받는 길은 `config/magazine_feeds.yaml`의 `market_media` 하나에 적혀 있다(`search: false` + `feeds`).
  검색 도구에 넣을 매체(`search_domains`)도 같은 목록에서 나온다 — 막힌 매체가 다시 섞일 수 없다.
- 루틴은 따로 부르지 않는다. `scripts/routine_precheck.py`가 ⑩으로 붙인다(턴을 늘리지 않는다).
- **본문은 열지 않는다.** 매체가 AI 접근을 막은 것이므로 로봇 이름도 감추지 않는다(`UA`). 제목은 단서이고,
  사실 확인은 검색되는 매체에서 한다.
- 이것은 아침 레이더가 아니다. 레이더는 주제를 고르는 도구이고 시황에는 붙이지 않는다(주제는 그날 장세).
  여기서는 그날 장세를 설명할 기사 제목만 매체당 몇 줄 본다.

줄이는 방식: 최근 N시간(`HOURS`) → 제목이 거의 같은 것은 한 줄(다른 매체면 `+매체`) → 우리 종목 이름이나
시장 낱말이 든 제목을 앞으로(그런 제목이 `MIN_ON_TOPIC`줄 이상이면 나머지는 뺀다) → 매체당 `PER_OUTLET`줄. 피드가 실패하면 그 자리에 `⚠`로 세고, 전부 실패하면
예외로 올린다(precheck가 `확인 실패`로 센다 — 조용한 실패 금지).
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys

import requests

from scripts import magazine_radar as mr

UA = {"User-Agent": "FermataMarketBrief/1.0 (+https://fermata.it.kr; headline feed reader)"}
HOURS = {"kr": 18, "us": 24}          # kr 16:20 실행 → 전날 22시부터, us 07:20 실행 → 미국 장 전체
PER_OUTLET = {"kr": 8, "us": 6}
TITLE_CLIP = 80
SUMMARY_CLIP = 70
MIN_ON_TOPIC = 3
SAME_STORY = 0.45
KST = dt.timezone(dt.timedelta(hours=9))

MARKET_WORDS = {
    "kr": re.compile(r"코스피|코스닥|증시|주가|주식|외국인|기관|개인|순매수|순매도|환율|원·달러|원/달러|반도체|"
                     r"급등|급락|상승|하락|강세|약세|마감|금리|수급|시가총액|공매도|ETF|실적|상장"),
    "us": re.compile(r"\b(stocks?|shares|Wall Street|S&P|Nasdaq|Dow|Treasur(y|ies)|yields?|Fed|oil|dollar|"
                     r"earnings|guidance|rall(y|ies|ied)|sell-?off|gains?|falls?|fell|rises?|rose|slides?|"
                     r"jumps?|tumbles?|surges?|downgrade[sd]?|upgrade[sd]?|record)\b", re.I),
}
_YONHAP_BYLINE = re.compile(r"^\([^)]{0,20}=[^)]{0,10}\)\s*(\S+\s+){0,2}(기자|특파원)\s*=\s*")
_TAGS = re.compile(r"<[^>]+>")


def outlets(market: str) -> list[dict]:
    """`market_media.<market>`를 한 모양으로 편다: name·domain·search(기본 True)·feeds(기본 [])."""
    rows = mr.config()["market_media"][market]
    out = []
    for row in rows:
        if not row.get("name") or not row.get("domain"):
            raise ValueError(f"market_media.{market}에 name·domain이 빠진 항목: {row!r}")
        search = row.get("search", True)
        feeds = list(row.get("feeds") or [])
        if not search and not feeds:  # 막혔는데 받는 길도 없으면 그 매체는 아무 데서도 안 보인다
            raise ValueError(f"market_media.{market}.{row['name']}: search: false인데 feeds가 없습니다")
        out.append({"name": row["name"], "domain": row["domain"], "search": bool(search), "feeds": feeds})
    return out


def search_domains(market: str) -> list[str]:
    """검색 도구의 `allowed_domains`에 넣어도 되는 주소 — 막힌 매체는 빠진다."""
    return [o["domain"] for o in outlets(market) if o["search"]]


def feed_outlets(market: str) -> list[dict]:
    return [o for o in outlets(market) if not o["search"]]


def parse(xml: str) -> list[dict]:
    """RSS item → 제목·링크·시각·요약. 제목·링크·시각 읽기는 레이더(`magazine_radar`)의 것을 그대로 쓴다."""
    out = []
    for block in re.findall(r"<item[\s>].*?</item>", xml, re.S):
        title = mr._TAIL.sub("", mr._text(block, "title"))   # 구글뉴스의 " - Reuters" 꼬리
        if not title:
            continue
        summary = _YONHAP_BYLINE.sub("", " ".join(mr.unescape(_TAGS.sub(" ", mr._text(block, "description"))).split()))
        out.append({"title": title, "link": mr._link(block), "at": mr._when(block), "summary": summary})
    return out


def fetch(url: str) -> list[dict]:
    r = requests.get(url, headers=UA, timeout=mr.TIMEOUT)
    r.raise_for_status()
    return parse(mr.body(r))


def _overlap(a: frozenset[str], b: frozenset[str]) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def _useful_summary(title: str, summary: str) -> str:
    """구글뉴스 요약은 제목 + 매체 이름뿐이다 — 제목과 거의 같으면 버린다."""
    if not summary or _overlap(mr._shingles(title), mr._shingles(summary)) >= 0.5:
        return ""
    return summary


def collect(market: str, *, now: dt.datetime | None = None, names: list[str] | tuple[str, ...] = (),
            hours: int | None = None) -> tuple[list[dict], list[str], dict[str, int]]:
    """(남은 줄, 실패한 피드, 매체별 받은 수). 남은 줄은 매체 순서 → 관련도 → 최신 순."""
    now = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    since = now - dt.timedelta(hours=hours or HOURS[market])
    words = MARKET_WORDS[market]
    wanted = [n for n in names if n and len(n) >= 2]
    kept: list[dict] = []
    failed: list[str] = []
    received: dict[str, int] = {}
    for outlet in feed_outlets(market):
        rows: list[dict] = []
        for url in outlet["feeds"]:
            try:
                got = fetch(url)
            except Exception as error:  # noqa: BLE001 — 세어서 찍는다(조용한 실패 금지)
                failed.append(f"{outlet['name']}: {type(error).__name__}")
                continue
            received[outlet["name"]] = received.get(outlet["name"], 0) + len(got)
            rows += [g for g in got if g["at"] is not None and since <= g["at"] <= now + dt.timedelta(minutes=5)]
        mine: list[dict] = []
        for row in sorted(rows, key=lambda r: r["at"], reverse=True):
            if mr.is_noise(row["title"]):          # [표]·[포토]·[인사] 같은 게시물
                continue
            keys = mr._shingles(row["title"])
            same = next((k for k in kept + mine if _overlap(keys, k["_keys"]) >= SAME_STORY), None)
            if same is not None:
                if same["source"] != outlet["name"] and outlet["name"] not in same["also"]:
                    same["also"].append(outlet["name"])
                continue
            hit = any(n in row["title"] for n in wanted)
            score = 2 if hit else 1 if words.search(row["title"]) else 0
            mine.append({**row, "source": outlet["name"], "_keys": keys, "also": [], "score": score})
        mine.sort(key=lambda r: (r["score"], r["at"]), reverse=True)
        on_topic = [r for r in mine if r["score"]]
        if len(on_topic) >= MIN_ON_TOPIC:   # 시장 제목이 넉넉하면 부동산·게임 같은 딴 기사는 뺀다
            mine = on_topic
        kept += mine[: PER_OUTLET[market]]
    return kept, failed, received


def render(market: str, *, now: dt.datetime | None = None, names: list[str] | tuple[str, ...] = (),
           hours: int | None = None) -> str:
    feeders = feed_outlets(market)
    rows, failed, received = collect(market, now=now, names=names, hours=hours)
    total_feeds = sum(len(o["feeds"]) for o in feeders)
    if failed and len(failed) >= total_feeds:
        raise RuntimeError("헤드라인 피드를 하나도 받지 못했습니다: " + " | ".join(failed))
    lines = [
        "검색 도구 `allowed_domains`에는 이것만: " + " · ".join(search_domains(market))
        + " (막힌 매체가 하나라도 섞이면 검색 전체가 400)",
        f"막힌 매체 {len(feeders)}곳({' · '.join(o['name'] for o in feeders)})은 아래 제목으로 봅니다 — 본문은 열지 않고, "
        "사실은 검색되는 매체에서 확인합니다. 숫자는 시세 파일에서만.",
    ]
    if failed:
        lines.append(f"⚠ {len(failed)}건을 받지 못했습니다: " + " | ".join(failed) + " — 그 매체는 오늘 제목이 없습니다")
    for outlet in feeders:
        mine = [r for r in rows if r["source"] == outlet["name"]]
        lines.append(f"[{outlet['name']}] {len(mine)}줄 (받은 것 {received.get(outlet['name'], 0)}건 · "
                     f"최근 {hours or HOURS[market]}시간)")
        for r in mine:
            when = r["at"].astimezone(KST).strftime("%m/%d %H:%M")
            also = f" +{'·'.join(r['also'])}" if r["also"] else ""
            summary = _useful_summary(r["title"], r["summary"])
            tail = f" — {mr._TAG.sub('', summary)[:SUMMARY_CLIP]}" if summary else ""
            lines.append(f"  {when}{also}  {r['title'][:TITLE_CLIP]}{tail}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("market", choices=("kr", "us"))
    ap.add_argument("--hours", type=int, default=None)
    a = ap.parse_args(argv)
    print(render(a.market, hours=a.hours))
    return 0


if __name__ == "__main__":
    sys.exit(main())
