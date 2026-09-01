"""외국인 투자자용 상시 가이드 6편: 영어로 한국 기업 조사하는 법 (DART/KIND).

시리즈: 외국인통합계좌 -> 환전 -> KOSPI vs KOSDAQ -> 세금·비용 -> 거래 규칙 -> (이번 편) 기업 조사.

출처 (2026-09-01 확인):
- 영문 공시 의무 2단계: 2026-05-01부터 자산 2조원 이상 KOSPI 상장사로 확대
  (111개사 -> 265개사, 2024년 말 기준). 항목도 KRX 공시 전 항목(주요경영사항 55개,
  공정공시, 조회공시)으로 확대: FSC 보도자료, Korea JoongAng Daily
- 제출 시한: 자산 10조원 이상은 원칙적으로 국문 공시 당일, 신규 편입 2조원 이상은 3일 이내
- 대상은 KOSPI 한정. FSC가 KOSDAQ 대형주 적용을 검토 중
- englishdart.fss.or.kr 첫 화면 면책 문구(2026-09-01 스크린샷으로 직접 확인):
  "disclosures in English are made voluntarily with no legal effect and may not
   correspond to the original disclosures in Korean due to mistranslation,
   the user is advised to refer to the original filings in Korean"
- 영문 DART 검색 카테고리(직접 확인): Periodic Disclosure / Report on Major Issues /
  Issuance Disclosure / Equity Disclosure / Miscellaneous Disclosures /
  External Audit Matters / Fund Disclosure / Asset Securitization /
  Exchange Disclosure / Fair Trade Commission Disclosure
- Today's Disclosure 탭: ALL / KOSPI / KOSDAQ / KONEX / OTHERS / 5%·Executive / FUND,
  30초마다 갱신
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.publish_guide import publish_guide  # noqa: E402

SLUG = "researching-korean-companies-in-english"
TITLE = "How to Research a Korean Company in English: DART, KIND, and What the Translation Leaves Out"

SECTIONS = [
    {
        "heading": "More of Korea's corporate filings are in English than a year ago",
        "body": (
            "The practical objection to buying individual Korean stocks was never really access or "
            "cost. It was that you could not read the company. Filings were in Korean, earnings "
            "materials were in Korean, and the disclosures that actually move a stock arrived in "
            "Korean first and in English — if at all — whenever someone got around to it.\n\n"
            "That has been changing in stages. From January 2024, KOSPI-listed companies with more "
            "than ₩10 trillion in assets were required to file key disclosures in English: 111 "
            "companies, 26 categories of material information. On May 1, 2026, the requirement "
            "entered its second phase. The threshold dropped to ₩2 trillion in assets, expanding "
            "coverage to roughly 265 companies, and the scope widened from 26 items to the full "
            "set of disclosures the exchange requires — 55 material information items, plus fair "
            "disclosure and inquired disclosure.\n\n"
            "Timing tightened too. The largest companies, those above ₩10 trillion, are expected "
            "to file the English version the same day as the Korean one. Companies newly captured "
            "at the ₩2 trillion threshold have three days.\n\n"
            "One limit worth knowing up front: this is a KOSPI rule. KOSDAQ companies are not "
            "covered by the mandate, though regulators have signaled they are considering "
            "extending it to large-cap KOSDAQ names. Many KOSDAQ companies file in English "
            "anyway — voluntarily."
        ),
    },
    {
        "heading": "Read the disclaimer before you trust the translation",
        "body": (
            "Open the Financial Supervisory Service's English DART site and the first thing on the "
            "page, above the search box, is a warning. The FSS states that it neither affirms nor "
            "certifies the accuracy of the English disclosures posted there, that English "
            "disclosures \"are made voluntarily with no legal effect and may not correspond to the "
            "original disclosures in Korean due to mistranslation,\" and that users are advised to "
            "refer to the original Korean filings for specific details.\n\n"
            "That is not boilerplate you can skim past. It defines what you are actually reading. "
            "The Korean filing is the legal document. The English version is a convenience copy, "
            "and where the two diverge, the Korean one is what binds the company and what a "
            "regulator or court would look at.\n\n"
            "In practice this matters most at the margins that matter most: conditional language "
            "in a contract disclosure, the precise scope of a buyback, the difference between a "
            "board resolving to consider something and a board approving it. If a single sentence "
            "is load-bearing for your investment case, that is exactly the sentence to check "
            "against the Korean original — with a machine translation of the Korean text, if "
            "necessary, rather than relying on the official English rendering alone."
        ),
    },
    {
        "heading": "DART and KIND are not the same system",
        "body": (
            "Korea splits corporate disclosure across two platforms, which trips up investors "
            "arriving from a market where EDGAR is the single front door.\n\n"
            "DART, run by the Financial Supervisory Service, is the statutory filing repository — "
            "annual and quarterly reports, audit matters, securities issuance, large-shareholding "
            "reports. It is the closest analogue to EDGAR, and its English edition sits at "
            "englishdart.fss.or.kr. KIND, run by the Korea Exchange, carries exchange-level "
            "disclosures: the material-information announcements, fair disclosures and responses "
            "to exchange inquiries that make up the day-to-day flow of company news. The English "
            "disclosure mandate described above is an exchange rule, so KIND is where its effects "
            "show up most directly.\n\n"
            "For most research, start on English DART and treat KIND as the second stop when you "
            "are chasing a specific announcement. The two systems overlap enough that a filing "
            "you cannot find on one is often on the other."
        ),
    },
    {
        "heading": "A workflow that works on the English site",
        "body": (
            "English DART's integrated search lets you filter by filing type, and the category "
            "names are the map of what exists. The ones worth knowing:\n\n"
            "**Periodic Disclosure** holds the annual and quarterly reports — the closest thing to "
            "a 10-K and 10-Q, and where you go for segment detail, capex and related-party "
            "transactions. **Report on Major Issues** is the material-event stream: capital "
            "increases, buybacks, large supply contracts, litigation. **Equity Disclosure** and "
            "the site's dedicated 5%·Executive view cover large-shareholding reports and "
            "executive holdings — who is accumulating and who is selling. **External Audit "
            "Matters** is where auditor changes and opinions surface, which is often the earliest "
            "public sign of trouble at a smaller company. **Issuance Disclosure** covers new "
            "securities, including the convertible bonds that dilute KOSDAQ shareholders more "
            "often than they expect.\n\n"
            "There is also a live feed: Today's Disclosure, refreshed every thirty seconds and "
            "split by market — KOSPI, KOSDAQ, KONEX and others. On an ordinary afternoon it runs "
            "to dozens of filings across the market, and scanning it is the fastest way to see "
            "what a Korean trading day actually consisted of, rather than reading about it "
            "second-hand a day later.\n\n"
            "For numbers specifically, the XBRL Financial Statements section gives you structured "
            "financial data rather than a PDF you have to read around — the practical route if "
            "you want to compare several companies on the same line items without trusting a "
            "translation of each one."
        ),
    },
    {
        "heading": "What is still missing, and how to work around it",
        "body": (
            "Four gaps survive the 2026 expansion, and knowing them saves you from concluding that "
            "information does not exist when it simply is not translated.\n\n"
            "The first is size. Below ₩2 trillion in assets — which is most of KOSDAQ and a long "
            "tail of KOSPI — English filing is voluntary. Coverage of small caps is patchy and "
            "inconsistent from one company to the next.\n\n"
            "The second is depth. A mandate covers specified disclosure items, not every page a "
            "company produces. Footnotes, the fuller management discussion, and much of the detail "
            "an analyst actually wants often remain Korean-only even at companies that comply "
            "fully.\n\n"
            "The third is timing. Same-day filing applies to the largest companies; three days is "
            "the standard for the newly covered tier. Three days is a long time in a stock that "
            "just announced a contract, and Korean-reading investors will have acted first.\n\n"
            "The fourth is translation quality. Regulators have been expanding machine translation "
            "and improving it with AI, which raises coverage and lowers precision at the same "
            "time. Treat a fluent English disclosure as a good summary and a poor contract.\n\n"
            "The workaround for all four is the same and unglamorous: use English DART to find out "
            "that a filing exists and roughly what it says, then put the Korean original through a "
            "translation tool when the specifics carry weight. Company IR pages are worth checking "
            "separately — large Korean companies increasingly publish English earnings decks and "
            "hold English calls that are more informative than any filing."
        ),
    },
]

INSIGHT_SECTION = {
    "heading": "Two things to internalize before your first filing",
    "stories": [
        {
            "heading": "Which document is the real one",
            "body": (
                "The hierarchy is simple once stated, and almost nobody states it. The Korean "
                "filing is the legal instrument. The English filing is a translation offered for "
                "convenience, and the regulator hosting it explicitly declines to certify that it "
                "is correct.\n\n"
                "This does not make English filings useless — it makes them a first pass. Use them "
                "to learn that something happened, to follow a company's ordinary flow of news, "
                "and to screen. Do not use them as the sole basis for a decision that turns on the "
                "exact wording of one clause, because that is precisely where a translation is "
                "most likely to be thin and where the disclaimer is pointed."
            ),
            "icon": "scale",
            "image_query": "person reading document on laptop",
            "table": [
                {"label": "Korean filing", "value": "The legal document — binding"},
                {"label": "English filing", "value": "Convenience translation — no legal effect"},
                {"label": "Where they can diverge", "value": "Conditions, scope, timing language"},
                {"label": "Safe use of English", "value": "Screening, following news flow, first pass"},
                {"label": "Check the Korean when", "value": "One clause carries your thesis"},
            ],
        },
        {
            "heading": "Coverage expanded, but only so far",
            "body": (
                "The May 2026 phase more than doubled the number of KOSPI companies required to "
                "file in English, and widened the requirement from a short list of key items to "
                "the exchange's full disclosure set. That is a real change in what a "
                "non-Korean-reading investor can follow without help.\n\n"
                "It is also bounded in a specific way. The rule follows company size, not company "
                "interest — a ₩1.5 trillion KOSDAQ company in the middle of the AI supply chain "
                "may be far more relevant to your portfolio than a ₩3 trillion KOSPI utility, and "
                "only the utility is covered. Below the threshold, English filing depends entirely "
                "on whether the company chooses to bother."
            ),
            "icon": "chip",
            "image_query": "glass office building facade",
            "chart": {
                "title": "KOSPI companies under the English disclosure mandate",
                "type": "stat",
                "labels": ["Phase 1 (from Jan 2024)", "Phase 2 (from May 2026)"],
                "data": [111, 265],
                "unit": " firms",
            },
        },
    ],
}

CLOSING = {
    "heading": "The takeaway",
    "body": (
        "Researching a Korean company in English is no longer a workaround, but it is not yet the "
        "same experience as researching a U.S. one. The May 2026 expansion took mandatory English "
        "disclosure from 111 companies to 265 and from 26 items to the exchange's full set, which "
        "covers most of what a foreign investor in large-cap Korea actually needs to follow.\n\n"
        "What has not changed is the hierarchy. English is the convenience copy; Korean is the "
        "document. English DART says so on its own front page, and the sensible reading of that "
        "warning is not to distrust the English filings but to know what they are for — finding "
        "out what happened, not adjudicating exactly what was promised.\n\n"
        "Start at englishdart.fss.or.kr, use KIND for exchange announcements, check the company's "
        "own IR page for English earnings materials, and go back to the Korean original whenever a "
        "single sentence is doing the work in your investment case. This guide describes the "
        "systems as of September 2026; disclosure rules in Korea have changed twice in three years "
        "and are likely to keep moving."
    ),
}

TAGS = [
    "DART",
    "KIND",
    "Korean stocks",
    "corporate disclosure",
    "English disclosure",
    "KOSPI",
    "foreign investors",
    "equity research",
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
