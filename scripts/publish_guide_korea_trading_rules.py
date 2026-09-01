"""외국인 투자자용 상시 가이드 5편: 한국 시장의 거래 시간과 변동성 제어 장치.

시리즈: 외국인통합계좌 -> 환전 -> KOSPI vs KOSDAQ -> 세금·비용 -> (이번 편) 거래 규칙.

출처 (2026-09-01 확인):
- 프리마켓 07:00-08:00 / 정규장 09:00-15:30 / 애프터마켓 16:00-20:00,
  2026-06-29 시행, 2027-12 24시간 거래 목표: Korea Times, Korea Herald
- 넥스트레이드(ATS) 외국인 비중 1월 약 14%(출범 후 4월 5% 미만에서 상승),
  주식 수·유동성은 본장보다 적음: Korea Herald
- 가격제한폭 +-30% (2015-06-15부터), 동적/정적 VI, 2분+랜덤엔드: MDPI 논문, KRX 자료
- 서킷브레이커 8/15/20%, 1·2단계 20분 중단, 3단계 당일 종료, 마감 40분 전 미적용
- 사이드카: KOSPI200 선물 +-5% 1분 지속 시 프로그램매매 5분 정지
- 2026-07-28 KOSPI 8.04% 급락, 10:14경 서킷브레이커 발동(2026년 8번째, 사상 14번째),
  삼성전자 -9.45%, SK하이닉스 -11.01%: Korea Times, UPI, Seoul Economic Daily
- 공매도: 2025-03-31 전면 재개(약 2,700개 전 종목), NSDS 도입: CNBC, KED Global
- 결제주기 T+2: Clearstream
- 수능일 1시간 지연 개장(11월 셋째 목요일): 다수 보도
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.publish_guide import publish_guide  # noqa: E402

SLUG = "korean-market-trading-hours-and-halts"
TITLE = "Korea's Trading Day Just Doubled: Hours, Price Limits, and Halts Foreign Investors Should Know"

SECTIONS = [
    {
        "heading": "The trading day changed on June 29, 2026",
        "body": (
            "For decades the Korean equity market ran on a single, tidy schedule: 09:00 to 15:30 "
            "Seoul time, no lunch break, and that was the day. On June 29, 2026, the Korea "
            "Exchange added sessions on both ends. There is now a pre-market from 07:00 to 08:00 "
            "and an after-hours market from 16:00 to 20:00, with the regular session unchanged in "
            "between. Total trading time went from roughly six and a half hours to about twelve.\n\n"
            "KRX has been explicit that this is a first step, not an endpoint — the stated goal is "
            "around-the-clock trading by December 2027, driven by competition with exchanges "
            "abroad that have been extending their own hours.\n\n"
            "For someone investing from outside Korea, the practical consequence is the part worth "
            "internalizing. Seoul is 13 hours ahead of New York in winter and 14 in summer, which "
            "historically meant the Korean regular session ran while the U.S. slept — 09:00 in "
            "Seoul is 19:00 or 20:00 the previous evening on the U.S. East Coast. The new "
            "after-hours session, running to 20:00 KST, reaches back toward the U.S. morning; the "
            "07:00 pre-market extends the other direction. The window in which a U.S.-based "
            "investor can trade Korean stocks at a civilized local hour is meaningfully wider than "
            "it was before June."
        ),
    },
    {
        "heading": "Longer hours are not the same as better hours",
        "body": (
            "The caveat matters as much as the change. Liquidity does not stretch simply because "
            "the session does. Market participants have been blunt that institutional investors "
            "care primarily about depth and tight bid-ask spreads, and both thin out in extended "
            "sessions. A price you can get at 11:00 in the regular session is not necessarily "
            "available at 19:00.\n\n"
            "There is also more than one venue now. Nextrade, Korea's alternative trading system, "
            "has drawn growing foreign participation — foreign investors accounted for roughly 14% "
            "of its volume in January, up from under 5% shortly after launch — but it lists far "
            "fewer stocks than the main exchange and carries thinner liquidity.\n\n"
            "The sensible reading: treat the extended sessions as a convenience for reacting to "
            "news, not as the place to build or exit a position of any size. If you are putting on "
            "a real position, the regular session is still where the market actually is."
        ),
    },
    {
        "heading": "The ±30% wall: Korea's daily price limit",
        "body": (
            "Korean stocks cannot move more than 30% up or down from their base price in a single "
            "day. The band was widened to ±30% on June 15, 2015, and applies to ordinary shares as "
            "well as depositary receipts, ETFs, ETNs and beneficiary certificates on both KOSPI "
            "and KOSDAQ.\n\n"
            "U.S. investors have no equivalent instinct for this. In New York, a stock that "
            "collapses on bad news simply keeps trading down. In Seoul, it stops at the limit and "
            "stays there, often with a queue of unfilled sell orders behind it — the price is at "
            "the floor, but that does not mean you can get out at the floor. Sellers can be locked "
            "in, and the remaining pressure spills into the following session.\n\n"
            "The mirror image applies on the way up. A stock pinned to the +30% ceiling looks like "
            "a spectacular gain, and sometimes is, but the limit itself tells you nothing about "
            "where the price would have settled without it."
        ),
    },
    {
        "heading": "Volatility interruptions: the two-minute pause you will eventually hit",
        "body": (
            "Well before a stock reaches the daily limit, Korea has a finer-grained brake. The "
            "volatility interruption, or VI, comes in two forms. A dynamic VI triggers when a "
            "single order moves the price beyond a threshold band — roughly 2% to 6%, depending on "
            "the security. A static VI triggers when cumulative moves across many orders push the "
            "price about 10% away from its reference.\n\n"
            "When either fires, continuous trading in that stock stops and a call auction takes "
            "its place for about two minutes, ending at a randomized moment between 2:00 and 2:30 "
            "so the reopening cannot be gamed. Orders accumulate, cross at a single price, and "
            "continuous trading resumes.\n\n"
            "None of this is a trading halt in the American sense — no news pending, no regulatory "
            "review. It is an automatic cooling mechanism that fires many times a day across the "
            "market, and it is completely routine. If you place a market order into a fast-moving "
            "Korean stock and it appears to hang, a VI is the most likely explanation."
        ),
    },
    {
        "heading": "Circuit breakers and sidecars: when the whole market stops",
        "body": (
            "At the index level, Korea runs a three-stage market-wide circuit breaker keyed to the "
            "KOSPI's decline from the previous close. An 8% fall sustained for one minute halts "
            "trading for 20 minutes. A 15% fall triggers a second 20-minute halt. A 20% fall ends "
            "the session for the day. Notably, market-wide breakers are not applied in the final "
            "40 minutes before the close, which prevents a halt from silently becoming an early "
            "close.\n\n"
            "Alongside them sits the sidecar, a narrower tool: when KOSPI 200 futures move ±5% and "
            "hold it for a minute, program trading is suspended for five minutes to let the "
            "arbitrage-driven order flow drain out.\n\n"
            "These are not museum pieces. On July 28, 2026, the KOSPI fell 8.04% and the circuit "
            "breaker fired at around 10:14 in the morning, halting the market for 20 minutes, with "
            "Samsung Electronics down 9.45% and SK Hynix down 11.01% as investors dumped "
            "semiconductor names on doubts about AI capital spending. It was the eighth "
            "circuit-breaker activation of 2026 alone, and the fourteenth on record.\n\n"
            "That frequency is the point worth carrying away. A market this concentrated in "
            "semiconductors moves as a bloc when the AI trade is repriced, and the index-level "
            "brakes get used."
        ),
    },
    {
        "heading": "Settlement, short selling, and a calendar with its own logic",
        "body": (
            "Korean equity trades settle on a T+2 basis — two business days after the trade — "
            "across regular and after-hours sessions alike. That is one day slower than the U.S. "
            "market's current T+1 cycle, so proceeds from a Korean sale free up later than a U.S. "
            "investor may expect, which matters if you are funding one purchase with another "
            "sale.\n\n"
            "Short selling, which Korea banned for 16 months, has been fully restored since March "
            "31, 2025 and now covers all listed stocks — roughly 2,700 names — rather than the 350 "
            "large caps that were exempted during the partial phase. The restoration came packaged "
            "with a naked short-selling detection system built to flag illegal shorts in real "
            "time.\n\n"
            "Finally, the calendar. KRX closes for Korean public holidays, which follow the lunar "
            "calendar for Seollal and Chuseok and therefore move every year — a Korean market "
            "holiday will rarely coincide with one of your own. And once a year, on the third "
            "Thursday of November, the market opens an hour late so the country's college entrance "
            "exam can proceed without traffic: aircraft are grounded during the English listening "
            "section, and the exchange simply starts at 10:00. It is the only equity market in the "
            "world that reschedules itself around a test."
        ),
    },
]

INSIGHT_SECTION = {
    "heading": "Two mechanics worth understanding before you need them",
    "stories": [
        {
            "heading": "What actually happens when a Korean stock stops moving",
            "body": (
                "The three brakes stack, and they fire in a predictable order as a move gets "
                "larger. A single aggressive order trips a dynamic VI first. Sustained pressure "
                "across many orders trips a static VI. Only an extreme move reaches the ±30% daily "
                "limit, and only an index-wide collapse brings in the circuit breaker.\n\n"
                "Knowing which one you are looking at tells you how long you will be waiting and "
                "what happens at the other end. A VI resolves itself in about two minutes through "
                "a call auction. A circuit breaker takes 20. The daily limit does not resolve at "
                "all — it holds until the next session, and that is the one that can genuinely "
                "trap a position."
            ),
            "icon": "shield",
            "image_query": "trading floor screens",
            "table": [
                {"label": "Dynamic VI", "value": "Single order moves price ~2–6% → ~2 min auction"},
                {"label": "Static VI", "value": "Cumulative move ~10% → ~2 min auction"},
                {"label": "Daily price limit", "value": "±30% from base price → holds until next session"},
                {"label": "Circuit breaker L1 / L2 / L3", "value": "KOSPI −8% / −15% / −20% → 20 min / 20 min / session ends"},
                {"label": "Sidecar", "value": "KOSPI 200 futures ±5% for 1 min → program trading paused 5 min"},
            ],
        },
        {
            "heading": "The trading day, before and after June 29, 2026",
            "body": (
                "The regular session did not move. What changed is what sits on either side of it, "
                "and the total window in which a Korean stock can be traded at all.\n\n"
                "For a U.S.-based holder, the after-hours session is the more useful of the two "
                "additions: running to 20:00 in Seoul, it overlaps the early hours of the U.S. "
                "business day in a way the old schedule never did. Whether that overlap is "
                "tradable in practice depends entirely on the liquidity in the individual name — "
                "which, in the extended sessions, is the open question rather than the settled "
                "one."
            ),
            "icon": "coin",
            "image_query": "clock on a city building",
            "chart": {
                "title": "KRX trading hours per day (KST)",
                "type": "stat",
                "labels": ["Before June 29, 2026", "After"],
                "data": [6.5, 12],
                "unit": "h",
            },
        },
    ],
}

CLOSING = {
    "heading": "The takeaway",
    "body": (
        "Korea's market is not structurally exotic, but it is governed by brakes that a U.S. "
        "investor has no muscle memory for. Prices stop at ±30%. Individual stocks pause for two "
        "minutes at a time, routinely, without any news attached. The whole market halts at −8%, "
        "and in 2026 that has already happened eight times. Trades settle a day later than they "
        "would at home.\n\n"
        "The June 2026 extension of trading hours is the biggest structural change to the trading "
        "day in years, and it genuinely helps investors in other time zones — with the honest "
        "caveat that a longer session is not automatically a liquid one.\n\n"
        "This guide describes market rules as of September 2026. Session rules for the new "
        "pre-market and after-hours windows are still bedding in, and not every broker offers "
        "access to every session — confirm with yours which windows you can actually trade in "
        "before you plan around them."
    ),
}

TAGS = [
    "KOSPI",
    "KOSDAQ",
    "Korea Exchange",
    "trading hours",
    "circuit breaker",
    "price limit",
    "short selling",
    "foreign investors",
]

if __name__ == "__main__":
    post_id = int(sys.argv[1]) if len(sys.argv) > 1 else None
    publish_guide(
        slug=SLUG,
        title=TITLE,
        sections=SECTIONS,
        closing=CLOSING,
        insight_section=INSIGHT_SECTION,
        tags=TAGS,
        post_id=post_id,
    )
