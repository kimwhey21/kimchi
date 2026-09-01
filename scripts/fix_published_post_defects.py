"""이미 발행된 글에 남아 있는 렌더링 결함 두 가지를 고칩니다.

둘 다 원인은 템플릿/렌더러 쪽이고, 이 스크립트는 **이미 올라간 글의 증상만**
고칩니다. 근본 원인은 아래에 적어 두었습니다(코덱스 영역이라 건드리지 않음).

1) 마크다운 볼드가 그대로 보임 — `**Periodic Disclosure**`
   원인: templates/post.html.j2가 본문을 `<p>{{ para }}</p>`로 출력하는데
   Jinja 자동 이스케이프가 걸려 있어 `**`도, `<strong>`도 문자 그대로 나갑니다.
   즉 본문 텍스트에는 마크다운을 쓸 수 없습니다.
   영향: 200번(영문 가이드 6편)에 5군데. 실제 사이트에 별표가 보입니다.

2) 여는 태그 없는 `</script>` 하나가 본문 끝에 남음
   원인: post.html.j2에서 `{% if has_insight_charts %}`가 여는 `<script>`만
   감싸고, 324행의 닫는 `</script>`는 if 블록 **밖**에 있습니다. 그래서
   insight_section은 있는데 chart가 없는 글은 닫는 태그만 출력됩니다.
   (publish_wordpress의 `<script>...</script>` 제거 정규식은 짝이 맞아야
   지워지므로 이 고아 태그는 그대로 통과합니다.)
   영향: 71, 173, 176번 + 이번 임시저장 244번.
   브라우저는 무시하므로 화면은 멀쩡하지만, 유효하지 않은 HTML입니다.

실행:
    python3 scripts/fix_published_post_defects.py            # 무엇을 고칠지만 출력
    python3 scripts/fix_published_post_defects.py --apply    # 실제 반영
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(str(Path(__file__).resolve().parent.parent / ".env"))

# 고아 </script>가 확인된 글 + 마크다운 볼드가 남은 글
TARGET_IDS = [71, 173, 176, 200, 244]

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)


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


def fix(content: str) -> tuple[str, list[str]]:
    notes: list[str] = []

    # 여는 <script>가 아예 없을 때만 고아 닫는 태그를 지웁니다.
    if "<script" not in content and "</script>" in content:
        count = content.count("</script>")
        content = content.replace("</script>\n", "").replace("</script>", "")
        notes.append(f"고아 </script> {count}개 제거")

    # `**텍스트**` -> <strong>텍스트</strong>
    # 본문은 이미 HTML이라 여기서는 <strong>이 그대로 살아납니다.
    bold_count = len(_BOLD_RE.findall(content))
    if bold_count:
        content = _BOLD_RE.sub(r"<strong>\1</strong>", content)
        notes.append(f"마크다운 볼드 {bold_count}군데를 <strong>으로 변환")

    return content, notes


def main() -> None:
    base = os.environ["WORDPRESS_URL"].rstrip("/")
    auth = (os.environ["WORDPRESS_USERNAME"], os.environ["WORDPRESS_APP_PASSWORD"])
    apply_changes = "--apply" in sys.argv

    for post_id in TARGET_IDS:
        r = _request(
            "GET", f"{base}/wp-json/wp/v2/posts/{post_id}",
            auth=auth, params={"context": "edit"},
        )
        data = r.json()
        content = data["content"]["raw"]
        updated, notes = fix(content)

        title = data["title"]["raw"][:40]
        if not notes:
            print(f"  [{post_id}] {title}: 고칠 것 없음")
            continue

        print(f"  [{post_id}] {title} ({data['status']}): {', '.join(notes)}")
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
