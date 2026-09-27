"""본진 한국 종목 데이터베이스 — 코스피·코스닥 전 종목을 영어 데이터 페이지로 (2026-09-27, 사장님 "바로 정식버전으로 구현하자").

    python -m src.stock_db webcheck                 # 회사 홈페이지가 아직 열리는지 다시 보고, 닫힌 것은 링크를 뺀다
    python -m src.stock_db rename                   # 이름 다듬기 규칙을 고친 뒤 메타 이름만 다시 짓기(DART 호출 없음)
    python -m src.stock_db meta                     # data/stock_meta.json(영문명·업종·설립·홈페이지) 만들기·보강 — 커밋하는 파일
    python -m src.stock_db run --push               # 매일: 전 종목 시세 + 상위 종목·순번 종목 상세 → 워드프레스
    python -m src.stock_db run --detail-all --push  # 처음 채우기(이 맥에서, 50분 안팎)
    python -m src.stock_db run --out output/stock_db   # 올리지 않고 JSON만(점검)

왜: 글(시황·가이드)은 AI가 답을 먼저 보여 줘서 클릭이 안 난다(2026-09 조사). 데이터 페이지는 사람이 숫자를 보러 직접 오고,
종목 수만큼 주소가 생긴다(StockAnalysis 모델). StockAnalysis는 한국을 코스피 829종목만, 외국인 지분·수급 없이 다룬다 —
그 빈자리를 영어로 채운다.

원천(2026-09-27 이 맥에서 확인):
- 네이버 모바일 증권 API(비공식): 전 종목 목록·시세(`/api/stocks/marketValue/{KOSPI|KOSDAQ}`), 종목 상세(`/integration`:
  PER·PBR·EPS·배당·외국인 소진율·컨센서스·5일 투자자별 순매수·동종 업종), 재무 4년(`/finance/annual`), 일봉·외국인 보유율 이력
  (`api.stock.naver.com/chart/domestic/item/{code}`), 지수(`/api/index/KOSPI/basic`)와 지수 투자자 수급(`/trend`).
- DART OpenAPI(`DART_API_KEY`): 상장사 영문명(corpCode.xml)과 업종·설립일·홈페이지(company.json) — `data/stock_meta.json`에 쌓아 커밋한다.
- SKHY(나스닥 ADR, 10주=원주 1주): yfinance.
글에 한글이 들어가면 안 된다(영어 사이트) — 이름은 DART 영문명, 업종은 KSIC 대분류 영어 표기, 동종 업종은 코드로 영문명을 찾는다.

워드프레스 쪽은 `templates/wp_stock_db.php`(코드 조각)가 받는다: 종목마다 옵션 하나(`fm_s_<code>`), 목록(`fm_stock_index`), 시장
요약(`fm_market`). 매일 시세만 바뀐 종목은 `q`(시세)만 보내 합친다 — 상세는 상위 종목과 요일별 순번으로 돌아가며 새로 받는다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import io
import json
import os
import re
import sys
import time
import zipfile
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
META = ROOT / "data" / "stock_meta.json"
WATCHLIST = ROOT / "config" / "watchlist_kr.yaml"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"}
NAVER = "https://m.stock.naver.com/api"
CHART = "https://api.stock.naver.com/chart/domestic/item/{code}?periodType=dayCandle"
DART = "https://opendart.fss.or.kr/api"
PAUSE = 0.18            # 네이버 요청 사이(초) — 한꺼번에 몰면 막힌다
DETAIL_TOP = 300        # 매일 상세를 새로 받는 시가총액 상위 종목 수
ROTATE_DAYS = 7         # 나머지 종목은 이 주기로 돌아가며 상세를 받는다
HISTORY_DAYS = 130      # 페이지 차트·외국인 보유율 이력 길이(거래일)
BATCH_BYTES = 50_000    # 워드프레스로 한 번에 보내는 양 — 56KB는 되고 224KB는 카페24가 502로 끊었다(2026-09-27)

# KSIC 대분류(앞 두 자리) → 영어. DART company.json의 induty_code 앞 두 자리로 찾는다(2026-09-27).
KSIC = {
    "01": "Agriculture", "02": "Forestry", "03": "Fishing", "05": "Coal mining", "06": "Oil & gas extraction",
    "07": "Metal ore mining", "08": "Mining", "10": "Food products", "11": "Beverages", "12": "Tobacco",
    "13": "Textiles", "14": "Apparel", "15": "Leather & footwear", "16": "Wood products", "17": "Pulp & paper",
    "18": "Printing", "19": "Refined petroleum", "20": "Chemicals", "21": "Pharmaceuticals", "22": "Rubber & plastics",
    "23": "Glass, cement & ceramics", "24": "Steel & metals", "25": "Fabricated metal products",
    "26": "Semiconductors & electronic components", "27": "Medical & precision instruments", "28": "Electrical equipment",
    "29": "Machinery", "30": "Autos & auto parts", "31": "Shipbuilding, aerospace & rail", "32": "Furniture",
    "33": "Other manufacturing", "34": "Industrial repair", "35": "Electric & gas utilities", "36": "Water supply",
    "37": "Sewage treatment", "38": "Waste management", "39": "Environmental remediation", "41": "Construction",
    "42": "Specialty construction", "45": "Auto sales", "46": "Wholesale trade", "47": "Retail", "49": "Land transport",
    "50": "Shipping", "51": "Airlines", "52": "Logistics", "55": "Hotels & lodging", "56": "Restaurants",
    "58": "Software & game publishing", "59": "Film, video & music", "60": "Broadcasting", "61": "Telecommunications",
    "62": "IT services", "63": "Internet & information services", "64": "Financial services", "65": "Insurance",
    "66": "Brokerage & asset management", "68": "Real estate", "70": "Research & development",
    "71": "Professional services", "72": "Engineering services", "73": "Scientific & technical services",
    "74": "Facility management", "75": "Business support services", "76": "Rental & leasing", "85": "Education",
    "86": "Health care", "87": "Social services", "90": "Arts & creative", "91": "Sports & recreation",
    "94": "Associations", "95": "Repair services", "96": "Personal services",
}
# 한국거래소 휴장일(2026) — editorial/guides/en_korea-market-holidays-2026.json과 같다. 해가 바뀌면 다음 해를 더한다.
KRX_HOLIDAYS = {
    "2026-01-01": "New Year's Day", "2026-02-16": "Lunar New Year", "2026-02-17": "Lunar New Year",
    "2026-02-18": "Lunar New Year", "2026-03-02": "Independence Movement Day (observed)", "2026-05-01": "Labor Day",
    "2026-05-05": "Children's Day", "2026-05-25": "Buddha's Birthday (observed)", "2026-06-03": "Local elections",
    "2026-07-17": "Constitution Day", "2026-08-17": "Liberation Day (observed)", "2026-09-24": "Chuseok",
    "2026-09-25": "Chuseok", "2026-10-05": "National Foundation Day (observed)", "2026-10-09": "Hangul Day",
    "2026-12-25": "Christmas Day", "2026-12-31": "Year-end closing",
}
_ACRONYM_KEEP = {"SK", "LG", "KB", "GS", "CJ", "HD", "LS", "DB", "KT", "NH", "BNK", "DGB", "JB", "KCC", "OCI", "SKC",
                 "SPC", "HMM", "KG", "SM", "YG", "JYP", "CNH", "KTB", "DL", "HL", "HK", "SNT", "KPX", "KISCO", "POSCO",
                 "KT&G", "BGF", "HDC", "SGC", "GKL", "KCTC", "AJ", "HLB", "NHN", "SOOP", "CJ", "KIWOOM", "DN", "TKG", "SBS", "KBS", "MBC"}
_SMALL = {"CO", "LTD", "INC", "CORP", "THE", "AND", "OF", "FOR", "HOLDINGS", "GROUP"}


class StockDBError(RuntimeError):
    pass


# ── 이름 ─────────────────────────────────────────────────────────────────────────────
def clean_name(raw: str) -> str:
    """DART 영문명 다듬기. 'SAMSUNG ELECTRONICS CO,.LTD' → 'Samsung Electronics Co., Ltd.'.
    대문자만 쓴 이름은 낱말마다 글자 크기를 고치고, 섞인 이름에서도 다섯 자 이상 대문자 낱말(AMOREPACIFIC)은 고친다.
    약어(SK·KT&G·POSCO)와 모음 없는 세 자 이하 낱말(CJ ENM의 ENM은 모음이 있어 네 자 이하 규칙으로 남긴다)은 둔다."""
    s = re.sub(r"\s+", " ", html.unescape(html.unescape(raw or "")).strip())
    if " " not in s and len(s) > 12:                                     # DART가 붙여 쓴 이름: EugeneTechnologyCo.,Ltd.
        s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s)
    s = re.sub(r"(?i)(?<=[a-z])(co\.,\s*ltd\.?)$", r" \1", s)             # Fireinsuranceco.,ltd.
    s = re.sub(r"(\w{3,})\s*&\s*(\w{3,})", r"\1 & \2", s)          # INVESTMENT&SECURITIES → 띄움
    s = re.sub(r"\b(\w{1,2}) & (\w{1,2})\b", r"\1&\2", s)          # KT&G·F&C·D&D는 붙인다
    body = re.sub(r"(?i)[,\s]*(co\s*[.,]*\s*ltd\.?|inc\.?|corp(oration)?\.?|ltd\.?)\s*$", "", s)
    letters = re.sub(r"[^A-Za-z]", "", body)
    all_caps = bool(letters) and letters.isupper() and len(letters) > 4
    words = []
    for word in s.split(" "):
        core = re.sub(r"[^A-Za-z&]", "", word).upper()
        if not word.isupper() or not core:
            words.append(word)
        elif core in _ACRONYM_KEEP or (len(core) <= 3 and core not in _SMALL and not re.search(r"[AEIOU]", core[1:])):
            words.append(word)
        elif all_caps or len(core) >= 5:
            words.append(word.capitalize())
        else:
            words.append(word)
    s = " ".join(words)
    s = re.sub(r"(?i)\bco\s*[.,]*\s*ltd\.?", "Co., Ltd.", s)
    s = re.sub(r"(?i)\binc\.?$", "Inc.", s)
    return s


def short_name(full: str) -> str:
    """페이지 제목·목록에 쓰는 짧은 이름 — 회사 형태 꼬리(Co., Ltd. / Inc. / Corporation)를 뗀다."""
    s = full
    for _ in range(3):
        s = re.sub(r"(?i)[,\s]*\b(co\.?,?\s*ltd\.?|co\.?|ltd\.?|inc\.?|incorporation|corporation|corp\.?|company|limited)\s*$", "", s).strip(" ,.&")
    return s or full


# DART 영문명이 붙여 쓰였거나 잘린 대형주 — 사람이 고친 표기(2026-09-27, 시가총액 상위 250개를 눈으로 보고)
NAME_FIX = {
    "006400": "Samsung SDI", "001450": "Hyundai Marine & Fire Insurance", "032820": "Woori Technology",
    "180640": "Hanjin KAL", "282330": "BGF Retail", "089860": "Lotte Rental", "281820": "KC Tech",
    "064350": "Hyundai Rotem", "071970": "HD Hyundai Marine Engine", "036460": "Korea Gas", "377300": "KakaoPay",
    "326030": "SK Biopharmaceuticals", "097950": "CJ CheilJedang", "051900": "LG H&H", "036570": "NCSoft",
}


def watchlist_names(path: Path = WATCHLIST) -> dict[str, str]:
    """워치리스트의 name_en(사람이 고른 표기)을 우선한다 — 'SK Hynix'가 'SK hynix'보다 낫다."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out = {}
    for group in data.values():
        for row in group if isinstance(group, list) else []:
            if isinstance(row, dict) and re.fullmatch(r"\w{6}", str(row.get("ticker") or "")) and row.get("name_en"):
                out[str(row["ticker"])] = str(row["name_en"])
    out.update(NAME_FIX)
    return out


