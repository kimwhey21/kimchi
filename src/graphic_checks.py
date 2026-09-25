"""그래픽 입력값과 배치 규약을 렌더 전·후에 검사한다.

OCR로 완벽한 미감을 판단하지는 않는다. 대신 제목이 주장하는 데이터 관계, 축의
정보 손실, 고정 캔버스에서 계산 가능한 텍스트 충돌을 발행 전에 실패시킨다.

2026-09-25 확장 — 감사·검증에서 **눈으로만 잡힌 오류 7건 중 6건은 코드가 판정할 수 있었다**:
① sector_bars 제목은 '반도체만 웃었습니다'인데 다른 업종 막대도 빨갛다 ② price_history·stock_spotlight
제목은 '신고가를 씁니다'인데 마지막 값이 이력의 최대값이 아니다 ③ movers_list가 그린 종목 이름이 그 절
본문에 없다(그림은 상위 6, 본문은 '편입 종목') ④ fact_table 셀 글자가 열 폭을 넘어 이웃 셀과 겹친다
(프리뷰 9/22·23·24 사흘 연속). 그전까지 `collect_spec_issues`는 valuation_bars·gap_bars·flow_compare·
calendar_strip만 봤다. 원칙은 `editorial_facts`와 같다 — **확실할 때만 실패시킨다.** 제목에 '근처'·'대비'
같은 한정어가 붙어 뜻이 흐리면 건너뛰고, 데이터가 없으면 건너뛴다.

호출 — spec dict만으로 돈다. 시세는 인자로 받는다(시황 경로는 원고에 박힌 `price_data`, 기준표·프리뷰는
`price_file`로 읽은 것). `section_body`는 그 그림이 붙는 절의 본문이다.

    graphic_checks.collect_spec_issues(kind, options, title, price_data=price_data,
                                       section_body=section.get("body"))
"""
from __future__ import annotations

import re
from pathlib import Path

from PIL import Image

from src import data_graphics
from src.data_graphics import W, korean_font
from src.post_tags import mentioned

# movers_list — 그린 이름 중 본문에 없는 것이 이 비율을 **넘으면** 실패(2026-09-25 지시: "절반 넘으면").
# 절 본문이 상위 두셋만 짚는 것은 정상이라 전부를 요구하지 않는다.
MOVERS_MISSING_RATIO = 0.5

# 제목이 하는 '최고·최저' 주장은 현재값이 이력의 최대·최소와 이만큼(비율) 안에 있으면 참으로 본다.
# 시세 파일의 `price`는 소수 둘째 자리로 반올림돼 있고(5.11) 이력 종가는 아니라서(5.114) 딱 같음을
# 요구하면 참인 주장을 거짓으로 잡는다 — 2026-09-25 실측(^TNX).
EXTREME_TOLERANCE = 1e-3

# 제목이 '하나만'을 주장하는 꼴. 한국어 '만'은 "만원·만에·만큼·만약"에도 들어가므로 앞에 한글·영문이 붙고
# 뒤에 조사·공백·문장 끝이 오는 것만 센다("반도체만 웃었다", "은행만이", "삼성전자만 올랐습니다").
_EXCLUSIVE = re.compile(r"(?<=[가-힣A-Za-z])만(?=[\s,·은이을를의도]|$)|유일|\bonly\b|\balone\b|\bsole\b|\blone\b",
                        re.IGNORECASE)
_UP_WORDS = re.compile(r"오르|올랐|올라|상승|웃|강세|플러스|빨간|빨갛|\bup\b|\brose\b|\bgain|\brall|\bclimb|\bhigher\b|\bred\b",
                       re.IGNORECASE)
_DOWN_WORDS = re.compile(r"내리|내렸|내려|하락|떨어|약세|울었|마이너스|파란|파랗|\bdown\b|\bfell\b|\bdrop|\bloss|\blower\b|\bblue\b",
                         re.IGNORECASE)

# 제목이 '최고·최저'를 주장하는 꼴과, 그 주장을 흐리는 한정어. '최고치 근처'·'최고가에서 밀려났습니다'·
# '3개월 최고 대비'는 최대값이라는 주장이 아니므로 검사하지 않는다(확실할 때만 실패).
_CLAIM_LOW = re.compile(r"신저가|최저치|최저가|최저|\blowest\b|\b(?:record|all-time|fresh|new)\b[^.,]{0,20}?\blows?\b",
                        re.IGNORECASE)
