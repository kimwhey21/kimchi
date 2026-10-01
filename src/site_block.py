"""본진이 진짜 화면 대신 호스팅의 봇 검사 화면을 돌려주는지 (2026-10-01).

카페24 서버는 자동 요청으로 보이면 `cupid.js`를 부르는 작은 HTML(쿠키 CUPID를 만든 뒤 `?ckattempt=N`으로 다시 부름)을 200으로
준다. Cloudflare를 거치면 접속 주소가 매번 달라 쿠키가 맞지 않고, 세 번 뒤 카페24(openresty)가 403을 낸다 — 2026-10-01 08시께부터
Cloudflare를 거친 방문자 전부가 이렇게 막혔다. 이 화면은 상태 코드가 200이라 "열렸다"로 읽히고, JSON을 기대한 곳은
`JSONDecodeError`로, 사이트맵을 기대한 곳은 "종목 사이트맵이 빠졌다"로 엉뚱하게 실패했다. 이 함수로 먼저 가려 한 줄로 말한다.
"""
from __future__ import annotations

MESSAGE = ("본진이 진짜 화면 대신 카페24 봇 검사 화면(cupid.js)을 돌려줍니다 — Cloudflare를 거친 방문자는 403입니다. "
           "카페24 보안 설정(봇 차단·스팸 쉴드)을 확인하거나 Cloudflare 프록시를 끄십시오")


def is_bot_challenge(text: str | bytes | None) -> bool:
    """응답 본문이 카페24 봇 검사 화면인가."""
    if not text:
        return False
    if isinstance(text, bytes):
        text = text[:4000].decode("utf-8", "ignore")
    head = text[:4000]
    return "/cupid.js" in head or ("toNumbers(" in head and "slowAES" in head) or ("ckattempt=" in head and "CUPID" in head)
