"""본문의 인용·숫자가 출처의 실제 문장에서 왔는지 확인한다(2026-10-06, 감사: 잡지 9편 중 6편에서 출처에 없는 숫자·인용).

원고에 근거 표를 둔다 — `evidence: [{"claim": 본문 구절, "url": 출처 주소, "original": 출처 원문 문장(외국어 그대로)}]`.
관문이 본다:
1. 출처(`sources`)마다 주소가 있다(10/2 잡지 세 편은 출처 여덟 개 주소가 전부 비어 대조할 수 없었다).
2. 본문의 큰따옴표 인용(“…”/"…")과 숫자가 든 문장마다, 그 문장 안에 들어 있는 `claim`을 가진 근거가 있다.
3. 근거의 `url`은 출처 목록에 있고, `original`은 그 주소의 실제 페이지에 그대로 있다(관문이 직접 연다 — 못 열면 근거가 아니다).
번역 문장의 뜻이 원문과 맞는지까지는 기계가 보지 못한다 — 그래도 출처에 없는 숫자·말을 지어내는 것은 막는다.
"""
from __future__ import annotations

import html
import os
import re

import requests

_UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141 Safari/537.36",
       "Accept-Language": "en-US,en;q=0.9,ko;q=0.8"}
_CACHE: dict[str, str | None] = {}
_QUOTE = re.compile(r"[“\"]([^”\"]{8,})[”\"]")
_SENT_SPLIT = re.compile(r"(?<=[.!?。])\s+|\n+")
MIN_ORIGINAL = 20
_ATTRIBUTION = re.compile(r"\b(?:said|says|say|stated|states|according to|wrote|writes|told|tells|warned|promised|noted|added|argued|"
                          r"puts|reads|announced|explained)\b|말했|밝혔|전했|설명했|강조했|덧붙였|경고했|썼|라고|이라고|고 말|며 |면서", re.I)


def normalize(text: str) -> str:
    text = html.unescape(text)
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace(" ", " ")
    text = re.sub(r"[​-‍﻿]", "", text)
    return re.sub(r"\s+", " ", text).strip().lower()


_CHALLENGE = re.compile(r"just a moment|checking your browser|enable javascript and cookies|attention required", re.I)


