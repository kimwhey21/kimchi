"""언론사 RSS에서 최근 헤드라인을 모아 무료 시황 생성기에 전달합니다.

시장별로 세 매체를 조회하고, 한 매체의 장애가 전체 예약 작업을 멈추지 않도록
각 피드의 실패를 개별적으로 흡수합니다. 기사 본문을 읽은 것으로 간주하지 않으며,
자동 원고에는 출처·제목·링크만 참고 자료로 제공합니다.
"""
from __future__ import annotations

import datetime as dt

import feedparser
import requests

# 언론사별 RSS 주소. 값을 바꾸거나 항목을 추가/삭제하면 됩니다.
# (2026-08-31 기준 확인: 매일경제는 Cloudflare 봇 차단(Just a moment...)이 걸려 있어 제외)
FEEDS: dict[str, list[tuple[str, str]]] = {
    "kr": [
        # 한국경제는 경제 일반 피드가 시장과 무관한 생활·산업 기사까지 많이
        # 섞이므로, 공식 RSS 안내에 있는 증권 전용 피드를 사용합니다.
        ("한국경제", "https://www.hankyung.com/feed/finance"),
        ("연합뉴스", "https://www.yna.co.kr/rss/economy.xml"),
        ("이데일리", "http://rss.edaily.co.kr/stock_news.xml"),
    ],
    "us": [
        ("CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
        ("Yahoo Finance", "https://finance.yahoo.com/news/rssindex"),
        ("Investing.com", "https://www.investing.com/rss/news_25.rss"),
    ],
}

_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
_REQUEST_TIMEOUT = 10


def _parse_published(entry) -> dt.datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return dt.datetime(*parsed[:6], tzinfo=dt.timezone.utc)


def fetch_headlines(
    market: str, max_age_hours: int = 36, max_per_source: int = 8
) -> list[dict]:
    """market('us'/'kr')에 해당하는 언론사 RSS에서 최근 max_age_hours 이내
    헤드라인을 모아 [{"source", "title", "link", "published"}] 형태로 돌려줍니다.
    발행 시각이 없는 항목은 최근 것으로 간주해 포함합니다(피드마다 필드가
    달라서 아예 빼면 유용한 항목까지 놓칠 수 있음). 실패한 피드는 조용히
    건너뜁니다 — 언론사 서버가 잠깐 막혀도 전체 파이프라인이 멈추면 안 됩니다.
    """
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=max_age_hours)
    items: list[dict] = []

    for source, url in FEEDS.get(market, []):
        try:
            # feedparser.parse(url=...)는 내부적으로 urllib으로 직접 요청하는데
            # timeout 인자가 없어서, 응답이 느린 서버를 만나면 전체 파이프라인이
            # 무한정 멈출 수 있습니다. requests로 타임아웃을 걸고 받아온 응답
            # 바이트를 feedparser에 넘기는 방식으로 우회합니다.
            response = requests.get(
                url, headers={"User-Agent": _USER_AGENT}, timeout=_REQUEST_TIMEOUT
            )
            response.raise_for_status()
            parsed = feedparser.parse(response.content)
        except Exception as exc:  # noqa: BLE001 - 피드 하나 실패로 전체를 막지 않음
            print(f"[fetch_news] {source} 피드 파싱 실패, 건너뜁니다: {exc}")
            continue

        if parsed.bozo and not parsed.entries:
            print(f"[fetch_news] {source} 피드를 읽지 못했습니다, 건너뜁니다: {parsed.get('bozo_exception')}")
            continue

        count = 0
        for entry in parsed.entries:
            if count >= max_per_source:
                break
            title = entry.get("title", "").strip()
            if not title:
                continue
            published = _parse_published(entry)
            if published and published < cutoff:
                continue
            items.append(
                {
                    "source": source,
                    "title": title,
                    "link": entry.get("link", ""),
                    "published": published.isoformat() if published else None,
                }
            )
            count += 1

    items.sort(key=lambda i: i["published"] or "", reverse=True)
    return items


if __name__ == "__main__":
    import json
    import sys

    market = sys.argv[1] if len(sys.argv) > 1 else "kr"
    print(json.dumps(fetch_headlines(market), ensure_ascii=False, indent=2))
