"""2026-08-31 미국장 글을 사람이 편집한 원고로 기존 임시저장에 반영합니다."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from src import editorial_quality, fetch_us, publish_wordpress, render_html, render_text

load_dotenv()

POST_ID = 176
DATE_STR = "2026-08-31"


def _get_or_upload_media(base_url: str, auth: tuple[str, str], image: dict) -> dict:
    """같은 Unsplash 사진을 다시 실행할 때 미디어 라이브러리에 중복 업로드하지 않습니다."""
    response = requests.get(
        f"{base_url}/wp-json/wp/v2/media",
        params={"search": image["id"], "per_page": 100, "context": "edit"},
        auth=auth,
        timeout=30,
    )
    response.raise_for_status()
    for media in response.json():
        if Path(media.get("source_url", "")).stem == image["id"]:
            return media

    media_id = publish_wordpress.upload_featured_image(base_url, auth, image)
    if not media_id:
        raise RuntimeError(f"이미지 업로드에 실패했습니다: {image['id']}")
    media_response = requests.get(
        f"{base_url}/wp-json/wp/v2/media/{media_id}", auth=auth, timeout=30
    )
    media_response.raise_for_status()
    return media_response.json()


def main() -> None:
    price_data = fetch_us.fetch_all()
    macro = price_data["macro"]
    stocks = price_data["watchlist"]

    # 8월 28일 데이터가 Yahoo 지수 이력에서 일부 누락돼 27일 대비 등락률이
    # 계산되는 문제가 있었습니다. 8월 31일 마감값은 AP의 지수 표와 Reuters의
    # 원유 결제값으로 교차검증해 이 편집본에 고정합니다.
    verified_macro = {
        "^DJI": {"price": 53185.90, "change_pct": -0.70},
        "^GSPC": {"price": 7686.14, "change_pct": -0.33},
        "^IXIC": {"price": 26370.89, "change_pct": -0.12},
        "^RUT": {"price": 2956.45, "change_pct": -0.54},
        "^VIX": {"price": 14.92, "change_pct": 2.83},
        "^TNX": {"price": 4.76, "change_pct": 1.84},
        "^TYX": {"price": 5.25, "change_pct": 1.12},
    }
    verified_stocks = {
        "CL=F": {"price": 85.76, "change_pct": 2.83},
        "DE": {"price": 654.91, "change_pct": 3.90},
        "TSLA": {"price": 367.95, "change_pct": 5.51},
        "AMZN": {"price": 259.77, "change_pct": -2.50},
        "NVDA": {"price": 220.78, "change_pct": 1.48},
        "SOXX": {"price": 511.04, "change_pct": 0.48},
    }
    for ticker, values in verified_macro.items():
        macro[ticker].update(values)
    for ticker, values in verified_stocks.items():
        stocks[ticker].update(values)

    dji, spx, nasdaq, russell = (macro[key] for key in ("^DJI", "^GSPC", "^IXIC", "^RUT"))
    vix, ten_year, thirty_year = (macro[key] for key in ("^VIX", "^TNX", "^TYX"))
    oil = stocks["CL=F"]
    deere, tesla, nvidia, soxx, amazon = (
        stocks[key] for key in ("DE", "TSLA", "NVDA", "SOXX", "AMZN")
    )

    # 검색 결과의 설명만 믿지 않고 실제로 내려받아 확인한 사진들입니다.
    featured_image = {
        "id": "0w3nOe1j29I",
        "url": "https://images.unsplash.com/photo-1768564206500-5cddb1fea679?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3wxMDQzMzk2fDB8MXxhbGx8fHx8fHx8fHwxNzg4MjI3NTMyfA&ixlib=rb-4.1.0&q=80&w=1080",
        "alt": "구름 낀 하늘 아래의 산업 정유시설",
        "width": 1080,
        "height": 607,
        "photographer": "Barnaby",
        "photographer_url": "https://unsplash.com/@bfenton_photo",
    }
    market_image = {
        "id": "jgOkEjVw-KM",
        "url": "https://images.unsplash.com/photo-1616261167032-b16d2df8333b?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3wxMDQzMzk2fDB8MXxhbGx8fHx8fHx8fHwxNzg4MjI3NTMyfA&ixlib=rb-4.1.0&q=80&w=1080",
        "alt": "디지털 화면에 표시된 하락 추세의 시장 그래프",
        "width": 1080,
        "height": 720,
        "photographer": "Markus Spiske",
        "photographer_url": "https://unsplash.com/@markusspiske",
    }
    deere_image = {
        "id": "_dnc3j1oVlk",
        "url": "https://images.unsplash.com/photo-1717702576954-c07131c54169?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3wxMDQzMzk2fDB8MXxhbGx8fHx8fHx8fHwxNzg4MjI3NTMyfA&ixlib=rb-4.1.0&q=80&w=1080",
        "alt": "해 질 무렵 밭을 가는 트랙터",
        "width": 1080,
        "height": 810,
        "photographer": "Tom De Decker",
        "photographer_url": "https://unsplash.com/@tombelgium",
    }
    base_url = os.environ["WORDPRESS_URL"].rstrip("/")
    auth = (os.environ["WORDPRESS_USERNAME"], os.environ["WORDPRESS_APP_PASSWORD"])
    featured_media = _get_or_upload_media(base_url, auth, featured_image)
    market_media = _get_or_upload_media(base_url, auth, market_image)
    deere_media = _get_or_upload_media(base_url, auth, deere_image)

    generated = {
        "title": "유가가 금리를 밀어 올린 날, 뉴욕증시는 하락 마감했습니다",
        "narrative": [
            {
                "heading": "세 지수는 내렸지만, 8월 전체의 상승 흐름은 지켰습니다",
                "body": (
                    f"8월 마지막 거래일 다우존스는 {dji['price']:,.2f}로 {dji['change_pct']:+.2f}%, "
                    f"S&P500은 {spx['price']:,.2f}로 {spx['change_pct']:+.2f}%, 나스닥종합은 "
                    f"{nasdaq['price']:,.2f}로 {nasdaq['change_pct']:+.2f}% 마감했습니다. 러셀2000은 "
                    f"{russell['price']:,.2f}로 {russell['change_pct']:+.2f}% 내려 대형주 지수보다 약했습니다.\n\n"
                    "AP의 마감 집계에 따르면 세 주요 지수는 이날 모두 하락했지만 월간 기준으로는 상승을 지켰습니다. "
                    "따라서 이번 움직임은 8월 추세의 전면적인 반전보다는, 지정학적 위험이 유가와 금리를 통해 하루의 "
                    "가격을 다시 매긴 장면으로 보는 편이 정확합니다."
                ),
            },
            {
                "heading": "이란 충돌 재개가 원유에서 국채금리로 번졌습니다",
                "body": (
                    f"Reuters 집계에서 WTI는 배럴당 {oil['price']:,.2f}달러로 {oil['change_pct']:+.2f}%, "
                    "브렌트유는 90.49달러로 2.71% 상승했습니다. 미국과 이란의 군사 충돌이 다시 불거지면서 "
                    "원유 공급 경로에 대한 우려가 가격에 붙었습니다. 미국 10년물 국채금리는 "
                    f"{ten_year['price']:.2f}%까지 올랐고, VIX는 {vix['price']:.2f}로 {vix['change_pct']:+.2f}% 상승했습니다.\n\n"
                    "핵심은 유가 상승 그 자체보다 전달 경로입니다. 비싼 에너지는 물가 둔화를 늦출 수 있고, 물가 우려는 "
                    "금리 인하 기대를 낮추거나 인상 가능성을 다시 가격에 넣게 합니다. 장기금리가 오르면 미래 이익의 "
                    "현재가치가 낮아지므로 주식의 평가 기준도 함께 엄격해집니다."
                ),
            },
            {
                "heading": "에너지는 올랐고 유틸리티는 무너졌습니다",
                "body": (
                    "지수 하락만 보면 시장 전체가 같은 방향으로 움직인 것처럼 보이지만 업종 내부는 선명하게 갈렸습니다. "
                    "AP와 Yahoo Finance는 S&P500 대부분 업종이 약세였던 가운데 에너지주가 예외적으로 상승했다고 전했습니다. "
                    "엑슨모빌은 2.7%, 셰브론은 2.1% 올랐습니다. 원유 상승의 수혜가 곧바로 에너지 기업의 주가에 반영된 것입니다.\n\n"
                    "반대편에서는 에디슨 인터내셔널이 23.1%, PG&E가 20.1% 급락했습니다. 캘리포니아 산불 관련 법안이 "
                    "보험사의 전력회사 상대 청구 가능성을 키울 수 있다는 보도가 부담이 됐습니다. 같은 약세장 안에서도 "
                    "유가 수혜와 법적 위험이라는 서로 다른 이유가 종목 가격을 갈랐습니다."
                ),
            },
            {
                "heading": "디어와 테슬라는 지수 밖의 이유로 올랐습니다",
                "body": (
                    f"디어는 {deere['price']:,.2f}달러로 {deere['change_pct']:+.2f}% 상승했습니다. Baird가 투자의견을 "
                    "중립에서 시장수익률 상회로 높이고 목표주가를 640달러에서 800달러로 상향한 것이 촉매였습니다. "
                    "북미 대형 농기계 수요가 저점을 지나 회복할 가능성과 초기 주문 흐름이 근거로 제시됐습니다.\n\n"
                    f"테슬라는 {tesla['change_pct']:+.2f}% 올랐고, 엔비디아와 필라델피아 반도체 ETF도 각각 "
                    f"{nvidia['change_pct']:+.2f}%, {soxx['change_pct']:+.2f}% 상승했습니다. 반면 아마존은 "
                    f"{amazon['change_pct']:+.2f}% 내렸습니다. 거시 부담이 컸던 날에도 개별 재료와 종목별 수급이 "
                    "지수 방향을 이길 수 있음을 보여준 차이입니다."
                ),
            },
        ],
        "theme_section": {
            "heading": "한 시장 안에서 네 방향이 갈렸습니다",
            "commentary": (
                "원유는 지정학적 위험, 디어는 투자의견 상향, 테슬라는 종목별 수급, 아마존은 대형 기술주 내부의 "
                "차별화를 각각 보여줬습니다."
            ),
            "highlights": [
                {"label": "농기계 회복 기대", "ticker": "DE"},
                {"label": "종목별 강세", "ticker": "TSLA"},
                {"label": "지정학적 위험", "ticker": "CL=F"},
                {"label": "대형 기술주 약세", "ticker": "AMZN"},
            ],
        },
        "stock_section": {
            "heading": "마감 숫자가 보여준 선택적 매수",
            "commentary": (
                "기술주 전체가 무너진 날은 아니었습니다. 엔비디아와 반도체 ETF는 상승했지만 아마존은 하락했고, "
                "디어와 테슬라는 뚜렷한 상대 강세를 보였습니다. 아래 수치는 8월 31일 정규장 종가 기준입니다."
            ),
            "featured_tickers": ["DE", "TSLA", "CL=F", "AMZN", "NVDA", "SOXX"],
        },
        "outlook": {
            "heading": "다음 거래일은 유가보다 금리의 잔상을 봐야 합니다",
            "body": (
                "먼저 WTI가 85달러대에서 추가 상승하는지 확인해야 합니다. 유가가 안정되면 물가 우려와 금리 압력도 "
                "빠르게 누그러질 수 있지만, 브렌트유 90달러선과 미국 10년물 4.75%가 함께 유지되면 주식시장은 다시 "
                "높은 할인율을 견뎌야 합니다.\n\n"
                "그다음은 시장 폭입니다. 에너지주만 오르고 대부분 업종이 약한 흐름이 이어지는지, 러셀2000이 S&P500보다 "
                "계속 부진한지, 반도체의 상대 강세가 유지되는지를 차례로 보면 됩니다. 세 신호가 함께 개선돼야 이번 하락을 "
                "일회성 지정학적 충격으로 판단할 근거가 강해집니다."
            ),
        },
        "insight_section": {
            "heading": "숫자 사이에서 읽어야 할 세 가지 흐름",
            "stories": [
                {
                    "heading": "유가·금리·변동성은 하나의 전달 경로였습니다",
                    "body": (
                        "유가는 기업 비용에, 장기금리는 주식의 평가 배수에, VIX는 투자자가 요구하는 위험 보상에 영향을 줍니다. "
                        "세 지표가 동시에 오르면 지수의 낙폭이 작더라도 시장이 부담을 느끼는 범위는 넓어집니다. 이날은 바로 "
                        "그 연결이 확인된 세션이었습니다."
                    ),
                    "icon": "scale",
                    "table": [
                        {"label": "WTI 원유", "value": f"{oil['price']:,.2f}달러 ({oil['change_pct']:+.2f}%)"},
                        {"label": "미국 10년물", "value": f"{ten_year['price']:.2f}%"},
                        {"label": "VIX", "value": f"{vix['price']:.2f} ({vix['change_pct']:+.2f}%)"},
                    ],
                },
                {
                    "heading": "하락률보다 먼저 봐야 할 것은 자금의 방향입니다",
                    "body": (
                        "시각자료에서 먼저 보이는 것은 지수 네 개의 동반 약세가 아니라 그 안의 상대 강도입니다. 러셀2000은 "
                        "S&P500보다 더 많이 내렸고, 에너지주는 오히려 상승했습니다. 자금이 시장에서 완전히 빠져나갔다기보다 "
                        "유가 수혜와 개별 촉매가 있는 곳으로 선택적으로 이동한 것입니다.\n\n"
                        "따라서 다음 거래일에는 지수의 색깔보다 상승 종목 수와 업종별 확산을 확인하는 편이 유용합니다. "
                        "에너지 외 업종으로 매수가 넓어지고 소형주의 상대 약세가 줄어들면 위험 회피가 완화되고 있다는 "
                        "신호가 됩니다."
                    ),
                    "icon": "scale",
                    "image": {**market_image, "url": market_media["source_url"]},
                    "table": [
                        {"label": "러셀2000", "value": f"{russell['price']:,.2f} ({russell['change_pct']:+.2f}%)"},
                        {"label": "다우존스", "value": f"{dji['price']:,.2f} ({dji['change_pct']:+.2f}%)"},
                        {"label": "S&P500", "value": f"{spx['price']:,.2f} ({spx['change_pct']:+.2f}%)"},
                    ],
                },
                {
                    "heading": "디어의 상승은 농기계 업황의 반전을 선반영했습니다",
                    "body": (
                        "Baird는 디어의 목표주가를 800달러로 높이며 북미 대형 농기계 사이클의 회복 가능성을 강조했습니다. "
                        "디어의 3분기 투자자자료와 함께 보면 시장은 현재 실적 한 분기보다 2027년 주문과 이익 회복 가능성을 "
                        "앞서 가격에 넣은 셈입니다.\n\n"
                        "다만 애널리스트의 목표주가는 사실이 아니라 전망입니다. 실제 주문 증가와 농가 수익성 개선이 뒤따르는지 "
                        "확인해야 이번 재평가가 지속될 수 있습니다."
                    ),
                    "icon": "chip",
                    "image": {**deere_image, "url": deere_media["source_url"]},
                    "table": [
                        {"label": "디어 종가", "value": f"{deere['price']:,.2f}달러 ({deere['change_pct']:+.2f}%)"},
                        {"label": "Baird 기존 목표가", "value": "640달러"},
                        {"label": "Baird 새 목표가", "value": "800달러"},
                    ],
                },
            ],
        },
        "calendar": [],
        "closing": {
            "heading": "오늘을 한 문장으로 정리하면",
            "body": (
                "8월 31일 뉴욕시장은 ‘주가가 얼마나 내렸는가’보다 ‘유가 충격이 금리와 업종 선택에 어떻게 번졌는가’를 "
                "보여준 하루였습니다. 지수는 약세였지만 에너지·디어·테슬라에는 선택적 매수가 남았습니다.\n\n"
                "다음 판단의 기준은 단순합니다. 원유와 장기금리가 함께 안정되고, 에너지 밖으로 매수세가 넓어지며, "
                "러셀2000의 상대 약세가 줄어드는지를 확인하면 됩니다."
            ),
        },
        "sources": [
            {
                "name": "AP",
                "title": "Oil prices rise and stocks fall after US hits Iranian sites in the Strait of Hormuz",
                "url": "https://apnews.com/article/00f872327d65e5330598054a234dc25a",
            },
            {
                "name": "Reuters · Yahoo Finance",
                "title": "Yields rise, oil jumps; US and Iran resume military attacks",
                "url": "https://finance.yahoo.com/markets/articles/shares-skid-asia-oil-yields-003835124.html",
            },
            {
                "name": "Yahoo Finance",
                "title": "Energy stocks lead in subdued final trading day of August, utilities under pressure",
                "url": "https://ca.finance.yahoo.com/news/energy-stocks-lead-in-subdued-final-trading-day-of-august-utilities-under-pressure-alphacheck-142014111.html",
            },
            {
                "name": "Investing.com",
                "title": "Deere stock rises after Baird upgrade to Outperform",
                "url": "https://in.investing.com/news/stock-market-news/deere-stock-rises-after-baird-upgrade-to-outperform-93CH-5577220",
            },
            {
                "name": "John Deere IR",
                "title": "John Deere 3Q 2026 Earnings Call",
                "url": "https://investor.deere.com/events/event-details/2026/John-Deere---3Q-Earnings-Call/default.aspx",
            },
        ],
    }

    editorial_quality.validate_generated(generated)
    html = render_html.render("us", DATE_STR, price_data, generated)
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    (output_dir / "us_2026-08-31_editorial.html").write_text(html, encoding="utf-8")
    # 워드프레스에 들어가는 것과 같은 CSS 스코프 결과를 별도 파일로 남겨,
    # 임시저장 글이 비공개여도 레이아웃을 화면에서 검수할 수 있게 합니다.
    wordpress_preview = """<!doctype html>
<html lang=\"ko\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<style>body{margin:0;background:#f7f6f3}main{max-width:900px;margin:0 auto;padding:48px 24px}</style>
</head><body><main>""" + publish_wordpress._to_wordpress_content(html) + "</main></body></html>"
    (output_dir / "us_2026-08-31_wordpress-preview.html").write_text(
        wordpress_preview, encoding="utf-8"
    )
    (output_dir / "us_2026-08-31_editorial.txt").write_text(
        render_text.render("us", DATE_STR, price_data, generated), encoding="utf-8"
    )

    result = publish_wordpress.update_draft(
        POST_ID,
        generated["title"],
        html,
        excerpt=(generated["narrative"][0]["body"].replace("\n\n", " ")[:280] + "…"),
        tags=["미국증시", "WTI 원유", "미국 국채금리", "디어", "테슬라", "엔비디아"],
        category="Daily",
        featured_media_id=featured_media["id"],
    )
    print(f"업데이트 완료: id={result['id']} {result['link']}")


if __name__ == "__main__":
    main()
