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


def page_text(url: str) -> str | None:
    """주소의 본문 글자(태그·스크립트 뺌, 정규화). 못 열면 None."""
    if url in _CACHE:
        return _CACHE[url]
    try:
        r = requests.get(url, headers=_UA, timeout=25)
        r.raise_for_status()
        raw = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", r.text)
        text = normalize(re.sub(r"<[^>]+>", " ", raw))
    except requests.RequestException as exc:
        print(f"[안내] 출처를 열지 못했습니다 {url[:80]}: {exc}")
        text = None
    _CACHE[url] = text
    return text


def needed_claims(doc: dict, numbers: bool = True) -> list[str]:
    """근거가 있어야 하는 본문 문장 — 큰따옴표 인용이 든 문장과(numbers면) 숫자가 든 문장."""
    ko = doc.get("ko") or doc
    out: list[str] = []
    for section in ko.get("narrative") or []:
        body = re.sub(r"<[^>]+>", "", str(section.get("body") or ""))
        for sentence in _SENT_SPLIT.split(body):
            sentence = sentence.strip()
            quoted = _QUOTE.search(sentence)
            if quoted and not numbers:   # 잡지 밖의 글: 누가 말했는지 가리키는 인용만(검색어·이름 따옴표는 근거가 필요 없다)
                quoted = (len(quoted.group(1).split()) >= 4 and _ATTRIBUTION.search(sentence)) and quoted
            if sentence and ((numbers and re.search(r"\d", sentence)) or quoted) and sentence not in out:
                out.append(sentence)
    return out


def evidence_issues(doc: dict, fetch=None, numbers: bool = True) -> list[str]:
    """`numbers=False`면 큰따옴표 인용만 본다(잡지 밖의 글 — 숫자는 시세 대조·엔진이 맡는다)."""
    fetch = fetch or page_text      # 부를 때 찾는다(시험이 page_text를 바꿔 끼울 수 있게)
    issues: list[str] = []
    sources = doc.get("sources") or []
    urls = {str(s.get("url") or "").strip() for s in sources if isinstance(s, dict)}
    for s in (sources if numbers else []):
        if isinstance(s, dict) and not str(s.get("url") or "").startswith("http"):
            issues.append(f"출처 '{s.get('name') or s.get('title')}'에 주소(url)가 없습니다 — 근거를 대조할 수 없습니다")
    evidence = [e for e in (doc.get("evidence") or []) if isinstance(e, dict)]
    for sentence in needed_claims(doc, numbers):
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
        text = fetch(url)
        if text is None:
            issues.append(f"근거 '{str(e.get('claim'))[:40]}'의 출처를 열 수 없습니다 — 열리는 출처를 쓰십시오: {url[:80]}")
        elif normalize(original) not in text:
            issues.append(f"근거 '{str(e.get('claim'))[:40]}'의 원문이 출처 페이지에 없습니다: '{original[:60]}'")
    return issues
