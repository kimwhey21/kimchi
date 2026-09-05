"""네이버에 한 번 로그인해서 세션을 프로필에 남깁니다. 처음 한 번만 돌리면 됩니다.

    python -m scripts.bench_login

창이 열리면 **"로그인 상태 유지"를 켜고** 로그인하세요. 그래야 쿠키가 세션
쿠키로 발급되지 않아 다음 날에도 남습니다. 앞서 한 번 만료된 이유가 이것입니다 —
저장된 `NID_AUT`/`NID_SES`가 전부 세션 쿠키였습니다.

로그인이 끝나면 유료 글 하나를 열어 실제로 본문이 보이는지 확인하고 끝냅니다.
"""
from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright

from scripts import bench_store as st

LOGIN_URL = ("https://nid.naver.com/nidlogin.login?url="
             "https%3A%2F%2Fcontents.premium.naver.com%2Ffinfarmer00%2Ffinfarmer")
# 잠금 확인용 유료 글 하나. 사라지면 최신 유료 글 id로 바꾸면 됩니다.
PROBE = "260905204330198kk"


def main() -> int:
    st.ensure_dirs()
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(st.PROFILE),
            headless=False,
            user_agent=st.UA,
            viewport={"width": 1200, "height": 900},
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(LOGIN_URL, timeout=60000)
        print("창에서 로그인하세요. '로그인 상태 유지'를 켜 두는 것이 중요합니다.")
        print("채널 화면으로 넘어가면 자동으로 확인하고 창을 닫습니다. (최대 5분 대기)")
        try:
            page.wait_for_url("**/contents.premium.naver.com/**", timeout=300000)
        except Exception:
            print("로그인 화면을 벗어나지 못했습니다. 다시 실행해 주세요.")
            ctx.close()
            return 1

        page.goto(st.POST_URL + PROBE, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2500)
        body = page.inner_text("body")
        ctx.close()

    if "프리미엄 구독자 전용" in body:
        print("로그인은 됐지만 유료 본문이 아직 잠겨 있습니다. 구독 계정이 맞는지 확인해 주세요.")
        return 2
    print(f"확인됨 — 유료 본문 {len(body):,}자를 읽었습니다.")
    print(f"세션 위치: {st.PROFILE}")
    print("이제 'python -m scripts.bench_watch'가 매일 알아서 돌아갑니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
