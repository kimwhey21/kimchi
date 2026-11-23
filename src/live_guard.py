"""시험 중에는 진짜 열쇠로 밖에 보내지 않는다 — 운영 알림·텔레그램 채널·스레드가 보내기 직전에 부른다.

시험이 가짜 응답(mock)을 빠뜨리면, 이 맥에서 바깥 접속을 열고 시험을 돌릴 때 `.env`의 진짜 열쇠로 실제 메시지가 나간다
(시험의 가짜 오류 문구 `ConnectionError('x')`가 운영 대화에 '창고를 비우지 못했습니다'로 도착했다). 시험이 일부러 넣은
가짜 열쇠는 그대로 두어 보내는 길을 시험할 수 있게 하고, `.env`에 적힌 진짜 값과 같은 열쇠만 막는다.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def under_test() -> bool:
    first = sys.argv[0] if sys.argv else ""
    return "unittest" in first or Path(first).name.startswith("test_") or "pytest" in sys.modules


def _real_values(env_file: Path) -> dict:
    try:
        from dotenv import dotenv_values
        return {k: v for k, v in dotenv_values(env_file).items() if v}
    except Exception:  # noqa: BLE001 — 못 읽으면 막을 것도 없다
        return {}


def blocked(*names: str, env_file: Path | None = None) -> bool:
    """시험 중이고, 지금 쓰려는 열쇠가 `.env`의 진짜 값이면 True — 부른 쪽은 보내지 않고 찍기만 한다."""
    if not under_test():
        return False
    real = _real_values(env_file or ENV_FILE)
    hit = [n for n in names if os.environ.get(n) and os.environ.get(n) == real.get(n)]
    if hit:
        print(f"[시험 중 실제 발송 막음] {', '.join(hit)} — 이 시험에 가짜 응답(mock)을 넣으십시오")
    return bool(hit)
