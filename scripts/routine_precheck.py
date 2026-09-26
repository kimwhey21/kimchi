"""루틴의 첫 명령 — 그날 상황을 한 화면(8,000자 이하)으로 (2026-09-25).

왜 (2026-09-25 루틴 실행 감사)
-------------------------------
루틴 실행 기록을 세어 보니 글을 쓰기 전의 낭비가 컸다 — 첫 탐색에 7턴, 어제 원고 JSON을 통째로 읽는 데
4만~8만 자, 예비 실행(17:40·08:40 KST)은 지시문 19K자를 다 읽은 뒤에야 "오늘 원고가 이미 있다"를 알았다.
그래서 루틴이 **첫 명령 하나**로 그날 상황을 알게 한다(`docs/routine_common.md` 절차 0). 첫 줄이
`종료:`면 그 이유를 보고하고 끝내고, `계속:`이면 이 출력이 절차의 재료다.

    python3 -m scripts.routine_precheck kr                 # 한국장 시황 루틴(거래일 = KST 오늘)
    python3 -m scripts.routine_precheck us                 # 미국장 시황 루틴(한국 아침, 거래일 = KST 어제)
    python3 -m scripts.routine_precheck preview            # 밤 프리뷰 루틴(editorial/previews/us_<KST 오늘>.json)
    python3 -m scripts.routine_precheck kr --allow-stale   # 예비 실행: 시세가 어제 것이어도 종료 대신 경고

항목 아홉 — ① 지금 시각 ② 최신 시세 파일(거래일·수집 시각·종목 수·수급 있는 종목 수) ③ 그 거래일 원고 유무
④ 새 거래일 시세 유무(휴장) ⑤ 재료 파일(`data/engines_*.txt`) ⑥ 어제 원고 요약(제목·소제목·확인 지점·
판정·전망 — 원고 통째 읽기를 대체) ⑦ 최근 제목 꼴(`scripts/recent_titles.render`) ⑧ 그래픽 종류·인자
(`src/data_graphics.py`·`src/feature_graphics.py`를 코드에서 읽음) ⑨ 관문이 자주 잡는 낱말
(`src/editorial_quality.py`의 상수에서 뽑음).

조용한 실패를 만들지 않는다(CLAUDE.md): 결론을 정하는 ①~④는 예외를 삼키지 않는다 — 틀리면 죽는 것이
낫다. ⑤~⑨는 항목마다 따로 돌려 실패하면 그 자리에 이유를 찍고 첫 줄 바로 아래에 `확인 실패 N건`으로 센다.

저장소 위치는 `--root` 또는 환경변수 `MARKET_BRIEF_ROOT`로 바꿀 수 있다(테스트가 임시 디렉터리를 쓴다).
데이터(`data/`·`editorial/`)만 root를 따르고, 코드에서 읽는 것(그래픽 빌더·금지 낱말)은 이 스크립트 옆의
`src/`에서 읽는다. `종료:`도 정상 종료(exit 0)다 — 루틴은 첫 줄을 읽는다. `--now 'YYYY-MM-DDTHH:MM'`은
시험용 KST 시각이다.
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
# KST는 서머타임이 없어 고정 오프셋이 정확하다 — zoneinfo/tzdata가 없는 샌드박스에서도 돈다.
KST = dt.timezone(dt.timedelta(hours=9), "KST")
MAX_CHARS = 8000
CLIP = 300
MAX_VOCAB = 20
MARKETS = ("kr", "us", "preview")
WEEKDAYS = "월화수목금토일"
_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})")
_TAG = re.compile(r"<[^>]+>")
_ENGINE_SECTION = re.compile(r"^\[([^\]]+)\]")


# ----------------------------------------------------------------------------- 공통
def default_root() -> Path:
    env = os.environ.get("MARKET_BRIEF_ROOT")
    return Path(env).resolve() if env else REPO_ROOT


def now_kst() -> dt.datetime:
    return dt.datetime.now(KST)


def parse_now(text: str) -> dt.datetime:
    """`--now 'YYYY-MM-DDTHH:MM'`(KST)."""
    return dt.datetime.strptime(text, "%Y-%m-%dT%H:%M").replace(tzinfo=KST)


def _clip(text: object, limit: int = CLIP) -> str:
    """HTML 태그·연속 공백을 걷어 내고 limit 자로 자른다(잘리면 '…')."""
    s = re.sub(r"\s+", " ", _TAG.sub("", str(text or ""))).strip()
    return s if len(s) <= limit else s[: limit - 1] + "…"


def _fmt_dt(when: dt.datetime) -> str:
    return when.astimezone(KST).strftime("%Y-%m-%d %H:%M KST")


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def target_date(market: str, now: dt.datetime) -> dt.date:
    """이 실행이 다뤄야 할 거래일. kr·preview는 KST 오늘, us는 KST 어제(미국 현지 날짜 —
    `docs/routine_us.md`: 한국 화요일 아침 세션이 다루는 거래일은 미국 월요일)."""
    today = now.astimezone(KST).date()
    return today - dt.timedelta(days=1) if market == "us" else today


def last_weekday_before(day: dt.date) -> dt.date:
    """day 직전의 평일 — 프리뷰가 기대하는 '어젯밤 미국장' 거래일(휴장은 모른다)."""
    prev = day - dt.timedelta(days=1)
    while prev.weekday() >= 5:
        prev -= dt.timedelta(days=1)
    return prev


def manuscript_path(root: Path, market: str, date_str: str) -> Path:
    if market == "preview":
        return root / "editorial" / "previews" / f"us_{date_str}.json"
    return root / "editorial" / f"{market}_{date_str}.json"


# ----------------------------------------------------------------------------- ② 시세
def latest_price(root: Path, key: str) -> tuple[Path, dict] | None:
    """가장 최근 data/price_<key>_<날짜>.json — 파일 이름의 날짜 순."""
    files = sorted(p for p in (root / "data").glob(f"price_{key}_*.json") if _DATE.search(p.name))
    if not files:
        return None
    path = files[-1]
    return path, json.loads(path.read_text(encoding="utf-8"))


def git_times(root: Path, rel: str) -> tuple[str, str]:
    """(첫 커밋 = 수집 시각, 마지막 커밋) — `git log -1 --format=%ci`. 시세 파일은 그날 처음 커밋된 뒤
    빈 칸 보강으로 다시 커밋될 수 있어(2026-09-25) 둘 다 보여 준다. git이 없거나 저장소가 아니면 그 이유."""
    out: list[str] = []
    for extra in (["--diff-filter=A"], []):
        try:
            proc = subprocess.run(["git", "-C", str(root), "log", "-1", "--format=%ci", *extra, "--", rel],
                                  capture_output=True, text=True, check=False)
        except FileNotFoundError:
            return ("커밋 이력 없음(git 명령 없음)",) * 2
        if proc.returncode != 0:
            reason = proc.stderr.strip().splitlines()[0] if proc.stderr.strip() else f"rc {proc.returncode}"
            return (f"커밋 이력 없음(git: {reason[:70]})",) * 2
        raw = proc.stdout.strip()
        if not raw:
            out.append("커밋 이력 없음(아직 커밋되지 않음)")
            continue
        try:
            out.append(_fmt_dt(dt.datetime.strptime(raw, "%Y-%m-%d %H:%M:%S %z")))
        except ValueError:
            out.append(f"시각 해석 실패: {raw}")
    return out[0], out[1]


def price_summary(root: Path, path: Path, data: dict) -> tuple[list[str], dict]:
    """시세 파일 한 줄 요약 + 결론에 쓸 숫자."""
    watch = data.get("watchlist") or {}
    entries = list(watch.values()) if isinstance(watch, dict) else list(watch)
    core = sum(1 for e in entries if e.get("source", "core") == "core")
    dynamic = sum(1 for e in entries if e.get("source") == "dynamic")
    flows = sum(1 for e in entries if e.get("foreign_net") is not None)
    macro = data.get("macro") or {}
    missing = data.get("missing") or []
    first, last = git_times(root, _rel(path, root))
    stats = {"n": len(entries), "core": core, "dynamic": dynamic, "flows": flows,
             "trading_date": str(data.get("trading_date") or "")}
    lines = [f"파일: {_rel(path, root)} · 거래일 {stats['trading_date'] or '(trading_date 없음)'}",
             f"수집(첫 커밋): {first} · 마지막 커밋: {last}",
             f"종목 {len(entries)} (코어 {core} · 편입 {dynamic}) · 수급(foreign_net) 있는 종목 {flows} · "
             f"지수·환율 {len(macro)} · missing {len(missing)}"
             + (f" ({', '.join(str(m) for m in missing[:6])})" if missing else "")]
    # 한국장 종목별 수급은 그날 파일에 없고 다음 날 아침 전 거래일 파일에 채워진다(2026-09-26) — 쓸 수 있는 쪽을 보여 준다.
    if path.name.startswith("price_kr_"):
        earlier = sorted(p for p in path.parent.glob("price_kr_*.json") if p.name < path.name)
        if earlier:
            try:
                prev = json.loads(earlier[-1].read_text(encoding="utf-8"))
                pw = list((prev.get("watchlist") or {}).values())
                pf = sum(1 for e in pw if e.get("foreign_net") is not None)
                lines.append(f"전 거래일 {earlier[-1].name}: 종목별 수급 {pf}/{len(pw)} — 종목별 수급은 여기서 '어제(날짜)'로 씁니다"
                             " (그림은 \"day\": \"previous\")")
            except (OSError, ValueError) as exc:
                lines.append(f"전 거래일 파일을 읽지 못했습니다: {earlier[-1].name} ({exc})")
    return lines, stats


# ----------------------------------------------------------------------------- ⑤ 재료
def engines_file(root: Path, key: str, date_str: str) -> tuple[Path | None, bool]:
    """(재료 파일, 그 날짜의 것인가). 그 날짜 파일이 없으면 가장 최근 것을 '다른 날짜'로 돌려준다."""
    exact = root / "data" / f"engines_{key}_{date_str}.txt"
    if exact.exists():
        return exact, True
    files = sorted(p for p in (root / "data").glob(f"engines_{key}_*.txt") if _DATE.search(p.name))
    return (files[-1], False) if files else (None, False)


def engines_summary(root: Path, key: str, date_str: str, hint: str = "") -> str:
    path, exact = engines_file(root, key, date_str)
    wanted = f"data/engines_{key}_{date_str}.txt"
    if path is None:
        return f"{wanted}: 없음(data/engines_{key}_*.txt가 하나도 없음). {hint}".rstrip()
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    warns = [(i + 1, line.strip()) for i, line in enumerate(lines) if "⚠" in line]
    sections = []
    for line in lines:
        found = _ENGINE_SECTION.match(line)
        if found and found.group(1) not in sections:
            sections.append(found.group(1))
    head = (f"{wanted}: {len(lines)}줄 · ⚠ {len(warns)}건" if exact
            else f"{wanted}: 없음 — 가장 최근 {_rel(path, root)}(다른 날짜, {len(lines)}줄, ⚠ {len(warns)}건). {hint}".rstrip())
    out = [head, "절: " + (" ".join(f"[{s}]" for s in sections) if sections else "없음")]
    for no, line in warns[:5]:
        out.append(f"  {no}행: {_clip(line, 110)}")
    if warns:
        out.append("  ⚠가 붙은 절의 결과는 쓰지 않는다 — '못 받았다'와 '0건'은 다르다.")
    return "\n".join(out)


# ----------------------------------------------------------------------------- ⑥ 어제 원고
def previous_daily(root: Path, market: str, date_str: str) -> tuple[Path, dict, str] | None:
    """editorial/<market>_<d>.json 가운데 d < date_str인 마지막 것 → (경로, 원고, 비고).
    저장소 루트에서는 `src.editorial_judgment.previous_manuscript`(같은 규칙)를 쓴다 — 관문과 같은 답을
    내려는 것이다. 임시 루트(테스트)나 그 모듈을 못 부르는 환경에서는 파일에서 직접 읽고 비고에 이유를 적는다."""
    files = sorted(p for p in (root / "editorial").glob(f"{market}_*.json") if p.stem < f"{market}_{date_str}")
    if not files:
        return None
    path, note = files[-1], ""
    if root.resolve() == REPO_ROOT:
        try:
            from src.editorial_judgment import previous_manuscript
        except ImportError as exc:
            note = f"(src.editorial_judgment를 못 불러 파일에서 직접 읽음: {exc})"
        else:
            doc = previous_manuscript(market, date_str)
            if doc is not None:
                return path, doc, note
            note = "(previous_manuscript가 None을 돌려줘 파일에서 직접 읽음)"
    return path, json.loads(path.read_text(encoding="utf-8")), note


def previous_preview(root: Path, date_str: str) -> tuple[Path, dict] | None:
    files = sorted(p for p in (root / "editorial" / "previews").glob("us_*.json") if p.stem < f"us_{date_str}")
    if not files:
        return None
    return files[-1], json.loads(files[-1].read_text(encoding="utf-8"))


def _check_text(check: object) -> str:
    if isinstance(check, dict):
        due, what = check.get("due"), check.get("what")
        return f"{due}까지 — {_clip(what)}" if due else _clip(what) or "없음"
    return _clip(check) or "없음"


def _review_text(review: object) -> str:
    if isinstance(review, dict):
        return (f"{review.get('of_date', '?')} 글 판정 {review.get('verdict', '?')} — "
                f"{_clip(review.get('result'))}")
    return _clip(review) or "없음"


def summarize(doc: dict, *, review: bool = True, outlook: bool = True) -> list[str]:
    """제목·소제목·closing.check·review·outlook만(각 300자 이내). 본문은 읽지 않는다."""
    ko = doc.get("ko") or {}
    heads = [str(s.get("heading", "")) for s in ko.get("narrative") or []]
    lines = [f"제목: {ko.get('title', '')}",
             (f"소제목 {len(heads)}개: " + " / ".join(f"{i}.{h}" for i, h in enumerate(heads, 1))) if heads
             else "소제목: 없음",
             "확인 지점(closing.check): " + _check_text((ko.get("closing") or {}).get("check"))]
    if review:
        lines.append("어제 판정(review): " + _review_text(doc.get("review") or ko.get("review")))
    if outlook:
        section = ko.get("outlook") or {}
        lines.append(f"전망(outlook) 「{section.get('heading', '')}」: {_clip(section.get('body'))}" if section
                     else "전망(outlook): 없음")
    return lines


# ----------------------------------------------------------------------------- ⑦ 최근 제목
def recent_titles_text(market: str, root: Path) -> str:
    """`scripts/recent_titles.render`가 있으면 그 출력 그대로(저장소 루트일 때), 아니면 피드의 최근 다섯 편 제목만."""
    from scripts import recent_titles
    render = getattr(recent_titles, "render", None)
    if render is not None and root.resolve() == recent_titles.ROOT.resolve():
        return render(market)
    from src import title_feed
    rows = title_feed.rows_before(count=5, root=root)
    if not rows:
        return "최근 글 없음(editorial/ 피드가 비어 있음)"
    return "\n".join(f"[{r['slot'].strftime('%m-%d %H:%M')} {r['series']}] {r['title']}" for r in rows)


# ----------------------------------------------------------------------------- ⑧ 그래픽
def _func_args(fn: ast.FunctionDef, skip: frozenset[str]) -> tuple[list[str], list[str]]:
    a = fn.args
    positional = list(a.posonlyargs) + list(a.args)
    split = len(positional) - len(a.defaults)
    required = [x.arg for x in positional[:split] if x.arg not in skip]
    optional = [x.arg for x in positional[split:] if x.arg not in skip]
    for x, default in zip(a.kwonlyargs, a.kw_defaults):
        if x.arg in skip:
            continue
        (optional if default is not None else required).append(x.arg)
    return required, optional


def _string_set(tree: ast.Module, name: str) -> set[str]:
    for node in tree.body:
        if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Set)
                and any(isinstance(t, ast.Name) and t.id == name for t in node.targets)):
            return {e.value for e in node.value.elts if isinstance(e, ast.Constant)}
    return set()


def graphic_kinds(path: Path, *, registry: str | None, skip: frozenset[str]) -> list[tuple[str, list[str], list[str]]]:
    """코드를 import하지 않고(PIL이 없어도 돌게) 소스를 파싱해 (종류, 필수 인자, 선택 인자)를 뽑는다.
    registry가 있으면 그 사전(`BUILDERS = {"kind": func}`)의 순서대로, 없으면 밑줄 없는 최상위 함수 전부."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    if registry:
        table = None
        for node in tree.body:
            if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict)
                    and any(isinstance(t, ast.Name) and t.id == registry for t in node.targets)):
                table = node.value
        if table is None:
            raise ValueError(f"{path.name}에 {registry} 사전이 없습니다")
        pairs = []
        for key, value in zip(table.keys, table.values):
            if not (isinstance(key, ast.Constant) and isinstance(value, ast.Name)):
                raise ValueError(f"{path.name} {registry}: 문자열→함수 이름 꼴이 아닌 항목이 있습니다")
            pairs.append((str(key.value), value.id))
    else:
        pairs = [(name, name) for name in funcs if not name.startswith("_")]
    out = []
    for kind, fname in pairs:
        if fname not in funcs:
            raise ValueError(f"{path.name}: 그래픽 {kind}의 함수 {fname}를 찾을 수 없습니다")
        required, optional = _func_args(funcs[fname], skip)
        out.append((kind, required, optional))
    return out


