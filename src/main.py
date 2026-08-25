"""매일 두 번(미국장/한국장) 실행하는 진입점.

사용법:
    python -m src.main --market us
    python -m src.main --market kr

흐름: 시세 수집(fetch_*.py) -> 문구 생성(generate_post.py) -> HTML 렌더링(render_html.py)
      -> output/ 폴더에 저장
"""
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from src import fetch_images, generate_post, render_html, render_text

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def run(market: str) -> Path:
    if market == "us":
        from src import fetch_us as fetcher
    elif market == "kr":
        from src import fetch_kr as fetcher
    else:
        raise ValueError("market은 'us' 또는 'kr' 이어야 합니다.")

    date_str = dt.date.today().isoformat()

    print(f"[1/4] {market} 시세 수집 중...")
    price_data = fetcher.fetch_all()

    print("[2/4] 제목/본문 생성 중 (Claude API)...")
    generated = generate_post.generate(market, date_str, price_data)

    print("[3/4] 인사이트 소재별 사진 검색 중 (Unsplash)...")
    if generated.get("insight_section", {}).get("stories"):
        generated["insight_section"]["stories"] = fetch_images.attach_images(
            generated["insight_section"]["stories"]
        )

    print("[4/4] HTML 렌더링 중...")
    html = render_html.render(market, date_str, price_data, generated)
    text = render_text.render(market, date_str, price_data, generated)

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / f"{market}_{date_str}.html"
    text_path = OUTPUT_DIR / f"{market}_{date_str}.txt"
    out_path.write_text(html, encoding="utf-8")
    text_path.write_text(text, encoding="utf-8")
    print(f"완료: {out_path}")
    print(f"완료(텍스트): {text_path}")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="시황 블로그 초안 자동 생성")
    parser.add_argument("--market", choices=["us", "kr"], required=True)
    args = parser.parse_args()
    run(args.market)
