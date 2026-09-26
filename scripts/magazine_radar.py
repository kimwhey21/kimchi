"""아침 레이더 — 매체들의 오늘 새 글 제목을 한 번에 본다 (2026-09-13, 2026-09-14에 묶음별로 확장).

    python -m scripts.magazine_radar                       # 잡지 묶음, 최근 36시간 제목을 갈래별로
    python -m scripts.magazine_radar --set ko              # 한국 매체 묶음 (한국어 가이드)
    python -m scripts.magazine_radar --set ko,magazine --hours 48   # 주말 Checkpoint
    python -m scripts.magazine_radar --media kr            # 시황 루틴이 조사할 매체 이름과 검색 주소 (피드를 읽지 않는다)
    python -m scripts.magazine_radar --set ko --raw        # 같은 기사 묶기를 끄고 받은 그대로
    python -m scripts.magazine_radar --hours 48 --json radar.json

왜 필요한가: 사용자가 물었다 — "피우스 블로그처럼 다양한 곳에서 자료를 가져오는 거 맞냐?" 첫 실행은 지시문의 주제 예시에서
골라 썼고, 그래서 피우스의 주 출처(WSJ·모틀리풀·야후·마켓워치·비주얼캐피털리스트)는 하나도 안 썼다. 피우스는 오늘 나온 기사에서
출발한다. 이 레이더가 그 출발점을 준다. **여기서 얻는 것은 주제다.** 글 하나를 옮기지 않고 출처 둘 이상을 종합해 쓴다.
매체 목록은 `config/magazine_feeds.yaml` 하나다 — 레이더가 읽는 묶음(`sets`)과 시황 루틴이 이름만 쓰는
목록(`market_media`)이 함께 있다. 시황에는 레이더를 붙이지 않는다: 주제가 이미 그날 장세로 정해져 있고
마감 직후의 급한 글이다.
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


def unescape(text: str) -> str:
    """이스케이프가 두 번 걸린 제목이 있다(`&amp;quot;` → `&quot;` → `"`). 더 안 바뀔 때까지 푼다.
    2026-09-14 실측: 연합인포맥스 제목이 화면에 `&quot;채권자 협의&quot;`로 그대로 찍혔다."""
    for _ in range(3):
        once = html.unescape(text)
        if once == text:
            break
        text = once
    return text


def _text(block: str, tag: str) -> str:
    m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", block, re.S)
    if not m:
        return ""
    return unescape(re.sub(r"<!\[CDATA\[|\]\]>", "", m.group(1))).strip()


def _link(block: str) -> str:
    m = re.search(r'<link[^>]*href="([^"]+)"', block) or re.search(r"<link[^>]*>(.*?)</link>", block, re.S)
    return unescape(re.sub(r"<!\[CDATA\[|\]\]>", "", m.group(1))).strip() if m else ""


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


def body(response) -> str:
    """서버가 charset을 안 알려 주면 requests가 ISO-8859-1로 읽어 제목이 깨진다(한겨레·더벨 실측).
    깨진 제목은 예외를 내지 않고 그냥 글자 쓰레기로 나오므로 — 조용한 실패다 — 여기서 다시 읽는다."""
    declared = (getattr(response, "encoding", None) or "").lower()
    apparent = getattr(response, "apparent_encoding", None)
    if declared == "iso-8859-1" and apparent:
        return response.content.decode(apparent, "replace")
    return response.text


def fetch(feed: dict) -> list[dict]:
    r = requests.get(feed["url"], headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    rows = parse(body(r))
    for row in rows:
        row["source"] = feed["name"]; row["column"] = feed.get("column", ""); row["paid"] = bool(feed.get("paid"))
        row["fold_tape"] = bool(feed.get("fold_tape"))
        # 구글뉴스 피드는 **한 피드가 여러 매체**다 — 같은 기사가 여덟 줄로 들어온다(KEPCO 실측).
        row["aggregator"] = "news.google.com" in feed["url"]
    return rows


def config() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def feeds_for(names: str) -> list[dict]:
    """`--set`의 이름들(`magazine`, `ko`, `en_kr`, `ko,magazine`, `all`)을 피드 목록 하나로 편다.

    "지수 시세를 접을 묶음인가"를 **피드마다** 달아 준다. 묶음을 섞어 부를 수 있으므로(Checkpoint는
    `ko,magazine`) 접기를 전체에 켜고 끄면 한쪽이 틀린다 — 한국 기사는 접고 잡지 기사는 남겨야 한다.
    """
    conf = config()
    sets = conf["sets"]
    folding = set(conf.get("fold_index_tape") or [])
    wanted = list(sets) if names.strip() == "all" else [n.strip() for n in names.split(",") if n.strip()]
    unknown = [n for n in wanted if n not in sets]
    if unknown:  # 이름을 잘못 적으면 "오늘 화제가 없다"가 아니라 여기서 멈춘다
        raise SystemExit(f"모르는 묶음: {', '.join(unknown)} (있는 것: {', '.join(sets)})")
    return [{**feed, "fold_tape": name in folding} for name in wanted for feed in sets[name]]


def radar(hours: int, feeds: list[dict] | None = None) -> tuple[list[dict], list[str]]:
    feeds = feeds if feeds is not None else feeds_for("magazine")
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


# 제목 앞의 꼬리표만 보고 버리는 것 — 기사가 아니라 게시물이다. 버린 수는 반드시 센다.
NOISE_TAGS = {"부고", "인사", "포토", "표", "사진", "알림", "공고", "부고·인사", "인사·부고", "신간"}
_TAG = re.compile(r"^\[([^\]]{1,20})\]\s*")
_TAIL = re.compile(r"\s+[-–]\s+[^-–]{1,40}$")          # 구글뉴스가 붙이는 " - 매체" 꼬리
_DROP = re.compile(r"[0-9.,%↑↓▲▼·…\"'“”‘’()\[\]〈〉<>·:;!?~/]+")


# 지수 시세 보도 — 오늘 코스피가 몇 % 움직였다는 기사. 매체 열 곳이 개장·마감마다 쓴다.
# 주제를 고르는 화면에서는 접는다: **그 이야기는 이미 우리 시황 글이 쓴다.** 접은 수는 찍는다.
_INDEX = ("코스피", "코스닥", "지수")
_MOVE = ("마감", "출발", "급락", "급등", "하락", "상승", "약세", "강세", "반등", "후퇴",
         "내린", "오른", "출렁", "반납", "회복", "포인트", "장중")
# 영어 한국 시장 기사에도 같은 것이 있다(2026-09-14 실측: `Korean stocks sink…`, `KOSPI falls below 6,700`,
# `[Closing Market] KOSPI Slides 3.26%`). 낱말은 여기서 늘리되 **어느 묶음에서 접을지는 설정이 정한다**
# (`fold_index_tape`) — 잡지 묶음에서는 접으면 안 된다.
_INDEX_EN = re.compile(r"\b(kospi|kosdaq|korean stocks?|korea stocks?|seoul (stocks?|shares)|"
                       r"south korean (stocks?|shares))\b", re.I)
_MOVE_EN = re.compile(r"\b(sinks?|slid|slides?|plunges?|drops?|falls?|slips?|tumbles?|rallies|rally|"
                      r"rebounds?|climbs?|gains?|rises?|jumps?|soars?|closes?|closed|opens?|opened|"
                      r"ends?|ended|higher|lower|leads? asia)\b", re.I)


def is_tape(title: str) -> bool:
    """지수 시세 보도인가 — "오늘 지수가 몇 % 움직였다". 한국어·영어 둘 다 본다.

    접는 자리는 **묶음이 정한다**(`fold_index_tape`). 잡지 묶음에서는 접지 않는다 —
    「시장 읽기」 코너가 바로 그 기사(S&P 500이 왜 빠졌나)로 글을 쓰기 때문이다.
    """
    if any(w in title for w in _INDEX) and any(w in title for w in _MOVE) and re.search(r"\d", title):
        return True
    return bool(_INDEX_EN.search(title) and _MOVE_EN.search(title))


def is_noise(title: str) -> bool:
    tag = _TAG.match(title)
    return bool(tag) and tag.group(1).strip() in NOISE_TAGS


def _shingles(title: str) -> frozenset[str]:
    """제목을 **글자 두 쌍** 자루로 만든다.

    낱말로 세면 한국어가 안 맞는다 — `전 사학연금`과 `前사학연금`, `기금이사에`와 `투자사령탑에`가
    다른 낱말이라 같은 인사 기사 셋이 따로 남았다(2026-09-14 실측). 글자 두 쌍은 조사·접두사가
    달라도 겹친다.
    """
    bare = re.sub(r"[^0-9A-Za-z가-힣]+", "", _TAIL.sub("", _TAG.sub("", title)))
    pairs = frozenset(bare[i:i + 2] for i in range(len(bare) - 1))
    return pairs or frozenset({bare})


AGGREGATOR_OVERLAP = 0.30


def group(rows: list[dict], overlap: float = 0.40) -> tuple[list[dict], dict[str, int]]:
    """주제를 고를 수 있는 화면으로 줄인다. 돌려주는 것은 (남은 줄, 센 것).

    왜 필요한가(2026-09-14): 한국 매체를 열두 곳까지 넣으니 증시 갈래가 14시간에 96줄이 됐는데
    그 대부분이 **같은 이야기**였다 — 개장·마감마다 매체 열 곳이 쓰는 지수 시세 보도. 주제를
    고르는 화면에서 그것은 잡음이다(그 이야기는 우리 시황 글이 이미 쓴다). 셋을 한다.
      tape   지수 시세 보도는 접는다 — 갈래마다 몇 건을 접었는지 찍는다
      merged 같은 기사를 글자 두 쌍으로 묶어 `+N곳`으로 — 열 곳이 함께 쓴 기사는 그 주의 화제다
      noise  [부고]·[인사]·[포토]처럼 기사가 아닌 게시물은 뺀다
    센 수를 전부 찍는 것이 규칙이다. 접은 것을 보려면 `--raw`.
    """
    kept, counts = [], {"tape": 0, "noise": 0, "merged": 0}
    for row in rows:
        if is_noise(row["title"]):
            counts["noise"] += 1
            continue
        if row.get("fold_tape") and is_tape(row["title"]):
            counts["tape"] += 1
            continue
        keys = _shingles(row["title"])
        for head in kept:
            other = head["_keys"]
            # 같은 피드의 닮은 제목은 대개 같은 기사가 아니라 **같은 틀의 다른 공시**다
            # (`링크솔루션 300억 전환사채` / `HLB글로벌 50억 전환사채`). 묶으면 `+N곳`이 거짓말이 된다.
            # 예외는 구글뉴스처럼 **한 피드가 여러 매체인** 경우다 — 거기서는 같은 피드 안의 닮은
            # 제목이 곧 여러 매체가 같은 기사를 쓴 것이다(2026-09-14 실측: KEPCO 거절 기사 여덟 줄이
            # 한 피드에서 왔다). 그런 피드끼리는 문턱도 낮춘다 — 질의가 이미 좁아 주제가 한 가지라
            # 0.30만 겹쳐도 같은 기사였다(그날 0.28~0.55 쌍 스물여덟 개가 전부 진짜 중복이었다).
            both_feed_is_many_outlets = head.get("aggregator") and row.get("aggregator")
            if head["source"] == row["source"] and not both_feed_is_many_outlets:
                continue
            limit = AGGREGATOR_OVERLAP if both_feed_is_many_outlets else overlap
            if len(keys & other) / len(keys | other) >= limit:
                head["also"].append(row["source"])
                break
        else:
            kept.append({**row, "_keys": keys, "also": []})
    counts["merged"] = sum(len(k["also"]) for k in kept)
    for head in kept:
        head.pop("_keys")
    return kept, counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--set", dest="feed_set", default="magazine", help="피드 묶음: magazine·ko·all, 쉼표로 여럿")
    ap.add_argument("--media", choices=("kr", "us"), help="시황 루틴이 조사할 매체 이름과 검색 주소만 찍고 끝낸다(피드를 읽지 않음)")
    ap.add_argument("--hours", type=int, default=36)
    ap.add_argument("--raw", action="store_true", help="묶지 않고 받은 그대로 (묶음이 의심스러울 때)")
    ap.add_argument("--json", type=Path)
    a = ap.parse_args(argv)
    if a.media:
        # 받는 길은 매체마다 적혀 있다(2026-09-26) — 검색이 막힌 곳은 precheck ⑩의 헤드라인으로 본다.
        media = config()["market_media"][a.media]
        print(f"{a.media} 시황 조사 매체 {len(media)}곳 — 이 가운데 3곳 이상:")
        print("  " + " · ".join(m["name"] + ("" if m.get("search", True) else "(헤드라인 피드)") for m in media))
        print("  allowed_domains: " + " · ".join(m["domain"] for m in media if m.get("search", True)))
        return 0
    raw, failed = radar(a.hours, feeds_for(a.feed_set))
    rows, counts = (raw, {"tape": 0, "noise": 0, "merged": 0}) if a.raw else group(raw)
    by_col: dict[str, list[dict]] = {}
    for r in rows:
        by_col.setdefault(r["column"] or "(기타)", []).append(r)
    print(f"아침 레이더({a.feed_set}) — 최근 {a.hours}시간 · 기사 {len(rows)}건 · "
          f"지수 시세 보도 {counts['tape']}건 접음 · 같은 기사 {counts['merged']}줄 묶음 · "
          f"게시물 {counts['noise']}건 제외 · 받은 것 {len(raw)}건 · 피드 실패 {len(failed)}개")
    if counts["tape"]:
        print("  (접은 것은 오늘 지수가 몇 % 움직였다는 기사입니다 — 그 이야기는 시황 글이 씁니다. 보려면 --raw)")
    for col, items in by_col.items():
        print(f"\n## {col} ({len(items)})")
        for r in items:
            when = r["at"].astimezone(dt.timezone(dt.timedelta(hours=9))).strftime("%m/%d %H:%M") if r["at"] else "     --    "
            paid = " [유료·제목만]" if r["paid"] else ""
            same = f" +{len(r['also'])}곳" if r.get("also") else ""
            print(f"  {when}  {r['source']}{paid}{same}: {r['title'][:90]}")
    if failed:
        print("\n못 읽은 피드:", ", ".join(failed))
    if a.json:
        a.json.write_text(json.dumps([{**r, "at": r["at"].isoformat() if r["at"] else None} for r in rows], ensure_ascii=False, indent=1), encoding="utf-8")
        print("저장:", a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