def priceless_kinds() -> set[str]:
    tree = ast.parse((SRC / "data_graphics.py").read_text(encoding="utf-8"))
    return _string_set(tree, "PRICELESS_KINDS")


def graphics_text(market: str) -> str:
    daily = graphic_kinds(SRC / "data_graphics.py", registry="BUILDERS",
                          skip=frozenset({"price_data", "output_path", "lang"}))
    priceless = priceless_kinds()

    def row(kind: str, required: list[str], optional: list[str]) -> str:
        return f"- {kind}: 필수 {'·'.join(required) or '없음'} → 선택 {'·'.join(optional) or '없음'}"

    lines: list[str] = []
    if market == "preview":
        lines.append("프리뷰 그래픽은 원고 최상위 `graphics` 목록: {\"kind\", \"alt\", \"args\": {...}, \"section\": <절 번호, "
                     "0부터>, \"price_file\": \"data/price_us_<날짜>.json\"} — 시황 그래픽에는 price_file 필수"
                     f"(단 {'·'.join(sorted(priceless))}는 시세 없이 그린다). 종류별 인자:")
        lines.append("[기준표·프리뷰 전용 src/feature_graphics.py — cover 계열은 표지]")
        for kind, required, optional in graphic_kinds(SRC / "feature_graphics.py", registry=None,
                                                      skip=frozenset({"output_path"})):
            lines.append(row(kind, required, optional))
        lines.append("[시황 그래픽 src/data_graphics.py — price_file 필요]")
    else:
        lines.append("시황 그래픽은 절 안에 `\"graphic\": {\"kind\": ..., 인자 그대로}`로 적는다(price_data는 자동, "
                     f"{'·'.join(sorted(priceless))}는 조사 값으로 그리므로 source 필수). 종류별 인자(src/data_graphics.py):")
    for kind, required, optional in daily:
        lines.append(row(kind, required, optional))
    return "\n".join(lines)


