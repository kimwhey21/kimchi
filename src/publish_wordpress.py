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
from pathlib import Path

import requests

TIMEOUT_SECONDS = 30

_SCRIPT_TAG_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
_HEAD_RE = re.compile(r"<head[^>]*>(.*?)</head>", re.IGNORECASE | re.DOTALL)
_BODY_RE = re.compile(r"<body[^>]*>(.*?)</body>", re.IGNORECASE | re.DOTALL)
_LINK_TAG_RE = re.compile(r"<link\b[^>]*>", re.IGNORECASE)
_STYLE_TAG_RE = re.compile(r"<style[^>]*>(.*?)</style>", re.IGNORECASE | re.DOTALL)
_SCOPE_CLASS = "mb-post"


def _scope_css(css: str, scope_class: str = _SCOPE_CLASS) -> str:
    """render_html.py의 CSS는 원래 문서 전체(body, h1~h3, p, *...)를 대상으로
    짜여 있습니다. 워드프레스 글 본문에 그대로 넣으면 그 규칙이 테마 전체
    (제목, 다른 글, 사이드바 등)에도 적용돼 사이트 레이아웃을 깨뜨리므로,
    모든 셀렉터 앞에 감싸는 div(.mb-post)를 붙여 그 안으로만 스코프합니다.

    CSS는 @media처럼 중첩 블록을 가질 수 있습니다. 정규식으로 한 번에 바꾸면
    중첩 중괄호를 잘못 짚어 모바일 규칙이 깨질 수 있으므로, 블록 경계를 직접
    읽으면서 일반 선택자만 스코프합니다.
    """
    scope = f".{scope_class}"

    def scope_selectors(selectors: str) -> str:
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
        return ", ".join(scoped)

    output: list[str] = []
    position = 0
    length = len(css)
    while position < length:
        opening = css.find("{", position)
        if opening == -1:
            output.append(css[position:])
            break

        selector = css[position:opening]
        depth = 1
        closing = opening + 1
        while closing < length and depth:
            if css[closing] == "{":
                depth += 1
            elif css[closing] == "}":
                depth -= 1
            closing += 1

        # 비정상 CSS는 원문을 유지합니다. 발행 과정이 스타일을 망가뜨리는
        # 것보다 원문을 남기는 편이 안전합니다.
        if depth:
            output.append(css[position:])
            break

        body = css[opening + 1 : closing - 1]
        stripped = selector.strip()
        if stripped.startswith("@"):
            # keyframes 내부의 from/to/% 선택자는 문서 선택자가 아니므로 손대지
            # 않고, 미디어/지원 규칙처럼 일반 CSS를 담는 블록만 재귀 처리합니다.
            if stripped.startswith(("@media", "@supports", "@container", "@layer")):
                output.append(f"{selector}{{{_scope_css(body, scope_class)}}}")
            else:
                output.append(f"{selector}{{{body}}}")
        else:
            output.append(f"{scope_selectors(selector)} {{{body}}}")
        position = closing

    return "".join(output)

# 스크립트가 통째로 빠지는 인사이트 섹션의 막대/선 차트는 빈 캔버스만 남아
# 어색하게 보이므로, 워드프레스로 보낼 때는 아예 숨깁니다.
_EXTRA_CSS = (
    f".{_SCOPE_CLASS}{{width:100%;max-width:760px;margin:0 auto;padding:0!important;"
    "box-sizing:border-box;overflow:hidden}}"
    f".{_SCOPE_CLASS} .mb-chart-wrap{{display:none}}"
)


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
            params={
                "search": name,
                "per_page": 100,
                **({"lang": lang} if lang else {}),
            },
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


