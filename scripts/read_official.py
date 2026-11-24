"""공식 기관 문서를 끝까지 읽는다 — `python -m scripts.read_official <주소> --find 말 [--find 말 ...]`.

왜 (2026-11-22): 일요일 가이드가 주제 셋을 다 놓쳤다. 공식 페이지가 막힌 게 아니라 WebFetch가 못 읽는 꼴이었다.
- 한국거래소 공지·국세청 해석사례: 처음 받는 HTML에 본문이 없고 자바스크립트가 나중에 불러온다(메뉴 틀만 읽혔다).
- 국세청 안내: 본문은 있는데 페이지가 커서 요약 도구가 앞부분만 읽고 잘랐다.
- 금융위 PDF: 서버가 PDF를 `application/octet-stream`으로 보내 이진 데이터로 읽혔다.

그래서 순서대로 한다.
1. 직접 받는다. PDF(앞 4바이트 `%PDF`)면 글자를 뽑는다(pypdf, 없으면 설치).
2. HTML이면 글자만 남긴다. `--find`로 준 말이 다 있으면 끝.
3. 없으면 **브라우저로 띄워** 자바스크립트가 불러온 본문까지 읽는다(Playwright 크로미움, 없으면 설치 — 처음 한 번 1~2분).
찾은 말마다 앞뒤 줄을 찍는다. `--find` 없이 부르면 앞 4,000자를 찍는다.

거래소 공지 게시판은 따로: `--krx "정기변경"`이 주가지수 공지에서 제목으로 찾아 최신 5건의 날짜·제목·본문을 찍는다.

막힌 사이트(403·차단 화면)를 위장이나 우회로 뚫지 않는다 — 그때는 '못 읽음'을 찍고 다른 출처로 간다.
"""
from __future__ import annotations

import argparse
import html
import io
import re
import subprocess
import sys

import requests

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9"}
KRX = "https://data.krx.co.kr/contents/MDC/COMS/board/"
KRX_BOARDS = {"index": ("MDCINFO005", "MKD01040000")}   # 주가지수 공지(정기변경·지수 신설 등)


def _pip(package: str) -> None:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", package], capture_output=True, timeout=300)


