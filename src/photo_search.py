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

고르는 순서
-----------
1. **그 회사 사진을 먼저 찾습니다.** 위키미디어 공용에 실제 사진이 있습니다
   (`Kookmin Bank Okcheon Branch`, `SK Hynix DDR5`). 있으면 그게 제일 좋습니다.
2. **없거나 마음에 안 들면 한 단계 넓힙니다.** 은행주 글이면 `bank`·`financial
   district`, 반도체 글이면 `microchip`·`semiconductor`. 특정 회사가 아니어도
   업종이 맞으면 표지로 충분합니다. 유니스플래시에 이런 사진은 많습니다.
3. **후보를 한 장에 모아 놓고 고릅니다.** `--sheet`가 여러 검색어를 한 번에 돌려
   번호가 붙은 대조표를 만듭니다.

2026-09-07에 이 순서를 안 지켜 시간을 버렸습니다. 그 회사 사진만 고집하다가
한 장씩 골라 보여 주고 퇴짜맞기를 여섯 번 반복했습니다. **한 장씩 들이밀지
말고 열두 장을 한 번에 펼치십시오.**

사용법
------
    python -m src.photo_search "SK Hynix"
    python -m src.photo_search --sheet 반도체 "SK Hynix" microchip semiconductor
    python -m src.photo_search --sheet 은행 bank "financial district" "bank building"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv
from PIL import Image

# 단독 실행 모듈입니다. 이게 빠지면 UNSPLASH_ACCESS_KEY가 .env에 있어도 안 읽혀
# "키가 없다"는 안내만 찍고 조용히 Openverse로만 도는 실패가 납니다
# (`src/publish_feature.py`가 이미 같은 이유로 겪은 것과 같은 함정).
load_dotenv()

API = "https://api.openverse.org/v1/images/"
UNSPLASH_API = "https://api.unsplash.com/search/photos"

# 위키미디어 원본은 5000px이 넘습니다(KB국민은행 사진이 5328x4000이었습니다).
# 그대로 올리면 워드프레스가 썸네일을 여러 벌 만들고 원본도 그대로 남습니다.
# 서버에 최적화 플러그인을 하나 더 두는 대신 **올리기 전에 여기서 줄입니다.**
MAX_EDGE = 1600
JPEG_QUALITY = 85
HEADERS = {"User-Agent": "market-brief/1.0 (https://fermata.it.kr)"}
TIMEOUT = 30

# 블로그에 쓰기 어려운 라이선스. NC는 상업적 이용 금지, ND는 변형 금지인데
# 워드프레스가 썸네일을 만들며 크기를 바꿉니다.
_BLOCKED = ("nc", "nd")

# 사진이 아닌 것들. 2026-09-06에 `power plant industrial` 검색 결과 12칸 중 2칸이
# **지도 마커 아이콘**이었습니다. 표지에 쓸 수 없는데 자리를 차지해, 한 판에
# 12장을 펼쳐 놓는 이 도구의 효율을 그대로 깎아먹습니다.
_NOT_PHOTOS = ("icon", "logo", "svg", "clipart", "clip art", "map marker",
               "coat of arms", "flag of", "diagram", "chart")
_MIN_EDGE = 500          # 아이콘·썸네일은 대체로 이보다 작습니다


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
        title = (item.get("title") or "").lower()
        url = (item.get("url") or "").lower()
        if any(word in title for word in _NOT_PHOTOS) or url.endswith(".svg"):
            continue
        width, height = item.get("width") or 0, item.get("height") or 0
        if width and height and min(width, height) < _MIN_EDGE:
            continue                       # 표지로 쓰기엔 너무 작습니다
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


