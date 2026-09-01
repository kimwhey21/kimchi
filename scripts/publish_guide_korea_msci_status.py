"""외국인 투자자용 상시 가이드 7편: 한국이 아직 신흥국인 이유(MSCI 2026 결정).

시리즈: 외국인통합계좌 -> 환전 -> KOSPI vs KOSDAQ -> 세금·비용 -> 거래 규칙 ->
기업 조사 -> (이번 편) MSCI 선진국 지수 편입.

이 편은 시리즈의 결론편 성격입니다. MSCI가 한국을 신흥국에 남겨둔 이유로 든
항목들이 1~6편이 설명한 장치들과 정확히 겹치기 때문입니다 — 원화 태환성(2편),
투자자 ID·외국인통합계좌(1편), 공매도 컴플라이언스(5편).

출처 (2026-09-01 확인):
- 2026-06-23(미국)/24(한국) MSCI 2026 시장분류 결과: 한국 신흥국 유지, 관찰대상국
  등재도 안 됨. 사유로 역외 원화 태환성 제한, 투자자 ID 제도, 옴니버스 계좌·실물
  이전(in-kind transfer)의 실제 활용 저조, 공매도 재개 후 컴플라이언스 부담,
  사전 결제자금(pre-funding) 부담: Korea Times, CNBC, Bloomberg
- 1992년 신흥국 지수 편입, 2008년 관찰대상국 등재, 2014년 6월 제외
  (원화 태환성 + 거래소 시세 데이터 사용 제한): KEIA, MSCI 문서
- MSCI EM 지수 국가 비중(2026-07-31 기준): 대만 26.63%, 중국 21.38%, 한국 20.33%
  (justETF, MSCI EM 지수 팩트시트 기준일과 동일)
- 편입 시 패시브 유입 추정 200억~400억 달러(수년에 걸쳐):
  Natixis 알리시아 가르시아-에레로, IFR 인터뷰
- CLSA: 편입되면 "큰 연못의 큰 물고기에서 아주 작은 물고기"가 된다 (Korea Times)
- BofA: "MSCI는 대개 실행·사용성·일관성의 지속적 증거를 본다" (Korea Times)
- 외환시장 24시간 개장 2026-07-06 시행, 역외 원화 결제 2026년 9월 시범 →
  2027년 1월 본격 시행: 파이낸셜뉴스 Q&A, 코리아타임스, 아시아경제
- RFI(역외 외국금융기관) 약 73개사 등록, 거래량 비중 1% 남짓: 아시아경제
- 영문 공시 의무 확대 시점을 2028년에서 2027년 3월로 앞당기는 방안 검토: Korea Herald

숫자 주의: KOSPI 연중 등락률·고점은 집계 사이트마다 값이 달라 확인되지 않아
본문에 쓰지 않았습니다. 지수 비중과 유입 추정치는 위 출처를 그대로 인용합니다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.publish_guide import publish_guide  # noqa: E402

SLUG = "korea-msci-emerging-market-status-2026"
TITLE = "Korea Is Still an Emerging Market: What MSCI's 2026 Decision Means for Foreign Investors"

SECTIONS = [
    {
        "heading": "The label did not change, and that is the interesting part",
        "body": (
            "In late June 2026, MSCI published its annual market classification review and left "
            "Korea where it has been since 1992: in the emerging markets index. Korea was not "
            "upgraded. It was not even added to the watchlist that normally precedes an upgrade.\n\n"
            "For an individual foreign investor this is easy to file under news that does not "
            "concern you. You can already buy Korean stocks directly — that is what the first "
            "guide in this series is about — and an index label does not change what your broker "
            "will let you do.\n\n"
            "It is worth a closer look anyway, for one reason: the objections MSCI listed are not "
            "abstract governance complaints. They are the same frictions you meet when you open "
            "the account, convert the money and place the order. Reading the decision is a "
            "reasonably efficient way to understand what is still awkward about investing in "
            "Korea from abroad, written by people whose job is to be precise about it."
        ),
    },
    {
        "heading": "What MSCI Actually Objects To",
        "body": (
            "Four things carried the decision, and each one has a lived equivalent.\n\n"
            "The currency comes first. MSCI's headline concern is the limited convertibility of "
            "the won in the offshore market, and that is the reason the currency mechanics in "
            "guide two look the way they do: your dollars become won through a chain that "
            "ultimately runs through Korea, on Korea's schedule.\n\n"
            "Then the identification system and omnibus accounts. Korea requires foreign "
            "investors to be identified in a way most developed markets do not, and the omnibus "
            "structure meant to soften that — the foreign integrated account this series opens "
            "with — is, in MSCI's words, still limited in operational adoption. The plumbing "
            "exists. It is not carrying much water yet.\n\n"
            "Short selling and pre-funding are the third item. Korea's short-selling ban was "
            "lifted in March 2025, but MSCI says the compliance regime that came back with it "
            "leaves participants with significant operational burdens, and that early "
            "pre-settlement funding requirements remain a burden of their own — you must have the "
            "cash in place earlier than a developed-market desk would expect.\n\n"
            "The fourth is in-kind transfers and off-exchange transactions. Moving positions "
            "between accounts without selling them, and trading off-exchange, are both more "
            "restricted than institutional investors are used to. This is invisible to a retail "
            "investor and decisive for a large fund."
        ),
    },
    {
        "heading": "Korea has been here before",
        "body": (
            "This is not a first attempt. Korea entered the emerging markets index in 1992, was "
            "added to the developed-market watchlist in 2008, sat on it for six years, and was "
            "removed in 2014. The reasons given then were the limited convertibility of the won "
            "and restrictions on the use of exchange data.\n\n"
            "Twelve years later, the first item on the list is the same. That is the context for "
            "how much Korea has changed in the last two years, which is genuinely a lot:\n\n"
            "Foreign financial institutions have been able to trade directly in Seoul's onshore FX "
            "market since January 2024. On July 6, 2026, that market moved to near-continuous "
            "trading, running from Monday morning to Saturday morning. An offshore won settlement "
            "system — letting foreign institutions hold and settle won for clients without "
            "routing through a Korean bank's business day — is due to begin a pilot in September "
            "2026 and full operation in January 2027.\n\n"
            "And yet. Roughly 73 foreign institutions are registered to trade onshore, and they "
            "account for about 1% of volume. That gap between what is permitted and what is "
            "actually used is, more or less, MSCI's whole argument. As a Bank of America "
            "economist put it after the decision, MSCI typically looks for sustained evidence of "
            "implementation, usability and consistency — not for rules on paper."
        ),
    },
    {
        "heading": "An upgrade would not be an unambiguous win",
        "body": (
            "The assumption behind most upgrade coverage is that reclassification would be good "
            "for Korean share prices. That is a claim, not an arithmetic certainty, and the "
            "reason is index weight.\n\n"
            "As of July 31, 2026, Korea was about 20.3% of the MSCI Emerging Markets index — the "
            "third-largest country weight, behind Taiwan at roughly 26.6% and China at roughly "
            "21.4%. In a developed-market index, Korea would be a low-single-digit weight sitting "
            "among the United States, Japan and Europe. A CLSA strategist described the change as "
            "going from a big fish in a little pond to a very small fish.\n\n"
            "Both flows are real, and they run in opposite directions. Funds tracking "
            "developed-market indices would have to buy: one estimate, from Natixis, puts passive "
            "inflows at roughly $20–40 billion spread over several years. Funds with "
            "emerging-market-only mandates would have to sell, mechanically, regardless of what "
            "they think of Korean companies.\n\n"
            "Which effect dominates, and over what period, is not something anyone can tell you "
            "with confidence in advance. The distributional point is easier: buying from "
            "developed-market trackers concentrates in the largest, most liquid names, while "
            "emerging-market selling touches everything Korea has in the index. Large caps would "
            "likely fare better than the rest of the market."
        ),
    },
    {
        "heading": "What to watch instead of the June headline",
        "body": (
            "MSCI reviews classifications every June, so there will be another headline in June "
            "2027. It is close to the least informative thing to wait for, because by the time it "
            "arrives the outcome has already been determined by things that are observable now.\n\n"
            "The reclassification path itself is slow by design: a market is added to a watchlist, "
            "reviewed for at least a year, announced, and only then implemented. Even the fast "
            "version of Korea's remaining path is measured in years, not months. What moves it "
            "along is usage, and usage is visible:\n\n"
            "Does the offshore won settlement system actually launch in January 2027, and do "
            "foreign institutions register for it? Does the share of onshore FX volume from "
            "registered foreign institutions rise meaningfully above 1%? Does omnibus account "
            "adoption pick up, or does it stay the theoretical convenience MSCI says it currently "
            "is? Separately, regulators have been considering pulling the next phase of mandatory "
            "English disclosure forward to March 2027 from 2028 — relevant to the research problem "
            "guide six covers, and a reasonable proxy for how seriously the foreign-investor "
            "agenda is being pursued.\n\n"
            "Those are the numbers that will decide the 2027 and 2028 reviews. The review itself "
            "is the scoreboard, not the game."
        ),
    },
]

INSIGHT_SECTION = {
    "heading": "Two things worth internalizing",
    "stories": [
        {
            "heading": "Why a label moves money at all",
            "body": (
                "An index classification is not a quality rating, and MSCI is not saying Korean "
                "companies are worse than Japanese ones. It is saying something narrower and more "
                "mechanical: how easily a large foreign institution can get money in, hold it, "
                "hedge it and get it out.\n\n"
                "That matters because trillions of dollars are managed against index benchmarks by "
                "funds that do not choose countries — they hold what the index holds. Membership "
                "therefore determines which pools of money are structurally obliged to own Korean "
                "shares, which is a different question from whether Korean shares are attractive. "
                "You are free to buy Korea today. A pension fund benchmarked to a developed-market "
                "index is not."
            ),
            "icon": "scale",
            "image_query": "seoul city skyline at night",
            "table": [
                {"label": "What the label is", "value": "A measure of market access, not company quality"},
                {"label": "Who it binds", "value": "Index-tracking funds, which must hold what the index holds"},
                {"label": "Who it does not bind", "value": "You — direct access already exists"},
                {"label": "Korea today", "value": "≈20.3% of the emerging markets index (July 31, 2026)"},
                {"label": "Korea if upgraded", "value": "A low-single-digit weight in a much larger index"},
            ],
        },
        {
            "heading": "The same complaint, twelve years apart",
            "body": (
                "Comparing the 2014 removal from the watchlist with the 2026 decision is the "
                "fastest way to see what has and has not moved. The currency sits at the top of "
                "both lists. What is new in 2026 is a set of complaints about implementation "
                "rather than prohibition — the omnibus account exists but is barely used, short "
                "selling is legal again but operationally heavy.\n\n"
                "That shift is arguably progress: it is easier to fix a take-up problem than a "
                "ban. It also explains why the 24-hour FX market and the offshore won settlement "
                "system matter more than another round of announcements. They are aimed at the "
                "one complaint that has survived both reviews."
            ),
            "icon": "coin",
            "image_query": "stock exchange trading screens",
            "table": [
                {"label": "2014 — why Korea was dropped", "value": "Won convertibility; restrictions on use of exchange data"},
                {"label": "2026 — still first on the list", "value": "Limited convertibility of the won offshore"},
                {"label": "2026 — investor identification", "value": "ID system; omnibus accounts barely used in practice"},
                {"label": "2026 — short selling", "value": "Compliance burden since the ban was lifted; pre-funding"},
                {"label": "2026 — institutional plumbing", "value": "Limits on in-kind transfers and off-exchange trades"},
            ],
        },
    ],
}

CLOSING = {
    "heading": "The takeaway",
    "body": (
        "Korea's classification says almost nothing about whether Korean companies are worth "
        "owning, and almost everything about how easily large foreign money can move in and out. "
        "For an individual investor with direct access, the practical content of MSCI's 2026 "
        "decision is a list of frictions you have probably already noticed, confirmed by an "
        "outside party.\n\n"
        "If you want to follow the story, ignore the annual verdict and watch the plumbing: "
        "whether the offshore won settlement system launches on schedule in January 2027, whether "
        "registered foreign institutions grow past about 1% of onshore FX volume, and whether the "
        "foreign integrated account starts being used at scale rather than merely existing. Those "
        "are the things MSCI said it is measuring.\n\n"
        "And treat the standard framing — upgrade means inflows means rally — with some caution. "
        "Korea is roughly a fifth of the emerging markets index and would be a small fraction of a "
        "developed one. Money would arrive from developed-market trackers and leave from "
        "emerging-market ones, and reasonable people disagree about the net. This guide describes "
        "the position as of September 2026."
    ),
}

TAGS = [
    "MSCI",
    "Korean stocks",
    "KOSPI",
    "emerging markets",
    "developed market status",
    "foreign investors",
    "Korean won",
    "market access",
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
        focus_keyword="Korea MSCI developed market status",
    )
