"""잡지 루틴의 아침 레이더 — 참고 블로그가 가져오는 매체들의 오늘 새 글 제목을 한 번에 본다 (2026-09-13).

    python -m scripts.magazine_radar              # 최근 36시간 제목을 코너별로
    python -m scripts.magazine_radar --hours 48 --json radar.json

왜 필요한가: 사용자가 물었다 — "피우스 블로그처럼 다양한 곳에서 자료를 가져오는 거 맞냐?" 첫 실행은 지시문의 주제 예시에서
골라 썼고, 그래서 피우스의 주 출처(WSJ·모틀리풀·야후·마켓워치·비주얼캐피털리스트)는 하나도 안 썼다. 피우스는 오늘 나온 기사에서
출발한다. 이 레이더가 그 출발점을 준다. **여기서 얻는 것은 주제다.** 글 하나를 옮기지 않고 출처 둘 이상을 종합해 쓴다.
피드 목록은 `config/magazine_feeds.yaml`.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "magazine_feeds.yaml"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/128.0 Safari/537.36"}
TIMEOUT = 15


def _text(block: str, tag: str) -> str:
    m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", block, re.S)
    if not m:
        return ""
    return html.unescape(re.sub(r"<!\[CDATA\[|\]\]>", "", m.group(1))).strip()


def _link(block: str) -> str:
    m = re.search(r'<link[^>]*href="([^"]+)"', block) or re.search(r"<link[^>]*>(.*?)</link>", block, re.S)
    return html.unescape(re.sub(r"<!\[CDATA\[|\]\]>", "", m.group(1))).strip() if m else ""


def _when(block: str) -> dt.datetime | None:
    for tag in ("pubDate", "published", "updated", "dc:date"):
        raw = _text(block, tag)
        if not raw:
            continue
        try:
            return parsedate_to_datetime(raw).astimezone(dt.timezone.utc)
        except Exception:
            try:
                return dt.datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(dt.timezone.utc)
            except Exception:
                continue
    return None


def parse(xml: str) -> list[dict]:
    """RSS(item)와 Atom(entry) 둘 다 — 제목·링크·시각. 시각을 못 읽은 항목은 버리지 않고 None으로 둔다."""
    items = re.findall(r"<item[\s>].*?</item>|<entry[\s>].*?</entry>", xml, re.S)
    out = []
    for block in items:
        title = _text(block, "title")
        if not title:
            continue
        out.append({"title": title, "link": _link(block), "at": _when(block)})
    return out


def fetch(feed: dict) -> list[dict]:
    r = requests.get(feed["url"], headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    rows = parse(r.text)
    for row in rows:
        row["source"] = feed["name"]; row["column"] = feed.get("column", ""); row["paid"] = bool(feed.get("paid"))
    return rows


def radar(hours: int, feeds: list[dict] | None = None) -> tuple[list[dict], list[str]]:
    feeds = feeds if feeds is not None else yaml.safe_load(CONFIG.read_text(encoding="utf-8"))["feeds"]
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)
    rows, failed = [], []
    for feed in feeds:
        try:
            got = fetch(feed)
        except Exception as error:  # noqa: BLE001 — 세어서 보고한다(조용한 실패 금지)
            failed.append(f"{feed['name']}: {type(error).__name__}")
            continue
        fresh = [g for g in got if g["at"] is None or g["at"] >= since]
        rows.extend(fresh[:12])
    rows.sort(key=lambda g: (g["column"], g["at"] or since), reverse=False)
    return rows, failed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--hours", type=int, default=36)
    ap.add_argument("--json", type=Path)
    a = ap.parse_args(argv)
    rows, failed = radar(a.hours)
    by_col: dict[str, list[dict]] = {}
    for r in rows:
        by_col.setdefault(r["column"] or "(기타)", []).append(r)
    print(f"아침 레이더 — 최근 {a.hours}시간, {len(rows)}건, 피드 실패 {len(failed)}개")
    for col, items in by_col.items():
        print(f"\n## {col} ({len(items)})")
        for r in items:
            when = r["at"].astimezone(dt.timezone(dt.timedelta(hours=9))).strftime("%m/%d %H:%M") if r["at"] else "     --    "
            paid = " [유료·제목만]" if r["paid"] else ""
            print(f"  {when}  {r['source']}{paid}: {r['title'][:90]}")
    if failed:
        print("\n못 읽은 피드:", ", ".join(failed))
    if a.json:
        a.json.write_text(json.dumps([{**r, "at": r["at"].isoformat() if r["at"] else None} for r in rows], ensure_ascii=False, indent=1), encoding="utf-8")
        print("저장:", a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
