"""시황(매일) 글과 별개로, 검색 유입을 노리는 상시(evergreen) 가이드 글을 올립니다.

시황 글은 generate_post.py/translate_post.py가 Claude API를 호출해 문구를
만들지만, 가이드 글은 API 호출 없이 이 스크립트를 부르는 쪽(대화 중인
Claude Code 세션)이 직접 조사하고 쓴 본문을 그대로 넘깁니다 — 그래서
build_generated()가 받는 narrative/closing은 이미 완성된 텍스트입니다.

render_html.render()는 macro_cards가 비어 있으면(post.html.j2의
{% if macro_cards %} 가드) 시세 그리드를 그냥 건너뛰므로, price_data를
빈 dict로 넘기면 시황 글과 같은 mb- 스타일을 그대로 재사용하면서
가격 카드 없는 글도 문제없이 렌더링됩니다.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from src import editorial_title, fetch_images, publish_wordpress, render_html

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

_EMPTY_PRICE_DATA = {"macro": {}, "watchlist": {}}


def _meta_description(generated: dict, limit: int = 300) -> str:
    body = (generated.get("narrative") or [{}])[0].get("body", "").replace("\n\n", " ")
    if len(body) <= limit:
        return body.strip()
    return body[:limit].rsplit(" ", 1)[0].strip() + "…"


def build_generated(
    title: str,
    sections: list[dict],
    closing: dict | None = None,
    insight_section: dict | None = None,
) -> dict:
    generated = {"title": title, "narrative": sections}
    if insight_section:
        generated["insight_section"] = insight_section
    if closing:
        generated["closing"] = closing
    return generated


def _featured_credit_html(image: dict, lang: str) -> str:
    """대표 이미지 출처를 본문 맨 아래에 한 줄로 답니다.

    대표 이미지는 본문에서 빼기 때문에(아래 publish_guide 참고) 사진 밑에 붙던
    출처 표기도 같이 사라집니다. Unsplash는 법적으로 출처 표기를 요구하지는
    않지만 이 사이트는 지금까지 계속 밝혀 왔으므로, 표기를 잃지 않도록 글
    끝으로 옮깁니다.
    """
    if image.get("credit"):
        return f'<p class="mb-photo-credit mb-featured-credit">{image["credit"]}</p>'
    if image.get("photographer") and image.get("photographer_url"):
        label = "Featured photo" if lang == "en" else "대표 사진"
        return (
            f'<p class="mb-photo-credit mb-featured-credit">{label}: '
            f'<a href="{image["photographer_url"]}" target="_blank" rel="noopener">'
            f'{image["photographer"]}</a> / Unsplash</p>'
        )
    return ""


def publish_guide(
    slug: str,
    title: str,
    sections: list[dict],
    closing: dict | None = None,
    insight_section: dict | None = None,
    lang: str = "en",
    market_label: str = "Investor Guide",
    tags: list[str] | None = None,
    category: str = "Guides",
    post_id: int | None = None,
    focus_keyword: str | None = None,
    featured_image_query: str | None = None,
) -> dict:
    """post_id를 주면 새 글을 만드는 대신 기존 글(예: 검수 중인 초안)을
    같은 자리에서 업데이트합니다 — 검수 피드백 반영 때마다 임시저장 글이
    중복으로 쌓이지 않게 하기 위함입니다.

    featured_image_query: 대표 이미지 전용 검색어. 주면 본문 사진과 **별개로**
    한 장을 더 찾아 대표 이미지로 씁니다. 주지 않으면 본문 첫 사진을 대표로
    올리고 같은 사진이 두 번 보이지 않도록 본문에서는 뺍니다.
    글 맨 위(대표)와 본문에 같은 사진이 나오던 문제 때문에 붙인 인자이고,
    검색어를 부르는 쪽이 정하게 한 이유는 **받은 사진을 눈으로 확인한 사람만
    그 검색어가 맞는지 판단할 수 있기 때문**입니다(원화 검색에 위안화가
    나오는 식의 사고를 자동화로는 못 막습니다).
    """
    featured_image = None
    if insight_section and insight_section.get("stories"):
        stories = fetch_images.attach_images(insight_section["stories"])
        if featured_image_query:
            used = {s["image"]["id"] for s in stories if s.get("image")}
            featured_image = fetch_images.search_image(
                featured_image_query, exclude_ids=used
            )
        if featured_image is None:
            featured_image = next((s["image"] for s in stories if s.get("image")), None)
            if featured_image:
                # 대표 이미지는 글 맨 위에 크게 걸립니다. 같은 사진을 본문에도
                # 그대로 두면 독자가 한 화면 안에서 같은 사진을 두 번 보게 되므로,
                # 대표로 올라간 사진은 본문에서 뺍니다. 출처는
                # _featured_credit_html()로 글 끝에 남깁니다.
                stories = [
                    {**s, "image": None} if s.get("image") is featured_image else s
                    for s in stories
                ]
        insight_section = {**insight_section, "stories": stories}
    generated = build_generated(title, sections, closing, insight_section)
    # 제목·소제목 규칙은 모든 글 공통(editorial_title). 손으로 올리는 경로라 경고만 찍습니다.
    for issue in editorial_title.collect_issues(generated, kind="가이드"):
        print(f"[경고] 제목·소제목: {issue}")
    date_str = dt.date.today().isoformat()

    html = render_html.render(
        "guide", date_str, _EMPTY_PRICE_DATA, generated, lang=lang, market_label=market_label
    )

    if featured_image:
        credit = _featured_credit_html(featured_image, lang)
        if credit and "<footer>" in html:
            html = html.replace("<footer>", f"{credit}\n  <footer>", 1)

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"guide_{slug}_{date_str}.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"완료: {out_path}")

    if not publish_wordpress.is_configured():
        # 조용히 빈 dict를 돌려주면 **부르는 쪽은 발행에 성공한 줄 압니다.**
        # 2026-09-06에 같은 모양의 침묵을 세 군데서 찾았습니다(publish_feature의
        # load_dotenv 누락, 한글 폰트 폴백, DART의 "0건"). 실패는 말합니다.
        raise publish_wordpress.WordPressPublishError(
            "워드프레스 설정이 없어 올리지 못했습니다. .env의 WORDPRESS_URL·"
            "WORDPRESS_USERNAME·WORDPRESS_APP_PASSWORD를 확인하십시오. "
            f"렌더된 HTML은 {out_path}에 있습니다.")

    if post_id:
        result = publish_wordpress.update_draft(
            post_id,
            title,
            html,
            excerpt=_meta_description(generated),
            tags=tags,
            category=category,
            lang=lang,
            image=featured_image,
            focus_keyword=focus_keyword,
        )
        print(f"완료(워드프레스 업데이트): id={result.get('id')} {result.get('link', '')}")
        # status=None이라 공개 상태는 그대로입니다. 무엇으로 남았는지 되읽어
        # 확인합니다 — 발행됐다고 출력하고 사이트에는 없던 적이 있습니다.
        publish_wordpress.verify_published(result["id"], title, expected_status=None)
    else:
        result = publish_wordpress.publish_draft(
            title,
            html,
            lang=lang,
            excerpt=_meta_description(generated),
            tags=tags,
            category=category,
            image=featured_image,
            focus_keyword=focus_keyword,
        )
        print(f"완료(워드프레스 임시저장): id={result.get('id')} {result.get('link', '')}")
        publish_wordpress.verify_published(result["id"], title, expected_status="draft")
    return result
