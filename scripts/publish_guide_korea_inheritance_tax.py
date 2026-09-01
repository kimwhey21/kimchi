"""외국인 투자자용 상시 가이드 9편: 비거주자가 한국 주식을 남기고 사망했을 때.

시리즈: 외국인통합계좌 -> 환전 -> KOSPI vs KOSDAQ -> 세금·비용 -> 거래 규칙 ->
기업 조사 -> MSCI -> 상장폐지 -> (이번 편) 상속세.

4편이 "보유·매매에 드는 세금"을 다뤘다면 이번 편은 4편이 건드리지 않은 축입니다.
영어권 개인투자자용 자료가 사실상 없는 주제이고, 자료마다 설명이 엇갈려서
결론은 법조문으로 직접 확인했습니다.

출처 (2026-09-01 확인):
- 상증세법 제5조(상속재산 등의 소재지): "주식등의 소재지는 그 주식등을 발행한
  법인의 본점 또는 주된 사무소의 소재지" → 한국 법인 주식은 어느 나라 증권사에
  들어 있든 한국 소재 재산: 국가법령정보센터
- 제18조(기초공제): "거주자나 비거주자의 사망으로 상속이 개시되는 경우"
  2억원 공제 → 비거주자도 기초공제는 받음: 국가법령정보센터
- 제21조(일괄공제) 5억원, 제19조(배우자 상속공제): 조문이 모두 "거주자의 사망으로
  상속이 개시되는 경우"를 전제 → 비거주자 사망에는 적용 안 됨: 국가법령정보센터
  ※ Forvis Mazars 블로그는 "비거주자도 거주자와 같은 공제를 받는다"고 적어
    두었으나 조문과 배치되어 채택하지 않았습니다. 조문과 실무 자료
    (Ask Korea Law, 이순신 법률사무소) 쪽을 따랐습니다.
- 세율 10~50% (1억 이하 10%, 1억~5억 20%, 5억~10억 30%, 10억~30억 40%,
  30억 초과 50%): 다수 실무 자료 일치
- 신고기한: 피상속인이나 상속인 중 한 명이라도 비거주자면 사망한 달의 말일부터
  9개월(거주자만이면 6개월). 기한 내 신고 시 3% 공제, 과소신고 가산세 10~40%
- 상장주식 평가: 평가기준일 전후 각 2개월간 종가의 평균액
- 2026년 세제개편: 상장주식 상속·증여 평가기간을 늘리는 방안 포함. 최근 13개
  반기 중 12개 반기에서 PBR이 업종 하위 25%인 기업이 대상: Korea Herald
- 상속세 개편(75년 만의 개편, 자녀공제 5억·배우자 1조...): 2028년 시행 목표로
  발의됐으나 2026년 중반 현재 시행되지 않음. 최고세율 50%→40% 인하안은
  281명 중 180명 반대로 부결: Korea Herald
- 한미 상속세 조약 없음(소득세 조약은 사망 시 과세를 다루지 않음). 미국 거주자는
  Form 706-CE로 외국납부 상속세 세액공제 가능: IRS 조약 목록, 실무 자료
- 환산 기준: 2026-09-01 원/달러 1,372.70 (이 사이트가 그날 집계한 마감 수치)

주의: 세무 자문이 아닙니다. 본문에도 그렇게 적었습니다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.publish_guide import publish_guide  # noqa: E402

SLUG = "korean-inheritance-tax-foreign-investors"
TITLE = "If You Die Owning Korean Stocks: The Inheritance Tax Foreign Investors Don't See Coming"

SECTIONS = [
    {
        "heading": "A risk that never appears on your brokerage statement",
        "body": (
            "Every other guide in this series is about what happens while you are alive to "
            "manage it. This one is about the case nobody puts in a plan: you hold Korean shares, "
            "you die, and your family finds out what Korea does about it.\n\n"
            "The short version is that Korea taxes those shares, that the arithmetic is harsher "
            "for you than for a Korean family holding exactly the same portfolio, and that "
            "nothing in your brokerage account will warn you. There is no line item for it, no "
            "prompt when you buy, and no equivalent of the estate-tax exemption most foreign "
            "investors are used to at home.\n\n"
            "None of this is a reason not to own Korean stocks. It is a reason to know the "
            "numbers, because they are unusually specific and unusually easy to plan around once "
            "you do."
        ),
    },
    {
        # 템플릿이 알아서 이스케이프하므로 여기서는 그냥 아포스트로피를 씁니다.
        # &#39;로 미리 써 두면 &amp;#39;로 두 번 이스케이프돼 화면에 그대로 보입니다.
        "heading": "Why Where You Hold the Shares Doesn't Matter",
        "body": (
            "The first instinct is that shares bought through a US or European broker, held in "
            "that broker's custody chain, sitting in an account in your own country, are foreign "
            "assets. They are not, for this purpose.\n\n"
            "Korea's Inheritance and Gift Tax Act settles the question in a single clause. Under "
            "Article 5, the location of shares is the location of the head office of the company "
            "that issued them. Samsung Electronics shares are Korean property because Samsung "
            "Electronics is headquartered in Korea — not because of where your account is, which "
            "broker holds them, or which country's law governs your will.\n\n"
            "For a non-resident, only Korean-situs assets are taxable, and Korean-listed shares "
            "sit squarely inside that definition. The account structure the first guide in this "
            "series describes — a global broker linked to a Korean partner — does not change it."
        ),
    },
    {
        "heading": "The deduction cliff",
        "body": (
            "Here is where a foreign investor and a Korean family stop being treated the same.\n\n"
            "The basic deduction of ₩200 million applies to everyone. Article 18 says so "
            "explicitly: it covers inheritance opened by the death of a resident or a "
            "non-resident. That is roughly $146,000 at the September 1, 2026 exchange rate of "
            "₩1,372.7 to the dollar.\n\n"
            "Every other significant deduction is written differently. The ₩500 million lump-sum "
            "deduction in Article 21 and the spousal deduction in Article 19 both open with the "
            "same condition — inheritance commencing on the death of a resident. A non-resident "
            "decedent falls outside them. The financial-asset deduction goes the same way. "
            "Practitioners summarize the result as: the basic deduction and appraisal fees, and "
            "not much else. Debts are deductible only on narrow terms, essentially where the debt "
            "is secured against the Korean property itself, and funeral expenses are not "
            "deductible at all.\n\n"
            "So the same portfolio that a Korean family would shelter behind ₩500 million or more "
            "of deductions is sheltered, for you, behind ₩200 million."
        ),
    },
    {
        "heading": "What It Actually Costs",
        "body": (
            "Korea taxes the estate, not each heir's share, at progressive rates: 10% on the "
            "first ₩100 million of the taxable base, 20% to ₩500 million, 30% to ₩1 billion, 40% "
            "to ₩3 billion, and 50% above that.\n\n"
            "Run it on a portfolio of ₩500 million — about $364,000. Subtract the ₩200 million "
            "basic deduction and the taxable base is ₩300 million. The tax is ₩10 million on the "
            "first slice and ₩40 million on the second: ₩50 million, or 10% of everything held.\n\n"
            "Run it on ₩1.5 billion, about $1.09 million. The base is ₩1.3 billion and the tax "
            "comes to ₩360 million — 24% of the position. Filing on time earns a 3% reduction of "
            "the computed amount; under-reporting draws penalties of 10% to 40%.\n\n"
            "These are illustrations of the rate structure, not a computation of anyone's "
            "liability. Real estates carry facts these numbers ignore."
        ),
    },
    {
        "heading": "The valuation window nobody expects",
        "body": (
            "One mechanic surprises people who assume the tax is based on the price on the day of "
            "death. It is not. Korean listed shares are valued at the average of daily closing "
            "prices over the two months before and the two months after the valuation date — a "
            "four-month window, half of which has not happened yet when someone dies.\n\n"
            "For a volatile small cap this cuts both ways and cannot be managed after the fact. "
            "It also means the tax base is knowable only two months after the death, which "
            "matters when the filing clock is already running.\n\n"
            "This is being tightened. Korea's 2026 tax overhaul lengthens the valuation period "
            "for inheritance and gift purposes at companies whose price-to-book ratio has ranked "
            "in the bottom quarter of their industry in 12 of the past 13 half-year periods. The "
            "target is controlling families suppressing a share price ahead of a transfer, which "
            "is a Korean governance problem rather than a foreign-investor one — but the rule "
            "applies to the shares, not to the shareholder."
        ),
    },
    {
        "heading": "Deadlines, and the treaty that does not exist",
        "body": (
            "The filing deadline is nine months from the end of the month in which the death "
            "occurred, rather than the six months that applies when everyone involved is a "
            "resident. The extension is automatic when the decedent or any heir is a "
            "non-resident. Nine months sounds generous until you consider that it includes "
            "obtaining Korean documents, appointing someone able to act in Korea, and waiting out "
            "a valuation window that does not close for two months.\n\n"
            "The second problem is that Korea has no inheritance or estate tax treaty with the "
            "United States, and the income tax treaty between them does not cover taxation at "
            "death. There is no treaty mechanism to allocate the tax between the two countries.\n\n"
            "What exists instead is domestic relief. A US estate can generally claim a credit for "
            "foreign death taxes paid on property situated in that country and included in the US "
            "gross estate, certified on Form 706-CE. Because Korean rates are high and the US "
            "exemption is large, the practical outcome for many US families is Korean tax owed and "
            "little or no additional US tax — but the credit is a mechanism with conditions, not "
            "an exemption, and investors in other countries need to check their own rules rather "
            "than assume this one."
        ),
    },
]

INSIGHT_SECTION = {
    "heading": "Two things worth knowing before you plan around this",
    "stories": [
        {
            "heading": "The reform everyone is waiting for has not happened",
            "body": (
                "Korea has been debating the first serious overhaul of its inheritance tax in 75 "
                "years. The proposal would move the system toward taxing what each heir receives "
                "rather than the estate as a whole, and would raise deductions substantially — a "
                "per-child deduction of ₩500 million and a spousal figure of ₩1 billion have both "
                "been discussed. The target date attached to it is 2028.\n\n"
                "It is not law. As of mid-2026 it had not taken effect, and a separate attempt to "
                "cut the top rate from 50% to 40% was voted down, 180 of 281 lawmakers against. "
                "Plan against the rules that exist. If the overhaul passes it will be a pleasant "
                "revision to your arithmetic, not the assumption underneath it."
            ),
            "icon": "scale",
            "image_query": "last will and testament document",
            "table": [
                {"label": "Basic deduction (resident or not)", "value": "₩200 million"},
                {"label": "Lump-sum deduction", "value": "₩500 million — residents only"},
                {"label": "Spousal deduction", "value": "₩500m–₩3bn — residents only"},
                {"label": "Rates", "value": "10% to 50%, on the estate"},
                {"label": "Proposed overhaul", "value": "Targeted at 2028, not enacted"},
            ],
        },
        {
            "heading": "What to check while it is still easy",
            "body": (
                "Three things are worth settling in advance, and none of them require a Korean "
                "lawyer to start.\n\n"
                "First, know roughly where your Korean holdings sit against ₩200 million, because "
                "that number decides whether this is paperwork or a real bill. Second, find out "
                "what your broker requires from an estate — global brokers differ sharply in how "
                "they handle a deceased client's foreign-market positions, and the answer is "
                "easier to get now than under a nine-month clock. Third, make sure whoever would "
                "handle your affairs knows the Korean holdings exist and that Korea taxes them; "
                "the most expensive version of this problem is the one discovered late.\n\n"
                "If the position is large enough that the arithmetic above produces a number that "
                "matters to you, that is the point at which professional advice stops being "
                "optional."
            ),
            "icon": "coin",
            # "hourglass on wooden desk"로는 아이맥이 놓인 책상 사진이 왔습니다.
            # 'sand timer'를 넣으니 실제 모래시계가 나옵니다.
            "image_query": "hourglass sand timer",
            "table": [
                {"label": "Filing deadline", "value": "9 months from month-end of death"},
                {"label": "If all parties resident", "value": "6 months"},
                {"label": "Listed share valuation", "value": "Average close, 2 months before and after"},
                {"label": "On-time filing", "value": "3% reduction of the tax"},
                {"label": "Under-reporting", "value": "10%–40% penalty"},
            ],
        },
    ],
}

CLOSING = {
    "heading": "The takeaway",
    "body": (
        "Korean shares are Korean property no matter whose platform they sit on, and when a "
        "non-resident dies owning them the deductions that make Korean inheritance tax "
        "manageable for a Korean family mostly do not apply. What is left is a ₩200 million "
        "basic deduction, rates from 10% to 50% on the estate, a valuation window that stays "
        "open for two months after the death, a nine-month filing deadline, and no treaty to "
        "divide the bill with your home country.\n\n"
        "The reason this is worth an article rather than a footnote is that almost nothing in the "
        "normal experience of buying a foreign stock signals any of it, and the reform that would "
        "soften it has not passed. The arithmetic is at least simple enough to check against your "
        "own position in a few minutes.\n\n"
        "This guide describes the rules as of September 2026 and is not tax or legal advice. "
        "Cross-border estates turn on facts — residency, domicile, how title is held, your own "
        "country's rules — that no general article can settle. If the numbers here are large "
        "enough to matter in your case, take them to a professional in both countries rather "
        "than to a search engine."
    ),
}

TAGS = [
    "inheritance tax",
    "Korean stocks",
    "non-resident",
    "estate planning",
    "foreign investors",
    "Korea tax",
    "KOSPI",
    "cross-border",
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
        focus_keyword="Korean inheritance tax non-resident",
        # 대표 이미지는 본문 사진과 별개로 받습니다(중복 방지). 한국임이 사진으로
        # 확인되는 대상으로 잡았고, 받은 뒤 눈으로 확인합니다.
        featured_image_query="korean traditional house roof tiles",
    )
