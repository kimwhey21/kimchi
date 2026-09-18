"""독자가 보는 한 줄 — 한국어 글 제목을 **올라가는 순서**로 뽑는다 (2026-09-18).

왜 필요한가
-----------
2026-09-18 아침, 사장님: "제목 상태 왜 이래 적용안된거같은데". 관문은 제목 규칙을 다 돌렸고 통과했다 —
그런데 **목록별로** 돌렸다(한국장 다섯 편·미국장 다섯 편·프리뷰 다섯 편 따로). 독자는 그렇게 안 본다.
네이버 피드 위에서 아래로:

    09-18 08:00 미국장  반도체는 일제히 웃었는데, 은행주는 왜 못 웃었을까요
    09-17 21:51 프리뷰  오늘 밤 필라델피아 지수가 은행주 사흘째를 정합니다
    09-17 17:12 한국장  3년 2개월 만의 금리 인상, 코스피는 오히려 잠잠했습니다
    09-17 08:00 미국장  다우 1.21% 하락, 이유는 금리 인상에 흔들린 은행주입니다
    09-16 21:52 프리뷰  오늘 밤 FOMC가 3년 2개월 만의 금리 인상을 결정합니다

'은행주' 셋, '금리 인상' 셋, '3년 2개월 만의 금리 인상' 둘, 대비 꼴 둘 — 목록별로는 전부 "다섯 편에
한 번"을 지켰다. 그래서 관문(editorial_gate·feature_gate·publish_editorial)과 `scripts/recent_titles`가
대조하는 '최근 글'은 이제 이 한 줄이다. 순서는 파일 이름이 아니라 **올라가는 시각**이다 — 미국장
거래일 D의 글은 한국 D+1 아침 07:20에 나가므로 프리뷰 D(21:30)·한국장 D(16:20)보다 뒤에 온다.

가이드는 뺀다 — 제목이 검색 질문이고 자기 목록(같은 시리즈) 규칙을 따로 본다. 잡지는 다른 블로그다.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 갈래 → (editorial 아래 폴더, 올라가는 시각 KST). 시황은 폴더가 같고 시장으로 갈린다.
SLOTS: dict[str, tuple[str, tuple[int, int]]] = {
    "한국장": ("", (16, 20)),        # editorial/kr_<거래일>.json — 그날 16:20
    "미국장": ("", (7, 20)),         # editorial/us_<거래일>.json — 한국 다음 날 07:20
    "프리뷰": ("previews", (21, 30)),
    "기준표": ("features", (9, 0)),
    "주간 결산": ("weekly", (10, 0)),
    "다음 주 일정": ("weekly", (20, 0)),
    "이벤트": ("events", (20, 10)),   # 일요일 다음 주 일정 루틴이 같은 저녁에 한 편 더 쓴다
}
FEED_SERIES = frozenset(SLOTS)
_PATTERNS = ("*.json", "previews/*.json", "features/*.json", "weekly/*.json", "events/*.json")
_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})")
_MARKET = {"kr": "한국장", "us": "미국장"}


def series_of(doc: dict) -> str | None:
    """이 원고가 피드의 어느 갈래인지 — 시황은 `market`, 나머지는 `series`. 피드 밖이면 None."""
    series = str(doc.get("series") or "")
    if series:
        return series if series in FEED_SERIES else None
    if "price_data" in doc or doc.get("market") in _MARKET:
        return _MARKET.get(str(doc.get("market")))
    return None


def slot_of(doc: dict, path: Path | None = None) -> datetime | None:
    """올라가는 시각(KST). 날짜는 원고의 `date`, 없으면 파일 이름에서. 피드 밖의 글은 None."""
    series = series_of(doc)
    if series is None:
        return None
    date_str = str(doc.get("date") or "")
    if not _DATE.match(date_str) and path is not None:
        found = _DATE.search(Path(path).name)
        date_str = found.group(1) if found else ""
    if not _DATE.match(date_str):
        return None
    try:
        day = datetime.strptime(date_str[:10], "%Y-%m-%d")
    except ValueError:
        return None
    if series == "미국장":
        day += timedelta(days=1)
    hour, minute = SLOTS[series][1]
    return day.replace(hour=hour, minute=minute)


def _load(path: Path) -> dict | None:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def feed_rows(root: Path | None = None) -> list[dict]:
    """피드의 모든 글 — 오래된 것부터. 각 행: slot·series·title·path·slug·doc."""
    base = (root or ROOT) / "editorial"
    rows: list[dict] = []
    for pattern in _PATTERNS:
        for path in sorted(base.glob(pattern)):
            doc = _load(path)
            if not doc:
                continue
            slot = slot_of(doc, path)
            title = str((doc.get("ko") or {}).get("title", "")).strip()
            if slot is None or not title:
                continue
            rows.append({"slot": slot, "series": series_of(doc) or "", "title": title,
                         "path": path, "slug": str(doc.get("slug") or ""), "doc": doc})
    rows.sort(key=lambda r: (r["slot"], r["path"].name))
    return rows


def rows_before(doc: dict | None = None, path: Path | None = None, count: int = 5, *,
                root: Path | None = None) -> list[dict]:
    """이 원고 바로 위에 보이는 최근 `count`편(행). `doc`가 있으면 그 글이 올라가는 시각보다
    앞선 글만, 없으면(아직 쓰기 전) 지금까지 전부. 자기 자신(같은 파일·같은 slug)은 뺀다."""
    cutoff = slot_of(doc, path) if doc is not None else None
    mine = Path(path).resolve() if path is not None else None
    my_name = mine.name if mine is not None else ""
    my_slug = str(doc.get("slug") or "") if doc is not None else ""
    out: list[dict] = []
    for row in feed_rows(root):
        other = row["path"]
        if mine is not None and other.resolve() == mine:
            continue
        if my_slug and row["slug"] == my_slug:
            continue
        if cutoff is not None:
            if row["slot"] > cutoff:
                continue
            # 같은 시각(주말 기준표 두 편)은 파일 이름 순서로 앞선 것만 '위에 보이는 글'이다.
            if row["slot"] == cutoff and not (my_name and other.name < my_name):
                continue
        out.append(row)
    return out[-count:]


def feed_titles(doc: dict | None = None, path: Path | None = None, count: int = 5, *,
                root: Path | None = None) -> list[str]:
    """관문이 뼈대·축·주인공을 대조하는 목록 — 독자가 보는 최근 `count`편 제목(오래된 것부터)."""
    return [row["title"] for row in rows_before(doc, path, count, root=root)]
