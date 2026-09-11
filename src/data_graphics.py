"""본문에 들어갈 데이터 그래픽을 그날 시세로 만듭니다.

왜 필요한가
-----------
2026-09-04에 벤치마크 채널(재테크농부) 116편·70만 자를 뜯어보니 편당 이미지가
9장이었고, 본문 블록 3개마다 그림이 하나씩 들어갔습니다. 10분짜리 긴 글을 끝까지
읽히게 만드는 장치가 그림 밀도였습니다.

다만 그쪽 그림의 상당수는 시세 위젯 스크린샷입니다. 우리는 같은 것을 **실제
데이터로 그릴 수 있습니다.** 스크린샷은 틀린 값이 박제될 위험이 있지만, 여기서
그리는 그림은 원고에 쓰는 price_data와 같은 출처에서 나오므로 어긋날 수 없습니다.
`featured_image.py`가 대표 이미지에 쓰는 원칙(데이터에서 텍스트를 그린다)을 본문
그래픽으로 넓힌 것입니다.

만드는 것 (2026-09-08에 넷을 더했습니다 — 사용자가 시안 A~D를 고름).
- index_card:   지수·환율 3분할 카드 + 최근 흐름 스파크라인
- sector_bars:  업종별 평균 등락률 가로 막대
- flow_chart:   외국인 순매수·순매도 상위 종목 막대
- price_history: 지수·종목 최근 3개월 종가 흐름(시세 파일 history)
- investor_flows: 외국인·기관·개인 순매수 큰 숫자(조사 값 + 출처)
- number_cards:  지수·환율·유가 숫자 카드 2~4개

사진과 달리 이 그림들은 "틀린 그림이 붙을 위험"이 없어 사람 검수 없이 나가는
경로에서도 안전합니다.
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# 대표 이미지(featured_image)는 영어 전용이라 한글이 두부(□)로 찍힙니다.
# 이 그래픽들은 본문에 들어가고 종목명·업종명이 한글이므로 한글 폰트가 필요합니다.
# GitHub Actions(우분투)에서도 돌아야 하므로 나눔고딕 경로를 함께 둡니다
# (워크플로에서 fonts-nanum 설치).
_KO_REGULAR = (
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
)
_KO_BOLD = (
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
)


def ensure_korean_font() -> str:
    """한글 폰트가 없으면 그림을 만들지 않습니다.

    2026-09-04에 실제로 겪었습니다. 로컬 맥에서는 AppleSDGothicNeo로 잘 나왔는데
    GitHub Actions 러너(우분투)에는 한글 폰트가 없어 종목명이 전부 두부(□□□)로
    찍힌 그림이 사이트에 올라갔습니다. 대표 이미지에서 같은 문제를 한 번 겪고도
    본문 그래픽에서 되풀이했습니다.

    깨진 그림을 내보내는 것보다 그림 없이 나가는 편이 낫습니다. 워크플로에
    fonts-nanum을 설치해 두었고, 그래도 없으면 여기서 멈춥니다.
    """
    for path in _KO_REGULAR:
        if Path(path).exists():
            return path
    raise ValueError(
        "한글 폰트를 찾지 못해 데이터 그래픽을 만들지 않습니다. "
        "우분투라면 fonts-nanum을 설치하세요."
    )


def korean_font(size: int, bold: bool = False):
    """한글이 그려지는 폰트. featured_image도 같은 목록을 씁니다.

    폰트 목록을 두 곳에 두면 한쪽만 고쳐져 한쪽 그림만 두부(□)로 나갑니다.
    실제로 대표 이미지에서 한 번, 본문 그래픽에서 또 한 번 겪은 문제라
    목록을 여기 한 곳에만 둡니다.
    """
    for path in _KO_BOLD if bold else _KO_REGULAR:
        if Path(path).exists():
            try:
                # .ttc는 굵기별 인덱스가 따로 있습니다 (AppleSDGothicNeo: 0 얇음 … 6 굵음)
                index = 6 if (bold and path.endswith(".ttc")) else 2 if path.endswith(".ttc") else 0
                return ImageFont.truetype(path, size=size, index=index)
            except Exception:
                continue
    # 여기까지 왔다면 한글 폰트가 없습니다. 기본 폰트로 그리면 한글이 두부(□)로
    # 찍히는데 **예외가 안 나서 테스트도 통과합니다.** 2026-09-06에 이 구멍을
    # 찾았습니다 — `ensure_korean_font()`를 안 부르고 렌더러를 직접 호출하면
    # 조용히 깨진 그림이 나옵니다. 그래서 여기서 소리를 냅니다.
    print("[경고] 한글 폰트를 찾지 못했습니다. 이 그림의 한글은 □로 찍힙니다. "
          "우분투라면 fonts-nanum을 설치하세요.", file=sys.stderr)
    return ImageFont.load_default(size=size)


def has_korean_font() -> bool:
    """한글 폰트가 있는지 — 없으면 대표 이미지는 영문 표기로 물러섭니다."""
    return any(Path(path).exists() for path in _KO_REGULAR)


def _font(size: int, bold: bool = False):
    return korean_font(size, bold)

# featured_image와 같은 색을 씁니다 — 글 전체가 한 벌로 보이게.
BG = "#F5F1EA"
INK = "#16202C"
SUB = "#6B7785"
UP = "#D4483B"
DOWN = "#2B6CB0"
FLAT = "#8A94A0"
PANEL = "#FFFFFF"
LINE = "#E3DED5"
W = 1000


def _color(change: float) -> str:
    if change > 0.05:
        return UP
    if change < -0.05:
        return DOWN
    return FLAT


def _fmt(value: float, unit: str = "") -> str:
    if abs(value) >= 1000:
        return f"{value:,.0f}{unit}"
    return f"{value:,.2f}{unit}"


def _stock_unit(entry: dict) -> str:
    """종목 주가에 붙일 단위. 한국 종목코드는 여섯 자리 숫자입니다.

    시세 파일에 시장 표시가 따로 없어 종목코드로 봅니다. 단위 없이 "22,500"만
    적으면 달러인지 원인지 읽는 사람이 알 수 없습니다.
    """
    if entry.get("unit"):
        return str(entry["unit"])
    ticker = str(entry.get("ticker", ""))
    return "원" if ticker.isdigit() and len(ticker) == 6 else ""


def _sparkline(draw: ImageDraw.ImageDraw, series, box, color: str) -> None:
    """최근 종가 흐름을 얇은 선으로."""
    x0, y0, x1, y1 = box
    pts = [float(v) for v in (series or []) if v is not None]
    if len(pts) < 2:
        return
    lo, hi = min(pts), max(pts)
    span = (hi - lo) or 1.0
    step = (x1 - x0) / (len(pts) - 1)
    coords = [
        (x0 + i * step, y1 - (v - lo) / span * (y1 - y0))
        for i, v in enumerate(pts)
    ]
    draw.line(coords, fill=color, width=2, joint="curve")
    draw.ellipse(
        [coords[-1][0] - 3, coords[-1][1] - 3, coords[-1][0] + 3, coords[-1][1] + 3],
        fill=color,
    )


def index_card(price_data: dict, output_path: Path, title: str = "오늘의 지수") -> Path:
    """지수·환율 3분할 카드."""
    ensure_korean_font()   # 폰트 없으면 두부(□) 그림 대신 여기서 멈춥니다
    macro = list((price_data.get("macro") or {}).values())[:3]
    h = 250
    img = Image.new("RGB", (W, h), BG)
    d = ImageDraw.Draw(img)
    d.text((32, 26), title, font=_font(21, True), fill=SUB)

    pad, gap = 32, 18
    cw = (W - pad * 2 - gap * (len(macro) - 1)) // max(1, len(macro))
    for i, entry in enumerate(macro):
        x = pad + i * (cw + gap)
        d.rounded_rectangle([x, 66, x + cw, h - 28], 14, fill=PANEL, outline=LINE)
        color = _color(entry["change_pct"])
        d.text((x + 22, 84), entry["name"], font=_font(19), fill=SUB)
        unit = "원" if entry.get("unit") == "원" else ""
        d.text((x + 22, 112), _fmt(entry["price"], unit), font=_font(33, True), fill=INK)
        d.text(
            (x + 22, 158),
            f"{entry['change_pct']:+.2f}%",
            font=_font(22, True),
            fill=color,
        )
        _sparkline(d, entry.get("series"), (x + cw - 150, 100, x + cw - 24, 165), color)
    img.save(output_path, format="PNG", optimize=True)
    return output_path


def sector_bars(price_data: dict, output_path: Path, title: str = "업종별 등락") -> Path:
    """업종 평균 등락률 가로 막대. sector가 붙은 코어 종목만 씁니다."""
    ensure_korean_font()   # 폰트 없으면 두부(□) 그림 대신 여기서 멈춥니다
    groups: dict[str, list[dict]] = {}
    for entry in (price_data.get("watchlist") or {}).values():
        sector = entry.get("sector")
        if sector:
            groups.setdefault(sector, []).append(entry)
    rows = sorted(
        ((s, sum(e["change_pct"] for e in v) / len(v), v) for s, v in groups.items()),
        key=lambda r: r[1],
        reverse=True,
    )
    if not rows:
        # 그릴 게 없으면 없는 경로를 돌려주지 않고 분명히 알립니다.
        # 조용히 넘기면 호출한 쪽이 존재하지 않는 파일을 업로드하려다
        # FileNotFoundError로 끝납니다(2026-09-04에 실제로 그랬습니다).
        raise ValueError("sector_bars: sector가 붙은 종목이 없습니다")

    row_h, top = 46, 78
    h = top + row_h * len(rows) + 30
    img = Image.new("RGB", (W, h), BG)
    d = ImageDraw.Draw(img)
    d.text((32, 26), title, font=_font(21, True), fill=SUB)

    span = max(abs(r[1]) for r in rows) or 1.0
    mid, half = 360, 250      # 오른쪽에 대표 종목 이름이 들어갈 자리를 남깁니다
    d.line([mid, top - 6, mid, h - 20], fill=LINE, width=1)
    for i, (sector, avg, members) in enumerate(rows):
        y = top + i * row_h
        color = _color(avg)
        width = abs(avg) / span * half
        if avg >= 0:
            d.rounded_rectangle([mid, y + 8, mid + width, y + 34], 5, fill=color)
        else:
            d.rounded_rectangle([mid - width, y + 8, mid, y + 34], 5, fill=color)
        d.text((32, y + 12), sector, font=_font(19, True), fill=INK)
        # 값 라벨은 항상 막대 오른쪽 바깥 한 자리에 고정해 서로 겹치지 않게 합니다.
        d.text((mid + half + 16, y + 12), f"{avg:+.2f}%", font=_font(19, True), fill=color)
        lead = max(members, key=lambda e: abs(e["change_pct"]))
        d.text((mid + half + 110, y + 14),
               f"{lead['name']} {lead['change_pct']:+.2f}%", font=_font(16), fill=SUB)
    img.save(output_path, format="PNG", optimize=True)
    return output_path


def flow_chart(price_data: dict, output_path: Path, top_n: int = 5,
               title: str = "외국인 순매매 상·하위") -> Path:
    """외국인 순매수·순매도 상위 종목 막대."""
    ensure_korean_font()   # 폰트 없으면 두부(□) 그림 대신 여기서 멈춥니다
    rows = [
        e for e in (price_data.get("watchlist") or {}).values()
        if e.get("foreign_net") is not None
    ]
    if not rows:
        raise ValueError("flow_chart: 외국인 순매매 데이터가 없습니다")
    rows.sort(key=lambda e: e["foreign_net"], reverse=True)
    picked = rows[:top_n] + rows[-top_n:]

    row_h, top = 42, 78
    h = top + row_h * len(picked) + 30
    img = Image.new("RGB", (W, h), BG)
    d = ImageDraw.Draw(img)
    d.text((32, 26), title, font=_font(21, True), fill=SUB)

    span = max(abs(e["foreign_net"]) for e in picked) or 1
    # 종목명은 왼쪽 고정. 막대가 이름을 덮지 않도록 0축을 충분히 오른쪽에 둡니다.
    mid, half = 430, 240
    d.line([mid, top - 6, mid, h - 20], fill=LINE, width=1)
    for i, e in enumerate(picked):
        y = top + i * row_h
        net = e["foreign_net"]
        color = UP if net >= 0 else DOWN
        width = abs(net) / span * half
        if net >= 0:
            d.rounded_rectangle([mid, y + 7, mid + width, y + 31], 5, fill=color)
        else:
            d.rounded_rectangle([mid - width, y + 7, mid, y + 31], 5, fill=color)
        d.text((32, y + 10), e["name"][:12], font=_font(18, True), fill=INK)
        # 라벨은 캔버스 밖으로 나가지 않도록 오른쪽 끝에 정렬합니다.
        label = f"{net:+,}주"
        d.text((W - 32 - d.textlength(label, font=_font(17)), y + 11), label,
               font=_font(17), fill=color)
    img.save(output_path, format="PNG", optimize=True)
    return output_path


def two_day_compare(price_data: dict, output_path: Path, previous: dict | None = None,
                    tickers: list[str] | None = None,
                    title: str = "어제와 오늘, 같은 종목의 등락") -> Path:
    """같은 종목의 전 거래일 대비 오늘 등락률을 나란히 놓습니다.

    하루 등락률만 보여주면 "그래서 어제와 뭐가 달라졌나"가 안 보입니다.
    업종이 자리를 바꾼 날에는 이 그림 하나가 본문 몇 문단을 대신합니다.
    """
    ensure_korean_font()   # 폰트 없으면 두부(□) 그림 대신 여기서 멈춥니다
    prev = (previous or {}).get("watchlist") or {}
    today = price_data.get("watchlist") or {}
    picks = [t for t in (tickers or []) if t in today and t in prev]
    if not picks:
        raise ValueError("two_day_compare: 비교할 종목이 없습니다")

    row_h, top = 56, 86
    h = top + row_h * len(picks) + 34
    img = Image.new("RGB", (W, h), BG)
    d = ImageDraw.Draw(img)
    d.text((32, 26), title, font=_font(21, True), fill=SUB)
    d.text((470, 56), "어제", font=_font(15), fill=SUB)
    d.text((720, 56), "오늘", font=_font(15), fill=SUB)

    span = max(
        max(abs(prev[t]["change_pct"]), abs(today[t]["change_pct"])) for t in picks
    ) or 1.0
    for i, t in enumerate(picks):
        y = top + i * row_h
        d.text((32, y + 14), today[t]["name"][:12], font=_font(19, True), fill=INK)
        for k, (src, x0) in enumerate(((prev[t], 420), (today[t], 670))):
            change = src["change_pct"]
            color = _color(change)
            width = abs(change) / span * 130
            if change >= 0:
                d.rounded_rectangle([x0, y + 8, x0 + width, y + 30], 4, fill=color)
            else:
                d.rounded_rectangle([x0 - width, y + 8, x0, y + 30], 4, fill=color)
            label = f"{change:+.2f}%"
            d.text((x0 + 140, y + 10), label, font=_font(17, True), fill=color)
        d.text((394, y + 10), "→", font=_font(18), fill=SUB) if False else None
    img.save(output_path, format="PNG", optimize=True)
    return output_path


def _closes(entry: dict) -> list[float]:
    """3개월 종가(history)가 있으면 그것, 없으면 8거래일 series."""
    closes = list(((entry.get("history") or {}).get("close")) or [])
    return closes if len(closes) >= 2 else [float(v) for v in (entry.get("series") or []) if v is not None]


def _pct_over(entry: dict, days: int) -> float | None:
    closes = _closes(entry)
    if len(closes) <= days:
        return None
    return (closes[-1] / closes[-1 - days] - 1) * 100


def _date_ordinal(price_data: dict) -> int:
    try:
        return dt.date.fromisoformat(str(price_data.get("trading_date"))).toordinal()
    except (TypeError, ValueError):
        return 0


MOVERS_STYLES = ("bars", "tiles", "table")


def _movers_style(picked: list[dict], price_data: dict) -> str:
    """상황에 맞게 고른다(2026-09-09, 사용자: "다채롭게 상황에 맞게 번갈아").
    오르고 내린 종목이 섞인 날은 막대(방향이 보인다), 한쪽으로만 움직인 날은 타일과 표를
    날짜로 번갈아 쓴다. 같은 날 다시 그리면 같은 그림이 나온다."""
    ups = sum(1 for e in picked if float(e["change_pct"]) > 0)
    if 0 < ups < len(picked):
        return "bars"
    return "tiles" if _date_ordinal(price_data) % 2 == 0 else "table"


def _pct_week(entry: dict, trading_date: str) -> float | None:
    """달력 기준 주간 등락 — 그 주 월요일 전 마지막 종가 대비 마지막 종가.

    `_pct_over(entry, 5)`는 '5거래일 전' 대비라 휴장이 낀 주(2026-09-07 노동절 → 미국장 4거래일)에는
    전주 목요일과 비교하게 된다. 첫 주간 결산(2026-09-12)에서 루틴이 이것을 알아채고 미국 지수는
    숫자를 손으로 적었다. 주간은 날짜로 센다 — `scripts/weekly_stats`와 같은 정의다.
    """
    history = entry.get("history") or {}
    dates = [str(d) for d in (history.get("dates") or [])]
    closes = history.get("close") or []
    if len(dates) != len(closes) or not dates:
        return None
    try:
        day = dt.date.fromisoformat(str(trading_date))
    except (TypeError, ValueError):
        return None
    monday = (day - dt.timedelta(days=day.weekday())).isoformat()
    before = [float(c) for d, c in zip(dates, closes) if d < monday and c is not None]
    inside = [float(c) for d, c in zip(dates, closes) if monday <= d <= day.isoformat() and c is not None]
    if not before or not inside or not before[-1]:
        return None
    return (inside[-1] / before[-1] - 1) * 100


def _period_pct(entry: dict, price_data: dict, period_days: int | None, period: str | None) -> float | None:
    if period == "week":
        return _pct_week(entry, str(price_data.get("trading_date") or ""))
    if period_days:
        return _pct_over(entry, int(period_days))
    return None


def _period_rows(price_data: dict, period_days: int | None = None, period: str | None = None) -> list[dict]:
    """종목마다 `change_pct`를 하루가 아니라 기간 등락으로 바꾼 사본 — `period="week"`(달력 주간, 권장)
    또는 `period_days`(N거래일).

    주간 결산(2026-09-12)이 쓴다 — 시세 파일의 3개월 이력(`history`)에서 계산하므로 숫자는
    여전히 전부 시세에서 나온다. 이력이 짧은 종목(그날 편입된 동적 종목 등)은 뺀다.
    """
    rows = []
    for entry in (price_data.get("watchlist") or {}).values():
        pct = _period_pct(entry, price_data, period_days, period)
        if pct is None:
            continue
        copy = dict(entry)
        copy["change_pct"] = round(pct, 2)
        rows.append(copy)
    return rows


def movers_list(price_data: dict, output_path: Path, top_n: int = 6,
                title: str = "오늘 많이 움직인 종목", style: str | None = None,
                period_days: int | None = None, period: str | None = None) -> Path:
    """등락 폭 상위 종목 목록 — 세 가지 모양(막대·타일·표) 중 하나.

    2026-09-09 사용자가 작은 추이선이 붙은 옛 목록을 "마음에 안 든다"고 해 네 안을 그려
    보였고, 이 셋을 골랐다("상황에 맞게 능동적으로 번갈아 쓰면 좋겠다"). `style`을 주면
    그 모양, 주지 않으면 `_movers_style`이 그날 상황으로 고른다. 그리는 것은 전부 시세
    파일에서 나오므로 틀린 그림이 붙을 수 없다.

    `period="week"`(달력 주간 — 휴장 주에도 전주 마지막 종가 대비, 권장)나 `period_days`(N거래일)를
    주면 하루 등락 대신 그 기간 등락으로 고르고 그린다. 이때 표 모양은 열 이름("오늘")이 거짓말이
    되므로 쓰지 않는다 — 막대나 타일로 간다.
    """
    ensure_korean_font()   # 폰트 없으면 두부(□) 그림 대신 여기서 멈춥니다
    if period == "week" or period_days:
        rows = _period_rows(price_data, period_days, period)
        if title == "오늘 많이 움직인 종목":
            title = ("이번 주 많이 움직인 종목" if period == "week" or int(period_days or 0) == 5
                     else f"{period_days}거래일 등락 상위")
    else:
        rows = [e for e in (price_data.get("watchlist") or {}).values() if e.get("change_pct") is not None]
    if not rows:
        raise ValueError("movers_list: 등락률이 있는 종목이 없습니다")
    rows.sort(key=lambda e: abs(float(e["change_pct"])), reverse=True)
    picked = sorted(rows[:top_n], key=lambda e: float(e["change_pct"]), reverse=True)
    if style and style not in MOVERS_STYLES:
        # 틀린 이름으로 발행이 죽거나 그림이 빠지지 않게 — 상황으로 고른 모양으로 그리고 알린다
        # (2026-09-09, 사용자: "루틴이 잘못된 그림을 그리지 않게 해서 발행 실패를 막아라").
        # 관문(editorial_gate)은 같은 경우를 막아서 커밋 전에 고치게 한다.
        print(f"[안내] movers_list: 모르는 style {style!r} — {MOVERS_STYLES} 중 상황에 맞는 것으로 그립니다.", file=sys.stderr)
        style = None
    style = style or _movers_style(picked, price_data)
    if (period_days or period == "week") and style == "table":
        style = "bars" if _movers_style(picked, price_data) == "bars" else "tiles"
    if style == "bars":
        return _movers_bars(picked, output_path, title)
    if style == "tiles":
        return _movers_tiles(picked, output_path, title)
    return _movers_table(picked, output_path, title)


def _movers_bars(picked: list[dict], output_path: Path, title: str) -> Path:
    row_h, top = 52, 90
    h = top + row_h * len(picked) + 30
    img = Image.new("RGB", (W, h), BG)
    d = ImageDraw.Draw(img)
    d.text((48, 36), title, font=_font(22, True), fill=INK)
    mx = max(abs(float(e["change_pct"])) for e in picked) or 1.0
    has_down = any(float(e["change_pct"]) < 0 for e in picked)
    zx = 330 if not has_down else 520
    span = (W - 110 - zx) if not has_down else (W - 110 - zx)
    left_span = zx - 340 if has_down else 0
    d.line([(zx, top - 10), (zx, h - 24)], fill=LINE, width=1)
    for i, e in enumerate(picked):
        y = top + i * row_h
        v = float(e["change_pct"]); c = _color(v)
        d.text((48, y + 6), str(e["name"])[:14], font=_font(20, True), fill=INK)
        label = f"{v:+.2f}%"; lf = _font(20, True)
        if v >= 0:
            bl = span * v / mx
            d.rounded_rectangle([zx, y, zx + max(bl, 4), y + 34], 6, fill=c)
            d.text((zx + bl + 10, y + 6), label, font=lf, fill=c)
        else:
            bl = (left_span or span) * abs(v) / mx
            d.rounded_rectangle([zx - max(bl, 4), y, zx, y + 34], 6, fill=c)
            d.text((zx - bl - 10 - d.textlength(label, font=lf), y + 6), label, font=lf, fill=c)
    img.save(output_path, format="PNG", optimize=True)
    return output_path


def _movers_tiles(picked: list[dict], output_path: Path, title: str) -> Path:
    cols = 3
    rows_n = (len(picked) + cols - 1) // cols
    h = 84 + rows_n * 160 + 20
    img = Image.new("RGB", (W, h), BG)
    d = ImageDraw.Draw(img)
    d.text((48, 36), title, font=_font(22, True), fill=INK)
    for i, e in enumerate(picked):
        x = 48 + (i % cols) * 308; y = 84 + (i // cols) * 160
        v = float(e["change_pct"]); c = _color(v)
        d.rounded_rectangle([x, y, x + 290, y + 140], 14, fill=PANEL, outline=LINE)
        d.text((x + 20, y + 18), str(e["name"])[:14], font=_font(20, True), fill=INK)
        d.text((x + 20, y + 52), f"{v:+.2f}%", font=_font(40, True), fill=c)
        d.text((x + 20, y + 106), _fmt(float(e["price"]), _stock_unit(e)), font=_font(15), fill=SUB)
    img.save(output_path, format="PNG", optimize=True)
    return output_path


def _movers_table(picked: list[dict], output_path: Path, title: str) -> Path:
    h = 122 + 46 * len(picked) + 30
    img = Image.new("RGB", (W, h), BG)
    d = ImageDraw.Draw(img)
    d.text((48, 36), title, font=_font(22, True), fill=INK)
    for key, x in (("종목", 48), ("종가", 420), ("오늘", 600), ("5거래일", 760)):
        d.text((x, 84), key, font=_font(15), fill=SUB)
    d.line([(48, 108), (W - 48, 108)], fill=LINE, width=1)
    for i, e in enumerate(picked):
        y = 122 + i * 46
        v = float(e["change_pct"]); p5 = _pct_over(e, 5)
        d.text((48, y), str(e["name"])[:14], font=_font(20, True), fill=INK)
        d.text((420, y), _fmt(float(e["price"]), _stock_unit(e)), font=_font(19), fill=INK)
        d.text((600, y), f"{v:+.2f}%", font=_font(20, True), fill=_color(v))
        if p5 is None:
            d.text((760, y), "—", font=_font(19), fill=SUB)
        else:
            d.text((760, y), f"{p5:+.1f}%", font=_font(19), fill=_color(p5))
        d.line([(48, y + 38), (W - 48, y + 38)], fill=LINE, width=1)
    img.save(output_path, format="PNG", optimize=True)
    return output_path


def flow_compare(price_data: dict, output_path: Path, top_n: int = 5,
                 title: str = "외국인과 기관, 같은 종목에서 반대로") -> Path:
    """같은 종목의 외국인·기관 순매매를 나란히 놓습니다.

    `institution_net`은 시세 파일에 늘 들어 있었는데 어디에도 그려지지 않았습니다.
    외국인만 보면 "무엇을 팔았다"까지만 보이고, 기관을 나란히 놓아야 그 매도를
    누가 받았는지가 보입니다(2026-09-04: 외국인이 판 신한지주·KB금융을 기관이
    받았습니다).

    **실제로 방향이 갈린 종목만 담습니다.** 전에는 외국인 순매수 상위와 순매도
    상위를 그냥 잘라 왔는데, 그러면 둘 다 순매수인 종목이 맨 위에 올라와 제목
    ("같은 종목에서 반대로")과 그림이 어긋났습니다. 2026-09-06에 실제로 상위 다섯
    줄이 전부 양쪽 순매수였습니다. 제목이 사실이 아닌 그림은 틀린 그림입니다.
    """
    ensure_korean_font()   # 폰트 없으면 두부(□) 그림 대신 여기서 멈춥니다
    rows = [
        e for e in (price_data.get("watchlist") or {}).values()
        if e.get("foreign_net") is not None and e.get("institution_net") is not None
        and e["foreign_net"] != 0 and e["institution_net"] != 0
    ]
    if not rows:
        raise ValueError("flow_compare: 외국인·기관 순매매가 함께 있는 종목이 없습니다")
    opposed = [e for e in rows if (e["foreign_net"] > 0) != (e["institution_net"] > 0)]
    if not opposed:
        raise ValueError("flow_compare: 그날 외국인과 기관이 반대로 간 종목이 없습니다")
    # 겹치는 물량이 클수록 "한쪽이 판 것을 다른 쪽이 받았다"가 뚜렷합니다.
    opposed.sort(key=lambda e: -min(abs(e["foreign_net"]), abs(e["institution_net"])))
    picked = opposed[:top_n * 2]

    row_h, top, bar_h = 54, 100, 18
    h = top + row_h * len(picked) + 30
    img = Image.new("RGB", (W, h), BG)
    d = ImageDraw.Draw(img)
    d.text((32, 26), title, font=_font(21, True), fill=SUB)
    # 범례
    d.rounded_rectangle([32, 62, 56, 62 + 14], 4, fill=INK)
    d.text((64, 60), "외국인", font=_font(16), fill=SUB)
    d.rounded_rectangle([132, 62, 156, 62 + 14], 4, fill=FLAT)
    d.text((164, 60), "기관", font=_font(16), fill=SUB)

    span = max(max(abs(e["foreign_net"]), abs(e["institution_net"])) for e in picked) or 1
    mid, half = 430, 230
    d.line([mid, top - 8, mid, h - 20], fill=LINE, width=1)
    for i, e in enumerate(picked):
        y = top + i * row_h
        d.text((32, y + 12), str(e["name"])[:12], font=_font(18, True), fill=INK)
        for j, (key, fill) in enumerate((("foreign_net", INK), ("institution_net", FLAT))):
            net = e[key]
            width = abs(net) / span * half
            by = y + 4 + j * (bar_h + 4)
            if net >= 0:
                d.rounded_rectangle([mid, by, mid + width, by + bar_h], 4, fill=fill)
            else:
                d.rounded_rectangle([mid - width, by, mid, by + bar_h], 4, fill=fill)
            label = f"{net:+,}"
            d.text((W - 32 - d.textlength(label, font=_font(15)), by + 1), label,
                   font=_font(15), fill=SUB)
    img.save(output_path, format="PNG", optimize=True)
    return output_path


SPOTLIGHT_STYLES = ("numbers", "history", "daily_bars")


def _spotlight_style(picked: dict, price_data: dict) -> str:
    """오늘 움직임이 최근 8거래일 중 가장 크면 일별 막대(오늘이 예외임이 보인다), 아니면
    3개월 선과 숫자 넷을 날짜로 번갈아. 3개월 이력이 없으면 일별 막대."""
    closes = _closes(picked)
    if len(closes) < 6:
        return "daily_bars"
    daily = [abs(closes[i] / closes[i - 1] - 1) for i in range(max(1, len(closes) - 8), len(closes))]
    if daily and daily[-1] >= max(daily):
        return "daily_bars"
    if len(closes) < 20:
        return "daily_bars"
    return "history" if _date_ordinal(price_data) % 2 == 0 else "numbers"


def stock_spotlight(price_data: dict, output_path: Path, ticker: str | None = None,
                    title: str = "", style: str | None = None) -> Path:
    """한 종목만 크게 세웁니다 — 이름·등락률에 오른쪽은 세 가지 모양 중 하나.

    numbers(종가·5거래일·3개월 최고·최저 대비), history(3개월 선), daily_bars(최근 8거래일
    일별 막대, 오늘 진하게). 2026-09-09 사용자가 옛 8거래일 꺾은선을 "마음에 안 든다"고
    해 바꿨고, `style`이 없으면 `_spotlight_style`이 상황으로 고른다.
    """
    ensure_korean_font()
    rows = [e for e in (price_data.get("watchlist") or {}).values() if e.get("change_pct") is not None]
    if not rows:
        raise ValueError("stock_spotlight: 등락률이 있는 종목이 없습니다")
    if ticker:
        picked = next((e for e in rows if str(e.get("ticker")) == str(ticker)), None)
        if picked is None:
            raise ValueError(f"stock_spotlight: {ticker}는 그날 시세에 없습니다")
    else:
        picked = max(rows, key=lambda e: abs(float(e["change_pct"])))
    if style and style not in SPOTLIGHT_STYLES:
        print(f"[안내] stock_spotlight: 모르는 style {style!r} — {SPOTLIGHT_STYLES} 중 상황에 맞는 것으로 그립니다.", file=sys.stderr)
        style = None
    style = style or _spotlight_style(picked, price_data)

    change = float(picked["change_pct"]); color = _color(change)
    h = 300
    img = Image.new("RGB", (W, h), BG)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([32, 24, W - 32, h - 24], 16, fill=PANEL, outline=LINE)
    if title:
        d.text((60, 48), title, font=_font(19, True), fill=SUB)
    name = str(picked["name"]); nf = _font(48, True)
    while d.textlength(name, font=nf) > 420 and nf.size > 26:
        nf = _font(nf.size - 4, True)
    d.text((60, 88), name, font=nf, fill=INK)
    d.text((60, 158), f"{change:+.2f}%", font=_font(68, True), fill=color)
    price = _fmt(float(picked["price"]), _stock_unit(picked))
    d.text((60, 240), price, font=_font(20), fill=SUB)

    closes = _closes(picked)
    x0, y0, x1, y1 = 520, 92, W - 60, 236
    if style == "numbers":
        p5 = _pct_over(picked, 5); hi, lo, cur = max(closes), min(closes), closes[-1]
        stats = [("종가", price, INK), ("5거래일", p5, None),
                 ("3개월 최고 대비", (cur / hi - 1) * 100, None), ("3개월 최저 대비", (cur / lo - 1) * 100, None)]
        for i, (key, value, fixed) in enumerate(stats):
            x = x0 + (i % 2) * 210; y = 92 + (i // 2) * 84
            d.text((x, y), key, font=_font(15), fill=SUB)
            if value is None:
                d.text((x, y + 24), "—", font=_font(28, True), fill=SUB)
            elif fixed:
                d.text((x, y + 24), str(value), font=_font(28, True), fill=fixed)
            else:
                d.text((x, y + 24), f"{value:+.1f}%", font=_font(28, True), fill=_color(float(value)))
    elif style == "history":
        lo, hi = min(closes), max(closes)
        pts = [(x0 + (x1 - x0) * i / (len(closes) - 1), y1 - (y1 - y0) * (c - lo) / (hi - lo or 1))
               for i, c in enumerate(closes)]
        d.polygon(pts + [(x1, y1), (x0, y1)], fill="#F6E4E0" if change >= 0 else "#E0EAF6")
        d.line(pts, fill=color, width=3)
        d.ellipse([pts[-1][0] - 5, pts[-1][1] - 5, pts[-1][0] + 5, pts[-1][1] + 5], fill=color)
        d.text((x0, y1 + 8), f"최근 3개월 · 최저 {lo:,.2f} · 최고 {hi:,.2f}", font=_font(15), fill=SUB)
    else:
        daily = [(closes[i] / closes[i - 1] - 1) * 100 for i in range(max(1, len(closes) - 8), len(closes))]
        mid = (y0 + y1) // 2; mx = max(abs(v) for v in daily) or 1.0; bw = (x1 - x0) / len(daily)
        d.line([(x0, mid), (x1, mid)], fill=LINE, width=1)
        for i, v in enumerate(daily):
            bx = x0 + i * bw + 6; bh = (mid - y0 - 10) * abs(v) / mx
            c = _color(v) if i == len(daily) - 1 else ("#E9B3AA" if v >= 0 else "#B3C8E6")
            d.rectangle([bx, mid - bh if v >= 0 else mid, bx + bw - 12, mid if v >= 0 else mid + bh], fill=c)
        d.text((x0, y1 + 8), f"최근 {len(daily)}거래일 일별 등락률 (오늘 진하게)", font=_font(15), fill=SUB)
    img.save(output_path, format="PNG", optimize=True)
    return output_path


def _entry_for(price_data: dict, ticker: str) -> dict:
    """macro → watchlist 순서로 지수·종목 항목을 찾습니다. 없으면 예외(다른 것을 그리지 않음)."""
    for group in ("macro", "watchlist"):
        for key, entry in (price_data.get(group) or {}).items():
            if str(key) == str(ticker) or str(entry.get("ticker")) == str(ticker):
                return {**entry, "ticker": entry.get("ticker") or key, "_group": group}
    raise ValueError(f"{ticker}는 그날 시세에 없습니다")


def _unit_for(entry: dict) -> str:
    return _stock_unit(entry) if entry.get("_group") == "watchlist" else str(entry.get("unit") or "")


def _footer(d: ImageDraw.ImageDraw, h: int, text: str) -> None:
    d.text((32, h - 34), text, font=_font(14), fill=SUB)


def price_history(price_data: dict, output_path: Path, ticker: str, title: str = "",
                  subtitle: str = "", guide: float | None = None, guide_label: str = "") -> Path:
    """한 지수·종목의 최근 3개월 종가 흐름 (2026-09-08, 사용자가 고른 시안 A·B).

    벤치마크(재테크농부) 이미지의 큰 몫이 이런 기간 차트 스크린샷입니다. 우리는
    시세 파일의 `history`(최근 70거래일, `src/price_history.py`)로 직접 그립니다 —
    8거래일 스파크라인은 "흐름"을 못 보여준다는 지적이 있었습니다.
    `guide`는 7,000선 같은 기준선, `title`은 그 그림이 하는 말입니다
    ("코스피, 7,000선을 넘지 못했습니다"). 이력이 없는 시세 파일(2026-09-08 이전)
    에서는 예외를 올립니다 — 조용히 스파크라인으로 바꾸지 않습니다.
    """
    ensure_korean_font()
    entry = _entry_for(price_data, ticker)
    history = entry.get("history") or {}
    dates = [str(v) for v in (history.get("dates") or [])]
    closes = [float(v) for v in (history.get("close") or [])]
    if len(closes) < 10 or len(dates) != len(closes):
        raise ValueError(
            f"price_history: {ticker}의 종가 이력이 부족합니다({len(closes)}개). "
            "시세 파일에 history가 없으면(2026-09-08 이전 수집기) 이 그래픽은 쓸 수 없습니다.")
    change = float(entry.get("change_pct") or 0)
    color = _color(change)
    unit = _unit_for(entry)
    fmt = "{:,.0f}" if abs(closes[-1]) >= 10000 else "{:,.2f}"
    name = str(entry.get("name"))
    title = title or f"{name}, 최근 3개월"
    subtitle = subtitle or f"{dates[-1]} 종가 {fmt.format(closes[-1])}{unit} ({change:+.2f}%)"

    h = 600
    img = Image.new("RGB", (W, h), BG)
    d = ImageDraw.Draw(img)
    d.text((32, 26), title, font=_font(26, True), fill=INK)
    d.text((32, 66), subtitle, font=_font(16), fill=SUB)
    x0, y0, x1, y1 = 118, 112, W - 48, h - 82
    lo, hi = min(closes), max(closes)
    if guide is not None:
        lo, hi = min(lo, float(guide)), max(hi, float(guide))
    pad = (hi - lo) * 0.12 or 1.0
    lo, hi = lo - pad, hi + pad
    def X(i: int) -> float:
        return x0 + (x1 - x0) * i / (len(closes) - 1)
    def Y(v: float) -> float:
        return y1 - (y1 - y0) * (v - lo) / (hi - lo)
    for k in range(5):
        v = lo + (hi - lo) * k / 4
        d.line([(x0, Y(v)), (x1, Y(v))], fill=LINE, width=1)
        d.text((x0 - 12, Y(v)), fmt.format(v), font=_font(13), fill=SUB, anchor="rm")
    pts = [(X(i), Y(v)) for i, v in enumerate(closes)]
    overlay = Image.new("RGBA", (W, h), (0, 0, 0, 0))
    ImageDraw.Draw(overlay).polygon([(x0, y1)] + pts + [(x1, y1)], fill=color + "22")
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    d = ImageDraw.Draw(img)
    d.line(pts, fill=color, width=4, joint="curve")
    if guide is not None:
        gy = Y(float(guide))
        for x in range(int(x0), int(x1), 14):
            d.line([(x, gy), (x + 7, gy)], fill=INK, width=2)
        d.text((x0 + 8, gy - 6), guide_label or fmt.format(float(guide)), font=_font(15, True),
               fill=INK, anchor="ld")
    seen: set[str] = set()
    for i, day in enumerate(dates):
        month = day[:7]
        if month not in seen and i > 0 and dates[i - 1][:7] != month:
            seen.add(month)
            d.text((X(i), y1 + 10), f"{int(day[5:7])}월", font=_font(14), fill=SUB, anchor="ma")
    lx, ly = pts[-1]
    d.ellipse([lx - 7, ly - 7, lx + 7, ly + 7], fill=color, outline=BG, width=3)
    d.text((lx - 12, ly - 10), fmt.format(closes[-1]) + unit, font=_font(20, True),
           fill=color, anchor="rd")
    _footer(d, h, f"자료: 마감 종가 {dates[0]}~{dates[-1]} · Fermata 작성")
    img.save(output_path, format="PNG", optimize=True)
    return output_path


def investor_flows(price_data: dict, output_path: Path, values: dict, source: str,
                   title: str = "투자자별 순매수", subtitle: str = "", unit: str = "억원") -> Path:
    """외국인·기관·개인 순매수를 큰 숫자 셋으로 (2026-09-08, 시안 C).

    이 숫자는 시세 파일이 아니라 **조사에서** 옵니다(마감 집계 기사). 그래서
    `source`(어느 매체의 집계인지)를 반드시 받아 그림 바닥에 찍습니다 — 출처 없는
    수급 그림은 쓰지 않습니다. 본문 문장의 숫자와 같은 값을 넣으십시오.
    """
    ensure_korean_font()
    if not values or not isinstance(values, dict):
        raise ValueError("investor_flows: values에 {'외국인': 6482, '기관': 6428, '개인': -13333}처럼 순매수를 주십시오")
    if not str(source or "").strip():
        raise ValueError("investor_flows: source(집계 출처)를 적으십시오 — 이 숫자는 시세 파일에 없습니다")
    rows = [(str(k), float(v)) for k, v in values.items()]
    row_h, top = 96, 120
    h = top + row_h * len(rows) + 70
    img = Image.new("RGB", (W, h), BG)
    d = ImageDraw.Draw(img)
    d.text((32, 26), title, font=_font(26, True), fill=INK)
    d.text((32, 66), subtitle or f"순매수 ({unit})", font=_font(16), fill=SUB)
    span = max(abs(v) for _, v in rows) or 1.0
    cx, half = 560, 330
    d.line([(cx, top - 10), (cx, h - 60)], fill=LINE, width=2)
    for i, (name, v) in enumerate(rows):
        y = top + i * row_h
        d.text((48, y + 22), name, font=_font(24, True), fill=INK, anchor="lm")
        width = max(6, abs(v) / span * half)
        color = UP if v > 0 else (DOWN if v < 0 else FLAT)
        label = f"{v:+,.0f}{unit if unit != '억원' else '억'}"
        lf = _font(26, True)
        if v >= 0:
            d.rounded_rectangle([cx, y, cx + width, y + 44], 8, fill=color)
            # 막대가 캔버스 오른쪽 끝에 가까우면 라벨을 막대 안쪽으로 넣습니다 — 그렇지
            # 않으면 순매수 값이 span(최댓값)에 가까운 날 라벨이 캔버스 밖으로 잘립니다
            # (2026-09-11 실측: "+24,259억"의 "억"이 잘려 나갔습니다).
            if cx + width + 14 + d.textlength(label, font=lf) > W - 12:
                if width > d.textlength(label, font=lf) + 24:
                    d.text((cx + width - 12, y + 22), label, font=lf, fill=PANEL, anchor="rm")
                else:
                    d.text((W - 12, y + 22), label, font=lf, fill=color, anchor="rm")
            else:
                d.text((cx + width + 14, y + 22), label, font=lf, fill=color, anchor="lm")
        else:
            d.rounded_rectangle([cx - width, y, cx, y + 44], 8, fill=color)
            if width > d.textlength(label, font=lf) + 24:
                d.text((cx - 12, y + 22), label, font=lf, fill=PANEL, anchor="rm")
            else:
                d.text((cx - width - 14, y + 22), label, font=lf, fill=color, anchor="rm")
    _footer(d, h, f"자료: {source} · Fermata 작성")
    img.save(output_path, format="PNG", optimize=True)
    return output_path


def number_cards(price_data: dict, output_path: Path, tickers: list[str] | None = None,
                 items: list[dict] | None = None, title: str = "오늘 시장을 정한 숫자",
                 subtitle: str = "", note: str = "", period_days: int | None = None,
                 period: str | None = None) -> Path:
    """지수·환율·유가 같은 숫자 2~4개를 카드로 (2026-09-08, 시안 D).

    `tickers`는 시세 파일의 지수·종목(값이 시세에서 나옵니다), `items`는 시세 파일에
    없는 숫자(WTI·금리 등)를 `{"label": "WTI", "value": "93.10달러", "change": "+1.8%"}`
    로 직접 적는 것입니다. 직접 적은 숫자는 본문에서 출처와 함께 설명해야 합니다.
    `note`는 카드 아래 한 줄 — "장중 7,171까지 올랐다가 밀렸습니다".
    `period="week"`(달력 주간 — 휴장이 낀 주에도 전주 마지막 종가 대비, 권장)나 `period_days`(N거래일)를
    주면 하루 등락 대신 그 기간 등락을 "주간 +1.2%"로 적습니다(시세 파일의 3개월 이력에서 계산).
    이력이 모자라면 예외로 멈춥니다 — 하루 등락을 주간처럼 보이게 두지 않습니다.
    """
    ensure_korean_font()
    cards: list[tuple[str, str, str, str]] = []
    for ticker in tickers or []:
        entry = _entry_for(price_data, ticker)
        if period == "week" or period_days:
            over = _period_pct(entry, price_data, period_days, period)
            if over is None:
                raise ValueError(f"number_cards: {ticker}의 이력이 짧아 주간(기간) 등락을 셀 수 없습니다")
            change = float(over)
            change_text = ("주간 " if period == "week" or int(period_days or 0) == 5 else f"{period_days}일 ") + f"{change:+.2f}%"
        else:
            change = float(entry.get("change_pct") or 0)
            change_text = f"{change:+.2f}%"
        price = float(entry["price"])
        # 지수는 소수점 둘째 자리까지가 관행(6,954.52)이고, 주가·환율은 정수로 읽는다.
        value = (f"{price:,.2f}" if entry.get("_group") == "macro" and not entry.get("unit")
                 else _fmt(price, _unit_for(entry)))
        cards.append((str(entry.get("name")), value, change_text, _color(change)))
    for item in items or []:
        change_text = str(item.get("change", "")).strip()
        color = UP if change_text.startswith("+") else (DOWN if change_text.startswith("-") else FLAT)
        cards.append((str(item.get("label", "")), str(item.get("value", "")), change_text, color))
    if not cards:
        macro = list((price_data.get("macro") or {}).values())[:3]
        cards = [(str(e.get("name")), _fmt(float(e["price"]), str(e.get("unit") or "")),
                  f"{float(e.get('change_pct') or 0):+.2f}%", _color(float(e.get("change_pct") or 0)))
                 for e in macro if e.get("price") is not None]
    if not 2 <= len(cards) <= 4:
        raise ValueError(f"number_cards: 카드는 2~4개입니다 (지금 {len(cards)}개)")
    h = 400 + (56 if note else 0)
    img = Image.new("RGB", (W, h), BG)
    d = ImageDraw.Draw(img)
    d.text((32, 26), title, font=_font(26, True), fill=INK)
    if subtitle:
        d.text((32, 66), subtitle, font=_font(16), fill=SUB)
    gap, left, top, bottom = 18, 32, 104, 300
    cw = (W - left * 2 - gap * (len(cards) - 1)) / len(cards)
    for i, (label, value, change, color) in enumerate(cards):
        x = left + i * (cw + gap)
        d.rounded_rectangle([x, top, x + cw, bottom], 14, fill=PANEL, outline=LINE)
        d.text((x + 22, top + 22), label[:14], font=_font(16), fill=SUB)
        vf = _font(30, True)
        while d.textlength(value, font=vf) > cw - 44 and vf.size > 18:
            vf = _font(vf.size - 2, True)
        d.text((x + 22, top + 74), value, font=vf, fill=INK)
        d.text((x + 22, top + 140), change, font=_font(24, True), fill=color)
    if note:
        d.text((32, bottom + 26), note, font=_font(19), fill=INK)
    _footer(d, h, "자료: 마감 시세 · 직접 적은 숫자는 본문 출처 참조 · Fermata 작성")
    img.save(output_path, format="PNG", optimize=True)
    return output_path


def fact_table(price_data: dict, output_path: Path, rows: list, source: str,
               title: str = "발표값과 예상값", subtitle: str = "", columns: list | None = None,
               note: str = "") -> Path:
    """지표 발표값 대 예상값, 실적 대 컨센서스 같은 "실제 표"를 그림으로 (2026-09-08, 제안 9번).

    재테크농부 이미지의 상당수가 이런 표다. `rows`는 `[["8월 비농업 고용", "16.2만", "5.3만",
    "+10.9만"], ...]`처럼 문자열 행이고, 마지막 열이 '+'로 시작하면 빨강, '-'면 파랑으로
    칠한다. 숫자는 시세 파일이 아니라 조사에서 오므로 `source`(매체)가 필수다.
    """
    ensure_korean_font()
    if not rows or not all(isinstance(r, (list, tuple)) and len(r) >= 2 for r in rows):
        raise ValueError("fact_table: rows는 문자열 행(2칸 이상)의 목록이어야 합니다")
    if not str(source or "").strip():
        raise ValueError("fact_table: source(출처 매체)를 적으십시오 — 이 숫자는 시세 파일에 없습니다")
    ncol = max(len(r) for r in rows)
    columns = list(columns or (["항목", "발표", "예상", "차이"][:ncol] + [""] * max(0, ncol - 4)))
    row_h, top = 54, 120
    h = top + row_h * (len(rows) + 1) + 40 + (40 if note else 0)
    img = Image.new("RGB", (W, h), BG)
    d = ImageDraw.Draw(img)
    d.text((32, 26), title, font=_font(26, True), fill=INK)
    if subtitle:
        d.text((32, 66), subtitle, font=_font(16), fill=SUB)
    first_w = 380
    other_w = (W - 64 - first_w) / max(1, ncol - 1)
    def x_of(j: int) -> float:
        return 32 + (0 if j == 0 else first_w + (j - 1) * other_w)
    y = top
    for j, name in enumerate(columns[:ncol]):
        d.text((x_of(j) + (12 if j == 0 else other_w - 12), y + 14), str(name), font=_font(15), fill=SUB,
               anchor="lm" if j == 0 else "rm")
    y += 40
    d.line([(32, y), (W - 32, y)], fill=INK, width=2)
    for i, row in enumerate(rows):
        y_top = y + i * row_h
        if i % 2 == 1:
            d.rectangle([32, y_top, W - 32, y_top + row_h], fill=PANEL)
        for j in range(ncol):
            cell = str(row[j]) if j < len(row) else ""
            color = INK
            if j == ncol - 1 and cell.startswith("+"):
                color = UP
            elif j == ncol - 1 and cell.startswith(("-", "−")):
                color = DOWN
            d.text((x_of(j) + (12 if j == 0 else other_w - 12), y_top + row_h / 2), cell,
                   font=_font(19, j != 0), fill=color, anchor="lm" if j == 0 else "rm")
        d.line([(32, y_top + row_h), (W - 32, y_top + row_h)], fill=LINE, width=1)
    if note:
        d.text((32, y + len(rows) * row_h + 18), note, font=_font(17), fill=INK)
    _footer(d, h, f"자료: {source} · Fermata 작성")
    img.save(output_path, format="PNG", optimize=True)
    return output_path


# 시세 파일이 필요 없는 그래픽 — 기준표·프리뷰에서 price_file 없이 쓸 수 있다.
PRICELESS_KINDS = {"fact_table", "investor_flows"}

BUILDERS = {"index_card": index_card, "sector_bars": sector_bars,
            "flow_chart": flow_chart, "two_day_compare": two_day_compare,
            "movers_list": movers_list, "flow_compare": flow_compare,
            "stock_spotlight": stock_spotlight,
            "price_history": price_history, "investor_flows": investor_flows,
            "number_cards": number_cards, "fact_table": fact_table}


def build(kind: str, price_data: dict, output_path: Path, **kwargs) -> dict:
    """원고의 graphic 지정을 그림 파일로 만들고 렌더러가 쓸 정보를 돌려줍니다."""
    # output/은 저장소에 없습니다(gitignore). 러너에서 처음 그릴 때 만듭니다 —
    # 2026-09-04 첫 실행이 이 디렉터리가 없어 FileNotFoundError로 끝났습니다.
    ensure_korean_font()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    if kind not in BUILDERS:
        raise ValueError(f"모르는 그래픽 종류 {kind!r} — 쓸 수 있는 것: {', '.join(sorted(BUILDERS))}")
    builder = BUILDERS[kind]
    builder(price_data, output_path, **kwargs)
    return {"local_path": str(output_path), "kind": kind}
