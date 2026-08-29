"""워드프레스 REST API로 완성된 HTML을 임시저장(draft) 글로 올립니다.

필요한 환경변수 (.env):
    WORDPRESS_URL           예: https://example.com
    WORDPRESS_USERNAME      워드프레스 로그인 아이디
    WORDPRESS_APP_PASSWORD  워드프레스 관리자 프로필에서 발급한 "응용 프로그램 비밀번호"
                             (로그인 비밀번호가 아닙니다)

셋 중 하나라도 비어 있으면 업로드를 건너뜁니다.
"""
from __future__ import annotations

import os
import re
import sys

import requests

TIMEOUT_SECONDS = 30

_SCRIPT_TAG_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
_HEAD_RE = re.compile(r"<head[^>]*>(.*?)</head>", re.IGNORECASE | re.DOTALL)
_BODY_RE = re.compile(r"<body[^>]*>(.*?)</body>", re.IGNORECASE | re.DOTALL)
_LINK_TAG_RE = re.compile(r"<link\b[^>]*>", re.IGNORECASE)
_STYLE_TAG_RE = re.compile(r"<style[^>]*>(.*?)</style>", re.IGNORECASE | re.DOTALL)
_CSS_RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}")
_SCOPE_CLASS = "mb-post"


def _scope_css(css: str, scope_class: str = _SCOPE_CLASS) -> str:
    """render_html.py의 CSS는 원래 문서 전체(body, h1~h3, p, *...)를 대상으로
    짜여 있습니다. 워드프레스 글 본문에 그대로 넣으면 그 규칙이 테마 전체
    (제목, 다른 글, 사이드바 등)에도 적용돼 사이트 레이아웃을 깨뜨리므로,
    모든 셀렉터 앞에 감싸는 div(.mb-post)를 붙여 그 안으로만 스코프합니다.

    _CSS_RULE_RE는 한 겹까지만 중첩된 블록(@media 안에 평범한 규칙들만 있는
    경우)은 우연히 문제없이 처리됩니다 — @media의 여는/닫는 중괄호 자체는
    "선택자{본문}" 패턴에 안 걸려서 그대로 남고, 그 안의 개별 규칙만 하나씩
    치환되기 때문입니다. 다만 @media 안에 :root나 * 처럼 더 복잡한 걸 넣거나
    2단 이상 중첩되면 깨지니 새로 추가할 땐 이 함수 출력을 한번 확인하세요.
    """
    scope = f".{scope_class}"

    def repl(match: re.Match) -> str:
        selectors, body = match.group(1), match.group(2)
        scoped = []
        for sel in selectors.split(","):
            sel = sel.strip()
            if not sel:
                continue
            if sel in (":root", "body"):
                scoped.append(scope)
            elif sel == "*":
                scoped.append(f"{scope}, {scope} *")
            else:
                scoped.append(f"{scope} {sel}")
        return f"{', '.join(scoped)} {{{body}}}"

    return _CSS_RULE_RE.sub(repl, css)

# 스크립트가 통째로 빠지는 인사이트 섹션의 막대/선 차트는 빈 캔버스만 남아
# 어색하게 보이므로, 워드프레스로 보낼 때는 아예 숨깁니다.
_EXTRA_CSS = f".{_SCOPE_CLASS} .mb-chart-wrap{{display:none}}"


