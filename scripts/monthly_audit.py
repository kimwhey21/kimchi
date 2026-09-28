"""한 달에 한 번 본진 전수 점검 — 모든 주소·모든 화면·메뉴 (2026-09-28).

    python -m scripts.monthly_audit          # 셋을 차례로 돌리고 결과를 운영 텔레그램으로 보낸다

이 맥의 launchd `kr.it.fermata.monthlyaudit`가 매달 1일 03:30에 돌린다(다른 예약이 없는 시각). 매일 점검
(scripts/site_health.py)은 핵심 페이지만 보므로, 종목 페이지 2,800여 개·모든 폭의 화면·버튼은 여기서 본다.
카페24는 동시 요청에 약해 셋을 **차례로** 돌린다. 기록은 ~/.market-brief-google/audit/<날짜>/에 남기고 저장소에는 넣지 않는다.
"""
from __future__ import annotations

import datetime as dt
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

from src import alert

ROOT = Path(__file__).resolve().parent.parent
OUT = Path.home() / ".market-brief-google" / "audit"
STEPS = [("전체 주소(site_crawl)", "scripts.site_crawl"), ("모든 화면·버튼(site_ui_audit)", "scripts.site_ui_audit"),
         ("메뉴 줄(nav_check)", "scripts.nav_check")]


def run_step(module: str, log: Path) -> tuple[int, str]:
    with log.open("w", encoding="utf-8") as f:
        code = subprocess.run([sys.executable, "-m", module], cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, timeout=6 * 3600).returncode
    lines = [l for l in log.read_text(encoding="utf-8").splitlines() if l.strip()]
    return code, (lines[-1] if lines else "(출력 없음)")


def main() -> int:
    load_dotenv(ROOT / ".env")
    day = dt.date.today().isoformat()
    folder = OUT / day
    folder.mkdir(parents=True, exist_ok=True)
    report, failed = [f"본진 월간 전수 점검 {day}"], 0
    for label, module in STEPS:
        code, last = run_step(module, folder / f"{module.split('.')[-1]}.log")
        failed += code != 0
        report.append(f"{'✅' if code == 0 else '❌'} {label}: {last[:200]}")
    report.append(f"기록: {folder}")
    text = "\n".join(report)
    print(text)
    alert.send(text, "fail" if failed else "ok")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
