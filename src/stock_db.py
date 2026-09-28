"""본진 한국 종목 데이터베이스 — 코스피·코스닥 전 종목을 영어 데이터 페이지로 (2026-09-27).

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
    # 2027은 계산값(python-holidays 0.105 — 2026년은 위 표와 전부 일치했다)에 근로자의 날·연말 폐장일을 더한 것이다.
    # 거래소가 12월에 내는 휴장일 공고와 대조할 것 — 특히 노동절·제헌절 대체휴일(5/3·7/19)과 임시공휴일.
    "2027-01-01": "New Year's Day", "2027-02-08": "Lunar New Year", "2027-02-09": "Lunar New Year (observed)",
    "2027-03-01": "Independence Movement Day", "2027-05-03": "Labor Day (observed)", "2027-05-05": "Children's Day",
    "2027-05-13": "Buddha's Birthday", "2027-07-19": "Constitution Day (observed)", "2027-08-16": "Liberation Day (observed)",
    "2027-09-14": "Chuseok", "2027-09-15": "Chuseok", "2027-09-16": "Chuseok", "2027-10-04": "National Foundation Day (observed)",
    "2027-10-11": "Hangul Day (observed)", "2027-12-27": "Christmas Day (observed)", "2027-12-31": "Year-end closing",
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
    # 2026-09-28 소개 작성 중 발견: DART 영문명이 낱말이 붙거나(Hanilcement) 법인 꼬리가 남거나(Innoxcorporation) 기호가 끼었다
    "023450": "Dongnam Chemical", "003070": "Kolon Global", "036200": "Union Semiconductor Equipment", "058970": "EMRO",
    "053300": "Korea Information Certificate Authority", "049950": "meerecompany", "199800": "ToolGen", "317690": "QuantaMatrix",
    "039440": "Systems Technology", "075180": "Saeron Automotive", "080160": "Modetour Network", "088390": "Innox",
    "064550": "Bioneer", "064480": "Bridgetec", "025770": "Korea Information & Communication", "025950": "Dongshin Engineering & Construction",
    "060540": "System and Application Technologies", "043910": "Nature and Environment", "101160": "Worldex Industry & Trading", "001290": "Sangsangin Investment & Securities",
    "091580": "Sangsin Energy Display Precision", "085670": "Newflex Technology", "006880": "Singsong Holdings", "051780": "Curo Holdings",
    "092300": "Hyunwoo Industrial", "081580": "Sungwoo Electronics", "100700": "Sewoon Medical", "099390": "Brainz Company",
    "068050": "Pan Entertainment", "124500": "Itcen Global", "300720": "Hanil Cement", "023000": "Samwon Steel",
    "362320": "Chungdam Global", "393210": "Tomato System", "398120": "SG Healthcare", "225430": "KM Pharmaceutical",
    "208350": "Jiran Security", "200780": "BC World Pharm", "388720": "Yuil Robotics", "389650": "Next Biomedical",
    "459510": "Nau Robotics", "476040": "Organoid Sciences", "005710": "Daewon Sanup", "000430": "Daewon Kang Up",
    "001420": "Taewon Mulsan", "024940": "PN Poongnyun", "005420": "Cosmo Chemical", "016380": "KG Dongbu Steel",
    "037710": "Gwangju Shinsegae",
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
    fund = re.compile(r"X클래스|클래스$")      # 'X클래스'는 회사가 아니라 펀드 상품(0106J0 대신 KOSPI200인덱스 X클래스) — 2026-09-27
    while True:
        data = _get(session, f"{NAVER}/stocks/marketValue/{market}", params={"page": page, "pageSize": 100}).json()
        stocks = data.get("stocks") or []
        for s in stocks:
            if s.get("stockEndType") != "stock" or fund.search(s.get("stockName") or ""):
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


SKHY_RATIO = 10          # SKHY ADR 1주 = SK하이닉스 보통주 10분의 1주(영어 가이드 korean-adrs-for-us-investors의 출처)
SKHY_START = "2026-07-10"   # 나스닥 첫 거래일(야후 이력의 첫 날)


def build_skhy(session: requests.Session) -> dict | None:
    """SKHY(나스닥)와 서울 원주의 가격 차이를 **같은 날짜끼리** 짝지어 상장일부터 늘어놓는다 (2026-09-28).

    프리미엄 = SKHY 종가 × 10 × 그날 원달러 ÷ 그날 서울 종가 − 1. 서울은 종목 페이지와 같은 네이버 일봉 종가, 환율은 야후
    KRW=X 일봉(SKHY 종가와 같은 날). 서울이 쉰 날·나스닥이 쉰 날은 짝이 없어 빠진다. 받지 못하면 None — 페이지와 홈 칸을 비운다."""
    try:
        import yfinance as yf
        usd = {str(i.date()): float(v) for i, v in yf.Ticker("SKHY").history(period="1y")["Close"].items()}
        fxs = {str(i.date()): float(v) for i, v in yf.Ticker("KRW=X").history(period="1y")["Close"].items()}
        start = SKHY_START.replace("-", "")
        rows = _get(session, f"https://api.stock.naver.com/chart/domestic/item/000660/day?startDateTime={start}0000"
                             f"&endDateTime={dt.date.today():%Y%m%d}2359").json()
        seoul = {f"{r['localDate'][:4]}-{r['localDate'][4:6]}-{r['localDate'][6:]}": float(r["closePrice"]) for r in rows}
    except Exception as error:  # noqa: BLE001 — 페이지 하나 때문에 전체를 멈추지 않는다. 이유는 찍는다
        print(f"[경고] SKHY 괴리율 이력을 못 구했습니다: {error!r}")
        return None
    out = []
    for day in sorted(set(usd) & set(seoul)):
        if day < SKHY_START or day not in fxs:
            continue
        per_adr = seoul[day] / SKHY_RATIO / fxs[day]              # 서울 1주를 ADR 한 주 크기의 달러로
        out.append({"d": day, "usd": round(usd[day], 2), "krw": seoul[day], "fx": round(fxs[day], 2),
                    "seoul_usd": round(per_adr, 2), "prem": round((usd[day] / per_adr - 1) * 100, 2)})
    if len(out) < 5:
        print(f"[경고] SKHY 짝이 {len(out)}일뿐입니다 — 페이지를 올리지 않습니다.")
        return None
    prems = [r["prem"] for r in out]
    hi = max(out, key=lambda r: r["prem"]); lo = min(out, key=lambda r: r["prem"])
    return {"date": out[-1]["d"], "ratio": SKHY_RATIO, "rows": out, "avg": round(sum(prems) / len(prems), 2),
            "high": {"d": hi["d"], "prem": hi["prem"]}, "low": {"d": lo["d"], "prem": lo["prem"]}, "days": len(out)}


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


# ── 배당(DART 공시) ─────────────────────────────────────────────────────────────────
# 순위표의 배당은 네이버 값이 아니라 DART 사업보고서 '배당에 관한 사항'(alotMatter)의 보통주 주당 현금배당금이다(2026-09-28).
# 연 1회 결산은 최근 사업연도 값, 반기 결산(리츠 등)은 최근 두 번을 더한 1년치.
# 공시로 확인되지 않는 배당은 순위표에 넣지 않는다.
DIVIDENDS = ROOT / "data" / "stock_dividends.json"


def _alot(session: requests.Session, key: str, corp: str, year: int) -> list[dict]:
    r = _get(session, f"{DART}/alotMatter.json", params={"crtfc_key": key, "corp_code": corp, "bsns_year": str(year), "reprt_code": "11011"})
    j = r.json()
    return j.get("list", []) if j.get("status") == "000" else []


def parse_dividends(rows: list[dict]) -> dict | None:
    """alotMatter 줄들 → {'end': 결산일, 'ttm': 최근 1년 주당배당금, 'prev': 그 전 1년, 'payout': 배당성향, 'periods': 1|2}. 없으면 None."""
    per: dict[str, dict] = {}
    for it in rows:
        end, se, knd = it.get("stlm_dt") or "", it.get("se") or "", it.get("stock_knd") or ""
        p = per.setdefault(end, {})
        if "주당 현금배당금" in se and knd == "보통주":
            p["dps"] = [_num(it.get(k)) for k in ("thstrm", "frmtrm", "lwfr")]
        elif "현금배당성향" in se and "payout" not in p:
            p["payout"] = _num(it.get("thstrm"))
    ends = sorted(e for e, p in per.items() if p.get("dps") and p["dps"][0] is not None)
    if not ends:
        return None
    last = per[ends[-1]]
    # 최근 1년 안의 결산을 모두 더한다 — 연 1회·반기(리츠)·분기(SK리츠) 모두 같은 식(2026-09-28: 분기 리츠가 절반만 잡혔다)
    latest = dt.date.fromisoformat(ends[-1])
    window = [e for e in ends if (latest - dt.date.fromisoformat(e)).days < 360]
    ttm = sum(per[e]["dps"][0] or 0 for e in window)
    prevs = [per[e]["dps"][1] for e in window]
    prev = sum(prevs) if all(v is not None for v in prevs) else None
    periods = len(window)
    return {"end": ends[-1], "ttm": ttm, "prev": prev, "payout": last.get("payout"), "periods": periods}


def fetch_dividends(session: requests.Session, key: str, meta: dict, codes: list[str], today: dt.date) -> dict:
    """전 종목 배당 공시. 12월 결산이면 작년 사업보고서 하나, 아니면(리츠 등) 올해 것도 받는다. 우선주는 보통주 회사 공시를 쓴다."""
    out, errors = {}, 0
    for n, code in enumerate(codes, 1):
        corp = (meta.get(code) or {}).get("corp")
        if not corp or (meta.get(code) or {}).get("pref"):
            continue
        try:
            rows = _alot(session, key, corp, today.year - 1)
            ends = {r.get("stlm_dt") for r in rows}
            if not rows or any(e and not e.endswith("-12-31") for e in ends):
                rows += _alot(session, key, corp, today.year)
            got = parse_dividends(rows)
            if got:
                out[code] = got
        except StockDBError:
            errors += 1
        time.sleep(0.1)
        if n % 300 == 0:
            print(f"  배당 공시 {n}/{len(codes)} (있음 {len(out)}, 실패 {errors})", flush=True)
    if errors > max(30, len(codes) * 0.05):
        raise StockDBError(f"배당 공시 실패가 {errors}건 — DART가 막혔을 수 있습니다.")
    return out


# ── 순위표(/stocks/lists/…) ──────────────────────────────────────────────────────────
# 2026-09-28. 매일 상세를 새로 받는 종목은 650개뿐이라, 전 종목 순위에 필요한 지표는
# data/stock_metrics.json에 이어 쓴다(상세를 받은 종목만 그날 값으로 바뀐다). 순위표마다 50위까지.
METRICS = ROOT / "data" / "stock_metrics.json"
LIST_SIZE = 50


def metrics_from_detail(d: dict) -> dict:
    """상세 한 종목 → 순위에 쓰는 지표. 외국인 지분은 실제 지분율(차트 이력) — 외인소진율은 한도 대비라 따로 둔다."""
    r = d.get("r") or {}
    fr = [x for x in ((d.get("hist") or {}).get("fr") or []) if isinstance(x, (int, float))]
    own = fr[-1] if fr else ((d.get("flows") or [{}])[0].get("fratio"))
    roe = None
    fin = d.get("fin") or {}
    cols, roes = fin.get("cols") or [], ((fin.get("rows") or {}).get("roe") or [])
    for col, v in reversed(list(zip(cols, roes))):
        if not col.endswith("E") and v is not None:
            roe = v
            break
    return {"pbr": r.get("pbr"), "per": r.get("per"), "fown": own, "fused": r.get("foreign_ratio"), "roe": roe, "dps_nv": r.get("dps")}


def update_metrics(metrics: dict, details: dict[str, dict], date: str) -> dict:
    for code, d in details.items():
        metrics[code] = {**metrics_from_detail(d), "d": date}
    return metrics


def _is_reit(name: str, industry: str) -> bool:
    return "reit" in name.lower() or "infrastructure fund" in name.lower()


def build_lists(listing: list[dict], metrics: dict, dividends: dict, meta: dict, date: str) -> dict:
    """순위표 넷. 우선주는 뺀다(보통주와 같은 회사). 행에는 화면에 그릴 값만 싣는다."""
    name = lambda c: (meta.get(c) or {}).get("name") or c            # noqa: E731
    ind = lambda c: (meta.get(c) or {}).get("industry") or ""       # noqa: E731
    base = [r for r in listing if r.get("close") and r.get("mcap") and not (meta.get(r["code"]) or {}).get("pref")]
    row = lambda r, **kw: {"code": r["code"], "name": name(r["code"]), "market": r["market"], "industry": ind(r["code"]),  # noqa: E731
                           "close": r["close"], "pct": r.get("pct"), "mcap": r["mcap"], **kw}
    out = {}
    divs, doubtful = [], []
    for r in base:
        dv = dividends.get(r["code"])
        if r["mcap"] < 1e11 or not dv or not dv.get("ttm"):
            continue
        # 공시 주당배당금은 결산 뒤 액면분할을 반영하지 않고(미원화학 4,500 vs 450), 가끔 총액이 잘못 들어간다(Y-entec 18억 원).
        # 네이버 값(분할 반영)과 15% 안으로 맞을 때만 싣는다. 네이버 값이 없으면(리츠 등) 공시값으로 — 주가보다 크면 오류로 뺀다.
        nv = (metrics.get(r["code"]) or {}).get("dps_nv")
        if dv["ttm"] >= r["close"] or (nv and abs(dv["ttm"] / nv - 1) > 0.15):
            doubtful.append({"code": r["code"], "dart": dv["ttm"], "naver": nv})
            continue
        flags = []
        if dv.get("prev") and dv["ttm"] >= 2 * dv["prev"]:
            flags.append(f"Dividend {dv['ttm'] / dv['prev']:.1f}× the year before")
        p = dv.get("payout")
        if p is not None and p < 0:
            flags.append("Paid out despite a loss")
        elif p is not None and p > 100:
            flags.append(f"Paid out {p:.0f}% of earnings")
        m = metrics.get(r["code"]) or {}
        divs.append(row(r, yld=round(dv["ttm"] / r["close"] * 100, 2), dps=dv["ttm"], prev=dv.get("prev"), end=dv.get("end"),
                        npay=dv.get("periods") or 1, reit=_is_reit(name(r["code"]), ind(r["code"])), flags=flags, fown=m.get("fown")))
    out["highest-dividend-yield"] = {
        "title": "Korean Stocks With the Highest Dividend Yield", "short": "Highest dividend yield",
        "blurb": "Top payers worth ₩100B+, with the yield and dividend per share",
        "lead": "KOSPI and KOSDAQ companies worth at least ₩100 billion, ranked by trailing dividend yield: the cash dividend per common share "
                "reported in each company's latest annual filing (DART), divided by the latest closing price. Companies that pay more than once a year (mostly REITs) use every payout "
                "from the latest 12 months. Only dividends that match across two sources (the filing and Naver Finance) are listed.",
        "count": len(divs), "rows": sorted(divs, key=lambda x: -x["yld"])[:LIST_SIZE], "doubtful": doubtful}
    fo = [row(r, fown=round((metrics.get(r["code"]) or {})["fown"], 2), fused=(metrics.get(r["code"]) or {}).get("fused"))
          for r in base if r["mcap"] >= 1e11 and (metrics.get(r["code"]) or {}).get("fown") is not None]
    out["most-foreign-owned"] = {
        "title": "Most Foreign-Owned Korean Stocks", "short": "Most foreign-owned",
        "blurb": "Where overseas investors hold the biggest share",
        "lead": "Share of each company's stock held by overseas investors, for KOSPI and KOSDAQ companies worth at least ₩100 billion. "
                "Some sectors cap foreign ownership by law (telecoms, utilities, airlines, media); for those, the share of the cap already used is shown.",
        "count": len(fo), "rows": sorted(fo, key=lambda x: -x["fown"])[:LIST_SIZE]}
    pb = [row(r, pbr=(metrics.get(r["code"]) or {})["pbr"], per=(metrics.get(r["code"]) or {}).get("per"), roe=(metrics.get(r["code"]) or {}).get("roe"))
          for r in base if r["mcap"] >= 5e11 and ((metrics.get(r["code"]) or {}).get("pbr") or 0) > 0]
    out["cheapest-by-pb"] = {
        "title": "Korean Stocks Trading Furthest Below Book Value", "short": "Cheapest by P/B",
        "blurb": "Lowest price-to-book ratios — the Value-Up question",
        "lead": "Companies worth at least ₩500 billion with the lowest price-to-book ratios. A P/B under 1 means the market values the company below "
                "its net assets — the gap Korea's Value-Up program is trying to close. Return on equity is from the latest annual results.",
        "count": len(pb), "rows": sorted(pb, key=lambda x: x["pbr"])[:LIST_SIZE]}
    kq = [row(r) for r in base if r["market"] == "KOSDAQ"]
    out["largest-kosdaq"] = {
        "title": "Largest KOSDAQ Companies by Market Cap", "short": "Largest KOSDAQ companies",
        "blurb": "Korea's growth board, ranked by market cap",
        "lead": "The biggest companies on the KOSDAQ, Korea's growth and technology board, ranked by market capitalization at the latest close.",
        "count": len(kq), "rows": sorted(kq, key=lambda x: -x["mcap"])[:LIST_SIZE]}
    for v in out.values():
        v["date"] = date
    return out


# ── 회사 소개(About) ────────────────────────────────────────────────────────────────
# 2026-09-28. 종목 페이지 About 칸의 영어 소개 두세 문장. 근거는 데이터 제공처의 한국어 기업개요(기준일 asof)이고 문장은 새로 쓴다
# (옮겨 쓰지 않는다) — 규칙은 output/about/WRITING_RULES.md, 근거 원문은 저장소에 넣지 않는다. 사람이 쓴 것을 about_issues가 기계로
# 본다: 한글, 길이, 근거에 없는 숫자(지어낸 연도·비율), 표시 이름으로 시작. 새 상장 종목은 소개가 없으면 예전 한 줄 그대로 나간다.
ABOUT = ROOT / "data" / "stock_about.json"
ABOUT_DATA: dict = json.loads(ABOUT.read_text(encoding="utf-8")) if ABOUT.exists() else {}
_HANGUL = re.compile(r"[\uac00-\ud7a3\u3131-\u318e]")
_NUM = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?")


def about_issues(text: str, name: str, source: str) -> list[str]:
    out = []
    if _HANGUL.search(text):
        out.append("한글")
    if not 120 <= len(text) <= 650:
        out.append(f"길이 {len(text)}")
    if not text.startswith(name):
        out.append("표시 이름으로 시작하지 않음")
    have = {n.replace(",", "") for n in _NUM.findall(source)}
    # 만·억·조가 붙은 숫자는 영어로 옮기면 자릿수가 바뀐다(920만 → 9.2 million) — 그대로 쓰면 틀린 숫자다(2026-09-28 작성 중 실제로 나왔다)
    # 조는 trillion과 자릿수가 같아 그대로 써도 맞다. 같은 숫자가 단위 없이도 나오면(계열사 15개·15억 불) 넘긴다
    korean_unit = {m.replace(",", "") for m in re.findall(r"(\d[\d,.]*)\s*(?:만|억)", source)}
    korean_unit -= {m.replace(",", "") for m in re.findall(r"(\d[\d,.]*)(?!\s*(?:만|억|[\d,.]))", source)}
    for n in _NUM.findall(text.replace(name, " ")):      # 이름 속 숫자(Y2 Solution·S-1)는 숫자가 아니다
        if n.replace(",", "") not in have:
            out.append(f"근거에 없는 숫자 {n}")
        elif n.replace(",", "") in korean_unit:
            out.append(f"한국어 단위(만·억·조) 숫자 {n} — 빼십시오")
    return out


def about_text(code: str, meta: dict, about: dict) -> str | None:
    """종목의 소개. 우선주는 보통주 소개에 한 문장을 붙인다(보통주 코드는 끝자리 0)."""
    m = meta.get(code) or {}
    if m.get("pref"):
        base = (about.get(code[:5] + "0") or {}).get("text")
        common = (meta.get(code[:5] + "0") or {}).get("name")
        return f"{base} These are its preferred shares, which usually carry no voting rights and trade separately from the common stock." if base and common else None
    return (about.get(code) or {}).get("text")


# ── 외국인 수급 페이지(/stocks/foreign-flows/) ────────────────────────────────────────
# 2026-09-28. 종목별 수급은 다음 날 아침에 확정되므로 가장 최근 수급 날짜 기준으로 만든다(07:50 실행이 어제로).
# 순위는 상세를 매일 받는 시가총액 상위 300종목(시가총액의 약 94%) 안에서. 하루 합계는 data/foreign_history.json에 쌓아 20일 그래프를 그린다.
FOREIGN_HISTORY = ROOT / "data" / "foreign_history.json"
FLOW_TOP = 20


def build_flows(listing: list[dict], details: dict[str, dict], meta: dict, idx: dict, history: dict) -> dict | None:
    name = lambda c: (meta.get(c) or {}).get("name") or c                  # noqa: E731
    top = [r["code"] for r in sorted(listing, key=lambda r: -(r.get("mcap") or 0))[:DETAIL_TOP]]
    firsts = {c: (details.get(c) or {}).get("flows") or [] for c in top}
    day = max((f[0]["d"] for f in firsts.values() if f and f[0].get("d")), default="")
    if not day:
        return None
    rows, streak, change = [], [], []
    by_code = {r["code"]: r for r in listing}
    for c in top:
        fl = firsts[c]
        if fl and fl[0].get("d") == day and fl[0].get("foreign") is not None and fl[0].get("close"):
            f0 = fl[0]
            # 등락률은 종목 페이지와 같은 목록 값만 — 네이버의 종가와 '전일 대비'는 기준이 다른 날이 있어(9/22 종가 277,500인데
            # 9/23 전일 대비는 276,500 기준) 종가끼리 나누면 종목 페이지와 어긋난다. 원인은 확인하지 못했다. 날짜가 다르면 비운다
            pct = by_code[c].get("pct") if by_code.get(c, {}).get("date") == day else None
            rows.append({"code": c, "name": name(c), "val": f0["foreign"] * f0["close"], "sh": f0["foreign"], "pct": pct, "own": f0.get("fratio")})
        if len(fl) == 5 and fl[0].get("d") == day and all((f.get("foreign") or 0) > 0 and f.get("close") for f in fl):
            streak.append({"code": c, "name": name(c), "val": sum(f["foreign"] * f["close"] for f in fl),
                           "from": fl[-1].get("fratio"), "to": fl[0].get("fratio"), "since": fl[-1]["d"]})
        hist = (details.get(c) or {}).get("hist") or {}
        fr = [(d, x) for d, x in zip(hist.get("d") or [], hist.get("fr") or []) if isinstance(x, (int, float))]
        if len(fr) > 60 and not (meta.get(c) or {}).get("pref"):
            change.append({"code": c, "name": name(c), "industry": (meta.get(c) or {}).get("industry", ""),
                           "from": fr[0][1], "to": fr[-1][1], "diff": round(fr[-1][1] - fr[0][1], 2), "since": fr[0][0]})
    buys = [r for r in rows if r["val"] > 0]
    sells = [r for r in rows if r["val"] < 0]
    # 지수 수급(시장 전체)은 그날 저녁에, 종목 수급은 다음 날 아침에 나온다 — 날짜별로 따로 적고 합친다(한쪽 실행이 다른 쪽 값을 지우지 않게)
    kospi = (idx.get("KOSPI") or {})
    fd = str(kospi.get("flow_date") or "")
    if len(fd) == 8 and kospi.get("foreign_net_eok") is not None:
        history.setdefault(f"{fd[:4]}-{fd[4:6]}-{fd[6:]}", {})["kospi_eok"] = kospi["foreign_net_eok"]
    history.setdefault(day, {}).update({"buy": sum(r["val"] for r in buys), "sell": sum(r["val"] for r in sells)})
    kospi_net = history[day].get("kospi_eok")
    series = [{"d": d, "kospi_eok": history[d]["kospi_eok"]} for d in sorted(history) if d <= day and history[d].get("kospi_eok") is not None][-20:]
    return {"date": day, "kospi_eok": kospi_net, "universe": len(top), "covered": len(rows),
            "buy_total": sum(r["val"] for r in buys), "sell_total": sum(r["val"] for r in sells), "n_buy": len(buys), "n_sell": len(sells),
            "buy": sorted(buys, key=lambda r: -r["val"])[:FLOW_TOP], "sell": sorted(sells, key=lambda r: r["val"])[:FLOW_TOP],
            "streak": sorted(streak, key=lambda r: -r["val"]),
            "up": sorted(change, key=lambda r: -r["diff"])[:10], "down": sorted(change, key=lambda r: r["diff"])[:10],
            "since": min((x["since"] for x in change), default=""), "series": series}


# ── 한 번 돌리기 ─────────────────────────────────────────────────────────────────────
def next_holiday(today: dt.date) -> dict | None:
    """오늘 이후 첫 휴장일. 목록이 끝나면 None — 칸을 비운다(지어내지 않는다)."""
    for day in sorted(KRX_HOLIDAYS):
        if day > today.isoformat():
            return {"date": day, "name": KRX_HOLIDAYS[day]}
    print("[경고] KRX_HOLIDAYS에 다음 휴장일이 없습니다 — 새해 휴장일을 더하십시오.")
    return None


KST = dt.timezone(dt.timedelta(hours=9))


def in_krx_session(now: dt.datetime | None = None) -> bool:
    """평일 09:00~15:30(한국 시각)이면 True — 장중에 받으면 장중 가격이 '종가'로 올라간다."""
    now = (now or dt.datetime.now(KST)).astimezone(KST)
    return now.weekday() < 5 and dt.time(9, 0) <= now.time() < dt.time(15, 30)


def list_all(session: requests.Session, expected: int, tries: int = 3, wait: int = 120) -> list[dict]:
    """코스피·코스닥 전 종목. 어제 목록보다 3% 넘게 적으면 기다렸다 다시 받는다 — 2026-09-28 08:48 실행이 2,490개만 받았다
    (정상 2,763). 같은 종목이 두 번 잡히면(쪽 사이에 순위가 바뀌면 생긴다) 하나로 합친다."""
    need = max(2500, int(expected * 0.97))
    rows: list[dict] = []
    for attempt in range(1, tries + 1):
        got = list_market(session, "KOSPI") + list_market(session, "KOSDAQ")
        rows = list({r["code"]: r for r in got}.values())
        if len(rows) >= need:
            return rows
        print(f"[안내] 종목 목록 {len(rows)}개 — 기대 {need}개 이상, {attempt}/{tries}번째. {wait}초 뒤 다시 받습니다.", flush=True)
        if attempt < tries:
            time.sleep(wait)
    raise StockDBError(f"종목 목록이 {len(rows)}개뿐입니다(기대 {need}개 이상) — 네이버가 막혔거나 목록을 채우는 중입니다.")


def still_listed(session: requests.Session, code: str) -> bool:
    """목록에서 빠진 종목이 정말 없어졌는지 네이버에 하나씩 묻는다. 조회되면 지우지 않는다(2026-09-28: 목록에서 빠진 6종목이 모두
    정상 거래 중이었다 — 쪽을 넘기는 사이 순위가 바뀌어 빠진 것). 물어보다 실패해도 지우지 않는 쪽으로 판단한다."""
    try:
        r = session.get(f"{NAVER}/stock/{code}/basic", timeout=20)
    except requests.RequestException:
        return True
    if r.status_code != 200:
        return r.status_code >= 500          # 서버 오류는 '모름' — 지우지 않는다. 404 등은 없어진 것으로 본다
    try:
        return bool(r.json().get("stockName"))
    except ValueError:
        return True


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
            text = about_text(row["code"], meta, ABOUT_DATA)
            if text:     # 상세 항목은 통째로 바뀌므로 소개를 같이 싣는다(시세만 가는 항목은 워드프레스가 옛 값에 합친다)
                data["about"] = text
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
    # 정리매매(DA Technology 2026-09-23 −96.68%)도 30%를 넘는다 — 이력이 하루뿐일 때만 상장 첫날로 본다
    def pick(r):
        out = {"code": r["code"], "name": name(r["code"]), "close": r["close"], "pct": r["pct"]}
        if abs(r["pct"] or 0) > 30.5:
            days = len(((details.get(r["code"]) or {}).get("hist") or {}).get("c") or [])
            out["ipo" if days <= 1 else "nolimit"] = True
        return out
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


def push(items: list[dict], index: list, market: dict, lists: dict | None = None, flows: dict | None = None,
         skhy: dict | None = None, *, pause: float = 1.5) -> int:
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
    # 어제 목록에 있었는데 오늘 없는 종목(상장폐지·펀드 제외)은 페이지를 지운다 — 남겨 두면 멈춘 숫자가 계속 보인다
    old = []
    try:
        old = requests.get(f"{base}/wp-json/fermata/v1/stock-index", headers=UA, timeout=60).json()
        gone = sorted({r[0] for r in old} - {i["code"] for i in items})
    except (requests.RequestException, ValueError) as error:
        print(f"[경고] 어제 목록을 못 받아 지울 종목을 못 셉니다: {error!r}")
        gone = []
    if len(gone) > 50:
        raise StockDBError(f"하루에 {len(gone)}종목이 사라졌습니다 — 목록 수집이 잘못됐을 수 있어 멈춥니다.")
    if gone:
        check = requests.Session()
        check.headers.update(UA)
        kept = [c for c in gone if still_listed(check, c)]
        if kept:
            print(f"[안내] 목록에서 빠졌지만 네이버에 아직 있는 종목은 지우지 않습니다: {kept}")
        gone = [c for c in gone if c not in kept]
    if gone:
        post({"items": [], "delete": gone}, f"페이지 지우기 {gone}")
        print(f"[안내] 목록에서 빠진 종목 페이지를 지웠습니다: {gone}")
    new = sorted({i["code"] for i in items} - {r[0] for r in old}) if old else []
    if (new or gone) and len(new) <= 50:
        from src import indexnow   # 새로 생기거나 사라진 종목 페이지를 빙에 알린다(2026-09-28)
        indexnow.submit([f"{base}/stocks/{c}/" for c in new + gone])
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
    if flows:
        post({"items": [], "flows": flows}, "외국인 수급")
    if skhy:
        post({"items": [], "skhy": skhy}, "SKHY 프리미엄")
    for slug, data in (lists or {}).items():          # 순위표는 하나씩(한 번에 보내면 50KB를 넘을 수 있다)
        post({"items": [], "list": {"slug": slug, "data": data}}, f"순위표 {slug}")
        time.sleep(pause)
    # 홈·목록은 캐시된 화면이라 비워야 새 숫자가 보인다
    c = requests.post(f"{base}/wp-json/wp-super-cache/v1/cache", json={"delete_cache": True}, auth=auth, headers=UA, timeout=60)
    if c.status_code != 200:
        print(f"[경고] 캐시를 못 비웠습니다: HTTP {c.status_code} — 새 숫자가 늦게 보일 수 있습니다.")
    return sent


def run(*, detail_all: bool, do_push: bool, out: Path | None, limit: int | None = None, force: bool = False) -> dict:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    if in_krx_session() and not force:
        raise StockDBError("지금은 한국장 장중입니다 — 장중 가격이 '종가'로 올라가므로 멈춥니다(굳이 돌리려면 --force).")
    session = requests.Session()
    session.headers.update(UA)
    try:
        expected = len(requests.get("https://fermata.it.kr/wp-json/fermata/v1/stock-index", headers=UA, timeout=60).json())
    except (requests.RequestException, ValueError):
        expected = 2500
    listing = list_all(session, expected)
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
    skhy_page = build_skhy(session) if not limit else None
    last = skhy_page["rows"][-1] if skhy_page else None     # 홈 칸도 페이지와 같은 날짜 짝으로
    skhy = {"usd": last["usd"], "date": last["d"], "premium_pct": round(last["prem"], 1)} if last else None
    items, index, _ = assemble(listing, details, meta)
    market = market_summary(listing, details, meta, idx, fx, skhy)
    metrics = json.loads(METRICS.read_text(encoding="utf-8")) if METRICS.exists() else {}
    date_now = max((r.get("date") or "" for r in listing), default="")
    metrics = update_metrics(metrics, details, date_now)
    dividends = (json.loads(DIVIDENDS.read_text(encoding="utf-8")).get("stocks") or {}) if DIVIDENDS.exists() else {}
    lists = build_lists(listing, metrics, dividends, meta, date_now) if not limit else {}
    fhist = json.loads(FOREIGN_HISTORY.read_text(encoding="utf-8")) if FOREIGN_HISTORY.exists() else {}
    flows_page = build_flows(listing, details, meta, idx, fhist) if not limit else None
    market["next_holiday"] = next_holiday(today)
    bad = hangul_problems({"items": [i["data"] for i in items], "index": index, "market": market, "lists": lists, "flows": flows_page, "skhy": skhy_page})
    if bad:
        raise StockDBError(f"영어 페이지에 한글이 {len(bad)}곳 — 예: {bad[:5]}")
    report = {"stocks": len(listing), "detailed": len(details), "failed": failed, "date": market["date"]}
    if out:
        out.mkdir(parents=True, exist_ok=True)
        (out / "items.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        (out / "index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
        (out / "market.json").write_text(json.dumps(market, ensure_ascii=False, indent=1), encoding="utf-8")
    if not limit:
        FOREIGN_HISTORY.write_text(json.dumps(fhist, ensure_ascii=False, indent=0, sort_keys=True) + "\n", encoding="utf-8")
        METRICS.write_text(json.dumps(metrics, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8")
    if out:
        (out / "lists.json").write_text(json.dumps(lists, ensure_ascii=False, indent=1), encoding="utf-8")
        (out / "flows.json").write_text(json.dumps(flows_page, ensure_ascii=False, indent=1), encoding="utf-8")
        (out / "skhy.json").write_text(json.dumps(skhy_page, ensure_ascii=False, indent=1), encoding="utf-8")
    if do_push:
        # 종목 수급은 다음 날 아침에 나온다 — 목록(등락률)과 날짜가 같은 아침 실행만 페이지를 바꾸고, 저녁 실행은 코스피 합계만 기록한다
        same_day = bool(flows_page) and all(r.get("date") == flows_page["date"] for r in listing if r["code"] in {x["code"] for x in flows_page["buy"] + flows_page["sell"]})
        report["flows"] = flows_page["date"] if same_day else None
        report["pushed"] = push(items, index, market, lists, flows_page if same_day else None, skhy_page)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("command", choices=["meta", "rename", "webcheck", "dividends", "run", "about-push"])
    ap.add_argument("--detail-all", action="store_true")
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--limit", type=int, help="시가총액 상위 N종목만(점검용)")
    ap.add_argument("--force", action="store_true", help="장중에도 돌린다(장중 가격이 종가로 올라가니 점검용으로만)")
    a = ap.parse_args(argv)
    if a.command == "dividends":
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
        key = os.environ.get("DART_API_KEY")
        if not key:
            raise SystemExit("DART_API_KEY가 없습니다.")
        session = requests.Session()
        session.headers.update(UA)
        meta = json.loads(META.read_text(encoding="utf-8"))
        codes = [r["code"] for r in list_all(session, 2500)] if not a.limit else sorted(meta)[: a.limit]
        divs = fetch_dividends(session, key, meta, codes, dt.date.today())
        DIVIDENDS.write_text(json.dumps({"fetched": dt.date.today().isoformat(), "stocks": divs}, ensure_ascii=False, indent=0, sort_keys=True) + "\n", encoding="utf-8")
        print(f"배당 공시 {len(divs)}종목 저장")
        return 0
    if a.command == "about-push":   # 소개를 새로 썼을 때 한 번 — 모든 종목 페이지에 about만 합쳐 넣는다(시세는 건드리지 않는다)
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
        meta = json.loads(META.read_text(encoding="utf-8"))
        rows = [{"code": c, "merge": True, "data": {"about": t}} for c in sorted(meta) if (t := about_text(c, meta, ABOUT_DATA))]
        bad = hangul_problems([r["data"] for r in rows])
        if bad:
            raise SystemExit(f"소개에 한글이 있습니다: {bad[:3]}")
        base = os.environ["WORDPRESS_URL"].rstrip("/")
        auth = (os.environ["WORDPRESS_USERNAME"], os.environ["WORDPRESS_APP_PASSWORD"])
        batch, size, sent = [], 0, 0
        for r in rows + [None]:
            n = len(json.dumps(r, ensure_ascii=False).encode()) if r else 0
            if batch and (r is None or size + n > 45_000):
                res = requests.post(f"{base}/wp-json/fermata/v1/stocks", json={"items": batch}, auth=auth, headers=UA, timeout=90)
                res.raise_for_status(); sent += res.json().get("saved", 0); batch, size = [], 0
                time.sleep(1.5)
            if r:
                batch.append(r); size += n
        requests.post(f"{base}/wp-json/wp-super-cache/v1/cache", json={"delete_cache": True}, auth=auth, headers=UA, timeout=60)
        print(f"소개 {sent}/{len(rows)}종목 저장")
        return 0 if sent == len(rows) else 1
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
    report = run(detail_all=a.detail_all, do_push=a.push, out=a.out, limit=a.limit, force=a.force)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