_CLAIM_HIGH = re.compile(r"신고가|최고치|최고가|최고|\bhighest\b|\brecord\b|\ball-time\b|\b(?:fresh|new)\b[^.,]{0,20}?\bhighs?\b",
                         re.IGNORECASE)
_HEDGE = re.compile(r"근처|부근|가까이|가까운|가깝|대비|밀려|내려왔|아래|밑|못 미|넘지 못|턱밑|눈앞|"
                    r"\bnear\b|\bbelow\b|\boff\b|\bshort of\b|\bfrom\b|\baway\b|\bshy\b|\bretreat|\bpull|\bapproach",
                    re.IGNORECASE)


def _width(text: str, size: int) -> float:
    # 실제 렌더러와 같은 폰트 측정을 써야 macOS/CI의 글자 폭 차이를 잡는다.
    return korean_font(size).getlength(str(text))


def _named(name: str | None, body: str) -> bool:
    """이름이 본문에 낱말로 나오는가 — `post_tags.mentioned`의 경계 규칙(앞에 글자가 붙으면 다른 낱말,
    두 글자 이름은 뒤에 조사만 허용)을 그대로 쓴다. 짧은 별칭은 허용하지 않는다(2026-09-25 지시)."""
    return bool(name) and mentioned(str(name).strip(), body)


def _current_and_series(entry: dict, trading_date: str) -> tuple[float, list[float]] | None:
    """(현재값, 비교할 종가 목록). 이력 마지막 날이 거래일과 다르면(일봉이 늦는 날, 2026-09-08·09-10 실측)
    이력 마지막 값은 어제 것이므로 현재값은 `price`로 잡고 이력 전체와 비교한다. 이력이 둘 미만이면 None."""
    closes = data_graphics._closes(entry)
    if len(closes) < 2:
        return None
    dates = [str(v) for v in ((entry.get("history") or {}).get("dates") or [])]
    price = entry.get("price")
    if dates and len(dates) == len(closes) and trading_date and dates[-1] != trading_date and price is not None:
        return float(price), [float(c) for c in closes]
    return float(closes[-1]), [float(c) for c in closes]


def _extreme_claim_issues(kind: str, title: str, entries: list[dict], trading_date: str) -> list[str]:
    """제목이 '신고가·최고·record·high'(또는 '최저·low')를 주장하면 그린 값 가운데 하나는 실제로 이력의
    최대(최소)여야 한다. 하나라도 맞으면 통과(number_cards는 카드가 여럿이라 어느 카드 이야기인지 제목만으로는
    모른다). 한정어가 있으면 판단하지 않는다."""
    if not title or _HEDGE.search(title):
        return []
    if _CLAIM_LOW.search(title):
        want = "low"
    elif _CLAIM_HIGH.search(title):
        want = "high"
    else:
        return []
    checked: list[str] = []
    for entry in entries:
        pair = _current_and_series(entry, trading_date)
        if pair is None:
            continue
        current, closes = pair
        bound = max(closes) if want == "high" else min(closes)
        slack = abs(bound) * EXTREME_TOLERANCE
        ok = current >= bound - slack if want == "high" else current <= bound + slack
        if ok:
            return []
        checked.append(f"{entry.get('name') or entry.get('ticker')} {current:,.2f} vs "
                       f"{'최고' if want == 'high' else '최저'} {bound:,.2f} ({len(closes)}일)")
    if not checked:
        return []   # 이력이 없어 판단할 수 없다 — 확실하지 않으면 실패시키지 않는다
    word = "최고·신고가" if want == "high" else "최저·신저가"
    return [f"{kind} 제목 '{title}'은 {word}를 말하는데 그린 값이 이력의 {'최대' if want == 'high' else '최소'}가 "
            f"아닙니다: {'; '.join(checked)} — 제목을 데이터에 맞추거나 '근처'처럼 한정하세요."]