def _find_existing_post_by_slug(
    base_url: str, auth: tuple[str, str], slug: str
) -> dict | None:
    """재실행 때 같은 글을 새로 만들지 않도록 고정 slug의 기존 글을 찾습니다."""
    response = requests.get(
        f"{base_url}/wp-json/wp/v2/posts",
        auth=auth,
        params=[
            ("slug", slug),
            ("context", "edit"),
            ("per_page", "1"),
            *(('status[]', status) for status in ("publish", "future", "draft", "pending", "private")),
        ],
        timeout=TIMEOUT_SECONDS,
    )
    if response.status_code >= 400:
        raise WordPressPublishError(
            f"기존 초안 확인 실패 (HTTP {response.status_code}): {response.text[:500]}"
        )
    posts = response.json()
    return posts[0] if posts else None


def upload_featured_image(base_url: str, auth: tuple[str, str], image: dict) -> int | None:
    """fetch_images.py가 돌려준 이미지 dict(url/alt/photographer/photographer_url)를
    실제로 내려받아 워드프레스 미디어 라이브러리에 올리고, 대표 이미지(featured
    image)로 쓸 수 있는 첨부파일 id를 돌려줍니다.

    실패해도 전체 업로드를 막으면 안 되므로 None을 돌려주고 넘어갑니다 —
    대표 이미지는 있으면 좋지만 없다고 글 자체가 안 올라가면 안 됩니다.
    """
    try:
        local_path = image.get("local_path")
        if local_path:
            path = Path(local_path)
            image_bytes = path.read_bytes()
            filename = path.name
            content_type = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        else:
            img_resp = requests.get(image["url"], timeout=TIMEOUT_SECONDS)
            img_resp.raise_for_status()
            image_bytes = img_resp.content
            filename = f"{image.get('id') or 'photo'}.jpg"
            content_type = "image/jpeg"

        upload = requests.post(
            f"{base_url}/wp-json/wp/v2/media",
            auth=auth,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": content_type,
            },
            data=image_bytes,
            timeout=TIMEOUT_SECONDS,
        )
        if upload.status_code >= 400:
            print(f"[경고] 대표 이미지 업로드 실패: {upload.text[:200]}", file=sys.stderr)
            return None
        media_id = upload.json()["id"]

        # Unsplash 사진에는 출처를, 별도로 만든 편집용 이미지에는 성격을 미디어
        # 라이브러리 캡션으로 남깁니다.
        photographer = image.get("photographer", "")
        photographer_url = image.get("photographer_url", "")
        if photographer and photographer_url:
            caption = (
                f'Photo: <a href="{photographer_url}" target="_blank" rel="noopener">'
                f"{photographer}</a> / Unsplash"
            )
        else:
            caption = image.get("caption", "Illustrative image created for this article.")
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


def _featured_media_matches(
    base_url: str, auth: tuple[str, str], media_id: int, image: dict
) -> bool:
    """기존 대표 이미지가 같은 데이터로 만든 것인지 alt text로 확인합니다.

    대표 이미지의 alt에는 지수·환율 값이 들어갑니다. 같은 거래일을 재실행해도
    값이 같으면 기존 미디어를 재사용하고, 장중값 정정처럼 숫자가 달라졌을 때만
    새 파일을 올려 미디어 라이브러리 중복을 최소화합니다.
    """
    try:
        response = requests.get(
            f"{base_url}/wp-json/wp/v2/media/{media_id}",
            auth=auth,
            params={"context": "edit"},
            timeout=TIMEOUT_SECONDS,
        )
        if response.status_code >= 400:
            return False
        return response.json().get("alt_text", "") == image.get("alt", "")
    except Exception:  # noqa: BLE001 - 비교 실패 시 새 이미지로 안전하게 교체
        return False


