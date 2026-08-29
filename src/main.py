"""매일 두 번(미국장/한국장) 실행하는 진입점.

사용법:
    python -m src.main --market us
    python -m src.main --market kr
    python -m src.main --market kr --en   # 해외 독자용 영어 번역판도 함께 생성 (Claude API 1회 추가 호출)

흐름: 시세 수집(fetch_*.py) -> 문구 생성(generate_post.py) -> HTML 렌더링(render_html.py)
      -> output/ 폴더에 저장 -> (설정돼 있으면) 워드프레스에 임시저장 업로드(publish_wordpress.py)

비용 절약: 생성된 결과는 output/{market}_{date}_generated.json에 캐시됩니다. 같은 날
같은 market으로 다시 실행하면(예: CSS만 바꾸고 재확인할 때) Claude API를 다시
호출하지 않고 이 캐시를 재사용합니다. 새로 생성하고 싶으면 그 파일을 지우세요.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from src import (
    fetch_images,
    generate_post,
    history,
    publish_wordpress,
    render_html,
    render_text,
    translate_post,
)

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def _meta_description(generated: dict, limit: int = 300) -> str:
    """검색엔진 메타 설명 + 워드프레스 홈 화면 글 미리보기(발췌문)에 함께 쓰입니다.
    첫 narrative 섹션 전체를 이어붙여서 자르므로, 첫 문단만 쓸 때보다 홈
    화면에서 실제로 무슨 내용인지 더 잘 드러납니다.
    """
    body = (generated.get("narrative") or [{}])[0].get("body", "").replace("\n\n", " ")
    if len(body) <= limit:
        return body.strip()
    return body[:limit].rsplit(" ", 1)[0].strip() + "…"


def _first_image(generated: dict) -> dict | None:
    """인사이트 섹션에서 이미 구해온 사진 중 하나를 돌려줍니다.
    _featured_image()가 제목에 언급된 종목/자산을 못 찾았을 때만 쓰는
    최후의 대안입니다 — 본문 아무 소재나 대표 이미지로 쓰면 제목과 안 맞는
    사진이 뜰 수 있어서, 가능하면 이 함수 대신 _featured_image()를 씁니다.
    """
    stories = (generated.get("insight_section") or {}).get("stories", [])
    for story in stories:
        if story.get("image"):
            return story["image"]
    return None


def _featured_image(generated: dict, price_data: dict, lang: str = "ko") -> dict | None:
    """대표 이미지는 제목에 실제로 언급된 종목 이름으로 새로 검색해서
    구합니다. 인사이트 섹션 사진을 그냥 재활용하면(순서상 처음 나온 것)
    그날 언급된 여러 종목 중 아무거나 뜰 수 있어 제목과 안 맞을 수 있기
    때문입니다 (예: 제목은 "아마존 홀로 상승"인데 사진은 엔비디아).

    watchlist(개별 종목)만 대상으로 합니다. macro(지수·환율·금리·원자재)는
    일부러 뺐습니다 — 실제로 "원화"로 검색해봤더니 위안화 사진이 나오는 등,
    통화·지수 같은 추상적인 개념은 Unsplash 검색 결과가 실제로 안 맞는
    사진을 줄 때가 많아서(직접 다운받아 확인함) 브랜드/제품처럼 사진으로
    분명하게 알아볼 수 있는 개별 종목만 이 방식을 씁니다.

    제목 문자열 안에서 가장 먼저 등장하는 종목 이름을 찾아 그 이름으로
    Unsplash를 다시 검색합니다 — Unsplash 검색은 무료라 추가 비용은 없습니다.
    매치되는 종목이 하나도 없으면 _first_image()로 대체합니다.
    """
    title = generated.get("title", "")
    name_field = "name_en" if lang == "en" else "name"
    entries = price_data.get("watchlist", {})

    matches = []
    for entry in entries.values():
        name = entry.get(name_field) or entry.get("name")
        if name and name in title:
            matches.append((title.index(name), entry.get("name_en") or name))
    if not matches:
        return _first_image(generated)

    matches.sort(key=lambda m: m[0])
    query = matches[0][1]

    used_ids = {
        s["image"]["id"]
        for s in (generated.get("insight_section") or {}).get("stories", [])
        if s.get("image")
    }
    image = fetch_images.search_image(query, exclude_ids=used_ids)
    return image or _first_image(generated)


def _derive_tags(generated: dict, price_data: dict, lang: str = "ko", limit: int = 12) -> list[str]:
    """그날 언급된 종목명·업종명을 태그로 씁니다. 관련 글 탐색·SEO에 가장
    직접적으로 도움되는 조합이라 여기서 추가 LLM 호출 없이 만듭니다.
    """
    names: list[str] = []

    stock_section = generated.get("stock_section") or {}
    for ticker in stock_section.get("featured_tickers", []):
        entry = price_data.get("watchlist", {}).get(ticker)
        if entry:
            names.append(entry.get("name_en") or entry["name"] if lang == "en" else entry["name"])

    theme_section = generated.get("theme_section") or {}
    for h in theme_section.get("highlights", []):
        if h.get("label"):
            names.append(h["label"])

    seen: list[str] = []
    for name in names:
        if name and name not in seen:
            seen.append(name)
    return seen[:limit]


def run(market: str, with_english: bool = False) -> Path:
    if market == "us":
        from src import fetch_us as fetcher
    elif market == "kr":
        from src import fetch_kr as fetcher
    else:
        raise ValueError("market은 'us' 또는 'kr' 이어야 합니다.")

    date_str = dt.date.today().isoformat()

    print(f"[1/5] {market} 시세 수집 중...")
    price_data = fetcher.fetch_all()

    generated_path = OUTPUT_DIR / f"{market}_{date_str}_generated.json"
    if generated_path.exists():
        print(f"[2/5] 캐시된 생성 결과 재사용 ({generated_path}) — Claude API 재호출 안 함.")
        generated = json.loads(generated_path.read_text(encoding="utf-8"))
    else:
        print("[2/5] 제목/본문 생성 중 (Claude API)...")
        recent_headings = history.load_recent_headings(market)
        generated = generate_post.generate(
            market, date_str, price_data, recent_headings=recent_headings
        )
        OUTPUT_DIR.mkdir(exist_ok=True)
        generated_path.write_text(
            json.dumps(generated, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    print("[3/5] 인사이트 소재별 사진 검색 중 (Unsplash)...")
    if generated.get("insight_section", {}).get("stories"):
        generated["insight_section"]["stories"] = fetch_images.attach_images(
            generated["insight_section"]["stories"]
        )

    print("[4/5] HTML 렌더링 중...")
    subscribe_form_action = os.environ.get("SUBSCRIBE_FORM_ACTION")
    html = render_html.render(
        market, date_str, price_data, generated, subscribe_form_action=subscribe_form_action
    )
    text = render_text.render(market, date_str, price_data, generated)

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"{market}_{date_str}.html"
    text_path = OUTPUT_DIR / f"{market}_{date_str}.txt"
    out_path.write_text(html, encoding="utf-8")
    text_path.write_text(text, encoding="utf-8")
    print(f"완료: {out_path}")
    print(f"완료(텍스트): {text_path}")

    if publish_wordpress.is_configured():
        print("[5/5] 워드프레스에 임시저장 업로드 중...")
        result = publish_wordpress.publish_draft(
            generated["title"],
            html,
            excerpt=_meta_description(generated),
            tags=_derive_tags(generated, price_data),
            category="Daily",
            image=_featured_image(generated, price_data, lang="ko"),
        )
        edit_link = result.get("link", "")
        print(f"완료(워드프레스 임시저장): id={result.get('id')} {edit_link}")
    else:
        print("[5/5] WORDPRESS_URL/USERNAME/APP_PASSWORD가 없어 워드프레스 업로드는 건너뜁니다.")

    history.append(market, date_str, generated)

    if market == "kr" and with_english:
        _run_english_version(date_str, price_data, generated)

    return out_path


def _run_english_version(date_str: str, price_data: dict, generated: dict) -> None:
    """한국장 결과물을 해외 독자용 영어 버전으로 각색해 별도 HTML로 만들고,
    (설정돼 있으면) 워드프레스에도 별도 임시저장 글로 올립니다.
    """
    generated_en_path = OUTPUT_DIR / f"kr_{date_str}_generated_en.json"
    if generated_en_path.exists():
        print(f"[EN 1/3] 캐시된 번역 결과 재사용 ({generated_en_path}) — Claude API 재호출 안 함.")
        generated_en = json.loads(generated_en_path.read_text(encoding="utf-8"))
    else:
        print("[EN 1/3] 영어 버전 각색 중 (Claude API)...")
        generated_en = translate_post.translate(generated)
        generated_en_path.write_text(
            json.dumps(generated_en, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    kr_images_by_query = {
        story.get("image_query"): story.get("image")
        for story in (generated.get("insight_section") or {}).get("stories", [])
    }
    en_stories = (generated_en.get("insight_section") or {}).get("stories") or []
    for story in en_stories:
        story["image"] = kr_images_by_query.get(story.get("image_query"))

    print("[EN 2/3] 영어 HTML 렌더링 중...")
    html_en = render_html.render(
        "kr", date_str, price_data, generated_en, lang="en", market_label="Korea Market Close",
        subscribe_form_action=os.environ.get("SUBSCRIBE_FORM_ACTION"),
    )
    out_path_en = OUTPUT_DIR / f"kr_{date_str}_en.html"
    out_path_en.write_text(html_en, encoding="utf-8")
    print(f"완료(영어): {out_path_en}")

    if publish_wordpress.is_configured():
        print("[EN 3/3] 워드프레스에 영어 버전 임시저장 업로드 중...")
        result = publish_wordpress.publish_draft(
            generated_en["title"],
            html_en,
            lang="en",
            excerpt=_meta_description(generated_en),
            tags=_derive_tags(generated_en, price_data, lang="en"),
            category="Daily",
            image=_featured_image(generated_en, price_data, lang="en"),
        )
        print(f"완료(워드프레스 임시저장, 영어): id={result.get('id')} {result.get('link', '')}")
    else:
        print("[EN 3/3] WORDPRESS_* 환경변수가 없어 영어 버전 워드프레스 업로드는 건너뜁니다.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="시황 블로그 초안 자동 생성")
    parser.add_argument("--market", choices=["us", "kr"], required=True)
    parser.add_argument(
        "--en",
        action="store_true",
        help="한국장(kr)일 때 영어 번역판도 만듭니다. Claude API 호출이 1번 더 늘어납니다 (기본: 끔).",
    )
    args = parser.parse_args()
    run(args.market, with_english=args.en)
