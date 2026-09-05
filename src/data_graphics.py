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

만드는 것은 셋입니다.
- index_card:   지수·환율 3분할 카드 + 최근 흐름 스파크라인
- sector_bars:  업종별 평균 등락률 가로 막대
- flow_chart:   외국인 순매수·순매도 상위 종목 막대

사진과 달리 이 그림들은 "틀린 그림이 붙을 위험"이 없어 사람 검수 없이 나가는
경로에서도 안전합니다.
"""
from __future__ import annotations

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


def movers_list(price_data: dict, output_path: Path, top_n: int = 6,
                title: str = "오늘 많이 움직인 종목") -> Path:
    """종목명 · 최근 주가 흐름 · 등락률을 한 줄씩 세운 목록입니다.

    벤치마크(재테크농부) 시황 본문의 이미지 349장을 받아 보니 대부분이 사진이
    아니라 이런 모양의 표·차트였습니다 — 종목 옆에 작은 추이선과 등락률이 붙은
    목록. 우리 글은 이미지가 5장인데 그쪽은 중앙값 14장이라, 차이를 사진이 아니라
    데이터 그래픽으로 메웁니다. 사진과 달리 여기 그리는 것은 전부 시세 파일에서
    나오므로 틀린 그림이 붙을 수 없습니다.

    절대 등락률 상위 `top_n`개를 오른 것부터 세웁니다.
    """
    rows = [
        e for e in (price_data.get("watchlist") or {}).values()
        if e.get("change_pct") is not None
    ]
    if not rows:
        raise ValueError("movers_list: 등락률이 있는 종목이 없습니다")
    rows.sort(key=lambda e: abs(float(e["change_pct"])), reverse=True)
    picked = sorted(rows[:top_n], key=lambda e: float(e["change_pct"]), reverse=True)

    row_h, top = 62, 78
    h = top + row_h * len(picked) + 24
    img = Image.new("RGB", (W, h), BG)
    d = ImageDraw.Draw(img)
    d.text((32, 26), title, font=_font(21, True), fill=SUB)

    # 대표 이미지의 타일과 같은 모양입니다 — 왼쪽 색 막대가 방향, 이름은 크게,
    # 등락률은 오른쪽 끝에. 대문과 본문이 한 벌로 보이게 맞춘 것입니다.
    for i, e in enumerate(picked):
        y = top + i * row_h
        color = _color(float(e["change_pct"]))
        d.rounded_rectangle([32, y, W - 32, y + row_h - 10], 12, fill=PANEL, outline=LINE)
        d.rounded_rectangle([32, y, 38, y + row_h - 10], 3, fill=color)
        d.text((58, y + 9), str(e["name"])[:14], font=_font(23, True), fill=INK)
        price = _fmt(float(e["price"]), _stock_unit(e))
        d.text((58, y + 36), price, font=_font(15), fill=SUB)
        _sparkline(d, e.get("series"), (W - 320, y + 14, W - 200, y + 38), color)
        pct = f"{float(e['change_pct']):+.2f}%"
        pf = _font(26, True)
        d.text((W - 58 - d.textlength(pct, font=pf), y + 13), pct, font=pf, fill=color)
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


def stock_spotlight(price_data: dict, output_path: Path, ticker: str | None = None,
                    title: str = "") -> Path:
    """한 종목만 크게 세웁니다 — 이름, 등락률, 최근 흐름.

    대표 이미지의 single 레이아웃과 같은 모양입니다. 그날 이야기가 종목 하나로
    설명되는 날(2026-09-02 델 테크놀로지스, 09-04 원익홀딩스)에는 그 종목을
    다루는 문단 옆에 표 대신 이 그림을 붙입니다. 목록형 그림(movers_list)은
    "여럿이 함께 움직였다"를 말하고, 이 그림은 "오늘은 이 종목이다"를 말합니다.

    ticker를 주면 그 종목을, 주지 않으면 그날 절대 등락 폭 1위를 그립니다.
    """
    rows = [
        e for e in (price_data.get("watchlist") or {}).values()
        if e.get("change_pct") is not None
    ]
    if not rows:
        raise ValueError("stock_spotlight: 등락률이 있는 종목이 없습니다")
    if ticker:
        picked = next((e for e in rows if str(e.get("ticker")) == str(ticker)), None)
        if picked is None:
            raise ValueError(f"stock_spotlight: {ticker}는 그날 시세에 없습니다")
    else:
        picked = max(rows, key=lambda e: abs(float(e["change_pct"])))

    change = float(picked["change_pct"])
    color = _color(change)
    h = 300
    img = Image.new("RGB", (W, h), BG)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([32, 24, W - 32, h - 24], 16, fill=PANEL, outline=LINE)
    if title:
        d.text((60, 48), title, font=_font(19, True), fill=SUB)

    name = str(picked["name"])
    nf = _font(52, True)
    while d.textlength(name, font=nf) > 470 and nf.size > 26:
        nf = _font(nf.size - 4, True)
    d.text((60, 88), name, font=nf, fill=INK)
    d.text((60, 168), f"{change:+.2f}%", font=_font(76, True), fill=color)
    price = _fmt(float(picked["price"]), _stock_unit(picked))
    d.text((60, 254), price, font=_font(20), fill=SUB)

    # 오른쪽에 최근 흐름. 대표 이미지와 달리 본문은 폭이 넓어 크게 들어갑니다.
    _sparkline(d, picked.get("series"), (W - 400, 96, W - 60, 236), color)
    d.text((W - 400, 254), "최근 8거래일", font=_font(16), fill=SUB)
    img.save(output_path, format="PNG", optimize=True)
    return output_path


BUILDERS = {"index_card": index_card, "sector_bars": sector_bars,
            "flow_chart": flow_chart, "two_day_compare": two_day_compare,
            "movers_list": movers_list, "flow_compare": flow_compare,
            "stock_spotlight": stock_spotlight}


def build(kind: str, price_data: dict, output_path: Path, **kwargs) -> dict:
    """원고의 graphic 지정을 그림 파일로 만들고 렌더러가 쓸 정보를 돌려줍니다."""
    # output/은 저장소에 없습니다(gitignore). 러너에서 처음 그릴 때 만듭니다 —
    # 2026-09-04 첫 실행이 이 디렉터리가 없어 FileNotFoundError로 끝났습니다.
    ensure_korean_font()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    builder = BUILDERS[kind]
    builder(price_data, output_path, **kwargs)
    return {"local_path": str(output_path), "kind": kind}
