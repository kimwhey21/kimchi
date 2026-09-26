"""네이버에 올린 글의 주소표 `data/naver_posts.json`을 맥의 게시 기록에서 만든다 (2026-09-26).

    python -m scripts.naver_map_sync            # 표만 다시 쓴다
    python -m scripts.naver_map_sync --push     # 바뀌었으면 그 파일만 커밋·푸시(하루 한 번)

왜 필요한가: 종목 페이지(`src/stock_pages.py`)의 「이 종목이 나온 글」이 한국어 글을 본진 주소로 이었는데, 한국어 글은
2026-09-22부터 본진에서 전부 비공개라 방문자에게 404였다(37쪽·179개). 독자가 열 수 있는 주소는 네이버뿐이다. 그런데 종목
페이지는 깃허브 러너에서 만들어지고, 네이버 글 번호는 이 맥의 게시 기록(`~/.market-brief-naver/posted.json`)에만 있다.
그래서 맥이 그 기록을 표로 옮겨 저장소에 올린다.

- 잡지(두 번째 블로그, 퍼플썸)는 넣지 않는다 — 페르마타 이름으로 잇지 않는 글이다.
- 커밋은 **이 파일 하나만** 지정해서 한다(`git commit -- <파일>`). 작업 중인 다른 변경이 딸려 올라가지 않는다.
- 하루 한 번만 커밋한다. 글마다 커밋하면 main에 잡음이 쌓인다(성적표 주소 커밋이 18일에 28번이었다). 종목 페이지는
  주 1회(토 11:30) 다시 만들어지므로 하루 늦어도 된다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAP_PATH = ROOT / "data" / "naver_posts.json"
POSTED = Path.home() / ".market-brief-naver" / "posted.json"
PUSHED_STAMP = Path.home() / ".market-brief-naver" / "naver_map_pushed"
DEFAULT_BLOG = "fermata49"      # 옛 기록에는 blog 칸이 없다 — 잡지가 생기기 전 글이라 전부 본 블로그다


def build(posted: dict) -> dict[str, str]:
    """게시 기록 → {저장소 기준 원고 경로: 네이버 주소}. 잡지는 뺀다."""
    out: dict[str, str] = {}
    for key, value in posted.items():
        rel = str(key).replace("\\", "/").split("market-brief/")[-1]
        if not rel.startswith("editorial/") or "/magazine/" in rel:
            continue
        if not isinstance(value, dict) or not value.get("logNo"):
            continue
        blog = str(value.get("blog") or DEFAULT_BLOG)
        if blog != DEFAULT_BLOG:
            continue
        out[rel] = f"https://blog.naver.com/{blog}/{value['logNo']}"
    return dict(sorted(out.items()))


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=120)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--push", action="store_true", help="바뀌었으면 그 파일만 커밋·푸시한다(하루 한 번)")
    args = parser.parse_args(argv)
    if not POSTED.exists():
        raise SystemExit(f"게시 기록이 없습니다: {POSTED} — 이 스크립트는 네이버에 글을 올리는 맥에서만 돕니다.")
    table = build(json.loads(POSTED.read_text(encoding="utf-8")))
    text = json.dumps(table, ensure_ascii=False, indent=1) + "\n"
    old = MAP_PATH.read_text(encoding="utf-8") if MAP_PATH.exists() else ""
    if text == old:
        print(f"네이버 주소표 그대로 ({len(table)}편)")
        return 0
    today = dt.date.today().isoformat()
    if args.push and PUSHED_STAMP.exists() and PUSHED_STAMP.read_text().strip() == today:
        print("네이버 주소표: 오늘 이미 올렸습니다 — 내일 올립니다")
        return 0
    MAP_PATH.write_text(text, encoding="utf-8")
    print(f"네이버 주소표를 다시 썼습니다 ({len(table)}편)")
    if not args.push:
        return 0
    add = _git("add", "--", str(MAP_PATH.relative_to(ROOT)))
    commit = _git("commit", "-q", "-m", f"네이버 주소표 갱신: {today} ({len(table)}편)", "--", str(MAP_PATH.relative_to(ROOT)))
    if add.returncode or commit.returncode:
        print(f"[경고] 네이버 주소표 커밋 실패: {(commit.stderr or add.stderr)[-200:]}", file=sys.stderr)
        return 1
    push = _git("push", "-q", "origin", "HEAD:main")
    if push.returncode:
        print(f"[경고] 네이버 주소표 푸시 실패(다음 실행에 다시): {push.stderr[-200:]}", file=sys.stderr)
        return 1
    PUSHED_STAMP.write_text(today)
    print("네이버 주소표를 커밋·푸시했습니다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
