"""가이드 8편의 첫 소재에 대표 이미지와 겹치지 않는 새 사진을 넣습니다.

앞선 커밋에서 대표 이미지와 같은 본문 사진을 걷어냈더니 첫 소재가 사진 없이
남았습니다. 이 스크립트는 그 자리를 **새로 고른 사진**으로 채웁니다.

사진은 전부 실제로 내려받아 눈으로 확인했습니다. 확인 과정에서 걸러낸 것들:
- 'signing paperwork at desk' -> 194번이 이미 쓰고 있는 사진과 동일 파일
- 'korean won banknote' -> **중국 위안화(마오쩌둥) 지폐**. CLAUDE.md에 적힌
  그 사례가 그대로 재현됐습니다. 통화 지폐 검색은 쓰지 않기로 했습니다.
- 'red traffic light' -> 초록불이 켜진 사진. 거래 정지 설명에 정반대 신호
- 'price tag label on clothing' -> 실존 패션 브랜드 상품 태그
- 'currency exchange booth sign' -> 태국 길거리 환전소
- 'laptop screen trading platform desk' -> 암호화폐 거래 화면
- 'airport currency exchange rates display' -> 미국 은행 간판

Unsplash가 돌려주는 alt가 사진과 어긋나는 경우가 있어(예: 상자 사진에
"usb flash drive"), 어긋난 것은 ALT_OVERRIDE로 바로잡습니다.

실행:
    python3 scripts/restore_body_photos.py            # 미리보기
    python3 scripts/restore_body_photos.py --apply    # 실제 반영
"""
from __future__ import annotations

import html as html_mod
import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(str(Path(__file__).resolve().parent.parent / ".env"))

# post_id -> 넣을 사진. url/photographer는 Unsplash 응답 그대로입니다.
PHOTOS_PATH = Path(__file__).resolve().parent.parent / "config" / "guide_body_photos.json"

ALT_OVERRIDE = {
    67: "A passport and documents on a desk",
    71: "An electronic board displaying rates in blue digits",
    244: "A cardboard storage box with a label holder",
}


def _request(method: str, url: str, **kwargs):
    last = None
    for attempt in range(1, 5):
        try:
            r = requests.request(method, url, timeout=60, **kwargs)
            if r.status_code < 500:
                r.raise_for_status()
                return r
            last = f"HTTP {r.status_code}"
        except requests.RequestException as exc:
            last = repr(exc)
        if attempt < 4:
            print(f"    재시도 {attempt}/3 ({last})")
            time.sleep(4)
    raise RuntimeError(f"요청 실패: {url} ({last})")


def build_photo_html(photo: dict, alt: str) -> str:
    src = html_mod.escape(photo["url"], quote=True)
    alt_attr = html_mod.escape(alt, quote=True)
    credit = (
        f'<p class="mb-photo-credit">Photo: '
        f'<a href="{html_mod.escape(photo["photographer_url"], quote=True)}" '
        f'target="_blank" rel="noopener">'
        f'{html_mod.escape(photo["photographer"])}</a> / Unsplash</p>'
    )
    return (
        f'\n  <img class="mb-story-photo" src="{src}" alt="{alt_attr}" loading="lazy">\n'
        f"  {credit}\n"
    )


def insert_after_first_story_head(content: str, photo_html: str) -> str | None:
    """첫 소재 제목 블록 바로 뒤에 사진을 넣습니다.

    이미 사진이 있으면 그 사진을 갈아 끼웁니다(여러 번 실행해도 늘어나지 않게).
    """
    head = re.search(r'<div class="mb-story-head">.*?</div>', content, re.DOTALL)
    if not head:
        return None
    tail_start = head.end()
    existing = re.match(
        r'\s*<img class="mb-story-photo"[^>]*>'
        r'(?:\s*<p class="mb-photo-credit">.*?</p>)?',
        content[tail_start:],
        re.DOTALL,
    )
    if existing:
        return content[:tail_start] + photo_html + content[tail_start + existing.end():]
    return content[:tail_start] + photo_html + content[tail_start:]


def main() -> None:
    base = os.environ["WORDPRESS_URL"].rstrip("/")
    auth = (os.environ["WORDPRESS_USERNAME"], os.environ["WORDPRESS_APP_PASSWORD"])
    apply_changes = "--apply" in sys.argv

    photos = json.loads(PHOTOS_PATH.read_text(encoding="utf-8"))

    for post_id_str, photo in photos.items():
        post_id = int(post_id_str)
        post = _request(
            "GET", f"{base}/wp-json/wp/v2/posts/{post_id}",
            auth=auth, params={"context": "edit"},
        ).json()
        content = post["content"]["raw"]

        alt = ALT_OVERRIDE.get(post_id, photo.get("alt") or "")
        updated = insert_after_first_story_head(content, build_photo_html(photo, alt))
        if updated is None:
            print(f"  [{post_id}] 소재 제목 블록을 못 찾음 — 건너뜀")
            continue

        before = content.count('class="mb-story-photo"')
        after = updated.count('class="mb-story-photo"')
        print(f"  [{post_id}] {post['title']['raw'][:34]}: 본문 사진 {before} → {after}장 "
              f"({photo['query']})")
        if apply_changes:
            _request(
                "POST", f"{base}/wp-json/wp/v2/posts/{post_id}",
                auth=auth, json={"content": updated},
            )
            print("        -> 반영 완료")

    if not apply_changes:
        print("\n미리보기만 했습니다. 실제 반영은 --apply 를 붙여 실행하세요.")


if __name__ == "__main__":
    main()
