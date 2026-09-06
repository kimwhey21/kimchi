"""표지 사진 후보를 라이선스가 확인된 곳에서만 찾습니다.

왜 필요한가
-----------
2026-09-07에 표지 사진을 찾으며 경로를 하나씩 두드려 봤습니다.

    유니스플래시(한국어)   `KB금융`·`신한지주` 결과 없음. `korean bank`는 삼청빌라,
                          `bank building seoul`은 용산 도시 전경.
    유니스플래시(영어)     실제 은행이 나오지만 OTP(헝가리)·ICICI(인도) 간판,
                          시카고 연방준비은행 — 우리 글이 다루지 않는 회사다.
    위키데이터 P18        신한은행 대표 이미지가 **숭례문**, SK하이닉스가
                          **정전기 방지 포장재**. 저장소가 이미 기록해 둔 함정이다.
    네이버·구글 이미지     검색은 되지만 **라이선스 필터가 없다.** 결과 대부분이
                          언론사·보도자료 사진이라 그대로 쓰면 저작권 침해다.
                          구글 CSE는 2027-01-01 종료 예정이고 신규 가입도 닫혔다.

남은 것이 둘이었습니다 — 위키미디어 공용, 그리고 **Openverse**입니다.

왜 Openverse인가
----------------
워드프레스 재단이 운영하는 CC 이미지 통합 검색입니다. 위키미디어·플리커 등을
한 번에 뒤지고, **결과마다 라이선스가 붙어 나오며**, `license_type=commercial`로
상업적 이용이 가능한 것만 거를 수 있습니다. 키가 필요 없습니다(2026-09-07 실측).

무엇을 하지 않는가
------------------
**자동으로 글에 붙이지 않습니다.** 후보를 내려받아 목록으로 보여줄 뿐이고, 어느
것을 쓸지는 사람이 눈으로 보고 정합니다. 검색어만 믿고 붙였다가 계곡 사진이
나간 적이 있습니다.

`BY-NC`(비상업)와 `BY-ND`(변형금지)는 기본으로 거릅니다 — 블로그는 상업적
이용으로 볼 여지가 있고, 워드프레스가 썸네일을 만들면서 크기를 바꿉니다.

사용법
------
    python -m src.photo_search "SK Hynix" --out output/photos
    python -m src.photo_search "Kookmin Bank" --all-licenses
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests

API = "https://api.openverse.org/v1/images/"
HEADERS = {"User-Agent": "market-brief/1.0 (https://fermata.it.kr)"}
TIMEOUT = 30

# 블로그에 쓰기 어려운 라이선스. NC는 상업적 이용 금지, ND는 변형 금지인데
# 워드프레스가 썸네일을 만들며 크기를 바꿉니다.
_BLOCKED = ("nc", "nd")


def search(query: str, limit: int = 8, commercial_only: bool = True) -> list[dict]:
    params = {"q": query, "page_size": max(limit * 2, 10)}
    if commercial_only:
        params["license_type"] = "commercial"
    response = requests.get(API, params=params, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    rows = []
    for item in response.json().get("results", []):
        license_code = (item.get("license") or "").lower()
        if commercial_only and any(part in license_code.split("-") for part in _BLOCKED):
            continue
        rows.append({
            "title": item.get("title") or "",
            "license": f"{license_code.upper()} {item.get('license_version') or ''}".strip(),
            "creator": item.get("creator") or "",
            "source": item.get("source") or "",
            "url": item.get("url"),
            "page": item.get("foreign_landing_url"),
            "width": item.get("width"), "height": item.get("height"),
        })
        if len(rows) >= limit:
            break
    return rows


def download(rows: list[dict], out_dir: Path) -> list[dict]:
    """후보를 파일로 내려받습니다. **보고 고르라고 받는 것입니다.**"""
    out_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for index, row in enumerate(rows, 1):
        if not row.get("url"):
            continue
        try:
            data = requests.get(row["url"], headers=HEADERS, timeout=60).content
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}"
            continue
        path = out_dir / f"{index:02d}.jpg"
        path.write_bytes(data)
        row["local_path"] = str(path)
        saved.append(row)
    return saved


def credit(row: dict) -> str:
    """캡션에 넣을 출처 문구. CC BY 계열은 저작자 표시가 의무입니다."""
    who = row.get("creator") or "작자 미상"
    where = {"wikimedia": "위키미디어 공용", "flickr": "플리커"}.get(
        row.get("source", ""), row.get("source", ""))
    return f"사진: {who} / {where} ({row.get('license', '')})".strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--out", default="output/photos")
    parser.add_argument("--all-licenses", action="store_true",
                        help="NC·ND까지 포함(쓰기 전에 조건을 직접 확인하십시오)")
    args = parser.parse_args()

    rows = search(args.query, args.limit, commercial_only=not args.all_licenses)
    if not rows:
        print(f"'{args.query}' 결과가 없습니다. 영어 회사명으로 다시 찾아보십시오 — "
              f"한국어 검색은 대체로 빈손입니다.")
        return 1
    out = Path(args.out) / args.query.replace(" ", "_")
    saved = download(rows, out)
    print(f"'{args.query}' 후보 {len(saved)}장 → {out}\n")
    for row in saved:
        print(f"  {Path(row['local_path']).name}  [{row['license']:<10}] "
              f"{row['title'][:40]:<42} {row['source']}")
        print(f"     {credit(row)}")
    print("\n**받은 파일을 직접 열어 보고 고르십시오.** 검색어만 믿고 붙이지 마십시오 — "
          "`korean bank`가 계곡 사진으로 나온 적이 있습니다.")
    (out / "candidates.json").write_text(
        json.dumps(saved, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
