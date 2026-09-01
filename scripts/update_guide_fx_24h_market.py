"""가이드 2편(환전, post 71)에 2026년 7월 외환시장 24시간 개장 내용을 추가합니다.

**기존 본문은 지우지 않고 섹션 하나를 끼워 넣습니다.** 2편이 다루는 "환전에
얼마가 드는가"는 지금도 맞는 내용입니다. 틀린 게 아니라 **빠진 것**이
있습니다 — 2026년 7월 6일부터 서울 외환시장이 사실상 24시간 돌아가면서
"언제 환전할 수 있는가"가 바뀌었는데, 8월 29일에 쓴 원문에는 그 얘기가
한 글자도 없습니다.

publish_guide(post_id=71)로 통째로 다시 렌더링하지 않는 이유:
1. 2편은 지금 스크립트가 남아 있지 않은 초기 글이라 sections 구조를 그대로
   복원할 수 없습니다. 복원하려다 문장이 미묘하게 바뀔 위험이 있습니다.
2. update_draft()는 본문을 통째로 갈아끼우므로 add_series_nav.py가 붙여 놓은
   시리즈 목차가 날아갑니다.
그래서 add_series_nav.py와 같은 방식(이미 올라간 HTML을 부분 수정)을 씁니다.

덤으로, 2편 본문에는 짝 없는 `</script>` 닫는 태그가 하나 들어 있습니다(초기
수작업 HTML의 잔재로 보입니다). 브라우저는 무시하지만 같이 지웁니다.
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

POST_ID = 71
MARKER = "mb-fx-24h"          # 다시 실행할 때 이전 삽입분을 찾아내는 표식
UPDATED_LABEL = "Updated 2026-09-01"


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


_ICON_CLOCK = (
    '<circle cx="16" cy="16" r="10"/>'
    '<line x1="16" y1="16" x2="16" y2="10"/>'
    '<line x1="16" y1="16" x2="20.5" y2="18.5"/>'
)
_ICON_GLOBE = (
    '<circle cx="16" cy="16" r="10"/>'
    '<ellipse cx="16" cy="16" rx="4.6" ry="10"/>'
    '<line x1="6" y1="16" x2="26" y2="16"/>'
)
# 저울 아이콘은 이미 이 글의 "Auto-convert vs. manual conversion"에서 쓰고 있어서,
# 같은 글 안에서 아이콘이 겹치지 않도록 동전 아이콘을 씁니다.
_ICON_COIN = (
    '<circle cx="16" cy="16" r="10"/>'
    '<line x1="16" y1="10" x2="16" y2="22"/>'
    '<line x1="12" y1="13" x2="20" y2="13"/><line x1="12" y1="19" x2="20" y2="19"/>'
)


def _head(icon: str, heading: str) -> str:
    return (
        '  <div class="mb-story-head">\n'
        '    <span class="mb-story-icon"><svg viewBox="0 0 32 32" fill="none" '
        'stroke="currentColor" stroke-width="1.6" stroke-linecap="round" '
        f'stroke-linejoin="round">{icon}</svg></span>\n'
        f"    <h3>{heading}</h3>\n"
        "  </div>\n"
    )


SECTION = (
    f'\n  <h2 class="{MARKER}">Update: The Won Now Trades Almost Around the Clock</h2>\n'
    "\n"
    "  <p>Everything above is about what conversion costs. Since this guide was first "
    "published, <em>when</em> you can convert has changed — and the change is big enough "
    "to deserve its own section.</p>\n"
    "\n"
    "  <p>On Monday, July 6, 2026, Seoul&#39;s foreign exchange market moved to "
    "near-continuous trading. The schedule it replaced was already an extension: the "
    "traditional 9:00 a.m. to 3:30 p.m. session had been stretched to 2:00 a.m. the "
    "following day back in July 2024. The new one opens Monday morning and does not "
    "close until Saturday morning.</p>\n"
    "\n"
    '  <div class="mb-table-wrap">\n'
    '    <table class="mb-data-table">\n'
    "      <tbody>\n"
    "        <tr><td>Before (from July 2024)</td><td>9:00 a.m. to 2:00 a.m. the next day, "
    "Korean time</td></tr>\n"
    "        <tr><td>Now (from July 6, 2026)</td><td>Monday 6:00 a.m. to Saturday 6:00 a.m. "
    "Korean time while New York is on daylight saving time; 7:00 a.m. to 7:00 a.m. "
    "otherwise</td></tr>\n"
    "        <tr><td>Still closed</td><td>Weekends and January 1. Korean public holidays "
    "are tradable, but settlement waits for the next bank business day</td></tr>\n"
    "      </tbody>\n"
    "    </table>\n"
    "  </div>\n"
    "\n"
    + _head(_ICON_COIN, "Why it happened, and why it isn&#39;t finished")
    + "\n"
    "  <p>The stated goal is to make the won usable as an international currency, and "
    "behind that, to get Korea reclassified by MSCI from emerging to developed market. "
    "In June 2026 MSCI declined again — it did not even add Korea to the review watchlist "
    "— citing the limited convertibility of the won offshore, the investor identification "
    "system, and the fact that omnibus accounts, the foreign integrated account this "
    "series opens with, are still barely used in practice.</p>\n"
    "\n"
    "  <p>The numbers behind that complaint are worth knowing, because they explain why "
    "an open market has not yet become a busy one. Foreign financial institutions have "
    "been allowed to trade directly in Seoul&#39;s onshore market since January 2024, and "
    "roughly 73 are registered — but they account for only about 1% of trading volume. "
    "Meanwhile something like 80% of won forward activity still happens offshore in "
    "non-deliverable forwards, against a global average nearer 21%. The door was opened; "
    "the traffic has not moved through it yet.</p>\n"
    "\n"
    + _head(_ICON_CLOCK, "What this changes for you — and what it doesn&#39;t")
    + "\n"
    "  <p><strong>What changes:</strong> the rate your broker quotes now references a "
    "market that is awake while New York is. The old pattern — deciding to buy a Korean "
    "stock in the evening in New York and either accepting whatever automatic conversion "
    "you are given or waiting for Seoul to open — is less often forced on you.</p>\n"
    "\n"
    "  <p><strong>What doesn&#39;t:</strong> this is an interbank market, not a retail "
    "one. Whether your own broker passes 24-hour pricing through to its conversion screen "
    "is a broker-by-broker question, and worth asking before you assume it. Settlement "
    "still follows bank business days, so a trade placed on a Korean holiday settles "
    "later, not sooner. The 3:30 p.m. closing rate is still the official reference many "
    "products quote, though the authorities plan to move to a time-weighted average. And "
    "none of this makes the markup in the table above any smaller — a market being open "
    "at 3 a.m. is not the same as a market being cheap at 3 a.m.</p>\n"
    "\n"
    + _head(_ICON_GLOBE, "Coming next: holding won without a Korean bank account")
    + "\n"
    "  <p>The larger change is still in progress. Korea is introducing registered offshore "
    "won settlement institutions — foreign financial institutions that can hold and settle "
    "won for their clients, with a new overnight settlement network at the Bank of Korea "
    "behind them. These institutions register rather than apply for a licence, which is "
    "the point: it is meant to be easy to become one. A pilot is due to begin in September "
    "2026, with full operation planned for January 2027.</p>\n"
    "\n"
    "  <p>If it works as designed, an investor in New York could obtain and hold won "
    "through an institution registered locally, during New York hours, instead of routing "
    "everything through a Korean bank&#39;s business day. Treat that as a plan with a date "
    "attached rather than a service you can use today — but it is the piece most likely to "
    "change the answer to &#34;how do my dollars become won&#34; for the second time in a "
    "year.</p>\n"
    "\n"
)

CLOSING_ADDITION = (
    f'\n    <p class="{MARKER}">One thing has changed since this guide was first '
    "published: the Seoul FX market now runs nearly around the clock, so timing is less "
    "of a constraint than it was. The cost questions above are unchanged — the market "
    "being open at 3 a.m. does not make your broker&#39;s spread any narrower.</p>\n"
)


def apply_update(content: str) -> str:
    """이미 삽입된 적이 있으면 걷어내고 새로 넣습니다(중복 방지)."""
    # 이전 삽입분 제거: 표식이 달린 h2부터 mb-closing 직전까지.
    content = re.sub(
        rf'\n  <h2 class="{MARKER}">.*?(?=  <div class="mb-closing">)',
        "",
        content,
        flags=re.DOTALL,
    )
    content = re.sub(rf'\n    <p class="{MARKER}">.*?</p>\n', "", content, flags=re.DOTALL)

    # 짝 없는 </script> 정리 (여는 태그가 없는 경우에만).
    if "<script" not in content:
        content = content.replace("</script>\n", "").replace("</script>", "")

    # 머리말에 갱신 날짜 표시.
    if UPDATED_LABEL not in content:
        content = content.replace(
            '<div class="mb-eyebrow">Investor Guide · 2026-08-29</div>',
            f'<div class="mb-eyebrow">Investor Guide · 2026-08-29 · {UPDATED_LABEL}</div>',
        )

    anchor = '  <div class="mb-closing">'
    if anchor not in content:
        raise RuntimeError("mb-closing 블록을 찾지 못했습니다. 구조가 바뀐 것 같습니다.")
    content = content.replace(anchor, SECTION + anchor, 1)

    # 마무리 문단 뒤에 한 문단 추가.
    closing_end = content.index(anchor) + len(anchor)
    tail_close = content.index("  </div>", closing_end)
    content = content[:tail_close] + CLOSING_ADDITION + content[tail_close:]
    return content


def main() -> None:
    base = os.environ["WORDPRESS_URL"].rstrip("/")
    auth = (os.environ["WORDPRESS_USERNAME"], os.environ["WORDPRESS_APP_PASSWORD"])

    r = _request(
        "GET", f"{base}/wp-json/wp/v2/posts/{POST_ID}",
        auth=auth, params={"context": "edit"},
    )
    content = r.json()["content"]["raw"]
    updated = apply_update(content)

    preview = Path(__file__).resolve().parent.parent / "output" / "guide_fx_updated_preview.html"
    preview.write_text(updated, encoding="utf-8")
    print(f"미리보기 저장: {preview} ({len(content)} → {len(updated)} chars)")

    if "--apply" not in sys.argv:
        print("실제 반영은 --apply 를 붙여 실행하세요. (지금은 미리보기만)")
        return

    _request(
        "POST", f"{base}/wp-json/wp/v2/posts/{POST_ID}",
        auth=auth, json={"content": updated},
    )
    print(f"완료: post {POST_ID} 갱신")


if __name__ == "__main__":
    main()
