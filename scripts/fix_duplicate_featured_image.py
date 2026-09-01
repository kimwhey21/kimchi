"""이미 발행된 가이드에서 대표 이미지와 겹치는 본문 사진을 걷어냅니다.

증상: 글 맨 위 대표 이미지와 본문 첫 사진이 **같은 파일**입니다. 독자는 스크롤
한 번에 같은 사진을 두 번 봅니다. 8편 전부(67·71·73·194·197·200·244·262)가
해당됩니다.

원인: src/publish_guide.py가 insight 스토리의 첫 사진을 그대로 대표 이미지로
올리면서 본문에도 남겨 뒀습니다. 근본 원인은 같은 커밋에서 고쳤고, 이 스크립트는
**이미 나간 글**만 손봅니다.

방식: publish_guide로 다시 렌더링하지 않습니다. 다시 렌더링하면 Unsplash를
새로 검색해 지금 걸려 있는(눈으로 확인한) 사진이 다른 사진으로 바뀌고,
add_series_nav.py가 붙여 둔 시리즈 목차도 날아갑니다. 그래서 저장된 HTML에서
해당 <img>와 바로 뒤의 출처 문단만 들어내고, 출처는 "Featured photo: ..."로
글 끝(<footer> 앞)에 옮겨 답니다 — 사진이 본문에서 사라져도 표기는 남습니다.

실행:
    python3 scripts/fix_duplicate_featured_image.py            # 미리보기
    python3 scripts/fix_duplicate_featured_image.py --apply    # 실제 반영
"""
from __future__ import annotations

import html as html_mod
import os
import re
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(str(Path(__file__).resolve().parent.parent / ".env"))

GUIDE_IDS = [67, 71, 73, 194, 197, 200, 244, 262]
MARKER = "mb-featured-credit"


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


def strip_duplicate(content: str, featured_alt: str) -> tuple[str, str | None]:
    """대표 이미지와 alt가 같은 본문 사진 한 장(과 그 출처 문단)을 들어냅니다.

    반환: (수정된 본문, 들어낸 출처 문단의 안쪽 HTML 또는 None)
    """
    alt = html_mod.escape(featured_alt, quote=True)
    pattern = re.compile(
        r'\s*<img class="mb-story-photo"[^>]*?alt="' + re.escape(alt) + r'"[^>]*?>'
        r'(?:\s*<p class="mb-photo-credit">(.*?)</p>)?',
        re.DOTALL,
    )
    match = pattern.search(content)
    if not match:
        return content, None
    return content[: match.start()] + content[match.end():], match.group(1)


def add_featured_credit(content: str, credit_inner: str | None) -> str:
    if not credit_inner or MARKER in content:
        return content
    # 본문 사진 밑에 있던 "Photo: X / Unsplash"를 "Featured photo: ..."로 바꿔
    # 답니다. 사진 위치가 글 맨 위로 옮겨졌으니 표현도 그에 맞춥니다.
    inner = credit_inner.strip()
    inner = re.sub(r"^Photo:\s*", "Featured photo: ", inner)
    line = f'<p class="mb-photo-credit {MARKER}">{inner}</p>'
    if "<footer>" in content:
        return content.replace("<footer>", f"{line}\n  <footer>", 1)
    return content + line


def main() -> None:
    base = os.environ["WORDPRESS_URL"].rstrip("/")
    auth = (os.environ["WORDPRESS_USERNAME"], os.environ["WORDPRESS_APP_PASSWORD"])
    apply_changes = "--apply" in sys.argv

    for post_id in GUIDE_IDS:
        post = _request(
            "GET", f"{base}/wp-json/wp/v2/posts/{post_id}",
            auth=auth, params={"context": "edit"},
        ).json()
        content = post["content"]["raw"]
        title = post["title"]["raw"][:38]

        media_id = post.get("featured_media")
        if not media_id:
            print(f"  [{post_id}] {title}: 대표 이미지 없음 — 건너뜀")
            continue

        media = _request(
            "GET", f"{base}/wp-json/wp/v2/media/{media_id}", auth=auth,
        ).json()
        featured_alt = (media.get("alt_text") or "").strip()
        if not featured_alt:
            print(f"  [{post_id}] {title}: 대표 이미지 alt가 비어 있어 자동 판별 불가")
            continue

        before = content.count('class="mb-story-photo"')
        updated, credit_inner = strip_duplicate(content, featured_alt)
        if credit_inner is None and updated == content:
            print(f"  [{post_id}] {title}: 겹치는 본문 사진 없음")
            continue
        updated = add_featured_credit(updated, credit_inner)
        after = updated.count('class="mb-story-photo"')

        print(f"  [{post_id}] {title}: 본문 사진 {before}장 → {after}장, 출처는 글 끝으로")
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
