"""스레드(Threads) API 토큰 만들기·갱신 — 사람이 한 번 승인하고, 그 뒤는 자동 (2026-09-12).

    python -m scripts.threads_auth url                 # 1. 승인 주소를 찍는다 → 사용자가 브라우저에서 열어 승인
    python -m scripts.threads_auth code "<돌아온 주소>"  # 2. 돌아온 주소(…?code=…)로 장기 토큰을 만들고 .env·GitHub 시크릿에 넣는다
    python -m scripts.threads_auth refresh             # 3. 장기 토큰 갱신(60일 만료, 24시간 지난 뒤 가능) — 주간 launchd가 부른다
    python -m scripts.threads_auth me                  # 토큰 확인(사용자 id·이름)

.env에 THREADS_APP_ID·THREADS_APP_SECRET(메타 앱 대시보드의 Threads 전용 값)이 있어야 한다. 돌아오는 주소(redirect URI)는
앱 설정에 등록한 것과 글자까지 같아야 한다 — https://fermata.it.kr/threads-callback/ (워드프레스 페이지, 코드만 보여 준다).
문서: developers.facebook.com/docs/threads/get-started (2026-09-12 확인) — 승인 https://threads.com/oauth/authorize,
교환 POST https://graph.threads.com/oauth/access_token, 장기 GET https://graph.threads.net/access_token?grant_type=th_exchange_token,
갱신 GET https://graph.threads.net/refresh_access_token?grant_type=th_refresh_token.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / ".env"
load_dotenv(ENV)

REDIRECT = "https://fermata.it.kr/threads-callback/"
SCOPES = "threads_basic,threads_content_publish"
TIMEOUT = 30


def _env_set(key: str, value: str) -> None:
    text = ENV.read_text(encoding="utf-8") if ENV.exists() else ""
    if re.search(rf"^{key}=", text, re.M):
        text = re.sub(rf"^{key}=.*$", f"{key}={value}", text, flags=re.M)
    else:
        text = text.rstrip("\n") + f"\n{key}={value}\n"
    ENV.write_text(text, encoding="utf-8")
    os.environ[key] = value


def _gh_secret(key: str, value: str) -> None:
    result = subprocess.run(["gh", "secret", "set", key, "--body", value], cwd=ROOT, capture_output=True, text=True)
    print(f"GitHub 시크릿 {key}: {'설정' if result.returncode == 0 else '실패 ' + result.stderr[-200:]}")


def cmd_url() -> None:
    app_id = os.environ["THREADS_APP_ID"]
    query = urllib.parse.urlencode({"client_id": app_id, "redirect_uri": REDIRECT, "scope": SCOPES, "response_type": "code", "state": "fermata"})
    print("브라우저에서 이 주소를 열고 승인하십시오:\n\nhttps://threads.com/oauth/authorize?" + query)
    print(f"\n승인 뒤 {REDIRECT}?code=… 로 돌아옵니다. 그 주소 전체를 복사해 `python -m scripts.threads_auth code \"<주소>\"`로 넘기십시오.")


def cmd_code(returned: str) -> None:
    code = urllib.parse.parse_qs(urllib.parse.urlparse(returned).query).get("code", [""])[0].split("#")[0]
    if not code:
        raise SystemExit("주소에 code=가 없습니다.")
    short = requests.post("https://graph.threads.com/oauth/access_token", timeout=TIMEOUT, data={
        "client_id": os.environ["THREADS_APP_ID"], "client_secret": os.environ["THREADS_APP_SECRET"],
        "code": code, "grant_type": "authorization_code", "redirect_uri": REDIRECT}).json()
    if "access_token" not in short:
        raise SystemExit(f"단기 토큰 실패: {short}")
    long_ = requests.get("https://graph.threads.net/access_token", timeout=TIMEOUT, params={
        "grant_type": "th_exchange_token", "client_secret": os.environ["THREADS_APP_SECRET"], "access_token": short["access_token"]}).json()
    if "access_token" not in long_:
        raise SystemExit(f"장기 토큰 실패: {long_}")
    _env_set("THREADS_ACCESS_TOKEN", long_["access_token"])
    _env_set("THREADS_USER_ID", str(short["user_id"]))
    _gh_secret("THREADS_ACCESS_TOKEN", long_["access_token"])
    _gh_secret("THREADS_USER_ID", str(short["user_id"]))
    print(f"장기 토큰 발급 완료 — 사용자 id {short['user_id']}, 유효 {long_.get('expires_in', 0) // 86400}일")


def cmd_refresh() -> None:
    token = os.environ["THREADS_ACCESS_TOKEN"]
    result = requests.get("https://graph.threads.net/refresh_access_token", timeout=TIMEOUT,
                          params={"grant_type": "th_refresh_token", "access_token": token}).json()
    from src import alert
    if "access_token" not in result:
        alert.send(f"스레드 토큰 갱신 실패: {str(result)[:200]} — 다시 승인이 필요할 수 있습니다(scripts/threads_auth.py url)", "fail")
        raise SystemExit(f"갱신 실패: {result}")
    _env_set("THREADS_ACCESS_TOKEN", result["access_token"])
    _gh_secret("THREADS_ACCESS_TOKEN", result["access_token"])
    print(f"갱신 완료 — 유효 {result.get('expires_in', 0) // 86400}일")
    alert.send(f"스레드 토큰 갱신 완료 — 유효 {result.get('expires_in', 0) // 86400}일", "ok")


def cmd_me() -> None:
    result = requests.get("https://graph.threads.net/v1.0/me", timeout=TIMEOUT,
                          params={"fields": "id,username,name", "access_token": os.environ["THREADS_ACCESS_TOKEN"]}).json()
    print(result)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(__doc__); return 1
    cmd = argv[0]
    if cmd == "url":
        cmd_url()
    elif cmd == "code":
        cmd_code(argv[1])
    elif cmd == "refresh":
        cmd_refresh()
    elif cmd == "me":
        cmd_me()
    else:
        print(__doc__); return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
