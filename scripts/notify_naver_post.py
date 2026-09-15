"""네이버에만 올라간 글(한국어 시황)을 텔레그램·스레드에 알린다 (2026-09-15, 사용자 결정).

    python -m scripts.notify_naver_post <원고.json> <네이버 주소>

왜 따로 있나: 시황이 워드프레스를 거치지 않게 되면서 `publish_editorial`의 알림 자리가 없어졌다.
알릴 수 있는 시점은 **맥의 동기화가 네이버에 올린 직후**이고, 그때 비로소 주소(logNo)가 생긴다.
같은 글을 두 번 알리지 않는 일은 부르는 쪽이 한다 — `posted.json`에 없는 글만 올리기 때문이다.
알림이 실패해도 종료 코드는 0이다(알림 때문에 동기화를 멈추지 않는다).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

from src import notify_telegram, notify_threads   # noqa: E402  (.env를 먼저 읽어야 한다)


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) < 2:
        print(__doc__.strip())
        return 0
    path, link = Path(args[0]), args[1]
    doc = json.loads(path.read_text(encoding="utf-8"))
    title = str((doc.get("ko") or {}).get("title") or "")
    if not title or not link.startswith("https://blog.naver.com/"):
        print(f"[알림] 건너뜀 — 제목이나 주소가 비었습니다 ({title!r}, {link!r})")
        return 0
    notify_telegram.notify_naver(doc, title, link)
    notify_threads.notify_naver(doc, title, link)
    return 0


if __name__ == "__main__":
    sys.exit(main())
