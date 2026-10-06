"""밤 11시 반 증명서 — 그날 독자가 본 것을 다른 원천으로 다시 계산해 텔레그램 한 줄로 보낸다 (2026-10-05).

    python -m src.daily_proof                 # 오늘(KST) 증명 — 텔레그램으로 보내고, 보내지 못하면 1로 끝난다
    python -m src.daily_proof --dry-run       # 보내지 않고 찍기만
    python -m src.daily_proof --day 2026-10-02

왜
--
2026-09-17에 지수 원천이 멈췄는데 2주 넘게 아무도 몰랐다. 글은 나갔고(메우는 장치가 가렸다), 발행 점검은 같은 죽은 원천을
보고 있었고, 경보는 울리지 않았다. 구멍은 셋 — 틀린 값, 몰래 덧대기, 경보 침묵. 이 한 장이 셋을 막는다:
**독자가 실제로 본 것**(시세 파일·본진 화면·오늘 글)을 **코드가 아닌 다른 원천**(ECOS·다음·네이버 전일·나스닥·FRED)으로
다시 계산하고, 돌았어야 할 작업이 돌았는지 보고, 결과를 반드시 한 줄로 보낸다. 증명서가 안 오면 Cloudflare 워커가 자정에
"오지 않았다"를 울린다(`cloudflare/backup_cron/jobs.json`의 watch, daily_proof.yml 실행 성공 여부로 본다).

무엇을 보나
-----------
1. 작업: 클라우드플레어 표(jobs.json)의 깃허브 작업이 오늘 KST 안에 성공했는가 + 루틴은 결과물(오늘 커밋된 원고)로 +
   맥 작업은 맥이 23:22에 커밋하는 `state/mac_beats.json`의 신호로.
2. 숫자: 지수(네이버 목록 정체·ECOS), 종목(다음 장 네이버 '전일'), 미국장(FRED·나스닥) — `close_check` 그대로.
3. 화면: 본진 종목 페이지 무작위 20개의 가격·날짜를 다음과, 홈 코스피를 네이버 목록과 맞춘다.
4. 글: 오늘 시황이 본진에 실제로 있는가(`check_publication`), 네이버·블로그스팟 게시 수(맥 신호).
5. 꼬리표: 오늘 시세 파일에서 두 원천으로 확인된 값의 수.
대조 0건인 묶음은 성공으로 치지 않는다(증명서 자체가 고장 난 것). 발행은 막지 않는다 — 알리기만 한다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import re
import subprocess
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

from src import alert, check_publication, close_check, fetch_kr, fetch_us
from src.site_block import MESSAGE as BLOCKED, is_bot_challenge
from src.stock_db import KRX_HOLIDAYS, KRX_HOLIDAYS_CONFIRMED, KRX_LATE_CLOSE, KRX_LATE_CLOSE_CONFIRMED

# 뉴욕증시 휴장일 — python-holidays 0.105 `financial_holidays("NYSE")`와 같다(2026-10-05; 2026-09-07 노동절엔 실제로 미국장 시세 파일이 없다).
# 미국 휴장일에는 미국장 시세·시황(다음 날 아침)과 프리뷰(그날 밤)를 기대하지 않는다. 해가 바뀌기 전에 다음 해를 더한다.
US_HOLIDAYS = {
    "2026-11-26", "2026-12-25",
    "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31", "2027-06-18", "2027-07-05",
    "2027-09-06", "2027-11-25", "2027-12-24",
}

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
KST = dt.timezone(dt.timedelta(hours=9))
UTC = dt.timezone.utc
REPO = "kimwhey21/kimchi"
BASE = "https://fermata.it.kr"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141 Safari/537.36"}
JOBS = ROOT / "cloudflare" / "backup_cron" / "jobs.json"
MAC_BEATS = ROOT / "state" / "mac_beats.json"
SCREEN_SAMPLE = 20
RUN_WINDOW = (dt.timedelta(minutes=10), dt.timedelta(minutes=150))   # 예약 시각 앞 10분 ~ 뒤 150분 안의 실행을 그 작업으로 본다
# 맥 작업(launchd) — 신호가 언제까지 있어야 하나. 분 단위면 "generated_at 기준 그 안", 시각이면 "그날 그 시각 이후".
MAC_JOBS = {"naver_sync": 30, "blogger_sync": 30, "gsc_queries": "10:30", "gsc_daily_index": "15:10",
            "daily_summary": "22:30", "bench_nightly": "23:10"}
MAC_WEEKLY = {"threads_refresh": (6, "21:30"), "expose_weekly": (0, "08:30"), "search_snapshot": (6, "22:00")}   # (weekday, 시각)


def calendar_issues(today: dt.date) -> list[str]:
    """해마다 사람이 채워야 하는 표가 비었으면 때맞춰 경고한다(2026-10-05) — 고칠 때까지 매일 뜬다.
    한국·미국 휴장일은 12월 1일부터 다음 해, 수능일은 7월 1일부터 그해, 수능 장 시간은 그 2주 전부터 거래소 공고 확인."""
    out = []
    nxt = str(today.year + 1)
    if today.month == 12:
        if not any(d.startswith(nxt) for d in KRX_HOLIDAYS):
            out.append(f"달력: 한국거래소 {nxt}년 휴장일이 stock_db.KRX_HOLIDAYS에 없습니다 — 거래소 공고로 넣으십시오")
        elif nxt not in KRX_HOLIDAYS_CONFIRMED:
            out.append(f"달력: 한국거래소 {nxt}년 휴장일(계산값)을 거래소 공고와 대조하고 KRX_HOLIDAYS_CONFIRMED에 더하십시오")
        if not any(d.startswith(nxt) for d in US_HOLIDAYS):
            out.append(f"달력: 뉴욕증시 {nxt}년 휴장일이 daily_proof.US_HOLIDAYS에 없습니다")
    this_year = [d for d in KRX_LATE_CLOSE if d.startswith(str(today.year))]
    if today.month >= 7 and not this_year:
        out.append(f"달력: {today.year}년 수능일이 stock_db.KRX_LATE_CLOSE에 없습니다 — 그날 장이 16:30에 닫힙니다(평가원 발표 확인)")
    for d in this_year:
        days_left = (dt.date.fromisoformat(d) - today).days
        if 0 <= days_left <= 14 and d not in KRX_LATE_CLOSE_CONFIRMED:
            out.append(f"달력: {d} 수능일 장 시간을 거래소 공고로 확인하고 KRX_LATE_CLOSE_CONFIRMED에 더하십시오({days_left}일 남음)")
    return out


def cron_dow_ok(spec: str, cron_dow: int) -> bool:
    """jobs.json의 days(크론 요일, 0=일요일)와 맞는가."""
    for part in str(spec).split(","):
        a, _, b = part.partition("-")
        if (int(a) <= cron_dow <= int(b)) if b else (cron_dow == int(a)):
            return True
    return False


# ── 1. 작업 ─────────────────────────────────────────────────────────────────────────
def expected_workflow_jobs(day: dt.date, jobs: dict | None = None) -> list[dict]:
    """이 KST 날짜(00:00~24:00)에 눌렀어야 할 깃허브 작업 — [{workflow, label, first(utc), window(utc, utc)}]."""
    jobs = jobs if jobs is not None else json.loads(JOBS.read_text(encoding="utf-8"))
    start = dt.datetime.combine(day, dt.time(0), KST)
    end = start + dt.timedelta(days=1)
    times: dict[tuple[str, str], list[dt.datetime]] = {}
    for job in jobs.get("direct") or []:
        label = job["workflow"] + (f" ({job['inputs']['market']})" if (job.get("inputs") or {}).get("market") else "")
        for hhmm in job["utc"]:
            h, m = map(int, hhmm.split(":"))
            for utc_date in (day - dt.timedelta(days=1), day):
                at = dt.datetime(utc_date.year, utc_date.month, utc_date.day, h, m, tzinfo=UTC)
                if start <= at < end and cron_dow_ok(job["days"], (at.weekday() + 1) % 7):
                    times.setdefault((job["workflow"], label), []).append(at)
    out = []
    for (workflow, label), ats in times.items():
        group: list[dt.datetime] = []
        for at in sorted(ats) + [None]:   # 한 시간 안에 이어지는 누르기(종가 사진 15:31·39·47)는 한 작업으로 묶는다
            if at is not None and (not group or at - group[-1] <= dt.timedelta(hours=1)):
                group.append(at)
                continue
            out.append({"workflow": workflow, "label": label, "first": group[0], "last": group[-1],
                        "window": (group[0] - RUN_WINDOW[0], group[-1] + RUN_WINDOW[1])})
            group = [at] if at is not None else []
    return sorted(out, key=lambda e: e["first"])


def github_runs(since: dt.datetime, token: str | None) -> list[dict]:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "fermata-daily-proof"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    runs: list[dict] = []
    for page in (1, 2, 3):
        r = requests.get(f"https://api.github.com/repos/{REPO}/actions/runs", headers=headers, timeout=30,
                         params={"created": f">={since.astimezone(UTC):%Y-%m-%dT%H:%M:%S}Z", "per_page": 100, "page": page})
        r.raise_for_status()
        batch = r.json().get("workflow_runs") or []
        runs += batch
        if len(batch) < 100:
            break
    return runs


def ran_for_real(run: dict, token: str | None) -> bool:
    """그 실행에서 본 작업(건너뛰기 판단 'guard'를 뺀 잡)이 실제로 돌아 성공했나. 건너뛴 예약도 실행 결론은 success라서(감사 F-037)
    잡을 본다. 조회에 실패하면 True(모르는 것을 실패로 세지 않는다 — 결과물 판정이 따로 있다)."""
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "fermata-daily-proof"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.get(f"https://api.github.com/repos/{REPO}/actions/runs/{run['id']}/jobs", headers=headers, timeout=30)
        r.raise_for_status()
        jobs = r.json().get("jobs") or []
    except (requests.RequestException, ValueError, KeyError) as exc:
        print(f"[안내] 실행 {run.get('id')}의 잡을 조회하지 못했습니다: {exc}")
        return True
    return any(j.get("conclusion") == "success" and not str(j.get("name", "")).startswith("guard") for j in jobs)


def job_status(job: dict, runs: list[dict], real=None) -> str:
    """'ok' | '건너뜀만' | '실패' | '진행 중' | '없음'. `real(run)`이 오면 성공한 실행 중 본 작업이 실제로 돈 것이 있어야 ok —
    건너뛴 예비 예약도 실행 결론은 success다(2026-10-06, 감사 F-037)."""
    path = f".github/workflows/{job['workflow']}"
    lo, hi = job["window"]
    hits = []
    for r in runs:
        if r.get("path") != path:
            continue
        created = dt.datetime.fromisoformat(str(r.get("created_at", "")).replace("Z", "+00:00"))
        if lo <= created <= hi:
            hits.append(r)
    successes = [r for r in hits if r.get("conclusion") == "success"]
    if successes and (real is None or any(real(r) for r in successes)):
        return "ok"
    if successes:
        return "건너뜀만"
    if not hits:
        return "없음"
    return "실패" if all(r.get("status") == "completed" for r in hits) else "진행 중"


def changed_today(day: dt.date, root: Path = ROOT) -> set[str]:
    """오늘(KST) 커밋에서 더해지거나 바뀐 파일 — 루틴의 결과물을 이것으로 본다."""
    since = dt.datetime.combine(day, dt.time(0), KST).isoformat()
    until = (dt.datetime.combine(day, dt.time(0), KST) + dt.timedelta(days=1)).isoformat()
    out = subprocess.run(["git", "log", f"--since={since}", f"--until={until}", "--name-only", "--pretty=format:", "--",
                          "editorial", "reports", "data"], cwd=root, capture_output=True, text=True)
    return {line.strip() for line in out.stdout.splitlines() if line.strip()}


# 원고마다 "이 시각(KST)이 지나야 없다고 말한다" — 낮에 손으로 돌려도 아직 쓸 때가 안 된 글을 빠졌다고 하지 않게(2026-10-05 13:17 시험 실행).
ARTIFACT_DUE = {"한국장 시세": "16:45", "종가 사진": "16:05", "한국장 시황": "17:40", "미국장 시황": "09:00", "미국장 시세": "08:00", "미국장 프리뷰": "22:30", "잡지 3편": "03:30",
                "한국어 가이드": "14:00", "영어 가이드": "12:00", "주말 Checkpoint": "10:00", "주간 결산": "11:00",
                "다음 주 일정": "21:00", "주간 점검": "09:30"}


def expected_artifacts(day: dt.date, changed: set[str], root: Path = ROOT,
                       now: dt.datetime | None = None) -> list[tuple[str, bool, str]]:
    """루틴이 오늘 남겼어야 할 원고 — (이름, 있나, 설명). 요일·휴장일로 기대를 정하고, `now`가 있으면 아직 때가 안 된 것은 뺀다."""
    d = day.isoformat()
    prev = (day - dt.timedelta(days=1)).isoformat()
    wd = day.weekday()   # 월=0
    out: list[tuple[str, bool, str]] = []
    has = lambda rel: (root / rel).exists()   # noqa: E731
    touched = lambda prefix, suffix="": any(p.startswith(prefix) and p.endswith(suffix) for p in changed)   # noqa: E731
    if wd < 5 and d not in KRX_HOLIDAYS:
        # 수집 작업이 '성공'으로 끝나도 결과물이 없을 수 있다(수능용 16:50 실행은 평일엔 아무것도 안 하고 성공한다) — 결과물로 본다(감사 F-036)
        out.append(("한국장 시세", has(f"data/price_kr_{d}.json"), f"data/price_kr_{d}.json"))
        snap = root / "data" / "krx_close" / f"{d}.json"
        try:
            n_close = len((json.loads(snap.read_text(encoding="utf-8")).get("close") or {})) if snap.exists() else 0
        except (OSError, ValueError):
            n_close = 0
        out.append(("종가 사진", n_close >= 2000, f"data/krx_close/{d}.json 전 종목 {n_close}개(2,000개 이상이어야)"))
        out.append(("한국장 시황", has(f"editorial/kr_{d}.json"), f"editorial/kr_{d}.json"))
    if 1 <= wd <= 5 and prev not in US_HOLIDAYS:
        if has(f"data/price_us_{prev}.json"):
            out.append(("미국장 시황", has(f"editorial/us_{prev}.json"), f"editorial/us_{prev}.json"))
        else:
            out.append(("미국장 시세", False, f"data/price_us_{prev}.json 없음 — 미국 휴장이 아니면 수집 실패"))
    if wd < 5 and d not in US_HOLIDAYS:
        out.append(("미국장 프리뷰", has(f"editorial/previews/us_{d}.json"), f"editorial/previews/us_{d}.json"))
    n_mag = len(list((root / "editorial" / "magazine").glob(f"{d}_*.json")))
    out.append(("잡지 3편", n_mag >= 3, f"editorial/magazine/{d}_* {n_mag}편"))
    out.append(("한국어 가이드", touched("editorial/guides/ko_", ".json"), "editorial/guides/ko_* 오늘 커밋"))
    out.append(("영어 가이드", touched("editorial/guides/en_", ".json"), "editorial/guides/en_* 오늘 커밋"))
    if wd in (5, 6):
        out.append(("주말 Checkpoint", touched("editorial/features/", ".json"), "editorial/features/* 오늘 커밋"))
    if wd == 5:
        out.append(("주간 결산", has(f"editorial/weekly/review_{d}.json"), f"editorial/weekly/review_{d}.json"))
    if wd == 6:
        out.append(("다음 주 일정", has(f"editorial/weekly/ahead_{d}.json"), f"editorial/weekly/ahead_{d}.json"))
    if wd == 0:
        out.append(("주간 점검", touched("reports/weekly_", ".md"), "reports/weekly_* 오늘 커밋"))
    if now is not None and now.date() == day:
        out = [row for row in out if now.time() >= dt.time(*map(int, ARTIFACT_DUE[row[0]].split(":")))]
    return out


def mac_issues(beats: dict | None, now: dt.datetime) -> tuple[list[str], int, int]:
    """맥 신호(state/mac_beats.json) — (문제, 기대 수, 정상 수)."""
    if not beats:
        return ["맥 상태 파일(state/mac_beats.json)이 없습니다 — 맥의 23:22 작업이 돌지 않았습니다"], 1, 0
    gen = beats.get("generated_at")
    try:
        made = dt.datetime.fromisoformat(str(gen))
    except (TypeError, ValueError):
        return [f"맥 상태 파일의 시각을 읽지 못했습니다: {gen!r}"], 1, 0
    if made.date() != now.date():
        return [f"맥 상태 파일이 오늘 것이 아닙니다({made:%m-%d %H:%M}) — 맥의 23:22 작업이 돌지 않았습니다"], 1, 0
    issues, expected, ok = [], 0, 0
    last = beats.get("beats") or {}
    rules = dict(MAC_JOBS)
    for name, (wd, hhmm) in MAC_WEEKLY.items():
        if now.weekday() == wd:
            rules[name] = hhmm
    for name, rule in rules.items():
        expected += 1
        when = last.get(name)
        try:
            at = dt.datetime.fromisoformat(str(when)) if when else None
        except ValueError:
            at = None
        if at is None:
            issues.append(f"맥 {name}: 신호 없음")
            continue
        if isinstance(rule, int):
            good = made - at <= dt.timedelta(minutes=rule)
        else:
            h, m = map(int, rule.split(":"))
            good = at.date() == made.date() and at.time() >= dt.time(h, m)
        if good:
            ok += 1
        else:
            issues.append(f"맥 {name}: 마지막 신호 {at:%m-%d %H:%M}")
    return issues, expected, ok


# ── 3. 화면 ─────────────────────────────────────────────────────────────────────────
def page_quote(html: str) -> tuple[float | None, str | None]:
    """종목 페이지의 종가와 'At close' 날짜(ISO)."""
    price = re.search(r'fs-price">₩([\d,]+)', html)
    date = re.search(r"At close: ([A-Z][a-z]{2} \d{1,2}, \d{4})", html)
    close = float(price.group(1).replace(",", "")) if price else None
    iso = dt.datetime.strptime(date.group(1), "%b %d, %Y").date().isoformat() if date else None
    return close, iso


def home_kospi(html: str, today: "dt.date | int") -> tuple[str | None, float | None]:
    """홈 띠의 코스피 날짜·값. 화면에는 연도가 없다 — 읽은 날짜가 오늘보다 뒤면 작년이다(1월 초에 'Dec 30'을 올해로 읽어 거짓 불일치,
    감사 F-150)."""
    m = re.search(r"KOSPI · ([A-Z][a-z]{2} \d{1,2}) close</span><b>([\d,.]+)", html)
    if not m:
        return None, None
    year = today if isinstance(today, int) else today.year
    day = dt.datetime.strptime(f"{m.group(1)} {year}", "%b %d %Y").date()
    if not isinstance(today, int) and day > today:
        day = day.replace(year=year - 1)
    return day.isoformat(), float(m.group(2).replace(",", ""))


def screen_issues(session: requests.Session, codes: list[str], now: dt.datetime) -> tuple[list[str], int, int]:
    """종목 페이지 표본과 홈 띠를 원천과 맞춘다 — (문제, 대조 건수, 맞은 건수).

    종목 값은 다음 일별 시세와 15:3x 종가 사진 **둘 다**와 맞춘다(감사 F-051: 페이지와 같은 원천(다음) 하나와만 맞춰 보면 그 원천이
    틀린 날 못 잡는다). 맞은 건수를 따로 센다 — 전에는 '건수 − 문제 수'라 막힌 페이지를 두 번 빼 음수가 나왔다(감사 F-166)."""
    from src import stock_db
    issues, n, ok = [], 0, 0
    fetch_kr._daum_down.clear()
    home = session.get(BASE + "/", headers=UA, timeout=60)
    if is_bot_challenge(home.text) or home.status_code == 403:
        return [f"본진 홈 HTTP {home.status_code}: {BLOCKED}"], 0
    try:
        rows = fetch_kr._fetch_naver_index_daily("KOSPI")
        day, close = home_kospi(home.text, now.date())
        n += 1
        if not rows:
            issues.append("네이버 코스피 목록이 비어 홈을 대조하지 못했습니다")
        elif day != rows[-1][0] or close is None or abs(close - rows[-1][1]) > 0.011:
            issues.append(f"홈 코스피 {day} {close} / 네이버 목록 {rows[-1][0]} {rows[-1][1]}")
        else:
            ok += 1
    except (requests.RequestException, ValueError) as exc:
        issues.append(f"홈 코스피 대조 실패: {exc}")
    for code in codes:
        try:
            r = session.get(f"{BASE}/stocks/{code}/", headers=UA, timeout=60)
            if is_bot_challenge(r.text) or r.status_code == 403:
                issues.append(f"본진 종목 페이지 HTTP {r.status_code}: {BLOCKED}")
                break
            close, day = page_quote(r.text)
            daum = fetch_kr._fetch_daum_days(code, rows=1)
        except (requests.RequestException, ValueError) as exc:
            issues.append(f"{code}: 화면 대조 실패 — {exc}")
            continue
        n += 1
        if not daum:
            issues.append(f"{code}: 다음 일별 시세 없음")
        elif close is None or day is None:
            issues.append(f"{code}: 페이지에서 가격·날짜를 못 읽었습니다(HTTP {r.status_code})")
        elif day != daum[-1][0] or abs(close - daum[-1][1]) > 0.5:
            issues.append(f"{code}: 화면 {day} ₩{close:,.0f} / 다음 {daum[-1][0]} ₩{daum[-1][1]:,.0f}")
        else:
            snap = (stock_db.snapshot_close(day) or {}).get(code)
            if snap and abs(close - float(snap[0])) > 0.5:
                issues.append(f"{code}: 화면 {day} ₩{close:,.0f} / 15시 반 종가 사진 ₩{float(snap[0]):,.0f}")
            else:
                ok += 1
    return issues, n, ok


def sample_codes(k: int = SCREEN_SAMPLE, root: Path = ROOT, seed: int | None = None) -> list[str]:
    meta = json.loads((root / "data" / "stock_meta.json").read_text(encoding="utf-8"))
    codes = sorted(c for c in meta if re.fullmatch(r"\d{6}", c))
    rng = random.Random(seed)
    return rng.sample(codes, min(k, len(codes)))


# ── 5. 꼬리표 ───────────────────────────────────────────────────────────────────────
def source_tags(doc: dict | None) -> tuple[int, int]:
    """(두 원천으로 확인된 값, 전체) — 시세 파일의 close_sources."""
    if not doc:
        return 0, 0
    entries = list((doc.get("watchlist") or {}).values()) + list((doc.get("macro") or {}).values())
    tagged = [e for e in entries if isinstance(e, dict) and e.get("close_sources")]
    return sum(len(e["close_sources"]) >= 2 for e in tagged), len(tagged)


# ── 한 장 ───────────────────────────────────────────────────────────────────────────
PROOF_STATE = ROOT / "state" / "proof_issues.json"


def _issue_key(issue: str) -> str:
    """숫자만 다른 같은 경고를 같은 것으로 센다."""
    return re.sub(r"[0-9][0-9,.:/%+\-]*", "#", issue)[:140]


def mark_repeats(day: dt.date, issues: list[str], state_path: Path = PROOF_STATE) -> tuple[list[str], dict]:
    """전날에도 있던 경고에 '🔁 N일째'를 붙여 맨 위로 올린다(2026-10-06, 감사 F-076 — 전에는 같은 경고가 매일 반복돼도 강조되지 않고
    다음 날 사라졌다). 돌려주는 것: (표시한 경고 목록, 새 상태)."""
    try:
        prev = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    except (OSError, ValueError) as exc:
        print(f"[경고] 지난 증명서 상태를 읽지 못했습니다: {exc}")
        prev = {}
    yesterday = (day - dt.timedelta(days=1)).isoformat()
    streaks = (prev.get("issues") or {}) if prev.get("day") == yesterday else {}
    if prev.get("day") == day.isoformat():          # 같은 날 다시 돌면(00:05 재실행) 어제 기준을 그대로 쓴다
        streaks = prev.get("base") or {}
    new, marked = {}, []
    for issue in issues:
        key = _issue_key(issue)
        n = int(streaks.get(key, 0)) + 1
        new[key] = n
        marked.append((n, f"🔁 {n}일째 · {issue}" if n >= 2 else issue))
    marked.sort(key=lambda pair: -pair[0])
    return [text for _, text in marked], {"day": day.isoformat(), "issues": new, "base": streaks}


def compose(day: dt.date, parts: dict, issues: list[str]) -> str:
    head = f"{day:%m/%d} 증명 — " + " · ".join(f"{k} {v}" for k, v in parts.items())
    if not issues:
        return "✅ " + head
    lines, size = [], len(head) + 10
    for issue in issues:   # 길면 자르되 몇 건을 잘랐는지 적는다(감사 F-059: 3,800자에서 말없이 끊겼다)
        line = f"- {issue}"
        if size + len(line) > 3700:
            lines.append(f"… 외 {len(issues) - len(lines)}건 잘림(실행 기록에 전부 있다)")
            break
        lines.append(line)
        size += len(line) + 1
    return "⚠️ " + head + "\n" + "\n".join(lines)


def build(day: dt.date, now: dt.datetime, *, session: requests.Session | None = None, token: str | None = None,
          root: Path = ROOT, screens: bool = True) -> tuple[str, list[str], dict]:
    session = session or requests.Session()
    issues: list[str] = []
    parts: dict[str, str] = {}

    # 1. 작업
    jobs = expected_workflow_jobs(day)
    try:
        runs = github_runs(dt.datetime.combine(day, dt.time(0), KST) - dt.timedelta(hours=1), token)
        for j in jobs:   # 같은 작업이 하루 두 번(종목 DB 07:50·17:05)이라 이름표가 아니라 작업마다 적는다(2026-10-05 시험에서 아침 것이 저녁 것에 덮였다)
            j["status"] = job_status(j, runs, real=lambda run: ran_for_real(run, token))
    except Exception as exc:  # noqa: BLE001 — 조회 실패도 한 줄로 적는다
        issues.append(f"깃허브 실행 목록을 받지 못했습니다: {exc}")
    pending = [j for j in jobs if j["last"] + RUN_WINDOW[1] > now]       # 아직 창이 안 닫힌 작업은 세지 않는다
    due = [j for j in jobs if j not in pending]
    bad = [f"작업 {j['label']} ({j['first'].astimezone(KST):%H:%M}): {j.get('status', '?')}"
           for j in due if j.get("status") != "ok"]
    issues += bad
    parts["작업"] = f"{len(due) - len(bad)}/{len(due)}"

    changed = changed_today(day, root)
    arts = expected_artifacts(day, changed, root, now)
    missing = [f"글 없음: {name} ({where})" for name, ok, where in arts if not ok]
    issues += missing
    parts["원고"] = f"{len(arts) - len(missing)}/{len(arts)}"

    beats = json.loads(MAC_BEATS.read_text(encoding="utf-8")) if (root / "state" / "mac_beats.json").exists() else None
    mac_bad, mac_n, mac_ok = mac_issues(beats, now)
    issues += mac_bad
    parts["맥"] = f"{mac_ok}/{mac_n}"

    issues += calendar_issues(day)

    # 2. 숫자
    n_numbers = 0
    key = os.environ.get("ECOS_API_KEY")
    kr_files = sorted((root / "data").glob("price_kr_*.json"))
    kr_doc = json.loads(kr_files[-1].read_text(encoding="utf-8")) if kr_files else None
    if not key:
        issues.append("ECOS_API_KEY가 없어 지수를 대조하지 못했습니다")
    elif kr_doc:
        try:
            issues += close_check.check(kr_doc, key)
            n_numbers += sum(len(((kr_doc.get("macro") or {}).get(t) or {}).get("history", {}).get("dates") or []) for t in ("KS11", "KQ11"))
        except Exception as exc:  # noqa: BLE001
            issues.append(f"지수 대조 실패: {exc}")
    try:
        pcv_day = close_check.pcv_day()
        issues += close_check.check_stocks(root)
        if pcv_day and (root / "data" / f"price_kr_{pcv_day}.json").exists():
            n_numbers += len(json.loads((root / "data" / f"price_kr_{pcv_day}.json").read_text(encoding="utf-8")).get("watchlist") or {})
    except Exception as exc:  # noqa: BLE001
        issues.append(f"종목 대조 실패: {exc}")
    us_files = sorted((root / "data").glob("price_us_*.json"))
    if us_files:
        try:
            us_doc = json.loads(us_files[-1].read_text(encoding="utf-8"))
            us_wrong, us_checked, us_missing = close_check.us_recheck(us_doc)
            issues += us_wrong
            n_numbers += us_checked   # 실제로 공식 원천과 다시 맞춘 수만 센다(감사 F-147: 전에는 꼬리표만 붙은 값까지 셌다)
            if us_missing:
                issues.append(f"미국장 {us_files[-1].stem[-10:]}: 공식 원천으로 다시 맞추지 못한 값 {len(us_missing)}개 — "
                              + ", ".join(us_missing[:10]))
        except Exception as exc:  # noqa: BLE001
            issues.append(f"미국장 대조 실패: {exc}")
    parts["숫자"] = f"{n_numbers:,}건"
    if n_numbers == 0:
        issues.append("숫자 대조 0건 — 증명서가 아무것도 대조하지 못했습니다")

    # 3. 화면
    if screens:
        s_issues, s_n, s_ok = screen_issues(session, sample_codes(root=root), now)
        issues += s_issues
        parts["화면"] = f"{s_ok}/{s_n}"
        if s_n == 0:
            issues.append("화면 대조 0건")

    # 4. 글
    check_site = all(os.environ.get(k) for k in ("WORDPRESS_URL", "WORDPRESS_USERNAME", "WORDPRESS_APP_PASSWORD"))
    sitemap = check_publication._sitemap_post_urls() if check_site else None
    for market in ("kr", "us"):
        try:
            issues += [f"본진 {p}" for p in check_publication.check_market(market, check_site, sitemap)]
        except Exception as exc:  # noqa: BLE001
            issues.append(f"본진 {market} 발행 확인 실패: {exc}")
    if beats:
        posted = beats.get("posted") or {}
        parts["네이버"] = str(posted.get("naver_today", "?")) + (f"(시황 멈춤 {posted['fermata49_paused']}~)" if posted.get("fermata49_paused") else "")
        parts["블로그스팟"] = str(posted.get("blogger_today", "?"))
        n_mag = len(list((root / "editorial" / "magazine").glob(f"{day.isoformat()}_*.json")))
        # 잡지는 07:30·12:30·19:30에 올라간다 — 마지막 편이 올라간 뒤(20:00)에만 센다(낮에 손으로 돌리면 늘 2편이다)
        if n_mag and now.time() >= dt.time(20, 0) and int(posted.get("naver_today") or 0) < min(3, n_mag):
            blocked = int(posted.get("naver_blocked_today") or 0)
            issues.append(f"네이버 잡지 게시 {posted.get('naver_today')}편 — 오늘 원고 {n_mag}편"
                          + (f"(게시 직전 검사에서 막은 원고 {blocked}편)" if blocked else ""))

    # 5. 꼬리표 — 두 시장 모두(감사 F-167: 전에는 한국장만 보고 0/0이면 말이 없었다)
    us_doc_tags = json.loads(us_files[-1].read_text(encoding="utf-8")) if us_files else None
    tag_parts = []
    for label, files, doc_ in (("한", kr_files, kr_doc), ("미", us_files, us_doc_tags)):
        two, total = source_tags(doc_)
        tag_parts.append(f"{label} {two}/{total}")
        if not total and files:
            issues.append(f"두 원천 확인 기록이 하나도 없는 시세 파일 ({files[-1].name}) — 확인 전 코드로 만든 파일입니다")
        elif total and two < total:
            issues.append(f"원천 하나로만 확인한 값 {total - two}개 ({files[-1].name})")
    parts["꼬리표"] = " · ".join(tag_parts)

    return compose(day, parts, issues), issues, parts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="밤 11시 반 증명서")
    parser.add_argument("--day", help="KST 날짜(기본 오늘)")
    parser.add_argument("--dry-run", action="store_true", help="텔레그램으로 보내지 않는다")
    parser.add_argument("--no-screens", action="store_true", help="본진 화면 대조를 건너뛴다(점검용)")
    args = parser.parse_args(argv)
    now = dt.datetime.now(KST)
    # 자정을 넘겨 돈 증명서(워커 00:05 재실행·늦게 온 깃허브 예약)는 전날 증명서다 — 전에는 '다음 날' 것이 됐다(감사 F-190)
    day = dt.date.fromisoformat(args.day) if args.day else (now.date() - dt.timedelta(days=1) if now.hour < 3 else now.date())
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        try:
            token = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=20).stdout.strip() or None
        except (OSError, subprocess.SubprocessError):
            token = None
    as_of = now if day == now.date() else dt.datetime.combine(day, dt.time(23, 59), tzinfo=KST)   # 전날 증명서는 그날 끝 기준으로
    text, issues, parts = build(day, as_of, token=token, screens=not args.no_screens)
    if issues:
        issues, state = mark_repeats(day, issues)
        text = compose(day, parts, issues)
    else:
        state = {"day": day.isoformat(), "issues": {}, "base": {}}
    if not args.dry_run:
        PROOF_STATE.parent.mkdir(parents=True, exist_ok=True)
        PROOF_STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(text)
    if args.dry_run:
        return 0
    # 머리 표시(✅·⚠️)는 alert가 붙인다 — compose의 것을 떼고 보낸다(감사 F-168: ⚠️가 두 번 붙었다)
    if not alert.send(text.removeprefix("⚠️ ").removeprefix("✅ "), "warn" if issues else "ok"):
        print("[오류] 증명서를 텔레그램으로 보내지 못했습니다 — 워커의 자정 확인이 '오지 않았다'를 울립니다.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
