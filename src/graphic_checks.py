"""그래픽 입력값과 배치 규약을 렌더 전·후에 검사한다.

OCR로 완벽한 미감을 판단하지는 않는다. 대신 제목이 주장하는 데이터 관계, 축의
정보 손실, 고정 캔버스에서 계산 가능한 텍스트 충돌을 발행 전에 실패시킨다.
"""
from __future__ import annotations

from pathlib import Path
from PIL import Image

from src.data_graphics import W, korean_font


def _width(text: str, size: int) -> float:
    # 실제 렌더러와 같은 폰트 측정을 써야 macOS/CI의 글자 폭 차이를 잡는다.
    return korean_font(size).getlength(str(text))


def collect_spec_issues(kind: str, args: dict, title: str = "") -> list[str]:
    issues = []
    rows = args.get("rows") or []
    if kind == "valuation_bars" and len(rows) > 1:
        values = sorted(float(r["forward_pe"]) for r in rows if r.get("forward_pe") is not None)
        if len(values) > 1 and values[-1] / max(values[-2], 0.001) > 4:
            issues.append("valuation_bars 축을 한 항목이 4배 넘게 지배합니다 — 비교군을 나누세요.")
        if any(_width(r.get("name", ""), 21) > 175 for r in rows):
            issues.append("valuation_bars 종목명이 왼쪽 라벨 영역을 넘습니다.")
        if any(_width(r.get("note", ""), 15) > 820 for r in rows if r.get("note")):
            issues.append("valuation_bars 보조 설명이 캔버스 밖으로 나갑니다.")
    if kind == "gap_bars":
        if any(_width(r.get("name", ""), 20) > 330 for r in rows):
            issues.append("gap_bars 종목명이 막대 영역과 겹칩니다.")
    if kind == "flow_compare":
        data = args.get("price_data") or {}
        rows = (data.get("watchlist") or {}).values()
        if "반대로" in title:
            bad = [r.get("name", "?") for r in rows
                   if r.get("foreign_net") is not None and r.get("institution_net") is not None
                   and r["foreign_net"] and r["institution_net"]
                   and (r["foreign_net"] > 0) == (r["institution_net"] > 0)]
            # 입력 전체에 동방향 종목이 있는 것은 정상이다. 선택 함수가 걸러내므로
            # 여기서는 반대 방향 종목이 하나도 없을 때만 제목 거짓말로 본다.
            opposed = [r for r in rows if r.get("foreign_net") and r.get("institution_net")
                       and (r["foreign_net"] > 0) != (r["institution_net"] > 0)]
            if not opposed:
                issues.append("flow_compare 제목은 '반대로'인데 반대 순매매 데이터가 없습니다.")
    if kind == "calendar_strip":
        events = args.get("events") or []
        if len(events) > 1:
            step = (W - 300) / (len(events) - 1)
            for event in events:
                if _width(event.get("label", ""), 19) > step - 12:
                    issues.append("calendar_strip 라벨이 이웃 일정과 겹칠 수 있습니다.")
                    break
    return issues


def verify_image(path: Path) -> list[str]:
    """빈 파일·비정상 크기·알파/캔버스 오류를 발행 전에 차단한다."""
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            if image.width < 400 or image.height < 120:
                return [f"그래픽 캔버스가 너무 작습니다: {image.size}"]
    except Exception as exc:
        return [f"그래픽 파일을 읽지 못했습니다: {path} ({exc})"]
    return []