def _sector_claim_issues(title: str, rows: list[tuple[str, float, list[dict]]]) -> list[str]:
    """sector_bars 제목이 '반도체만 웃었습니다'처럼 하나만을 주장하는데 같은 방향 막대가 둘 이상이면 실패.
    방향은 ① 제목에 든 업종 이름의 실제 부호 ② 제목의 오름·내림 낱말 ③ 둘 다 없으면 소수 쪽(하나만이라는
    말은 그쪽이 소수라는 뜻) 순으로 정한다. 막대 색이 회색인 ±0.05% 안은 어느 쪽도 아니다(`_color`와 같은 문턱)."""
    if not title or not rows or not _EXCLUSIVE.search(title):
        return []
    ups = [s for s, avg, _ in rows if avg > 0.05]
    downs = [s for s, avg, _ in rows if avg < -0.05]
    subjects = [(s, avg) for s, avg, _ in rows if s in title]   # 제목이 이름을 댄 업종
    if subjects:
        side = "up" if subjects[0][1] > 0.05 else "down" if subjects[0][1] < -0.05 else None
        if side is None:
            return [f"sector_bars 제목 '{title}'이 하나만이라고 말하는 업종 '{subjects[0][0]}'은 "
                    f"{subjects[0][1]:+.2f}%로 막대가 회색입니다 — 제목을 데이터에 맞추세요."]
    elif _UP_WORDS.search(title) and not _DOWN_WORDS.search(title):
        side = "up"
    elif _DOWN_WORDS.search(title) and not _UP_WORDS.search(title):
        side = "down"
    else:
        side = "up" if len(ups) <= len(downs) else "down"
    same = ups if side == "up" else downs
    named = {s for s, _ in subjects}
    others = [s for s in same if s not in named]
    # 이름을 댄 업종이 있으면 그 밖의 같은 방향 업종이 하나라도 있으면 거짓말, 없으면 같은 방향이 둘 이상이면 거짓말.
    if (named and others) or (not named and len(same) >= 2):
        return [f"sector_bars 제목 '{title}'은 하나만 {'올랐다' if side == 'up' else '내렸다'}고 하는데 같은 방향 "
                f"업종이 {len(same)}개입니다: {', '.join(same)} — 제목을 데이터에 맞추세요."]
    return []


def _sector_body_issues(rows: list[tuple[str, float, list[dict]]], body: str) -> list[str]:
    """sector_bars는 업종 전부(한국장 10개)를 늘 그리고 절 본문은 그중 두셋만 말하므로, movers_list처럼
    '절반'을 요구하면 기존 17장이 전부 걸린다(2026-09-25 실측). 여기서는 그린 업종 이름도 대표 종목 이름도
    **하나도** 본문에 없을 때만 실패한다 — 그림이 엉뚱한 절에 붙은 경우(2026-09-16 국채금리 절 밑의 종목 카드)다."""
    labels: list[str] = []
    for sector, _, members in rows:
        labels.append(sector)
        lead = max(members, key=lambda e: abs(e["change_pct"]))
        labels.extend(str(v) for v in (lead.get("name"), lead.get("name_en")) if v)
    if any(_named(label, body) for label in labels):
        return []
    return ["sector_bars가 그린 업종·대표 종목 이름이 절 본문에 하나도 없습니다 — 그림이 이 절 이야기가 아닙니다. "
            "업종을 말하는 절로 옮기거나 본문에 그 업종을 적으세요."]


def _movers_body_issues(picked: list[dict], body: str, notes_out: list[str] | None = None) -> list[str]:
    """그린 종목이 본문에 **하나도** 없으면 실패(엉뚱한 절에 붙은 그림 — 확실한 오류). 절반 넘게 없으면
    `notes_out`에 참고로만 적는다 — 2026-09-25 실측으로 기존 59장 중 30장이 절반 규칙에 걸렸다(루틴이 그림은
    상위 6을 그리고 본문은 두셋만 말하는 습관). 매일 막히는 관문은 루틴이 문턱만 넘는 글을 쓰게 만든다."""
    missing = [str(e.get("name")) for e in picked
               if not (_named(e.get("name"), body) or _named(e.get("name_en"), body))]
    if not picked:
        return []
    if len(missing) == len(picked):
        return [f"movers_list가 그린 {len(picked)}종목({', '.join(missing)})이 절 본문에 하나도 없습니다 — "
                "다른 절에 붙었거나 본문이 그림과 다른 이야기를 합니다. 그림이 말하는 종목을 본문에 적거나 "
                "그림을 그 종목을 다루는 절로 옮기세요."]
    if len(missing) > len(picked) * MOVERS_MISSING_RATIO and notes_out is not None:
        notes_out.append(f"movers_list가 그린 {len(picked)}종목 가운데 {len(missing)}개가 절 본문에 없습니다: "
                         f"{', '.join(missing)} — 그림은 등락 폭 상위를 그리므로 본문도 그 종목을 말하는 것이 좋습니다"
                         "(top_n을 줄이거나 본문에 이름을 적으세요).")
    return []


