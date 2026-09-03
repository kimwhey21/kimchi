"""인사이트 섹션 각 소재에 어울리는 사진을 찾습니다.

출처는 두 곳이고 순서가 있습니다.

1. **Unsplash** (검색어 기반). 무료 API이지만 키가 필요합니다:
   https://unsplash.com/developers 에서 Access Key를 받습니다. 정책상 사진작가와
   Unsplash를 함께 표기해야 해서 photographer/photographer_url을 함께 돌려줍니다.
2. **위키미디어 공용** (종목 기반). Unsplash에 결과가 없을 때만 봅니다.
   한국 기업이 특히 그렇습니다 — "KB Financial Group"은 Unsplash 검색 결과가
   0건입니다.

두 번째 경로는 검색어가 아니라 **종목 자체**로 찾습니다. 위키데이터에서 그
회사 항목을 찾고 P18(대표 사진)에 걸린 파일만 씁니다. 검색어로 찾으면 저장소가
여러 번 겪은 그 실패가 그대로 재현되기 때문입니다. 실제로 확인한 것들:

- 한국어 위키백과 '신한지주' 문서의 대표 이미지는 숭례문 사진이었습니다.
- 위키데이터에서 '카카오'를 이름으로 검색하면 카카오 열매 항목이 먼저 나오고,
  그 항목의 사진은 페루 아마존에서 찍은 것이었습니다.

그래서 이름으로 찾은 항목이라도 **P31(무엇인가)이 회사일 때만** 통과시킵니다.
카카오 열매 항목은 여기서 걸러집니다. 이어서 파일 이름이 로고·워드마크로
보이면 제외하고(삼성중공업의 P18은 검은 배경 워드마크였습니다), 형식과 가로세로
비율, 라이선스까지 확인합니다.

2026-09-03 기준 한국 코어 21종목 중 이 경로로 사진이 나오는 것은 5종목입니다
(삼성전자·SK하이닉스·신한지주·HD현대중공업·네이버). 나머지는 위키데이터에
사진이 없어 사진 없이 나갑니다 — 틀린 사진보다 낫습니다.
"""
from __future__ import annotations

import os
import re
import sys

import requests

UNSPLASH_SEARCH_URL = "https://api.unsplash.com/search/photos"
CANDIDATES_PER_QUERY = 5

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
# 위키미디어는 요청 주체를 밝히는 User-Agent를 요구합니다.
_WIKI_HEADERS = {"User-Agent": "market-brief/1.0 (https://fermata.it.kr)"}
_WIKI_TIMEOUT = 20

# P31(instance of)이 이 중 하나여야 회사로 봅니다. 카카오 열매(분류군)처럼
# 이름만 같은 항목을 걸러내는 장치입니다.
_COMPANY_TYPES = {
    "Q4830453",   # business
    "Q891723",    # public company
    "Q6881511",   # enterprise
    "Q783794",    # company
    "Q18388277",  # technology company
    "Q219577",    # holding company
    "Q22687",     # bank
    "Q43229",     # organization
}
# 파일 이름이 이렇게 생겼으면 사진이 아니라 로고·워드마크입니다.
_LOGO_FILENAME = re.compile(r"(logo|wordmark|symbol|icon|emblem|signature)", re.IGNORECASE)
_PHOTO_MIME = ("image/jpeg", "image/png")
# 상업적 사용이 가능한 라이선스만 씁니다. NC(비영리)와 ND(변경 금지)는 제외합니다
# — 이 블로그는 광고가 붙는 상업적 사이트이고, 표시할 때 크기를 줄이기 때문입니다.
# 허용 패턴만 두면 "CC BY-NC 2.0"이 "cc by"에 걸려 통과합니다(테스트로 확인).
_ALLOWED_LICENSE = re.compile(r"(public domain|^cc0|^cc[ -]by|^fal$|free art)", re.IGNORECASE)
_DENIED_LICENSE = re.compile(r"(\bnc\b|noncommercial|non-commercial|\bnd\b|noderiv)", re.IGNORECASE)
_MIN_RATIO, _MAX_RATIO = 0.5, 2.6


def _wiki_get(url: str, **params) -> dict:
    params.setdefault("format", "json")
    response = requests.get(url, params=params, headers=_WIKI_HEADERS, timeout=_WIKI_TIMEOUT)
    response.raise_for_status()
    return response.json()


def _company_entity(name: str) -> dict | None:
    """이름으로 찾은 위키데이터 항목 중 **회사인 것**의 claims를 돌려줍니다."""
    for language in ("ko", "en"):
        found = _wiki_get(
            WIKIDATA_API,
            action="wbsearchentities",
            language=language,
            uselang=language,
            search=name,
            type="item",
            limit=5,
        )
        for hit in found.get("search") or []:
            entity = _wiki_get(
                WIKIDATA_API,
                action="wbgetentities",
                ids=hit["id"],
                props="claims",
            )
            claims = (entity.get("entities", {}).get(hit["id"], {}) or {}).get("claims", {})
            kinds = {
                (claim["mainsnak"].get("datavalue", {}) or {}).get("value", {}).get("id")
                for claim in claims.get("P31", [])
            }
            if kinds & _COMPANY_TYPES:
                return claims
    return None