class WordPressPublishError(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(
        os.environ.get("WORDPRESS_URL")
        and os.environ.get("WORDPRESS_USERNAME")
        and os.environ.get("WORDPRESS_APP_PASSWORD")
    )


def _to_wordpress_content(html_content: str) -> str:
    """render_html.py가 만든 완결된 HTML 문서를 워드프레스 글 본문으로 바꿉니다.

    <!DOCTYPE>/<html>/<head>/<body>가 통째로 들어간 문서를 워드프레스 글
    본문에 그대로 넣으면 워드프레스의 자동 서식(wpautop)이 <style> 블록
    한가운데에 <br>을 끼워넣는 등 완전히 망가뜨립니다. 그래서 <head>의
    <link>/<style>과 <body> 안쪽 내용만 뽑아 재조립하고, 전체를 "Custom
    HTML" 블록(<!-- wp:html -->)으로 감싸서 자동 서식이 손대지 못하게 합니다.
    <script>는 방화벽 차단 및 신뢰성 문제로 어차피 제거합니다.
    """
    head_match = _HEAD_RE.search(html_content)
    body_match = _BODY_RE.search(html_content)
    head = head_match.group(1) if head_match else ""
    body = body_match.group(1) if body_match else html_content

    links = "".join(_LINK_TAG_RE.findall(head))
    raw_css = "".join(_STYLE_TAG_RE.findall(head))
    scoped_css = _scope_css(raw_css)
    body = _SCRIPT_TAG_RE.sub("", body)

    fragment = (
        f"{links}<style>{scoped_css}{_EXTRA_CSS}</style>"
        f'<div class="{_SCOPE_CLASS}">{body}</div>'
    )
    return f"<!-- wp:html -->\n{fragment}\n<!-- /wp:html -->"


def _get_or_create_term_id(
    base_url: str, auth: tuple[str, str], endpoint: str, name: str, lang: str | None = None
) -> int | None:
    """워드프레스 태그/카테고리(taxonomy term)는 이름이 아니라 id로 지정해야
    해서, 이름으로 기존 term을 찾아보고 없으면 새로 만듭니다.

    lang: Polylang 사이트에서 카테고리처럼 언어별로 분리된 taxonomy는 생성 시
    `?lang=` 쿼리 파라미터를 줘야 해당 언어의 term으로 만들어집니다 (글
    생성 때와 같은 방식 — publish_draft의 lang 설명 참고).
    """
    try:
        search = requests.get(
            f"{base_url}/wp-json/wp/v2/{endpoint}",
            auth=auth,
            params={"search": name, "per_page": 100},
            timeout=TIMEOUT_SECONDS,
        )
        match = next((t for t in search.json() if t.get("name") == name), None)
        if match:
            return match["id"]
        created = requests.post(
            f"{base_url}/wp-json/wp/v2/{endpoint}",
            auth=auth,
            params={"lang": lang} if lang else None,
            json={"name": name},
            timeout=TIMEOUT_SECONDS,
        )
        if created.status_code < 400:
            return created.json()["id"]
        print(f"[경고] {endpoint} 생성 실패 ('{name}'): {created.text[:200]}", file=sys.stderr)
    except Exception as e:
        print(f"[경고] {endpoint} 처리 실패 ('{name}'): {e!r}", file=sys.stderr)
    return None


def _get_or_create_tag_ids(base_url: str, auth: tuple[str, str], names: list[str]) -> list[int]:
    ids = [_get_or_create_term_id(base_url, auth, "tags", name) for name in names]
    return [i for i in ids if i is not None]


def upload_featured_image(base_url: str, auth: tuple[str, str], image: dict) -> int | None:
    """fetch_images.py가 돌려준 이미지 dict(url/alt/photographer/photographer_url)를
    실제로 내려받아 워드프레스 미디어 라이브러리에 올리고, 대표 이미지(featured
    image)로 쓸 수 있는 첨부파일 id를 돌려줍니다.

    실패해도 전체 업로드를 막으면 안 되므로 None을 돌려주고 넘어갑니다 —
    대표 이미지는 있으면 좋지만 없다고 글 자체가 안 올라가면 안 됩니다.
    """
    try:
        img_resp = requests.get(image["url"], timeout=TIMEOUT_SECONDS)
        img_resp.raise_for_status()

        filename = f"{image.get('id') or 'photo'}.jpg"
        upload = requests.post(
            f"{base_url}/wp-json/wp/v2/media",
            auth=auth,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": "image/jpeg",
            },
            data=img_resp.content,
            timeout=TIMEOUT_SECONDS,
        )
        if upload.status_code >= 400:
            print(f"[경고] 대표 이미지 업로드 실패: {upload.text[:200]}", file=sys.stderr)
            return None
        media_id = upload.json()["id"]

        # Unsplash API 정책상 사진을 쓸 때는 사진작가/Unsplash 표기가 필요합니다.
        # 대표 이미지 슬롯 자체엔 표기가 안 붙으므로 미디어 라이브러리 캡션에
        # 남겨둡니다 (같은 사진이 본문에도 쓰였다면 거기엔 이미 표기가 있습니다).
        photographer = image.get("photographer", "")
        photographer_url = image.get("photographer_url", "")
        caption = (
            f'Photo: <a href="{photographer_url}" target="_blank" rel="noopener">'
            f"{photographer}</a> / Unsplash"
        )
        requests.post(
            f"{base_url}/wp-json/wp/v2/media/{media_id}",
            auth=auth,
            json={"alt_text": image.get("alt", ""), "caption": caption},
            timeout=TIMEOUT_SECONDS,
        )
        return media_id
    except Exception as e:
        print(f"[경고] 대표 이미지 처리 실패: {e!r}", file=sys.stderr)
        return None


