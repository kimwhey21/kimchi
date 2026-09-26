"""독자가 보는 **본진 화면**을 받아 빈 그림과 죽은 링크를 센다 (2026-09-26).

    python -m scripts.site_audit --english     # 시장별 가장 최근 영어 시황(고친 날 이후 글)

왜 필요한가: 2026-09-26 점검에서 셋이 한꺼번에 나왔다 — 영어 시황 24편의 그림 자리가 전부 `<img src="">`였고(9/9부터),
종목 페이지 37쪽의 글 링크 179개가 방문자에게 404였다(한국어 글을 본진 비공개로 돌린 9/22부터). 둘 다 "독자가 읽는 곳이
바뀌었는데 그 글을 가져다 쓰는 곳이 따라 바뀌지 않은" 꼴이고, 우리 검사는 네이버 화면(`naver_audit`)만 보고 있었다.
본진의 영어 글도 **실제 화면**을 받아 센다(종목 페이지 점검 `--stocks`는 2026-09-26 종목 페이지를 없애며 뺐다). 카페24 공유 호스팅이라 한 번에 하나씩, 사이에 쉰다.
문제가 있으면 0이 아닌 값으로 끝나 워크플로가 빨간 X가 되고 텔레그램 운영 알림이 간다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://fermata.it.kr"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"}   # NinjaFirewall이 헤드리스 UA를 막는다
PAUSE = 1.5
ENGLISH_GRAPHICS_START = "2026-09-26"     # 영어판 그림을 그리기 시작한 날 — 그전 글은 그림이 없는 채로 남아 있다
_IMG = re.compile(r"<img\b[^>]*>", re.IGNORECASE)


def _get(url: str) -> requests.Response:
    response = requests.get(url, headers=UA, timeout=40)
    time.sleep(PAUSE)
    return response


def empty_images(html: str) -> int:
    return sum(1 for tag in _IMG.findall(html) if re.search(r'\bsrc=""', tag) or "src=" not in tag)


def figure_count(html: str) -> int:
    return sum(1 for tag in _IMG.findall(html) if 'class="mb-figure"' in tag and not re.search(r'\bsrc=""', tag))


def english_problems(root: Path = ROOT, get=_get) -> list[str]:
    problems: list[str] = []
    for market in ("kr", "us"):
        docs = []
        for path in sorted((root / "editorial").glob(f"{market}_*.json")):
            doc = json.loads(path.read_text(encoding="utf-8"))
            if doc.get("en") and str(doc.get("date")) >= ENGLISH_GRAPHICS_START:
                docs.append(doc)
        if not docs:
            print(f"{market}: {ENGLISH_GRAPHICS_START} 이후 영어 시황이 아직 없습니다 — 건너뜀")
            continue
        doc = docs[-1]
        url = f"{SITE}/editorial-{market}-{doc['date']}-en/"
        response = get(url)
        if response.status_code != 200:
            problems.append(f"{url}: HTTP {response.status_code}")
            continue
        expected = sum(1 for s in doc["en"].get("narrative") or [] if (s.get("graphic") or {}).get("kind"))
        empty, figures = empty_images(response.text), figure_count(response.text)
        print(f"{url}: 그림 {figures}/{expected} · 빈 그림 {empty}")
        if empty:
            problems.append(f"{url}: 빈 그림 태그 {empty}개")
        if figures < expected:
            problems.append(f"{url}: 본문 그림 {figures}개 — 원고의 영어 그림은 {expected}개")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--english", action="store_true")
    args = parser.parse_args(argv)
    if not args.english:
        parser.error("--english")
    problems: list[str] = []
    if args.english:
        problems += english_problems()
    if problems:
        print("\n문제:", *problems, sep="\n- ")
        return 1
    print("화면 확인: 문제 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main())
