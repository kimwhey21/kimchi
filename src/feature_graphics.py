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
             subtitle: str = "", unit: str = "%",
             legend: str = "왼쪽 = 52주 고점 대비 하락률 · 오른쪽 = 애널리스트 평균 목표주가까지의 거리(전망)") -> Path:
    """한 항목의 두 숫자가 반대 방향으로 뻗는 모양을 그립니다.

    캡션(`legend`)과 단위(`unit`)를 반드시 데이터에 맞게 넘기십시오. 2026-09-07에
    이 함수를 수급(만주)에 쓰면서 기본 캡션을 그대로 뒀더니 그림이 "52주 고점 대비
    하락률"이라고 말했습니다 — **그림이 사실과 다른 말을 한 것입니다.**
    `graphic_checks`가 이 조합을 막습니다.
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
        left_text = f"{row['down_pct']:.1f}{unit}"
        right_text = f"+{row['upside_pct']:.1f}{unit}"
        left_width = draw.textlength(left_text, font=korean_font(18, bold=True))
        # 왼쪽 값이 이름 칸을 침범하면 막대 안쪽에 씁니다. 밖에 쓰면 이름이
        # 가려져 어느 줄인지 못 읽습니다(2026-09-07 실측).
        left_x = center - left - 14 - left_width
        left_fill = DOWN
        if left_x < 300:
            # 막대 안으로 옮길 때는 글자색도 바꿔야 합니다. 같은 색으로 쓰면
            # 파란 막대에 파란 글씨가 되어 값이 아예 안 보입니다(실측).
            left_x = center - left + 10
            left_fill = PANEL
        draw.text((left_x, y + 10), left_text, font=korean_font(18, bold=True), fill=left_fill)
        draw.text((center + right + 14, y + 10), right_text,
                  font=korean_font(18, bold=True), fill=UP)
        y += 82

    draw.text((60, height - 64), legend, font=korean_font(15), fill=SUB)
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


def sector_breadth(rows: list[dict], output_path: Path,
                   title: str = "업종별 등락", subtitle: str = "") -> Path:
    """업종 등락률과 **그 안에서 몇 종목이 올랐는지**를 함께 그립니다.

    등락률만 그리면 한 종목이 끌어올린 업종과 열 종목이 함께 오른 업종이 같은
    막대로 보입니다. 실제로 2026-09-04 창업투자는 +3.64%인데 89종목 중 오른 것이
    27개, 내린 것이 28개였습니다 — 업종이 오른 것이 아니라 몇 종목이 튄 것입니다.

    `rows`: [{"name", "change_pct", "up", "down", "stocks"}]

    이름이 `sector_bars`가 아닌 이유: `data_graphics`에 같은 이름이 이미 있고,
    `publish_feature._build_graphics`가 `feature_graphics`를 먼저 봅니다. 같은
    이름을 두면 일간 시황이 부르는 그래픽이 조용히 이 함수로 바뀝니다 —
    인자 규약이 달라 그 자리에서 죽거나, 더 나쁘게는 다른 그림이 나갑니다.
    """
    # 이름 칸을 먼저 확보합니다. 음수 막대가 왼쪽으로 뻗으면서 이름을 덮어
    # "손해보험"이 "손"으로 보였습니다. 마지막 줄 설명이 캡션과 겹치지 않게
    # 아래 여백도 늘립니다.
    height = 250 + len(rows) * 62
    image, draw, y = _canvas(height, title, subtitle)
    center = 520
    span = W - center - 150
    scale = max(abs(r["change_pct"]) for r in rows) or 1.0

    for row in rows:
        color = UP if row["change_pct"] > 0 else DOWN
        draw.text((60, y + 6), row["name"][:12], font=korean_font(19, bold=True), fill=INK)
        length = int(span * abs(row["change_pct"]) / scale)
        if row["change_pct"] >= 0:
            draw.rectangle([center, y + 4, center + length, y + 30], fill=color)
            label_x = center + length + 12
        else:
            draw.rectangle([center - length, y + 4, center, y + 30], fill=color)
            label_x = center + 12
        draw.text((label_x, y + 6), f"{row['change_pct']:+.2f}%",
                  font=korean_font(18, bold=True), fill=color)
        breadth = f"{row['stocks']}종목 중 상승 {row['up']} · 하락 {row['down']}"
        draw.text((60, y + 32), breadth, font=korean_font(14), fill=SUB)
        y += 62

    draw.text((60, height - 62),
              "막대는 업종 등락률, 아래 줄은 그 안에서 오른 종목 수입니다. "
              "한 종목이 끌어올린 업종과 여럿이 오른 업종은 다릅니다.",
              font=korean_font(15), fill=SUB)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return output_path


def rate_compare(rows: list[dict], output_path: Path,
                 title: str = "금리는 어디에 있나", subtitle: str = "") -> Path:
    """금리 몇 개의 현재값과 기간 안 위치를 한 줄씩 그립니다.

    `rows`: [{"name", "value", "low", "high", "unit"}]
    막대가 아니라 **구간 위의 점**으로 그립니다. 금리는 절대값보다 "최근 범위에서
    어디쯤인가"가 이야기가 되기 때문입니다.
    """
    height = 200 + len(rows) * 74
    image, draw, y = _canvas(height, title, subtitle)
    left, right = 330, W - 150

    for row in rows:
        draw.text((60, y + 8), row["name"][:14], font=korean_font(19, bold=True), fill=INK)
        draw.line([left, y + 20, right, y + 20], fill=LINE, width=3)
        span = (row["high"] - row["low"]) or 1.0
        x = left + (right - left) * (row["value"] - row["low"]) / span
        draw.ellipse([x - 8, y + 12, x + 8, y + 28], fill=UP)
        draw.text((left - 4, y + 32), f"{row['low']:g}", font=korean_font(13), fill=SUB)
        draw.text((right - 34, y + 32), f"{row['high']:g}", font=korean_font(13), fill=SUB)
        value = f"{row['value']:g}{row.get('unit', '')}"
        draw.text((x - draw.textlength(value, font=korean_font(17, bold=True)) / 2, y - 8),
                  value, font=korean_font(17, bold=True), fill=INK)
        y += 74

    # 위에 부제를 이미 찍었으면 같은 문구를 아래에 또 쓰지 않습니다.
    if not subtitle:
        draw.text((60, height - 62), "선의 양 끝은 최근 90일 최저·최고입니다.",
                  font=korean_font(15), fill=SUB)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return output_path


def guide_cover(output_path: Path, kicker: str, subject: str,
                up: dict | None = None, down: dict | None = None,
                note: str = "") -> Path:
    """가이드 글 표지. **시황 카드와 다른 어법으로 그립니다.**

    시황의 대표 이미지는 지수 KPI를 상자에 담습니다. 같은 모양을 가이드에 쓰면
    "그날 시황"처럼 읽힙니다 — 가이드는 그날 숫자가 아니라 관계를 다루는 글입니다.
    그래서 숫자 상자 대신 **화살표 두 개로 대비 자체를 그립니다.**

    사진을 쓰지 않는 이유도 적어 둡니다. 2026-09-07에 `bank building seoul`로
    받은 것은 용산 도시 전경이었고 `korean bank`는 계곡에서 밥 먹는 사람들이었습니다.
    `KB금융`·`신한지주`는 결과가 아예 없습니다. 무관한 사진은 없는 것보다 나쁩니다.
    """
    ensure_korean_font()
    width, height = 1200, 630
    image = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(image)
    draw.rectangle([40, 40, width - 40, height - 40], fill=PANEL, outline=LINE)

    def centered(text: str, y: int, font, fill) -> None:
        draw.text(((width - draw.textlength(text, font=font)) / 2, y), text,
                  font=font, fill=fill)

    centered(kicker, 96, korean_font(23, bold=True), SUB)
    centered(subject, 148, korean_font(46, bold=True), INK)

    # 화살표 둘. 위로 가는 것과 아래로 가는 것을 나란히 놓아 대비를 만듭니다.
    base_y, top_y = 430, 268
    for side, item, color in ((-1, up, UP), (1, down, DOWN)):
        if not item:
            continue
        cx = width // 2 + side * 210
        rising = color is UP
        y0, y1 = (base_y, top_y) if rising else (top_y, base_y)
        draw.line([cx, y0, cx, y1], fill=color, width=7)
        head = 18
        tip = y1
        draw.polygon([(cx - head, tip + (head if rising else -head)),
                      (cx + head, tip + (head if rising else -head)),
                      (cx, tip)], fill=color)
        label_font, value_font = korean_font(22), korean_font(40, bold=True)
        draw.text((cx - draw.textlength(item["label"], font=label_font) / 2, base_y + 28),
                  item["label"], font=label_font, fill=SUB)
        draw.text((cx - draw.textlength(item["value"], font=value_font) / 2, base_y + 60),
                  item["value"], font=value_font, fill=color)

    if note:
        centered(note, height - 96, korean_font(20), SUB)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return output_path


# 사진을 못 구했을 때 쓰는 손그림 아이콘 표지입니다(docs/feature-style.md 3절).
# Openverse가 세션에 따라 막힐 때가 있어 만들었습니다. 사진처럼 실제 회사를
# 가리키지 않도록 **브랜드 색(존 디어 초록 등)을 쓰지 않고** 사이트 팔레트
# 회색·잉크색만 씁니다 — 실루엣이라 어느 회사인지 특정되지 않습니다.
_ICON_FILL = "#C9CFD6"
_ICON_LINE = INK


def _tractor_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int) -> None:
    """트랙터 옆모습 실루엣. 큰 뒷바퀴·작은 앞바퀴·캡·보닛만으로 단순화합니다."""
    ground = cy + 96
    # 뒷바퀴(큰 것)
    r_rear = 78
    rear_cx = cx - 90
    draw.ellipse([rear_cx - r_rear, ground - r_rear * 2, rear_cx + r_rear, ground],
                 fill=_ICON_FILL, outline=_ICON_LINE, width=4)
    draw.ellipse([rear_cx - 26, ground - 26 - 70, rear_cx + 26, ground - 70 + 26],
                 fill=BG, outline=_ICON_LINE, width=3)
    # 앞바퀴(작은 것)
    r_front = 42
    front_cx = cx + 130
    draw.ellipse([front_cx - r_front, ground - r_front * 2, front_cx + r_front, ground],
                 fill=_ICON_FILL, outline=_ICON_LINE, width=4)
    # 차체: 캡(뒤, 높음) + 보닛(앞, 낮음)을 한 다각형으로
    body = [
        (cx - 168, ground - 150), (cx - 168, ground - 230), (cx - 60, ground - 230),
        (cx - 30, ground - 150), (cx + 70, ground - 150), (cx + front_cx - cx, ground - 90),
        (cx + front_cx - cx - 10, ground - 60), (cx - 168, ground - 60),
    ]
    draw.polygon(body, fill=_ICON_FILL, outline=_ICON_LINE, width=4)
    # 캡 창문
    draw.rectangle([cx - 148, ground - 210, cx - 82, ground - 165],
                   fill=BG, outline=_ICON_LINE, width=3)
    # 배기관
    draw.rectangle([cx - 190, ground - 270, cx - 168, ground - 220],
                   fill=_ICON_FILL, outline=_ICON_LINE, width=3)


def _wafer_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int) -> None:
    """반도체 웨이퍼 실루엣. 원판 + 다이(die) 격자 + 노치로 단순화합니다."""
    r = 130
    box = [cx - r, cy - r, cx + r, cy + r]
    draw.ellipse(box, fill="#D9CBA8", outline=_ICON_LINE, width=4)
    # 다이 격자(칩 낱개를 나누는 선)
    step = 34
    for x in range(cx - r + step, cx + r, step):
        dy = int((r * r - (x - cx) ** 2) ** 0.5)
        draw.line([x, cy - dy, x, cy + dy], fill="#B7A67E", width=2)
    for y in range(cy - r + step, cy + r, step):
        dx = int((r * r - (y - cy) ** 2) ** 0.5)
        draw.line([cx - dx, y, cx + dx, y], fill="#B7A67E", width=2)
    # 정렬 노치(웨이퍼 특유의 잘린 자국)
    notch = [(cx - 34, cy + r - 6), (cx + 34, cy + r - 6), (cx, cy + r - 34)]
    draw.polygon(notch, fill=BG, outline=_ICON_LINE, width=3)


_ICONS = {"tractor": _tractor_icon, "wafer": _wafer_icon}


def icon_cover(output_path: Path, kicker: str, subject: str, icon: str,
               up: dict | None = None, down: dict | None = None,
               note: str = "") -> Path:
    """사진 대신 쓰는 손그림 아이콘 표지. `icon`은 `tractor` 또는 `wafer`.

    사진을 구하지 못했을 때만 씁니다(우선순위는 여전히 실제 사진 →
    데이터 그래픽 → 이 아이콘 순). `up`/`down`은 `guide_cover`와 같은 모양의
    대비 숫자를 아이콘 아래에 선택적으로 얹습니다.
    """
    draw_icon = _ICONS.get(icon)
    if draw_icon is None:
        raise ValueError(f"알 수 없는 아이콘: {icon} (tractor, wafer만 있습니다)")
    ensure_korean_font()
    width, height = 1200, 630
    image = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(image)
    draw.rectangle([40, 40, width - 40, height - 40], fill=PANEL, outline=LINE)

    def centered(text: str, y: int, font, fill) -> None:
        draw.text(((width - draw.textlength(text, font=font)) / 2, y), text,
                  font=font, fill=fill)

    centered(kicker, 48, korean_font(22, bold=True), SUB)
    draw_icon(draw, width // 2, 280)
    centered(subject, 460, korean_font(38, bold=True), INK)

    if up or down:
        base_y = 512
        quarter = width // 4
        for i, side in enumerate((up, down)):
            if not side:
                continue
            cx_side = quarter + i * (width // 2)
            label_font, value_font = korean_font(20), korean_font(34, bold=True)
            draw.text((cx_side - draw.textlength(side["label"], font=label_font) / 2, base_y),
                      side["label"], font=label_font, fill=SUB)
            draw.text((cx_side - draw.textlength(side["value"], font=value_font) / 2, base_y + 30),
                      side["value"], font=value_font,
                      fill=DOWN if side.get("down") else UP)
    if note:
        centered(note, height - 74, korean_font(18), SUB)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return output_path