def publish_draft(
    title: str,
    html_content: str,
    lang: str | None = None,
    excerpt: str | None = None,
    tags: list[str] | None = None,
    category: str | None = None,
    image: dict | None = None,
) -> dict:
    """워드프레스에 임시저장 글을 만들고 응답 JSON(dict)을 돌려줍니다.

    lang: Polylang 언어 코드(예: "en")로 글을 생성해봅니다. 참고: `GET
    /wp/v2/posts?lang=en` 같은 목록 필터링은 이 사이트의 Polylang 무료판에서
    무시되지만(가짜 값을 넣어도 결과가 똑같음), `POST /wp/v2/posts?lang=en`로
    글을 "생성"할 때는 실제로 언어가 지정됩니다 — 생성된 글의 링크에 `/en/`
    접두사가 붙고 해당 언어의 기본 카테고리로 분류되는 것으로 확인했습니다.
    그래도 사이트 설정에 따라 달라질 수 있으니, 아래에서 결과를 실제로
    확인해서 애매하면 수동 확인을 안내합니다.

    excerpt: 검색엔진 메타 설명(SEO)으로 쓰일 짧은 요약. 이 사이트엔 별도
    SEO 플러그인(Yoast/RankMath 등)이 안 깔려 있어서 전용 메타 설명 필드가
    없는데, 워드프레스 기본 "발췌문(excerpt)" 필드는 테마가 메타 설명
    대체용으로 자주 쓰므로 여기 넣어둡니다.

    tags: 그날 언급된 종목명·테마명 같은 태그 이름 목록. 없는 태그는 자동으로
    새로 만듭니다.

    category: 카테고리 이름 (예: "시황"). 시황 자동생성 글과 나중에 추가할
    다른 종류의 글을 홈 화면에서 구분해 보여주는 용도입니다. 없는 카테고리는
    자동으로 만듭니다 (lang이 있으면 그 언어로).

    image: fetch_images.py가 돌려준 이미지 dict. 있으면 워드프레스 미디어
    라이브러리에 올려서 대표 이미지(featured image)로 지정합니다 — 홈
    화면 카드에 썸네일이 뜨게 하는 용도.
    """
    base_url = os.environ["WORDPRESS_URL"].rstrip("/")
    username = os.environ["WORDPRESS_USERNAME"]
    app_password = os.environ["WORDPRESS_APP_PASSWORD"]
    auth = (username, app_password)

    safe_content = _to_wordpress_content(html_content)

    payload = {"title": title, "content": safe_content, "status": "draft"}
    if excerpt:
        payload["excerpt"] = excerpt
    if tags:
        payload["tags"] = _get_or_create_tag_ids(base_url, auth, tags)
    if category:
        cat_id = _get_or_create_term_id(base_url, auth, "categories", category, lang=lang)
        if cat_id:
            payload["categories"] = [cat_id]
    if image:
        media_id = upload_featured_image(base_url, auth, image)
        if media_id:
            payload["featured_media"] = media_id

    endpoint = f"{base_url}/wp-json/wp/v2/posts"
    response = requests.post(
        endpoint,
        auth=auth,
        params={"lang": lang} if lang else None,
        json=payload,
        timeout=TIMEOUT_SECONDS,
    )

    if response.status_code >= 400:
        raise WordPressPublishError(
            f"워드프레스 업로드 실패 (HTTP {response.status_code}): {response.text[:500]}"
        )

    result = response.json()

    if lang:
        link = result.get("link", "")
        tagged = f"/{lang}/" in link
        if tagged:
            print(f"[안내] Polylang 언어 태깅 확인됨: {link} (언어={lang})")
        else:
            print(
                f"[안내] Polylang 언어 태깅이 됐는지 확실치 않습니다 (링크에 '/{lang}/'이 "
                f"안 보임: {link}) — 워드프레스 관리자 화면에서 이 글(id={result.get('id')})을 "
                f"열어 오른쪽 사이드바에서 언어를 {lang}로 확인/설정하고, 원본 글과 번역 "
                f"연결도 확인해주세요.",
                file=sys.stderr,
            )

    return result


def update_draft(
    post_id: int,
    title: str,
    html_content: str,
    lang: str | None = None,
    excerpt: str | None = None,
    tags: list[str] | None = None,
    category: str | None = None,
    image: dict | None = None,
) -> dict:
    """이미 올라간 글(주로 검수 중인 임시저장 글)의 내용을 그 자리에서
    갱신합니다. publish_draft와 인자가 같지만 새 글을 만들지 않고
    기존 post_id를 덮어써서, 피드백 반영마다 임시저장 글이 중복으로
    쌓이는 걸 막습니다.
    """
    base_url = os.environ["WORDPRESS_URL"].rstrip("/")
    username = os.environ["WORDPRESS_USERNAME"]
    app_password = os.environ["WORDPRESS_APP_PASSWORD"]
    auth = (username, app_password)

    safe_content = _to_wordpress_content(html_content)

    payload = {"title": title, "content": safe_content}
    if excerpt:
        payload["excerpt"] = excerpt
    if tags:
        payload["tags"] = _get_or_create_tag_ids(base_url, auth, tags)
    if category:
        cat_id = _get_or_create_term_id(base_url, auth, "categories", category, lang=lang)
        if cat_id:
            payload["categories"] = [cat_id]
    if image:
        media_id = upload_featured_image(base_url, auth, image)
        if media_id:
            payload["featured_media"] = media_id

    endpoint = f"{base_url}/wp-json/wp/v2/posts/{post_id}"
    response = requests.post(endpoint, auth=auth, json=payload, timeout=TIMEOUT_SECONDS)

    if response.status_code >= 400:
        raise WordPressPublishError(
            f"워드프레스 업데이트 실패 (HTTP {response.status_code}): {response.text[:500]}"
        )

    return response.json()
