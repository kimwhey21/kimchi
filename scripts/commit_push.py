"""원고를 main에 올리는 한 명령 (2026-10-05) — 루틴이 네다섯 턴 쓰던 add→commit→push 거부→fetch→log→rebase→push를 한 턴으로.

    python -m scripts.commit_push "시황 원고: 2026-10-06 한국장" editorial/kr_2026-10-06.json [다른 파일...]

하는 일: 지정한 파일만 add → commit → `git pull --rebase origin main` → `git push origin HEAD:main`(세 번까지) → 가지 위에 있으면
upstream을 origin/main으로 맞춘다(샌드박스의 stop hook이 "unpushed commits"라며 claude/* 가지를 또 밀게 하던 것, 10/2 한국장 기록).
결과는 한 줄(커밋 해시)이다. 실패하면 이유 한 줄과 종료 코드 1 — 루틴은 그 줄을 보고에 적고 끝낸다(업스트림 커밋을 들여다보지 않는다).
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RETRIES = 3


def _git(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    out = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True)
    if check and out.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} 실패: {(out.stderr or out.stdout).strip()[:300]}")
    return out


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 2:
        print("쓰는 법: python -m scripts.commit_push \"<커밋 메시지>\" <파일> [<파일>...]")
        return 2
    message, paths = argv[0], argv[1:]
    for p in paths:
        if p.startswith("output/") or p == "output":
            raise SystemExit(f"{p}: output/은 커밋하지 않습니다")
    _git("add", "--", *paths, check=True)
    if _git("diff", "--cached", "--quiet").returncode == 0:
        print("커밋할 변화가 없습니다")
        return 0
    _git("commit", "-q", "-m", message, check=True)
    for attempt in range(1, RETRIES + 1):
        pull = _git("pull", "-q", "--rebase", "origin", "main")
        if pull.returncode != 0:
            _git("rebase", "--abort")
            print(f"[안내] pull --rebase 실패 {attempt}/{RETRIES}: {pull.stderr.strip()[:200]}")
        else:
            push = _git("push", "-q", "origin", "HEAD:main")
            if push.returncode == 0:
                branch = _git("symbolic-ref", "-q", "--short", "HEAD").stdout.strip()
                if branch:
                    _git("branch", "--set-upstream-to=origin/main", branch)   # stop hook이 '안 올린 커밋'으로 보지 않게
                print(f"커밋·푸시 완료 {_git('rev-parse', '--short', 'HEAD').stdout.strip()} — {message}")
                return 0
            print(f"[안내] push 실패 {attempt}/{RETRIES}: {push.stderr.strip()[:200]}")
        time.sleep(5 * attempt)
    print("[오류] main에 올리지 못했습니다 — 이 줄을 보고에 적고 끝내십시오(커밋은 로컬에 남아 있습니다)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