# ----------------------------------------------------------------------------- ⑨ 낱말
def vocabulary_cards() -> list[str]:
    """관문(editorial_quality)이 잡는 낱말을 코드 상수에서 뽑는다 — 목록을 여기 베껴 두면 한쪽만 고쳐진다."""
    from src import editorial_quality as eq
    cards: list[str] = []
    # 같은 안내문을 가진 낱말(눌렸/눌리, 배 갈렸/갈린, 넉 달/넉달, 코앞/문턱)은 한 장으로 — 따로 세면
    # 18+3=21장이라 20장 상한에 마지막 장이 조용히 잘렸다(실측).
    groups: dict[str, list[str]] = {}
    for word, why in eq._NEVER_USED.items():
        groups.setdefault(why, []).append(word)
    for why, words in groups.items():
        alts = re.findall(r"`([^`]+)`", why)
        label = "/".join(words)
        cards.append(f"{label}→{'/'.join(alts)}" if alts else label)
    cards.append("등락의 내렸/내린/내려→하락했습니다(금리 인하·끌어내리다·내려가다는 그대로)")
    jargon = [w for w in eq._INTERNAL_JARGON.pattern.strip("()").split("|") if not w.isascii()]
    cards.append("·".join(jargon) + "→'우리가 보는 종목 가운데'(우리 장치 이름은 글에 안 쓴다)")
    cards.append("'…남은/빠진/만의 자리입니다'→동사로 끝내거나 '수준'")
    if len(cards) > MAX_VOCAB:
        raise ValueError(f"낱말 카드가 {len(cards)}장 — 상한 {MAX_VOCAB}장을 넘습니다. 안내문이 같은 낱말을 묶거나 상한을 올리십시오.")
    return cards


