"""운영 알림 — 실패·건너뜀·하루 요약을 사장님 텔레그램 1:1 대화로 보낸다 (2026-09-12).

왜
--
루틴의 휴대폰 알림은 Claude 앱으로만 가고, GitHub Actions 실패는 메일로만 온다. 사용자: "어떤 게 실패했는지 어떤
상황인지 모니터링도 가능하면서 알림을 받아보고 싶다." 그래서 채널(`@fermata_kr`, 독자용)과 별개로 봇과 사장님의
1:1 대화(`TELEGRAM_ADMIN_CHAT_ID`)에 운영 소식을 보낸다.

    python -m src.alert "<메시지>" [--level ok|warn|fail]     # 워크플로의 실패 단계·맥 작업이 부른다
    python -m src.alert --whoami                              # /start 를 누른 사람의 chat_id 찾기(처음 한 번)

설정이 없으면 찍고 건너뛴다(알림 실패가 본 작업을 실패시키면 안 된다).
"""
from __future__ import annotations

import argparse
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

TIMEOUT = 20
ICON = {"ok": "✅", "warn": "⚠️", "fail": "❌", "info": "ℹ️"}


def configured() -> bool:
    return bool(os.environ.get("TELEGRAM_BOT_TOKEN")) and bool(os.environ.get("TELEGRAM_ADMIN_CHAT_ID"))


def send(message: str, level: str = "info") -> bool:
    if not configured():
        print(f"[알림 미설정] {ICON.get(level, '')} {message}")
        return False
    api = f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}"
    text = f"{ICON.get(level, '')} {message}".strip()
    try:
        r = requests.post(f"{api}/sendMessage", timeout=TIMEOUT,
                          json={"chat_id": os.environ["TELEGRAM_ADMIN_CHAT_ID"], "text": text[:4000], "disable_web_page_preview": True})
        ok = bool(r.json().get("ok"))
        if not ok:
            print(f"[알림 실패] {r.text[:200]}")
        return ok
    except Exception as error:   # noqa: BLE001
        print(f"[알림 실패] {error}")
        return False


def whoami() -> list[dict]:
    """봇에게 /start 를 보낸 대화 목록 — chat_id를 찾아 TELEGRAM_ADMIN_CHAT_ID에 넣는다."""
    api = f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}"
    r = requests.get(f"{api}/getUpdates", timeout=TIMEOUT).json()
    out = []
    for u in r.get("result", []):
        m = u.get("message") or u.get("my_chat_member", {})
        chat = (m or {}).get("chat") or {}
        if chat.get("type") == "private":
            out.append({"chat_id": chat.get("id"), "name": chat.get("first_name") or chat.get("username"), "text": (m.get("text") if isinstance(m, dict) else None)})
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("message", nargs="?")
    parser.add_argument("--level", default="info", choices=list(ICON))
    parser.add_argument("--whoami", action="store_true")
    args = parser.parse_args(argv)
    if args.whoami:
        rows = whoami()
        print(rows or "봇에게 /start 를 보낸 대화가 없습니다.")
        return 0
    if not args.message:
        parser.print_help()
        return 1
    return 0 if send(args.message, args.level) else 1


if __name__ == "__main__":
    sys.exit(main())