def collect_spec_issues(kind: str, args: dict, title: str = "", price_data: dict | None = None,
                        section_body: str | None = None, notes_out: list[str] | None = None) -> list[str]:
    """그래픽 spec 하나의 데이터·배치 문제 목록. 비어 있으면 통과.

    `price_data`·`section_body`는 2026-09-25에 더한 선택 인자다 — 없으면 그에 기대는 검사는 건너뛴다
    (옛 호출 `collect_spec_issues(kind, args, title)`은 그대로 돈다).
    """
    issues = []
    title = str(title or args.get("title") or "")
    body = str(section_body or "")
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
        # 기본 캡션은 밸류에이션 문구입니다. 다른 자료에 쓰면서 그대로 두면
        # 그림이 사실과 다른 말을 합니다(2026-09-07: 수급 데이터에 "52주 고점
        # 대비 하락률"이라고 적힌 그림이 나갔습니다).
        legend = args.get("legend") or ""
        unit = args.get("unit", "%")
        looks_valuation = ("52주" in legend or "목표주가" in legend or not legend)
        subtitle = str(args.get("subtitle") or "")
        if looks_valuation and (unit != "%" or "주" in subtitle or "만주" in subtitle):
            issues.append("gap_bars 캡션이 밸류에이션 문구인데 데이터는 다릅니다 — "
                          "legend와 unit을 자료에 맞게 넘기세요.")
        if any(_width(r.get("name", ""), 20) > 330 for r in rows):
            issues.append("gap_bars 종목명이 막대 영역과 겹칩니다.")
    if kind == "flow_compare":
        data = args.get("price_data") or price_data or {}
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

    # ---- 2026-09-25: 제목의 주장·절 본문·표 기하 ----
    trading_date = str((price_data or {}).get("trading_date") or "")
    if kind == "sector_bars" and price_data:
        sector_rows = data_graphics.sector_rows(price_data)
        issues += _sector_claim_issues(title, sector_rows)
        if section_body is not None and sector_rows:
            issues += _sector_body_issues(sector_rows, body)
    if kind == "movers_list" and price_data and section_body is not None:
        try:
            picked = data_graphics.movers_picked(price_data, int(args.get("top_n", 6)),
                                                 args.get("period_days"), args.get("period"))
        except ValueError as exc:
            issues.append(f"movers_list — {exc}")
        else:
            issues += _movers_body_issues(picked, body, notes_out)
    if kind in ("price_history", "stock_spotlight", "number_cards") and price_data:
        entries: list[dict] = []
        try:
            if kind == "price_history":
                entries = [data_graphics._entry_for(price_data, str(args.get("ticker")))]
            elif kind == "stock_spotlight":
                if args.get("ticker"):
                    entries = [data_graphics._entry_for(price_data, str(args["ticker"]))]
                else:   # 렌더러의 기본값과 같이 그날 등락 폭 1위
                    candidates = [e for e in (price_data.get("watchlist") or {}).values()
                                  if e.get("change_pct") is not None]
                    entries = [max(candidates, key=lambda e: abs(float(e["change_pct"])))] if candidates else []
            else:
                tickers = args.get("tickers") or []
                if tickers:
                    entries = [data_graphics._entry_for(price_data, str(t)) for t in tickers]
                elif not args.get("items"):   # 렌더러의 기본값: macro 앞 셋
                    entries = list((price_data.get("macro") or {}).values())[:3]
        except ValueError as exc:
            issues.append(f"{kind} — {exc}")   # 없는 티커는 렌더러도 같은 이유로 멈춘다 — 삼키지 않고 적는다
        if entries:
            issues += _extreme_claim_issues(kind, title, entries, trading_date)
    if kind == "fact_table" and rows and all(isinstance(r, (list, tuple)) and len(r) >= 2 for r in rows):
        if data_graphics.fact_table_fit_size(rows, args.get("columns")) is None:
            smallest = data_graphics.FACT_TABLE_SIZES[-1]
            over = data_graphics.fact_table_overflows(rows, args.get("columns"), smallest)
            issues.append(f"fact_table 셀이 글꼴 {smallest}으로 줄여도 열 폭을 넘어 이웃 셀과 겹칩니다({len(over)}곳): "
                          f"{'; '.join(over[:3])} — 셀 글자를 줄이거나 열을 줄이세요.")
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
