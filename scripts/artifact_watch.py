"""루틴 결과물이 마감 시각을 넘겨도 없으면 바로 알린다 (2026-10-06, 감사 F-064·F-112).

    python -m scripts.artifact_watch            # 지금(KST) 마감이 막 지난(30분 안) 결과물 가운데 없는 것을 운영 대화로
    python -m scripts.artifact_watch --dry-run  # 보내지 않고 찍기만

왜: 루틴이 사용량 한도로 끝나거나 관문에 막혀 포기하면 처음 아는 것이 밤 11시 반 증명서였다(잡지는 02:00에 실패하고 21시간 뒤).
증명서와 같은 기대 목록(`daily_proof.expected_artifacts`·`ARTIFACT_DUE`)을 쓰고, 마감 10분 뒤에 Cloudflare가 누른다
(`artifact_watch.yml`). 마감이 30분 안으로 지난 것만 보므로 같은 결과물을 두 번 알리지 않는다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys

from src import daily_proof

WINDOW_MINUTES = 30


def due_now(now: dt.datetime) -> set[str]:
    """마감이 막(30분 안) 지난 결과물 이름."""
    out = set()
    for name, hhmm in daily_proof.ARTIFACT_DUE.items():
        due = dt.datetime.combine(now.date(), dt.time(*map(int, hhmm.split(":"))), tzinfo=now.tzinfo)
        if due <= now < due + dt.timedelta(minutes=WINDOW_MINUTES):
            out.add(name)
    return out


def missing(now: dt.datetime) -> list[str]:
    names = due_now(now)
    if not names:
        return []
    arts = daily_proof.expected_artifacts(now.date(), daily_proof.changed_today(now.date()), now=now)
    return [f"{name} — {where}" for name, ok, where in arts if name in names and not ok]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    now = dt.datetime.now(daily_proof.KST)
    lines = missing(now)
    if not lines:
        print(f"{now:%H:%M} 마감이 막 지난 결과물: {', '.join(sorted(due_now(now))) or '없음'} — 빠진 것 없음")
        return 0
    text = f"{now:%m/%d %H:%M} 마감을 넘겼는데 아직 없습니다:\n" + "\n".join(f"- {l}" for l in lines) + \
        "\n루틴 실행 기록을 보고, 필요하면 다시 돌리십시오(밤 증명서보다 먼저 알리는 것)."
    print(text)
    if args.dry_run:
        return 0
    from src import alert
    return 0 if alert.send(text, "warn") else 1


if __name__ == "__main__":
    sys.exit(main())
