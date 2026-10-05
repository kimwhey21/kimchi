"""맥 예약 작업의 '돌았다' 신호 (2026-10-05).

맥의 launchd 작업(네이버·블로그스팟 동기화, 서치콘솔, 벤치마크 야간 등)은 깃허브에서 보이지 않는다 — 2026-10-02에 13시간
멈춰 있었는데 아무도 몰랐다. 작업이 끝나면 `beat("<이름>")`로 `~/.market-brief-state/beats/<이름>` 파일을 만지고,
`scripts/mac_beats.py`(launchd 23:22)가 그 시각들을 `state/mac_beats.json`으로 커밋한다. 밤 11시 반 증명서(src/daily_proof.py)가
그 파일로 "오늘 돌았어야 할 맥 작업이 돌았나"를 본다. 신호는 "돌았다"이지 "올렸다"가 아니다.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

DIR = Path.home() / ".market-brief-state" / "beats"
KST = dt.timezone(dt.timedelta(hours=9))


def beat(name: str, folder: Path | None = None) -> None:
    """작업이 끝났다고 적는다. 적지 못해도 본 작업을 실패시키지 않는다."""
    try:
        folder = folder or DIR
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).touch()
    except OSError:
        pass


def read_all(folder: Path | None = None) -> dict[str, str]:
    """{이름: 마지막 신호 시각(KST ISO)}."""
    folder = folder or DIR
    if not folder.exists():
        return {}
    return {p.name: dt.datetime.fromtimestamp(p.stat().st_mtime, KST).isoformat(timespec="seconds")
            for p in sorted(folder.iterdir()) if p.is_file()}
