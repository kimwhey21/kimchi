"""인사이트 섹션 각 소재에 어울리는 사진을 Unsplash에서 검색합니다.

무료 API이지만 키 발급이 필요합니다: https://unsplash.com/developers 에서
애플리케이션을 만들면 Access Key를 받을 수 있습니다.

Unsplash API 정책상 사진을 쓸 때는 사진작가와 Unsplash를 함께 표기해야 합니다.
이 모듈이 반환하는 dict에 photographer/photographer_url을 포함하는 것도 그 때문입니다.
"""
from __future__ import annotations

import os

import requests

UNSPLASH_SEARCH_URL = "https://api.unsplash.com/search/photos"


def search_image(query: str) -> dict | None:
    """검색어에 맞는 사진 1장을 찾아 dict로 돌려줍니다. 실패하면 None을 돌려줍니다.

    반환 형식: {"url": ..., "alt": ..., "photographer": ..., "photographer_url": ...}
    """
    access_key = os.environ.get("UNSPLASH_ACCESS_KEY")
    if not access_key:
        return None  # 키가 없으면 조용히 건너뜀 — 사진 없이도 글은 완성되어야 함

    try:
        response = requests.get(
            UNSPLASH_SEARCH_URL,
            params={"query": query, "per_page": 1, "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {access_key}"},
            timeout=10,
        )
        response.raise_for_status()
        results = response.json().get("results", [])
        if not results:
            return None

        photo = results[0]
        return {
            "url": photo["urls"]["regular"],
            "alt": photo.get("alt_description") or query,
            "photographer": photo["user"]["name"],
            "photographer_url": photo["user"]["links"]["html"],
        }
    except Exception:
        return None  # 이미지 검색 실패는 전체 파이프라인을 막으면 안 됨


def attach_images(stories: list[dict]) -> list[dict]:
    """insight_section.stories 각각에 image_query로 찾은 사진을 붙여줍니다."""
    for story in stories:
        query = story.get("image_query")
        story["image"] = search_image(query) if query else None
    return stories
