"""깃허브 예약의 예비 장치를 Cloudflare Workers에 올린다 (2026-09-29).

    python -m scripts.deploy_backup_cron            # worker.js + jobs.json 올리기, 비밀값·매분 예약 설정
    python -m scripts.deploy_backup_cron --check    # 올라간 상태만 본다(예약·비밀 이름)

열쇠는 이 맥에만 있다 — `~/.cloudflare_workers_token`(Workers 편집), `~/.github_dispatch_token`(kimchi 저장소 Actions 읽기·쓰기만),
텔레그램 값은 `.env`. 어떤 값도 화면에 찍지 않는다. 표를 고치면 `cloudflare/backup_cron/jobs.json`만 고치고 다시 돌린다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import requests
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "cloudflare" / "backup_cron"
NAME = "fermata-backup-cron"
CRON = "* * * * *"
API = "https://api.cloudflare.com/client/v4"


def _secret(path: str) -> str:
    value = Path(path).expanduser().read_text().strip()
    if not value:
        raise SystemExit(f"{path}가 비어 있습니다")
    return value


def _ok(r: requests.Response, what: str) -> dict:
    try:
        body = r.json()
    except ValueError:
        body = {}
    if not r.ok or body.get("success") is False:
        raise SystemExit(f"{what} 실패 ({r.status_code}): {json.dumps(body.get('errors') or r.text[:300], ensure_ascii=False)}")
    return body


def script_source() -> str:
    jobs = json.loads((DIR / "jobs.json").read_text(encoding="utf-8"))
    src = (DIR / "worker.js").read_text(encoding="utf-8")
    if "__JOBS__" not in src:
        raise SystemExit("worker.js에 __JOBS__ 자리가 없습니다")
    return src.replace("__JOBS__", json.dumps(jobs, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {_secret('~/.cloudflare_workers_token')}"
    accounts = _ok(s.get(f"{API}/accounts", timeout=30), "계정 조회")["result"]
    if len(accounts) != 1:
        raise SystemExit(f"계정이 {len(accounts)}개입니다 — 하나여야 합니다")
    base = f"{API}/accounts/{accounts[0]['id']}/workers/scripts/{NAME}"

    if not args.check:
        metadata = {"main_module": "worker.js", "compatibility_date": "2026-09-01", "keep_bindings": ["secret_text"]}
        files = {
            "metadata": (None, json.dumps(metadata), "application/json"),
            "worker.js": ("worker.js", script_source(), "application/javascript+module"),
        }
        _ok(s.put(base, files=files, timeout=60), "스크립트 올리기")
        print("스크립트 올림")
        env = dotenv_values(ROOT / ".env")
        secrets = {
            "GH_TOKEN": _secret("~/.github_dispatch_token"),
            "TELEGRAM_BOT_TOKEN": env.get("TELEGRAM_BOT_TOKEN") or "",
            "TELEGRAM_ADMIN_CHAT_ID": env.get("TELEGRAM_ADMIN_CHAT_ID") or "",
        }
        for key, value in secrets.items():
            if not value:
                raise SystemExit(f"{key} 값이 없습니다")
            _ok(s.put(f"{base}/secrets", json={"name": key, "text": value, "type": "secret_text"}, timeout=30), f"비밀 {key}")
        print(f"비밀값 {len(secrets)}개 넣음")
        _ok(s.put(f"{base}/schedules", json=[{"cron": CRON}], timeout=30), "예약 설정")
        print(f"예약 설정: {CRON}")

    schedules = _ok(s.get(f"{base}/schedules", timeout=30), "예약 조회")["result"]
    names = [x["name"] for x in _ok(s.get(f"{base}/secrets", timeout=30), "비밀 조회")["result"]]
    print("예약:", [x.get("cron") for x in schedules.get("schedules", [])])
    print("비밀 이름:", sorted(names))
    return 0


if __name__ == "__main__":
    sys.exit(main())
