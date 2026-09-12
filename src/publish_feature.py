"""기준표(feature) 원고 한 파일의 유일한 발행 진입점.

외부 호출은 이 모듈을 실제 실행할 때만 일어난다. 테스트는 publish_wordpress를
mock하여 렌더·해시·상태 보존 계약만 검증한다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv

from src import data_graphics, feature_graphics, graphic_checks, notify_telegram, post_tags, publish_wordpress

# 단독 실행 모듈이라 main.py가 대신 불러 주지 않습니다. 이게 빠져 있으면
# `is_configured()`가 False가 되어 **조용히 "업로드 안 함"으로 끝납니다** —
# 발행한 줄 알았는데 사이트에 아무것도 없는 상태가 됩니다.
load_dotenv()
from src.feature_gate import run as run_gate
from src.render_feature import render

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output" / "features"


# 독자에게 보이는 시리즈 이름 (2026-09-09, 사용자 결정: "이름은 체크포인트로, 영어로 표기").
# 내부 키(`series: 기준표`, 문서·검사·성적표 코드)는 그대로 두고, 화면에 나가는 곳 — 워드프레스
# 분류(Checkpoint, id 432)·홈 탭·글 머리말·표지 kicker — 만 이 표를 거친다. 제목 글자에는
# 라벨을 넣지 않는다(제목은 검색에서 서른 자 안팎만 보인다). 대신 확인 날짜를 제목에 넣는다.
SERIES_LABEL = {"기준표": "Checkpoint", "Guide": "Investor Guide"}

# 유입 편성(2026-09-12, 사용자 승인): 상시 가이드(한국어 "가이드"·영어 "Guide")와 정기 이벤트 글("이벤트").
# 가이드 머리말은 확인 날짜(최상위 `checked`, YYYY-MM-DD)를 보인다 — 상시 글은 "언제 기준인지"가 검색 결과의
# 신뢰다. 이벤트 글은 행사 날짜(최상위 `event_date`)를 보인다.
_MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August",
              "September", "October", "November", "December"]


def _date_or_none(value) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _period_text(doc: dict) -> str:
    """주말 시리즈의 대상 기간(원고 최상위 `period`: {"start", "end"}) — `9월 7일~11일`."""
    period = doc.get("period") or {}
    try:
        start = dt.date.fromisoformat(str(period.get("start")))
        end = dt.date.fromisoformat(str(period.get("end")))
    except (TypeError, ValueError):
        return ""
    if start.month == end.month:
        return f"{start.month}월 {start.day}일~{end.day}일"
    return f"{start.month}월 {start.day}일~{end.month}월 {end.day}일"


def _kicker(doc: dict) -> str:
    """글 맨 위 머리말. 기준표는 `Checkpoint · 9월 30일까지 확인할 것`(원고 최상위 `deadline`),
    주말 시리즈는 `주간 결산 · 9월 7일~11일` / `다음 주 일정 · 9월 14일~18일`(최상위 `period`)."""
    series = str(doc.get("series") or "기준표")
    label = SERIES_LABEL.get(series, series)
    if series == "기준표" and doc.get("deadline"):
        day = dt.date.fromisoformat(str(doc["deadline"]))
        return f"{label} · {day.month}월 {day.day}일까지 확인할 것"
    if series in ("주간 결산", "다음 주 일정") and _period_text(doc):
        return f"{label} · {_period_text(doc)}"
    if series == "가이드" and _date_or_none(doc.get("checked")):
        day = _date_or_none(doc.get("checked"))
        return f"가이드 · {day.year}년 {day.month}월 {day.day}일 확인"
    if series == "Guide" and _date_or_none(doc.get("checked")):
        day = _date_or_none(doc.get("checked"))
        return f"{label} · Checked {_MONTHS_EN[day.month - 1]} {day.day}, {day.year}"
    if series == "이벤트" and _date_or_none(doc.get("event_date")):
        day = _date_or_none(doc.get("event_date"))
        return f"이벤트 · {day.month}월 {day.day}일"
    return label


def _slug(doc: dict, path: Path) -> str:
    value = doc.get("slug") or path.stem
    return re.sub(r"[^a-z0-9-]+", "-", str(value).lower()).strip("-")


def _seo_lead(doc: dict) -> str:
    """프리뷰 설명문 첫 문장(2026-09-08). 기준표는 상시 글이라 날짜를 앞세우지 않는다.
    주말 시리즈(2026-09-12)는 기간을 앞세운다 — 검색 결과에서 어느 주의 글인지 보이게."""
    series = doc.get("series")
    if series in ("주간 결산", "다음 주 일정") and _period_text(doc):
        noun = "주간 증시 결산" if series == "주간 결산" else "다음 주 증시 일정"
        return f"{_period_text(doc)} {noun}입니다. "
    if series == "이벤트" and _date_or_none(doc.get("event_date")):
        day = _date_or_none(doc.get("event_date"))
        return f"{day.month}월 {day.day}일 {doc.get('event_name') or '증시 이벤트'} 정리입니다. "
    if series != "프리뷰" or not doc.get("date"):
        return ""
    year, month, day = (int(x) for x in str(doc["date"]).split("-"))
    return f"{month}월 {day}일 밤 미국장 프리뷰입니다. "


def _excerpt(ko: dict, limit: int = 200, lead: str = "") -> str:
    """홈 카드·검색 결과·SNS 미리보기에 보이는 요약.

    원고에 `excerpt`가 없으면 워드프레스가 본문 앞부분을 잘라 쓰는데, 우리 본문은
    표식(기준표/프리뷰)·제목·첫 소제목이 먼저 나와 홈 카드에 "프리뷰 오늘 밤 미국장,
    … 1. 오늘 밤 일정 —"처럼 찍혔다(2026-09-08). 첫 절의 첫 문단을 쓴다.
    """
    if ko.get("excerpt"):
        return lead + str(ko["excerpt"])
    first = ((ko.get("narrative") or [{}])[0].get("body", "")).split("\n\n")[0]
    text = re.sub(r"<[^>]+>", "", first).strip()
    room = max(60, limit - len(lead))
    if len(text) <= room:
        return lead + text
    return lead + text[:room].rsplit(" ", 1)[0].strip() + "…"


def _build_graphics(doc: dict, output: Path) -> tuple[list[dict], dict[int, dict], dict | None]:
    """JSON의 graphics 선언을 실제 PNG와 절 번호별 figure로 바꾼다."""
    generated, figures, cover = [], {}, None
    for index, spec in enumerate(doc.get("graphics") or []):
        kind, args = spec["kind"], dict(spec.get("args") or {})
        title = str(args.get("title") or spec.get("alt") or "")
        issues = graphic_checks.collect_spec_issues(kind, args, title)
        if issues:
            raise ValueError("그래픽 데이터 검사 실패:\n- " + "\n- ".join(issues))
        feature_builder = getattr(feature_graphics, kind, None)
        path = output / f"{index + 1:02d}-{kind}.png"
        if feature_builder is not None:
            feature_builder(output_path=path, **args)
        elif kind in data_graphics.BUILDERS:
            # 시황용 데이터 그래픽(price_history·number_cards·movers_list 등)을 기준표·
            # 프리뷰에서도 씁니다(2026-09-08). 원고에는 시세가 없으므로 `price_file`로
            # 시세 파일을 가리킵니다 — "price_file": "data/price_us_2026-09-04.json".
            price_file = spec.get("price_file")
            if kind in data_graphics.PRICELESS_KINDS and not price_file:
                price_data = {}   # 표·수급 그림은 조사 값으로만 그린다(출처 필수)
            else:
                if not price_file:
                    raise ValueError(f"그래픽 {index + 1}({kind}): 시세 파일이 필요합니다 — "
                                     "\"price_file\": \"data/price_<market>_<날짜>.json\"을 적으십시오.")
                price_path = ROOT / price_file
                if not price_path.exists():
                    raise ValueError(f"그래픽 {index + 1}({kind}): 시세 파일이 없습니다: {price_file}")
                price_data = json.loads(price_path.read_text(encoding="utf-8"))
            data_graphics.build(kind, price_data, path, **args)
        else:
            raise ValueError(f"알 수 없는 그래픽 종류: {kind}")
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


def publish(path: Path, *, upload: bool = True, live: bool = False) -> dict:
    """검사 → PNG 생성 → 해시 기반 미디어 재사용 → 상태 보존 갱신 → 되읽기.

    live=False(기본)면 새 글은 임시저장, 기존 글은 상태를 건드리지 않는다.
    live=True는 사용자가 "발행"이라고 한 뒤에만 쓴다 — 공개 상태로 올린다.
    """
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
    html = render(doc, _kicker(doc), figures=figures,
                  meta_description=_excerpt(ko, lead=_seo_lead(doc)),
                  lang=str(doc.get("lang") or "ko"))
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
        credit = photo.get("credit", "")
        if photo.get("local_path"):
            local = ROOT / photo["local_path"] if not Path(photo["local_path"]).is_absolute() \
                else Path(photo["local_path"])
            if not local.exists():
                raise ValueError(f"표지 사진이 없습니다: {local}")
            image = {"local_path": str(local), "alt": photo.get("alt", ""),
                     "caption": credit, "id": local.stem}
        elif photo.get("url"):
            # 루틴이 샌드박스에서 대조표를 `Read`로 보고 고른 사진. 파일은 저장소에
            # 없고(output/은 커밋하지 않는다) 발행 러너가 이 URL로 받는다. 여기서
            # 검색하지 않는다 — URL은 이미 사람(루틴)이 본 것이다(2026-09-08).
            image = {"url": photo["url"], "alt": photo.get("alt", ""),
                     "caption": credit, "id": f"{slug}-cover"}
        else:
            raise ValueError("featured_photo에는 local_path(로컬 파일)나 url(직접 보고 고른 사진) "
                             "중 하나가 있어야 합니다.")
        featured_id = publish_wordpress.upload_featured_image(base, auth, image)
        if not featured_id:
            raise publish_wordpress.WordPressPublishError("표지 사진 업로드 실패")
    if featured:
        featured_id = publish_wordpress.upload_featured_image(base, auth, featured)
        if not featured_id:
            raise publish_wordpress.WordPressPublishError("대표 그래픽 업로드 실패")
    category_id = doc.get("category_id")
    if not isinstance(category_id, int):
        raise ValueError("category_id(언어별 WordPress 숫자 id)가 필요합니다. 이름 생성은 금지합니다.")
    common = dict(lang=doc.get("lang", "ko"), excerpt=_excerpt(ko, lead=_seo_lead(doc)),
                  tags=post_tags.build_tags(doc), category=category_id,   # 원고의 tags + 글에서 뽑은 태그(2026-09-12)
                  featured_media_id=featured_id, focus_keyword=doc.get("focus_keyword"))
    if existing:
        # status=None은 공개·비공개 어느 상태도 바꾸지 않는다. live일 때만 공개로 올린다.
        result = publish_wordpress.update_draft(existing["id"], ko["title"], html,
                                                status="publish" if live else None, **common)
    else:
        # 새 글은 원칙대로 임시저장한다. --publish는 사용자가 "발행"이라고 한 뒤에만 쓴다.
        result = publish_wordpress.publish_draft(ko["title"], html, slug=slug,
                                                 status="publish" if live else "draft", **common)
    expected = "publish" if live else (existing.get("status", "draft") if existing else "draft")
    publish_wordpress.verify_published(
        result["id"], ko["title"], expected_status=expected,
        expected_featured_media=featured_id, expected_category_id=category_id,
    )
    if live:
        # 텔레그램 채널 알림(2026-09-12, 홍보 1번). 다시 올린 글은 notify_post가 스스로 거른다. 실패해도 발행은 성공이다.
        notify_telegram.notify_post(base, result["id"], ko["title"], doc)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--render-only", action="store_true")
    parser.add_argument("--publish", action="store_true",
                        help="공개 상태로 발행. 사용자가 '발행'이라고 한 뒤에만 쓴다(기본은 임시저장).")
    args = parser.parse_args(argv)
    result = publish(args.path, upload=not args.render_only, live=args.publish)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
