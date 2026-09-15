"""성적표의 빈 주소를 네이버 글 주소로 채운다 (2026-09-15, 사용자 결정).

    python -m scripts.scoreboard_naver_urls            # 채우고 저장(바뀐 것이 있으면 0, 없으면 1)
    python -m scripts.scoreboard_naver_urls --dry      # 무엇을 채울지만 보여 준다

왜 필요한가: 한국어 시황이 네이버 블로그 전용이 되면서 **발행 시점에 주소를 모르게** 됐다.
네이버 글 번호(logNo)는 이 맥의 동기화가 실제로 올린 뒤에야 생긴다. 그래서 발행 워크플로는
성적표 항목을 `key`(예: `kr_2026-09-15`)로 먼저 만들어 두고 주소는 비워 두며, 올린 뒤에
이 스크립트가 채운다. 빈 주소인 항목은 성적표 페이지가 알아서 건너뛰므로 그사이에도 깨지지 않는다.

기록은 맥의 `~/.market-brief-naver/posted.json`에 있다(원고 경로 → logNo·blog).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCOREBOARD = ROOT / "data" / "scoreboard.yaml"
POSTED = Path.home() / ".market-brief-naver" / "posted.json"
KEY = re.compile(r"editorial/(kr|us)_(\d{4}-\d{2}-\d{2})\.json$")


def naver_urls(posted: dict) -> dict[str, str]:
    """{성적표 열쇠: 네이버 주소} — 시황 원고만 고른다."""
    out: dict[str, str] = {}
    for path, info in (posted or {}).items():
        match = KEY.search(str(path).replace("\\", "/"))
        if not match or not info.get("logNo"):
            continue
        market, date_str = match.group(1), match.group(2)
        blog = info.get("blog") or "fermata49"
        out[f"{market}_{date_str}"] = f"https://blog.naver.com/{blog}/{info['logNo']}"
    return out


def fill(articles: list[dict], urls: dict[str, str]) -> list[str]:
    filled = []
    for entry in articles:
        key = str(entry.get("key") or "")
        if not key or entry.get("url"):
            continue
        url = urls.get(key)
        if url:
            entry["url"] = url
            filled.append(f"{key} → {url}")
    return filled


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--posted", type=Path, default=POSTED)
    a = ap.parse_args(argv)
    if not a.posted.exists():
        print(f"기록 파일이 없습니다: {a.posted}")   # 맥이 아닌 곳에서 돌 수 있다 — 실패는 아니다
        return 1
    articles = yaml.safe_load(SCOREBOARD.read_text(encoding="utf-8")) or []
    urls = naver_urls(json.loads(a.posted.read_text(encoding="utf-8")))
    filled = fill(articles, urls)
    if not filled:
        print("채울 주소가 없습니다.")
        return 1
    for line in filled:
        print("  ", line)
    if a.dry:
        return 0
    header = []
    for line in SCOREBOARD.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            header.append(line)
        else:
            break
    body = yaml.safe_dump(articles, allow_unicode=True, sort_keys=False, width=100)
    SCOREBOARD.write_text("\n".join(header) + "\n\n" + body, encoding="utf-8")
    print(f"{len(filled)}개 채웠습니다: {SCOREBOARD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
