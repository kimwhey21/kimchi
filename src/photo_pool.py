"""시황 표지에 쓸 **미리 승인된** 사진을 그날 데이터로 고릅니다.

왜 미리 승인하는가
------------------
시황은 사람 검수 없이 자동 공개됩니다. 발행 시점에 사진을 검색하면 틀린 사진이
그대로 사이트에 걸립니다 — `korean bank`가 삼청빌라, `korean won banknote`가
중국 위안화(마오쩌둥), `red traffic light`가 초록불로 나온 실측 기록이 있습니다.

그래서 **검색은 사람이 미리 하고, 자동 실행은 고르기만 합니다.**
`config/photo_pool.yaml`의 사진은 전부 `Read` 툴로 한 장씩 보고 승인한 것이며,
이 모듈은 네트워크를 쓰지 않습니다.

어떻게 고르는가
---------------
그날 주인공 종목이 정해지면(제목이 부른 종목, 없으면 등락 1위) 그 종목의
**업종** 사진을 씁니다. 업종이 맞으면 표지로 충분하다는 것이 2026-09-06에
정리한 규칙입니다 — 은행주가 무너진 글에 은행 사진이 나오는 것은 당연합니다.

같은 업종에 사진이 여럿이면 **날짜로 돌려 씁니다.** 삼성전자가 사흘 연속
주인공이어도 표지는 사흘 다 다릅니다. 목록에서 어제 글과 구분되게 하는 것이
이 기능의 목적이라, 회전이 없으면 절반은 의미가 없습니다.

없으면 없는 대로 갑니다
-----------------------
업종에 사진이 없거나(소비재 등) 주인공이 지수뿐인 날은 `None`을 돌려주고,
`featured_image`가 지금까지처럼 데이터 그래픽을 그립니다. 억지로 아무 사진이나
붙이지 않습니다 — 그러면 이 보관함을 만든 이유가 없어집니다.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "config" / "photo_pool.yaml"


class PhotoPoolError(RuntimeError):
    pass


def load(path: Path | None = None) -> list[dict]:
    """보관함을 읽습니다. 없거나 비어 있으면 **예외로 올립니다.**

    빈 목록을 조용히 돌려주면 "사진을 안 붙이기로 한 날"과 "설정 파일이 깨진
    날"이 같은 화면으로 나옵니다. 2026-09-06에 그 유형의 침묵을 여섯 개 걷어낸
    참이라 여기서 다시 만들지 않습니다.
    """
    path = path or MANIFEST
    if not path.exists():
        raise PhotoPoolError(f"사진 보관함이 없습니다: {path}")
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    photos = doc.get("photos") or []
    if not photos:
        raise PhotoPoolError(f"{path}에 사진이 하나도 없습니다.")
    missing = [p["id"] for p in photos if not (ROOT / p["file"]).exists()]
    if missing:
        raise PhotoPoolError(
            f"보관함이 가리키는 파일이 없습니다: {', '.join(missing)}. "
            f"assets/photos/를 확인하십시오.")
    return photos


def _candidates(photos: list[dict], entry: dict | None) -> list[dict]:
    """주인공 종목에 맞는 사진을 좁힙니다 — 티커 먼저, 그다음 업종."""
    if not entry:
        return []
    if entry.get("source") == "dynamic":
        # 그날 거래대금으로 편입된 종목에는 사진을 붙이지 않습니다 — 저장소가
        # 이미 정해 둔 규칙입니다(CLAUDE.md「비용/자동 발행 원칙」). 이름도 모르는
        # 종목에 업종 사진을 붙이면 엉뚱한 그림이 됩니다. 지금은 스크리너가 주는
        # 업종 이름("Technology")이 보관함과 안 맞아 저절로 걸러지지만, 그건
        # 우연이라 규칙으로 굳혀 둡니다.
        return []
    ticker = str(entry.get("ticker") or "")
    sector = entry.get("sector")
    # 티커로 직접 지정된 사진이 있으면 그쪽이 우선입니다(현대차 라인 사진처럼
    # 그 회사가 실제로 찍힌 것이 있습니다).
    exact = [p for p in photos if ticker and ticker in (p.get("tickers") or [])]
    if exact:
        return exact
    return [p for p in photos if sector and p.get("sector") == sector]


def pick(entry: dict | None, date_str: str, photos: list[dict] | None = None) -> dict | None:
    """그날 쓸 사진 하나. 맞는 것이 없으면 None(= 데이터 그래픽으로 갑니다).

    `date_str`로 돌려 쓰기 때문에 같은 종목이 이어져도 표지가 달라집니다.
    무작위가 아니라 날짜 함수라, 같은 날 다시 돌리면 같은 사진이 나옵니다 —
    재실행이 표지를 바꾸면 워드프레스에 미디어가 중복으로 쌓입니다.
    """
    photos = photos if photos is not None else load()
    hits = _candidates(photos, entry)
    if not hits:
        return None
    hits = sorted(hits, key=lambda p: p["id"])
    try:
        ordinal = dt.date.fromisoformat(date_str).toordinal()
    except (TypeError, ValueError):
        raise PhotoPoolError(f"날짜를 읽지 못했습니다: {date_str!r}")
    return hits[ordinal % len(hits)]


def resolve(photo: dict) -> Path:
    return ROOT / photo["file"]