def set_focus_keyword(base_url: str, auth: tuple[str, str], post_id: int, keyword: str) -> bool:
    """Rank Math의 포커스 키워드를 설정합니다.

    워드프레스 기본 REST(`wp/v2/posts`)로는 이 값을 쓸 수 없어서, Rank Math가
    제공하는 `rankmath/v1/updateMeta` 엔드포인트를 씁니다. 키워드를 안 넣으면
    글 목록에 "키워드 미설정"으로 남고 Rank Math의 SEO 분석도 동작하지 않습니다.

    읽어서 확인하는 경로가 REST에 없으므로(쓰기 전용), 실패해도 발행 자체를
    막지 않고 경고만 남깁니다 — 키워드는 있으면 좋지만 없다고 글이 안 올라가면
    안 되기 때문입니다.
    """
    try:
        response = requests.post(
            f"{base_url}/wp-json/rankmath/v1/updateMeta",
            auth=auth,
            json={
                "objectID": post_id,
                "objectType": "post",
                "meta": {"rank_math_focus_keyword": keyword},
            },
            timeout=TIMEOUT_SECONDS,
        )
        if response.status_code >= 400:
            print(
                f"[경고] 포커스 키워드 설정 실패 (id={post_id}): {response.text[:200]}",
                file=sys.stderr,
            )
            return False
        return True
    except Exception as e:  # noqa: BLE001 - 키워드 실패로 발행을 막지 않음
        print(f"[경고] 포커스 키워드 설정 실패 (id={post_id}): {e!r}", file=sys.stderr)
        return False


def publish_draft(
    title: str,
    html_content: str,
    lang: str | None = None,
    excerpt: str | None = None,
    tags: list[str] | None = None,
    category: str | None = None,
    image: dict | None = None,
    featured_media_id: int | None = None,
    slug: str | None = None,
    focus_keyword: str | None = None,
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

    if slug:
        existing = _find_existing_post_by_slug(base_url, auth, slug)
        if existing:
            if existing.get("status") == "draft":
                print(
                    f"[안내] 같은 거래일의 기존 초안(id={existing.get('id')})을 갱신합니다."
                )
                existing_featured = existing.get("featured_media") or None
                replacement_image = None
                resolved_featured = featured_media_id or existing_featured
                if image and existing_featured:
                    if _featured_media_matches(base_url, auth, existing_featured, image):
                        resolved_featured = existing_featured
                    else:
                        replacement_image = image
                        resolved_featured = None
                return update_draft(
                    existing["id"],
                    title,
                    html_content,
                    lang=lang,
                    excerpt=excerpt,
                    tags=tags,
                    category=category,
                    image=replacement_image if existing_featured else image,
                    featured_media_id=resolved_featured,
                )
            print(
                f"[안내] 같은 거래일 글(id={existing.get('id')})이 이미 "
                f"{existing.get('status')} 상태라 새 초안을 만들지 않습니다."
            )
            return existing

    safe_content = _to_wordpress_content(html_content)

    payload = {"title": title, "content": safe_content, "status": "draft"}
    if slug:
        payload["slug"] = slug
    if excerpt:
        payload["excerpt"] = excerpt
    if tags:
        payload["tags"] = _get_or_create_tag_ids(base_url, auth, tags)
    if category:
        cat_id = _get_or_create_term_id(base_url, auth, "categories", category, lang=lang)
        if cat_id:
            payload["categories"] = [cat_id]
    if featured_media_id:
        payload["featured_media"] = featured_media_id
    elif image:
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

    if focus_keyword and result.get("id"):
        set_focus_keyword(base_url, auth, result["id"], focus_keyword)

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
    featured_media_id: int | None = None,
    focus_keyword: str | None = None,
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
    if featured_media_id:
        payload["featured_media"] = featured_media_id
    elif image:
        media_id = upload_featured_image(base_url, auth, image)
        if media_id:
            payload["featured_media"] = media_id

    endpoint = f"{base_url}/wp-json/wp/v2/posts/{post_id}"
    response = requests.post(endpoint, auth=auth, json=payload, timeout=TIMEOUT_SECONDS)

    if response.status_code >= 400:
        raise WordPressPublishError(
            f"워드프레스 업데이트 실패 (HTTP {response.status_code}): {response.text[:500]}"
        )

    if focus_keyword:
        set_focus_keyword(base_url, auth, post_id, focus_keyword)

    return response.json()
