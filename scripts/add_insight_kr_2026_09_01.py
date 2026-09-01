"""215·216번 글에 인사이트 섹션을 추가해 같은 글을 덮어씁니다.

무료 생성 경로(generate_free.py)는 insight_section을 None으로 둡니다. 시세와 RSS
제목만으로는 산업·정책 동향을 조사할 수 없어서, 넣으려면 근거 없는 내용을 지어내야
하기 때문입니다. 이 스크립트는 그 자리를 사람(에이전트)이 직접 조사한 내용으로 채웁니다.

확인한 출처 (2026-09-01 검색):
- 자사주 소각 의무화(3차 상법 개정) 시행, 금융위 자기주식 공시 강화,
  2024-05 이후 2026-03까지 밸류업 공시 590개사, 삼성전자 3/18 7조2000억 매입·
  3/31 5조3000억 소각: 뉴데일리, thebell, 노컷뉴스
- LG에너지솔루션 미국 ESS 출하량이 2026년 EV용을 추월 전망, AI 데이터센터
  투자로 ESS 수요 급증 / 에코프로머티 매출 1조·영업이익 1076억 흑자전환 전망,
  전구체 외부판매 비중 2025년 25% → 2026년 70%: 증권사 리서치 종합
- 2026년 HBM 실수요 42억3000만GB(+95% YoY), 생산 전망 44억4000만GB,
  글로벌 반도체 시장 9750억달러(+25%), 메모리 30%대 성장: SK하이닉스 뉴스룸 외
- 중동발 유가 상승이 2026년 소비자물가를 1.2%p(기초)~1.6%p(고유가 장기화)
  추가 상승시킬 수 있다는 전망: 국내 언론 종합
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src import fetch_kr, fetch_images, publish_wordpress, render_html, editorial_quality  # noqa: E402
from publish_kr_brief_2026_09_01 import KO, EN, DATE, SOURCES  # noqa: E402

KO_POST_ID, EN_POST_ID = 215, 216
FEATURED_MEDIA_ID = 217

KO_INSIGHT = {
    "heading": "오늘 숫자 뒤에 있는 네 가지 흐름",
    "stories": [
        {
            "heading": "자사주 매입은 기업의 선의가 아니라 제도의 결과입니다",
            "icon": "scale",
            "body": (
                "오늘 지수를 떠받친 기타법인 1조6,888억원 순매수는 갑자기 나온 돈이 "
                "아닙니다. 자사주 소각을 의무화한 3차 상법 개정안이 국회를 통과해 "
                "시행되면서, 기업이 자기 주식을 사서 없애는 일이 선택이 아니라 의무가 "
                "됐습니다. 금융위원회는 후속 조치로 자기주식 공시 제도도 강화했습니다.\n\n"
                "규모가 이미 시장을 움직일 만큼 커졌습니다. 2024년 5월 기업가치 제고 계획 "
                "공시가 시행된 뒤 2026년 3월까지 590개 기업이 공시를 냈고, 삼성전자는 "
                "3월 18일 7조2,000억원 매입을 결정한 데 이어 3월 31일 5조3,000억원 "
                "소각을 결정했습니다.\n\n"
                "소각은 매입과 다릅니다. 사들인 주식을 없애면 발행주식 수가 줄어 "
                "주당순이익이 올라갑니다. 다만 투자자 입장에서 기억할 점은 이 매수가 "
                "정해진 기간과 금액 안에서만 이뤄진다는 것입니다. 오늘처럼 이 힘이 "
                "지수를 떠받치는 구도는 프로그램이 끝나면 함께 끝납니다."
            ),
            "table": [
                {"label": "오늘 기타법인 순매수", "value": "1조6,888억원"},
                {"label": "삼성전자 자사주 매입 결정(3/18)", "value": "7조2,000억원"},
                {"label": "삼성전자 소각 결정(3/31)", "value": "5조3,000억원"},
                {"label": "밸류업 공시 기업(2026-03 누적)", "value": "590개사"},
            ],
        },
        {
            "heading": "2차전지의 무게중심이 전기차에서 ESS로 옮겨가고 있습니다",
            "icon": "battery",
            "body": (
                "오늘 에코프로가 4.49%, 에코프로비엠이 3.81%, LG에너지솔루션이 2.91% "
                "내렸습니다. 전기차 수요 둔화, 이른바 캐즘이 여전히 주가에 남아 있다는 "
                "뜻이지만, 업계가 보는 그림은 조금 달라졌습니다.\n\n"
                "LG에너지솔루션은 미국 사업에서 2026년을 기점으로 ESS(에너지저장장치) "
                "출하량이 전기차용 출하량을 추월할 것으로 전망됩니다. AI 데이터센터 투자가 "
                "늘면서 전력 저장 수요가 함께 커진 결과입니다. 배터리 회사의 성장 동력이 "
                "자동차에서 전력 인프라로 이동하는 구조 변화입니다.\n\n"
                "에코프로 쪽에서도 방향 전환이 보입니다. 에코프로머티는 올해 매출 1조원, "
                "영업이익 1,076억원으로 흑자 전환이 예상되고, 전구체 외부 판매 비중이 "
                "2025년 25%에서 2026년 70%까지 확대될 것으로 전망됩니다. 계열사 안에서만 "
                "팔던 소재를 밖에 파는 회사로 바뀌는 중입니다.\n\n"
                "다만 이 수치들은 전망이지 확정된 실적이 아닙니다. 오늘의 하락은 그 전망이 "
                "아직 주가에 온전히 반영되지 않았다는 사실을 보여줍니다."
            ),
            "table": [
                {"label": "에코프로머티 예상 매출", "value": "1조원"},
                {"label": "예상 영업이익", "value": "1,076억원 (흑자 전환)"},
                {"label": "전구체 외부판매 비중", "value": "25% (2025) → 70% (2026)"},
                {"label": "LG엔솔 미국 ESS 출하량", "value": "2026년 EV용 추월 전망"},
            ],
        },
        {
            "heading": "반도체가 버틴 이유는 수급만이 아닙니다",
            "icon": "chip",
            "image_query": "semiconductor wafer",
            "body": (
                "SK하이닉스는 외국인이 21만주 넘게 팔았는데도 1.14% 올랐고 삼성전자도 "
                "0.38% 상승했습니다. 자사주 매입이라는 수급 요인이 컸지만, 업황 자체가 "
                "받쳐주고 있다는 점도 함께 봐야 합니다.\n\n"
                "2026년 HBM 실수요는 42억3,000만GB로 전년 대비 95% 증가할 것으로 "
                "전망됩니다. 생산 전망치는 44억4,000만GB로 수요를 소폭 웃도는 수준입니다. "
                "글로벌 반도체 시장 전체로는 전년 대비 25% 이상 성장한 약 9,750억 달러가 "
                "예상되고, 그중 메모리는 30%대 성장률로 시장 평균을 웃돌 것으로 "
                "관측됩니다.\n\n"
                "AI가 학습 단계를 지나 추론 단계로 넘어가면서 메모리 수요의 성격도 "
                "바뀌었습니다. 두 회사는 이미 2026년 생산 물량의 상당 부분을 예약 "
                "완료했고, SK하이닉스는 HBM4 전환을 준비하고 있습니다.\n\n"
                "수요와 공급 전망이 42억3,000만GB 대 44억4,000만GB로 근접해 있다는 점은 "
                "기억해둘 만합니다. 공급이 수요를 조금이라도 크게 넘어서면 가격 협상력이 "
                "달라지기 때문입니다."
            ),
            "chart": {
                "title": "2026년 HBM 수요와 생산 전망",
                "type": "stat",
                "labels": ["실수요 전망", "생산 전망"],
                "data": [42.3, 44.4],
                "unit": "억GB",
            },
        },
        {
            "heading": "환율 0.23% 상승이 물가로 이어지는 경로",
            "icon": "gold",
            "image_query": "oil refinery pipeline",
            "body": (
                "오늘 원/달러 환율은 1,372.70원으로 0.23% 올랐습니다. 연합뉴스는 중동 "
                "긴장이 다시 높아진 것을 배경으로 지목했습니다. 하루 0.23%는 작아 보이지만 "
                "이 경로가 어디로 이어지는지는 알아둘 필요가 있습니다.\n\n"
                "한국은 원유를 전량 수입합니다. 유가가 오르고 원화가 약해지면 수입 단가가 "
                "두 번 오릅니다. 국내 분석에서는 중동발 유가 상승이 2026년 소비자물가 "
                "상승률을 기초 시나리오에서 1.2%포인트, 고유가가 길어질 경우 1.6%포인트 "
                "이상 끌어올릴 수 있다고 봅니다.\n\n"
                "물가가 오르면 금리 인하 기대가 뒤로 밀립니다. 금리가 높게 유지되면 "
                "성장주의 밸류에이션 부담이 커집니다. 오늘 2차전지와 건설이 내리고 보험·"
                "금융이 오른 업종 구도와 무관하지 않은 흐름입니다.\n\n"
                "환율은 외국인 투자자에게 또 다른 의미가 있습니다. 원화가 약해지면 달러 "
                "기준 수익률이 깎이므로, 주가가 올라도 손실이 날 수 있습니다. 오늘 외국인이 "
                "코스피와 코스닥에서 모두 순매도였던 배경 중 하나입니다."
            ),
            "chart": {
                "title": "유가 상승의 2026년 소비자물가 추가 상승 전망",
                "type": "stat",
                "labels": ["기초 시나리오", "고유가 장기화"],
                "data": [1.2, 1.6],
                "unit": "%p",
            },
        },
    ],
}

EN_INSIGHT = {
    "heading": "Four currents behind today's numbers",
    "stories": [
        {
            "heading": "The buyback bid is policy, not corporate generosity",
            "icon": "scale",
            "body": (
                "The ₩1.69 trillion of corporate net buying that held the index up today did not "
                "appear out of nowhere. Korea's third round of Commercial Act amendments, now in "
                "force, makes cancelling repurchased shares mandatory rather than optional, and "
                "the Financial Services Commission has tightened the accompanying disclosure "
                "rules.\n\n"
                "The scale is already large enough to move the market. Since corporate "
                "value-up disclosure began in May 2024, 590 companies had filed plans as of March "
                "2026. Samsung Electronics alone approved a ₩7.2 trillion buyback on March 18 and "
                "a ₩5.3 trillion cancellation on March 31.\n\n"
                "Cancellation is the part that matters. Retiring the shares reduces the count "
                "outstanding and lifts earnings per share. For an investor, though, the important "
                "caveat is that these programs run to a fixed size and schedule. A market held up "
                "by this bid is held up only as long as the program lasts."
            ),
            "table": [
                {"label": "Corporate net buying today", "value": "₩1.69tn"},
                {"label": "Samsung buyback approved (Mar 18)", "value": "₩7.2tn"},
                {"label": "Samsung cancellation (Mar 31)", "value": "₩5.3tn"},
                {"label": "Value-up filings by Mar 2026", "value": "590 companies"},
            ],
        },
        {
            "heading": "Batteries are shifting from cars to grid storage",
            "icon": "battery",
            "body": (
                "Ecopro fell 4.49%, Ecopro BM 3.81% and LG Energy Solution 2.91% today — the EV "
                "demand slowdown is still in these prices. But the industry's own outlook has "
                "moved on.\n\n"
                "LG Energy Solution's US shipments of energy storage systems are expected to "
                "overtake its EV battery shipments from 2026, driven by power demand from AI data "
                "centre construction. That is a structural shift in where a battery maker's growth "
                "comes from: from vehicles to electricity infrastructure.\n\n"
                "Ecopro shows a similar pivot. Ecopro Materials is forecast to turn profitable "
                "this year on revenue of ₩1 trillion and operating profit of ₩107.6 billion, with "
                "external precursor sales rising from 25% of output in 2025 to 70% in 2026 — from "
                "supplying affiliates to selling on the open market.\n\n"
                "These are forecasts, not results. Today's decline is a reminder that the market "
                "has not yet priced them in."
            ),
            "table": [
                {"label": "Ecopro Materials revenue (est.)", "value": "₩1tn"},
                {"label": "Operating profit (est.)", "value": "₩107.6bn — first profit"},
                {"label": "External precursor sales", "value": "25% (2025) → 70% (2026)"},
                {"label": "LGES US ESS shipments", "value": "To overtake EV from 2026"},
            ],
        },
        {
            "heading": "Semis held up on more than flows",
            "icon": "chip",
            "image_query": "semiconductor wafer",
            "body": (
                "SK Hynix rose 1.14% despite foreign investors selling over 211,000 shares, and "
                "Samsung Electronics gained 0.38%. Buyback flow explains part of it. The demand "
                "backdrop explains the rest.\n\n"
                "Real HBM demand in 2026 is forecast at 4.23 billion GB, a 95% increase year on "
                "year, against production of 4.44 billion GB. The global semiconductor market is "
                "expected to grow more than 25% to roughly $975 billion, with memory outpacing "
                "the average at around 30%.\n\n"
                "As AI workloads move from training to inference, the shape of memory demand has "
                "changed with it. Both Korean makers have already committed much of their 2026 "
                "output, and SK Hynix is preparing the transition to HBM4.\n\n"
                "Worth noting: at 4.23 billion GB of demand against 4.44 billion of supply, the "
                "two sit close together. If supply runs meaningfully ahead, pricing power changes."
            ),
            "chart": {
                "title": "2026 HBM demand vs. production forecast",
                "type": "stat",
                "labels": ["Real demand", "Production"],
                "data": [4.23, 4.44],
                "unit": "bn GB",
            },
        },
        {
            "heading": "How a 0.23% currency move reaches consumer prices",
            "icon": "gold",
            "image_query": "oil refinery pipeline",
            "body": (
                "The won weakened 0.23% to 1,372.70 today, which Yonhap linked to renewed Middle "
                "East tension. A single day's 0.23% is small; the transmission path is not.\n\n"
                "Korea imports all of its crude. When oil rises and the won weakens, the import "
                "bill rises twice over. Domestic analysis puts the effect of Middle East-driven "
                "oil prices at an additional 1.2 percentage points on 2026 consumer inflation "
                "under a base case, and more than 1.6 points if high prices persist.\n\n"
                "Higher inflation pushes rate-cut expectations further out. Rates staying high "
                "weigh on growth-stock valuations — which is consistent with today's sector split, "
                "where batteries and construction fell while insurance and financials rose.\n\n"
                "For a foreign investor the currency carries a second meaning: a weaker won cuts "
                "dollar-denominated returns even when share prices rise. That is part of the "
                "backdrop to foreign investors selling on both boards today."
            ),
            "chart": {
                "title": "Added 2026 CPI from oil, by scenario",
                "type": "stat",
                "labels": ["Base case", "Sustained high oil"],
                "data": [1.2, 1.6],
                "unit": "pp",
            },
        },
    ],
}


def main() -> None:
    price_data = fetch_kr.fetch_all()

    # 눈으로 확인한 검색어(웨이퍼/정유 플랜트)만 사진을 붙입니다. "자사주 매입",
    # "배터리"처럼 추상적·범주적인 검색어는 결과가 어긋나서(졸업장, AA 건전지)
    # 일부러 표·차트만 남겼습니다.
    ko_stories = fetch_images.attach_images(
        [dict(s) for s in KO_INSIGHT["stories"]]
    )
    ko_insight = {**KO_INSIGHT, "stories": ko_stories}
    by_query = {s.get("image_query"): s.get("image") for s in ko_stories}
    en_stories = []
    for story in EN_INSIGHT["stories"]:
        story = dict(story)
        story["image"] = by_query.get(story.get("image_query"))
        en_stories.append(story)
    en_insight = {**EN_INSIGHT, "stories": en_stories}

    ko = {**KO, "insight_section": ko_insight, "sources": SOURCES}
    en = {**EN, "insight_section": en_insight, "sources": SOURCES}

    editorial_quality.validate_generated(ko)
    print("한국어 편집 기준 검사 통과")

    html_ko = render_html.render("kr", DATE, price_data, ko)
    html_en = render_html.render(
        "kr", DATE, price_data, en, lang="en", market_label="Korea Market Close"
    )
    out = Path(__file__).resolve().parent.parent / "output"
    (out / f"kr_{DATE}_written.html").write_text(html_ko, encoding="utf-8")
    (out / f"kr_{DATE}_written_en.html").write_text(html_en, encoding="utf-8")

    def excerpt(doc: dict, limit: int = 300) -> str:
        body = doc["narrative"][0]["body"].replace("\n\n", " ")
        return body if len(body) <= limit else body[:limit].rsplit(" ", 1)[0] + "…"

    r1 = publish_wordpress.update_draft(
        KO_POST_ID, ko["title"], html_ko,
        excerpt=excerpt(ko), category="Daily",
        featured_media_id=FEATURED_MEDIA_ID, focus_keyword="코스피 마감 시황",
    )
    print("한국어 갱신:", r1.get("id"), r1.get("status"))

    r2 = publish_wordpress.update_draft(
        EN_POST_ID, en["title"], html_en, lang="en",
        excerpt=excerpt(en), category="Daily",
        featured_media_id=FEATURED_MEDIA_ID, focus_keyword="Kospi close",
    )
    print("영어 갱신:", r2.get("id"), r2.get("status"))


if __name__ == "__main__":
    main()
