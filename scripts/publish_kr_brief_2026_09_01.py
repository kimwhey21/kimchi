"""2026-09-01 한국장 마감 시황 — 직접 작성한 한국어판·영어판 초안 업로드.

generate_free.py의 자동 생성본(수치 나열)을 대체하는 원고입니다. 수치는 전부
fetch_kr.py의 실제 시세와 확인된 기사에서만 가져왔고, 원인·해석에는 출처를 답니다.

확인한 출처 (2026-09-01):
- 아시아경제: 코스피 6835.80 마감(+0.23%, +15.78P), 코스닥 821.25(-1.56%, -13.04P),
  기타법인 1조6888억원 순매수, 코스피 개인·외국인·기관 순매도,
  코스닥 개인 4338억 순매수 / 외국인 1515억·기관 2748억 순매도,
  업종: 유통 +2.98% 보험 +2.15% 금융 +1.52% / 건설 -3.50% 기계장비 -1.34%,
  종목: 삼성물산 +3.72% SK스퀘어 +2.89% / 심텍 -2.86%
- 연합뉴스: 삼성전자·SK하이닉스 자사주 매입에 '전약후강', 6,830선 마감
- 연합뉴스: 중동 긴장 재고조·저가매수세 유입에 환율 소폭 상승
- 한국경제: 코스피, 중동 긴장 딛고 강보합
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src import fetch_kr, publish_wordpress, render_html, editorial_quality  # noqa: E402

DATE = "2026-09-01"
FEATURED_MEDIA_ID = 212  # main.py 실행 때 이미 올라간 오늘자 데이터 그래픽

SOURCES = [
    {
        "name": "아시아경제",
        "title": "코스피, 6800선 강보합 마감…코스닥은 하락",
        "url": "https://view.asiae.co.kr/article/2026090115561233028",
    },
    {
        "name": "연합뉴스",
        "title": "삼전·닉스 자사주 매입에 또 '전약후강'…코스피, 6,830선 마감(종합)",
        "url": "https://www.yna.co.kr/economy/all",
    },
    {
        "name": "연합뉴스",
        "title": "중동 긴장 재고조·저가매수세 유입에 환율 소폭 상승",
        "url": "https://www.yna.co.kr/economy/all",
    },
    {
        "name": "한국경제",
        "title": "코스피, 중동 긴장 딛고 강보합…6830대 마감",
        "url": "https://www.hankyung.com/all-news-finance",
    },
]

KO = {
    "title": "코스피는 자사주 매입에 0.23% 올랐고, 코스닥은 1.56% 하락했습니다",
    "narrative": [
        {
            "heading": "지수는 올랐지만, 판 쪽이 훨씬 많았습니다",
            "body": (
                "9월 1일 코스피는 15.78포인트 오른 6,835.80으로 마감했습니다. 상승률은 "
                "0.23%입니다. 같은 날 코스닥은 13.04포인트 내린 821.25로 1.56% 하락했고, "
                "원/달러 환율은 1,372.70원으로 0.23% 올랐습니다.\n\n"
                "지수만 보면 무난한 하루로 보이지만 수급을 열어보면 그림이 다릅니다. "
                "아시아경제 집계에 따르면 이날 코스피에서 개인과 외국인, 기관이 모두 "
                "순매도였고, 순매수는 기타법인 한 곳뿐이었습니다. 그 규모가 1조6,888억원입니다.\n\n"
                "저희가 추적하는 관심 종목 10개 중에서도 3개만 올랐고 7개가 내렸습니다. "
                "지수의 방향과 종목의 방향이 반대였던 날입니다."
            ),
        },
        {
            "heading": "기타법인 1조6,888억원의 정체는 자사주 매입입니다",
            "body": (
                "기타법인은 금융회사가 아닌 일반 법인의 매매를 묶은 항목입니다. 기업이 "
                "자기 주식을 사들이면 이 계정으로 잡힙니다. 연합뉴스는 이날 삼성전자와 "
                "SK하이닉스의 자사주 매입이 지수를 떠받치면서 장 초반 약세가 마감 강보합으로 "
                "바뀌었다고 전했습니다.\n\n"
                "숫자로도 흔적이 남습니다. SK하이닉스는 외국인이 21만1,935주를 순매도했는데도 "
                "1.14% 올라 169만3,000원에 마감했습니다. 삼성전자도 0.38% 오른 26만1,000원이었습니다. "
                "파는 물량을 받아준 주체가 따로 있었다는 뜻입니다.\n\n"
                "어제 8월 31일에도 같은 구도였습니다. 장중 3%대 급락을 자사주 매입이 되돌렸고, "
                "오늘은 그 매입이 하락 출발을 상승 마감으로 바꿨습니다. 이틀 연속 같은 힘이 "
                "지수의 바닥을 만들고 있습니다."
            ),
        },
        {
            "heading": "코스닥에는 같은 방어막이 없었습니다",
            "body": (
                "코스닥의 수급은 정반대였습니다. 개인이 4,338억원을 순매수했지만 외국인이 "
                "1,515억원, 기관이 2,748억원을 순매도했습니다. 코스피를 떠받친 자사주 매입 "
                "같은 대형 매수 주체가 없었고, 지수는 1.56% 내렸습니다.\n\n"
                "하락을 이끈 건 2차전지였습니다. 에코프로가 4.49% 내린 8만7,200원, "
                "에코프로비엠이 3.81% 내린 11만6,200원으로 마감했고, 코스피 상장사인 "
                "LG에너지솔루션도 2.91% 하락한 36만7,000원이었습니다. 업종별로는 건설이 "
                "3.50% 내려 낙폭이 가장 컸고, 기계·장비가 1.34% 하락했습니다.\n\n"
                "오른 업종은 성격이 달랐습니다. 유통이 2.98%, 보험이 2.15%, 금융이 1.52% "
                "올랐습니다. 성장주에서 빠진 돈이 방어적인 업종으로 옮겨간 하루로 읽힙니다."
            ),
        },
        {
            "heading": "환율은 중동發 불확실성을 반영했습니다",
            "body": (
                "원/달러 환율은 1,372.70원으로 0.23% 올랐습니다. 연합뉴스는 중동 긴장이 "
                "다시 높아진 가운데 저가 매수세가 유입되며 환율이 소폭 올랐다고 전했습니다. "
                "한국경제도 코스피가 중동 긴장을 딛고 강보합으로 마감했다고 보도했습니다.\n\n"
                "환율 상승은 외국인 수급에 부담입니다. 원화 가치가 내려가면 달러 기준 "
                "수익률이 깎이기 때문입니다. 이날 외국인이 코스피와 코스닥에서 모두 "
                "순매도였던 것과 무관하지 않은 흐름입니다."
            ),
        },
    ],
    "theme_section": {
        "heading": "2차전지는 하락, 반도체는 상승",
        "commentary": (
            "같은 시장 안에서 방향이 갈렸습니다. 반도체 대형주는 자사주 매입이라는 수급 "
            "요인으로 버텼고, 2차전지는 매수 주체 없이 낙폭을 키웠습니다. 아래 카드는 "
            "각 테마를 대표하는 종목의 실제 마감 등락률입니다."
        ),
        "highlights": [
            {"label": "반도체", "ticker": "000660"},
            {"label": "2차전지", "ticker": "086520"},
            {"label": "인터넷", "ticker": "035420"},
            {"label": "바이오", "ticker": "196170"},
        ],
    },
    "stock_section": {
        "heading": "외국인이 판 종목과 산 종목이 엇갈렸습니다",
        "commentary": (
            "외국인 순매도 1위는 SK하이닉스(21만1,935주)였지만 주가는 1.14% 올랐습니다. "
            "반대로 카카오는 외국인이 10만2,298주를 순매수했는데도 0.14% 내렸습니다. "
            "외국인 수급만으로 그날 주가를 설명할 수 없었던 날입니다. 알테오젠은 외국인이 "
            "11만8,301주를 순매도하며 2.11% 하락해, 수급과 주가 방향이 일치한 쪽에 속했습니다."
        ),
        "featured_tickers": ["000660", "005930", "035720", "196170", "086520", "373220"],
    },
    "outlook": {
        "heading": "다음 거래일에 확인할 것",
        "body": (
            "첫째, 기타법인 순매수가 계속되는지입니다. 자사주 매입은 예정된 기간과 금액이 "
            "정해진 프로그램이므로 무한정 이어지지 않습니다. 이 매수가 줄어들 때 지수가 "
            "버티는지가 관건입니다.\n\n"
            "둘째, 코스닥과 코스피의 격차입니다. 이틀 연속 코스피만 방어된 구도라면 "
            "지수 상승이 시장 전반의 회복을 뜻하지 않습니다. 코스닥이 함께 오르는지 "
            "확인해야 방향을 판단할 수 있습니다.\n\n"
            "셋째, 환율입니다. 중동 관련 불확실성이 이어지면 원화 약세가 외국인 순매도를 "
            "자극할 수 있습니다."
        ),
    },
    "closing": {
        "heading": "오늘을 한 줄로 정리하면",
        "body": (
            "코스피 0.23% 상승이라는 숫자 뒤에는, 개인과 외국인과 기관이 모두 팔고 "
            "기업이 자기 주식을 사들여 그 물량을 받아낸 하루가 있었습니다.\n\n"
            "지수가 올랐다고 시장이 좋았다고 말하기 어려운 이유입니다. 코스닥 1.56% 하락과 "
            "관심 종목 10개 중 7개 하락이 그날의 실제 온도에 더 가깝습니다."
        ),
    },
    "sources": SOURCES,
}

EN = {
    "title": "Buybacks Lifted KOSPI 0.23% While KOSDAQ Fell 1.56%",
    "narrative": [
        {
            "heading": "The index rose. Almost everyone else was selling.",
            "body": (
                "On September 1 the KOSPI closed at 6,835.80, up 15.78 points or 0.23%. The "
                "KOSDAQ, Korea's secondary board for smaller and growth companies, fell 13.04 "
                "points to 821.25, a decline of 1.56%. The won weakened 0.23% against the "
                "dollar to 1,372.70.\n\n"
                "The index number hides what actually happened. According to Asiae's session "
                "tally, retail investors, foreign investors and domestic institutions were all "
                "net sellers of KOSPI shares. Exactly one category was buying: \"other "
                "corporations,\" to the tune of ₩1.69 trillion.\n\n"
                "Of the ten stocks on our Korea watchlist, three rose and seven fell. The index "
                "and the individual stocks moved in opposite directions."
            ),
        },
        {
            "heading": "That ₩1.69 trillion is corporate buybacks",
            "body": (
                "In Korean market data, \"other corporations\" is the bucket for non-financial "
                "companies trading in the market — which is where a company buying its own "
                "shares shows up. Yonhap reported that share repurchases by Samsung Electronics "
                "and SK Hynix supported the index, turning an early decline into a modest "
                "gain by the close.\n\n"
                "The stock-level numbers corroborate it. SK Hynix rose 1.14% to ₩1,693,000 even "
                "as foreign investors sold a net 211,935 shares. Samsung Electronics gained "
                "0.38% to ₩261,000. Something was absorbing the selling.\n\n"
                "This is now a pattern rather than an event. On August 31 the same buyback flow "
                "reversed an intraday drop of more than 3%. On September 1 it converted a lower "
                "open into a higher close. Two sessions running, the same buyer has been setting "
                "the floor."
            ),
        },
        {
            "heading": "KOSDAQ had no such buyer",
            "body": (
                "Flows on the KOSDAQ ran the other way. Retail investors bought a net ₩434 "
                "billion, while foreign investors sold ₩152 billion and institutions sold ₩275 "
                "billion. With no large corporate bid underneath it, the index fell 1.56%.\n\n"
                "Battery names led the decline. Ecopro dropped 4.49% to ₩87,200 and Ecopro BM "
                "fell 3.81% to ₩116,200; LG Energy Solution, listed on the KOSPI, lost 2.91% to "
                "₩367,000. By sector, construction fell the most at 3.50%, followed by machinery "
                "and equipment at 1.34%.\n\n"
                "What rose tells the same story from the other side: retail and distribution "
                "gained 2.98%, insurance 2.15% and financials 1.52%. Money left growth and moved "
                "toward defensives."
            ),
        },
        {
            "heading": "The won priced in Middle East risk",
            "body": (
                "The won slipped 0.23% to 1,372.70 per dollar. Yonhap attributed the move to "
                "renewed Middle East tension combined with bargain-hunting dollar demand. "
                "Hankyung likewise described the KOSPI as closing modestly higher despite that "
                "tension.\n\n"
                "For a foreign holder this matters directly. A weaker won reduces dollar-denominated "
                "returns on Korean equities regardless of what the share price does — which is "
                "consistent with foreign investors selling on both boards that day."
            ),
        },
    ],
    "theme_section": {
        "heading": "Semiconductors held, batteries did not",
        "commentary": (
            "The split within a single session was clean. Large-cap semiconductors were supported "
            "by a flow factor — the buyback — while battery names fell with no comparable bid. "
            "The cards below show the actual closing move for a representative stock in each theme."
        ),
        "highlights": [
            {"label": "Semiconductors", "ticker": "000660"},
            {"label": "Batteries", "ticker": "086520"},
            {"label": "Internet", "ticker": "035420"},
            {"label": "Biotech", "ticker": "196170"},
        ],
    },
    "stock_section": {
        "heading": "Foreign flows did not decide the day",
        "commentary": (
            "The largest foreign net sale was SK Hynix, at 211,935 shares — and the stock rose "
            "1.14%. Kakao saw net foreign buying of 102,298 shares and still slipped 0.14%. "
            "Alteogen was the case where flow and price agreed: foreign investors sold a net "
            "118,301 shares and the stock fell 2.11%."
        ),
        "featured_tickers": ["000660", "005930", "035720", "196170", "086520", "373220"],
    },
    "outlook": {
        "heading": "What to watch next session",
        "body": (
            "First, whether corporate net buying continues. Buyback programs run to a disclosed "
            "size and schedule; they do not last indefinitely. The test is what the index does "
            "when that bid thins out.\n\n"
            "Second, the KOSPI–KOSDAQ gap. If only the large-cap index is being defended, an "
            "index gain does not mean the market recovered. A KOSDAQ that rises alongside it "
            "would say something different.\n\n"
            "Third, the won. Sustained Middle East risk that keeps the currency weak gives "
            "foreign investors a reason to keep selling."
        ),
    },
    "closing": {
        "heading": "The session in one line",
        "body": (
            "Behind a 0.23% gain sits a session in which retail, foreign and institutional "
            "investors all sold, and companies bought their own shares to absorb it.\n\n"
            "That is why the index number is a poor summary of the day. A 1.56% decline on the "
            "KOSDAQ, and seven of ten watchlist stocks falling, is closer to how it actually felt."
        ),
    },
    "sources": SOURCES,
}


def main() -> None:
    price_data = fetch_kr.fetch_all()
    print("거래일:", price_data.get("trading_date"))

    editorial_quality.validate_generated(KO)
    print("한국어 편집 기준 검사 통과")

    html_ko = render_html.render("kr", DATE, price_data, KO)
    html_en = render_html.render(
        "kr", DATE, price_data, EN, lang="en", market_label="Korea Market Close"
    )
    out = Path(__file__).resolve().parent.parent / "output"
    (out / f"kr_{DATE}_written.html").write_text(html_ko, encoding="utf-8")
    (out / f"kr_{DATE}_written_en.html").write_text(html_en, encoding="utf-8")
    print("렌더링 완료")

    def excerpt(doc: dict, limit: int = 300) -> str:
        body = doc["narrative"][0]["body"].replace("\n\n", " ")
        return body if len(body) <= limit else body[:limit].rsplit(" ", 1)[0] + "…"

    ko_res = publish_wordpress.publish_draft(
        KO["title"], html_ko,
        excerpt=excerpt(KO),
        tags=["코스피", "코스닥", "자사주 매입", "삼성전자", "SK하이닉스", "에코프로", "원달러 환율"],
        category="Daily",
        featured_media_id=FEATURED_MEDIA_ID,
        slug=f"market-brief-kr-{DATE}-ko-written",
        focus_keyword="코스피 마감 시황",
    )
    print("한국어 초안:", ko_res.get("id"), ko_res.get("link"))

    en_res = publish_wordpress.publish_draft(
        EN["title"], html_en, lang="en",
        excerpt=excerpt(EN),
        tags=["KOSPI", "KOSDAQ", "share buyback", "Samsung Electronics", "SK Hynix", "Korean won"],
        category="Daily",
        featured_media_id=FEATURED_MEDIA_ID,
        slug=f"market-brief-kr-{DATE}-en-written",
        focus_keyword="Kospi close",
    )
    print("영어 초안:", en_res.get("id"), en_res.get("link"))


if __name__ == "__main__":
    main()
