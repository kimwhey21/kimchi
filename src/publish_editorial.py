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
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from src import editorial_quality, publish_wordpress, render_html  # noqa: E402

EDITORIAL_DIR = Path(__file__).resolve().parent.parent / "editorial"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

_KO_TAGS = ["코스피", "코스닥", "원달러 환율"]
_EN_TAGS = ["KOSPI", "KOSDAQ", "Korean won"]


def _excerpt(doc: dict, limit: int = 300) -> str:
    body = (doc.get("narrative") or [{}])[0].get("body", "").replace("\n\n", " ")
    if len(body) <= limit:
        return body.strip()
    return body[:limit].rsplit(" ", 1)[0].strip() + "…"


def _latest_editorial() -> Path | None:
    files = sorted(EDITORIAL_DIR.glob("*.json"))
    return files[-1] if files else None


def publish(path: Path, publish_live: bool = False) -> None:
    doc = json.loads(path.read_text(encoding="utf-8"))
    market = doc["market"]
    date_str = doc["date"]
    price_data = doc["price_data"]
    ko = doc["ko"]
    en = doc.get("en")

    # 한국어 원고는 저장소의 편집 기준을 통과해야 올라갑니다.
    editorial_quality.validate_generated(ko)
    print("한국어 편집 기준 검사 통과")

    market_label_en = "Korea Market Close" if market == "kr" else "U.S. Market Close"
    html_ko = render_html.render(market, date_str, price_data, ko)
    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / f"{market}_{date_str}_editorial.html").write_text(html_ko, encoding="utf-8")

    if not publish_wordpress.is_configured():
        print("WORDPRESS_* 환경변수가 없어 업로드를 건너뜁니다 (렌더링만 완료).")
        return

    status = "publish" if publish_live else "draft"
    ko_result = publish_wordpress.publish_draft(
        ko["title"],
        html_ko,
        excerpt=_excerpt(ko),
        tags=_KO_TAGS,
        category="Daily",
        slug=f"editorial-{market}-{date_str}-ko",
        focus_keyword="코스피 마감 시황" if market == "kr" else "뉴욕증시 마감",
    )
    print(f"한국어 초안: id={ko_result.get('id')} {ko_result.get('link','')}")

    if en:
        html_en = render_html.render(
            market, date_str, price_data, en, lang="en", market_label=market_label_en
        )
        (OUTPUT_DIR / f"{market}_{date_str}_editorial_en.html").write_text(
            html_en, encoding="utf-8"
        )
        en_result = publish_wordpress.publish_draft(
            en["title"],
            html_en,
            lang="en",
            excerpt=_excerpt(en),
            tags=_EN_TAGS,
            category="Daily",
            featured_media_id=ko_result.get("featured_media") or None,
            slug=f"editorial-{market}-{date_str}-en",
            focus_keyword="Kospi close" if market == "kr" else "US stocks close",
        )
        print(f"영어 초안: id={en_result.get('id')} {en_result.get('link','')}")

    print(f"상태: {status} (검수 후 공개 전환)")


def main() -> None:
    parser = argparse.ArgumentParser(description="커밋된 편집 원고를 워드프레스에 올립니다")
    parser.add_argument("path", nargs="?", help="editorial/*.json 경로 (생략하면 가장 최근 파일)")
    args = parser.parse_args()

    path = Path(args.path) if args.path else _latest_editorial()
    if path is None or not path.exists():
        sys.exit("발행할 원고 파일이 없습니다 (editorial/*.json).")
    print(f"원고: {path}")
    publish(path)


if __name__ == "__main__":
    main()