def clean_web(raw: str) -> str:
    """DART 홈페이지 칸 — 주소처럼 생긴 것만 둔다('없음'·'-' 같은 값이 실제로 있다)."""
    s = (raw or "").strip()
    return s if re.fullmatch(r"(https?://)?[\w.-]+\.[a-zA-Z]{2,}(/\S*)?", s) else ""


def base_code(code: str) -> str:
    """우선주(005935·00088K 등)는 보통주 코드(마지막 자리 0)로 DART를 찾는다."""
    return code[:5] + "0"


# ── 네이버 ───────────────────────────────────────────────────────────────────────────
def _get(session: requests.Session, url: str, *, params=None, tries: int = 4) -> requests.Response:
    last = None
    for attempt in range(tries):
        try:
            r = session.get(url, params=params, timeout=25)
            if r.status_code == 200:
                return r
            last = f"HTTP {r.status_code}"
        except requests.RequestException as error:
            last = repr(error)
        time.sleep(2 + attempt * 3)
    raise StockDBError(f"{url} — {last}")


def _num(text) -> float | None:
    if text is None:
        return None
    s = str(text).replace(",", "").replace("배", "").replace("원", "").replace("%", "").replace("+", "").strip()
    if s in ("", "-", "N/A", "NaN"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def list_market(session: requests.Session, market: str) -> list[dict]:
    """전 종목 목록(주식만 — ETF·ETN 제외). 시가총액 순."""
    rows, page = [], 1
    while True:
        data = _get(session, f"{NAVER}/stocks/marketValue/{market}", params={"page": page, "pageSize": 100}).json()
        stocks = data.get("stocks") or []
        for s in stocks:
            if s.get("stockEndType") != "stock":
                continue
            rows.append({
                "code": s["itemCode"], "market": market, "name_ko": s.get("stockName"),
                "close": _num(s.get("closePriceRaw") or s.get("closePrice")),
                "chg": _num(s.get("compareToPreviousClosePriceRaw") or s.get("compareToPreviousClosePrice")) or 0.0,
                "pct": _num(s.get("fluctuationsRatio")) or 0.0,
                "volume": _num(s.get("accumulatedTradingVolumeRaw") or s.get("accumulatedTradingVolume")),
                "value": _num(s.get("accumulatedTradingValueRaw")),
                "mcap": _num(s.get("marketValueRaw")),
                "date": str(s.get("localTradedAt") or "")[:10],
                "trading": (s.get("tradeStopType") or {}).get("name") == "TRADING",
            })
            if (s.get("compareToPreviousPrice") or {}).get("name") in ("FALLING", "LOWER_LIMIT") and rows[-1]["chg"] > 0:
                rows[-1]["chg"] = -rows[-1]["chg"]
        if len(stocks) < 100 or page * 100 >= int(data.get("totalCount") or 0):
            break
        page += 1
        time.sleep(PAUSE)
    return rows


_TOTAL_KEYS = {"전일": "prev", "시가": "open", "고가": "high", "저가": "low", "52주 최고": "high52", "52주 최저": "low52",
               "PER": "per", "EPS": "eps", "추정PER": "fper", "추정EPS": "feps", "PBR": "pbr", "BPS": "bps",
               "배당수익률": "div_yield", "주당배당금": "dps", "외인소진율": "foreign_ratio"}
_FIN_ROWS = {"매출액": "revenue", "영업이익": "op", "당기순이익": "net", "영업이익률": "opm", "순이익률": "npm",
             "ROE": "roe", "부채비율": "debt", "EPS": "eps", "PER": "per", "BPS": "bps", "PBR": "pbr", "주당배당금": "dps"}


def detail(session: requests.Session, code: str) -> dict:
    """종목 상세 — 지표·컨센서스·5일 수급·동종 업종(integration), 재무 4년(finance/annual), 일봉·외국인 보유율 이력(chart)."""
    integ = _get(session, f"{NAVER}/stock/{code}/integration").json()
    time.sleep(PAUSE)
    ratios = {}
    for row in integ.get("totalInfos") or []:
        key = _TOTAL_KEYS.get(row.get("key"))
        if key:
            ratios[key] = _num(row.get("value"))
    cons = integ.get("consensusInfo") or {}
    flows = []
    for d in (integ.get("dealTrendInfos") or [])[:5]:
        flows.append({"d": f"{d['bizdate'][:4]}-{d['bizdate'][4:6]}-{d['bizdate'][6:]}", "close": _num(d.get("closePrice")),
                      "foreign": _num(d.get("foreignerPureBuyQuant")), "inst": _num(d.get("organPureBuyQuant")),
                      "retail": _num(d.get("individualPureBuyQuant")), "fratio": _num(d.get("foreignerHoldRatio"))})
    peers = [p["itemCode"] for p in (integ.get("industryCompareInfo") or []) if p.get("itemCode") and p["itemCode"] != code][:6]
    fin = {}
    try:
        f = _get(session, f"{NAVER}/stock/{code}/finance/annual").json()
        info = f.get("financeInfo") or {}
        cols = [c for c in info.get("trTitleList") or []]
        keys = [c["key"] for c in cols]
        rows = {}
        for r in info.get("rowList") or []:
            name = _FIN_ROWS.get(r.get("title"))
            if name:
                rows[name] = [_num((r.get("columns") or {}).get(k, {}).get("value")) for k in keys]
        if keys:
            fin = {"cols": [f"FY{k[:4]}" + ("E" if c.get("isConsensus") == "Y" else "") for k, c in zip(keys, cols)], "rows": rows}
    except StockDBError:
        fin = {}
    time.sleep(PAUSE)
    hist = {}
    try:
        chart = _get(session, CHART.format(code=code)).json()
        infos = (chart.get("priceInfos") or [])[-HISTORY_DAYS:]
        hist = {"d": [f"{p['localDate'][:4]}-{p['localDate'][4:6]}-{p['localDate'][6:]}" for p in infos],
                "c": [p.get("closePrice") for p in infos], "fr": [p.get("foreignRetentionRate") for p in infos]}
    except StockDBError:
        hist = {}
    time.sleep(PAUSE)
    return {"r": ratios, "c": {"rating": _num(cons.get("recommMean")), "target": _num(cons.get("priceTargetMean")),
                               "date": cons.get("createDate")} if cons else {},
            "flows": flows, "peers": peers, "fin": fin, "hist": hist}


def market_index(session: requests.Session) -> dict:
    out = {}
    for name in ("KOSPI", "KOSDAQ"):
        b = _get(session, f"{NAVER}/index/{name}/basic").json()
        chg = _num(b.get("compareToPreviousClosePrice")) or 0.0
        if (b.get("compareToPreviousPrice") or {}).get("name") in ("FALLING", "LOWER_LIMIT"):
            chg = -abs(chg)
        out[name] = {"close": _num(b.get("closePrice")), "chg": chg, "pct": _num(b.get("fluctuationsRatio")),
                     "date": str(b.get("localTradedAt") or "")[:10]}
        time.sleep(PAUSE)
    trend = _get(session, f"{NAVER}/index/KOSPI/trend").json()
    out["KOSPI"]["foreign_net_eok"] = _num(trend.get("foreignValue"))       # 억 원
    out["KOSPI"]["flow_date"] = trend.get("bizdate")
    return out


def usdkrw() -> dict | None:
    """원달러 — 우리 한국장 시세 파일(마지막 거래일)."""
    files = sorted((ROOT / "data").glob("price_kr_*.json"))
    if not files:
        return None
    macro = json.loads(files[-1].read_text(encoding="utf-8")).get("macro") or {}
    for entry in (macro.values() if isinstance(macro, dict) else macro):
        if isinstance(entry, dict) and "USD/KRW" in str(entry.get("name_en") or entry.get("ticker") or ""):
            return {"close": entry.get("price"), "pct": entry.get("change_pct"), "date": files[-1].stem[-10:]}
    return None


def skhy_premium(hynix_close: float | None, fx: float | None) -> dict | None:
    """SKHY(나스닥 ADR, 10주 = 원주 1주)와 서울 원주의 가격 차이. 받지 못하면 None — 칸을 비운다."""
    if not hynix_close or not fx:
        return None
    try:
        import yfinance as yf
        hist = yf.Ticker("SKHY").history(period="5d")
        if hist.empty:
            return None
        usd = float(hist["Close"].iloc[-1])
        return {"usd": round(usd, 2), "date": str(hist.index[-1].date()),
                "premium_pct": round((usd * 10 * fx / hynix_close - 1) * 100, 1)}
    except Exception as error:  # noqa: BLE001 — 칸 하나 때문에 전체를 멈추지 않는다. 이유는 찍는다
        print(f"[경고] SKHY 괴리율을 못 구했습니다: {error!r}")
        return None


# ── 메타(영문명·업종) ────────────────────────────────────────────────────────────────
def _curl_status(url: str) -> int:
    """curl로 연다(파이썬 SSL은 브라우저가 여는 옛 사이트의 핸드셰이크를 못 한다 — gabia.com, 2026-09-27). 못 열면 0."""
    import subprocess
    try:
        out = subprocess.run(["curl", "-sL", "-o", "/dev/null", "-m", "15", "-A", UA["User-Agent"], "-w", "%{http_code}", url],
                             capture_output=True, text=True, timeout=40).stdout.strip()
        return int(out or 0)
    except (subprocess.SubprocessError, ValueError):
        return 0


def web_alive(url: str) -> str | None:
    """회사 홈페이지가 사람에게 열리면 쓸 주소를, 아니면 None. http → https → 도메인 첫 화면 순서.
    403·401·429처럼 '봇이라 막음'은 산 것으로 본다(브라우저로는 열린다). 깊은 주소가 404인데 도메인이 살아 있으면 도메인으로 바꾼다."""
    bare = re.sub(r"^https?://", "", url.strip())
    root = bare.split("/")[0]
    candidates = [("http://" + bare, url), ("https://" + bare, "https://" + bare)]
    if root != bare.rstrip("/"):
        candidates += [("http://" + root, root), ("https://" + root, "https://" + root)]
    for probe, keep in candidates:
        code = _curl_status(probe)
        if 200 <= code < 400 or code in (401, 403, 405, 429, 999):
            return keep
    return None


def web_check(meta: dict, workers: int = 16) -> list[str]:
    """홈페이지 칸을 다시 확인해 닫힌 사이트는 비운다(web_dead에 원래 주소). 바깥 사이트라 동시에 연다."""
    import concurrent.futures as cf
    rows = [(c, v.get("web") or v.get("web_dead")) for c, v in meta.items() if v.get("web") or v.get("web_dead")]
    dead = []
    with cf.ThreadPoolExecutor(workers) as pool:
        for (code, url), alive in zip(rows, pool.map(lambda r: web_alive(r[1]), rows)):
            if alive:
                meta[code]["web"] = alive
                meta[code].pop("web_dead", None)
            else:
                meta[code]["web_dead"] = url
                meta[code]["web"] = ""
                dead.append(code)
    return dead


def build_meta(session: requests.Session, codes: list[str], existing: dict, key: str, max_company_calls: int = 4000) -> dict:
    """DART 영문명과 업종·설립·홈페이지. 이미 있는 종목은 건너뛴다(회사 개황은 잘 안 바뀐다)."""
    r = _get(session, f"{DART}/corpCode.xml", params={"crtfc_key": key})
    xml = zipfile.ZipFile(io.BytesIO(r.content)).read("CORPCODE.xml").decode("utf-8")
    dart = {}
    for item in re.findall(r"<list>(.*?)</list>", xml, re.S):
        stock = re.search(r"<stock_code>\s*(\w*)\s*</stock_code>", item).group(1)
        if stock:
            eng = re.search(r"<corp_eng_name>(.*?)</corp_eng_name>", item)
            dart[stock] = {"corp": re.search(r"<corp_code>(\d+)", item).group(1), "en": (eng.group(1).strip() if eng else "")}
    override = watchlist_names()
    meta = dict(existing)
    calls = 0
    for code in codes:
        row = meta.get(code) or {}
        src = dart.get(code) or dart.get(base_code(code))
        pref = code not in dart and base_code(code) in dart
        full = clean_name(src["en"]) if src and src["en"] else ""
        name = override.get(code) or (override.get(base_code(code)) and f"{override[base_code(code)]} (Pref.)") \
            or (short_name(full) + (" (Pref.)" if pref else "") if full else "")
        if row.get("name"):
            # 이미 이름이 있는 종목은 두다 — 다듬기 규칙은 `rename`으로만 다시 적용한다. 원문을 매번 다시 다듬으면
            # 규칙이 두 번 적용된 이름과 한 번 적용된 이름이 오가며 119개가 바뀌었다(2026-09-27 깃허브 첫 실행)
            row.setdefault("corp", (src or {}).get("corp"))
        else:
            row.update({"en": full, "name": name, "pref": pref, "corp": (src or {}).get("corp")})
        if src and "industry" not in row and calls < max_company_calls:
            info = _get(session, f"{DART}/company.json", params={"crtfc_key": key, "corp_code": src["corp"]}).json()
            calls += 1
            if info.get("status") == "000":
                ind = str(info.get("induty_code") or "")
                row.update({"industry": ("Holding company" if ind.startswith("6499") else KSIC.get(ind[:2], "")),
                            "ksic": ind, "founded": str(info.get("est_dt") or "")[:4],
                            "web": clean_web(str(info.get("hm_url") or ""))})
            time.sleep(0.12)
        meta[code] = row
    return meta


# ── 한 번 돌리기 ─────────────────────────────────────────────────────────────────────
def next_holiday(today: dt.date) -> dict | None:
    """오늘 이후 첫 휴장일. 목록이 끝나면 None — 칸을 비운다(지어내지 않는다)."""
    for day in sorted(KRX_HOLIDAYS):
        if day > today.isoformat():
            return {"date": day, "name": KRX_HOLIDAYS[day]}
    print("[경고] KRX_HOLIDAYS에 다음 휴장일이 없습니다 — 새해 휴장일을 더하십시오.")
    return None


def detail_targets(listing: list[dict], today: dt.date, all_: bool, top: int = DETAIL_TOP) -> list[str]:
    """상세를 새로 받을 종목 — 시가총액 상위 `top` + 나머지 가운데 오늘 차례(코드 순번 % 7 == 요일)."""
    if all_:
        return [r["code"] for r in listing]
    ranked = sorted(listing, key=lambda r: -(r["mcap"] or 0))
    head = [r["code"] for r in ranked[:top]]
    rest = sorted(r["code"] for r in ranked[top:])
    slot = today.toordinal() % ROTATE_DAYS
    return head + [c for i, c in enumerate(rest) if i % ROTATE_DAYS == slot]


def display_name(code: str, name_ko: str | None, meta: dict) -> str:
    """화면 이름. 우선주가 여럿인 회사(현대차우·현대차2우B)는 한국어 이름의 꼬리로 갈라 '(Pref. 2B)'처럼 적는다."""
    m = meta.get(code) or {}
    name = m.get("name") or code
    tail = re.search(r"(\d?)우([A-Z]?)(\(전환\))?$", name_ko or "")
    if m.get("pref") and tail and (tail.group(1) or tail.group(2)):
        name = name.replace("(Pref.)", f"(Pref. {tail.group(1)}{tail.group(2)})".replace("Pref. )", "Pref.)"))
    return name


def quote(row: dict) -> dict:
    return {k: row[k] for k in ("close", "chg", "pct", "volume", "value", "mcap", "date") if row.get(k) is not None}


def assemble(listing: list[dict], details: dict[str, dict], meta: dict) -> tuple[list[dict], list[list], dict]:
    """워드프레스로 보낼 것 — 종목별 항목(상세가 있으면 전체, 없으면 시세만), 목록, 시장 요약의 종목 부분."""
    items = []
    listed = {r["code"] for r in listing}
    for row in listing:
        m = meta.get(row["code"]) or {}
        data = {"code": row["code"], "market": row["market"], "name": display_name(row["code"], row.get("name_ko"), meta), "en": m.get("en", ""),
                "industry": m.get("industry", ""), "founded": m.get("founded", ""), "web": clean_web(m.get("web", "")),
                "pref": m.get("pref", False), "q": quote(row)}
        full = row["code"] in details
        if full:
            data.update(details[row["code"]])
            # 네이버 동종 업종에 ETF·목록 밖 종목이 섞여 온다 — 우리 페이지가 없는 코드로 링크하면 404(2026-09-27 전수 점검 9곳)
            data["peers"] = [{"code": p, "name": (meta.get(p) or {}).get("name") or p} for p in data.get("peers", []) if p in listed]
            data["detail_date"] = row.get("date")
        items.append({"code": row["code"], "merge": not full, "data": data})
    index = [[r["code"], display_name(r["code"], r.get("name_ko"), meta), r["market"], r.get("close"), r.get("pct"),
              r.get("mcap")] for r in sorted(listing, key=lambda r: -(r["mcap"] or 0))]
    return items, index, {}


def market_summary(listing: list[dict], details: dict[str, dict], meta: dict, idx: dict, fx: dict | None,
                   skhy: dict | None) -> dict:
    name = lambda c: (meta.get(c) or {}).get("name") or c  # noqa: E731
    stocks = [r for r in listing if r.get("trading") and r.get("close")]
    big = sorted(stocks, key=lambda r: -(r["mcap"] or 0))
    liquid = [r for r in stocks if (r.get("value") or 0) >= 5e9]      # 거래대금 50억 원 이상만 상승·하락 순위에(잡주 제외)
    gain = sorted(liquid, key=lambda r: -(r["pct"] or 0))[:5]
    lose = sorted(liquid, key=lambda r: (r["pct"] or 0))[:5]
    date = max((r["date"] for r in stocks if r.get("date")), default="")
    # 종목별 수급은 마감 직후엔 전날 줄까지만 나온다(네이버, 2026-09-26 실측) — 상세를 받은 종목들에서 가장 최근 날을 쓴다
    firsts = [(code, (d.get("flows") or [None])[0]) for code, d in details.items()]
    flow_date = max((f["d"] for _, f in firsts if f and f.get("d")), default="")
    flows = []
    for code, f in firsts:
        if f and f.get("d") == flow_date and f.get("foreign") is not None and f.get("close"):
            flows.append({"code": code, "name": name(code), "value": f["foreign"] * f["close"]})
    buys = sorted([f for f in flows if f["value"] > 0], key=lambda f: -f["value"])[:5]
    sells = sorted([f for f in flows if f["value"] < 0], key=lambda f: f["value"])[:5]
    # 하루 상한은 30% — 넘는 것은 상장 첫날(공모가 대비)뿐이다(2026-09-23 Wise Planet +280.83%). 틀린 숫자로 보이지 않게 표시한다
    pick = lambda r: {"code": r["code"], "name": name(r["code"]), "close": r["close"], "pct": r["pct"],  # noqa: E731
                      **({"ipo": True} if abs(r["pct"] or 0) > 30.5 else {})}
    return {"date": date, "index": idx, "usdkrw": fx, "skhy": skhy, "flow_universe": len(flows), "flow_date": flow_date,
            "largest": [pick(r) for r in big[:7]], "gainers": [pick(r) for r in gain], "losers": [pick(r) for r in lose],
            "foreign_buy": buys, "foreign_sell": sells, "counts": {"KOSPI": sum(r["market"] == "KOSPI" for r in listing),
                                                                  "KOSDAQ": sum(r["market"] == "KOSDAQ" for r in listing)}}


def hangul_problems(obj, path: str = "") -> list[str]:
    """영어 사이트에 나갈 값에 한글이 있으면 그 자리를 돌려준다(name_ko 칸만 예외 — 화면에 안 쓴다)."""
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k != "name_ko":
                out += hangul_problems(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += hangul_problems(v, f"{path}[{i}]")
    elif isinstance(obj, str) and re.search(r"[가-힣]", obj):
        out.append(f"{path}={obj[:30]}")
    return out


def batches(rows: list, limit: int = BATCH_BYTES) -> list[list]:
    """JSON 길이가 `limit`를 넘지 않게 자른다(한 항목이 한도보다 크면 그 항목만 한 묶음)."""
    out, cur, size = [], [], 0
    for row in rows:
        n = len(json.dumps(row, ensure_ascii=False).encode("utf-8")) + 1
        if cur and size + n > limit:
            out.append(cur)
            cur, size = [], 0
        cur.append(row)
        size += n
    if cur:
        out.append(cur)
    return out


def push(items: list[dict], index: list, market: dict, *, pause: float = 1.5) -> int:
    """종목 → 목록(나눠 보내고 서버가 다 받은 뒤 한 번에 바꾼다) → 시장 요약 → 캐시 비우기."""
    base = os.environ["WORDPRESS_URL"].rstrip("/")
    auth = (os.environ["WORDPRESS_USERNAME"], os.environ["WORDPRESS_APP_PASSWORD"])
    url = f"{base}/wp-json/fermata/v1/stocks"

    def post(body: dict, what: str) -> dict:
        last = ""
        for attempt in range(4):
            try:
                r = requests.post(url, json=body, auth=auth, headers=UA, timeout=90)
                if r.status_code == 200:
                    return r.json()
                last = f"HTTP {r.status_code} {r.text[:120]}"
            except requests.RequestException as error:
                last = repr(error)
            time.sleep(10 + attempt * 10)
        raise StockDBError(f"워드프레스 저장 실패({what}): {last}")

    sent = 0
    for chunk in batches(items):
        got = post({"items": chunk}, f"종목 {sent}~{sent + len(chunk)}")
        if got.get("saved") != len(chunk):
            raise StockDBError(f"종목 {len(chunk)}개를 보냈는데 {got.get('saved')}개만 저장됐습니다.")
        sent += len(chunk)
        time.sleep(pause)
    parts = batches(index)
    for n, part in enumerate(parts):
        got = post({"items": [], "index_part": part, "index_reset": n == 0, "index_total": len(index) if n == len(parts) - 1 else 0},
                   f"목록 {n + 1}/{len(parts)}")
        time.sleep(pause)
    if got.get("index") != len(index):
        raise StockDBError(f"목록 {len(index)}줄을 보냈는데 서버가 {got.get('index')}줄로 받았습니다 — 바꾸지 않았습니다.")
    post({"items": [], "market": market}, "시장 요약")
    # 홈·목록은 캐시된 화면이라 비워야 새 숫자가 보인다
    c = requests.post(f"{base}/wp-json/wp-super-cache/v1/cache", json={"delete_cache": True}, auth=auth, headers=UA, timeout=60)
    if c.status_code != 200:
        print(f"[경고] 캐시를 못 비웠습니다: HTTP {c.status_code} — 새 숫자가 늦게 보일 수 있습니다.")
    return sent


def run(*, detail_all: bool, do_push: bool, out: Path | None, limit: int | None = None) -> dict:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    session = requests.Session()
    session.headers.update(UA)
    listing = list_market(session, "KOSPI") + list_market(session, "KOSDAQ")
    if len(listing) < 2500:
        raise StockDBError(f"종목 목록이 {len(listing)}개뿐입니다 — 네이버가 막혔거나 화면이 바뀌었습니다.")
    if limit:
        listing = sorted(listing, key=lambda r: -(r["mcap"] or 0))[:limit]
    meta = json.loads(META.read_text(encoding="utf-8")) if META.exists() else {}
    missing = [r["code"] for r in listing if r["code"] not in meta]
    if missing:
        print(f"[안내] 메타에 없는 종목 {len(missing)}개 — 이름은 코드로 나갑니다. `python -m src.stock_db meta`로 채우십시오.")
    today = dt.date.today()
    targets = detail_targets(listing, today, detail_all)
    details, failed = {}, []
    for n, code in enumerate(targets, 1):
        try:
            details[code] = detail(session, code)
        except StockDBError as error:
            failed.append(code)
            print(f"[경고] {code} 상세 실패: {error}")
        if n % 200 == 0:
            print(f"  상세 {n}/{len(targets)} (실패 {len(failed)})", flush=True)
    if len(failed) > max(20, len(targets) * 0.1):
        raise StockDBError(f"상세 실패가 {len(failed)}/{len(targets)}건 — 네이버가 막혔을 수 있습니다. 올리지 않습니다.")
    idx = market_index(session)
    fx = usdkrw()
    hynix = next((r for r in listing if r["code"] == "000660"), None)
    skhy = skhy_premium(hynix and hynix["close"], fx and fx.get("close"))
    items, index, _ = assemble(listing, details, meta)
    market = market_summary(listing, details, meta, idx, fx, skhy)
    market["next_holiday"] = next_holiday(today)
    bad = hangul_problems({"items": [i["data"] for i in items], "index": index, "market": market})
    if bad:
        raise StockDBError(f"영어 페이지에 한글이 {len(bad)}곳 — 예: {bad[:5]}")
    report = {"stocks": len(listing), "detailed": len(details), "failed": failed, "date": market["date"]}
    if out:
        out.mkdir(parents=True, exist_ok=True)
        (out / "items.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        (out / "index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
        (out / "market.json").write_text(json.dumps(market, ensure_ascii=False, indent=1), encoding="utf-8")
    if do_push:
        report["pushed"] = push(items, index, market)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("command", choices=["meta", "rename", "webcheck", "run"])
    ap.add_argument("--detail-all", action="store_true")
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--limit", type=int, help="시가총액 상위 N종목만(점검용)")
    a = ap.parse_args(argv)
    if a.command == "webcheck":
        meta = json.loads(META.read_text(encoding="utf-8"))
        dead = web_check(meta)
        META.write_text(json.dumps(meta, ensure_ascii=False, indent=0, sort_keys=True) + "\n", encoding="utf-8")
        print(f"홈페이지 {sum(1 for v in meta.values() if v.get('web')) + len(dead)}개 확인 — 닫힌 {len(dead)}개를 비움")
        return 0
    if a.command == "rename":
        meta = json.loads(META.read_text(encoding="utf-8"))
        override = watchlist_names()
        for code, row in meta.items():
            if row.get("en"):
                row["en"] = clean_name(row["en"])
                own = override.get(code) or (override.get(base_code(code)) and f"{override[base_code(code)]} (Pref.)")
                row["name"] = own or short_name(row["en"]) + (" (Pref.)" if row.get("pref") else "")
            if "web" in row:
                row["web"] = clean_web(row["web"])
        META.write_text(json.dumps(meta, ensure_ascii=False, indent=0, sort_keys=True) + "\n", encoding="utf-8")
        print(f"이름 {len(meta)}개 다시 지음")
        return 0
    if a.command == "meta":
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
        key = os.environ.get("DART_API_KEY")
        if not key:
            raise SystemExit("DART_API_KEY가 없습니다 — .env에 넣으십시오.")
        session = requests.Session()
        session.headers.update(UA)
        listing = list_market(session, "KOSPI") + list_market(session, "KOSDAQ")
        existing = json.loads(META.read_text(encoding="utf-8")) if META.exists() else {}
        meta = build_meta(session, [r["code"] for r in listing], existing, key)
        META.write_text(json.dumps(meta, ensure_ascii=False, indent=0, sort_keys=True) + "\n", encoding="utf-8")
        named = sum(1 for v in meta.values() if v.get("name"))
        print(f"메타 {len(meta)}종목 저장 — 영문 이름 {named}, 업종 {sum(1 for v in meta.values() if v.get('industry'))}")
        return 0
    report = run(detail_all=a.detail_all, do_push=a.push, out=a.out, limit=a.limit)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
