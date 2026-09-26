"""기준표(feature) 원고 한 파일의 유일한 발행 진입점.

외부 호출은 이 모듈을 실제 실행할 때만 일어난다. 테스트는 publish_wordpress를
mock하여 렌더·해시·상태 보존 계약만 검증한다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html as html_lib
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv

from src import (contact_sheet, data_graphics, feature_graphics, graphic_checks, notify_telegram, notify_threads,
                 post_tags, publish_wordpress)

# 단독 실행 모듈이라 main.py가 대신 불러 주지 않습니다. 이게 빠져 있으면
# `is_configured()`가 False가 되어 **조용히 "업로드 안 함"으로 끝납니다** —
# 발행한 줄 알았는데 사이트에 아무것도 없는 상태가 됩니다.
load_dotenv()
from src.feature_gate import run as run_gate
from src.render_feature import render

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "output" / "features"


# 독자에게 보이는 시리즈 이름 (2026-09-09, 사용자 결정: "이름은 체크포인트로, 영어로 표기").
# 내부 키(`series: 기준표`, 문서·검사 코드)는 그대로 두고, 화면에 나가는 곳 — 워드프레스
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
    """글 주소. 영문 소문자·숫자·하이픈만 — 한글이 섞였거나 비면 멈춘다(2026-09-26).

    전에는 영문 밖의 글자를 지우고 넘어가서 `"삼성전자-목표주가"`는 빈 주소가, `"samsung-목표가"`는 `samsung`이 됐다.
    빈 주소로 기존 글을 찾으면 워드프레스가 조건을 무시하고 최근 글을 돌려줘 **그 글을 덮어쓸** 수 있었다.
    """
    value = str(doc.get("slug") or path.stem)
    if re.search(r"[^A-Za-z0-9_\-]", value):
        raise ValueError(f"slug {value!r}에 영문 소문자·숫자·하이픈 밖의 글자가 있습니다 — 영문으로 적으십시오.")
    slug = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
    if not slug:
        raise ValueError(f"slug가 비었습니다({value!r}).")
    return slug


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


def _refresh_related(related: list | None) -> list[dict]:
    """`related`의 링크 제목을 **살아 있는 제목**으로 바꾼다(2026-09-18, 사장님 "2번 진행" — 내부 링크로 올리기).

    그전에는 루틴마다 제목을 손으로 적어 넣어, 같은 글을 페이지마다 다른 이름으로 가리켰다(실측: 거래시간 글을
    세 페이지가 "Korea Stock Market Hours 2026: Sessions…", "How to Buy Korean Stocks From the US in 2026: Brokers…",
    "Can Foreigners Buy Korean Stocks? What Changed in 2026"으로 링크). 내부 링크의 글자(앵커)는 검색엔진이 그 글의
    주제를 읽는 자리라, 제목을 고쳐도 앵커가 옛 제목이면 반쪽이다. 우리 사이트 주소(slug)로 글을 찾아 제목을 갈아
    끼우고, 못 찾으면(오프라인·삭제된 글) 원고의 제목을 그대로 둔다. 실패는 세어서 로그에 남긴다.
    """
    rows = [dict(r) for r in (related or []) if isinstance(r, dict) and r.get("url")]
    if not rows or not publish_wordpress.is_configured():
        return rows
    base = os.environ["WORDPRESS_URL"].rstrip("/")
    auth = (os.environ["WORDPRESS_USERNAME"], os.environ["WORDPRESS_APP_PASSWORD"])
    host = re.sub(r"^https?://", "", base).split("/")[0]
    changed = missed = 0
    for row in rows:
        url = str(row["url"])
        if host not in url:
            continue   # 바깥 링크는 손대지 않는다
        slug = url.rstrip("/").rsplit("/", 1)[-1]
        try:
            post = publish_wordpress._find_existing_post_by_slug(base, auth, slug)
        except Exception as error:  # noqa: BLE001 - 링크 하나 때문에 발행을 막지 않는다
            print(f"[안내] 관련 글 조회 실패({slug}): {error!r} — 원고 제목을 둡니다")
            missed += 1
            continue
        title = html_lib.unescape(((post or {}).get("title") or {}).get("rendered") or "").strip()
        if not title or (post or {}).get("status") != "publish":
            missed += 1
            continue
        if title != row.get("title"):
            row["title"] = title
            changed += 1
    print(f"[안내] 관련 글 제목: 살아 있는 제목으로 {changed}개 갱신, 못 찾은 것 {missed}개 (전체 {len(rows)})")
    return rows


def _build_graphics(doc: dict, output: Path) -> tuple[list[dict], dict[int, dict], dict | None]:
    """JSON의 graphics 선언을 실제 PNG와 절 번호별 figure로 바꾼다."""
    generated, figures, cover = [], {}, None
    sections = (doc.get("ko") or doc).get("narrative") or []
    for index, spec in enumerate(doc.get("graphics") or []):
        kind, args = spec["kind"], dict(spec.get("args") or {})
        title = str(args.get("title") or spec.get("alt") or "")
        feature_builder = getattr(feature_graphics, kind, None)
        price_data: dict = {}
        if feature_builder is None and kind in data_graphics.BUILDERS:
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
        # 제목↔데이터·그린 종목↔절 본문·표 셀 폭 검사(2026-09-25). 시세를 먼저 읽어야 제목 주장을 잴 수 있다.
        body = None
        if "section" in spec:
            try:
                body = str(sections[int(spec["section"])].get("body") or "")
            except (IndexError, ValueError, AttributeError):
                body = None   # 절 번호가 틀린 것은 아래 배치 검사가 따로 잡는다
        notes: list[str] = []
        issues = graphic_checks.collect_spec_issues(kind, args, title, price_data=price_data or None,
                                                    section_body=body, notes_out=notes)
        if issues:
            raise ValueError("그래픽 데이터 검사 실패:\n- " + "\n- ".join(issues))
        for note in notes:
            print(f"(참고) 그래픽 {index + 1}({kind}) — {note}")
        path = output / f"{index + 1:02d}-{kind}.png"
        if feature_builder is not None:
            feature_builder(output_path=path, **args)
        elif kind in data_graphics.BUILDERS:
            data_graphics.build(kind, price_data, path, lang=str(doc.get("lang") or "ko"), **args)
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


# 시리즈별 공개 상태(2026-09-15, 사용자 지시). 기본은 공개다.
#
# 프리뷰와 기준표(Checkpoint)는 `private` — 네이버에 **본문 전문**이 나가는데 본진에도 같은 글을
# 공개해 두면 네이버가 유사문서로 걸러 낼 수 있다. 시황은 아예 본진에 올리지 않는 쪽을 골랐고,
# 이 둘은 글을 남기되 사이트에 보이지 않게 한다 — 워드프레스의 `private`는 글·주소·분류를 그대로
# 두고 로그인한 관리자에게만 보이며, 사이트맵·목록·피드에서 빠진다. 되돌리려면 표에서 한 줄을 지운다.
#
# Checkpoint는 2026-09-15에 더했다(사용자: "체크포인트는 2번 가이드는 3번으로 진행해"). 근거는
# 서치콘솔 실측 — 구글 노출은 사실상 영어 가이드에서만 나왔고 Checkpoint는 0에 가까웠다. 본진에
# 남겨 둘 이득보다 네이버가 막힐 위험이 크다. **가이드는 일부러 공개로 둔다** — 구글 유입이
# 거기서 나오므로 같은 처리를 하면 안 된다.
# 본진에 비공개로만 올리는 갈래. 프리뷰·기준표(2026-09-15)에 더해 2026-09-22부터 한국어 가이드·주간 결산·다음 주 일정·
# 이벤트도 — 사장님: "네이버는 한글 컨텐츠를 주력으로, 본진에서는 비공개 처리". 영어 가이드("Guide")는 구글 유입의 전부라
# 그대로 공개다. 이 표에 없는 시리즈는 publish.
LIVE_STATUS = {"프리뷰": "private", "기준표": "private",
               "가이드": "private", "주간 결산": "private", "다음 주 일정": "private", "이벤트": "private"}


def _live_status(doc: dict) -> str:
    # 시리즈 칸이 빠진 원고는 관문(`feature_gate`)이 커밋 전에 막는다(2026-09-26). 이 표 자체는 사장님이 정한 대로 둔다.
    return LIVE_STATUS.get(str(doc.get("series") or ""), "publish")


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
    # 그림을 낱장으로 Read하면 프리뷰 한 편에 8~11턴이다(2026-09-25 감사). 원본 크기 그대로 이어 붙인
    # 모음판(`<slug>/sheets/sheet-NN.png`)만 읽게 한다 — 발행 러너에서는 아무도 안 보지만 몇백 ms라 그냥 만든다.
    try:
        sheets = contact_sheet.build(contact_sheet.gather(output), output / contact_sheet.SUBDIR)
        for line in contact_sheet.describe(sheets):
            print(line)
    except Exception as exc:  # noqa: BLE001 - 모음판 실패는 낱장으로 대신하고 이유를 남긴다
        print(f"(참고) 그림 모음판을 만들지 못했습니다 — {output}의 낱장을 읽으십시오: {exc}")
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
    doc = {**doc, "related": _refresh_related(doc.get("related"))}   # 앵커는 살아 있는 제목으로(2026-09-18)
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
    wanted = _live_status(doc)   # 보통 "publish", 프리뷰는 "private"(2026-09-15)
    if existing:
        # status=None은 공개·비공개 어느 상태도 바꾸지 않는다. live일 때만 상태를 올린다.
        result = publish_wordpress.update_draft(existing["id"], ko["title"], html,
                                                status=wanted if live else None, **common)
    else:
        # 새 글은 원칙대로 임시저장한다. --publish는 사용자가 "발행"이라고 한 뒤에만 쓴다.
        result = publish_wordpress.publish_draft(ko["title"], html, slug=slug,
                                                 status=wanted if live else "draft", **common)
    expected = wanted if live else (existing.get("status", "draft") if existing else "draft")
    publish_wordpress.verify_published(
        result["id"], ko["title"], expected_status=expected,
        expected_featured_media=featured_id, expected_category_id=category_id,
    )
    if live and wanted == "publish":
        # 텔레그램 채널 알림(2026-09-12, 홍보 1번). 다시 올린 글은 notify_post가 스스로 거른다. 실패해도 발행은 성공이다.
        # 비공개로 올리는 글(프리뷰)은 여기서 알리지 않는다 — 링크가 독자에게 404다.
        # 그 글의 알림은 맥의 동기화가 네이버에 올린 뒤 네이버 주소로 보낸다(scripts/notify_naver_post.py).
        notify_telegram.notify_post(base, result["id"], ko["title"], doc)
        notify_threads.notify_post(base, result["id"], ko["title"], doc)     # 스레드(2026-09-12, 홍보 2번)
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