def pdf_text(data: bytes) -> str:
    try:
        import pypdf
    except ImportError:
        _pip("pypdf")
        import pypdf
    reader = pypdf.PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def html_text(markup: str) -> str:
    markup = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", markup)
    markup = re.sub(r"(?i)<br\s*/?>|</(p|div|li|tr|h\d|td|th)>", "\n", markup)
    text = html.unescape(re.sub(r"<[^>]+>", " ", markup))
    lines = (re.sub(r"[ \t ]+", " ", line).strip() for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def rendered_text(url: str, wait_ms: int = 4000) -> str:
    """브라우저로 띄워 자바스크립트가 채운 뒤의 글자. 크로미움이 없으면 한 번 설치한다."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        _pip("playwright")
        from playwright.sync_api import sync_playwright

    def _read(p) -> str:
        last: Exception | None = None
        for options in ({}, {"channel": "chrome"}):
            try:
                browser = p.chromium.launch(headless=True, **options)
            except Exception as exc:  # noqa: BLE001 — 다음 방법으로
                last = exc
                continue
            try:
                page = browser.new_page(user_agent=UA["User-Agent"], locale="ko-KR")
                # 'networkidle'만 기다리면 거래소 페이지는 뒤에서 계속 묻느라 조용해지지 않아 60초 뒤 실패한다(2026-11-24) —
                # 문서가 뜨면 조용해지기를 15초까지만 기다리고, 그래도 안 되면 그대로 읽는다
                page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                try:
                    page.wait_for_load_state("networkidle", timeout=15_000)
                except Exception:  # noqa: BLE001 — 조용해지지 않는 페이지도 읽는다
                    pass
                page.wait_for_timeout(wait_ms)
                return page.inner_text("body")
            finally:
                browser.close()
        raise RuntimeError(f"브라우저를 띄우지 못했습니다: {last}")

    with sync_playwright() as p:
        try:
            return _read(p)
        except RuntimeError:
            pass
    subprocess.run([sys.executable, "-m", "playwright", "install", "--with-deps", "chromium"],
                   capture_output=True, timeout=600)
    with sync_playwright() as p:
        return _read(p)


def read(url: str, finds: list[str]) -> tuple[str, str]:
    """(어떻게 읽었나, 글자). 못 읽으면 ('못 읽음: 이유', '')."""
    try:
        response = requests.get(url, headers=UA, timeout=40)
    except requests.RequestException as exc:
        return f"못 읽음: {type(exc).__name__}", ""
    if response.status_code >= 400:
        return f"못 읽음: HTTP {response.status_code} — 우회하지 말고 다른 출처로", ""
    if response.content[:4] == b"%PDF":
        return "PDF에서 글자를 뽑음", pdf_text(response.content)
    response.encoding = response.apparent_encoding if response.encoding in (None, "ISO-8859-1") else response.encoding
    text = html_text(response.text)
    if finds and all(word in text for word in finds):
        return "직접 받은 HTML", text
    if not finds and len(text) > 2000:
        return "직접 받은 HTML", text
    try:
        # 브라우저 글자와 처음 받은 글자를 함께 둔다 — 브라우저 쪽이 펼치지 않은 칸(접힌 탭 등)이 빠지지 않게
        return "브라우저로 띄워 읽음(자바스크립트가 불러온 본문 포함) + 처음 받은 글자", rendered_text(url) + "\n\n" + text
    except Exception as exc:  # noqa: BLE001 — 받은 만큼이라도 돌려준다
        return f"직접 받은 HTML(브라우저 실패: {type(exc).__name__})", text


def krx_notices(keyword: str, board: str = "index", count: int = 5) -> list[dict]:
    board_id, bbs_id = KRX_BOARDS[board]
    headers = {**UA, "Referer": f"{KRX}MDCCOMS010_S1.cmd?boardId={board_id}"}
    rows = requests.post(f"{KRX}MDCCOMS010_S1D1.cmd", headers=headers, timeout=40, data={
        "curPage": 1, "pageSize": count, "mktId": "", "condTp": "2", "titleContn": keyword,
        "strtDd": "", "endDd": "", "boardId": board_id}).json()["output"]["OutBlock_1"]
    out = []
    for row in rows[:count]:
        detail = requests.post(f"{KRX}MDCCOMS010_S2D1.cmd", headers=headers, timeout=40, data={
            "boardId": board_id, "cmBbsId": row.get("CM_BBS_ID") or bbs_id, "bbsSeq": row["BBS_SEQ"]}).json()["output"]
        out.append({"date": row.get("REG_DT"), "title": row.get("TITLE"),
                    "url": f"{KRX}MDCCOMS010_S2.cmd?boardId={board_id}&cmBbsId={row.get('CM_BBS_ID') or bbs_id}&bbsSeq={row['BBS_SEQ']}",
                    "body": html_text(detail.get("MAINDOC_CONTN") or ""), "files": detail.get("ATTACH_FILE_INFO") or ""})
    return out


def excerpts(text: str, word: str, around: int = 2, limit: int = 6) -> list[str]:
    lines = text.splitlines()
    hits = [i for i, line in enumerate(lines) if word in line][:limit]
    return ["\n".join(lines[max(0, i - around): i + around + 1]) for i in hits]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("url", nargs="?")
    parser.add_argument("--find", action="append", default=[], help="본문에서 찾을 말(여러 번 쓸 수 있음)")
    parser.add_argument("--krx", help="한국거래소 주가지수 공지에서 제목으로 찾기")
    parser.add_argument("--chars", type=int, default=4000)
    args = parser.parse_args(argv)
    if args.krx:
        for notice in krx_notices(args.krx):
            print(f"== {notice['date']} {notice['title']}\n{notice['url']}\n{notice['body'][:args.chars]}\n붙임: {notice['files']}\n")
        return 0
    if not args.url:
        parser.error("주소나 --krx가 필요합니다")
    how, text = read(args.url, args.find)
    print(f"[{how}] {len(text):,}자")
    if not text:
        return 1
    if not args.find:
        print(text[:args.chars])
        return 0
    missing = []
    for word in args.find:
        found = excerpts(text, word)
        if not found:
            missing.append(word)
            continue
        print(f"\n--- '{word}' {len(found)}곳")
        for chunk in found:
            print(chunk + "\n·")
    if missing:
        print(f"\n[없음] {', '.join(missing)} — 이 문서에는 없습니다. 지어내지 말고 다른 공식 출처로 확인하십시오.")
    return 0 if not missing else 2


if __name__ == "__main__":
    sys.exit(main())
