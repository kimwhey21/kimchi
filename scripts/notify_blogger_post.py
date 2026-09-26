"""블로그스팟에 올라간 한국어 글을 텔레그램 채널·스레드에 알린다 (2026-09-26, 사장님: "텔레그램 알림은 블로그스팟 주소로 보내도록
바꿔" → "스레드도 같이 고쳐주는거지?").

    python -m scripts.notify_blogger_post <원고.json> <블로그스팟 주소>

왜: 한국어 글 알림은 맥의 네이버 동기화가 시황 블로그(fermata49)에 올린 뒤 네이버 주소로 보냈다(`notify_naver_post`).
2026-09-26에 그 블로그 게시를 멈추자 알림도 끊겼다 — 독자가 열 수 있는 한국어 글 주소는 이제 블로그스팟뿐이다.
맥의 `blogger_sync`가 글을 올리고 주소를 확인한 직후 이 스크립트를 부른다(시황 블로그 게시가 멈춰 있을 때만 —
다시 켜면 네이버 쪽 알림과 겹친다).

거르는 것:
- 잡지(시리즈 `매거진`) — 퍼플썸 브랜드라 페르마타 채널에 보내지 않는다.
- 영어 글.
- 밀린 원고 — 원고 날짜가 오늘·어제가 아니면 보내지 않는다. 블로그스팟은 밀린 글을 하루 열 편까지 올리므로 그대로 두면
  채널에 옛 글이 쏟아진다.
- 블로그스팟 주소가 아닌 것(주소를 못 찾은 경우 포함).
알림이 실패해도 종료 코드는 0이다(알림 때문에 동기화를 멈추지 않는다).
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

from src import notify_telegram, notify_threads   # noqa: E402  (.env를 먼저 읽어야 한다)

BLOGSPOT = "https://fermata49.blogspot.com/"
FRESH_DAYS = 1


def skip_reason(path: Path, doc: dict, link: str, today: dt.date) -> str:
    if not link.startswith(BLOGSPOT):
        return f"블로그스팟 주소가 아닙니다({link!r})"
    if doc.get("series") == "매거진" or "/magazine/" in str(path):
        return "잡지 글은 페르마타 채널에 보내지 않습니다"
    if str(doc.get("lang") or "ko") == "en":
        return "영어 글"
    if not str((doc.get("ko") or {}).get("title") or ""):
        return "제목이 비었습니다"
    try:
        age = (today - dt.date.fromisoformat(str(doc.get("date") or ""))).days
    except ValueError:
        return f"원고 날짜를 읽지 못했습니다({doc.get('date')!r})"
    if age > FRESH_DAYS:
        return f"밀린 원고({doc.get('date')})"
    return ""


def main(argv: list[str] | None = None, today: dt.date | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) < 2:
        print(__doc__.strip())
        return 0
    path, link = Path(args[0]), args[1]
    doc = json.loads(path.read_text(encoding="utf-8"))
    reason = skip_reason(path, doc, link, today or dt.date.today())
    if reason:
        print(f"[알림] 건너뜀 — {reason}: {path.name}")
        return 0
    title = str(doc["ko"]["title"])
    notify_telegram.notify_naver(doc, title, link)
    notify_threads.notify_naver(doc, title, link)
    return 0


if __name__ == "__main__":
    sys.exit(main())
