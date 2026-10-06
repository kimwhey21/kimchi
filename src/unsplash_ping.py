"""원고에 쓴 Unsplash 사진마다 '썼음' 신호를 보낸다 (2026-10-06 결정, 감사 F-186).

    python -m src.unsplash_ping editorial/magazine/2026-10-07_x.json      # 맥의 네이버·블로그스팟 동기화가 글을 올린 뒤 부른다

왜: 루틴이 Unsplash 검색 열쇠(API)로 사진을 고르는데, 열쇠 이용 규칙은 고른 사진마다 그 사진의 download 주소를 한 번 부르라고 한다
(작가에게 다운로드 수가 잡힌다). 지키지 않으면 열쇠가 막혀 잡지 표지·인사이트 사진 검색이 멈출 수 있다. 원고에는 사진 주소 옆에
`unsplash_id`(photo_search 대조표가 찍어 준다)를 적고, 이 모듈이 원고 전체에서 그 번호를 모아 한 번씩만 부른다(보낸 기록은 맥에).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
LEDGER = Path(os.environ.get("UNSPLASH_PING_LEDGER") or (Path.home() / ".market-brief-state" / "unsplash_pinged.json"))


def photo_ids(node) -> list[str]:
    """원고 어디에 있든 `unsplash_id` 값을 모은다(표지·인사이트·절 사진)."""
    found: list[str] = []
    if isinstance(node, dict):
        value = node.get("unsplash_id")
        if isinstance(value, str) and value.strip() and value.strip() not in found:
            found.append(value.strip())
        for child in node.values():
            found += [i for i in photo_ids(child) if i not in found]
    elif isinstance(node, list):
        for child in node:
            found += [i for i in photo_ids(child) if i not in found]
    return found


def missing_ids(node, where: str = "") -> list[str]:
    """Unsplash 사진 주소인데 `unsplash_id`가 없는 자리 — 관문이 막는다(신호를 보낼 수 없다)."""
    out: list[str] = []
    if isinstance(node, dict):
        url = str(node.get("url") or "")
        if "images.unsplash.com" in url and not str(node.get("unsplash_id") or "").strip():
            out.append(f"{where or '원고'}: Unsplash 사진({url[:60]})에 unsplash_id가 없습니다 — photo_search 대조표의 번호를 url 옆에 적으십시오")
        for key, child in node.items():
            out += missing_ids(child, f"{where}.{key}" if where else str(key))
    elif isinstance(node, list):
        for index, child in enumerate(node):
            out += missing_ids(child, f"{where}[{index}]")
    return out


def ping(doc: dict, key: str, *, name: str = "", ledger: Path | None = None, get=None) -> tuple[int, list[str]]:
    """(보낸 수, 실패한 번호). 이미 보낸 (원고, 번호)는 다시 보내지 않는다."""
    ledger = ledger or LEDGER
    get = get or requests.get
    done = json.loads(ledger.read_text(encoding="utf-8")) if ledger.exists() else {}
    sent, failed = 0, []
    for photo in photo_ids(doc):
        mark = f"{name}|{photo}"
        if mark in done:
            continue
        try:
            r = get(f"https://api.unsplash.com/photos/{photo}/download", headers={"Authorization": f"Client-ID {key}"}, timeout=20)
            ok = getattr(r, "status_code", 0) == 200
        except requests.RequestException as exc:
            print(f"[안내] Unsplash 신호 {photo}: {exc}")
            ok = False
        if ok:
            done[mark] = True
            sent += 1
        else:
            failed.append(photo)
    if sent:
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
    return sent, failed


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("쓰는 법: python -m src.unsplash_ping <원고.json>")
        return 2
    load_dotenv(ROOT / ".env")
    key = os.environ.get("UNSPLASH_ACCESS_KEY")
    path = Path(args[0])
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not photo_ids(doc):
        print(f"Unsplash 사진 번호가 없습니다: {path.name}")
        return 0
    if not key:
        print("[경고] UNSPLASH_ACCESS_KEY가 없어 Unsplash 신호를 보내지 못했습니다")
        return 1
    sent, failed = ping(doc, key, name=path.name)
    print(f"Unsplash 신호 {sent}건 보냄" + (f" · 실패 {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
