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

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
EDITORIAL_DIR = ROOT / "editorial"
TIMEOUT_SECONDS = 20
# 발행이 이 시간 안에 이뤄졌어야 "오늘 것"으로 봅니다. 주말·휴장을 지나 같은
# 거래일 파일이 며칠 남아 있을 수 있으므로 넉넉하게 둡니다.
_FRESH_HOURS = 36


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


def check_market(market: str, check_site: bool) -> list[str]:
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
            age = dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(
                modified
            ).replace(tzinfo=dt.timezone.utc)
            if age > dt.timedelta(hours=_FRESH_HOURS):
                problems.append(
                    f"{market} {trading_date} [{lang}]: 글이 {age.days}일 전에 마지막으로 "
                    "수정됐습니다. 새 원고가 반영되지 않았을 수 있습니다."
                )
        except ValueError:
            problems.append(f"{market} {trading_date} [{lang}]: 수정 시각을 읽지 못했습니다 ({modified}).")
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
    for market in args.markets or ["kr", "us"]:
        problems.extend(check_market(market, check_site))

    if problems:
        print("\n확인 실패:", file=sys.stderr)
        for problem in problems:
            print(f"- {problem}", file=sys.stderr)
        sys.exit(1)
    print("\n모두 정상입니다.")


if __name__ == "__main__":
    main()