def _browser_text(url: str) -> str | None:
    """진짜 크롬(창 없음)으로 연 본문 — 봇 검사(Cloudflare 등)가 프로그램 요청만 막는 사이트용(2026-10-11: theprint·teslaoracle은 열리고
    autoevolution은 크롬도 막는다). 이 맥의 게시 직전 검사에서만 쓴다(EVIDENCE_BROWSER=1). 못 열면 None."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, channel="chrome", args=["--disable-blink-features=AutomationControlled"])
            page = browser.new_context(user_agent=_UA["User-Agent"], locale="en-US").new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=40000)
            page.wait_for_timeout(6000)
            title, body = page.title(), page.inner_text("body")
            browser.close()
    except Exception as exc:  # noqa: BLE001 — 센다: 못 열면 None으로 돌려 부른 쪽이 '열 수 없음'을 적는다
        print(f"[안내] 크롬으로도 출처를 열지 못했습니다 {url[:80]}: {exc.__class__.__name__}")
        return None
    if _CHALLENGE.search(title) or _CHALLENGE.search(body[:400]):
        print(f"[안내] 크롬으로도 봇 검사 화면입니다 {url[:80]}")
        return None
    return normalize(body)


def page_text(url: str) -> str | None:
    """주소의 본문 글자(태그·스크립트 뺌, 정규화). 못 열면 None. 봇 검사 화면(200으로 오는 'Just a moment…')은 못 연 것으로 본다."""
    if url in _CACHE:
        return _CACHE[url]
    text = None
    try:
        r = requests.get(url, headers=_UA, timeout=25)
        r.raise_for_status()
        raw = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", r.text)
        title = re.search(r"(?is)<title[^>]*>(.*?)</title>", r.text)
        if not (title and _CHALLENGE.search(title.group(1))):
            text = normalize(re.sub(r"<[^>]+>", " ", raw))
    except requests.RequestException as exc:
        print(f"[안내] 출처를 열지 못했습니다 {url[:80]}: {exc}")
    if text is None and os.environ.get("EVIDENCE_BROWSER") == "1":
        text = _browser_text(url)
    _CACHE[url] = text
    return text


# 일정 글(다음 주 일정·이벤트)에서 근거가 있어야 하는 사건 낱말(2026-10-06, 감사 F-029: 10/4 「다음 주 일정」이 2025년 뉴스를 섞어
# 있지도 않은 '10월 1일부터 미국 정부 셧다운'을 사실처럼 썼다). 일정 자체(지표 발표일)는 공식 달력이 있어 여기 넣지 않는다.
_EVENT = re.compile(r"셧다운|shutdown|파업|strike|디폴트|default|부도|폐쇄|중단|연기|철회|사임|해임|제재|sanction|탄핵|봉쇄")


def needed_claims(doc: dict, numbers: bool = True, events: bool = False) -> list[str]:
    """근거가 있어야 하는 본문 문장 — 큰따옴표 인용이 든 문장과(numbers면) 숫자가 든 문장, (events면) 사건 낱말이 든 문장."""
    ko = doc.get("ko") or doc
    out: list[str] = []
    for section in ko.get("narrative") or []:
        body = re.sub(r"<[^>]+>", "", str(section.get("body") or ""))
        for sentence in _SENT_SPLIT.split(body):
            sentence = sentence.strip()
            quoted = _QUOTE.search(sentence)
            if quoted and not numbers:   # 잡지 밖의 글: 누가 말했는지 가리키는 인용만(검색어·이름 따옴표는 근거가 필요 없다)
                quoted = (len(quoted.group(1).split()) >= 4 and _ATTRIBUTION.search(sentence)) and quoted
            if sentence and ((numbers and re.search(r"\d", sentence)) or quoted or (events and _EVENT.search(sentence))) \
                    and sentence not in out:
                out.append(sentence)
    return out


# 근거 구절의 숫자와 원문 숫자(2026-10-06, 감사 F-088: 본문 '39조 달러'의 원문이 '$38.5 trillion'이어도 통과했다).
_KO_UNIT = {"조": 1e12, "억": 1e8, "만": 1e4, "천": 1e3}
_EN_UNIT = {"trillion": 1e12, "billion": 1e9, "bn": 1e9, "million": 1e6, "mn": 1e6, "thousand": 1e3}
_NUM_TOKEN = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(조|억|만|천|trillion|billion|bn|million|mn|thousand)?", re.I)


def _values(text: str) -> list[float]:
    """글 속 숫자 값 — 단위를 곱하고 '1만 7,000'처럼 이어진 한국어 단위는 더한 값도 넣는다."""
    out: list[float] = []
    tokens = []
    for m in _NUM_TOKEN.finditer(text):
        try:
            base = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        unit = (m.group(2) or "").lower()
        value = base * _KO_UNIT.get(unit, _EN_UNIT.get(unit, 1))
        tokens.append((m.start(), m.end(), value, unit))
        out.append(value)
    for (s1, e1, v1, u1), (s2, e2, v2, u2) in zip(tokens, tokens[1:]):
        if u1 in _KO_UNIT and s2 - e1 <= 2 and (not u2 or _KO_UNIT.get(u2, 0) < _KO_UNIT[u1]):
            out.append(v1 + v2)
    return out


def number_mismatches(claim: str, original: str) -> list[tuple[float, float]]:
    """구절의 숫자 가운데 원문의 가장 가까운 숫자와 0.5%~50% 어긋나는 것 — 옮겨 적다 틀린 숫자(39 대 38.5).
    원문에 짝이 아예 없는 숫자(날짜를 문맥에서 가져온 것 등)는 여기서 보지 않는다."""
    months = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}
    have = [v for v in _values(original) if v] + [float(months[w[:3]]) for w in re.findall(r"[A-Za-z]{3,}", original.lower())
                                                  if w[:3] in months and (len(w) == 3 or w in (
                                                      "january", "february", "march", "april", "june", "july", "august",
                                                      "september", "sept", "october", "november", "december"))]
    bad = []
    claim_values = _values(claim)
    combined = set(claim_values[len(_NUM_TOKEN.findall(claim)):])
    for value in claim_values:
        if not value or not have:
            continue
        nearest = min(have, key=lambda o: abs(o - value) / max(abs(o), abs(value)))
        gap = abs(nearest - value) / max(abs(nearest), abs(value))
        integers = value == int(value) and nearest == int(nearest) and value != nearest   # 1907 대 1906 — 정수가 다르면 옮겨 적다 틀린 것
        covered = any(abs(c - nearest) <= 1e-9 * max(abs(c), 1) for c in claim_values) or \
            any(abs(c - nearest) / max(abs(c), 1) <= 0.005 for c in combined)   # 그 원문 숫자를 다른 구절 숫자가 이미 옮겼다
        if (0.005 < gap or integers) and gap <= 0.5 and not covered:
            bad.append((value, nearest))
    return bad


# 게시 직전 검사(이 맥)가 크롬으로도 열지 못하는 출처(봇 검사) — 루틴이 쓸 때 열렸어도 맥에서 막혀 글이 버려진다(2026-10-09~11
# 잡지 세 편). 쓰는 단계(관문)에서 막아 다른 출처를 찾게 한다. 새로 막히는 사이트가 보이면 여기에 더한다.
NO_FETCH_DOMAINS = ("autoevolution.com", "stocktwits.com", "freedom969.com")


def _blocked_domain(url: str) -> str | None:
    host = re.sub(r"^https?://(www\.)?", "", url).split("/")[0].lower()
    return next((d for d in NO_FETCH_DOMAINS if host == d or host.endswith("." + d)), None)


def evidence_issues(doc: dict, fetch=None, numbers: bool = True, events: bool = False) -> list[str]:
    """`numbers=False`면 큰따옴표 인용만 본다(잡지 밖의 글 — 숫자는 시세 대조·엔진이 맡는다)."""
    fetch = fetch or page_text      # 부를 때 찾는다(시험이 page_text를 바꿔 끼울 수 있게)
    issues: list[str] = []
    sources = doc.get("sources") or []
    urls = {str(s.get("url") or "").strip() for s in sources if isinstance(s, dict)}
    for s in (sources if numbers or events else []):
        if isinstance(s, dict) and not str(s.get("url") or "").startswith("http"):
            issues.append(f"출처 '{s.get('name') or s.get('title')}'에 주소(url)가 없습니다 — 근거를 대조할 수 없습니다")
    evidence = [e for e in (doc.get("evidence") or []) if isinstance(e, dict)]
    for sentence in needed_claims(doc, numbers, events):
        key = normalize(sentence)
        if not any(normalize(str(e.get("claim") or "")) and normalize(str(e.get("claim"))) in key for e in evidence):
            issues.append(f"근거 없음: '{sentence[:70]}' — evidence에 이 문장 안의 구절(claim)·출처 주소·원문 문장을 적으십시오")
    for e in evidence:
        url, original = str(e.get("url") or "").strip(), str(e.get("original") or "")
        if url not in urls:
            issues.append(f"근거 '{str(e.get('claim'))[:40]}'의 주소가 출처 목록에 없습니다: {url[:80]}")
            continue
        if len(normalize(original)) < MIN_ORIGINAL:
            issues.append(f"근거 '{str(e.get('claim'))[:40]}'의 원문(original)이 비었거나 {MIN_ORIGINAL}자보다 짧습니다")
            continue
        if _blocked_domain(url):
            issues.append(f"근거 '{str(e.get('claim'))[:40]}'의 출처({_blocked_domain(url)})는 게시 직전 검사에서 열리지 않습니다"
                          " — 같은 사실을 담은 다른 출처를 쓰십시오")
            continue
        text = fetch(url)
        if text is None:
            issues.append(f"근거 '{str(e.get('claim'))[:40]}'의 출처를 열 수 없습니다 — 열리는 출처를 쓰십시오: {url[:80]}")
        elif normalize(original) not in text:
            issues.append(f"근거 '{str(e.get('claim'))[:40]}'의 원문이 출처 페이지에 없습니다: '{original[:60]}'")
        for value, nearest in number_mismatches(str(e.get("claim") or ""), original):
            issues.append(f"근거 '{str(e.get('claim'))[:40]}'의 숫자 {value:,.10g}이(가) 원문의 {nearest:,.10g}과 다릅니다 — 원문 숫자를 그대로 옮기십시오")
    return issues
