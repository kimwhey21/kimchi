"""본진 종목 데이터베이스 조각(templates/wp_stock_db.php)을 Code Snippets에 올린다 (2026-09-27).

    python -m scripts.deploy_stock_db          # 바뀌었으면 올리고 캐시를 지운다
    python -m scripts.deploy_stock_db --dry    # 대상 조각과 길이만 본다

올리는 방식은 홈·목록 스타일 조각과 같다(scripts/deploy_list_style.deploy) — 이름으로 찾아 갱신, 코드 오류면 예외.
"""
from __future__ import annotations

import sys

from scripts.deploy_list_style import ROOT, deploy

SOURCE = ROOT / "templates" / "wp_stock_db.php"
NAME = "종목 데이터베이스 /stocks/ + 홈 시장 판"


def main(argv: list[str] | None = None) -> int:
    dry = "--dry" in (argv if argv is not None else sys.argv[1:])
    return deploy(SOURCE, NAME, "templates/wp_stock_db.php가 원본. scripts/deploy_stock_db.py로 올린다.", dry=dry)


if __name__ == "__main__":
    sys.exit(main())
