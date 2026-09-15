"""성적표의 빈 주소를 네이버 글 주소로 채운다 (2026-09-15, 사용자 결정).

    python -m scripts.scoreboard_naver_urls            # 채우고 저장(바뀐 것이 있으면 0, 없으면 1)
    python -m scripts.scoreboard_naver_urls --dry      # 무엇을 채울지만 보여 준다

왜 필요한가: 한국어 시황이 네이버 블로그 전용이 되면서 **발행 시점에 주소를 모르게** 됐다.
네이버 글 번호(logNo)는 이 맥의 동기화가 실제로 올린 뒤에야 생긴다. 그래서 발행 워크플로는
성적표 항목을 `key`(예: `kr_2026-09-15`)로 먼저 만들어 두고 주소는 비워 두며, 올린 뒤에
이 스크립트가 채운다. 빈 주소인 항목은 성적표 페이지가 알아서 건너뛰므로 그사이에도 깨지지 않는다.

2026-09-15 저녁부터는 **이미 적혀 있는 본진 주소도 바꾼다**. 프리뷰·Checkpoint 본진 글을 비공개로
돌렸고(사용자: "체크포인트는 2번"), 그날까지 공개돼 있던 한국어 시황 일곱 편도 같이 비공개로 돌렸다.
비공개 글의 주소는 방문자에게 404라서 성적표가 그 항목을 통째로 뺀다 — 판정을 지우지 않겠다고 한
성적표가 글만 안 보이면 빈 페이지가 된다. 그래서 네이버에 같은 글이 있으면 그 주소로 갈아 끼운다.

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
# 본진에 공개 쌍둥이가 없는 갈래 — 시황(아예 안 올린다)·프리뷰·기준표(비공개로만 올린다).
# `naver_sync.py`가 알림을 보내는 조건과 같은 목록이다. 한쪽만 고치면 주소와 알림이 어긋난다.
NAVER_ONLY_SERIES = {"프리뷰", "기준표"}


def _wp_slug(doc: dict, path: Path) -> str:
    """이 원고가 본진에서 썼던 slug. `publish_feature._slug`·`publish_editorial`과 같은 규칙이다."""
    if KEY.search(str(path).replace("\\", "/")):
        return f"editorial-{doc.get('market')}-{doc.get('date')}-ko"
    value = doc.get("slug") or path.stem
    return re.sub(r"[^a-z0-9-]+", "-", str(value).lower()).strip("-")


def _naver_only(doc: dict) -> bool:
    return doc.get("market") in ("kr", "us") or doc.get("series") in NAVER_ONLY_SERIES


def naver_urls(posted: dict, root: Path = ROOT) -> tuple[dict[str, str], dict[str, str]]:
    """({성적표 열쇠: 네이버 주소}, {본진 slug: 네이버 주소}) — 네이버에만 있는 글만 고른다.

    열쇠는 새 항목(주소를 비워 둔 것)을, slug는 옛 항목(본진 주소가 적혀 있는 것)을 위한 것이다.
    """
    keys: dict[str, str] = {}
    slugs: dict[str, str] = {}
    for path, info in (posted or {}).items():
        if not info.get("logNo"):
            continue
        clean = str(path).replace("\\", "/")
        manuscript = Path(clean)
        if not manuscript.is_absolute():
            manuscript = root / clean
        if not manuscript.exists():
            continue
        try:
            doc = json.loads(manuscript.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue           # 읽을 수 없는 원고는 건너뛴다 — 세어 두고 싶을 만큼 흔하지 않다
        if not _naver_only(doc):
            continue
        url = f"https://blog.naver.com/{info.get('blog') or 'fermata49'}/{info['logNo']}"
        match = KEY.search(clean)
        if match:
            keys[f"{match.group(1)}_{match.group(2)}"] = url
        slugs[_wp_slug(doc, manuscript)] = url
    return keys, slugs


def fill(articles: list[dict], keys: dict[str, str], slugs: dict[str, str] | None = None) -> list[str]:
    """빈 주소는 열쇠로 채우고, 비공개가 된 본진 주소는 네이버 주소로 갈아 끼운다."""
    slugs = slugs or {}
    filled = []
    for entry in articles:
        url = str(entry.get("url") or "")
        key = str(entry.get("key") or "")
        if not url:
            if key and keys.get(key):
                entry["url"] = keys[key]
                filled.append(f"{key} → {keys[key]}")
            continue
        if "fermata.it.kr/" not in url:
            continue           # 이미 네이버 주소다
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        if slugs.get(slug):
            entry["url"] = slugs[slug]
            filled.append(f"{slug} → {slugs[slug]}")
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
    keys, slugs = naver_urls(json.loads(a.posted.read_text(encoding="utf-8")))
    filled = fill(articles, keys, slugs)
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
