"""한국장·미국장 시황을 무료 생성해 HTML과 워드프레스 초안으로 저장합니다.

사용법:
    python -m src.main --market us
    python -m src.main --market kr --en

외부 생성형 AI API는 호출하지 않습니다. 한국장 ``--en`` 옵션은 동일한 시세
데이터에서 영어판을 별도로 작성하고 한국어판과 함께 검증한 뒤 업로드합니다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from src import (
    editorial_quality,
    editorial_quality_en,
    data_quality,
    fetch_news,
    featured_image,
    generate_free,
    generate_free_en,
    history,
    publish_wordpress,
    render_html,
    render_text,
)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
CACHE_VERSION = 5


def _meta_description(generated: dict, limit: int = 300) -> str:
    body = (generated.get("narrative") or [{}])[0].get("body", "").replace("\n\n", " ")
    if len(body) <= limit:
        return body.strip()
    return body[:limit].rsplit(" ", 1)[0].strip() + "…"


def _focus_keyword(market: str, lang: str = "ko") -> str:
    """시황 글의 Rank Math 포커스 키워드.

    키워드를 안 넣으면 글 목록에 "키워드 미설정"으로 남고 Rank Math의 SEO
    분석이 동작하지 않습니다. 시황은 매일 같은 형식이라 시장·언어별 고정
    문구로 충분합니다.
    """
    if lang == "en":
        return "Kospi close" if market == "kr" else "US stocks close"
    return "코스피 마감 시황" if market == "kr" else "뉴욕증시 마감"


def _derive_tags(
    generated: dict, price_data: dict, lang: str = "ko", limit: int = 12
) -> list[str]:
    names: list[str] = []
    stock_section = generated.get("stock_section") or {}
    for ticker in stock_section.get("featured_tickers", []):
        entry = price_data.get("watchlist", {}).get(ticker)
        if entry:
            names.append(
                (entry.get("name_en") or entry["name"]) if lang == "en" else entry["name"]
            )

    for highlight in (generated.get("theme_section") or {}).get("highlights", []):
        if highlight.get("label"):
            names.append(highlight["label"])

    unique: list[str] = []
    for name in names:
        if name and name not in unique:
            unique.append(name)
    return unique[:limit]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: dict) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_current_cache(path: Path) -> dict | None:
    if not path.exists():
        return None
    cached = _read_json(path)
    if cached.get("_generator_version") != CACHE_VERSION:
        print(f"[안내] 생성 규칙이 바뀌어 이전 캐시를 새로 만듭니다 ({path}).")
        return None
    return cached


def _fetch_news_safely(market: str) -> list[dict]:
    try:
        return fetch_news.fetch_headlines(market)
    except Exception as exc:  # noqa: BLE001 - RSS 장애가 종가 초안을 막지 않게 함
        print(f"[경고] 언론사 RSS 조회 실패, 뉴스 링크 없이 계속합니다: {exc}")
        return []


def _draft_slug(market: str, date_str: str, lang: str) -> str:
    return f"market-brief-{market}-{date_str}-{lang}"


def _fetch_price_data(fetcher, market: str) -> dict:
    attempts = 3 if market == "kr" else 1
    for attempt in range(1, attempts + 1):
        price_data = fetcher.fetch_all()
        try:
            data_quality.validate_trading_dates(market, price_data)
            return price_data
        except data_quality.MarketDataNotReadyError:
            if attempt >= attempts:
                raise
            print(
                f"[대기] 장마감 데이터 기준일이 아직 섞여 있어 45초 뒤 재확인합니다 "
                f"({attempt}/{attempts})."
            )
            time.sleep(45)
    raise RuntimeError("시세 수집 재시도 흐름이 비정상적으로 종료됐습니다.")


def run(market: str, with_english: bool = False, publish: bool = True) -> Path | None:
    if market == "us":
        from src import fetch_us as fetcher
    elif market == "kr":
        from src import fetch_kr as fetcher
    else:
        raise ValueError("market은 'us' 또는 'kr' 이어야 합니다.")
    if with_english and market != "kr":
        raise ValueError("영어판 자동 생성은 한국장(--market kr)에서만 지원합니다.")

    print(f"[1/4] {market} 시세 수집 중...")
    price_data = _fetch_price_data(fetcher, market)
    trading_date = price_data.get("trading_date")
    date_str = trading_date or dt.date.today().isoformat()

    ko_cache = OUTPUT_DIR / f"{market}_{date_str}_generated_free.json"
    en_cache = OUTPUT_DIR / f"kr_{date_str}_generated_free_en.json"
    generated_ko = _read_current_cache(ko_cache)
    generated_en = _read_current_cache(en_cache) if with_english else None
    if (
        trading_date
        and history.already_published(market, trading_date)
        and generated_ko is not None
        and (not with_english or generated_en is not None)
    ):
        print(
            f"[중단] {trading_date} 거래일 결과가 이미 생성·처리되어 추가 작업 없이 건너뜁니다."
        )
        return None

    needs_news = generated_ko is None or (with_english and generated_en is None)
    recent_news = _fetch_news_safely(market) if needs_news else []

    if generated_ko is not None:
        print(f"[2/4] 한국어 생성 결과 재사용 ({ko_cache}).")
    else:
        print("[2/4] 시세·RSS 기반 한국어 시황 생성 중...")
        generated_ko = generate_free.generate(
            market, date_str, price_data, recent_news=recent_news
        )
        generated_ko["_generator_version"] = CACHE_VERSION
        _write_json(ko_cache, generated_ko)

    if with_english:
        if generated_en is not None:
            print(f"[2/4] 영어 생성 결과 재사용 ({en_cache}).")
        else:
            print("[2/4] 같은 시세에서 영어 시황 직접 작성 중...")
            generated_en = generate_free_en.generate(
                date_str, price_data, recent_news=recent_news
            )
            generated_en["_generator_version"] = CACHE_VERSION
            _write_json(en_cache, generated_en)

    # 어느 한 언어라도 검사에 실패하면 워드프레스 업로드 전에 중단합니다.
    editorial_quality.validate_generated(generated_ko)
    if generated_en:
        editorial_quality_en.validate_generated(generated_en)

    print("[3/4] 한국어·영어 결과 렌더링 중..." if generated_en else "[3/4] 결과 렌더링 중...")
    subscribe_form_action = os.environ.get("SUBSCRIBE_FORM_ACTION")
    html_ko = render_html.render(
        market,
        date_str,
        price_data,
        generated_ko,
        subscribe_form_action=subscribe_form_action,
    )
    text_ko = render_text.render(market, date_str, price_data, generated_ko)
    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"{market}_{date_str}.html"
    out_path.write_text(html_ko, encoding="utf-8")
    (OUTPUT_DIR / f"{market}_{date_str}.txt").write_text(text_ko, encoding="utf-8")

    html_en: str | None = None
    if generated_en:
        html_en = render_html.render(
            "kr",
            date_str,
            price_data,
            generated_en,
            lang="en",
            market_label="Korea Market Close",
            subscribe_form_action=subscribe_form_action,
        )
        (OUTPUT_DIR / f"kr_{date_str}_en.html").write_text(html_en, encoding="utf-8")
        (OUTPUT_DIR / f"kr_{date_str}_en.txt").write_text(
            render_text.render("kr", date_str, price_data, generated_en, lang="en"),
            encoding="utf-8",
        )

    print(f"완료: {out_path}")
    if html_en:
        print(f"완료(영어): {OUTPUT_DIR / f'kr_{date_str}_en.html'}")

    image_path = OUTPUT_DIR / f"{market}_{date_str}_featured.png"
    image = featured_image.create(market, date_str, price_data, image_path)
    print(f"완료(대표 이미지): {image_path}")

    if publish and publish_wordpress.is_configured():
        print("[4/4] 워드프레스 임시저장 업로드 중...")
        ko_result = publish_wordpress.publish_draft(
            generated_ko["title"],
            html_ko,
            excerpt=_meta_description(generated_ko),
            tags=_derive_tags(generated_ko, price_data),
            category="Daily",
            image=image,
            slug=_draft_slug(market, date_str, "ko"),
            focus_keyword=_focus_keyword(market, "ko"),
        )
        print(f"완료(한국어 초안): id={ko_result.get('id')} {ko_result.get('link', '')}")

        if generated_en and html_en:
            en_result = publish_wordpress.publish_draft(
                generated_en["title"],
                html_en,
                lang="en",
                excerpt=_meta_description(generated_en),
                tags=_derive_tags(generated_en, price_data, lang="en"),
                category="Daily",
                image=image if not ko_result.get("featured_media") else None,
                featured_media_id=ko_result.get("featured_media") or None,
                slug=_draft_slug("kr", date_str, "en"),
                focus_keyword=_focus_keyword("kr", "en"),
            )
            print(f"완료(영어 초안): id={en_result.get('id')} {en_result.get('link', '')}")
    elif publish:
        print("[4/4] 워드프레스 설정이 없어 파일 생성까지만 완료했습니다.")
    else:
        print("[4/4] 시험 실행이라 워드프레스 업로드를 건너뛰었습니다.")

    if publish:
        history.append(market, date_str, generated_ko, trading_date=trading_date)
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="시황 블로그 초안 자동 생성")
    parser.add_argument("--market", choices=["us", "kr"], required=True)
    parser.add_argument(
        "--en",
        action="store_true",
        help="한국장 시황의 영어판도 같은 데이터에서 무료로 생성합니다.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="파일 생성과 품질 검사만 하고 워드프레스에는 올리지 않습니다.",
    )
    args = parser.parse_args()
    run(args.market, with_english=args.en, publish=not args.dry_run)
