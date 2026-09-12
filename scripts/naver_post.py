"""네이버 블로그(blog.naver.com/fermata49)용 원고 만들기 (2026-09-10, 사용자 결정).

본진(fermata.it.kr) 글을 네이버 독자용으로 다시 짠다 — 전문이 아니라 **요약 + 그림 셋 + 링크**.
이유: 네이버 검색은 네이버 안의 본문만 보고, 전문을 두 곳에 올리면 구글이 한쪽(대개 네이버)만
고르며, 네이버 독자는 결론이 앞에 있는 짧은 글을 읽는다. 그래서
  1. 제목은 검색어 머리 + 본진 제목("코스피 마감 시황 9월 10일: …"),
  2. 첫 문단은 Fermata's Take(판단)를 맨 위로,
  3. 절 다섯 개(그날 이야기·어제 판정·수급·주인공·다음 확인 지점), 1,500자 안팎,
  4. 그림 셋(지수 카드·움직인 종목·주인공 카드; 사진은 저작권 표시가 깨지므로 안 씀),
  5. 맨 아래 본진 링크 한 줄, 태그는 고정 넷 + 그날 것.
올리는 일 자체는 이 맥의 `~/.market-brief-naver/naver_sync.py`가 한다(네이버는 글쓰기 API가 없다).

    python -m scripts.naver_post build editorial/kr_2026-09-10.json --graphics output/gate/kr_2026-09-10 --out post.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import re
import sys
from pathlib import Path

from src import post_tags

ROOT = Path(__file__).resolve().parent.parent
FIXED_TAGS = {"kr": ["코스피", "주식시황", "코스피마감", "페르마타"],
              "us": ["미국증시", "주식시황", "뉴욕증시마감", "페르마타"],
              "feature": ["주식", "투자체크포인트", "페르마타"],
              "주간 결산": ["주간증시", "코스피", "미국증시", "주식시황", "페르마타"],      # 주말 편성(2026-09-12)
              "다음 주 일정": ["다음주증시", "증시일정", "실적발표", "주식시황", "페르마타"],
              "가이드": ["주식", "주식공부", "주식초보", "페르마타"],                    # 유입 편성(2026-09-12)
              "이벤트": ["증시일정", "주식시황", "페르마타"]}
GRAPHIC_PREFERENCE = ["number_cards", "movers_list", "stock_spotlight", "price_history", "flow_compare",
                      "investor_flows", "sector_bars", "rate_compare", "fact_table", "checklist", "calendar_strip"]
_TAG = re.compile(r"<[^>]+>")


def _plain(text: str) -> list[str]:
    return [p.strip() for p in _TAG.sub("", str(text or "")).split("\n") if p.strip()]


_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def _chunks(paragraphs: list[str], max_sentences: int = 3, max_chars: int = 260) -> list[str]:
    """문단을 2~3문장, 260자 안팎으로 자른다 (2026-09-12, 사용자: 모바일에서 문단이 벽처럼 읽힘).
    원문 문단 하나가 5~6줄이 되던 것을 나눈다. 문장 경계는 마침표 뒤 공백."""
    out: list[str] = []
    for para in paragraphs:
        sentences = [x.strip() for x in _SENTENCE.split(para) if x.strip()]
        cur: list[str] = []
        for sent in sentences:
            if cur and (len(cur) >= max_sentences or len(" ".join(cur)) + len(sent) > max_chars):
                out.append(" ".join(cur)); cur = []
            cur.append(sent)
        if cur:
            out.append(" ".join(cur))
    return out


def _kdate(date_str: str) -> str:
    d = dt.date.fromisoformat(date_str)
    return f"{d.month}월 {d.day}일"


def _period(doc: dict) -> str:
    """주말 시리즈의 대상 기간(최상위 `period`) — `9월 7일~11일`. 없으면 글 날짜."""
    period = doc.get("period") or {}
    try:
        start = dt.date.fromisoformat(str(period.get("start")))
        end = dt.date.fromisoformat(str(period.get("end")))
    except (TypeError, ValueError):
        return _kdate(str(doc.get("date")))
    if start.month == end.month:
        return f"{start.month}월 {start.day}일~{end.day}일"
    return f"{start.month}월 {start.day}일~{end.month}월 {end.day}일"


def _pick_sections(doc: dict) -> list[dict]:
    """다섯 절: 첫 절, 어제 판정 절, 수급 절, 주인공(stock_spotlight) 절, 다음 거래일/확인 절."""
    sections = list((doc.get("ko") or {}).get("narrative") or [])
    if not sections:
        return []
    if len(sections) <= 5:
        # 다섯 절 이하면 고를 것이 없다 — 원래 순서 그대로. 첫 주간 결산(2026-09-12)에서 '다음 주에 확인할 것'이
        # "다음|확인" 규칙에 잡혀 두 번째로 올라가 한국장·미국장 절보다 먼저 나갔다.
        return sections
    chosen: list[dict] = [sections[0]]
    def first(pred):
        for s in sections:
            if s not in chosen and pred(s):
                chosen.append(s); return
    first(lambda s: re.search(r"어제|지난 거래일|전날", s.get("heading", "")))
    first(lambda s: (s.get("graphic") or {}).get("kind") in ("investor_flows", "flow_compare") or re.search(r"외국인|기관|수급", s.get("heading", "")))
    first(lambda s: (s.get("graphic") or {}).get("kind") == "stock_spotlight" or re.search(r"주인공|주요 종목", s.get("heading", "")))
    first(lambda s: re.search(r"다음|확인|지켜볼|볼 것", s.get("heading", "")))
    for s in sections:                      # 다섯이 안 되면 순서대로 채운다
        if len(chosen) >= 5:
            break
        if s not in chosen:
            chosen.append(s)
    return chosen[:5]


def _graphics(graphics_dir: Path | None, limit: int = 3) -> list[str]:
    if not graphics_dir or not graphics_dir.exists():
        return []
    files = sorted(glob.glob(str(graphics_dir / "*.png")))
    ranked = []
    for kind in GRAPHIC_PREFERENCE:
        for f in files:
            if kind in Path(f).name and f not in ranked and "cover" not in Path(f).name:
                ranked.append(f)
    return ranked[:limit]


def _cover(graphics_dir: Path | None) -> str | None:
    """표지 그림 — 기준표·프리뷰·주간은 `01-cover.png`, 시황은 `cover_editorial.png`(naver_post cover가 만든다).
    첫 그림이 곧 네이버 목록의 섬네일이라 표지를 맨 앞에 둔다(2026-09-12)."""
    if not graphics_dir or not graphics_dir.exists():
        return None
    for f in sorted(glob.glob(str(graphics_dir / "*.png"))):
        if "cover" in Path(f).name:
            return f
    return None


def build(path: Path, graphics_dir: Path | None = None) -> dict:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    ko = doc.get("ko") or {}
    market = doc.get("market")
    date_str = str(doc.get("date"))
    is_daily = market in ("kr", "us")
    if is_daily:
        prefix = ("코스피 마감 시황 " if market == "kr" else "미국증시 마감 ") + _kdate(date_str)
        url = f"https://fermata.it.kr/editorial-{market}-{date_str}-ko/"
        category = "시황"
        tags = list(FIXED_TAGS[market])
    elif doc.get("series") == "프리뷰":
        # 2026-09-10 사용자: "켜라, 카테고리는 시황에 넣고 날짜 붙여" — 지난 글이 검색에 걸려도 날짜가 보이게
        prefix = "오늘 밤 미국장 프리뷰 " + _kdate(date_str)
        slug = doc.get("slug") or f"us-{date_str}-preview"
        url = f"https://fermata.it.kr/{slug}/"
        category = "시황"
        tags = ["미국증시", "미국장프리뷰", "주식시황", "페르마타"]
    elif doc.get("series") in ("주간 결산", "다음 주 일정"):
        # 주말 편성(2026-09-12): 검색어 머리에 기간을 붙인다 — "주간 증시 결산 9월 7일~11일: …"
        prefix = ("주간 증시 결산 " if doc["series"] == "주간 결산" else "다음 주 증시 일정 ") + _period(doc)
        slug = doc.get("slug") or Path(path).stem.replace("_", "-")
        url = f"https://fermata.it.kr/{slug}/"
        category = "Weekly"      # 네이버에도 같은 이름의 카테고리(2026-09-12)
        tags = list(FIXED_TAGS[doc["series"]])
    elif doc.get("series") == "가이드":
        # 유입 편성(2026-09-12, 사용자 승인 5번): 네이버에도 가이드를 싣는다. 제목이 곧 검색 질문이라 머리를 붙이지 않는다.
        prefix = ""
        slug = doc.get("slug") or Path(path).stem.replace("_", "-")
        url = f"https://fermata.it.kr/{slug}/"
        category = "가이드"
        tags = list(FIXED_TAGS["가이드"])
    elif doc.get("series") == "이벤트":
        prefix = "증시 이벤트 " + _kdate(str(doc.get("event_date") or date_str))
        slug = doc.get("slug") or Path(path).stem.replace("_", "-")
        url = f"https://fermata.it.kr/{slug}/"
        category = "Weekly"
        tags = list(FIXED_TAGS["이벤트"])
    else:
        prefix = "투자 체크포인트"
        slug = doc.get("slug") or Path(path).stem.replace("_", "-", 1).replace("_", "-")
        url = f"https://fermata.it.kr/{slug}/"
        category = "Checkpoint"
        tags = list(FIXED_TAGS["feature"])
    base_title = str(ko.get("title", ""))
    if doc.get("series") == "프리뷰" and base_title.startswith("오늘 밤 미국장"):
        title = f"미국장 프리뷰 {_kdate(date_str)} | {base_title}"
    elif not is_daily and "체크포인트" in base_title:
        title = base_title                                   # 제목에 이미 '체크포인트'가 있으면 머리를 안 붙인다
    elif not prefix:
        title = base_title                                   # 가이드: 제목 그대로
    elif ":" in base_title:
        title = f"{prefix} | {base_title}"                   # 콜론이 겹치지 않게
    else:
        title = f"{prefix}: {base_title}"
    # 블록 종류: img(그림) · h(소제목) · q(인용구 — Fermata's Take) · p(문단, 2~3문장). 표지가 맨 앞(2026-09-12).
    blocks: list[tuple[str, str]] = []
    cover = _cover(graphics_dir)
    if cover:
        blocks.append(("img", cover))
    take = _plain((ko.get("closing") or {}).get("body", ""))
    if take:
        blocks.append(("h", "Fermata's Take"))
        blocks.append(("q", "\n".join(take[:2])))
    pics = _graphics(graphics_dir)
    for i, section in enumerate(_pick_sections(doc)):
        heading = re.sub(r"^\s*\d{1,2}\.\s*", "", str(section.get("heading", "")))
        blocks.append(("h", heading))
        blocks += [("p", p) for p in _chunks(_plain(section.get("body", ""))[:2])]
        if i < len(pics):
            blocks.append(("img", pics[i]))
    check = ((ko.get("closing") or {}).get("check") or {}).get("what")
    if check:
        blocks.append(("h", "다음 확인 지점"))
        blocks.append(("p", str(check)))
    blocks.append(("p", "업종별 등락, 외국인·기관 수급, 금리·환율 표까지 전체 글은 페르마타 블로그에서 볼 수 있습니다."))
    blocks.append(("p", url))
    # 태그는 글에서 뽑는다(src/post_tags.py, 2026-09-12): 고정어 + 종목 이름 + 주제어 + 달. 12개까지.
    tags = post_tags.build_tags(doc)
    return {"title": title, "category": category, "tags": tags, "url": url, "blocks": blocks,
            "source": str(path), "chars": sum(len(b[1]) for b in blocks if b[0] in ("p", "q"))}


def make_cover(path: Path, out: Path) -> Path | None:
    """시황 원고의 대표 이미지(표지)를 만든다 — 발행 워크플로가 만드는 것과 같은 그림(featured_image.create)."""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("market") not in ("kr", "us") or not doc.get("price_data"):
        return None
    from src import featured_image
    out.parent.mkdir(parents=True, exist_ok=True)
    featured_image.create(doc["market"], str(doc["date"]), doc["price_data"], out, doc.get("ko"))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build"); b.add_argument("manuscript", type=Path)
    b.add_argument("--graphics", type=Path); b.add_argument("--out", type=Path)
    c = sub.add_parser("cover"); c.add_argument("manuscript", type=Path); c.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.cmd == "cover":
        made = make_cover(args.manuscript, args.out)
        print(f"cover: {made or '(시황 원고가 아니라 건너뜀)'}")
        return 0
    post = build(args.manuscript, args.graphics)
    text = json.dumps(post, ensure_ascii=False, indent=1)
    if args.out:
        args.out.write_text(text, encoding="utf-8"); print(f"{args.out}: {post['title']} / {post['chars']}자 / 그림 {sum(1 for b in post['blocks'] if b[0]=='img')}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