def search_unsplash(query: str, limit: int = 8) -> list[dict]:
    """Unsplash 검색. Openverse가 세션에 따라 자주 막혀서(2026-09-06 실측,
    같은 명령 7번 중 6번 타임아웃) 두 번째 출처로 둔다.

    **영어 업종어에만 쓴다.** `docs/feature-style.md`가 이미 경고한 함정은
    한국어 검색·특정 회사명 검색이다(`korean bank`→삼청빌라, `KB금융`→결과
    없음). `tractor`·`semiconductor fab` 같은 영어 업종어는 그 함정과 다르다 —
    Unsplash 자체가 사진작가 중심 스톡 사이트라 화질이 Openverse(플리커 개인
    업로드 위주)보다 훨씬 낫다. 키가 없으면 빈 리스트를 돌려준다(조용히
    건너뛰지 않도록 호출부에서 안내한다).
    """
    access_key = os.environ.get("UNSPLASH_ACCESS_KEY")
    if not access_key:
        return []
    response = requests.get(
        UNSPLASH_API,
        params={"query": query, "per_page": limit, "orientation": "landscape"},
        headers={"Authorization": f"Client-ID {access_key}"},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    rows = []
    for item in response.json().get("results", [])[:limit]:
        rows.append({
            "title": item.get("alt_description") or item.get("description") or "",
            "license": "Unsplash License",
            "creator": (item.get("user") or {}).get("name") or "",
            "source": "unsplash",
            "url": (item.get("urls") or {}).get("regular"),
            "page": (item.get("links") or {}).get("html"),
            "width": item.get("width"), "height": item.get("height"),
        })
    return rows


def _shrink(path: Path) -> tuple[int, int]:
    """긴 변을 MAX_EDGE로 맞춥니다. 이미 작으면 그대로 둡니다."""
    with Image.open(path) as image:
        image = image.convert("RGB")
        width, height = image.size
        if max(width, height) <= MAX_EDGE:
            image.save(path, "JPEG", quality=JPEG_QUALITY, optimize=True)
            return width, height
        scale = MAX_EDGE / max(width, height)
        size = (round(width * scale), round(height * scale))
        image.resize(size, Image.LANCZOS).save(
            path, "JPEG", quality=JPEG_QUALITY, optimize=True)
        return size


def download(rows: list[dict], out_dir: Path) -> list[dict]:
    """후보를 내려받아 **긴 변 1600px로 줄여** 저장합니다.

    보고 고르라고 받는 것이고, 고른 그대로 표지로 올라가므로 여기서 줄여 둡니다.
    """
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
        before = len(data)
        try:
            row["size"] = _shrink(path)
        except Exception as exc:
            row["error"] = f"줄이기 실패 {type(exc).__name__}"
            continue
        row["bytes_before"], row["bytes_after"] = before, path.stat().st_size
        row["local_path"] = str(path)
        saved.append(row)
    return saved


def credit(row: dict) -> str:
    """캡션에 넣을 출처 문구. CC BY 계열은 저작자 표시가 의무입니다."""
    who = row.get("creator") or "작자 미상"
    if row.get("source") == "unsplash":
        # Unsplash는 법적 의무는 아니지만 사진작가 표기를 관례로 남긴다
        # (publish_wordpress.py의 다른 Unsplash 삽입 경로와 같은 문구).
        return f"사진: {who} / Unsplash"
    where = {"wikimedia": "위키미디어 공용", "flickr": "플리커"}.get(
        row.get("source", ""), row.get("source", ""))
    return f"사진: {who} / {where} ({row.get('license', '')})".strip()


def contact_sheet(name: str, queries: list[str], out_dir: Path,
                  per_query: int = 3, source: str = "openverse") -> Path:
    """검색어 여러 개를 한 번에 돌려 번호가 붙은 대조표 한 장을 만듭니다.

    한 장씩 보여 주고 고르게 하면 왕복이 길어집니다. 열두 장을 한 화면에 펼쳐
    번호로 고르게 하는 편이 훨씬 빠릅니다(2026-09-07에 배운 것).

    `source="unsplash"`는 Openverse가 막혔을 때 쓰는 대안이다(2026-09-06 실측).
    **영어 업종어에만 쓴다** — 한국어·특정 회사명 검색은 여전히 금지다.
    """
    from PIL import ImageDraw
    from src.data_graphics import ensure_korean_font, korean_font
    ensure_korean_font()
    searcher = search_unsplash if source == "unsplash" else search

    cands: list[dict] = []
    for query in queries:
        try:
            rows = searcher(query, limit=per_query)
        except Exception:
            continue
        for row in download(rows, out_dir / query.replace(" ", "_")):
            row["query"] = query
            cands.append(row)
    if not cands:
        hint = ("Unsplash 키(UNSPLASH_ACCESS_KEY)를 확인하거나 검색어를 바꿔 보십시오"
                if source == "unsplash" else
                "--source unsplash로 다시 시도하거나 검색어를 영어로 바꿔 보십시오")
        raise SystemExit(f"후보를 하나도 받지 못했습니다. {hint}.")

    cands = cands[:12]
    cols, cell_w, cell_h = 3, 620, 470
    rows_n = (len(cands) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell_w, rows_n * (cell_h + 76)), "#F5F1EA")
    draw = ImageDraw.Draw(sheet)
    for index, row in enumerate(cands):
        x, y = (index % cols) * cell_w, (index // cols) * (cell_h + 76)
        draw.rectangle([x + 8, y + 8, x + cell_w - 8, y + cell_h + 8],
                       fill="#FFFFFF", outline="#E3DED5")
        try:
            image = Image.open(row["local_path"]).convert("RGB")
            image.thumbnail((cell_w - 40, cell_h - 40))
            sheet.paste(image, (x + 20 + (cell_w - 40 - image.width) // 2,
                                y + 20 + (cell_h - 40 - image.height) // 2))
        except Exception:
            pass
        row["label"] = f"{index + 1:02d}"
        draw.text((x + 20, y + cell_h + 18), f"{row['label']}   {row['query'][:24]}",
                  font=korean_font(23, bold=True), fill="#16202C")
        draw.text((x + 20, y + cell_h + 48), f"{row['license']} · {row['title'][:34]}",
                  font=korean_font(15), fill="#6B7785")
    path = out_dir / f"sheet_{name}.png"
    sheet.save(path)
    (out_dir / f"sheet_{name}.json").write_text(
        json.dumps(cands, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"대조표 {len(cands)}장 → {path}\n")
    for row in cands:
        print(f"  {row['label']}  {row['query'][:20]:<22} {row['license']:<12} {row['local_path']}")
    print("\n**번호로 고르십시오.** 한 장씩 들이밀지 마십시오.")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sheet", metavar="이름",
                        help="검색어 여러 개를 한 번에 돌려 대조표 한 장을 만듭니다")
    parser.add_argument("query", nargs="+")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--out", default="output/photos")
    parser.add_argument("--all-licenses", action="store_true",
                        help="NC·ND까지 포함(쓰기 전에 조건을 직접 확인하십시오)")
    parser.add_argument("--source", choices=["openverse", "unsplash"], default="openverse",
                        help="Openverse가 막히면 unsplash로 (영어 업종어만)")
    args = parser.parse_args()

    if args.sheet:
        contact_sheet(args.sheet, args.query, Path(args.out), source=args.source)
        return 0

    query = args.query[0]
    if args.source == "unsplash":
        rows = search_unsplash(query, args.limit)
    else:
        rows = search(query, args.limit, commercial_only=not args.all_licenses)
    if not rows:
        print(f"'{query}' 결과가 없습니다. 영어 업종어로 다시 찾아보거나 "
              f"--source unsplash를 시도해 보십시오 — 한국어 검색은 대체로 빈손입니다.")
        return 1
    out = Path(args.out) / query.replace(" ", "_")
    saved = download(rows, out)
    print(f"'{query}' 후보 {len(saved)}장 → {out}\n")
    for row in saved:
        w, h = row.get("size", (0, 0))
        before_kb = row.get("bytes_before", 0) // 1024
        after_kb = row.get("bytes_after", 0) // 1024
        print(f"  {Path(row['local_path']).name}  [{row['license']:<10}] "
              f"{row['title'][:36]:<38} {w}x{h}  {before_kb}KB→{after_kb}KB")
        print(f"     {credit(row)}")
    print("\n**받은 파일을 직접 열어 보고 고르십시오.** 검색어만 믿고 붙이지 마십시오 — "
          "`korean bank`가 계곡 사진으로 나온 적이 있습니다.")
    (out / "candidates.json").write_text(
        json.dumps(saved, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
