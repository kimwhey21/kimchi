"""글이 공개되면 텔레그램 채널에 알린다 (2026-09-12, 사용자: 블로그 홍보 — 1번 텔레그램 채널).

왜
--
2026-09-12까지 방문자가 오는 통로는 검색 하나였다(외부 링크 0, 소셜 채널 없음). 한국 개인 투자자가 시황을 받아
보는 1순위 통로가 텔레그램 채널이라 글이 공개될 때마다 표지 + 요약 + 링크를 봇이 올린다. 채널 `@fermata_kr`
("Fermata주식이야기"), 봇 `fermata_post_bot`(채널 관리자). 토큰은 GitHub 시크릿 `TELEGRAM_BOT_TOKEN`과 로컬 `.env`에만 있다.

원칙
----
- 알림은 발행의 곁가지다. 토큰이 없으면 "설정 없음"을 찍고 건너뛰고, 보내기가 실패해도 발행을 되돌리거나 실패시키지
  않는다 — 대신 `[텔레그램 실패]`를 크게 찍는다(조용한 실패 금지).
- **다시 올린 글은 알리지 않는다.** 글의 최초 공개 시각(`date_gmt`)과 마지막 수정(`modified_gmt`)이 10분 넘게
  벌어져 있으면 재발행(옛 글 재작성·태그 정리·네이버용 본문 추가)이다. 채널에 같은 글이 두 번 가면 구독이 끊긴다.
- 영어 글은 보내지 않는다(한국어 채널).

    python -m src.notify_telegram <post_id> <원고.json> [--force]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

TIMEOUT = 30
REPUBLISH_GAP_SECONDS = 600
CAPTION_LIMIT = 1024
LABELS = {"kr": "코스피 마감 시황", "us": "뉴욕증시 마감", "프리뷰": "오늘 밤 미국장 프리뷰", "기준표": "Checkpoint",
          "주간 결산": "주간 결산", "다음 주 일정": "다음 주 일정", "가이드": "가이드", "이벤트": "증시 이벤트"}
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def configured() -> bool:
    return bool(os.environ.get("TELEGRAM_BOT_TOKEN")) and bool(os.environ.get("TELEGRAM_CHAT_ID"))


def label(doc: dict) -> str:
    if doc.get("market") in ("kr", "us"):
        return LABELS[str(doc["market"])]
    return LABELS.get(str(doc.get("series") or "기준표"), "새 글")


def summary(doc: dict, limit: int = 260) -> str:
    """Fermata's Take 앞 두 문장. 없으면 첫 절 첫 문단. 태그는 벗긴다."""
    ko = doc.get("ko") or doc
    take = re.sub(r"<[^>]+>", "", str((ko.get("closing") or {}).get("body") or "")).strip()
    if not take:
        first = ((ko.get("narrative") or [{}])[0].get("body") or "").split("\n\n")[0]
        take = re.sub(r"<[^>]+>", "", str(first)).strip()
    sentences = [s for s in _SENTENCE.split(take) if s.strip()]
    text = " ".join(sentences[:2]).strip()
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0].rstrip(",.") + "…"
    return text


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def compose(doc: dict, title: str, link: str) -> str:
    body = summary(doc)
    text = f"<b>{_escape(title)}</b>"
    if body:
        text += f"\n\n{_escape(body)}"
    text += f"\n\n{link}"
    return text[:CAPTION_LIMIT]


def post_info(base: str, post_id: int) -> dict:
    """공개 REST로 글의 주소·표지·시각을 읽는다(인증 불필요)."""
    response = requests.get(f"{base}/wp-json/wp/v2/posts/{post_id}", timeout=TIMEOUT, headers={"User-Agent": "Mozilla/5.0"},
                            params={"_fields": "link,featured_media,date_gmt,modified_gmt,status"})
    response.raise_for_status()
    post = response.json()
    image_url = None
    if post.get("featured_media"):
        media = requests.get(f"{base}/wp-json/wp/v2/media/{post['featured_media']}", timeout=TIMEOUT,
                             headers={"User-Agent": "Mozilla/5.0"}, params={"_fields": "source_url"})
        if media.ok:
            image_url = media.json().get("source_url")
    return {"link": post.get("link"), "image_url": image_url, "status": post.get("status"),
            "date_gmt": post.get("date_gmt"), "modified_gmt": post.get("modified_gmt")}


def is_republish(info: dict) -> bool:
    try:
        created = dt.datetime.fromisoformat(str(info.get("date_gmt")))
        modified = dt.datetime.fromisoformat(str(info.get("modified_gmt")))
    except (TypeError, ValueError):
        return False
    return (modified - created).total_seconds() > REPUBLISH_GAP_SECONDS


def send(text: str, image_url: str | None = None) -> dict:
    token, chat = os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"]
    api = f"https://api.telegram.org/bot{token}"
    if image_url:
        response = requests.post(f"{api}/sendPhoto", timeout=TIMEOUT,
                                 json={"chat_id": chat, "photo": image_url, "caption": text, "parse_mode": "HTML"})
        result = response.json()
        if result.get("ok"):
            return result
        print(f"[텔레그램] 사진 전송 실패({result.get('description')}) — 글로만 보냅니다")
    response = requests.post(f"{api}/sendMessage", timeout=TIMEOUT,
                             json={"chat_id": chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": False})
    return response.json()


def notify_post(base: str, post_id: int, title: str, doc: dict, *, force: bool = False) -> bool:
    """공개된 글 하나를 채널에 알린다. 돌려주는 값은 '보냈는가'. 예외를 밖으로 내지 않는다."""
    if str(doc.get("lang") or "ko") == "en":
        return False
    if not configured():
        print("[텔레그램] 설정 없음(TELEGRAM_BOT_TOKEN·TELEGRAM_CHAT_ID) — 알림을 건너뜁니다")
        return False
    try:
        info = post_info(base, post_id)
        if info.get("status") != "publish":
            print(f"[텔레그램] 글 {post_id}이(가) 공개 상태가 아닙니다({info.get('status')}) — 건너뜁니다")
            return False
        if is_republish(info) and not force:
            print(f"[텔레그램] 글 {post_id}은(는) 다시 올린 글(최초 {info['date_gmt']}, 수정 {info['modified_gmt']}) — 알리지 않습니다")
            return False
        text = compose(doc, f"{label(doc)} · {title}" if label(doc) not in title else title, info["link"])
        result = send(text, info.get("image_url"))
        if not result.get("ok"):
            print(f"[텔레그램 실패] {result.get('description')}")
            return False
        print(f"[텔레그램] 채널에 올림: {info['link']} (message {result['result'].get('message_id')})")
        return True
    except Exception as error:   # noqa: BLE001 — 알림 실패가 발행을 실패시키면 안 된다
        print(f"[텔레그램 실패] {error}")
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("post_id", type=int)
    parser.add_argument("manuscript", type=Path)
    parser.add_argument("--force", action="store_true", help="다시 올린 글이어도 보낸다(시험용)")
    args = parser.parse_args(argv)
    doc = json.loads(args.manuscript.read_text(encoding="utf-8"))
    base = (os.environ.get("WORDPRESS_URL") or "https://fermata.it.kr").rstrip("/")
    ko = doc.get("ko") or doc
    return 0 if notify_post(base, args.post_id, str(ko.get("title")), doc, force=args.force) else 1


if __name__ == "__main__":
    raise SystemExit(main())
