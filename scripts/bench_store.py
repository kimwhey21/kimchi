"""벤치마크(재테크농부) 수집의 공통 설정입니다.

유료 구독 콘텐츠라서 **저장소 안에 본문을 두지 않습니다.** 홈 디렉터리 아래
별도 폴더에 쌓고, 저장소에는 이 스크립트들만 둡니다. `compare_to_benchmark.py`의
기준값처럼 본문에서 뽑은 수치만 저장소로 옮깁니다.

폴더 구조
---------
    ~/.market-brief-bench/
        profile/            크로미움 프로필 (로그인 세션이 여기 남습니다)
        posts/<id>.json     글 하나의 블록 구조 전문
        index.json          id -> 제목·날짜·분류·잠김 여부
        logs/               실행 기록
        NEW.md              마지막 실행의 요약 (읽기용)
"""
from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path.home() / ".market-brief-bench"
PROFILE = ROOT / "profile"
POSTS = ROOT / "posts"
LOGS = ROOT / "logs"
INDEX = ROOT / "index.json"
DIGEST = ROOT / "NEW.md"
LOCK = ROOT / "run.lock"

CHANNEL = "https://contents.premium.naver.com/finfarmer00/finfarmer"
LIST_URL = CHANNEL + "/contents"
POST_URL = CHANNEL + "/contents/"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")


def ensure_dirs() -> None:
    for d in (ROOT, PROFILE, POSTS, LOGS):
        d.mkdir(parents=True, exist_ok=True)


def load_index() -> dict:
    if INDEX.exists():
        return json.loads(INDEX.read_text(encoding="utf-8"))
    return {}


def save_index(index: dict) -> None:
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
