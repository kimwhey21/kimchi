"""글이 공개되면 스레드(Threads)에 올린다 (2026-09-12, 사용자: 블로그 홍보 2번 "진행해줘").

왜
--
텔레그램은 이미 아는 사람만 들어오는 닫힌 방이고, 스레드는 팔로워가 없어도 알고리즘이 관심 있는 사람 피드에
글을 보여 주는 열린 곳이다 — 검색 말고 새 사람이 들어오는 두 번째 입구. 계정 `@kimwhey218`(사용자, 2026-09-12 개설).

API(2026-09-12 개발자 문서 확인, developers.facebook.com/docs/threads):
  1) POST https://graph.threads.net/v1.0/{user_id}/threads   media_type=IMAGE, image_url, text(≤500자)  → container id
  2) 30초쯤 뒤 POST https://graph.threads.net/v1.0/{user_id}/threads_publish   creation_id → post id
  이미지는 JPEG/PNG, 320~1440px 너비, 8MB 이하(우리 표지 1200×630 PNG가 맞는다). 하루 250편 한도.
  토큰은 60일짜리 장기 토큰(`THREADS_ACCESS_TOKEN`), 24시간 지난 뒤 만료 전에 `/refresh_access_token`으로 갱신 —
  이 맥의 주간 작업(`~/.market-brief-naver/threads_refresh.py`)이 갱신해 .env와 GitHub 시크릿에 넣는다.

원칙은 텔레그램 알림(`notify_telegram`)과 같다 — 설정이 없으면 건너뛰고, 실패해도 발행을 실패시키지 않으며
`[스레드 실패]`로 크게 찍는다. 영어 글과 다시 올린 글은 보내지 않는다.

    python -m src.notify_threads <post_id> <원고.json> [--force]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

from src import notify_telegram

load_dotenv()

GRAPH = "https://graph.threads.net/v1.0"
TIMEOUT = 30
TEXT_LIMIT = 500
PUBLISH_WAIT_SECONDS = 30
STATUS_POLL_SECONDS = 5
STATUS_POLL_MAX = 12


def configured() -> bool:
    return bool(os.environ.get("THREADS_ACCESS_TOKEN")) and bool(os.environ.get("THREADS_USER_ID"))


def compose(doc: dict, title: str, link: str, limit: int = TEXT_LIMIT) -> str:
    """제목 + Take 한두 문장 + 링크. 스레드는 서식이 없으니 줄바꿈만 쓴다. 500자(바이트 아님) 안."""
    body = notify_telegram.summary(doc, limit=200)
    label = notify_telegram.label(doc)
    head = title if label in title else f"{label} · {title}"
    text = head + ("\n\n" + body if body else "") + "\n\n" + link
    if len(text) <= limit:
        return text
    room = limit - len(head) - len(link) - 5
    body = (body[:room].rsplit(" ", 1)[0].rstrip(",.") + "…") if room > 20 else ""
    return head + ("\n\n" + body if body else "") + "\n\n" + link


def _post(path: str, params: dict) -> dict:
    params = dict(params, access_token=os.environ["THREADS_ACCESS_TOKEN"])
    response = requests.post(f"{GRAPH}/{path}", data=params, timeout=TIMEOUT)
    try:
        payload = response.json()
    except ValueError:
        payload = {"error": {"message": response.text[:200]}}
    if response.status_code >= 400 or "error" in payload:
        raise RuntimeError(f"{path}: {payload.get('error', payload)}")
    return payload


def _container_ready(container_id: str) -> bool:
    response = requests.get(f"{GRAPH}/{container_id}", timeout=TIMEOUT,
                            params={"fields": "status,error_message", "access_token": os.environ["THREADS_ACCESS_TOKEN"]})
    payload = response.json() if response.ok else {}
    status = payload.get("status")
    if status == "ERROR":
        raise RuntimeError(f"container {container_id}: {payload.get('error_message')}")
    return status == "FINISHED"


def publish(text: str, image_url: str | None, *, wait: float = PUBLISH_WAIT_SECONDS) -> str:
    """컨테이너를 만들고 처리가 끝나면 공개한다. 돌려주는 값은 스레드 글 id."""
    user = os.environ["THREADS_USER_ID"]
    params = {"media_type": "IMAGE", "image_url": image_url, "text": text} if image_url else {"media_type": "TEXT", "text": text}
    container = _post(f"{user}/threads", params)["id"]
    deadline = time.time() + wait + STATUS_POLL_SECONDS * STATUS_POLL_MAX
    time.sleep(min(wait, 30))
    while not _container_ready(container):
        if time.time() > deadline:
            raise RuntimeError(f"container {container}: 처리가 끝나지 않았습니다")
        time.sleep(STATUS_POLL_SECONDS)
    return _post(f"{user}/threads_publish", {"creation_id": container})["id"]


def notify_post(base: str, post_id: int, title: str, doc: dict, *, force: bool = False) -> bool:
    if str(doc.get("lang") or "ko") == "en":
        return False
    if not configured():
        print("[스레드] 설정 없음(THREADS_ACCESS_TOKEN·THREADS_USER_ID) — 건너뜁니다")
        return False
    try:
        info = notify_telegram.post_info(base, post_id)
        if info.get("status") != "publish":
            print(f"[스레드] 글 {post_id}이(가) 공개 상태가 아닙니다({info.get('status')}) — 건너뜁니다")
            return False
        if notify_telegram.is_republish(info) and not force:
            print(f"[스레드] 글 {post_id}은(는) 다시 올린 글 — 올리지 않습니다")
            return False
        text = compose(doc, title, info["link"])
        thread_id = publish(text, info.get("image_url"))
        print(f"[스레드] 올림: {info['link']} (thread {thread_id})")
        return True
    except Exception as error:   # noqa: BLE001 — 알림 실패가 발행을 실패시키면 안 된다
        print(f"[스레드 실패] {error}")
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("post_id", type=int)
    parser.add_argument("manuscript", type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    doc = json.loads(args.manuscript.read_text(encoding="utf-8"))
    base = (os.environ.get("WORDPRESS_URL") or "https://fermata.it.kr").rstrip("/")
    ko = doc.get("ko") or doc
    return 0 if notify_post(base, args.post_id, str(ko.get("title")), doc, force=args.force) else 1


if __name__ == "__main__":
    raise SystemExit(main())
