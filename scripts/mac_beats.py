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
# 게시 직전 검사에서 막힌 원고(2026-10-06) — 증명서가 '안 올라간 것'과 '막아서 안 올린 것'을 가른다
NAVER_BLOCKED = Path.home() / ".market-brief-naver" / "blocked.json"
BLOGGER_BLOCKED = Path.home() / ".market-brief-google" / "blogger_blocked.json"
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


PAUSE = Path.home() / ".market-brief-naver" / "fermata49_pause.json"


def _paused(path: Path = PAUSE) -> str | None:
    """시황 블로그(fermata49) 게시 멈춤이면 멈춘 날 — 증명서가 '멈춤'과 '고장'을 가른다(감사 F-136)."""
    try:
        state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except ValueError:
        return "읽지 못함"
    return str(state.get("since") or state.get("at") or "날짜 모름")[:10] if state.get("paused") else None


def build(now: dt.datetime | None = None, beats: dict[str, str] | None = None,
          naver: Path = NAVER_POSTED, blogger: Path = BLOGGER_POSTED,
          naver_blocked: Path = NAVER_BLOCKED, blogger_blocked: Path = BLOGGER_BLOCKED, pause: Path = PAUSE) -> dict:
    now = now or dt.datetime.now(KST)
    return {"generated_at": now.isoformat(timespec="seconds"),
            "beats": beats if beats is not None else read_all(),
            "posted": {"naver_today": posted_today(naver, now.date()), "blogger_today": posted_today(blogger, now.date()),
                       "naver_blocked_today": posted_today(naver_blocked, now.date()),
                       "blogger_blocked_today": posted_today(blogger_blocked, now.date()),
                       "fermata49_paused": _paused(pause)}}


TOKEN = Path.home() / ".github_dispatch_token"


def worker_presses_today(now: dt.datetime | None = None, token_path: Path = TOKEN) -> int | None:
    """오늘(KST) Cloudflare 워커가 누른 실행(workflow_dispatch) 수. 조회하지 못하면 None.

    워커는 모든 예약을 정시에 누르는 알람인데, 워커가 멈추면 증명서까지 함께 안 돌아 아무도 모른다(2026-10-06, 감사 F-037).
    워커 밖에 있는 이 맥이 하루 한 번 센다 — 평일에 0이면 운영 대화로 알린다."""
    import requests
    now = now or dt.datetime.now(KST)
    since = dt.datetime.combine(now.date(), dt.time(0), KST).astimezone(dt.timezone.utc)
    try:
        token = token_path.read_text(encoding="utf-8").strip()
        r = requests.get("https://api.github.com/repos/kimwhey21/kimchi/actions/runs", timeout=30,
                         headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                         params={"event": "workflow_dispatch", "created": f">={since:%Y-%m-%dT%H:%M:%SZ}", "per_page": 1})
        r.raise_for_status()
        return int(r.json().get("total_count") or 0)
    except (OSError, ValueError, requests.RequestException) as exc:
        print(f"[경고] 워커가 누른 실행 수를 세지 못했습니다: {exc}")
        return None


def check_worker(now: dt.datetime | None = None, count: int | None = -1) -> str | None:
    """평일인데 워커가 오늘 한 번도 누르지 않았으면 경보 문장(주말도 증명서는 매일 누른다)."""
    now = now or dt.datetime.now(KST)
    count = worker_presses_today(now) if count == -1 else count
    if count is None:
        return "맥 신호: Cloudflare 워커가 오늘 누른 실행 수를 세지 못했습니다 — 깃허브 열쇠(~/.github_dispatch_token)를 확인하십시오"
    if count == 0:
        return ("❌ Cloudflare 워커(fermata-backup-cron)가 오늘 한 번도 실행을 누르지 않았습니다 — 워커가 멈췄을 수 있습니다. "
                "`python -m scripts.deploy_backup_cron`으로 다시 올리고 Cloudflare 대시보드의 워커 로그를 보십시오")
    return None


def telegram_alive() -> str | None:
    """운영 텔레그램 봇이 살아 있나 — 막혔으면 이유(감사 F-057: 알림 통로가 텔레그램 하나라 막히면 모든 경보가 사라진다)."""
    from src import alert
    if not alert.configured():
        return "텔레그램 설정(.env)이 없습니다"
    import os
    import requests
    try:
        body = requests.get(f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/getMe", timeout=20).json()
    except (requests.RequestException, ValueError) as exc:
        return f"텔레그램에 닿지 못했습니다({exc.__class__.__name__})"
    return None if body.get("ok") else f"텔레그램 봇이 거절했습니다({str(body.get('description'))[:80]})"


def local_notice(text: str) -> None:
    """맥 화면 알림 — 텔레그램이 막혔을 때의 두 번째 통로."""
    safe = text.replace('"', "'")[:200]
    subprocess.run(["osascript", "-e", f'display notification "{safe}" with title "페르마타 경보"'], capture_output=True)


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([GIT, *args], cwd=ROOT, text=True, capture_output=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    doc = build()
    worker = check_worker()
    doc["worker_ok"] = worker is None
    if worker:
        print(worker)
        if not args.dry_run:
            from src import alert
            if not alert.send(worker, "fail"):
                local_notice(worker)
    dead = telegram_alive()
    if dead:
        print(f"[경고] {dead}")
        if not args.dry_run:
            local_notice(f"{dead} — 오늘 밤 증명서와 모든 경보가 오지 않습니다")
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
