"""블로그스팟(fermata49.blogspot.com)용 HTML 렌더 (2026-09-25, 사장님 "진행해").

원고 JSON을 네이버와 같은 차례의 블록(`scripts.naver_post.build`)으로 만든 뒤 HTML로 바꾼다. 새로 쓰는 문장은 없다 —
네이버에 올라간 글과 같은 본문이 블로그스팟에도 올라간다(네이버 봇 `Yeti`는 블로거 robots.txt로 막아 두었다).

- 그림은 본진 워드프레스 미디어 라이브러리에 올려(해시로 멱등, `publish_wordpress.upload_featured_image`) 그 주소를 쓴다.
  블로거 API도 편집기 자동화도 파일을 받아 주지 않기 때문이다. 이미 올라간 그림은 다시 올리지 않는다.
- 잡지 표지는 원고의 `featured_photo.url`(Unsplash 원본 주소)을 그대로 쓰고 캡션에 저작자를 적는다.
- 글 끝 고정 줄: 시황·프리뷰는 네이버(이웃 추가), 새 글 알림은 텔레그램, 본문에 나온 코어 종목은 본진 종목 페이지.
  잡지는 퍼플썸 네이버 블로그로 안내하고 페르마타 이름을 쓰지 않는다(2026-09-13 브랜드 규칙).
- 라벨은 시리즈 하나 + 코너/시장 하나 + 종목 이름 몇 개. 라벨 페이지가 곧 허브다.

    python -m scripts.blogger_post <원고.json> [--graphics <그림 폴더>] [--out <결과.json>] [--no-upload]
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
from pathlib import Path

from scripts import naver_post
from src import post_tags, publish_wordpress, stock_pages

NAVER_FERMATA = "https://blog.naver.com/fermata49"
NAVER_MAGAZINE = "https://blog.naver.com/puplesum_"
TELEGRAM = "https://t.me/fermata_kr"
STOCKS_BASE = "https://fermata.it.kr/stocks/"
DISCLAIMER = "이 글은 정보 제공을 위한 것이며 특정 종목의 매수·매도 권유가 아닙니다. 투자 판단과 책임은 독자에게 있습니다."
MAX_STOCK_LINKS = 4
MAX_LABELS = 8


def _esc(text: str) -> str:
    return html.escape(str(text or ""), quote=True)


def _kdate(value) -> str:
    try:
        day = dt.date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return str(value or "")
    return f"{day.year}년 {day.month}월 {day.day}일"


def kicker(doc: dict) -> str:
    """글 맨 위 한 줄. 시황·프리뷰·잡지는 여기서, 기준표 계열은 본진과 같은 머리말(`publish_feature._kicker`)."""
    series = str(doc.get("series") or "")
    market = doc.get("market")
    if market == "kr":
        return f"코스피 마감 시황 · {_kdate(doc.get('date'))}"
    if market == "us":
        return f"미국증시 마감 · {_kdate(doc.get('date'))}"
    if series == "프리뷰":
        return f"오늘 밤 미국장 프리뷰 · {_kdate(doc.get('date'))}"
    if series == "매거진":
        return str(doc.get("group") or "매거진")
    try:
        from src import publish_feature
        text = publish_feature._kicker(doc)
        if text:
            return str(text)
    except Exception:
        pass
    return series


def _unsplash(url: str) -> str:
    if "images.unsplash.com" in url and "?" not in url:
        return url + "?w=1200&q=80"
    return url


def _upload(path: Path) -> str | None:
    """본진 미디어 라이브러리에 올리고 공개 주소를 돌려준다. 설정이 없으면 None — 조용히 넘기지 않고 호출한 쪽이 센다."""
    if not publish_wordpress.is_configured():
        return None
    base = os.environ["WORDPRESS_URL"].rstrip("/")
    auth = (os.environ["WORDPRESS_USERNAME"], os.environ["WORDPRESS_APP_PASSWORD"])
    media_id = publish_wordpress.upload_featured_image(base, auth, {"local_path": str(path)})
    if not media_id:
        return None
    response = publish_wordpress.requests.get(
        f"{base}/wp-json/wp/v2/media/{media_id}", auth=auth, timeout=publish_wordpress.TIMEOUT_SECONDS)
    response.raise_for_status()
    return str(response.json().get("source_url") or "") or None


def stock_links(doc: dict, text: str) -> list[tuple[str, str]]:
    """본문에 이름이 나온 코어 종목 → 본진 종목 페이지(/stocks/<slug>/, 공개). 낱말 경계로 찾는다(post_tags.mentioned)."""
    out: list[tuple[str, str]] = []
    for item in stock_pages.load_config():
        name = item.get("name") or ""
        if name and post_tags.mentioned(name, text):
            out.append((name, f"{STOCKS_BASE}{item['slug']}/"))
        if len(out) >= MAX_STOCK_LINKS:
            break
    return out


def labels(doc: dict, stocks: list[tuple[str, str]]) -> list[str]:
    series = str(doc.get("series") or "")
    market = doc.get("market")
    if market == "kr":
        base = ["시황", "코스피"]
    elif market == "us":
        base = ["시황", "미국증시"]
    elif series == "프리뷰":
        base = ["프리뷰", "미국증시"]
    elif series == "매거진":
        base = ["매거진", str(doc.get("group") or "")]
    elif series == "가이드":
        base = ["가이드"]
    elif series in ("주간 결산", "다음 주 일정"):
        base = ["Weekly", series]
    elif series == "이벤트":
        base = ["Weekly", "이벤트"]
    else:
        base = ["Checkpoint"]
    out: list[str] = []
    for label in base + [name for name, _ in stocks]:
        label = label.strip().replace(",", " ")
        if label and label not in out:
            out.append(label)
    return out[:MAX_LABELS]


def permalink(doc: dict, path: Path) -> str:
    market = doc.get("market")
    if market in ("kr", "us"):
        raw = f"{market}-{doc.get('date')}"
    else:
        raw = str(doc.get("slug") or path.stem)
    raw = re.sub(r"[^a-z0-9-]+", "-", raw.lower()).strip("-")
    return raw[:60].rstrip("-")


def footer(doc: dict, stocks: list[tuple[str, str]]) -> str:
    magazine = doc.get("series") == "매거진"
    lines: list[str] = []
    if magazine:
        lines.append(f'<p>이 잡지는 네이버 블로그 <a href="{NAVER_MAGAZINE}">퍼플썸 매거진</a>에서도 읽을 수 있습니다.</p>')
    else:
        lines.append(
            f'<p><b>매일 아침 코스피 마감 시황과 저녁 미국장 프리뷰</b>는 네이버 블로그에 올라갑니다. '
            f'<a href="{NAVER_FERMATA}">페르마타 네이버 블로그 이웃 추가</a></p>')
        lines.append(f'<p>새 글 알림은 <a href="{TELEGRAM}">텔레그램 채널 @fermata_kr</a>에서 받을 수 있습니다.</p>')
    if stocks:
        lines.append("<p>종목 페이지: " + ", ".join(f'<a href="{url}">{_esc(name)}</a>' for name, url in stocks) + "</p>")
    lines.append(f"<p><small>{_esc(DISCLAIMER)}</small></p>")
    return "<hr>\n" + "\n".join(lines)


def blocks_to_html(blocks: list[tuple[str, str]], resolve) -> tuple[str, list[str]]:
    parts: list[str] = []
    images: list[str] = []
    for kind, value in blocks:
        if kind == "img":
            url, caption = resolve(value)
            if not url:
                continue
            images.append(url)
            cap = f"<figcaption>{_esc(caption)}</figcaption>" if caption else ""
            parts.append(f'<figure><img src="{_esc(url)}" alt="" style="max-width:100%;height:auto">{cap}</figure>')
        elif kind == "h":
            parts.append(f"<h2>{_esc(value)}</h2>")
        elif kind == "q":
            parts.append("<blockquote>" + _esc(value).replace("\n", "<br>") + "</blockquote>")
        else:
            parts.append("<p>" + _esc(value).replace("\n", "<br>") + "</p>")
    return "\n".join(parts), images


def render(path: Path | str, graphics_dir: Path | None = None, upload: bool = True) -> dict:
    path = Path(path)
    doc = json.loads(path.read_text(encoding="utf-8"))
    post = naver_post.build(path, graphics_dir)
    magazine = doc.get("series") == "매거진"
    photo = doc.get("featured_photo") or {}
    unresolved: list[str] = []
    blocks = list(post["blocks"])
    # 표지 사진은 잡지만이 아니라 원고에 `featured_photo.url`이 있는 모든 글이다(2026-09-26, 사장님: "사진이 안 보이는데 …
    # 다양하게 다채롭게 돌려쓰기로 한 거 아니었냐"). 그전에는 Checkpoint·프리뷰·가이드가 전부 같은 남색·베이지 cover 그래픽이었다.
    if photo.get("url"):
        # 네이버 동기화는 표지를 파일로 내려받아 붙이지만 여기서는 원본 주소를 쓴다 — 그림 폴더가 없어도 표지는 붙는다.
        # 남색·베이지 cover 그래픽은 사진 **다음에** 그대로 간다(사장님 2026-09-26: "엄선했던 작품, 함부로 버릴 수 없다").
        if blocks and blocks[0][0] == "img" and "photo-cover" in Path(str(blocks[0][1])).name:
            blocks[0] = ("img", str(photo["url"]))      # 맥이 내려받은 사본 대신 원본 주소
        elif not (blocks and blocks[0][0] == "img" and str(blocks[0][1]).startswith("http")):
            blocks.insert(0, ("img", str(photo["url"])))

    def resolve(src: str) -> tuple[str | None, str | None]:
        src = str(src)
        name = Path(src).name
        if photo.get("url") and (src.startswith("http") or (magazine and "cover" in name)):
            credit = photo.get("credit")
            return _unsplash(str(photo["url"])), (f"사진: {credit}" if credit else None)
        if src.startswith("http"):
            return src, None
        if not upload:
            return src, None
        url = _upload(Path(src))
        if url:
            return url, None
        unresolved.append(src)
        return None, None

    body, images = blocks_to_html(blocks, resolve)
    text = " ".join(str(v) for k, v in blocks if k in ("p", "q", "h"))
    stocks = [] if magazine else stock_links(doc, text)
    page = f"<p><small>{_esc(kicker(doc))}</small></p>\n{body}\n{footer(doc, stocks)}"
    return {
        "title": post["title"],
        "html": page,
        "labels": labels(doc, stocks),
        "slug": permalink(doc, path),
        "date": str(doc.get("date") or ""),
        "series": str(doc.get("series") or doc.get("market") or ""),
        "images": images,
        "unresolved": unresolved,
        "chars": post["chars"],
        "source": str(path),
    }


def main(argv: list[str] | None = None) -> int:
    from dotenv import load_dotenv  # 단독 실행 모듈은 반드시 .env를 읽는다 — 없으면 "업로드 안 함"으로 조용히 끝난다.
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path")
    parser.add_argument("--graphics", help="관문·렌더가 만든 그림 폴더")
    parser.add_argument("--out", help="결과 JSON(title/html/labels/slug)을 쓸 곳")
    parser.add_argument("--no-upload", action="store_true", help="그림을 올리지 않고 로컬 경로를 그대로 둔다(시험용)")
    args = parser.parse_args(argv)
    result = render(args.path, Path(args.graphics) if args.graphics else None, upload=not args.no_upload)
    if args.out:
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{result['title']} | 라벨 {', '.join(result['labels'])} | 그림 {len(result['images'])}장"
          f" | 못 올린 그림 {len(result['unresolved'])}장 | 본문 {result['chars']}자")
    for missing in result["unresolved"]:
        print(f"  못 올림: {missing}", file=sys.stderr)
    return 1 if result["unresolved"] else 0


if __name__ == "__main__":
    sys.exit(main())
