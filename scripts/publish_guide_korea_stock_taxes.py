"""외국인 투자자용 상시 가이드 4편: 한국 주식 보유 시 실제로 내는 세금·비용.

시리즈 앞 세 편(외국인통합계좌 / 환전 / KOSPI vs KOSDAQ)에 이어지는 글입니다.
본문은 API 호출 없이 이 스크립트를 부르는 세션이 직접 조사해 작성했습니다.

출처 (2026-09-01 확인):
- 증권거래세 0.15% -> 0.20% (2026-01-01 양도분부터, KOSPI/KOSDAQ 모두):
  PwC Tax Summaries, Korea - Corporate - Other taxes
- 배당 원천징수 20% + 지방소득세 10% 부가 = 22%, 미국 조약 10%/15%,
  2026-01-01부터 실질귀속자 입증서류 제출 의무:
  PwC Tax Summaries, Korea - Corporate - Withholding taxes
- 비거주자 상장주식 양도차익: 양도일 속한 연도 및 직전 5년간 25% 미만 보유 +
  국내 고정사업장 없음 -> 비과세. 해당 없으면 양도가액 11%와 양도차익 22% 중 적은 금액.
- 2026년 고배당 상장기업 배당소득 분리과세(거주자 개인 대상, 14%~ 누진):
  Korea Herald, PwC Significant developments
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.publish_guide import publish_guide  # noqa: E402

SLUG = "korean-stock-taxes-and-costs"
TITLE = "The Real Cost of Owning Korean Stocks: Taxes and Fees Foreign Investors Pay in 2026"

SECTIONS = [
    {
        "heading": "The cost most people miss: Korea taxes the sale, not the profit",
        "body": (
            "Almost every guide to buying Korean stocks explains the brokerage side and stops "
            "there. The part that catches foreign investors off guard is simpler and harder to "
            "avoid: Korea levies a securities transaction tax on the value of every sale, "
            "whether the trade made money or lost it.\n\n"
            "The rate went up this year. For share transfers made on or after January 1, 2026, "
            "the tax on listed shares traded on KOSPI and KOSDAQ rose from 0.15% to 0.20% of the "
            "sale proceeds, inclusive of the special tax for rural development. On KOSPI, that "
            "0.20% is the sum of a 0.05% securities transaction tax — new in 2026, the first "
            "time the main board has carried one — and the 0.15% rural development levy that was "
            "already there. KOSDAQ reaches the same 0.20% through a single rate. KONEX stays at "
            "0.1%, and unlisted shares are taxed at 0.35%.\n\n"
            "The mechanics matter more than the number. The tax is charged on gross proceeds, not "
            "on gain, so a position you sell at a loss is still taxed. It is collected by your "
            "broker at settlement rather than billed to you later, which is why it tends to show "
            "up as an unexplained line item on a trade confirmation instead of a bill you can "
            "plan around."
        ),
    },
    {
        "heading": "Dividends: 22% by default, 15% if your treaty says so",
        "body": (
            "Korea withholds tax on dividends at the moment they are paid. The statutory rate for "
            "non-residents is 20%, plus a local income surtax equal to 10% of that tax, which "
            "brings the all-in rate to 22%. Nothing is billed to you afterward — the money simply "
            "never arrives.\n\n"
            "If you are resident in a country with a Korean tax treaty, you may be entitled to "
            "less. For U.S. residents, the standard treaty rate on portfolio dividends is 15%; a "
            "10% rate exists but applies only in narrow ownership situations that retail "
            "investors will not meet. Treaty rates across Korea's network generally land between "
            "5% and 15%, depending on the country and the size of the holding.\n\n"
            "The treaty rate is not automatic. Your broker acts as withholding agent and has to "
            "hold documentation establishing where you are resident and that you are the "
            "beneficial owner of the dividend before it can apply the lower rate. And as of "
            "January 1, 2026, Korea tightened this: withholding agents must now file the "
            "treaty-rate application together with supporting evidence of substantive ownership "
            "with the competent tax office, by the end of February following the year the income "
            "was paid. In practice this means the paperwork your broker asks you for is no longer "
            "a formality it can quietly skip — if it is missing, you are taxed at 22%."
        ),
    },
    {
        "heading": "Capital gains: most foreign retail investors owe Korea nothing",
        "body": (
            "This is the part that surprises people in the other direction. A non-resident who "
            "sells listed Korean shares at a profit is generally not subject to Korean capital "
            "gains tax at all, provided two conditions hold: the investor did not own 25% or more "
            "of the company's total issued shares at any point during the year of the sale or the "
            "preceding five years, and has no permanent establishment in Korea.\n\n"
            "For anyone buying a few hundred shares of Samsung Electronics or SK Hynix, the 25% "
            "threshold is not a live concern. It exists to catch strategic and control-level "
            "stakes, not portfolios.\n\n"
            "Where the exemption does not apply — and no treaty relief covers it — Korean tax is "
            "charged at the lower of 11% of the sale proceeds or 22% of the realized gain. It is "
            "also worth knowing what did not happen: the financial investment income tax (FIIT) "
            "that Korea had scheduled for 2025, which would have taxed retail investment gains "
            "broadly, was withdrawn before taking effect. The older regime described here is what "
            "remains in force.\n\n"
            "Being exempt in Korea does not make the gain untaxed. Your own country almost "
            "certainly taxes it — U.S. investors report the sale on their own return exactly as "
            "they would a domestic one."
        ),
    },
    {
        "heading": "What the whole bill looks like on a real position",
        "body": (
            "Taxes are only part of what separates the price on the screen from the money that "
            "reaches your account. The full stack, in the order you meet it:\n\n"
            "First, the FX conversion. Dollars have to become won, and the spread your broker "
            "applies there is usually the largest single cost of a small Korean position — larger "
            "than the commission and often larger than the transaction tax. Second, the "
            "commission, which varies widely by broker and by whether you are routed through an "
            "integrated account. Third, the 0.20% transaction tax when you sell. Fourth, 15% to "
            "22% withheld from any dividend along the way. And finally, conversion back to your "
            "home currency, where you pay the spread a second time.\n\n"
            "None of these individually is large enough to change an investment case. Together, "
            "on a position held for a few months, they can consume a meaningful share of a modest "
            "gain — which is an argument for sizing positions so the fixed costs are not "
            "proportionally punishing, and for treating Korean equities as multi-year holdings "
            "rather than short-term trades."
        ),
    },
    {
        "heading": "Why Korean dividends themselves may be getting larger",
        "body": (
            "One more 2026 change is worth understanding even though foreign investors cannot "
            "claim it directly. From January 1, 2026, Korea applies separate, lower taxation to "
            "dividend income that resident individuals receive from qualifying high-dividend "
            "listed companies — starting at 14% on the first ₩20 million and rising through "
            "higher brackets above that, in place of the ordinary progressive treatment. It runs "
            "through the fiscal year that includes December 31, 2028.\n\n"
            "The qualification test is what makes it interesting: a company's dividend must not "
            "have fallen versus the FY2024 base year, and its payout ratio must be at least 40% — "
            "or at least 25% with a year-on-year increase of 10% or more. In other words, the tax "
            "break belongs to the shareholder but the behavior it is designed to change belongs "
            "to the company.\n\n"
            "It appears to be working at the margin. Of the firms that announced dividends for "
            "2025, 398 — about 44.8% — met the eligibility criteria, nearly double the 287 "
            "companies (24.2%) that would have qualified on FY2024 settlement terms.\n\n"
            "A foreign holder is still taxed under the treaty rate, not this domestic schedule. "
            "But if a Korean company raises its payout ratio to keep its domestic shareholders "
            "inside the 14% bracket, the larger dividend reaches every holder on the register, "
            "wherever they live. That is the channel through which this reform matters to you."
        ),
    },
]

INSIGHT_SECTION = {
    "heading": "Two things worth working through before you trade",
    "stories": [
        {
            "heading": "A worked example: ₩10,000,000 bought, sold a year later at ₩11,000,000",
            "body": (
                "Assume a U.S.-resident investor with treaty documentation on file, a position "
                "bought for ₩10,000,000 and sold twelve months later for ₩11,000,000, having "
                "collected ₩200,000 in dividends along the way.\n\n"
                "Korean capital gains tax on the ₩1,000,000 profit: nothing, because the 25% "
                "ownership threshold is nowhere close. Securities transaction tax: 0.20% of the "
                "₩11,000,000 sale value, or ₩22,000 — charged on the proceeds, not the gain. "
                "Dividend withholding at the 15% treaty rate: ₩30,000, leaving ₩170,000 of the "
                "₩200,000 declared.\n\n"
                "Korean tax on the round trip therefore comes to ₩52,000 against a ₩1,200,000 "
                "gross return — a little over 4% of it. Note what is not in that figure: the FX "
                "spread on the way in and out, and your broker's commission, neither of which is "
                "a tax and both of which are frequently larger."
            ),
            "icon": "scale",
            "image_query": "seoul city skyline at dusk",
            "table": [
                {"label": "Capital gains tax (Korea)", "value": "₩0 — under the 25% threshold"},
                {"label": "Securities transaction tax", "value": "₩22,000 (0.20% of ₩11,000,000)"},
                {"label": "Dividend withholding at 15%", "value": "₩30,000 of ₩200,000"},
                {"label": "Total Korean tax", "value": "₩52,000"},
                {"label": "Not included", "value": "FX spread, broker commission"},
            ],
        },
        {
            "heading": "Getting the treaty rate is a paperwork problem, not a tax problem",
            "body": (
                "The difference between 22% and 15% on every dividend you will ever receive from "
                "a Korean company comes down to whether a form reached the right desk in time. "
                "Since January 2026 the filing obligation on your broker is explicit and dated, "
                "which cuts both ways: it is harder for the step to be skipped, and easier for a "
                "missing document on your side to cost you the rate.\n\n"
                "Three things are worth confirming with your broker before the first dividend "
                "rather than after it. Whether they hold current residency documentation for you. "
                "Whether they apply treaty rates at source, or withhold at 22% and leave you to "
                "reclaim the difference — a materially worse outcome, because reclaims are slow "
                "and some are never filed. And what they report to you at year end, since the "
                "foreign tax withheld is what supports a foreign tax credit claim at home.\n\n"
                "For U.S. investors, tax actually withheld by Korea is generally creditable "
                "against U.S. tax on the same income, subject to the limitations of the foreign "
                "tax credit rules. That is the mechanism that keeps the dividend from being taxed "
                "twice — but it depends on the withholding being documented, which returns you to "
                "the paperwork."
            ),
            "icon": "shield",
            "image_query": "signing documents at a desk",
            "chart": {
                "title": "Withholding on a Korean dividend, by documentation status",
                "type": "stat",
                "labels": ["No treaty documentation", "Treaty rate applied (US resident)"],
                "data": [22, 15],
                "unit": "%",
            },
        },
    ],
}

CLOSING = {
    "heading": "The takeaway",
    "body": (
        "Korea's tax treatment of foreign retail investors is, on balance, mild: no capital gains "
        "tax for ordinary position sizes, a dividend rate that a treaty can cut to 15%, and a "
        "transaction tax that is real but small. The 2026 changes tightened two edges of that "
        "picture — the transaction tax rose from 0.15% to 0.20%, and claiming a treaty rate now "
        "carries a documented filing obligation with a February deadline.\n\n"
        "The costs most likely to erode a Korean position are still the ones that are not taxes "
        "at all: the FX spread, paid twice, and the commission. Confirm those with your broker "
        "with the same care you would give a tax question.\n\n"
        "This guide describes the rules as of September 2026 and is not tax advice. Withholding "
        "rates depend on your country of residence and the documentation your broker holds, and "
        "your home country's treatment of the same income is a separate question entirely. "
        "Confirm your own position with your broker or a tax professional before you invest."
    ),
}

TAGS = [
    "Korean stocks",
    "withholding tax",
    "securities transaction tax",
    "tax treaty",
    "foreign investors",
    "KOSPI",
    "KOSDAQ",
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
