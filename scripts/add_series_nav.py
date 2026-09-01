"""영문 가이드 6편 끝에 시리즈 목차를 붙입니다.

원칙: **본문은 한 글자도 바꾸지 않습니다.** 문단 사이에 링크를 끼워 넣으면 읽는
흐름이 끊기므로, 글이 완전히 끝난 뒤(마무리 문단 다음)에만 목차 블록을 답니다.
읽던 사람은 방해받지 않고, 다 읽은 사람에게만 다음 글이 보입니다.

기술적으로는 워드프레스에 이미 올라간 본문 HTML의 끝(`</div>` 직전)에 블록을
삽입합니다. 렌더링 템플릿(post.html.j2)은 건드리지 않습니다.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(str(Path(__file__).resolve().parent.parent / ".env"))

import os  # noqa: E402

import time  # noqa: E402

import requests  # noqa: E402


def _request(method: str, url: str, **kwargs):
    """이 사이트는 간헐적으로 502를 돌려줍니다. 몇 번 다시 시도합니다."""
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

# 독자가 밟아야 할 순서대로. (post_id, 짧은 제목, 한 줄 설명)
SERIES = [
    (67, "Getting access", "How foreigners can now buy Korean stocks directly"),
    (71, "Converting currency", "The FX math behind a won-denominated position"),
    (73, "Choosing a board", "What KOSPI vs. KOSDAQ actually tells you"),
    (194, "What it costs", "Taxes, transaction levies and the fees in between"),
    (197, "When you can trade", "Hours, price limits and the halts that stop them"),
    (200, "Doing the research", "Reading Korean filings in English on DART and KIND"),
]

_STYLE = (
    "<style>"
    ".mb-post .mb-series{margin-top:44px;padding-top:24px;border-top:1px solid var(--mb-border,#e5e3dd)}"
    ".mb-post .mb-series h2{margin:0 0 6px;font-size:17px}"
    ".mb-post .mb-series-note{margin:0 0 14px;font-size:13px;color:var(--mb-text-muted,#6b6a66)}"
    ".mb-post .mb-series-list{list-style:none;margin:0;padding:0}"
    ".mb-post .mb-series-item{display:grid;grid-template-columns:22px minmax(0,1fr);"
    "gap:10px;padding:9px 0;border-bottom:1px solid var(--mb-border,#e5e3dd);align-items:baseline}"
    ".mb-post .mb-series-num{color:var(--mb-text-muted,#6b6a66);font-size:12px;font-weight:700}"
    ".mb-post .mb-series-item a{color:var(--mb-text,#17171a);font-size:14px;font-weight:600;"
    "text-decoration-thickness:1px;text-underline-offset:2px}"
    ".mb-post .mb-series-desc{display:block;margin-top:2px;font-size:13px;font-weight:400;"
    "color:var(--mb-text-muted,#6b6a66)}"
    ".mb-post .mb-series-current{color:var(--mb-text-muted,#6b6a66);font-size:14px;font-weight:600}"
    "@media (max-width:480px){.mb-post .mb-series-item{grid-template-columns:1fr;gap:2px}}"
    "</style>"
)


def build_block(links: dict[int, str], current_id: int) -> str:
    rows = []
    for index, (post_id, label, desc) in enumerate(SERIES, start=1):
        num = f'<span class="mb-series-num">{index:02d}</span>'
        if post_id == current_id:
            body = (
                f'<span class="mb-series-current">{label} — you are here'
                f'<span class="mb-series-desc">{desc}</span></span>'
            )
        else:
            body = (
                f'<a href="{links[post_id]}">{label}'
                f'<span class="mb-series-desc">{desc}</span></a>'
            )
        rows.append(f'<li class="mb-series-item">{num}{body}</li>')
    return (
        f'{_STYLE}<section class="mb-series">'
        f"<h2>The Korea investing series</h2>"
        f'<p class="mb-series-note">Six guides, in the order they build on each other.</p>'
        f'<ul class="mb-series-list">{"".join(rows)}</ul>'
        f"</section>"
    )


def main() -> None:
    base = os.environ["WORDPRESS_URL"].rstrip("/")
    auth = (os.environ["WORDPRESS_USERNAME"], os.environ["WORDPRESS_APP_PASSWORD"])

    links: dict[int, str] = {}
    for post_id, _, _ in SERIES:
        r = _request("GET", f"{base}/wp-json/wp/v2/posts/{post_id}", auth=auth)
        links[post_id] = r.json()["link"]

    for post_id, label, _ in SERIES:
        r = _request(
            "GET", f"{base}/wp-json/wp/v2/posts/{post_id}",
            auth=auth, params={"context": "edit"},
        )
        content = r.json()["content"]["raw"]

        # 이미 붙어 있으면 옛 블록을 걷어내고 새로 답니다(중복 방지).
        content = re.sub(
            r"<style>\.mb-post \.mb-series\{.*?</section>", "", content, flags=re.DOTALL
        )

        block = build_block(links, post_id)
        marker = "\n<!-- /wp:html -->"
        if marker in content:
            # Custom HTML 블록 안, 본문 래퍼가 닫히기 직전에 삽입합니다.
            head, _, tail = content.rpartition("</div>")
            updated = f"{head}{block}</div>{tail}"
        else:
            updated = content + block

        _request(
            "POST", f"{base}/wp-json/wp/v2/posts/{post_id}",
            auth=auth, json={"content": updated},
        )
        print(f"  [{post_id}] {label}: 시리즈 목차 추가")


if __name__ == "__main__":
    main()
