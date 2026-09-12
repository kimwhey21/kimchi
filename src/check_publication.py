"""그날 시황이 실제로 사이트에 올라갔는지 확인합니다.

왜 필요한가
-----------
2026-09-03 아침에 워크플로가 초록 체크로 끝났는데 한국장 글은 올라가지
않았습니다. 알아챈 것은 사람이 사이트를 열어봤기 때문입니다. `verify_published`가
발행 순간을 확인하지만, 그건 발행 스크립트가 **돌았을 때** 이야기입니다.
루틴이 원고를 못 써서 아무것도 커밋되지 않거나, 예약 실행이 시세를 못 받아
멈춘 날은 아무도 실패를 알리지 않습니다.

그래서 발행 시각이 지난 뒤 저장소와 사이트를 함께 확인합니다.

1. 가장 최근 시세 파일(`data/price_<market>_<거래일>.json`)이 있는가
2. 그 거래일 원고(`editorial/<market>_<거래일>.json`)가 있는가
3. 그 원고가 워드프레스에 공개 상태로 올라가 있고, 제목이 원고와 같은가

하나라도 어긋나면 0이 아닌 코드로 끝납니다. 워크플로가 빨간 X로 끝나면
깃허브가 메일을 보내므로, 조용히 지나가는 일이 없어집니다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

# 단독 실행 모듈입니다. main.py가 대신 불러 주지 않으므로 여기서 .env를 읽습니다 —
# 없으면 로컬에서 손으로 돌릴 때 설정이 없는 것처럼 동작합니다(2026-09-06 전수 점검).
load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
EDITORIAL_DIR = ROOT / "editorial"
TIMEOUT_SECONDS = 20
# 글의 신선도는 "거래일 이후에 수정됐는가"로 봅니다. 전에는 "지금부터 36시간
# 안에 수정됐는가"였는데, 주말·휴장을 지나면 새 거래일이 없어 같은 글이 그대로
# 최신인데도 헛경보가 났습니다 — 2026-09-07 노동절 다음 아침이 그랬을 것입니다
# (9/4 글, 9/5 12:53 UTC 수정, 화요일 01:00 UTC 검사 = 60시간). 거래일보다 앞서
# 수정된 글은 그날 원고를 담을 수 없으므로 그것만 잡습니다.


def _latest_trading_date(market: str) -> str | None:
    dates = sorted(
        match.group(1)
        for path in DATA_DIR.glob(f"price_{market}_*.json")
        if (match := re.search(r"(\d{4}-\d{2}-\d{2})\.json$", path.name))
    )
    return dates[-1] if dates else None


def _wordpress_post(slug: str) -> dict | None:
    base_url = os.environ["WORDPRESS_URL"].rstrip("/")
    auth = (os.environ["WORDPRESS_USERNAME"], os.environ["WORDPRESS_APP_PASSWORD"])
    response = requests.get(
        f"{base_url}/wp-json/wp/v2/posts",
        auth=auth,
        params=[("slug", slug), ("context", "edit"), ("per_page", "1"),
                *(("status[]", s) for s in ("publish", "draft", "pending", "future", "private"))],
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    posts = response.json()
    return posts[0] if posts else None


def _sitemap_post_urls() -> set[str] | None:
    """사이트맵(/wp-sitemap.xml)에 실린 글 주소 전부. 못 읽으면 None.

    2026-09-12 검색 유입 전수조사에서 Rank Math 사이트맵이 9/8부터 멈춰 새 글 20편이 사이트맵에 없었던 것을
    나흘 뒤에야 알았다(두 번째 재발). 이제 워드프레스 기본 사이트맵을 쓰지만, 어느 쪽이든 "그날 글이 사이트맵에
    있는가"를 발행 확인이 함께 본다 — 멈추면 그날 저녁 메일로 안다.
    """
    base_url = os.environ["WORDPRESS_URL"].rstrip("/")
    headers = {"User-Agent": "Mozilla/5.0 (fermata publish-check)"}
    try:
        index = requests.get(f"{base_url}/wp-sitemap.xml", headers=headers, timeout=TIMEOUT_SECONDS)
        if index.status_code != 200:
            return None
        urls: set[str] = set()
        for loc in re.findall(r"<loc>([^<]+)</loc>", index.text):
            if "wp-sitemap-posts-post" not in loc:
                continue
            part = requests.get(loc, headers=headers, timeout=TIMEOUT_SECONDS)
            if part.status_code != 200:
                return None
            urls.update(re.findall(r"<loc>([^<]+)</loc>", part.text))
        return urls
    except requests.RequestException:
        return None


def _actual_trading_date(market: str) -> str | None:
    """지금 시점에서 마지막으로 장이 열린 날을 데이터 소스에 물어봅니다.

    저장소 파일만 보면 "오늘 데이터가 아예 안 들어온 날"을 놓칩니다. 2026-09-04이
    그랬습니다 — 시세 수집이 실패해 그날 파일이 없었는데, 점검은 가장 최근 파일
    (9월 3일)과 그 원고를 보고 정상이라고 끝냈습니다.

    휴장일에 헛경보를 내지 않으려고 달력 대신 지수의 실제 마지막 거래일을
    씁니다. 조회에 실패하면 None을 돌려주고 이 검사만 건너뜁니다 — 점검 도구가
    네트워크 문제로 빨간 X를 내는 것은 도움이 되지 않습니다.
    """
    try:
        import FinanceDataReader as fdr

        symbol = "KS11" if market == "kr" else "DJI"
        start = (dt.date.today() - dt.timedelta(days=10)).isoformat()
        frame = fdr.DataReader(symbol, start)
        if frame.empty:
            return None
        return frame.index[-1].date().isoformat()
    except Exception as exc:  # noqa: BLE001 - 확인 못 하면 검사만 건너뜁니다
        print(f"[안내] {market}: 실제 거래일을 확인하지 못해 최신성 검사를 건너뜁니다 ({exc}).")
        return None


def check_market(market: str, check_site: bool, sitemap_urls: set[str] | None = None) -> list[str]:
    """`sitemap_urls`가 주어지면 공개된 글이 사이트맵에 실려 있는지도 본다(None이면 건너뜀)."""
    problems: list[str] = []
    trading_date = _latest_trading_date(market)
    if not trading_date:
        return [f"{market}: 시세 파일이 하나도 없습니다 (data/price_{market}_*.json)."]

    actual = _actual_trading_date(market)
    if actual and actual > trading_date:
        problems.append(
            f"{market}: 마지막 거래일은 {actual}인데 저장소의 최신 시세 파일은 "
            f"{trading_date}입니다. 그날 시세 수집이 실패했거나 커밋되지 않았습니다."
        )

    manuscript = EDITORIAL_DIR / f"{market}_{trading_date}.json"
    if not manuscript.exists():
        problems.append(
            f"{market}: {trading_date} 시세는 있는데 원고가 없습니다 ({manuscript.name}). "
            "조사·집필 루틴이 돌지 않았거나 중간에 멈췄습니다."
        )
        return problems

    if not check_site:
        print(f"{market} {trading_date}: 원고 있음 (사이트 확인은 건너뜀)")
        return problems

    doc = json.loads(manuscript.read_text(encoding="utf-8"))
    for lang in ("ko", "en"):
        if lang not in doc:
            continue
        slug = f"editorial-{market}-{trading_date}-{lang}"
        post = _wordpress_post(slug)
        if not post:
            problems.append(f"{market} {trading_date} [{lang}]: 사이트에 글이 없습니다 (slug={slug}).")
            continue
        if post.get("status") != "publish":
            problems.append(
                f"{market} {trading_date} [{lang}]: 상태가 '{post.get('status')}'입니다 "
                f"(id={post.get('id')}). 공개되지 않았습니다."
            )
        modified = post.get("modified_gmt") or ""
        try:
            modified_at = dt.datetime.fromisoformat(modified).replace(tzinfo=dt.timezone.utc)
        except ValueError:
            problems.append(f"{market} {trading_date} [{lang}]: 수정 시각을 읽지 못했습니다 ({modified}).")
            continue
        day_start = dt.datetime.fromisoformat(trading_date).replace(tzinfo=dt.timezone.utc)
        if modified_at < day_start:
            problems.append(
                f"{market} {trading_date} [{lang}]: 글이 거래일보다 앞선 "
                f"{modified_at:%Y-%m-%d %H:%M} UTC에 마지막으로 수정됐습니다. "
                "그날 원고가 반영되지 않은 옛 글입니다."
            )
        link = str(post.get("link") or "")
        if sitemap_urls is not None and link and link.rstrip("/") not in {u.rstrip("/") for u in sitemap_urls}:
            problems.append(
                f"{market} {trading_date} [{lang}]: 글은 공개됐는데 사이트맵(/wp-sitemap.xml)에 없습니다 ({link}). "
                "사이트맵이 멈췄습니다 — 검색엔진이 새 글을 못 찾습니다(2026-09-08·09-12에 겪은 일)."
            )
        if not problems:
            print(f"{market} {trading_date} [{lang}]: 공개 확인 (id={post.get('id')})")
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description="그날 시황이 실제로 공개됐는지 확인합니다")
    parser.add_argument("markets", nargs="*", default=["kr", "us"], help="확인할 시장 (기본: kr us)")
    args = parser.parse_args()

    check_site = all(
        os.environ.get(key)
        for key in ("WORDPRESS_URL", "WORDPRESS_USERNAME", "WORDPRESS_APP_PASSWORD")
    )
    if not check_site:
        print("[안내] WORDPRESS_* 환경변수가 없어 저장소 파일만 확인합니다.")

    problems: list[str] = []
    sitemap_urls: set[str] | None = None
    if check_site:
        sitemap_urls = _sitemap_post_urls()
        if sitemap_urls is None:
            problems.append("사이트맵(/wp-sitemap.xml)을 읽지 못했습니다 — 검색엔진도 못 읽습니다.")
        else:
            print(f"사이트맵: 글 {len(sitemap_urls)}개")
    for market in args.markets or ["kr", "us"]:
        problems.extend(check_market(market, check_site, sitemap_urls))

    if problems:
        print("\n확인 실패:", file=sys.stderr)
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        sys.exit(1)
    print("\n모두 정상입니다.")


if __name__ == "__main__":
    main()
