"""저장소 밖에서 손으로만 고치던 작은 조각들(Code Snippets #5~#12)을 원본 파일에서 올린다 (2026-09-28).

    python -m scripts.deploy_snippets          # 바뀐 것만 올리고 캐시를 지운다
    python -m scripts.deploy_snippets --dry    # 대상과 길이만 본다

원본은 templates/wp_snippets/*.php — 관리 화면에서 고치면 다음 배포가 덮어쓴다. 이름으로 찾아 갱신하므로 이름을 바꾸지 말 것.
큰 조각은 따로 있다: #14 scripts/deploy_list_style.py, #16 scripts/deploy_stock_db.py. #13(옛 한국어 주소 301)은 이 맥의
~/.market-brief-google/redirect_sync.py가 만들므로 여기에 두지 않는다. 카페24는 동시 요청에 약해 하나씩 차례로 올린다.
"""
from __future__ import annotations

import sys

from scripts.deploy_list_style import ROOT, deploy

DIR = ROOT / "templates" / "wp_snippets"
# (파일, 조각 이름, 적용 범위, 켬) — 이름은 관리 화면의 이름 그대로여야 한다. 끈 조각도 원본은 남겨 표에서 켜고 끈다
SNIPPETS = [
    ("05_sitemap_no_taxonomies.php", "사이트맵에서 태그·분류 아카이브 빼기", "front-end"),
    ("06_hreflang_ko_en.php", "한국어·영어 시황 hreflang 연결", "front-end", False),   # 2026-09-28 끔: 본진에 한국어 글이 없어 짝이 없다
    ("07_english_post_lang.php", "영어 글은 html lang을 en으로", "front-end", False),   # 2026-09-28 끔: #12가 사이트 전체를 en-US로 둔다
    ("08_ads_txt.php", "ads.txt", "front-end"),
    ("09_adsense_head.php", "애드센스 코드 (head)", "front-end"),
    ("10_hide_korean_blocks_on_english.php", "영어 글에서 한국어 텔레그램 안내·더 많은 게시물 감추기", "front-end", False),   # 2026-09-28 끔: 글 밑 More posts(영어)를 보인다
    ("11_seo_home_english.php", "SEO: 홈·영어 목록 영어 표시, 빈 페이지 검색 제외", "front-end"),
    ("12_visitor_locale_en.php", "영어 사이트: 방문자 화면 언어 en_US·태그라인", "front-end"),
]


def main(argv: list[str] | None = None) -> int:
    dry = "--dry" in (argv if argv is not None else sys.argv[1:])
    for file, name, scope, *on in SNIPPETS:
        print(f"— {file}")
        deploy(DIR / file, name, f"templates/wp_snippets/{file}가 원본. scripts/deploy_snippets.py로 올린다.", dry=dry, scope=scope,
               active=on[0] if on else True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
