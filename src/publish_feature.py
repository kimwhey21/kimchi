"""기준표(feature) 원고 한 파일의 유일한 발행 진입점.

외부 호출은 이 모듈을 실제 실행할 때만 일어난다. 테스트는 publish_wordpress를
mock하여 렌더·해시·상태 보존 계약만 검증한다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv

from src import data_graphics, feature_graphics, graphic_checks, publish_wordpress

# 단독 실행 모듈이라 main.py가 대신 불러 주지 않습니다. 이게 빠져 있으면
# `is_configured()`가 False가 되어 **조용히 "업로드 안 함"으로 끝납니다** —
# 발행한 줄 알았는데 사이트에 아무것도 없는 상태가 됩니다.
load_dotenv()
from src.feature_gate import run as run_gate
from src.render_feature import render

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output" / "features"


def _slug(doc: dict, path: Path) -> str:
    value = doc.get("slug") or path.stem
    return re.sub(r"[^a-z0-9-]+", "-", str(value).lower()).strip("-")


def _build_graphics(doc: dict, output: Path) -> tuple[list[dict], dict[int, dict], dict | None]:
    """JSON의 graphics 선언을 실제 PNG와 절 번호별 figure로 바꾼다."""
    generated, figures, cover = [], {}, None
    for index, spec in enumerate(doc.get("graphics") or []):
        kind, args = spec["kind"], dict(spec.get("args") or {})
        title = str(args.get("title") or spec.get("alt") or "")
        issues = graphic_checks.collect_spec_issues(kind, args, title)
        if issues:
            raise ValueError("그래픽 데이터 검사 실패:\n- " + "\n- ".join(issues))
        builder = getattr(feature_graphics, kind, None) or data_graphics.BUILDERS.get(kind)
        if builder is None:
            raise ValueError(f"알 수 없는 그래픽 종류: {kind}")
        path = output / f"{index + 1:02d}-{kind}.png"
        builder(output_path=path, **args)
        image_issues = graphic_checks.verify_image(path)
        if image_issues:
            raise ValueError("그래픽 렌더 검사 실패:\n- " + "\n- ".join(image_issues))
        image = {"local_path": str(path), "alt": spec.get("alt", title),
                 "caption": spec.get("caption", "Fermata data graphic.")}
        generated.append(image)
        if "section" not in spec and not spec.get("featured"):
            raise ValueError(f"그래픽 {index + 1}은 section 또는 featured에 배치해야 합니다.")
        if spec.get("featured"):
            if cover is not None:
                raise ValueError("대표 그래픽은 하나만 지정할 수 있습니다.")
            cover = image
        if "section" in spec:
            section = int(spec["section"])
            if section in figures:
                raise ValueError(f"절 {section}에 그래픽을 두 장 배치할 수 없습니다.")
            figures[section] = {"image": image, "alt": image["alt"]}
    return generated, figures, cover


def publish(path: Path, *, upload: bool = True) -> dict:
    """검사 → PNG 생성 → 해시 기반 미디어 재사용 → 상태 보존 갱신 → 되읽기."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("kind") != "feature":
        raise ValueError("feature 원고(kind: feature)만 받을 수 있습니다.")
    output = OUTPUT / _slug(doc, path)
    output.mkdir(parents=True, exist_ok=True)
    images, section_images, featured = _build_graphics(doc, output)
    run_gate(doc, graphics=len(images), path=path)  # 다섯 검사의 단일 관문

    figures = {}
    if upload and publish_wordpress.is_configured():
        for section, value in section_images.items():
            media_id = publish_wordpress.upload_featured_image(
                os.environ["WORDPRESS_URL"].rstrip("/"),
                (os.environ["WORDPRESS_USERNAME"], os.environ["WORDPRESS_APP_PASSWORD"]),
                value["image"],
            )
            if not media_id:
                raise publish_wordpress.WordPressPublishError("본문 그래픽 업로드 실패")
            # upload_featured_image가 돌려준 id를 다시 추측하지 않고 조회한다.
            response = publish_wordpress.requests.get(
                os.environ["WORDPRESS_URL"].rstrip("/") + f"/wp-json/wp/v2/media/{media_id}",
                auth=(os.environ["WORDPRESS_USERNAME"], os.environ["WORDPRESS_APP_PASSWORD"]),
                timeout=publish_wordpress.TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            figures[section] = {"url": response.json()["source_url"], "alt": value["alt"]}
    else:
        figures = {k: {"url": v["image"]["local_path"], "alt": v["alt"]}
                   for k, v in section_images.items()}

    ko = doc.get("ko") or doc
    html = render(doc, doc.get("series", "기준표"), figures=figures,
                  meta_description=ko.get("excerpt"))
    html_path = output / "article.html"
    html_path.write_text(html, encoding="utf-8")
    if not upload:
        return {"html": str(html_path), "uploaded": False}
    if not publish_wordpress.is_configured():
        # 설정이 없으면 조용히 넘어가지 않고 말합니다. 발행한 줄 알고 넘어가는
        # 것이 발행 실패보다 나쁩니다.
        raise publish_wordpress.WordPressPublishError(
            "워드프레스 설정이 없어 올리지 못했습니다. .env의 WORDPRESS_URL·"
            "WORDPRESS_USERNAME·WORDPRESS_APP_PASSWORD를 확인하십시오. "
            f"렌더된 HTML은 {html_path}에 있습니다.")

    base = os.environ["WORDPRESS_URL"].rstrip("/")
    auth = (os.environ["WORDPRESS_USERNAME"], os.environ["WORDPRESS_APP_PASSWORD"])
    slug = _slug(doc, path)
    existing = publish_wordpress._find_existing_post_by_slug(base, auth, slug)
    featured_id = None
    # 사진 표지. 데이터 그래픽 표지가 "그날 시황"처럼 읽힌다는 지적이 있어
    # 가이드는 사진을 쓸 수 있게 열어 둡니다. 다만 **쓰기 전에 사람이 받아서 눈으로
    # 확인한 파일만** 원고에 적습니다 — 검색어로 자동으로 붙이지 않습니다.
    # 2026-09-07에 `korean bank`가 삼청빌라, `bank building seoul`이 용산 전경으로
    # 나왔습니다. 특정 은행 간판이 찍힌 사진도 쓰지 않습니다(다른 회사로 읽힙니다).
    photo = doc.get("featured_photo")
    if photo and featured:
        raise ValueError("표지는 사진이나 그래픽 중 하나만 지정하십시오.")
    if photo:
        local = ROOT / photo["local_path"] if not Path(photo["local_path"]).is_absolute() \
            else Path(photo["local_path"])
        if not local.exists():
            raise ValueError(f"표지 사진이 없습니다: {local}")
        credit = photo.get("credit", "")
        featured_id = publish_wordpress.upload_featured_image(base, auth, {
            "local_path": str(local), "alt": photo.get("alt", ""),
            "caption": credit, "id": local.stem,
        })
        if not featured_id:
            raise publish_wordpress.WordPressPublishError("표지 사진 업로드 실패")
    if featured:
        featured_id = publish_wordpress.upload_featured_image(base, auth, featured)
        if not featured_id:
            raise publish_wordpress.WordPressPublishError("대표 그래픽 업로드 실패")
    category_id = doc.get("category_id")
    if not isinstance(category_id, int):
        raise ValueError("category_id(언어별 WordPress 숫자 id)가 필요합니다. 이름 생성은 금지합니다.")
    common = dict(lang=doc.get("lang", "ko"), excerpt=ko.get("excerpt"),
                  tags=doc.get("tags") or [], category=category_id,
                  featured_media_id=featured_id, focus_keyword=doc.get("focus_keyword"))
    if existing:
        # status=None은 공개·비공개 어느 상태도 바꾸지 않는다.
        result = publish_wordpress.update_draft(existing["id"], ko["title"], html, status=None, **common)
    else:
        # 새 글만 원칙대로 임시저장한다.
        result = publish_wordpress.publish_draft(ko["title"], html, slug=slug, status="draft", **common)
    expected = existing.get("status", "draft") if existing else "draft"
    publish_wordpress.verify_published(
        result["id"], ko["title"], expected_status=expected,
        expected_featured_media=featured_id, expected_category_id=category_id,
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--render-only", action="store_true")
    args = parser.parse_args(argv)
    result = publish(args.path, upload=not args.render_only)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
