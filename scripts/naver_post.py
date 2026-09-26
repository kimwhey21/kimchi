"""네이버 블로그(blog.naver.com/fermata49)용 원고 만들기 (2026-09-10, 사용자 결정).

**한국어 글은 전부 본진 글을 그대로 옮긴다** — 절·그림·사진·outlook·insight·출처까지 본진
`templates/post.html.j2`와 같은 차례로, 본진 링크 없이. 2026-09-16까지는 시황·프리뷰·Checkpoint만
이랬고 가이드·주간·이벤트는 요약 + 그림 셋 + 본진 링크였는데, 2026-09-22에 사장님이 "네이버 시황 블로그에
워드프레스 링크가 붙는 컨텐츠에 링크를 모두 빼고 본문을 공개하고, 본진에서는 비공개 처리하라 — 네이버는 한글
컨텐츠를 주력으로" 했다. 잡지(두 번째 블로그)는 원래부터 링크가 없다.
이유: 네이버 검색은 네이버 안의 본문만 보고, 전문을 두 곳에 올리면 구글이 한쪽(대개 네이버)만
고르며, 네이버 독자는 결론이 앞에 있는 짧은 글을 읽는다. 그래서
  1. 제목은 본진 제목 그대로(2026-09-17 — 그전엔 검색어·날짜 머리를 붙였다),
  2. 요약본은 Fermata's Take(판단)를 맨 위로, 본문 전문을 싣는 글(시황·프리뷰)은 본진처럼 맨 아래로,
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
TELEGRAM_URL = "https://t.me/fermata_kr"
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



def _media_by_section(doc: dict, graphics_dir: Path | None) -> dict[int, list[str]]:
    """{절 번호(0부터): 그 절에 붙는 그림·사진 파일} — 본진과 같은 자리에 붙이기 위한 표.

    파일 이름 앞의 두 자리는 **만든 쪽이 박아 둔 번호**이고, 뜻이 둘로 갈린다.
      · 시황(`editorial_gate`): 절 번호 그 자체(1부터). `04-price_history.png` → 4번째 절.
      · 기준표·프리뷰(`publish_feature`): 원고 `graphics` 목록에서의 순서(1부터).
        그 항목의 `section` 값이 진짜 절 번호다.
    한쪽 규칙으로 뭉뚱그리면 그림이 남의 절에 붙는다 — 2026-09-15까지 실제로 그랬다
    (국채금리 절 밑에 원익홀딩스 카드가 붙어 있었다).
    """
    if not graphics_dir or not Path(graphics_dir).exists():
        return {}
    specs = doc.get("graphics")
    out: dict[int, list[str]] = {}
    for f in sorted(Path(graphics_dir).glob("*.*")):
        if f.suffix.lower() not in (".png", ".jpg", ".jpeg") or "cover" in f.name:
            continue
        match = re.match(r"(\d{2})-", f.name)
        if not match:
            continue
        number = int(match.group(1))
        if isinstance(specs, list) and specs:
            spec = specs[number - 1] if 0 < number <= len(specs) else None
            if not isinstance(spec, dict) or spec.get("kind") == "cover":
                continue
            section = spec.get("section")
            if section is None:
                continue
            index = int(section)
        else:
            index = number - 1          # 시황: 파일 번호가 곧 절 번호(1부터)
        out.setdefault(index, []).append(str(f))
    return out


def _story_blocks(ko: dict, graphics_dir: Path | None) -> list[tuple[str, str]]:
    """「이날 눈여겨볼 것」(insight_section) — 본진에 실리는 그대로. 2026-09-16 전에는 통째로 빠졌다."""
    section = ko.get("insight_section") or {}
    stories = section.get("stories") or []
    if not stories:
        return []
    photos = sorted(Path(graphics_dir).glob("9*-story*.*")) if graphics_dir and Path(graphics_dir).exists() else []
    blocks: list[tuple[str, str]] = [("h", str(section.get("heading") or "이날 눈여겨볼 것"))]
    for i, story in enumerate(stories):
        heading = re.sub(r"^\s*\d{1,2}\.\s*", "", str(story.get("heading", "")))
        if heading:
            blocks.append(("h", heading))
        if i < len(photos):
            blocks.append(("img", str(photos[i])))
        blocks += [("p", x) for x in _chunks(_plain(story.get("body", "")))]
        rows = [r for r in (story.get("table") or []) if isinstance(r, dict) and r.get("label")]
        # 네이버 본문에는 표 블록이 없다. 본진의 두 칸짜리 표는 `이름 · 값` 한 줄로 옮긴다 —
        # 모양은 못 살려도 숫자가 사라지지는 않는다.
        blocks += [("p", f"{r['label']} · {r.get('value', '')}".strip(" ·")) for r in rows]
    return blocks


def _source_blocks(doc: dict) -> list[tuple[str, str]]:
    """「자료 확인」 — 본진 글 맨 아래 출처 목록. 2026-09-16 전에는 시황에서 통째로 빠졌다."""
    ko = doc.get("ko") or {}
    srcs = [x for x in (ko.get("sources") or doc.get("sources") or [])
            if isinstance(x, dict) and x.get("name")]
    if not srcs:
        return []
    blocks: list[tuple[str, str]] = [("h", "자료 확인")]
    for x in srcs:
        title = str(x.get("title") or "").strip()
        blocks.append(("p", f"{x['name']}, {title}" if title else str(x["name"])))
    return blocks


def _pick_sections(doc: dict) -> list[dict]:
    """다섯 절: 첫 절, 어제 판정 절, 수급 절, 주인공(stock_spotlight) 절, 다음 거래일/확인 절."""
    sections = list((doc.get("ko") or {}).get("narrative") or [])
    if not sections:
        return []
    if len(sections) <= 5 or doc.get("series") in ("가이드", "이벤트"):
        # 가이드·이벤트(2026-09-12)는 답 → 원리 → 예 → 할 것 순서가 글이라 앞 다섯 절을 순서대로 싣는다 —
        # 시황용 고르기 규칙("확인" 절 앞당김)이 첫 가이드에서 6절을 두 번째로 올렸다.
        return sections[:5]
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
    for f in sorted(glob.glob(str(graphics_dir / "*.png")) + glob.glob(str(graphics_dir / "*.jpg"))):
        if "cover" in Path(f).name:   # 잡지 표지는 Unsplash JPG(2026-09-13)
            return f
    return None


def _template_cover(graphics_dir: Path | None, photo: str) -> str | None:
    """사진 표지(`00-photo-cover.jpg`) 뒤에 붙일 cover 그래픽(`01-cover.png`) — 사진이 아닌 cover 파일 중 첫 것."""
    if not graphics_dir or not Path(graphics_dir).exists():
        return None
    for f in sorted(glob.glob(str(graphics_dir / "*.png")) + glob.glob(str(graphics_dir / "*.jpg"))):
        if "cover" in Path(f).name and f != photo and "photo-cover" not in Path(f).name:
            return f
    return None


# 네이버 제목은 **앞자리가 곧 검색 매칭 자리**다(2026-09-13, 사장님 "왜 네이버에서 검색해도 안 나오냐" 조사).
# 실측: 네이버에 올린 18편 중 여덟 편이 "투자 체크포인트:"로 시작했는데 아무도 그 말로 검색하지 않는다.
# 게다가 모바일 검색 결과는 제목을 30자 안팎에서 자르므로, 종목·지수 이름이 뒤로 밀리면 검색어와 겹칠 기회 자체가 없다.
# 그래서 **사람이 실제로 검색하는 말이 앞에 오게 하고, 갈래 이름은 꼬리로 보낸다.**
# 시황·주간 결산의 머리말은 그대로 둔다 — "코스피 마감 시황", "주간 증시 결산"은 실제로 검색되는 말이다.
# 반대로 "투자 체크포인트"·"증시 이벤트"는 우리가 지어낸 이름이라 앞자리를 줄 이유가 없다.


def naver_title(base: str, prefix: str, series: str | None, kdate: str) -> str:
    """네이버 제목은 **본진 제목 그대로다**(2026-09-17, 사장님: "날짜 시황 제목 앞에 쓰는거 삭제").

    2026-09-13부터 9-16까지는 앞에 검색어와 날짜(`코스피 마감 시황 9월 16일: …`,
    `오늘 밤 미국장 프리뷰 9월 10일 | …`)를 붙이고 Checkpoint에는 `| 투자 체크포인트` 꼬리를
    달았다. 상위 블로그 제목 450개를 읽어 보니(2026-09-17) 앞자리는 **훅**이 차지해야 하고,
    검색어는 제목 어딘가에 있으면 된다 — 김무무·경제현미경은 앞 15자를 독자 목소리에 쓰고도
    검색 1·2위다. 그래서 머리도 꼬리도 붙이지 않는다. 인자는 호환을 위해 그대로 받는다.
    """
    return (base or "").strip()


def build(path: Path, graphics_dir: Path | None = None) -> dict:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    ko = doc.get("ko") or {}
    market = doc.get("market")
    date_str = str(doc.get("date"))
    is_daily = market in ("kr", "us")
    if is_daily:
        prefix = ("코스피 마감 시황 " if market == "kr" else "미국증시 마감 ") + _kdate(date_str)
        # 한국어 시황은 본진에 쌍둥이가 없다(2026-09-15, 사용자 결정) — 링크를 걸 곳이 없고,
        # 네이버는 밖으로 나가는 링크가 붙은 글을 좋게 보지 않는다. 이 글이 곧 전문이다.
        url = ""
        category = "시황"
        tags = list(FIXED_TAGS[market])
    elif doc.get("series") == "프리뷰":
        # 2026-09-10 사용자: "켜라, 카테고리는 시황에 넣고 날짜 붙여" — 지난 글이 검색에 걸려도 날짜가 보이게
        prefix = "오늘 밤 미국장 프리뷰 " + _kdate(date_str)
        # 네이버에는 본문 전문을 싣고 본진 링크를 빼 준다(2026-09-15, 사용자 지시).
        # 시황과 같은 처리다 — 네이버는 밖으로 나가는 링크가 붙은 글을 좋게 보지 않고,
        # 요약본 뒤에 링크를 다는 것보다 글 하나로 끝나는 편이 끝까지 읽힌다.
        url = ""
        category = "시황"
        tags = ["미국증시", "미국장프리뷰", "주식시황", "페르마타"]
    elif doc.get("series") in ("주간 결산", "다음 주 일정"):
        # 주말 편성(2026-09-12): 검색어 머리에 기간을 붙인다 — "주간 증시 결산 9월 7일~11일: …"
        prefix = ("주간 증시 결산 " if doc["series"] == "주간 결산" else "다음 주 증시 일정 ") + _period(doc)
        slug = doc.get("slug") or Path(path).stem.replace("_", "-")
        url = ""      # 본진은 비공개(2026-09-22) — 가리킬 공개 주소가 없다
        category = "Weekly"      # 네이버에도 같은 이름의 카테고리(2026-09-12)
        tags = list(FIXED_TAGS[doc["series"]])
    elif doc.get("series") == "가이드":
        # 유입 편성(2026-09-12, 사용자 승인 5번): 네이버에도 가이드를 싣는다. 제목이 곧 검색 질문이라 머리를 붙이지 않는다.
        prefix = ""
        slug = doc.get("slug") or Path(path).stem.replace("_", "-")
        url = ""      # 본진은 비공개(2026-09-22) — 가리킬 공개 주소가 없다
        category = "가이드"
        tags = list(FIXED_TAGS["가이드"])
    elif doc.get("series") == "이벤트":
        prefix = "증시 이벤트 " + _kdate(str(doc.get("event_date") or date_str))
        slug = doc.get("slug") or Path(path).stem.replace("_", "-")
        url = ""      # 본진은 비공개(2026-09-22) — 가리킬 공개 주소가 없다
        category = "Weekly"
        tags = list(FIXED_TAGS["이벤트"])
    elif doc.get("series") == "매거진":
        # 두 번째 네이버 블로그(2026-09-13, 사용자: "jeunkim처럼 다양한 분야의 글을 잡지처럼"). 본진에는 안 가므로 링크가 없고,
        # 카테고리는 코너 이름(시장의 역사·투자 심리·기업과 기술·과학·돈의 상식·만약에)이다. 제목은 그대로 — 코너 이름을 앞에 붙이지 않는다.
        prefix = ""
        slug = doc.get("slug") or Path(path).stem
        url = ""
        category = str(doc.get("group") or "매거진")
        # 고정 태그는 브랜드 이름이다. 두 번째 블로그는 퍼플썸이지 페르마타가 아니다(2026-09-13 저녁, 사용자: "태그도 페르마타가
        # 들어가는 거 같은데") — 잡지 글 어디에도 페르마타가 나가면 안 된다.
        tags = [str(t) for t in (doc.get("tags") or []) if "페르마타" not in str(t) and "fermata" not in str(t).lower()][:10] + ["퍼플썸매거진"]
    else:
        prefix = "투자 체크포인트"
        # Checkpoint도 2026-09-15부터 본문 전문·링크 없음이다(사용자: "체크포인트는 2번"). 본진 글은
        # 같은 날 `private`로 돌렸으므로 가리킬 공개 주소가 없다 — 시황·프리뷰와 같은 처리다.
        url = ""
        category = "Checkpoint"
        tags = list(FIXED_TAGS["feature"])
    base_title = str(ko.get("title", ""))
    title = naver_title(base_title, prefix, doc.get("series"), _kdate(date_str))
    # 블록 종류: img(그림) · h(소제목) · q(인용구 — Fermata's Take) · p(문단, 2~3문장). 표지가 맨 앞(2026-09-12).
    blocks: list[tuple[str, str]] = []
    cover = _cover(graphics_dir)
    if cover:
        blocks.append(("img", cover))
        if "photo-cover" in Path(cover).name:
            # 원고의 Unsplash 사진이 첫 그림일 때도 남색·베이지 cover 그래픽은 그 다음에 그대로 간다(2026-09-26, 사장님:
            # "남색베이지 틀도 우리 그때 당시 엄선했던 작품이다 함부로 버릴수 없다"). 사진과 틀 중 무엇을 남길지는 사장님이 정한다.
            template = _template_cover(graphics_dir, cover)
            if template:
                blocks.append(("img", template))
    take = _plain((ko.get("closing") or {}).get("body", ""))
    magazine = doc.get("series") == "매거진"
    preview = doc.get("series") == "프리뷰"
    # 본문 전문을 싣는 글(시황·프리뷰)은 본진과 같은 차례로 간다 — Fermata's Take가 맨 아래다
    # (2026-09-15, 사용자: "본문 형식으로 바꾸면 페르마타 테이크가 맨 아래로 가는거 아니었니 … 워드프레스 본진에 올라가던 형식말이야").
    # 2026-09-22부터 **한국어 글은 전부 전문**이다(사장님: "네이버는 한글 컨텐츠를 주력으로"). 요약본 + 인용구 Take +
    # 본진 링크 꼴은 가이드·주간·이벤트에서도 없어졌다 — 본진이 비공개라 가리킬 곳이 없고, 요약본은 검색·애드포스트에 불리하다.
    checkpoint = doc.get("series") == "기준표"
    full_body = not magazine
    if take and not magazine and not full_body:   # 잡지에는 Take가 없다(2026-09-13 사용자 결정).
        blocks.append(("h", "Fermata's Take"))
        blocks.append(("q", "\n".join(take[:2])))
    full = (doc.get("naver") or {}).get("narrative") or []
    if full_body:
        # 시황·프리뷰·Checkpoint는 네이버가 유일한 공개처다(2026-09-15). 축약본이 아니라 본문을 그대로
        # 싣는다 — 그전에는 900~2,200자 요약본이 갔고, 본진과 겹치지 않게 매번 다시 쓰는 일이 딸려 있었다.
        full = list(ko.get("narrative") or [])
    if magazine:
        # 참고 블로그(피우스의 책도둑 & 매거진) 실측 꼴은 제목 → 📌 간단 브리핑 → 본문 → 자료 출처인데, 브리핑과 Take는 사용자 결정으로 뺐다.
        # 본문은 `ko.narrative` 그대로가 네이버 본문이다(본진 쌍둥이가 없으니 naver.narrative를 따로 두지 않는다).
        full = list(ko.get("narrative") or [])
        # 간단 브리핑은 싣지 않는다(2026-09-13, 사용자: "잡지블로그에서 간단 브리핑쪽은 빼줘"). 참고 블로그 꼴 중 남기는 것은
        # 표지 → 본문 → 자료 출처뿐이다.
    if full:
        # 절을 다 싣고 문단도 자르지 않는다(길이만 2~3문장으로 나눈다).
        # 그림은 **그 절의 것**을 붙인다(2026-09-16, 사용자: "본진 글을 똑같이 옮기기만 해라").
        # 2026-09-15까지는 종류 선호 순서로 다시 줄을 세워 앞 네 장만 잘라 붙였고, 그래서
        # 국채금리 절 밑에 원익홀딩스 카드가 붙고 나머지 절은 그림 없이 남았다.
        by_section = _media_by_section(doc, graphics_dir) if full_body or magazine else {}
        leftovers = _graphics(graphics_dir, limit=4) if not by_section else []
        for i, section in enumerate(full):
            heading = re.sub(r"^\s*\d{1,2}\.\s*", "", str(section.get("heading", "")))
            blocks.append(("h", heading))
            blocks += [("p", p) for p in _chunks(_plain(section.get("body", "")))]
            for media in by_section.get(i, []):
                blocks.append(("img", media))
            if not by_section and i < len(leftovers):
                blocks.append(("img", leftovers[i]))
    else:
        pics = _graphics(graphics_dir)
    for i, section in enumerate([] if full else _pick_sections(doc)):
        heading = re.sub(r"^\s*\d{1,2}\.\s*", "", str(section.get("heading", "")))
        blocks.append(("h", heading))
        blocks += [("p", p) for p in _chunks(_plain(section.get("body", ""))[:2])]
        if i < len(pics):
            blocks.append(("img", pics[i]))
    if full_body and not magazine:
        # 본진 `templates/post.html.j2`의 차례 그대로 — 본문 뒤에 outlook, 그다음 insight_section.
        # 2026-09-16 전에는 둘 다 네이버에 실린 적이 없었고, 본진을 비공개로 돌린 뒤로는
        # 아무 데도 실리지 않았다(하루 800~1,500자).
        outlook = ko.get("outlook") or {}
        outlook_body = _plain(outlook.get("body", ""))
        if outlook_body:
            blocks.append(("h", str(outlook.get("heading") or "다음 거래일에 확인할 것")))
            blocks += [("p", x) for x in _chunks(outlook_body)]
        blocks += _story_blocks(ko, graphics_dir)
    if take and full_body:
        # 본진 마무리 절과 같은 자리·같은 분량이다(요약본처럼 두 문단만 자르지 않는다).
        blocks.append(("h", "Fermata's Take"))
        blocks += [("p", x) for x in _chunks(take)]
    check = ((ko.get("closing") or {}).get("check") or {}).get("what")
    if check:
        blocks.append(("h", "다음 확인 지점"))
        blocks.append(("p", str(check)))
    if magazine:
        # 잡지에는 Fermata's Take가 없다(2026-09-13, 사용자: "잡지에서는 페르마타 테이크가 없어야 하는데"). 배경을 읽는 글이지
        # 우리 판단을 덧붙이는 글이 아니다. 원고에 closing이 있어도 싣지 않는다.
        srcs = [x for x in (doc.get("sources") or []) if isinstance(x, dict) and x.get("name")]
        if srcs:
            blocks.append(("h", "자료 출처"))
            blocks += [("p", f"{x['name']}, {x['title']}" if x.get("title") else str(x["name"])) for x in srcs]
    else:
        # 본진 글이 비공개라 가리킬 공개 주소가 없다 — "블로그에도 있습니다"는 갈 곳 없는 안내가 된다.
        # 대신 본진 맨 아래의 「자료 확인」을 그대로 옮긴다(2026-09-16). 2026-09-22부터 모든 한국어 글이 이 길이다.
        blocks += _source_blocks(doc)
    if url:   # 지금은 어느 갈래도 본진 링크를 갖지 않는다(2026-09-22). 되돌릴 때를 위해 남긴다.
        blocks.append(("p", url))
    # 텔레그램 안내(2026-09-12~2026-09-22)는 뺐다 — 사장님 "a b 진행해"(2026-09-22). 네이버 검색에 fermata49 글이 0/52인
    # 원인 조사에서, 52편 전부가 같은 문장 + 외부 링크(t.me)로 끝나는 것이 잡지(외부 링크 0, 검색됨)와 다른 점 중 하나였다.
    # 네이버 제한 기준에 "텍스트 링크로 외부 사이트로 유도"가 명시돼 있다. 이미 올라간 글은 건드리지 않는다(재수정 금지).
    # 네이버 글에는 이제 외부 링크가 하나도 없다. TELEGRAM_URL은 알림(notify_*)에서 쓰므로 남긴다.
    # 태그는 글에서 뽑는다(src/post_tags.py, 2026-09-12): 고정어 + 종목 이름 + 주제어 + 달. 12개까지. 잡지는 원고의 tags 그대로.
    if not magazine:
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
