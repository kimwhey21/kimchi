"""시세 수집의 경고 줄과 재료 엔진의 실패 표시를 모아 운영 대화로 보낸다(2026-10-06).

    python -m scripts.collect_warnings <수집 기록 파일> <kr|us>

왜: 수집기의 '[경고]' 줄과 엔진의 '⚠ N건을 받지 못했습니다'·'[error]'는 실행 기록에만 남았다. 9/17 지수 원천 정체가 이렇게 18일
숨었고(감사 F-012), 업종 엔진은 9/10부터 25일 연속 실패했는데 아무도 몰랐다(F-064). 시세 수집 워크플로가 그날 시세 파일이 처음
생긴 실행에서 이것을 부른다(재시도 실행마다 같은 경고를 다시 보내지 않게).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE_MARKS = ("⚠", "[error]", "못했습니다", "실패")


def warnings_from_log(text: str) -> list[str]:
    seen: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("[경고]") and line not in seen:
            seen.append(line)
    return seen


def engine_failures(market: str, root: Path | None = None) -> tuple[str, list[str]]:
    files = sorted(((root or ROOT) / "data").glob(f"engines_{market}_*.txt"))
    if not files:
        return "", []
    lines = [l.strip() for l in files[-1].read_text(encoding="utf-8", errors="replace").splitlines()]
    return files[-1].name, [l for l in lines if any(m in l for m in ENGINE_MARKS)]


def compose(market: str, log_lines: list[str], engine_file: str, engine_lines: list[str]) -> str:
    parts = []
    if log_lines:
        cleaned = [re.sub(r"^\[경고\]\s*", "", l)[:220] for l in log_lines[:15]]   # f-문자열 안에 역슬래시를 넣으면 파이썬 3.11이 못 읽는다
        parts.append(f"{market} 시세 수집 경고 {len(log_lines)}줄:\n" + "\n".join(f"- {c}" for c in cleaned))
    if engine_lines:
        parts.append(f"재료 엔진 실패 {len(engine_lines)}줄({engine_file}):\n" + "\n".join(f"- {l[:220]}" for l in engine_lines[:15]))
    return "\n\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("쓰는 법: python -m scripts.collect_warnings <수집 기록 파일> <kr|us>")
        return 2
    log_path, market = Path(argv[0]), argv[1]
    text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
    if not text:
        print(f"[경고] 수집 기록 {log_path}이 비어 있습니다 — 경고를 모을 수 없습니다")
    engine_file, engine_lines = engine_failures(market)
    message = compose(market, warnings_from_log(text), engine_file, engine_lines)
    if not message:
        print("모을 경고가 없습니다")
        return 0
    print(message)
    from src import alert
    return 0 if alert.send(message, "warn") else 1


if __name__ == "__main__":
    sys.exit(main())
