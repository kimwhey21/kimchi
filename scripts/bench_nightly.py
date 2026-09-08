"""벤치마크 야간 작업 — 이 맥의 launchd가 매일 23:10에 돌립니다(kr.it.fermata.benchwatch).

    1. scripts.bench_watch                    재테크농부 새 글 본문 수집 (~/.market-brief-bench/, 커밋 안 함)
    2. compare_to_benchmark.export_stats()    집계표 data/benchmark_stats.json 갱신
    3. 집계값이 실제로 바뀐 날만 그 파일 하나를 커밋·푸시 (클라우드 루틴이 이 표를 읽습니다)

왜 파이썬인가: 처음에는 셸 스크립트였는데 macOS 폴더 보호(TCC) 때문에 launchd가 띄운
/bin/bash는 ~/Downloads의 파일을 읽지 못했습니다("Operation not permitted", 2026-09-08 실측).
python3는 이미 허용돼 있어 그 안에서 git을 부릅니다.

왜 생겼는가: 코퍼스는 유료 콘텐츠라 이 컴퓨터에만 있고, 클라우드 루틴은 집계표만
읽습니다. 2026-09-08까지 집계표는 사람이 손으로 내보낼 때만 갱신됐습니다(마지막 9/7).
사용자 승인(2026-09-08 "진행해")으로 수집 직후 자동 갱신하게 했습니다.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATS = ROOT / "data" / "benchmark_stats.json"
GIT = "/usr/bin/git"


def _run(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(list(args), cwd=ROOT, text=True, capture_output=True, check=check)


def _stats_changed() -> bool:
    """날짜(measured_at)만 바뀐 날은 커밋하지 않습니다 — 집계값·편수가 바뀐 날만."""
    new = json.loads(STATS.read_text(encoding="utf-8"))
    shown = _run(GIT, "show", "HEAD:data/benchmark_stats.json").stdout
    old = json.loads(shown) if shown.strip() else {}
    return (new.get("stats"), new.get("posts")) != (old.get("stats"), old.get("posts"))


def main() -> int:
    os.chdir(ROOT)
    os.environ["PATH"] = "/usr/local/bin:/usr/bin:/bin:" + os.environ.get("PATH", "")
    print(f"=== {dt.datetime.now():%Y-%m-%d %H:%M} bench_nightly 시작 ===", flush=True)

    watch = subprocess.run([sys.executable, "-m", "scripts.bench_watch"], cwd=ROOT)
    rc = watch.returncode
    if rc == 2:
        print("[경고] 벤치마크 로그인 세션이 풀렸습니다 — 'python3 -m scripts.bench_login'으로 다시 "
              "저장하십시오. 집계표는 기존 본문으로 갱신합니다.", flush=True)
    elif rc != 0:
        print(f"[경고] 수집이 종료 코드 {rc}로 끝났습니다. 집계표는 기존 본문으로 갱신합니다.", flush=True)

    from scripts import compare_to_benchmark  # 코퍼스가 있는 이 컴퓨터에서만 돕니다
    compare_to_benchmark.export_stats()
    print(f"집계표 내보냄: {STATS}", flush=True)

    if not _stats_changed():
        _run(GIT, "checkout", "--", "data/benchmark_stats.json")
        print(f"집계값 변화 없음 — 커밋하지 않습니다 ({dt.datetime.now():%H:%M})", flush=True)
        return rc

    _run(GIT, "add", "data/benchmark_stats.json", check=True)
    message = (f"벤치마크 집계 갱신: {dt.date.today():%Y-%m-%d} (야간 자동, scripts/bench_nightly.py)\n\n"
               "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>\n")
    commit = _run(GIT, "commit", "-q", "-F", "-") if False else subprocess.run(
        [GIT, "commit", "-q", "-F", "-"], cwd=ROOT, text=True, input=message, capture_output=True)
    if commit.returncode != 0:
        print(f"[오류] 커밋 실패: {commit.stderr.strip()}", flush=True)
        return 1
    for attempt in range(1, 4):
        pull = _run(GIT, "pull", "-q", "--rebase", "--autostash", "origin", "main")
        push = _run(GIT, "push", "-q", "origin", "HEAD:main") if pull.returncode == 0 else None
        if push is not None and push.returncode == 0:
            print(f"집계표 커밋·푸시 완료 ({dt.datetime.now():%H:%M})", flush=True)
            return rc
        print(f"[안내] push 실패 — 재시도 {attempt}/3: "
              f"{(pull.stderr if pull.returncode else (push.stderr if push else '')).strip()[:200]}", flush=True)
        _run(GIT, "rebase", "--abort")
        time.sleep(20)
    print("[오류] 집계표를 푸시하지 못했습니다. 커밋은 로컬에 남아 있어 다음 날 밤에 다시 올라갑니다.",
          flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
