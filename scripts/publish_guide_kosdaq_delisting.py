"""외국인 투자자용 상시 가이드 8편: 강화된 상장폐지 요건(코스닥 중심).

시리즈: 외국인통합계좌 -> 환전 -> KOSPI vs KOSDAQ -> 세금·비용 -> 거래 규칙 ->
기업 조사 -> MSCI -> (이번 편) 상장폐지.

3편이 "코스닥이 어떤 시장인가"를 설명했다면, 이번 편은 그 시장에서 실제로
돈을 잃는 경로를 다룹니다. 2026년 7월 1일부터 주가·시가총액 기준이 크게
올라갔고, 8월 12~13일에 첫 관리종목 지정이 실제로 나왔습니다.

출처 (2026-09-01 확인):
- 시가총액 기준: 코스닥 40억 -> 150억(2026-01) -> 200억(2026-07-01) ->
  300억(2027-01-01), 코스피 300억 -> 500억(2027-01): 금융위 보도자료(영문),
  인포스탁데일리/알파경제
- 동전주 요건 신설: 30거래일 연속 주가 1,000원 미만이면 관리종목,
  이후 90거래일 중 45거래일 연속 기준을 회복하지 못하면 상장폐지: 금융위, 뉴스핌
- 실제 첫 적용(2026-08-12 발표, 8-13 지정): 개정 규정에 해당한 종목 총 36곳,
  이 중 기존 관리종목 6곳을 뺀 30곳이 신규 지정. 코스피·코스닥 합산 수치이며
  대부분이 코스닥: 뉴스핌, 인포스탁데일리(투자닷컴 전재)
  ※ 시장별·사유별 세부 숫자는 매체마다 달라 본문에 쓰지 않았습니다.
- 개선기간 1.5년 -> 1년 단축, 효율화 조치는 2026-04-01 시행: 금융위
- 완전자본잠식 반기 기준 심사 추가(2026년 상반기부터), 공시위반 벌점 15점 ->
  10점, 감사의견 미달 2회 연속이면 즉시 상장폐지 절차: 금융위, 신김 뉴스레터
- 거래소 시뮬레이션: 2026년 상장폐지 대상 약 150개사(기존 전망 약 50개사):
  금융위 보도자료
- 2026-08-03 시점 코스닥 1,820개사 중 316개사(17.36%)가 기준 미달.
  주가 1,000원 미만 149개사, 시가총액 200억원 미만 214개사: Seoul Economic Daily
- 정리매매: 7거래일, 30분 단위 단일가매매, 가격제한폭 없음.
  이후 K-OTC 상장폐지지정기업부에서 한시 거래, 첫날 기준가는 상장폐지 전
  마지막 종가와 직전 3거래일 평균 종가 중 낮은 값, 일일 ±30%: 나무위키/K-OTC 규정,
  디지털타임스
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.publish_guide import publish_guide  # noqa: E402

SLUG = "kosdaq-delisting-rules-2026"
TITLE = "Korea Is Purging Its Penny Stocks: What the New Delisting Rules Mean for Foreign Investors"

SECTIONS = [
    {
        "heading": "A rule you can be caught by without doing anything wrong",
        "body": (
            "Most delisting rules punish a company for something it did: fraud, a failed audit, "
            "an accounting restatement. Two of the tests Korea introduced on July 1, 2026 are "
            "different. They do not look at the business at all. They look at the share price and "
            "the market value.\n\n"
            "A KOSDAQ company can be profitable, honest and current on every filing, and still be "
            "put on the delisting track because its shares trade below ₩1,000 or because its "
            "market capitalization sits under ₩20 billion — roughly $14 million. If you own small "
            "Korean companies, this is a risk that arrived in your portfolio in July without any "
            "of those companies doing anything.\n\n"
            "This is not theoretical. On August 12, 2026 the exchange published the first list "
            "drawn up under the new standards, and it was not small."
        ),
    },
    {
        "heading": "The Two Tests That Are New",
        "body": (
            "The first is a minimum share price. A stock that closes below ₩1,000 for 30 "
            "consecutive trading days is designated an administrative issue — Korea's watch list.\n\n"
            "The second is a minimum market capitalization, and it is being ratcheted up on a "
            "published schedule rather than in one step. For KOSDAQ the floor was ₩4 billion until "
            "the start of 2026. It went to ₩15 billion in January, to ₩20 billion on July 1, and "
            "is set to reach ₩30 billion on January 1, 2027. That is a 7.5-fold increase inside "
            "twelve months. KOSPI is moving too, from ₩30 billion now to ₩50 billion in January "
            "2027.\n\n"
            "The direction of travel matters more than any single number. A company that clears "
            "the bar today may not clear the one arriving in January, and the schedule is public, "
            "which means the market can see who is close to the line before the exchange acts."
        ),
    },
    {
        "heading": "How the clock actually runs",
        "body": (
            "Designation is not delisting. It starts a recovery window, and the window is "
            "specific enough to be worth knowing precisely.\n\n"
            "Once a company is designated, it has 90 trading days. Within those 90 days it must "
            "close above the standard for 45 consecutive trading days. Not 45 days in total — 45 "
            "in a row. If it fails, the company becomes subject to delisting.\n\n"
            "The first application of this ran on schedule. On August 12, 2026 the exchange "
            "identified 36 issues across the two markets that met the new criteria; six were "
            "already on the watch list, so 30 companies were newly designated the following day. "
            "The overwhelming majority were KOSDAQ names. Their 90-day clocks are running now, "
            "which means the first delistings under these rules land in the first half of 2027."
        ),
    },
    {
        "heading": "The rest of the tightening, which is easy to miss",
        "body": (
            "The price and market-cap tests got the attention, but they arrived alongside a set of "
            "changes that shorten the distance between trouble and removal.\n\n"
            "The improvement period a company gets to fix a substantive problem was cut from a "
            "year and a half to one year, with the efficiency measures taking effect on April 1, "
            "2026. Full capital impairment is now assessed twice a year rather than once, so a "
            "company that erodes its equity in the first half no longer has until the annual "
            "report to be caught. The disclosure demerit threshold dropped from 15 points in a "
            "year to 10. And two consecutive years of an inadequate audit opinion now move "
            "straight to delisting procedures rather than through the older, slower ladder.\n\n"
            "The exchange's own simulation put roughly 150 companies in scope for delisting in "
            "2026, against about 50 under the previous rules. That is the scale of what changed: "
            "not a new category of misconduct, but a much faster and wider net."
        ),
    },
    {
        "heading": "What Happens to Your Shares",
        "body": (
            "This is the part that most English-language coverage skips, and it is the part that "
            "determines what you actually lose.\n\n"
            "When a delisting is confirmed, the stock enters a liquidation trading period lasting "
            "seven trading days. Two features of that window are unlike ordinary Korean trading. "
            "Orders are matched by single-price auction roughly every thirty minutes rather than "
            "continuously, and — critically — the ±30% daily price limit that applies to every "
            "other Korean stock does not apply here. A stock in liquidation trading can lose most "
            "of its remaining value in a single session, and routinely does.\n\n"
            "After those seven days the shares are no longer listed. Korea does provide an "
            "afterlife: the K-OTC market operates a segment for delisted issues, where the "
            "opening reference price is the lower of the final listed close and the average close "
            "of the preceding three sessions, with a ±30% daily limit restored. It is thin, but it "
            "is not nothing.\n\n"
            "The practical question for a foreign investor is whether your broker can reach any of "
            "it. Global brokers that offer Korean equities through a linked local partner do not "
            "necessarily support the over-the-counter market, and some restrict trading in "
            "administrative issues well before delisting. Ask before you need the answer, because "
            "the seven-day liquidation window may be the only exit you actually have — and it is "
            "seven days, not seven weeks."
        ),
    },
]

INSIGHT_SECTION = {
    "heading": "Two things to check this week",
    "stories": [
        {
            "heading": "How many companies this touches",
            "body": (
                "In early August 2026, before the first designations were published, one count put "
                "316 of KOSDAQ's 1,820 listed companies — 17.4%, about one in six — below at least "
                "one of the two new thresholds. Roughly 149 were trading under ₩1,000 and about "
                "214 had market values under ₩20 billion, with overlap between the two groups.\n\n"
                "Not all of them will be delisted. A rising market fixes both tests automatically, "
                "which is precisely why the exchange gives a 90-day window. But the arithmetic "
                "cuts the other way too: a weak stretch in small caps now converts directly into "
                "delisting risk in a way it did not a year ago, regardless of what any individual "
                "company reports."
            ),
            "icon": "scale",
            # 검색어 두 개를 버리고 이걸로 정했습니다. "stock market data screen decline"은
            # 5편(197번) 대표 이미지와 완전히 같은 사진이 나왔고(같은 파일, 152,316바이트),
            # "closed shop metal shutter street"는 이탈리아 피자집 셔터가 나왔습니다.
            # fetch_images의 중복 방지는 한 번의 실행 안에서만 동작하고, 추상적인 검색어는
            # 엉뚱한 나라 사진을 물어옵니다 — 한국임이 사진으로 확인되는 것만 씁니다.
            "image_query": "seoul office buildings business district",
            "table": [
                {"label": "KOSDAQ companies (early Aug 2026)", "value": "1,820"},
                {"label": "Below at least one new threshold", "value": "316 — about one in six"},
                {"label": "Trading under ₩1,000", "value": "≈149"},
                {"label": "Market cap under ₩20bn", "value": "≈214"},
                {"label": "First designations (Aug 13, 2026)", "value": "30 newly designated, 36 flagged"},
            ],
        },
        {
            "heading": "The thresholds are still moving",
            "body": (
                "Reading the current number alone will mislead you, because the standard is on a "
                "published escalator. The KOSDAQ market-cap floor has gone from ₩4 billion to ₩20 "
                "billion in a year and reaches ₩30 billion in January 2027; KOSPI goes to ₩50 "
                "billion at the same time.\n\n"
                "For an investor holding small Korean companies, the useful exercise is not "
                "\"does this clear the bar\" but \"does this clear the January bar, and by how "
                "much.\" A company at ₩25 billion is comfortably compliant today and fails on "
                "January 1 unless something changes. That gap is visible now, to anyone who looks."
            ),
            "icon": "coin",
            # 기준선이 계단식으로 올라간다는 내용이라 실제 계단 사진을 씁니다.
            # "korea exchange stock ticker board"로는 버스 주차장 사진이 나왔습니다.
            "image_query": "staircase steps concrete",
            "table": [
                {"label": "KOSDAQ — until Dec 2025", "value": "₩4bn market cap"},
                {"label": "KOSDAQ — January 2026", "value": "₩15bn"},
                {"label": "KOSDAQ — July 1, 2026", "value": "₩20bn, plus the ₩1,000 share price test"},
                {"label": "KOSDAQ — January 1, 2027", "value": "₩30bn"},
                {"label": "KOSPI — now / January 2027", "value": "₩30bn → ₩50bn"},
            ],
        },
    ],
}

CLOSING = {
    "heading": "The takeaway",
    "body": (
        "Korea decided to clear out its smallest listed companies, and it chose tests that are "
        "mechanical rather than judgmental: a share price and a market value, measured over "
        "consecutive trading days. That makes the risk unusually easy to screen for and unusually "
        "easy to ignore, because nothing about the company has to go wrong for it to apply.\n\n"
        "If you hold small KOSDAQ names, three checks are worth doing now rather than later. "
        "Whether the share price has been near ₩1,000. Whether the market value clears not just "
        "the current floor but the January 2027 one. And whether your broker will let you trade "
        "the stock through a watch-list designation and a seven-day liquidation window with no "
        "price limits, which is the mechanism through which the loss is actually realized.\n\n"
        "The larger point is the one guide three made about KOSDAQ generally, now with a deadline "
        "attached: the board is not a smaller version of KOSPI. It is a different risk, and Korea "
        "has just made that difference explicit. This guide describes the rules as of September "
        "2026; the thresholds are scheduled to rise again in January."
    ),
}

TAGS = [
    "KOSDAQ",
    "delisting",
    "Korean stocks",
    "KRX",
    "penny stocks",
    "foreign investors",
    "market regulation",
    "small caps",
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
        focus_keyword="KOSDAQ delisting rules",
    )