def _commons_photo(filename: str) -> dict | None:
    """공용 파일이 사진으로 쓸 만한지 확인하고 URL·출처 표기를 만듭니다."""
    data = _wiki_get(
        COMMONS_API,
        action="query",
        titles=f"File:{filename}",
        prop="imageinfo",
        iiprop="url|mime|extmetadata",
        iiurlwidth=1200,
    )
    for page in (data.get("query", {}).get("pages", {}) or {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        if info.get("mime") not in _PHOTO_MIME:
            return None
        width, height = info.get("thumbwidth") or 0, info.get("thumbheight") or 0
        if not height or not (_MIN_RATIO <= width / height <= _MAX_RATIO):
            return None
        meta = info.get("extmetadata", {}) or {}
        license_name = (meta.get("LicenseShortName") or {}).get("value", "")
        if not _ALLOWED_LICENSE.search(license_name) or _DENIED_LICENSE.search(license_name):
            return None
        artist = re.sub(r"<[^>]+>", "", (meta.get("Artist") or {}).get("value", "")).strip()
        credit = f"사진: {artist or '위키미디어 공용 기여자'} / 위키미디어 공용 ({license_name})"
        return {
            "id": f"wikimedia:{filename}",
            "url": info.get("thumburl"),
            "alt": filename.rsplit(".", 1)[0].replace("_", " "),
            "credit": credit,
            "credit_url": info.get("descriptionurl"),
        }
    return None


def _wikimedia_entity_photo(entity: str, exclude_ids: set[str]) -> dict | None:
    """종목 이름으로 위키데이터 회사 항목의 대표 사진(P18)을 찾습니다."""
    try:
        claims = _company_entity(entity)
        if not claims:
            print(f"[안내] 위키데이터에서 '{entity}' 회사 항목을 찾지 못했습니다.", file=sys.stderr)
            return None
        if "P18" not in claims:
            print(f"[안내] 위키데이터 '{entity}' 항목에 대표 사진이 없습니다.", file=sys.stderr)
            return None
        filename = claims["P18"][0]["mainsnak"]["datavalue"]["value"]
        if _LOGO_FILENAME.search(filename):
            print(
                f"[안내] '{entity}'의 위키데이터 사진이 로고 파일이라 쓰지 않습니다 ({filename}).",
                file=sys.stderr,
            )
            return None
        photo = _commons_photo(filename)
        if not photo or photo["id"] in exclude_ids:
            return None
        return photo
    except Exception as exc:  # noqa: BLE001 - 사진이 없어도 글은 나가야 합니다
        print(f"[경고] 위키미디어 조회 실패 ('{entity}'): {exc!r}", file=sys.stderr)
        return None


def search_image(
    query: str, exclude_ids: set[str] = frozenset(), entity: str | None = None
) -> dict | None:
    """검색어에 맞는 사진을 찾아 dict로 돌려줍니다. 실패하면 None을 돌려줍니다.

    exclude_ids에 있는 사진은 건너뛰고, 후보 중 첫 번째로 남는 것을 씁니다
    (같은 날 여러 소재에 같은 사진이 중복으로 붙는 것을 방지).

    entity를 주면 Unsplash에서 못 찾았을 때 그 이름의 회사 사진을 위키미디어
    공용에서 한 번 더 찾습니다. 종목명을 그대로 넘기세요.

    반환 형식: {"id", "url", "alt", 그리고 출처 표기용으로 Unsplash는
    photographer/photographer_url, 위키미디어는 credit/credit_url}
    """
    unsplash = _search_unsplash(query, exclude_ids)
    if unsplash:
        return unsplash
    if entity:
        return _wikimedia_entity_photo(entity, exclude_ids)
    return None


def _search_unsplash(query: str, exclude_ids: set[str]) -> dict | None:
    access_key = os.environ.get("UNSPLASH_ACCESS_KEY")
    if not access_key:
        return None  # 키가 없으면 조용히 건너뜀 — 사진 없이도 글은 완성되어야 함

    try:
        response = requests.get(
            UNSPLASH_SEARCH_URL,
            params={"query": query, "per_page": CANDIDATES_PER_QUERY, "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {access_key}"},
            timeout=10,
        )
        response.raise_for_status()
        results = response.json().get("results", [])
        if not results:
            print(f"[경고] Unsplash: '{query}' 검색 결과가 없습니다.", file=sys.stderr)
            return None

        photo = next((p for p in results if p["id"] not in exclude_ids), results[0])
        return {
            "id": photo["id"],
            "url": photo["urls"]["regular"],
            "alt": photo.get("alt_description") or query,
            "photographer": photo["user"]["name"],
            "photographer_url": photo["user"]["links"]["html"],
        }
    except Exception as e:
        # 이미지 검색 실패는 전체 파이프라인을 막으면 안 되지만, 원인은 남겨야
        # "관련 사진이 없나 보다"와 "키/한도 문제로 실패했다"를 구분할 수 있습니다.
        print(f"[경고] Unsplash 검색 실패 ('{query}'): {e!r}", file=sys.stderr)
        return None


def attach_images(stories: list[dict]) -> list[dict]:
    """insight_section.stories 각각에 image_query로 찾은 사진을 붙여줍니다.

    같은 실행 안에서 이미 쓴 사진은 다른 소재에 중복으로 붙지 않게 피합니다.
    """
    used_ids: set[str] = set()
    for story in stories:
        query = story.get("image_query")
        image = search_image(query, exclude_ids=used_ids) if query else None
        if image:
            used_ids.add(image["id"])
        story["image"] = image
    return stories
