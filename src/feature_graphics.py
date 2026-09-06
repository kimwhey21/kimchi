"""기준표 글에 들어갈 데이터 그래픽입니다.

왜 따로 두는가
--------------
`data_graphics.py`는 그날 `price_data` 한 벌을 받아 그립니다. 기준표 글은 그날
시세가 아니라 **밸류에이션·일정처럼 시점이 다른 재료**를 씁니다. 같은 모듈에
넣으면 price_data를 안 쓰는 함수가 섞여 인자 규약이 무너지므로 나눴습니다.

색과 폭은 `data_graphics`의 것을 그대로 가져옵니다. 한 글 안에서 그림 두 종류가
서로 다른 팔레트로 보이면 안 됩니다.

여기 그림도 사진이 아니라 **숫자에서 그린 것**이라 틀린 그림이 붙을 위험이
없습니다(`featured_image`·`data_graphics`와 같은 원칙).
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from src.data_graphics import (
    BG, INK, SUB, UP, DOWN, FLAT, PANEL, LINE, W,
    ensure_korean_font, korean_font,
)


def _canvas(height: int, title: str, subtitle: str = "") -> tuple[Image.Image, ImageDraw.ImageDraw, int]:
    ensure_korean_font()
    image = Image.new("RGB", (W, height), BG)
    draw = ImageDraw.Draw(image)
    draw.rectangle([28, 28, W - 28, height - 28], fill=PANEL, outline=LINE)
    draw.text((60, 58), title, font=korean_font(30, bold=True), fill=INK)
    y = 104
    if subtitle:
        draw.text((60, y), subtitle, font=korean_font(17), fill=SUB)
        y += 34
    return image, draw, y + 16


def valuation_bars(rows: list[dict], output_path: Path,
                   title: str = "내년 예상 이익 기준 PER",
                   subtitle: str = "") -> Path:
    """FWD PER을 가로 막대로 견줍니다.

    `rows`: [{"name", "forward_pe", "note"}] — 낮은 값이 왼쪽에 오도록 정렬합니다.
    막대 길이만 보면 "낮을수록 좋다"로 읽히므로 색은 넣지 않고 회색 하나로 씁니다.
    싸다는 판단은 글이 하지, 그림이 하지 않습니다.

    **성격이 다른 종목을 같이 넣지 마십시오.** 장비주(한미반도체 43.59배)를 메모리
    3사와 한 그림에 넣었더니 그 하나가 축을 다 먹어 3.50배와 6.56배의 차이가
    그림에서 사라졌습니다. 비교는 같은 줄에 세울 수 있는 것끼리만 합니다.
    """
    rows = sorted(rows, key=lambda r: r["forward_pe"])
    # 마지막 줄 설명이 아래 캡션과 겹치지 않도록 여유를 둡니다.
    height = 226 + len(rows) * 74
    image, draw, y = _canvas(height, title, subtitle)
    widest = max(r["forward_pe"] for r in rows) or 1.0
    bar_x, bar_max = 250, W - 250 - 150

    for row in rows:
        draw.text((60, y + 10), row["name"], font=korean_font(21, bold=True), fill=INK)
        length = max(8, int(bar_max * row["forward_pe"] / widest))
        draw.rectangle([bar_x, y + 8, bar_x + length, y + 40], fill="#C9CFD6")
        draw.text((bar_x + length + 14, y + 10),
                  f"{row['forward_pe']:.2f}배", font=korean_font(21, bold=True), fill=INK)
        if row.get("note"):
            draw.text((60, y + 42), row["note"], font=korean_font(15), fill=SUB)
        y += 74

    draw.text((60, height - 62),
              "PER이 낮다고 싼 것은 아닙니다. 사이클 업종은 이익이 정점일 때 가장 낮게 보입니다.",
              font=korean_font(15), fill=SUB)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return output_path


def gap_bars(rows: list[dict], output_path: Path,
             title: str = "고점 대비 하락률과 목표주가 상승 여력",
             subtitle: str = "") -> Path:
    """왼쪽으로 하락률, 오른쪽으로 상승 여력을 그립니다.

    한 종목의 두 숫자가 반대 방향으로 뻗어 나가는 모양이라, 이 글이 다루는 긴장
    (많이 빠졌는데 전망은 높다)이 그림 하나로 보입니다.
    """
    height = 236 + len(rows) * 82
    image, draw, y = _canvas(height, title, subtitle)
    center = W // 2
    span = (W // 2) - 190
    scale = max(max(abs(r["down_pct"]) for r in rows),
                max(abs(r["upside_pct"]) for r in rows)) or 1.0

    draw.line([center, y - 6, center, y + len(rows) * 82 - 30], fill=LINE, width=1)
    for row in rows:
        # 이름은 막대와 같은 높이에 둡니다. 아래로 내리면 다음 줄 막대에 붙어
        # 어느 막대의 이름인지 읽히지 않습니다.
        draw.text((60, y + 10), row["name"], font=korean_font(20, bold=True), fill=INK)
        left = int(span * abs(row["down_pct"]) / scale)
        right = int(span * abs(row["upside_pct"]) / scale)
        draw.rectangle([center - left, y + 6, center, y + 38], fill=DOWN)
        draw.rectangle([center, y + 6, center + right, y + 38], fill=UP)
        draw.text((center - left - 96, y + 10), f"{row['down_pct']:.1f}%",
                  font=korean_font(18, bold=True), fill=DOWN)
        draw.text((center + right + 14, y + 10), f"+{row['upside_pct']:.1f}%",
                  font=korean_font(18, bold=True), fill=UP)
        y += 82

    draw.text((60, height - 64),
              "왼쪽 = 52주 고점 대비 하락률 · 오른쪽 = 애널리스트 평균 목표주가까지의 거리(전망)",
              font=korean_font(15), fill=SUB)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return output_path


def calendar_strip(events: list[dict], output_path: Path,
                   title: str = "다음 확인 지점",
                   subtitle: str = "") -> Path:
    """실적 일정을 한 줄로 늘어놓습니다. `events`: [{"date", "label", "note"}]"""
    # 아래 설명줄까지 패널 안에 들어와야 합니다. 300으로 두면 첫 항목 설명이
    # 패널 테두리를 물고 나갑니다.
    height = 344
    image, draw, y = _canvas(height, title, subtitle)
    count = len(events)
    # 양 끝을 150에서 시작합니다. 100이면 첫 항목의 가운데 정렬 문구가 왼쪽으로
    # 잘려 나갑니다.
    margin = 150
    step = (W - margin * 2) // max(1, count - 1) if count > 1 else 0
    line_y = y + 60
    draw.line([margin, line_y, W - margin, line_y], fill=LINE, width=3)

    for i, event in enumerate(events):
        x = margin + i * step if count > 1 else W // 2
        highlight = event.get("highlight")
        radius = 13 if highlight else 9
        draw.ellipse([x - radius, line_y - radius, x + radius, line_y + radius],
                     fill=UP if highlight else FLAT)
        date_font = korean_font(22 if highlight else 19, bold=bool(highlight))
        date_text = event["date"]
        draw.text((x - draw.textlength(date_text, font=date_font) / 2, line_y - 62),
                  date_text, font=date_font, fill=INK if highlight else SUB)
        label_font = korean_font(19 if highlight else 17, bold=bool(highlight))
        label = event["label"]
        draw.text((x - draw.textlength(label, font=label_font) / 2, line_y + 30),
                  label, font=label_font, fill=INK if highlight else SUB)
        if event.get("note"):
            note_font = korean_font(14)
            draw.text((x - draw.textlength(event["note"], font=note_font) / 2, line_y + 58),
                      event["note"], font=note_font, fill=SUB)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return output_path


def checklist(items: list[dict], output_path: Path,
              title: str = "확인할 다섯 가지", subtitle: str = "") -> Path:
    """번호 · 항목 · 왜 보는지를 한 장에 담습니다. `items`: [{"label", "why"}]"""
    height = 180 + len(items) * 96
    image, draw, y = _canvas(height, title, subtitle)
    for i, item in enumerate(items, 1):
        draw.ellipse([60, y + 4, 96, y + 40], fill=INK)
        number = str(i)
        draw.text((78 - draw.textlength(number, font=korean_font(19, bold=True)) / 2, y + 11),
                  number, font=korean_font(19, bold=True), fill=PANEL)
        draw.text((118, y + 6), item["label"], font=korean_font(22, bold=True), fill=INK)
        draw.text((118, y + 42), item["why"], font=korean_font(16), fill=SUB)
        if i < len(items):
            draw.line([118, y + 80, W - 60, y + 80], fill=LINE, width=1)
        y += 96
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return output_path


def cover(output_path: Path, kicker: str, subject: str,
          left: dict | None = None, right: dict | None = None) -> Path:
    """가이드 글의 대표 이미지.

    **제목을 그리지 않습니다.** 2026-09-06에 표지에 제목을 크게 넣었더니 글을
    열었을 때 표지의 제목과 본문 h1이 같은 문장으로 두 번 보였습니다. 저장소는
    이미 같은 이유로 대표 이미지에서 머리글을 뺀 적이 있습니다(2b7cce6
    "대표 이미지에서 머리글을 빼고"). 표지에는 제목이 말하지 않는 것 — 숫자 —
    만 담습니다.

    1200x630으로 그리되 테마가 3:2로 잘라 보여주므로 가운데로 모읍니다. 왼쪽에
    붙였다가 "기준표"가 "표"로 잘린 적이 있습니다.
    """
    ensure_korean_font()
    width, height = 1200, 630
    image = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(image)
    draw.rectangle([40, 40, width - 40, height - 40], fill=PANEL, outline=LINE)

    def centered(text: str, y: int, font, fill) -> None:
        draw.text(((width - draw.textlength(text, font=font)) / 2, y), text,
                  font=font, fill=fill)

    centered(kicker, 120, korean_font(24, bold=True), SUB)
    centered(subject, 186, korean_font(58, bold=True), INK)

    if left or right:
        base = 330
        draw.line([250, base, width - 250, base], fill=LINE, width=1)
        quarter = width // 4
        for i, side in enumerate((left, right)):
            if not side:
                continue
            cx = quarter + i * (width // 2)
            label_font, value_font = korean_font(24), korean_font(62, bold=True)
            draw.text((cx - draw.textlength(side["label"], font=label_font) / 2, base + 56),
                      side["label"], font=label_font, fill=SUB)
            draw.text((cx - draw.textlength(side["value"], font=value_font) / 2, base + 100),
                      side["value"], font=value_font,
                      fill=DOWN if side.get("down") else UP)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return output_path
