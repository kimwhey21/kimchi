"""검색되는 말 후보의 크기를 잰다 — 한 달에 몇 번 검색되는지(수요)와 그 말로 쓴 블로그 글이 몇 편인지(경쟁).

    python -m scripts.phrase_size "후보1" "후보2" "후보3"      # 고를 말부터 차례로
    python -m scripts.phrase_size --related "씨앗 낱말"         # 그 낱말의 연관 검색어를 검색 수 순으로 재어 준다
    python -m scripts.phrase_size --json "후보1" "후보2"
    python -m scripts.phrase_size --news "말"                   # 그 말의 최신 기사 제목·매체(국내 매체가 실제로 쓰는 표기와 출처 찾기)
    python -m scripts.phrase_size --official "말"               # 그 말을 다룬 공식 기관 문서(국세청·금융감독원·거래소 …)
    python -m scripts.phrase_size --guide                       # 한국어 가이드의 남은 주제를 지금 쓸 차례대로(뜨는 말 → 제철 → 나머지)

쓰는 자리: 「실험」 절의 검색되는 말 고르기(`docs/routine_magazine.md`·`routine_column.md`).
넓은 말(글이 십만 편 안팎부터)로는 새 글이 앞에 서지 못하고, 찾는 사람이 없는 말은 앞에 서도 아무도 오지 않는다 —
**좁은 말 가운데 검색 수가 가장 많은 말**을 고른다(좁음에 없으면 보통에서).
원천은 둘 다 공식 API다(화면을 긁지 않는다): 경쟁 글 수는 NAVER API HUB 블로그 검색(`NAVER_CLIENT_ID`·`NAVER_CLIENT_SECRET`),
월 검색 수는 네이버 검색광고 키워드 도구(`SEARCHAD_CUSTOMER_ID`·`SEARCHAD_API_KEY`·`SEARCHAD_SECRET`). 환경변수에서 읽고,
이 맥에서는 `~/.market-brief-naver/naver_api.env`. 열쇠 값은 어디에도 찍지 않는다. 검색광고 열쇠가 없으면 경쟁만 재고 그렇다고 알린다.

때를 재는 값 둘(2026-11-14): **기사 24시간**(뉴스 검색 — 지금 그 말로 기사가 쏟아지는가, `NAVER_NEWS_CLIENT_ID`·`NAVER_NEWS_CLIENT_SECRET`,
`--official`의 웹문서 검색도 이 열쇠)과 **검색 ×N**(검색어 트렌드 — 어제 검색이 그 앞 14일 평균의 몇 배인가, 블로그 검색과 같은 열쇠).
월 검색 수는 지난 30일 값이라 **오늘 처음 뜬 말은 0으로 나온다** — 그런 말은 기사 24시간 건수로 고른다(`pick`).
뉴스 열쇠가 없거나 이 둘을 못 받아도 고르기는 예전대로 된다(못 받았다고 알린다).
"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from email.utils import parsedate_to_datetime
from pathlib import Path

HUB = "https://naverapihub.apigw.ntruss.com"
API = HUB + "/search/v1/blog"
NEWS_API, DOCS_API, TREND_API = HUB + "/search/v1/news", HUB + "/search/v1/webkr", HUB + "/search-trend/v1/search"
KST = dt.timezone(dt.timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
GUIDE_DOC = ROOT / "docs" / "routine_guide_ko.md"
GUIDES = ROOT / "editorial" / "guides"
KEY_FILE = Path.home() / ".market-brief-naver" / "naver_api.env"
# 띠의 문턱(경쟁 글 수). 실측으로 정했다 — 내력은 비공개 기록. 바꿀 때는 그 뒤 올린 글의 순위를 다시 보고 바꾼다.
NARROW, MIDDLE = 15_000, 60_000
BANDS = ("좁음", "보통", "넓음")
# 한 번에 받는 건수. **30을 넘기지 않는다** — 100건을 한 번에 받으면 맨 앞 30건이 31~60번째로 밀려 나와 순위가 30씩 틀린다
# (2026-11-10 실측: 10건씩 세 쪽과 30건 한 쪽은 순서가 같고, 100건 한 번은 다르다).
PAGE = 30
AD_API, AD_URI = "https://api.searchad.naver.com", "/keywordstool"
MIN_SEARCHES = 100      # 월 검색이 이보다 적은 말은 앞에 서도 올 사람이 없다(잠정 — 순위 기록이 쌓이면 고친다)
RELATED_TOP = 15        # --related가 경쟁까지 재는 연관어 수(연관어마다 호출 한 번)
FRESH_NEWS = 10         # 월 검색이 아직 안 잡힌 말이라도 24시간 기사가 이만큼이면 '새로 뜬 말'로 고를 수 있다(잠정)
FRESH_SHARE = 0.005     # …그리고 그 24시간 기사가 그 말의 전체 기사의 이 몫을 넘어야 한다 — 늘 기사가 많은 흔한 말(`주식 유상증자`)을 거른다
NEWS_CAP = 100          # 뉴스 검색 한 번에 받는 기사 수 — 24시간 기사가 이보다 많으면 '100+'
SURGE = 1.5             # 어제 검색이 그 앞 14일 평균의 이 배수를 넘으면 '뜨는 중'
SURGE_MIN = 1_000       # 월 검색이 이보다 적은 말은 하루 몇 번꼴이라 배수가 우연히 튄다 — '뜨는 중'으로 치지 않는다(기사가 몰린 말은 예외)
SEASON_SHARE = 0.7      # 이번 달이나 다음 달 검색이 한 해 꼭대기의 이만큼이면 '제철'
SEASON_CONTRAST = 1.5   # …그리고 꼭대기가 보통 달(중앙값)의 이 배수는 돼야 한다 — 일 년 내내 비슷한 말은 제철이 없다
OFFICIAL = re.compile(r"(\.go\.kr|(^|\.)(fss|kofia|ksd|bok|kinfa|fsec|kcmi)\.or\.kr|(^|\.)krx\.co\.kr|(^|\.)hometax\.go\.kr)$")


class NoKeys(RuntimeError):
    """열쇠가 없다 — 조용히 넘어가지 않고 알린다."""


def _env(names: tuple[str, ...]) -> tuple[str, ...]:
    vals = [os.environ.get(n, "") for n in names]
    if not all(vals) and KEY_FILE.exists():
        f = dict(line.strip().split("=", 1) for line in KEY_FILE.read_text(encoding="utf-8").splitlines() if "=" in line)
        vals = [os.environ.get(n) or f.get(n, "") for n in names]
    return tuple(vals)


def load_keys() -> tuple[str, str]:
    cid, sec = _env(("NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET"))
    if not (cid and sec):
        raise NoKeys("NAVER_CLIENT_ID·NAVER_CLIENT_SECRET가 없습니다 — 환경변수(루틴) 또는 ~/.market-brief-naver/naver_api.env(맥)")
    return cid, sec


def load_news_keys() -> tuple[str, str] | None:
    """뉴스·웹문서 검색 열쇠(블로그 검색과 다른 애플리케이션). 없으면 None — 부르는 쪽이 '기사 수는 못 쟀다'고 알린다."""
    vals = _env(("NAVER_NEWS_CLIENT_ID", "NAVER_NEWS_CLIENT_SECRET"))
    return vals if all(vals) else None


def load_ad_keys() -> tuple[str, str, str] | None:
    """검색광고 열쇠(고객 번호, 액세스라이선스, 비밀키). 없으면 None — 부르는 쪽이 '검색 수는 못 쟀다'고 알린다."""
    vals = _env(("SEARCHAD_CUSTOMER_ID", "SEARCHAD_API_KEY", "SEARCHAD_SECRET"))
    return vals if all(vals) else None


def _norm(phrase: str) -> str:
    """키워드 도구의 표기: 띄어쓰기 없이, 로마자는 대문자."""
    return re.sub(r"\s+", "", phrase).upper()


def _count(v) -> int:
    """월 검색 수 칸. 10 미만은 문자열 '< 10'으로 온다 — 0으로 센다."""
    return v if isinstance(v, int) else 0


def keyword_tool(hints: list[str], ad_keys: tuple[str, str, str]) -> list[dict]:
    """키워드 도구 한 번(힌트 다섯 개까지). [{keyword, searches}] — searches는 PC+모바일 월 검색 수."""
    customer, api_key, secret = ad_keys
    ts = str(int(time.time() * 1000))
    sig = base64.b64encode(hmac.new(secret.encode(), f"{ts}.GET.{AD_URI}".encode(), hashlib.sha256).digest()).decode()
    url = AD_API + AD_URI + "?" + urllib.parse.urlencode({"hintKeywords": ",".join(_norm(h) for h in hints), "showDetail": 1})
    req = urllib.request.Request(url, headers={"X-Timestamp": ts, "X-API-KEY": api_key, "X-Customer": customer, "X-Signature": sig})
    with urllib.request.urlopen(req, timeout=30) as r:
        rows = json.loads(r.read()).get("keywordList") or []
    return [{"keyword": str(k.get("relKeyword", "")), "searches": _count(k.get("monthlyPcQcCnt")) + _count(k.get("monthlyMobileQcCnt"))} for k in rows]


def volumes(phrases: list[str], ad_keys: tuple[str, str, str]) -> dict[str, int]:
    """말마다 월 검색 수. 도구가 돌려주지 않은 말은 0(검색이 거의 없는 말)."""
    out: dict[str, int] = {}
    for i in range(0, len(phrases), 5):
        chunk = phrases[i:i + 5]
        got = {r["keyword"].upper(): r["searches"] for r in keyword_tool(chunk, ad_keys)}
        for p in chunk:
            out[p] = got.get(_norm(p), 0)
        time.sleep(0.5)
    return out


def related(seed: str, ad_keys: tuple[str, str, str]) -> list[dict]:
    """씨앗 낱말의 연관 검색어(씨앗의 낱말을 하나라도 품은 것만), 검색 수 많은 순."""
    tokens = [t.upper() for t in seed.split() if len(t) >= 2] or [_norm(seed)]
    rows = [r for r in keyword_tool([seed], ad_keys) if any(t in r["keyword"].upper() for t in tokens)]
    return sorted(rows, key=lambda r: -r["searches"])


def _hub(url: str, keys: tuple[str, str], params: dict | None = None, body: dict | None = None) -> dict:
    """NAVER API HUB 한 번. params면 GET, body면 JSON POST. 실패는 예외로 올린다."""
    headers = {"X-NCP-APIGW-API-KEY-ID": keys[0], "X-NCP-APIGW-API-KEY": keys[1]}
    data = None
    if params:
        url += "?" + urllib.parse.urlencode(params)
    if body is not None:
        data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=30) as r:
        return json.loads(r.read())


def _plain(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", str(text)).replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")).strip()


def _host(link: str) -> str:
    return urllib.parse.urlparse(link).netloc.removeprefix("www.")


def search(query: str, start: int = 1, display: int = PAGE, keys: tuple[str, str] | None = None) -> dict:
    """블로그 검색 한 쪽(관련도순). 실패는 예외로 올린다. display는 PAGE 이하로만 쓴다(위 PAGE 설명)."""
    return _hub(API, keys or load_keys(), {"query": query, "display": display, "start": start, "sort": "sim"})


def news(query: str, news_keys: tuple[str, str]) -> tuple[list[dict], int]:
    """그 말의 최신 기사 NEWS_CAP건(최신순)과 전체 기사 수. 기사는 [{title, press, link, at}] — at은 시간대가 붙은 datetime."""
    out = []
    page = _hub(NEWS_API, news_keys, {"query": query, "display": NEWS_CAP, "start": 1, "sort": "date"})
    for it in page.get("items") or []:
        try:
            at = parsedate_to_datetime(str(it.get("pubDate", "")))
        except (TypeError, ValueError):
            continue
        link = str(it.get("originallink") or it.get("link") or "")
        out.append({"title": _plain(it.get("title", "")), "press": _host(link), "link": link, "at": at})
    return out, int(page.get("total") or 0)


def news24(query: str, news_keys: tuple[str, str], now: dt.datetime | None = None) -> tuple[int, int]:
    """(지난 24시간에 그 말로 나온 기사 수, 전체 기사 수). 앞의 값은 NEWS_CAP에서 멈춘다 — 그 값이면 '그 이상'."""
    now = now or dt.datetime.now(dt.timezone.utc)
    items, total = news(query, news_keys)
    return sum(1 for a in items if (now - a["at"]).total_seconds() <= 86400), total


def is_fresh(row: dict) -> bool:
    """새로 뜬 말인가: 24시간 기사가 FRESH_NEWS건을 넘고, 그것이 그 말의 전체 기사에서 FRESH_SHARE를 넘는다."""
    n = row.get("news24") or 0
    return n >= FRESH_NEWS and n >= FRESH_SHARE * (row.get("news_total") or 0)


def official(query: str, news_keys: tuple[str, str]) -> list[dict]:
    """그 말을 다룬 공식 기관 문서(웹문서 검색 30건 가운데 OFFICIAL 도메인만). [{title, host, link, text}]"""
    items = _hub(DOCS_API, news_keys, {"query": query, "display": 30, "start": 1}).get("items") or []
    rows = [{"title": _plain(it.get("title", "")), "host": _host(str(it.get("link", ""))), "link": str(it.get("link", "")),
             "text": _plain(it.get("description", ""))} for it in items]
    return [r for r in rows if OFFICIAL.search(r["host"])]


def trend(phrases: list[str], keys: tuple[str, str], start: dt.date, end: dt.date, unit: str = "date") -> dict[str, dict[str, float]]:
    """검색어 트렌드: 말마다 {기간 첫날: 비율}. 한 번에 다섯 말. 비율은 그 호출 안의 상대값이다 —
    **말끼리 크기를 견주지 않고 한 말의 흐름만 본다.** 검색이 없던 날은 빠져서 온다(0으로 읽는다). 띄어 쓴 꼴과 붙여 쓴 꼴을 한 말로 묶는다."""
    out: dict[str, dict[str, float]] = {}
    phrases = list(dict.fromkeys(phrases))
    for i in range(0, len(phrases), 5):
        chunk = phrases[i:i + 5]
        body = {"startDate": start.isoformat(), "endDate": end.isoformat(), "timeUnit": unit,
                "keywordGroups": [{"groupName": p, "keywords": sorted({p, re.sub(r"\s+", "", p)})} for p in chunk]}
        for r in _hub(TREND_API, keys, body=body).get("results") or []:
            out[str(r.get("title", ""))] = {str(d["period"]): float(d["ratio"]) for d in r.get("data") or []}
        time.sleep(0.15)
    return out


def surge(series: dict[str, float], today: dt.date) -> float | None:
    """가장 최근에 집계된 날(어제, 새벽에는 그제)의 검색이 그 앞 14일 평균의 몇 배인가. 그날 검색이 없으면 None."""
    for back in (1, 2):
        last_day = today - dt.timedelta(days=back)
        if series.get(last_day.isoformat()):
            break
    else:
        return None
    base = sum(series.get((last_day - dt.timedelta(days=i)).isoformat(), 0.0) for i in range(1, 15)) / 14
    return round(min(series[last_day.isoformat()] / base, 99.0), 1) if base > 0 else 99.0


def surges(phrases: list[str], keys: tuple[str, str], today: dt.date | None = None) -> dict[str, float | None]:
    today = today or dt.datetime.now(KST).date()
    got = trend(phrases, keys, today - dt.timedelta(days=20), today)
    return {p: surge(got.get(p, {}), today) for p in phrases}


def seasons(phrases: list[str], keys: tuple[str, str], today: dt.date | None = None) -> dict[str, dict[int, float]]:
    """말마다 지난 열두 달의 달별 검색 비율 {월: 비율}."""
    today = today or dt.datetime.now(KST).date()
    end = today.replace(day=1) - dt.timedelta(days=1)
    start = end.replace(year=end.year - 1, day=1) + dt.timedelta(days=32)
    got = trend(phrases, keys, start.replace(day=1), end, unit="month")
    return {p: {int(k[5:7]): v for k, v in got.get(p, {}).items()} for p in phrases}


def in_season(months: dict[int, float], today: dt.date) -> bool:
    """이번 달이나 다음 달이 그 말의 한 해 꼭대기에 가까운가."""
    peak = max(months.values(), default=0)
    if peak <= 0:
        return False
    vals = sorted(months.get(m, 0.0) for m in range(1, 13))
    if peak < SEASON_CONTRAST * (vals[5] + vals[6]) / 2:
        return False
    return max(months.get(today.month, 0), months.get(today.month % 12 + 1, 0)) >= SEASON_SHARE * peak


def is_rising(row: dict) -> bool:
    """검색이 뜨는 중인가: 어제 검색이 평소의 SURGE배를 넘고, 그 배수를 믿을 만큼 찾는 사람이 있거나(SURGE_MIN) 기사가 몰린 말이다."""
    return (row.get("surge") or 0) >= SURGE and ((row.get("searches") or 0) >= SURGE_MIN or is_fresh(row))


def band(total: int) -> str:
    return BANDS[0] if total <= NARROW else BANDS[1] if total <= MIDDLE else BANDS[2]


def size(query: str, keys: tuple[str, str] | None = None) -> dict:
    """그 말의 경쟁 글 수와 띠."""
    total = int(search(query, display=1, keys=keys).get("total") or 0)
    return {"phrase": query, "total": total, "band": band(total)}


def rank(query: str, blog_pattern: str, depth: int = 300, keys: tuple[str, str] | None = None) -> dict:
    """그 말로 검색했을 때 `blog_pattern`(정규식, 블로그 주소에 대조)에 맞는 첫 글의 순위. depth 안에 없으면 rank는 None."""
    keys = keys or load_keys()
    pat, total = re.compile(blog_pattern), 0
    for start in range(1, depth + 1, PAGE):
        page = search(query, start=start, display=PAGE, keys=keys)
        total = int(page.get("total") or 0)
        items = page.get("items") or []
        for i, it in enumerate(items):
            if pat.search(str(it.get("link", ""))) or pat.search(str(it.get("bloggerlink", ""))):
                return {"phrase": query, "total": total, "band": band(total), "rank": start + i,
                        "title": re.sub(r"<[^>]+>", "", str(it.get("title", ""))), "link": str(it.get("link", ""))}
        if len(items) < PAGE:
            break
        time.sleep(0.15)
    return {"phrase": query, "total": total, "band": band(total), "rank": None, "title": "", "link": ""}


def pick(rows: list[dict]) -> dict | None:
    """고를 말: 월 검색이 MIN_SEARCHES를 넘는 말 가운데 좁음 띠에서 검색 수가 가장 많은 것, 좁음에 없으면 보통 띠에서.
    넓음 띠는 고르지 않는다. 검색 수를 못 쟀으면 None. (보통 띠의 검색 많은 말은 센 글이 몰려 있어 좁음을 먼저 본다.)"""
    for b in BANDS[:2]:
        ok = [r for r in rows if r["band"] == b and r.get("searches") is not None and r["searches"] >= MIN_SEARCHES]
        if ok:
            return max(ok, key=lambda r: (r["searches"], -r["total"]))
    # 새로 뜬 말(2026-11-14): 월 검색은 지난 30일 값이라 오늘 처음 뜬 이름·사건은 0으로 나온다 — 재긴 했는데 문턱 아래인 말 가운데
    # 지난 24시간에 기사가 몰린 것(`is_fresh`)을 고른다(실측: 방문을 가장 많이 만든 말들이 그날 뉴스의 이름+사건이었다).
    for b in BANDS[:2]:
        fresh = [r for r in rows if r["band"] == b and r.get("searches") is not None and is_fresh(r)]
        if fresh:
            return max(fresh, key=lambda r: (r["news24"], -r["total"]))
    return None


def _order(r: dict) -> tuple:
    return (BANDS.index(r["band"]), -(r.get("searches") or 0), r["total"])


NET_ERRORS = (urllib.error.URLError, ValueError, TimeoutError, KeyError)


def timing(rows: list[dict], keys: tuple[str, str], news_keys: tuple[str, str] | None, failed: list[tuple[str, str]]) -> None:
    """말마다 때를 재는 값을 붙인다: news24·news_total(뉴스 열쇠가 있을 때)과 surge. 못 받은 것은 failed에 적고 값은 None으로 둔다."""
    for r in rows:
        r["news24"] = r["news_total"] = r["surge"] = None
    if news_keys:
        for r in rows:
            try:
                r["news24"], r["news_total"] = news24(r["phrase"], news_keys)
            except NET_ERRORS as e:
                failed.append((f"기사 수: {r['phrase']}", f"{type(e).__name__}: {e}"))
            time.sleep(0.1)
    try:
        got = surges([r["phrase"] for r in rows], keys)
        for r in rows:
            r["surge"] = got.get(r["phrase"])
    except NET_ERRORS as e:
        failed.append(("검색 추세", f"{type(e).__name__}: {e}"))


def _line(r: dict) -> str:
    s_txt = "      –" if r.get("searches") is None else f"{r['searches']:>7,}"
    n = r.get("news24")
    n_txt = "   –" if n is None else f"{NEWS_CAP}+" if n >= NEWS_CAP else f"{n:>4}"
    g = r.get("surge")
    g_txt = "     " if g is None else f"×{g:<4}"
    mark = (" 기사 몰림" if is_fresh(r) else "") + (" 검색 뜨는 중" if is_rising(r) else "")
    return f"{r['band']}  월 검색 {s_txt}회  경쟁 글 {r['total']:>9,}편  기사 24시간 {n_txt}건  검색 {g_txt}{mark}  {r['phrase']}"


def guide_topics(doc: Path | None = None) -> list[dict]:
    """가이드 지시문의 주제 목록 줄(- `slug` — 설명 (검색어))을 읽는다. 이미 쓴 것은 written=True."""
    text = (doc or GUIDE_DOC).read_text(encoding="utf-8")
    group, out = "", []
    for line in text.splitlines():
        g = re.match(r"\*\*([A-Z])\. ", line)
        if g:
            group = g.group(1)
        m = re.match(r"- `([a-z0-9-]+)` — (.+?) \(([^()]+)\)\s*$", line)
        if m:
            out.append({"slug": m.group(1), "what": m.group(2), "phrase": m.group(3), "group": group,
                        "written": (GUIDES / f"ko_{m.group(1)}.json").exists()})
    return out


def guide_main(as_json: bool) -> int:
    """남은 가이드 주제를 지금 쓸 차례대로. 차례: 기사 몰림·검색 뜨는 중 → 제철 → 나머지, 그 안에서는 띠가 좁고 검색이 많은 것부터."""
    try:
        keys = load_keys()
    except NoKeys as e:
        print(f"⚠ {e}", file=sys.stderr)
        return 2
    topics = guide_topics()
    if not topics:
        print(f"⚠ 주제 목록을 읽지 못했습니다: {GUIDE_DOC}", file=sys.stderr)
        return 3
    today, failed = dt.datetime.now(KST).date(), []
    ad_keys, news_keys = load_ad_keys(), load_news_keys()
    phrases = [t["phrase"] for t in topics]
    vol: dict[str, int] = {}
    if ad_keys:
        try:
            vol = volumes(phrases, ad_keys)
        except NET_ERRORS as e:
            failed.append(("월 검색 수", f"{type(e).__name__}: {e}"))
    months: dict[str, dict[int, float]] = {}
    try:
        months = seasons(phrases, keys, today)
    except NET_ERRORS as e:
        failed.append(("달별 검색", f"{type(e).__name__}: {e}"))
    for t in topics:
        m = months.get(t["phrase"], {})
        t["searches"] = vol.get(t["phrase"]) if vol else None
        # 찾는 사람이 거의 없는 말은 달별 값도 우연이다 — 제철로 치지 않는다
        t["season"] = in_season(m, today) and (t["searches"] is None or t["searches"] >= MIN_SEARCHES)
        t["peak"] = max(m, key=m.get) if m else None
    left = [t for t in topics if not t["written"]]
    for t in left:
        try:
            t.update(size(t["phrase"], keys))
        except NET_ERRORS as e:
            failed.append((t["phrase"], f"{type(e).__name__}: {e}"))
            t.update(total=0, band=BANDS[2])
        time.sleep(0.1)
    timing(left, keys, news_keys, failed)
    left.sort(key=lambda t: (not (is_fresh(t) or is_rising(t)), not t["season"], *_order(t)))
    again = [t for t in topics if t["written"] and t["season"]]
    if as_json:
        print(json.dumps({"left": left, "written_in_season": again, "failed": [p for p, _ in failed]}, ensure_ascii=False, default=str))
    else:
        print(f"남은 주제 {len(left)}개 — 위에서부터 씁니다(어제와 같은 갈래는 건너뜁니다). 제철 = 이번 달·다음 달이 한 해 검색의 꼭대기")
        for t in left:
            flags = ("제철 " if t["season"] else "     ") + (f"꼭대기 {t['peak']:>2}월" if t["peak"] else "          ")
            print(f"{t['group']} {flags}  {_line(t)}  → {t['slug']}")
        if again:
            print("이미 쓴 주제 가운데 지금이 제철인 것(주제가 떨어졌을 때 파생 질문의 첫 후보): "
                  + ", ".join(f"{t['phrase']}({t['peak']}월)" for t in again))
        if not news_keys:
            print("(기사 수는 재지 못했습니다 — 뉴스 열쇠 NAVER_NEWS_CLIENT_ID·NAVER_NEWS_CLIENT_SECRET가 없습니다.)")
    for p, why in failed:
        print(f"⚠ 받지 못했습니다: {p} ({why})", file=sys.stderr)
    return 3 if failed else 0


def news_main(query: str, as_official: bool) -> int:
    news_keys = load_news_keys()
    if not news_keys:
        print("⚠ NAVER_NEWS_CLIENT_ID·NAVER_NEWS_CLIENT_SECRET가 없습니다 — 환경변수(루틴) 또는 ~/.market-brief-naver/naver_api.env(맥)", file=sys.stderr)
        return 2
    try:
        if as_official:
            rows = official(query, news_keys)
            for r in rows:
                print(f"{r['host']}  {r['title']}\n    {r['link']}\n    {r['text'][:110]}")
            if not rows:
                print(f"공식 기관 문서가 잡히지 않았습니다: {query} — 기관 이름을 붙여 다시 찾아 보십시오(예: `{query} 국세청`).")
            return 0
        now = dt.datetime.now(dt.timezone.utc)
        items, total = news(query, news_keys)
        day = [a for a in items if (now - a["at"]).total_seconds() <= 86400]
        print(f"{query}: 지난 24시간 기사 {len(day)}{'건 이상' if len(day) >= NEWS_CAP else '건'} (전체 {total:,}건) — 최신 15건")
        for a in items[:15]:
            print(f"{int((now - a['at']).total_seconds() // 3600):>4}시간 전  {a['press']:<22} {a['title']}\n            {a['link']}")
        return 0
    except NET_ERRORS as e:
        print(f"⚠ 받지 못했습니다: {query} ({type(e).__name__}: {e})", file=sys.stderr)
        return 3


def main(argv: list[str]) -> int:
    as_json, want_related = "--json" in argv, "--related" in argv
    phrases = [a for a in argv if not a.startswith("--")]
    if "--guide" in argv:
        return guide_main(as_json)
    if not phrases:
        print(__doc__.strip())
        return 2
    if "--news" in argv or "--official" in argv:
        return news_main(" ".join(phrases), "--official" in argv)
    try:
        keys = load_keys()
    except NoKeys as e:
        print(f"⚠ {e}", file=sys.stderr)
        return 2
    ad_keys, news_keys = load_ad_keys(), load_news_keys()
    failed: list[tuple[str, str]] = []
    vol: dict[str, int] = {}
    if want_related:
        if not ad_keys:
            print("⚠ --related는 검색광고 열쇠(SEARCHAD_*)가 있어야 합니다", file=sys.stderr)
            return 2
        seed = " ".join(phrases)
        try:
            rel = [r for r in related(seed, ad_keys) if r["searches"] >= MIN_SEARCHES]
        except (urllib.error.URLError, ValueError, TimeoutError) as e:
            print(f"⚠ 받지 못했습니다: 연관 검색어 ({type(e).__name__}: {e})", file=sys.stderr)
            return 3
        if len(rel) > RELATED_TOP:
            print(f"(연관 검색어 {len(rel)}개 중 검색 수 상위 {RELATED_TOP}개만 잽니다)")
        vol = {r["keyword"]: r["searches"] for r in rel[:RELATED_TOP]}
        phrases = list(vol)
        if not phrases:
            print(f"연관 검색어가 없습니다(월 검색 {MIN_SEARCHES}회 이상): {seed} — 새 이름·사건은 도구에 아직 없을 수 있습니다. 후보를 직접 적어 재 보십시오.")
            return 0
    elif ad_keys:
        try:
            vol = volumes(phrases, ad_keys)
        except (urllib.error.URLError, ValueError, TimeoutError) as e:
            failed.append(("월 검색 수", f"{type(e).__name__}: {e}"))
    rows = []
    for p in dict.fromkeys(phrases):
        try:
            rows.append({**size(p, keys), "searches": vol.get(p) if vol else None})
        except (urllib.error.URLError, ValueError, TimeoutError) as e:
            failed.append((p, f"{type(e).__name__}: {e}"))
        if want_related:
            time.sleep(0.15)
    timing(rows, keys, None if want_related else news_keys, failed)
    rows.sort(key=_order)
    best = pick(rows)
    if as_json:
        print(json.dumps({"rows": rows, "pick": best and best["phrase"], "failed": [p for p, _ in failed]}, ensure_ascii=False))
    else:
        for r in rows:
            print(_line(r))
        if not vol:
            print("(월 검색 수는 재지 못했습니다 — 검색광고 열쇠 SEARCHAD_*가 없습니다. 경쟁 글 수만으로 고르십시오.)")
            narrow = [r["phrase"] for r in rows if r["band"] == BANDS[0]]
            print(f"→ 좁은 말: {', '.join(narrow)}" if narrow else
                  "→ 좁은 말이 없습니다. 같은 이야기의 더 좁힌 말(이름+사건, 이름+제도, 낯선 고유명사)을 두세 개 더 재 보십시오.")
        elif best and (best["searches"] or 0) >= MIN_SEARCHES:
            print(f"→ 고를 말: {best['phrase']} (월 검색 {best['searches']:,}회 · 경쟁 글 {best['total']:,}편 · {best['band']})")
        elif best:
            print(f"→ 고를 말: {best['phrase']} (새로 뜬 말 — 월 검색은 아직 안 잡혔고 지난 24시간 기사 {best['news24']}건 · 경쟁 글 {best['total']:,}편 · {best['band']})")
        elif rows:
            print(f"→ 고를 말이 없습니다 — 앞에 설 수 있는 말(좁음·보통) 가운데 월 검색 {MIN_SEARCHES}회를 넘는 것도, 지난 24시간에 기사가 몰린 것도 없습니다. "
                  "다른 꼴(이름+사건, 이름+제도)을 더 재거나 `--related \"씨앗\"`으로 사람들이 실제로 치는 꼴을 찾으십시오.")
    if not news_keys and not want_related:   # 실패가 아니다(종료 코드는 그대로) — 다만 조용히 넘어가지 않는다
        print("(기사 수는 재지 못했습니다 — 뉴스 열쇠 NAVER_NEWS_CLIENT_ID·NAVER_NEWS_CLIENT_SECRET가 없습니다. 새로 뜬 말은 못 가립니다.)", file=sys.stderr)
    for p, why in failed:
        print(f"⚠ 받지 못했습니다: {p} ({why})", file=sys.stderr)
    return 3 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
