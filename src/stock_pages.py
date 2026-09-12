"""종목 허브 페이지 — /stocks/<slug>/ 37개와 목록 /stocks/ (2026-09-12, 유입 편성 3번, 사용자 승인).

왜
--
"삼성전자 주가", "SK하이닉스 주가 전망", "테슬라 주가"는 개인 투자자가 가장 많이 치는 검색어이고,
벤치마크(재테크농부) 118편 제목의 상당수가 종목 이름으로 시작한다. 시황은 하루짜리 글이라 그 검색어를
받지 못한다. 그래서 종목마다 **주소 하나를 두고 계속 갱신**한다 — 검색엔진은 오래 살아 있고 자주 바뀌는
주소에 순위를 준다.

무엇을 채우나
-------------
- 숫자: 코어 워치리스트 시세 파일(`data/price_<market>_<날짜>.json`)의 70거래일 이력에서 종가·하루·1주·
  1개월·3개월 등락과 3개월 고저. **다른 데서 가져오지 않는다.**
- 그림: `data_graphics.price_history`로 그린 3개월 차트(해시로 미디어 재사용).
- 회사 소개: `config/stock_pages.yaml`의 두 줄(사실만).
- 최근 흐름: 매달 1일 루틴이 쓰는 `editorial/stocks/notes_<YYYY-MM>.json`(`docs/routine_stock_notes.md`).
  없으면 절을 비운다 — 없는 판단을 만들어 넣지 않는다.
- 이 종목이 나온 글: `editorial/` 원고의 제목·소제목에 이름이 낱말로 나오는 글(post_tags.mentioned) 최근 5편.

실행
----
    python -m src.stock_pages --market all               # 렌더 + 업로드(스위치가 true면 공개, 아니면 임시저장)
    python -m src.stock_pages --market kr --render-only  # output/stocks/*.html만
    python -m src.stock_pages --check-notes editorial/stocks/notes_2026-10.json

`stock_pages.yml`이 매주 토요일 11:30 KST와 노트 파일 커밋 때 돌린다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, select_autoescape

from src import data_graphics, post_tags, publish_wordpress
from src.feature_checks import POSITION_PHRASES

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "stock_pages.yaml"
NOTES_DIR = ROOT / "editorial" / "stocks"
OUTPUT = ROOT / "output" / "stocks"
TEMPLATES = ROOT / "templates"
PARENT_SLUG = "stocks"
PARENT_TITLE = "종목별 주가 페이지"
TIMEOUT = 60
MARKET_LABEL = {"kr": "한국장", "us": "미국장"}
RELATED_LIMIT = 5
NOTE_MIN, NOTE_MAX = 60, 500


class StockPagesError(RuntimeError):
    pass


# ── 설정·시세 ──────────────────────────────────────────────────────────────

def load_config(path: Path = CONFIG) -> list[dict]:
    """설정의 종목 + 워치리스트의 이름·업종. 워치리스트에 없는 티커는 예외 — 시세가 없는 페이지를 만들지 않는다."""
    config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    items: list[dict] = []
    for market in ("kr", "us"):
        watch = yaml.safe_load((ROOT / "config" / f"watchlist_{market}.yaml").read_text(encoding="utf-8")) or {}
        by_ticker = {str(r["ticker"]): r for r in (watch.get("watchlist") or [])}
        for row in config.get(market) or []:
            ticker = str(row["ticker"])
            if ticker not in by_ticker:
                raise StockPagesError(f"{market} 워치리스트에 없는 티커입니다: {ticker} — 코어 종목만 페이지를 만든다")
            base = by_ticker[ticker]
            items.append({"market": market, "ticker": ticker, "slug": str(row["slug"]),
                          "name": str(base.get("name") or ticker), "name_en": str(base.get("name_en") or ""),
                          "sector": str(base.get("sector") or ""), "blurb": str(row.get("blurb") or "").strip()})
    slugs = [i["slug"] for i in items]
    if len(set(slugs)) != len(slugs):
        raise StockPagesError("slug가 겹칩니다: " + ", ".join(s for s in slugs if slugs.count(s) > 1))
    return items


def latest_price_file(market: str, data_dir: Path | None = None) -> Path:
    files = sorted((data_dir or ROOT / "data").glob(f"price_{market}_*.json"))
    if not files:
        raise StockPagesError(f"{market} 시세 파일이 없습니다")
    return files[-1]


def _fmt_price(value: float, unit: str) -> str:
    if unit == "달러" or unit == "$":
        return f"{value:,.2f}"
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def _pct(now: float | None, base: float | None) -> float | None:
    if now is None or base is None or not base:
        return None
    return round((now / base - 1) * 100, 2)


def _pct_text(value: float | None) -> str:
    return "—" if value is None else f"{value:+.2f}%"


def _cls(value: float | None) -> str:
    if value is None or value == 0:
        return ""
    return "up" if value > 0 else "down"


def stats(entry: dict, trading_date: str) -> dict:
    """종가·하루·1주·1개월(21거래일)·3개월(이력 첫 값)·3개월 고저. 이력이 없으면 예외 — 조용히 비우지 않는다."""
    history = entry.get("history") or {}
    closes = [float(v) for v in (history.get("close") or []) if v is not None]
    dates = [str(v) for v in (history.get("dates") or [])]
    if len(closes) < 5 or len(closes) != len(dates):
        raise StockPagesError(f"{entry.get('ticker')}: 이력이 없거나 짧습니다({len(closes)}일)")
    close = closes[-1]
    unit = str(entry.get("unit") or ("달러" if str(entry.get("ticker", "")).isalpha() or "=" in str(entry.get("ticker", "")) else "원"))
    pct_1d = float(entry.get("change_pct")) if entry.get("change_pct") is not None else _pct(close, closes[-2])
    pct_1w = data_graphics._pct_week(entry, trading_date)
    pct_1m = _pct(close, closes[-22]) if len(closes) >= 22 else None
    pct_3m = _pct(close, closes[0])
    high, low = max(closes), min(closes)
    high_i = closes.index(high)
    from_high = _pct(close, high)
    if from_high is not None and from_high >= -1:
        position = f"3개월 고점 부근입니다. 고점은 {dates[high_i][5:].replace('-', '/')}의 {_fmt_price(high, unit)}이고, 지금은 그보다 {abs(from_high):.1f}% 아래입니다."
    else:
        position = (f"3개월 고점({dates[high_i][5:].replace('-', '/')}, {_fmt_price(high, unit)})보다 {abs(from_high):.1f}% 아래, "
                    f"3개월 저점({_fmt_price(low, unit)})보다 {abs(_pct(close, low) or 0):.1f}% 위에 있습니다.")
    trend = "올랐고" if (pct_1m or 0) > 0 else "내렸고"
    # 등락 부호는 sans 서체로 — Literata 300에서는 '+'가 세로줄처럼 보였다(2026-09-12 첫 화면 확인)
    position += f" 최근 한 달 {abs(pct_1m or 0):.1f}% {trend}, 이번 주는 <span class=\"pct\">{_pct_text(pct_1w)}</span>입니다."
    return {"close": _fmt_price(close, unit), "close_raw": close, "unit": unit,
            "pct_1d": _pct_text(pct_1d), "pct_1w": _pct_text(pct_1w), "pct_1m": _pct_text(pct_1m), "pct_3m": _pct_text(pct_3m),
            "pct_1w_raw": pct_1w, "pct_1m_raw": pct_1m,
            "d_class": _cls(pct_1d), "w_class": _cls(pct_1w), "m_class": _cls(pct_1m), "q_class": _cls(pct_3m),
            "high_3m": _fmt_price(high, unit), "low_3m": _fmt_price(low, unit), "position_text": position,
            "first_date": dates[0], "last_date": dates[-1]}


# ── 루틴이 쓰는 노트 ────────────────────────────────────────────────────────

def latest_notes(notes_dir: Path = NOTES_DIR) -> tuple[dict, str] | None:
    files = sorted(notes_dir.glob("notes_*.json"))
    if not files:
        return None
    doc = json.loads(files[-1].read_text(encoding="utf-8"))
    return (doc.get("notes") or {}), str(doc.get("checked") or files[-1].stem.replace("notes_", ""))


def validate_notes(doc: dict, items: list[dict]) -> list[str]:
    """매달 루틴이 커밋하기 전에 돌리는 검사. 빠진 종목·길이·포지션 화법·마크다운 볼드를 막는다."""
    issues: list[str] = []
    notes = doc.get("notes") or {}
    if not re.fullmatch(r"\d{4}-\d{2}", str(doc.get("month") or "")):
        issues.append("`month`(YYYY-MM)가 없습니다.")
    try:
        dt.date.fromisoformat(str(doc.get("checked")))
    except (TypeError, ValueError):
        issues.append("`checked`(YYYY-MM-DD)가 없습니다.")
    for item in items:
        note = str(notes.get(item["ticker"]) or "").strip()
        if not note:
            issues.append(f"{item['name']}({item['ticker']}) 노트가 없습니다.")
            continue
        if not NOTE_MIN <= len(note) <= NOTE_MAX:
            issues.append(f"{item['name']} 노트가 {len(note)}자입니다 — {NOTE_MIN}~{NOTE_MAX}자.")
        for phrase in POSITION_PHRASES:
            if phrase in note:
                issues.append(f"{item['name']} 노트에 포지션 화법 {phrase!r} — 우리는 종목을 들고 있지 않습니다.")
        if "**" in note:
            issues.append(f"{item['name']} 노트에 마크다운 볼드(**)가 있습니다 — <b>…</b>.")
        if re.search(r"(오를|내릴|상승할|하락할) (것이다|겁니다|것입니다)", note):
            issues.append(f"{item['name']} 노트가 예측합니다 — 조건문으로 쓰십시오.")
    return issues


# ── 이 종목이 나온 글 ───────────────────────────────────────────────────────

def _doc_url(doc: dict, path: Path) -> str:
    market = doc.get("market")
    if market in ("kr", "us"):
        return f"https://fermata.it.kr/editorial-{market}-{doc.get('date')}-ko/"
    slug = doc.get("slug") or (f"us-{doc.get('date')}-preview" if doc.get("series") == "프리뷰"
                               else path.stem.replace("_", "-", 1).replace("_", "-"))
    return f"https://fermata.it.kr/{slug}/"


def related_posts(name: str, editorial_dir: Path | None = None, limit: int = RELATED_LIMIT) -> list[dict]:
    """제목이나 소제목에 이름이 낱말로 나오는 우리 글, 최신순. 영어 원고는 뺀다."""
    base = editorial_dir or ROOT / "editorial"
    rows: list[tuple[str, str, str]] = []
    for path in glob.glob(str(base / "**" / "*.json"), recursive=True):
        p = Path(path)
        if p.parent.name == "stocks":
            continue
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if str(doc.get("lang") or "ko") == "en":
            continue
        ko = doc.get("ko") or {}
        title = str(ko.get("title") or "")
        sections = ko.get("narrative") or []
        headings = " ".join(str(s.get("heading", "")) for s in sections)
        body = " ".join(str(s.get("body", "")) for s in sections)
        if not title:
            continue
        # 제목·소제목에 나온 글이 먼저, 본문에만 나온 글은 그다음(2026-09-12: 제목만 보니 삼성전자도 두 편뿐이었다)
        if post_tags.mentioned(name, title) or post_tags.mentioned(name, headings):
            rank = 0
        elif post_tags.mentioned(name, body):
            rank = 1
        else:
            continue
        rows.append((rank, str(doc.get("date") or ""), title, _doc_url(doc, p)))
    rows.sort(key=lambda r: (r[0], r[1]), reverse=False)
    rows = sorted(rows, key=lambda r: r[1], reverse=True)
    rows = sorted(rows, key=lambda r: r[0])
    return [{"date": d, "title": t, "url": u} for _, d, t, u in rows[:limit]]


# ── 렌더 ─────────────────────────────────────────────────────────────────────

def _env() -> Environment:
    return Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=select_autoescape(["html", "xml", "j2"]))


def _label(date_str: str) -> str:
    d = dt.date.fromisoformat(date_str)
    return f"{d.year}년 {d.month}월 {d.day}일"


def render_page(item: dict, s: dict, trading_date: str, chart_url: str | None,
                note: str | None, note_label: str | None, related: list[dict]) -> str:
    return _env().get_template("stock.html.j2").render(
        mode="page", market_label=MARKET_LABEL[item["market"]], trading_label=_label(trading_date),
        name=item["name"], name_en=item["name_en"], ticker=item["ticker"], sector=item["sector"], s=s,
        chart_url=chart_url, blurb=item["blurb"], note=note, note_label=note_label, related=related)


def render_index(rows: list[dict], trading_dates: dict[str, str]) -> str:
    groups = []
    for market in ("kr", "us"):
        part = [r for r in rows if r["market"] == market]
        if part:
            groups.append({"label": f"{MARKET_LABEL[market]} · {_label(trading_dates[market])} 마감", "rows": part})
    labels = [_label(trading_dates[m]) for m in ("kr", "us") if m in trading_dates]
    label = " / ".join(dict.fromkeys(labels))   # 두 시장의 기준일이 같으면 한 번만
    return _env().get_template("stock.html.j2").render(mode="index", rows=rows, groups=groups, trading_label=label)


def excerpt(item: dict, s: dict, trading_date: str) -> str:
    return (f"{item['name']}({item['ticker']}) 주가: {_label(trading_date)} 종가 {s['close']}{s['unit']}, "
            f"1주 {s['pct_1w']}, 1개월 {s['pct_1m']}, 3개월 {s['pct_3m']}. 3개월 차트와 이 종목이 나온 시황·Checkpoint를 매주 갱신합니다.")


def page_title(item: dict) -> str:
    return f"{item['name']} 주가 ({item['ticker']})"


# ── 워드프레스 ───────────────────────────────────────────────────────────────

def _find_page(base: str, auth: tuple[str, str], slug: str) -> dict | None:
    response = requests.get(f"{base}/wp-json/wp/v2/pages", auth=auth, timeout=TIMEOUT,
                            params=[("slug", slug), ("context", "edit"), ("per_page", "5"),
                                    *(("status[]", s) for s in ("publish", "draft", "pending", "private"))])
    response.raise_for_status()
    pages = response.json()
    return pages[0] if pages else None


def upsert_page(base: str, auth: tuple[str, str], slug: str, title: str, html: str, *,
                parent: int = 0, excerpt_text: str = "", live: bool) -> dict:
    """있으면 본문·제목·요약만 갱신(상태 유지), 없으면 스위치에 따라 공개/임시저장으로 만든다. 저장 뒤 되읽는다."""
    page = _find_page(base, auth, slug)
    body = {"title": title, "content": html, "excerpt": excerpt_text, "parent": parent, "template": "page-no-title"}
    if page:
        response = requests.post(f"{base}/wp-json/wp/v2/pages/{page['id']}", auth=auth, json=body, timeout=TIMEOUT)
        action = f"갱신 (상태 {page.get('status')})"
    else:
        body.update({"slug": slug, "status": "publish" if live else "draft"})
        response = requests.post(f"{base}/wp-json/wp/v2/pages", auth=auth, json=body, timeout=TIMEOUT)
        action = "새로 만듦 (공개)" if live else "새로 만듦 (임시저장)"
    if response.status_code >= 400:
        raise StockPagesError(f"{slug} 저장 실패 (HTTP {response.status_code}): {response.text[:300]}")
    result = response.json()
    check = requests.get(f"{base}/wp-json/wp/v2/pages/{result['id']}", auth=auth, params={"context": "edit"}, timeout=TIMEOUT)
    check.raise_for_status()
    raw = check.json()["content"]["raw"]
    if title.split(" (")[0] not in raw and PARENT_TITLE not in raw:
        raise StockPagesError(f"{slug}: 저장 뒤 되읽었더니 본문이 다릅니다.")
    print(f"페이지 {action}: /{PARENT_SLUG}/{slug if slug != PARENT_SLUG else ''} id={result['id']}")
    return result


def _upload_chart(base: str, auth: tuple[str, str], path: Path, alt: str) -> str:
    media_id = publish_wordpress.upload_featured_image(base, auth, {"local_path": str(path), "alt": alt,
                                                                    "caption": "페르마타 시세 파일로 그린 3개월 종가.", "id": path.stem})
    if not media_id:
        raise StockPagesError(f"차트 업로드 실패: {path}")
    response = requests.get(f"{base}/wp-json/wp/v2/media/{media_id}", auth=auth, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()["source_url"]


# ── 전체 실행 ────────────────────────────────────────────────────────────────

def build(markets: list[str], *, upload: bool, live: bool, data_dir: Path | None = None) -> dict:
    items = [i for i in load_config() if i["market"] in markets]
    prices = {m: json.loads(latest_price_file(m, data_dir).read_text(encoding="utf-8")) for m in markets}
    trading_dates = {m: str(prices[m]["trading_date"]) for m in markets}
    notes = latest_notes()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    base = auth = None
    if upload:
        if not publish_wordpress.is_configured():
            raise StockPagesError("워드프레스 설정이 없어 올리지 못했습니다(WORDPRESS_URL·WORDPRESS_USERNAME·WORDPRESS_APP_PASSWORD).")
        base = os.environ["WORDPRESS_URL"].rstrip("/")
        auth = (os.environ["WORDPRESS_USERNAME"], os.environ["WORDPRESS_APP_PASSWORD"])
    index_rows, done, missing = [], [], []
    parent_id = 0
    if upload:
        parent = _find_page(base, auth, PARENT_SLUG)
        parent_id = parent["id"] if parent else 0
    for item in items:
        market = item["market"]
        entry = (prices[market].get("watchlist") or {}).get(item["ticker"]) or (prices[market].get("macro") or {}).get(item["ticker"])
        if not entry:
            missing.append(f"{item['name']}({item['ticker']}): 시세 파일에 없음")
            continue
        try:
            s = stats(entry, trading_dates[market])
        except StockPagesError as error:
            missing.append(str(error))
            continue
        chart = OUTPUT / f"{item['slug']}-3m.png"
        data_graphics.price_history(prices[market], chart, ticker=item["ticker"],
                                    title=f"{item['name']}, 최근 3개월", subtitle=f"{_label(trading_dates[market])} 종가 {s['close']}{s['unit']}")
        chart_url = _upload_chart(base, auth, chart, f"{item['name']} 최근 3개월 종가 차트") if upload else str(chart)
        note = note_label = None
        if notes and notes[0].get(item["ticker"]):
            note, note_label = str(notes[0][item["ticker"]]), _label(notes[1]) + " 기준"
        related = related_posts(item["name"])
        html = render_page(item, s, trading_dates[market], chart_url, note, note_label, related)
        (OUTPUT / f"{item['slug']}.html").write_text(html, encoding="utf-8")
        if upload:
            if not parent_id:
                # 자리만 잡는다 — 되읽기 검사가 제목을 찾으므로 본문에 제목을 넣는다(2026-09-12 첫 실행이 여기서 죽었다)
                parent_id = upsert_page(base, auth, PARENT_SLUG, PARENT_TITLE, f"<p>{PARENT_TITLE} — 준비 중</p>", live=live)["id"]
            upsert_page(base, auth, item["slug"], page_title(item), html, parent=parent_id,
                        excerpt_text=excerpt(item, s, trading_dates[market]), live=live)
        index_rows.append({"market": market, "name": item["name"], "ticker": item["ticker"], "sector": item["sector"],
                           "url": f"/{PARENT_SLUG}/{item['slug']}/", "close": s["close"], "pct_1w": s["pct_1w"], "pct_1m": s["pct_1m"],
                           "w_class": s["w_class"], "m_class": s["m_class"]})
        done.append(item["slug"])
    index_html = render_index(index_rows, trading_dates)
    (OUTPUT / "index.html").write_text(index_html, encoding="utf-8")
    if upload and index_rows:
        upsert_page(base, auth, PARENT_SLUG, PARENT_TITLE, index_html, live=live)
        requests.post(f"{base}/wp-json/wp-super-cache/v1/cache", auth=auth, json={"delete_cache": True}, timeout=TIMEOUT)
    if missing:
        # 몇 종목이 빠진 채 "성공"으로 끝나지 않게 한다 — 다만 만든 페이지는 그대로 둔다.
        raise StockPagesError("일부 종목을 만들지 못했습니다:\n- " + "\n- ".join(missing))
    return {"pages": done, "index": str(OUTPUT / "index.html"), "trading_dates": trading_dates}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--market", default="all", choices=["all", "kr", "us"])
    parser.add_argument("--render-only", action="store_true")
    parser.add_argument("--publish", action="store_true", help="새 페이지를 공개로 만든다. 저장소 변수 FERMATA_AUTO_PUBLISH=true도 같다.")
    parser.add_argument("--check-notes", type=Path, help="루틴 노트 파일을 검사만 한다")
    args = parser.parse_args(argv)
    if args.check_notes:
        issues = validate_notes(json.loads(args.check_notes.read_text(encoding="utf-8")), load_config())
        if issues:
            print("노트 검사 실패:\n- " + "\n- ".join(issues))
            return 1
        print("노트 검사 통과")
        return 0
    live = args.publish or os.environ.get("FERMATA_AUTO_PUBLISH", "").strip().lower() == "true"
    markets = ["kr", "us"] if args.market == "all" else [args.market]
    result = build(markets, upload=not args.render_only, live=live)
    print(f"완료: {len(result['pages'])}개 페이지, 기준일 {result['trading_dates']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
