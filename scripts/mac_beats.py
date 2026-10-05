"""맥 작업 신호를 저장소에 커밋한다 — launchd `kr.it.fermata.macbeats`, 매일 23:22 KST (2026-10-05).

    python -m scripts.mac_beats            # ~/.market-brief-state/beats/* + 네이버·블로그스팟 오늘 게시 수 → state/mac_beats.json 커밋·푸시
    python -m scripts.mac_beats --dry-run  # 파일만 만들고 커밋하지 않는다

밤 11시 반 증명서(src/daily_proof.py)가 이 파일로 맥 작업이 돌았는지, 네이버·블로그스팟에 오늘 몇 편이 올라갔는지 본다.
파일이 없거나 오늘 것이 아니면 증명서가 "맥의 23:22 작업이 돌지 않았다"고 적는다 — 그래서 이 스크립트 자체가 맥의 심장 박동이다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import time
from pathlib import Path

from src.beat import KST, read_all

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "state" / "mac_beats.json"
NAVER_POSTED = Path.home() / ".market-brief-naver" / "posted.json"
BLOGGER_POSTED = Path.home() / ".market-brief-google" / "blogger_posted.json"
GIT = "/usr/bin/git"


def posted_today(path: Path, day: dt.date) -> int:
    """게시 기록({원고: {"at": ISO, ...}})에서 오늘 올라간 수."""
    if not path.exists():
        return 0
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return 0
    n = 0
    for info in (rows.values() if isinstance(rows, dict) else rows):
        at = str((info or {}).get("at") or "")[:10] if isinstance(info, dict) else ""
        n += at == day.isoformat()
    return n


def build(now: dt.datetime | None = None, beats: dict[str, str] | None = None,
          naver: Path = NAVER_POSTED, blogger: Path = BLOGGER_POSTED) -> dict:
    now = now or dt.datetime.now(KST)
    return {"generated_at": now.isoformat(timespec="seconds"),
            "beats": beats if beats is not None else read_all(),
            "posted": {"naver_today": posted_today(naver, now.date()), "blogger_today": posted_today(blogger, now.date())}}


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([GIT, *args], cwd=ROOT, text=True, capture_output=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    doc = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"맥 신호 {len(doc['beats'])}개, 네이버 오늘 {doc['posted']['naver_today']}편, 블로그스팟 오늘 {doc['posted']['blogger_today']}편")
    if args.dry_run:
        return 0
    _run("add", str(OUT.relative_to(ROOT)))
    commit = subprocess.run([GIT, "commit", "-q", "-F", "-"], cwd=ROOT, text=True, capture_output=True,
                            input=f"맥 작업 신호: {doc['generated_at'][:10]}\n")
    if commit.returncode != 0:
        print(f"[안내] 커밋할 변화가 없거나 실패: {commit.stderr.strip()[:200]}")
        return 0 if "nothing to commit" in (commit.stdout + commit.stderr) else 1
    for attempt in range(1, 4):
        pull = _run("pull", "-q", "--rebase", "--autostash", "origin", "main")
        push = _run("push", "-q", "origin", "HEAD:main") if pull.returncode == 0 else None
        if push is not None and push.returncode == 0:
            print("커밋·푸시 완료")
            return 0
        _run("rebase", "--abort")
        print(f"[안내] push 실패 — 재시도 {attempt}/3")
        time.sleep(20)
    print("[오류] 맥 신호를 푸시하지 못했습니다")
    return 1


if __name__ == "__main__":
    sys.exit(main())