def vocabulary_text(width: int = 110) -> str:
    """카드를 ' · '로 이어 붙이되 줄은 카드 경계에서만 바꾼다 — textwrap은 카드 한가운데를 잘랐다(실측)."""
    lines: list[str] = []
    for card in vocabulary_cards():
        if lines and len(lines[-1]) + 3 + len(card) <= width:
            lines[-1] += " · " + card
        else:
            lines.append(card)
    return "\n".join(lines)


# ----------------------------------------------------------------------------- 조립
def _run_section(title: str, fn, failures: list[str]) -> str:
    """⑤~⑨ 항목 하나. 실패하면 그 자리에 이유를 찍고 failures에 센다 — 삼키지 않는다."""
    try:
        body = fn()
    except Exception as exc:  # noqa: BLE001 — 이유를 찍고 첫 줄 아래에 센다(조용한 실패 금지)
        failures.append(f"{title}: {type(exc).__name__}: {exc}")
        body = f"확인 실패 — {type(exc).__name__}: {exc}"
    return f"## {title}\n{body}"


def build(market: str, *, root: Path | None = None, now: dt.datetime | None = None,
          allow_stale: bool = False) -> str:
    if market not in MARKETS:
        raise ValueError(f"market은 {', '.join(MARKETS)} 중 하나입니다: {market!r}")
    root = (root or default_root()).resolve()
    now = (now or now_kst()).astimezone(KST)
    key = "us" if market == "preview" else market
    today = now.date()
    target = target_date(market, now)
    target_s = target.isoformat()
    warnings: list[str] = []
    failures: list[str] = []
    sections: list[str] = []

    # ① 지금
    sections.append("## ① 지금\n"
                    f"KST {now.strftime('%Y-%m-%d %H:%M')} ({WEEKDAYS[now.weekday()]}) · 오늘 {today.isoformat()} · "
                    f"다루는 거래일 {target_s}"
                    + {"kr": "(한국 날짜 그대로)", "us": "(미국 현지 = KST 어제)", "preview": "(오늘 밤 프리뷰)"}[market])

    # ② 최신 시세
    price = latest_price(root, key)
    stats: dict = {}
    if price is None:
        price_lines = [f"data/price_{key}_*.json: 없음"]
        price_date = ""
    else:
        price_lines, stats = price_summary(root, *price)
        price_date = stats["trading_date"]
        if stats["n"] and stats["dynamic"] == 0:
            warnings.append("시세 파일에 편입(dynamic) 종목이 없음 — 편입 종목 수집이 막힌 날이다. 글은 쓰되 완료 보고에 적는다.")
    if market == "preview":
        kr_today = root / "data" / f"price_kr_{today.isoformat()}.json"
        price_lines.append(f"오늘 한국장 종가 data/price_kr_{today.isoformat()}.json: "
                           + ("있음" if kr_today.exists() else "없음(휴장이거나 미수집 — 10절 '내일 아침 한국장'은 가장 최근 파일로)"))
    sections.append("## ② 최신 시세\n" + "\n".join(price_lines))

    # ③ 원고 · ④ 새 거래일
    manuscript = manuscript_path(root, market, target_s)
    manuscript_rel = _rel(manuscript, root)
    exists = manuscript.exists()
    lines = [f"{'오늘 밤 프리뷰' if market == 'preview' else '원고'} {manuscript_rel}: "
             + ("있음 → 종료" if exists else "없음 → 씁니다")]
    verdict: str
    if exists:
        verdict = f"종료: 원고 있음 {manuscript_rel}"
    elif price is None:
        verdict = f"종료: 시세 파일 없음(data/price_{key}_*.json)"
    elif market == "preview":
        expected = last_weekday_before(today)
        if price_date < expected.isoformat():
            warnings.append(f"어젯밤 미국장(마지막 평일 {expected}) 시세가 없음 — 최신은 {price_date}. 휴장이었으면 정상, "
                            "아니면 07:20 수집 실패. 가격대 숫자는 최신 파일로만.")
            lines.append(f"어젯밤 미국장 시세: 없음(최신 {price_date}, 기대 {expected})")
        else:
            lines.append(f"어젯밤 미국장 시세: 있음(거래일 {price_date})")
        lines.append("오늘 밤 미국 휴장 여부는 이 도구가 모른다 — 지시문대로 WebSearch \"NYSE holidays 2026\"으로 확인.")
        verdict = (f"계속: preview {target_s} — 어젯밤 미국장 시세 {price_date}({stats.get('n', 0)}종목), "
                   f"오늘 밤 프리뷰 없음({manuscript_rel}) → 씁니다")
    elif price_date != target_s:
        lines.append(f"새 거래일 시세: 없음 — 최신 파일의 거래일은 {price_date}(휴장이거나 수집 실패)")
        if allow_stale:
            warnings.append(f"시세 파일 거래일 {price_date} ≠ 다루는 거래일 {target_s} — 휴장이면 보고하고 종료, 수집 실패면 "
                            f"장 마감 뒤에만 자구책(`python3 -m src.main --market {key} --fetch-only`)으로 받는다(--allow-stale).")
            verdict = (f"계속: {market} 거래일 {target_s} — 시세 없음(최신 {price_date}, --allow-stale), "
                       f"원고 없음({manuscript_rel})")
        else:
            verdict = f"종료: 새 거래일 시세 없음(거래일 {price_date})"
    else:
        lines.append(f"새 거래일 시세: 있음(거래일 {price_date} = 다루는 거래일)")
        verdict = (f"계속: {market} 거래일 {target_s} — 시세 있음({stats['n']}종목·수급 {stats['flows']}), "
                   f"원고 없음({manuscript_rel}) → 씁니다")
    sections.append("## ③ 원고 · ④ 새 거래일\n" + "\n".join(lines))

    if verdict.startswith("종료:"):
        # 첫 줄이 종료면 루틴은 더 읽지 않는다 — 아래 항목을 붙여 봐야 낭비다.
        return "\n".join([verdict] + [f"경고: {w}" for w in warnings] + [""] + sections)

    # ⑤ 재료
    engines_date = today.isoformat() if market == "preview" else target_s
    hint = ("(story_material.yml 20:40 KST 예약 → 실제 커밋 21:00~21:05. 없으면 `python3 -m src.story_engines all "
            "--market us > data/engines_us_<오늘>.txt`를 시도하되 커밋하지 않는다)" if market == "preview"
            else f"(없을 때만 `python3 -m src.story_engines all --market {key}`을 직접 돌린다)")
    sections.append(_run_section("⑤ 재료", lambda: engines_summary(root, key, engines_date, hint), failures))

    # ⑥ 어제 원고 요약
    def yesterday_text() -> str:
        out: list[str] = []
        if market == "preview":
            found = previous_daily(root, "us", today.isoformat())
            if found is None:
                out.append("어제 미국장 원고: 없음")
            else:
                path, doc, note = found
                out.append(f"[어제 미국장 {_rel(path, root)}] {note}".rstrip())
                out += ["  " + line for line in summarize(doc)]
            prev = previous_preview(root, today.isoformat())
            if prev is None:
                out.append("어제 프리뷰: 없음")
            else:
                out.append(f"[어제 프리뷰 {_rel(prev[0], root)}] — 오늘 2절이 이 확인 지점을 판정한다")
                out += ["  " + line for line in summarize(prev[1], review=False, outlook=False)]
            if found is None and engines_file(root, key, engines_date)[0] is None:
                warnings.append("어제 미국장 원고도 재료 파일도 없음 — 확인된 일정까지 없으면 보고하고 종료(routine_preview「쓰지 않는 날」).")
            return "\n".join(out)
        found = previous_daily(root, market, target_s)
        if found is None:
            return f"없음(editorial/{market}_*.json 가운데 {target_s} 이전 것이 없음)"
        path, doc, note = found
        return "\n".join([f"[{_rel(path, root)}] {note}".rstrip()] + summarize(doc))

    sections.append(_run_section("⑥ 어제 원고 요약(제목·소제목·확인 지점·판정·전망만 — JSON을 통째로 읽지 않는다)",
                                 yesterday_text, failures))

    # ⑦ 최근 제목 꼴
    sections.append(_run_section("⑦ 최근 제목 꼴(scripts.recent_titles)", lambda: recent_titles_text(market, root), failures))

    # ⑧ 그래픽
    sections.append(_run_section("⑧ 그래픽 종류·인자(코드에서 읽음)", lambda: graphics_text(market), failures))

    # ⑨ 낱말
    sections.append(_run_section("⑨ 관문이 자주 잡는 낱말(src/editorial_quality.py 상수, 앞→뒤로 바꿔 쓴다)",
                                 vocabulary_text, failures))

    head = [verdict] + [f"경고: {w}" for w in warnings]
    if failures:
        head.append(f"확인 실패 {len(failures)}건: " + " | ".join(failures))
    text = "\n".join(head + [""] + sections)
    if len(text) > MAX_CHARS:
        tail = (f"\n(… {MAX_CHARS:,}자 상한으로 뒤를 잘랐습니다 — 잘린 것은 뒤쪽 항목(낱말·그래픽)이고 결론·시세·원고·"
                "재료·어제 요약은 위에 다 있습니다)")
        text = text[: MAX_CHARS - len(tail)].rstrip() + tail
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="루틴의 첫 명령 — 그날 상황 한 화면. 첫 줄이 `계속:` 또는 `종료: <이유>`.")
    parser.add_argument("market", choices=MARKETS)
    parser.add_argument("--allow-stale", action="store_true",
                        help="시세 파일 거래일이 오늘과 달라도 종료하지 않고 경고만(예비 실행의 자구책 수집용)")
    parser.add_argument("--root", type=Path, default=None, help="저장소 위치(기본: 이 스크립트의 저장소 또는 $MARKET_BRIEF_ROOT)")
    parser.add_argument("--now", default=None, help="시험용 KST 시각 'YYYY-MM-DDTHH:MM'")
    args = parser.parse_args(argv)
    now = parse_now(args.now) if args.now else None
    print(build(args.market, root=args.root, now=now, allow_stale=args.allow_stale))
    return 0


if __name__ == "__main__":
    sys.exit(main())
