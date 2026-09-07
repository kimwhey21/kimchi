"""저장소에 커밋된 편집 원고(editorial/*.json)를 워드프레스 초안으로 발행합니다.

왜 이 단계가 따로 있는가
------------------------
`generate_free.py`는 시세와 RSS 제목만 조합하므로 "왜 그렇게 움직였는지"를 쓸 수
없습니다. 그 조사·해석은 웹 검색이 가능한 에이전트(클라우드 루틴)가 맡고, 결과를
`editorial/<market>_<date>.json`으로 저장소에 커밋합니다. 이 스크립트는 그 파일을
읽어 렌더링·업로드만 합니다.

이렇게 나눈 이유는 자격증명입니다. 클라우드 루틴은 로컬 `.env`나 GitHub Secrets에
접근할 수 없습니다. 반대로 GitHub Actions는 이미 `WORDPRESS_*` 시크릿을 갖고
있습니다. 그래서 **조사·집필은 루틴이, 발행은 Actions가** 맡고 워드프레스
비밀번호는 GitHub 밖으로 나가지 않습니다.

원고 파일 형식
--------------
{
  "market": "kr",
  "date": "2026-09-02",
  "price_data": { ... fetch_kr.fetch_all() 결과 그대로 ... },
  "ko": {"title":..., "narrative":[...], "insight_section":{...}, "sources":[...]},
  "en": {...}                      # 선택. 없으면 한국어판만 발행합니다.
}

price_data를 함께 저장하는 이유는 재현성입니다. 발행 시점에 시세를 다시 부르면
원고가 인용한 숫자와 달라질 수 있습니다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from src import (  # noqa: E402
    data_graphics,
    editorial_facts,
    editorial_quality,
    editorial_title,
    editorial_quality_en,
    featured_image,
    photo_pool,
    publish_wordpress,
    render_html,
)

ROOT = Path(__file__).resolve().parent.parent
EDITORIAL_DIR = ROOT / "editorial"
OUTPUT_DIR = ROOT / "output"

_KO_TAGS = ["코스피", "코스닥", "원달러 환율"]
_EN_TAGS = ["KOSPI", "KOSDAQ", "Korean won"]


def _excerpt(doc: dict, limit: int = 300) -> str:
    body = (doc.get("narrative") or [{}])[0].get("body", "").replace("\n\n", " ")
    if len(body) <= limit:
        return body.strip()
    return body[:limit].rsplit(" ", 1)[0].strip() + "…"


_NAME_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})\.json$")


def _editorial_order(path: Path) -> tuple[str, float]:
    """파일명에 든 거래일을 우선 보고, 없으면 수정 시각으로 정렬합니다."""
    match = _NAME_DATE.search(path.name)
    return (match.group(1) if match else "", path.stat().st_mtime)


def _latest_editorial() -> Path | None:
    """가장 최근 거래일 원고를 고릅니다.

    전에는 `sorted(glob("*.json"))[-1]`이었습니다. 그건 '가장 최근'이 아니라
    '파일명 알파벳 마지막'이고, "us" > "kr"이라 미국장 원고가 하나라도 있으면
    한국장 원고는 날짜가 더 최신이어도 절대 선택되지 않았습니다.

    2026-09-03에 실제로 그렇게 됐습니다. 그날 한국장 원고(kr_2026-09-03.json)를
    커밋했더니 워크플로가 us_2026-09-02.json을 골랐고, 그 글은 이미 공개 상태라
    아무것도 바뀌지 않은 채 초록 체크로 끝났습니다. 한국장 글은 발행되지 않았고
    실패로 잡히지도 않았습니다.

    이제 워크플로는 푸시에 실제로 들어 있던 파일 경로를 넘기므로 이 함수는
    수동 실행(workflow_dispatch, 경로를 비운 경우)의 기본값으로만 쓰입니다.
    """
    files = sorted(EDITORIAL_DIR.glob("*.json"), key=_editorial_order)
    return files[-1] if files else None


def _watchlist_names(price_data: dict) -> list[str]:
    """사진을 붙여도 되는 종목명(한글·영문)을 모읍니다 — **코어 종목만**.

    거래대금 상위로 그날 자동 편입된 종목(source="dynamic")은 제외합니다.
    이 경로는 사람 검수 없이 바로 공개되는데, 편입 종목은 매일 달라지고 그중
    상당수는 사진으로 확인할 만한 대상이 없습니다(지주회사, 중견 제조사 등).
    삼성전자·현대차처럼 사진이 분명한 대상만 통과시키는 원칙을 유지하려면
    목록이 고정된 코어만 여는 것이 맞습니다.
    """
    names: list[str] = []
    for entry in (price_data.get("watchlist") or {}).values():
        if entry.get("source") == "dynamic":
            continue
        for key in ("name", "name_en"):
            value = (entry.get(key) or "").strip()
            if value:
                names.append(value)
    return names


def _concrete_image_query(query: str | None, price_data: dict) -> str | None:
    """사진을 붙여도 되는 검색어면 그대로, 아니면 None을 돌려줍니다."""
    matched = _matched_core_name(query, price_data)
    return query if matched else None


def _matched_core_name(query: str | None, price_data: dict) -> str | None:
    """검색어 안에 들어 있는 코어 종목명을 돌려줍니다. 없으면 None.

    반환된 이름은 두 곳에 쓰입니다. 첫째, 사진을 붙여도 되는 검색어인지 판단
    (아래 설명). 둘째, Unsplash에 결과가 없을 때 위키미디어에서 그 회사 사진을
    찾는 열쇠 — 검색어가 아니라 종목 자체로 찾아야 엉뚱한 사진을 피합니다.

    통과 조건은 하나입니다 — **검색어에 그날 워치리스트 종목명이 들어 있을 것.**

    왜 이렇게 좁게 여는가: 이 경로는 사람 검수 없이 바로 공개됩니다. 검색어가
    추상적이면 엉뚱한 사진이 그대로 나갑니다. 실제로 걸러낸 사례가 있습니다 —
    "korean won banknote"에 중국 위안화(마오쩌둥) 지폐, "red traffic light"에
    초록불, "currency exchange booth"에 태국 길거리 환전소, "hourglass on
    wooden desk"에 아이맥이 놓인 책상. 반면 삼성전자·엔비디아처럼 사진으로
    확인 가능한 대상은 검색이 비교적 안전합니다. src/main.py의 대표 이미지
    로직이 watchlist만 대상으로 하고 macro(지수·환율·금리)를 제외하는 것과
    같은 원칙입니다.

    통과하지 못한 검색어는 조용히 버리지 않고 이유를 출력합니다.
    """
    if not query:
        return None
    lowered = query.lower()
    for name in _watchlist_names(price_data):
        if name.lower() in lowered:
            return name
    print(
        f"[안내] 사진 없이 갑니다 — 검색어 '{query}'에 워치리스트 종목명이 없습니다. "
        "검수 없이 공개되는 경로라 구체적인 종목명이 든 검색어만 사진을 붙입니다."
    )
    return None


def _watchlist_entry_named(name: str, price_data: dict) -> dict | None:
    """코어 종목명(한/영)으로 그날 워치리스트 항목을 찾습니다."""
    for ticker, entry in (price_data.get("watchlist") or {}).items():
        if entry.get("source") == "dynamic":
            continue
        if name in ((entry.get("name") or "").strip(), (entry.get("name_en") or "").strip()):
            return {**entry, "ticker": entry.get("ticker") or ticker}
    return None


def _pool_image(photo: dict, upload: bool) -> dict:
    """승인 풀 사진 하나를 템플릿이 읽는 image dict로 바꿉니다."""
    path = photo_pool.resolve(photo)
    url = str(path)
    if upload and publish_wordpress.is_configured():
        uploaded = publish_wordpress.upload_image_url(
            {"local_path": str(path), "alt": photo.get("seen", ""),
             "caption": photo.get("credit", ""), "id": photo["id"]}
        )
        if not uploaded:
            raise publish_wordpress.WordPressPublishError(f"풀 사진 업로드 실패: {photo['id']}")
        url = uploaded
    return {"id": photo["id"], "url": url, "alt": photo.get("seen", ""),
            "credit": photo.get("credit", ""), "credit_url": photo.get("source_page")}


def _attach_story_images(doc_section: dict | None, price_data: dict, date_str: str = "",
                         upload: bool = True, exclude_ids: set[str] | None = None) -> dict | None:
    """인사이트 스토리 사진. 두 경로뿐이고 **둘 다 사람이 본 사진**입니다(2026-09-07).

    1. 루틴이 `image`를 채워 보냈으면 그대로 씁니다. 루틴 샌드박스 네트워크가
       열려서(2026-09-07 실측) 루틴이 Unsplash 후보를 직접 내려받아 `Read`로 보고
       고른 뒤 **URL과 출처만** 원고에 적습니다 — 파일은 커밋하지 않습니다.
       필수 키 `url`, 선택 `alt`·`photographer`·`photographer_url`·`credit`·
       `credit_url`·`width`·`height`(템플릿이 그대로 읽습니다).
    2. 없으면 `image_query`에 든 코어 종목명으로 승인 풀(`config/photo_pool.yaml`)
       에서 그 종목·업종 사진을 고릅니다. 네트워크를 쓰지 않습니다. 풀에 없으면
       사진 없이(표·차트만) 갑니다.

    발행 시점의 실시간 검색은 뺐습니다. 아무도 안 보고 붙는 유일한 사진이었고,
    실제로 'SK Hynix memory chip'에 로고 사진이 나갔습니다(2026-09-07). 사진이
    없는 것이 틀린 사진보다 낫다는 원칙은 그대로입니다.
    """
    if not doc_section or not doc_section.get("stories"):
        return doc_section
    stories = []
    used: set[str] = set(exclude_ids or ())
    for story in doc_section["stories"]:
        story = dict(story)
        provided = story.get("image")
        if isinstance(provided, dict) and str(provided.get("url", "")).startswith("http"):
            # 루틴이 눈으로 보고 고른 사진. 건드리지 않습니다.
            print(f"[안내] 루틴이 고른 사진 사용: {provided.get('url')}")
            stories.append(story)
            continue
        story["image"] = None
        query = story.get("image_query")
        name = _matched_core_name(query, price_data)
        entry = _watchlist_entry_named(name, price_data) if name else None
        if entry:
            try:
                photo = photo_pool.pick(entry, date_str, exclude=used)
            except photo_pool.PhotoPoolError as error:
                print(f"[경고] 사진 풀을 읽지 못해 사진 없이 갑니다: {error}")
                photo = None
            if photo:
                used.add(photo["id"])
                story["image"] = _pool_image(photo, upload)
                print(f"[안내] 풀 사진 첨부: '{query}' -> {photo['id']} ({photo.get('seen', '')[:40]})")
            else:
                print(f"[안내] 사진 없이 갑니다 — '{entry.get('name')}'({entry.get('sector')})에 맞는 풀 사진이 없습니다.")
        stories.append(story)
    return {**doc_section, "stories": stories}


def _attach_section_graphics(doc_section: list, price_data: dict, market: str,
                             date_str: str, previous: dict | None,
                             upload: bool = True) -> None:
    """본문 절에 지정된 데이터 그래픽을 만들고, `upload`면 사이트에 올려 URL을 채웁니다.

    사진과 달리 이 그림은 그날 시세에서 그리므로 숫자가 어긋날 수 없습니다.
    업로드에 실패하면 그림 없이 글이 나갑니다 — 그림 하나가 발행을 막으면 안 됩니다.

    `upload=False`(렌더 전용 확인)면 미디어 라이브러리에 쓰지 않고 로컬 파일
    경로를 그대로 `url`에 넣는다 — `output/`에 결과 HTML과 PNG가 같이 있으므로
    브라우저로 열어 보면 그대로 뜬다. 2026-09-06에 이 구분이 없어서 렌더
    확인만 하려다 실제로 미디어 라이브러리에 업로드해버린 적이 있다.
    """
    for index, section in enumerate(doc_section or [], start=1):
        spec = section.get("graphic")
        if not isinstance(spec, dict) or not spec.get("kind"):
            continue
        kind = spec["kind"]
        options = {k: v for k, v in spec.items() if k not in ("kind", "url", "alt")}
        if kind == "two_day_compare":
            options["previous"] = previous
        try:
            local = OUTPUT_DIR / f"{market}_{date_str}_{index}_{kind}.png"
            data_graphics.build(kind, price_data, local, **options)
            if not upload:
                section["graphic"] = {"url": str(local), "alt": spec.get("title", ""), "kind": kind}
                print(f"[안내] 본문 그래픽(업로드 안 함): {kind} -> {local}")
                continue
            url = publish_wordpress.upload_image_url(
                {"local_path": str(local), "alt": spec.get("title", ""),
                 "caption": "이 글의 시세로 만든 데이터 그래픽입니다."}
            )
            if url:
                section["graphic"] = {"url": url, "alt": spec.get("title", ""), "kind": kind}
                print(f"[안내] 본문 그래픽: {kind} -> {url}")
            else:
                section.pop("graphic", None)
        except Exception as exc:  # noqa: BLE001
            print(f"[안내] 본문 그래픽 생략 — {kind}: {exc!r}")
            section.pop("graphic", None)


def _previous_price_data(market: str, date_str: str) -> dict | None:
    """전 거래일 시세 파일(이틀 비교 그래픽용)."""
    files = sorted(
        p for p in (ROOT / "data").glob(f"price_{market}_*.json") if p.stem < f"price_{market}_{date_str}"
    )
    if not files:
        return None
    return json.loads(files[-1].read_text(encoding="utf-8"))


def _previous_daily_post(market: str, date_str: str, lang: str) -> dict | None:
    """전 거래일 같은 시장·같은 언어 시황 글을 찾습니다(내부 링크용, 2026-09-06 추가).

    벤치마크(재테크농부)는 이전 글로 내부 링크를 99% 걸지만 시황 자동 발행
    경로는 0%였다. 날짜는 이 시장의 실제 전 거래일 시세 파일명에서 가져온다 —
    주말·공휴일을 건너뛴 진짜 전 거래일이라야 slug가 실제로 존재한다.
    자동 공개 경로이므로 조회가 실패하거나(네트워크, 설정 없음) 그날 글이
    없거나(첫 글, 이전 발행 실패) 아직 초안이면 조용히 None을 돌려주고
    발행을 막지 않는다 — 관련 글 링크는 있으면 좋은 것이지 필수 조건이 아니다.
    """
    files = sorted(
        p for p in (ROOT / "data").glob(f"price_{market}_*.json")
        if p.stem < f"price_{market}_{date_str}"
    )
    if not files:
        return None
    prev_date = files[-1].stem.removeprefix(f"price_{market}_")
    if not publish_wordpress.is_configured():
        return None
    try:
        base = os.environ["WORDPRESS_URL"].rstrip("/")
        auth = (os.environ["WORDPRESS_USERNAME"], os.environ["WORDPRESS_APP_PASSWORD"])
        slug = f"editorial-{market}-{prev_date}-{lang}"
        post = publish_wordpress._find_existing_post_by_slug(base, auth, slug)
        if not post or post.get("status") != "publish":
            return None
        return {"title": post["title"]["rendered"], "url": post["link"]}
    except Exception as exc:  # noqa: BLE001 - 링크 하나 때문에 발행을 막지 않음
        print(f"[안내] 이전 글 링크 조회 실패, 링크 없이 계속합니다: {exc!r}", file=sys.stderr)
        return None


def publish(path: Path, publish_live: bool = False, render_only: bool = False) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    doc = json.loads(path.read_text(encoding="utf-8"))
    # 기준표(feature) 원고는 스키마가 다릅니다 — 그날 시세가 아니라 밸류에이션·
    # 일정을 다루므로 market·price_data가 없습니다. **`doc["market"]`을 읽기 전에**
    # 걸러야 KeyError로 죽지 않습니다(워크플로 트리거도 좁혀 뒀지만, 수동 실행에서
    # 경로를 직접 넘길 수 있어 여기도 막습니다).
    if doc.get("kind") == "feature" or "price_data" not in doc:
        print(f"[안내] {path.name}은 기준표 원고입니다 — 이 워크플로가 발행하지 않습니다. "
              f"docs/feature-style.md 참조.")
        return
    market = doc["market"]
    date_str = doc["date"]
    price_data = doc["price_data"]
    ko = doc["ko"]
    en = doc.get("en")

    # 원고는 저장소의 편집 기준을 통과해야 올라갑니다. 자동 공개 경로에서는
    # 이 검사가 유일한 안전장치라 영어판도 같이 검사합니다(main.py와 동일).
    editorial_quality.validate_generated(ko)
    print("한국어 편집 기준 검사 통과")
    # 형식 검사와 별개로 원고의 숫자를 시세와 대조합니다. 검수 없이 공개되는
    # 경로라 "숫자는 시세에서만 가져온다"를 사람의 성실성에만 맡기지 않습니다.
    editorial_facts.validate(ko, price_data, lang="ko")
    print("시세 대조 검사 통과 (한국어)")
    # 제목 문법은 문서에만 적혀 있었고, 규칙을 전부 어긴 제목이 위 두 검사를
    # 그대로 통과했습니다(2026-09-04 실측). 검수 없이 공개되는 경로라 기계적으로
    # 잡을 수 있는 것은 여기서 막습니다. 영어판 제목은 이 문법의 대상이 아닙니다.
    editorial_title.validate(ko, price_data)
    print("제목 문법 검사 통과 (한국어)")
    if en:
        editorial_quality_en.validate_generated(en)
        print("영어 편집 기준 검사 통과")
        editorial_facts.validate(en, price_data, lang="en")
        print("시세 대조 검사 통과 (영어)")

    # 본문 데이터 그래픽 (한국어판). 그날 시세로 그리므로 숫자가 어긋날 수 없습니다.
    # render_only일 때는 로컬 파일만 만들고 미디어 라이브러리에는 올리지 않는다.
    if publish_wordpress.is_configured():
        _attach_section_graphics(
            ko.get("narrative"), price_data, market, date_str,
            _previous_price_data(market, date_str),
            upload=not render_only,
        )

    # 인사이트 스토리 사진. 한국어판에서 찾은 사진을 영어판이 그대로 쓰도록
    # 순서를 맞춰 재사용합니다(같은 소재에 다른 사진이 붙지 않게, 그리고
    # Unsplash 호출을 두 배로 늘리지 않게).
    # 표지가 풀 사진을 쓰는 날은 그 사진을 본문에서 다시 쓰지 않습니다.
    cover_photo = featured_image._photo_for(price_data, ko, date_str)
    ko["insight_section"] = _attach_story_images(
        ko.get("insight_section"), price_data, date_str,
        upload=not render_only,
        exclude_ids={cover_photo["id"]} if cover_photo else None,
    )
    if en and en.get("insight_section") and ko.get("insight_section"):
        ko_images = [s.get("image") for s in ko["insight_section"].get("stories", [])]
        en_stories = []
        for index, story in enumerate(en["insight_section"].get("stories", [])):
            story = dict(story)
            story["image"] = ko_images[index] if index < len(ko_images) else None
            en_stories.append(story)
        en["insight_section"] = {**en["insight_section"], "stories": en_stories}

    market_label_en = "Korea Market Close" if market == "kr" else "U.S. Market Close"
    related_ko = _previous_daily_post(market, date_str, "ko")
    html_ko = render_html.render(
        market, date_str, price_data, ko,
        related=[related_ko] if related_ko else None,
    )
    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / f"{market}_{date_str}_editorial.html").write_text(html_ko, encoding="utf-8")

    html_en = None
    if en:
        related_en = _previous_daily_post(market, date_str, "en")
        html_en = render_html.render(
            market, date_str, price_data, en, lang="en", market_label=market_label_en,
            related=[related_en] if related_en else None,
        )
        (OUTPUT_DIR / f"{market}_{date_str}_editorial_en.html").write_text(
            html_en, encoding="utf-8"
        )

    # 대표 이미지는 실제 마감 수치로 생성합니다. 검수되지 않은 사진 검색 결과를
    # 예약 경로에 쓰지 않는다는 AGENTS.md 원칙을 그대로 따릅니다.
    # 업로드 여부와 무관하게 만들어 둡니다 — 자격증명 없이 돌려도 결과물을
    # 눈으로 확인할 수 있어야 하기 때문입니다.
    # 언어마다 따로 만듭니다. 영어 글에 한글 종목명이 박힌 그림이 붙으면 읽는
    # 사람이 무슨 종목인지 알 수 없습니다. 레이아웃은 두 언어가 같습니다 —
    # 같은 날 같은 이야기이므로 한국어 원고 하나로 정합니다.
    image_meta = None
    image_meta_en = None
    try:
        # 원고를 함께 넘깁니다 — 제목이 종목 하나를 부르면 그 종목을 대문에
        # 크게 세우고, 여럿을 부르거나 지수가 주인공인 날이면 상위 셋을
        # 나열합니다(featured_image.choose_layout).
        image_meta = featured_image.create(
            market, date_str, price_data,
            OUTPUT_DIR / f"{market}_{date_str}_editorial.png", ko,
        )
        print(f"대표 이미지 생성: {image_meta['local_path']}")
        if en:
            image_meta_en = featured_image.create(
                market, date_str, price_data,
                OUTPUT_DIR / f"{market}_{date_str}_editorial_en.png", ko, lang="en",
            )
            print(f"대표 이미지(영어) 생성: {image_meta_en['local_path']}")
    except Exception as exc:  # noqa: BLE001 - 이미지 실패로 발행을 막지 않음
        print(f"[경고] 대표 이미지 생성 실패, 이미지 없이 계속합니다: {exc!r}")

    if not publish_wordpress.is_configured():
        # **이 경로는 `editorial_publish.yml`이 자동으로 돌립니다.** 조용히
        # 돌아가면 워크플로가 초록 체크로 끝나고 사이트에는 아무것도 없습니다 —
        # 2026-09-03 아침에 실제로 그렇게 됐고, 알아챈 것은 사람이 사이트를
        # 열어봤기 때문이었습니다. 빨간 X로 끝나야 메일이 옵니다.
        #
        # 손으로 렌더만 해 보고 싶을 때는 `--render-only`를 쓰십시오.
        if render_only:
            print("WORDPRESS_* 환경변수가 없습니다. 렌더링만 하고 끝냅니다.")
            return
        raise publish_wordpress.WordPressPublishError(
            "WORDPRESS_* 환경변수가 없어 발행하지 못했습니다. 자동 실행이라면 "
            "저장소 시크릿(WORDPRESS_URL·WORDPRESS_USERNAME·WORDPRESS_APP_PASSWORD)을 "
            "확인하십시오. 렌더된 HTML은 output/에 있습니다.")

    if render_only:
        # 워드프레스 설정이 있어도 여기서 멈춘다 — 위 그래픽은 이미 업로드 없이
        # 로컬로만 만들었고(upload=not render_only), html_ko/html_en도 이미
        # output/에 썼다. 아래 publish_draft는 실제 글 발행/미디어 업로드를
        # 하므로 호출 자체를 건너뛴다. 2026-09-06 전에는 이 분기가 없어서
        # `--render-only`가 워드프레스 설정이 있으면 이름과 달리 실제로
        # 그래픽을 올리고, 새 날짜면 글까지 만들었다.
        print("--render-only: 워드프레스에 쓰지 않고 렌더 결과만 output/에 남깁니다.")
        return

    status = "publish" if publish_live else "draft"
    ko_result = publish_wordpress.publish_draft(
        ko["title"],
        html_ko,
        excerpt=_excerpt(ko),
        tags=_KO_TAGS,
        category="Daily",
        image=image_meta,
        slug=f"editorial-{market}-{date_str}-ko",
        focus_keyword="코스피 마감 시황" if market == "kr" else "뉴욕증시 마감",
        status=status,
    )
    print(f"한국어 {status}: id={ko_result.get('id')} {ko_result.get('link','')}")
    if publish_live:
        publish_wordpress.verify_published(ko_result["id"], ko["title"])

    if en:
        en_result = publish_wordpress.publish_draft(
            en["title"],
            html_en,
            lang="en",
            excerpt=_excerpt(en),
            tags=_EN_TAGS,
            category="Daily",
            image=image_meta_en,
            slug=f"editorial-{market}-{date_str}-en",
            focus_keyword="Kospi close" if market == "kr" else "US stocks close",
            status=status,
        )
        print(f"영어 {status}: id={en_result.get('id')} {en_result.get('link','')}")
        if publish_live:
            publish_wordpress.verify_published(en_result["id"], en["title"])

    print(
        f"상태: {status}"
        + (" (바로 공개)" if publish_live else " (검수 후 공개 전환)")
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="커밋된 편집 원고를 워드프레스에 올립니다")
    # 한 번의 푸시에 한국장·미국장 원고가 함께 들어올 수 있어 경로를 여러 개
    # 받습니다. 하나만 받던 시절에는 나머지가 조용히 발행되지 않았습니다.
    parser.add_argument(
        "paths",
        nargs="*",
        help="editorial/*.json 경로 (생략하면 가장 최근 거래일 파일 하나)",
    )
    parser.add_argument(
        "--publish-live",
        action="store_true",
        help="임시저장이 아니라 바로 공개 상태로 올립니다 (원고 커밋 자동 실행 전용).",
    )
    parser.add_argument(
        "--render-only",
        action="store_true",
        help="워드프레스 설정이 없어도 HTML만 만들고 조용히 끝냅니다. "
             "**자동 실행에는 붙이지 마십시오** — 설정 누락이 성공으로 보입니다.",
    )
    args = parser.parse_args()

    if args.paths:
        paths = [Path(p) for p in args.paths]
    else:
        latest = _latest_editorial()
        paths = [latest] if latest else []
    if not paths:
        sys.exit("발행할 원고 파일이 없습니다 (editorial/*.json).")

    # 하나라도 없는 경로가 있으면 아무것도 올리기 전에 멈춥니다.
    missing = [p for p in paths if not p.exists()]
    if missing:
        sys.exit("원고 파일이 없습니다: " + ", ".join(str(p) for p in missing))

    for path in paths:
        print(f"원고: {path}")
        publish(path, publish_live=args.publish_live, render_only=args.render_only)


if __name__ == "__main__":
    main()
