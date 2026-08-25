"""인사이트 섹션 각 소재에 어울리는 사진을 Unsplash에서 검색합니다.

무료 API이지만 키 발급이 필요합니다: https://unsplash.com/developers 에서
애플리케이션을 만들면 Access Key를 받을 수 있습니다.

Unsplash API 정책상 사진을 쓸 때는 사진작가와 Unsplash를 함께 표기해야 합니다.
이 모듈이 반환하는 dict에 photographer/photographer_url을 포함하는 것도 그 때문입니다.
"""
from __future__ import annotations

import os
import sys

import requests

UNSPLASH_SEARCH_URL = "https://api.unsplash.com/search/photos"
CANDIDATES_PER_QUERY = 5


def search_image(query: str, exclude_ids: set[str] = frozenset()) -> dict | None:
    """검색어에 맞는 사진을 찾아 dict로 돌려줍니다. 실패하면 None을 돌려줍니다.

    exclude_ids에 있는 사진은 건너뛰고, 후보 중 첫 번째로 남는 것을 씁니다
    (같은 날 여러 소재에 같은 사진이 중복으로 붙는 것을 방지).

    반환 형식: {"id": ..., "url": ..., "alt": ..., "photographer": ..., "photographer_url": ...}
    """
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
