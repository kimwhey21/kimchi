"""지난 한 주 점검 — 매주 월요일 아침 사장님께 드리는 한 장 (2026-09-08, 제안 7번).

무엇을 재는가
-------------
- 발행: 시장별 거래일(시세 파일) 대비 원고 수, 빠진 날
- 글의 꼴: 절 수·소제목 길이·시각자료 수·제목 길이와 등락률 개수·문장 수·'습니다' 비율을
  재테크농부 집계(data/benchmark_stats.json)와 나란히
- 판단: Fermata's Take 확인 지점·어제 판정·초보자 설명·기관 인용이 있는 글의 비율
- 성적표: 이번 주에 판정된 확인 지점의 적중률, 기한이 지났는데 판정이 없는 것
- 검색 수치(노출·클릭)는 여기서 못 잰다 — Site Kit 화면은 관리자 로그인이 필요하다.
  Claude 세션이 화면을 읽어 덧붙인다.

    python -m scripts.weekly_review                      # 지난주(월~일) → reports/weekly_<일요일>.md
    python -m scripts.weekly_review --week-ending 2026-09-13
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import re
import statistics
import sys
from pathlib import Path

import yaml

from src import editorial_title

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"
_PCT = re.compile(r"\d+(?:\.\d+)?\s*%")
_INSTITUTION = re.compile(r"증권|리포트|목표주가|투자의견|애널리스트|골드만|JP모건|모건스탠리|씨티|UBS")


def _kst_today() -> dt.date:
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=9)).date()


def _window(week_ending: dt.date) -> tuple[dt.date, dt.date]:
    start = week_ending - dt.timedelta(days=6)
    return start, week_ending


def _in(date_str: str, start: dt.date, end: dt.date) -> bool:
    try:
        return start <= dt.date.fromisoformat(str(date_str)[:10]) <= end
    except ValueError:
        return False


def _post_stats(doc: dict) -> dict:
    ko = doc.get("ko") or {}
    sections = ko.get("narrative") or []
    headings = [re.sub(r"^\s*\d{1,2}\.\s*", "", str(s.get("heading", ""))) for s in sections]
    text = " ".join(str(s.get("body", "")) for s in sections)
    text += " " + " ".join(str(s.get("body", "")) for s in (ko.get("insight_section") or {}).get("stories") or [])
    text += " " + str((ko.get("closing") or {}).get("body", ""))
    plain = re.sub(r"<[^>]+>", "", text)
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", plain) if s.strip()]
    polite = sum(1 for s in sentences if s.strip().endswith(("습니다.", "니다.", "습니다", "니다")))
    graphics = sum(1 for s in sections if s.get("graphic")) + len(doc.get("graphics") or [])
    photos = sum(1 for s in sections if s.get("photo")) + (1 if doc.get("featured_photo") else 0)
    title = str(ko.get("title", ""))
    return {
        "title": title, "date": str(doc.get("date", "")), "market": doc.get("market") or doc.get("series", "기준표"),
        "sections": len(sections),
        "heading_len": statistics.median(len(h) for h in headings) if headings else 0,
        "visuals": graphics + photos,
        "title_len": len(title), "title_pct": len(_PCT.findall(title)),
        "sentences": len(sentences), "polite_pct": round(100 * polite / len(sentences)) if sentences else 0,
        "has_check": bool(((ko.get("closing") or {}).get("check") or {}).get("due")),
        "has_review": bool(doc.get("review")),
        "beginner": "초보자" in plain, "institution": bool(_INSTITUTION.search(plain)),
        # 같은 틀 반복(2026-09-09, 네 번째 지적) — 제목의 끝말·대비 꼴, 소제목의 문장 비율
        "title_last": editorial_title.last_word(title),
        "title_contrast": editorial_title.title_frame(title)["contrast"],
        "sentence_pct": round(100 * sum(1 for h in headings if editorial_title.heading_shape(h).endswith("문장"))
                              / len(headings)) if headings else 0,
    }


def collect(week_ending: dt.date) -> dict:
    start, end = _window(week_ending)
    daily = []
    for path in sorted(glob.glob(str(ROOT / "editorial" / "*.json"))):
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        if "price_data" in doc and _in(doc.get("date", ""), start, end):
            daily.append(_post_stats(doc))
    features = []
    for path in sorted(glob.glob(str(ROOT / "editorial" / "features" / "*.json")) + glob.glob(str(ROOT / "editorial" / "previews" / "*.json"))):
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        if _in(doc.get("date", ""), start, end):
            features.append(_post_stats(doc))
    # 빠진 날: 시세 파일은 있는데 원고가 없는 거래일
    missed = []
    for market in ("kr", "us"):
        for path in glob.glob(str(ROOT / "data" / f"price_{market}_*.json")):
            day = Path(path).stem.split("_")[-1]
            if _in(day, start, end) and not (ROOT / "editorial" / f"{market}_{day}.json").exists():
                missed.append(f"{market} {day}")
    # 성적표
    judged, pending_overdue = [], []
    sb = ROOT / "data" / "scoreboard.yaml"
    if sb.exists():
        for article in yaml.safe_load(sb.read_text(encoding="utf-8")) or []:
            for check in article.get("checks", []):
                verdict = check.get("verdict", "pending")
                if verdict != "pending" and _in(str(check.get("checked", "")), start, end):
                    judged.append(verdict)
                if verdict == "pending" and str(check.get("due", ""))[:10] < end.isoformat():
                    pending_overdue.append(f"{article.get('title', '')[:30]} — {check.get('due')}")
    bench = {}
    bs = ROOT / "data" / "benchmark_stats.json"
    if bs.exists():
        bench = json.loads(bs.read_text(encoding="utf-8")).get("stats", {})
    return {"start": start, "end": end, "daily": daily, "features": features, "missed": sorted(missed),
            "judged": judged, "pending_overdue": pending_overdue, "bench": bench}


def _med(rows: list[dict], key: str):
    values = [r[key] for r in rows if isinstance(r.get(key), (int, float))]
    return round(statistics.median(values), 1) if values else None


def latest_search_report(reports_dir: Path | None = None) -> list[str]:
    """가장 최근 `reports/search_<날짜>.md`의 표 (2026-09-12, 사용자 승인 "주간 검색 성적 기록").

    구글·네이버 색인 수와 노출·클릭은 관리자 화면에서만 읽히므로, 이 맥의 일요일 22:00 작업
    (`~/.market-brief-google/search_snapshot.py`)이 읽어 저장소에 남기고 여기서는 그 파일을 싣는다.
    기준선 2026-09-12: 구글 색인 11, 네이버 색인 1 — 늘지 않으면 검색엔진이 새 글을 못 찾는 것이다.
    """
    folder = reports_dir or REPORTS
    files = sorted(folder.glob("search_*.md"))
    if not files:
        return []
    body = files[-1].read_text(encoding="utf-8").splitlines()
    rows = [l for l in body if l.startswith("|")]
    previous = sorted(folder.glob("search_*.json"))
    note = []
    if len(previous) >= 2:
        try:
            a = json.loads(previous[-2].read_text(encoding="utf-8")); b = json.loads(previous[-1].read_text(encoding="utf-8"))
            note = [f"- 지난 기록({a.get('date')}) 대비: 구글 색인 {a.get('google_indexed')} → {b.get('google_indexed')}, "
                    f"네이버 색인 {a.get('naver_indexed')} → {b.get('naver_indexed')}, "
                    f"네이버 블로그 이웃 {a.get('naver_blog_neighbors')} → {b.get('naver_blog_neighbors')}"]
        except (OSError, ValueError):
            note = []
    note += naver_milestones(previous[-1] if previous else None)
    return [f"기록일 {files[-1].stem.replace('search_', '')}", ""] + rows + [""] + note


def naver_milestones(latest_json: Path | None) -> list[str]:
    """네이버 블로그 성장 조건(2026-09-12, 사용자 "네이버도 애드포스트, 본진만큼 중요"): 글 50편이 되면 인플루언서 신청,
    개설 90일(2026-12-09)이 지나면 애드포스트 신청 — 사람이 할 일이라 보고서가 시점을 알려 준다."""
    if not latest_json:
        return []
    try:
        b = json.loads(latest_json.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    posts = b.get("naver_blog_posts")
    lines = []
    if isinstance(posts, int):
        if posts >= 50:
            lines.append(f"- 네이버 블로그 글 {posts}편 — 50편 조건을 넘었습니다. **네이버 인플루언서(경제) 신청**을 사장님 계정으로 할 때입니다.")
        else:
            lines.append(f"- 네이버 블로그 글 {posts}편 — 인플루언서·애드포스트 조건(50편)까지 {50 - posts}편.")
    try:
        d_day = (dt.date(2026, 12, 9) - dt.date.fromisoformat(str(b.get("date")))).days
        lines.append("- 애드포스트 신청 가능일 2026-12-09" + (f" (D-{d_day})" if d_day > 0 else " — **지났습니다. 신청하십시오.**"))
    except (TypeError, ValueError):
        pass
    return lines


def render(data: dict) -> tuple[str, str]:
    """(보고서 markdown, 알림용 요약 8줄 안팎)."""
    d, f = data["daily"], data["features"]
    bench = data["bench"]
    b = lambda key: (bench.get(key) or [None])[0]
    polite_bench = b("'습니다'로 끝")
    lines = [f"# 지난 한 주 점검 — {data['start']} ~ {data['end']}", ""]
    lines += [f"시황 {len(d)}편, 기준표·프리뷰 {len(f)}편. 빠진 거래일: {', '.join(data['missed']) or '없음'}.", ""]
    lines += ["## 글의 꼴 (중앙값) — 재테크농부와 나란히", "",
              "| 항목 | 우리 시황 | 재테크농부 |", "|---|---:|---:|",
              f"| 절(소제목) 수 | {_med(d, 'sections')} | {b('소제목 수')} |",
              f"| 소제목 길이(자) | {_med(d, 'heading_len')} | {b('소제목 길이(중앙값)')} |",
              f"| 시각자료 수 | {_med(d, 'visuals')} | 10 |",
              f"| 문장 수 | {_med(d, 'sentences')} | {b('문장 수')} |",
              f"| '습니다' 비율(%) | {_med(d, 'polite_pct')} | {polite_bench} |",
              f"| 제목 길이(자) | {_med(d, 'title_len')} | 25 |",
              f"| 제목의 등락률 개수 | {_med(d, 'title_pct')} | 0 |", ""]
    if d:
        pct = lambda key: round(100 * sum(1 for r in d if r[key]) / len(d))
        lines += ["## 판단이 있는 글", "",
                  f"- 확인 지점(Fermata's Take) 있음: {pct('has_check')}%",
                  f"- 어제 판정 있음: {pct('has_review')}%",
                  f"- 초보자 설명 있음: {pct('beginner')}%",
                  f"- 증권사·기관 인용 있음: {pct('institution')}%", ""]
    if d:
        by_market: dict[str, list[dict]] = {}
        for r in sorted(d, key=lambda r: r["date"]):
            by_market.setdefault(str(r["market"]), []).append(r)
        repeats = sum(1 for rows in by_market.values() for a, b in zip(rows, rows[1:]) if a["title_last"] == b["title_last"])
        contrast = sum(1 for r in d if r["title_contrast"])
        lines += ["## 같은 틀 반복 (2026-09-09부터 잰다)", "",
                  f"- 바로 앞 글과 같은 말로 끝난 제목: {repeats}건 (0이어야 한다)",
                  f"- 대비 꼴(`…했는데 …는 오히려`) 제목: {contrast}편 / {len(d)}편 (재테크농부 104편 중 4편)",
                  f"- 소제목 중 문장(`~습니다`·`~다`) 비율 중앙값: {_med(d, 'sentence_pct')}% (재테크농부 절반 안팎, 관문은 60%까지)", ""]
    judged = data["judged"]
    if judged:
        hit = judged.count("hit"); mixed = judged.count("mixed"); miss = judged.count("miss")
        lines += ["## 성적표", "", f"- 이번 주 판정 {len(judged)}건: 적중 {hit} · 절반 {mixed} · 빗나감 {miss} (적중률 {round(100 * (hit + 0.5 * mixed) / len(judged))}%)"]
    else:
        lines += ["## 성적표", "", "- 이번 주 판정된 확인 지점 없음"]
    if data["pending_overdue"]:
        lines += [f"- 기한이 지났는데 판정이 없는 것 {len(data['pending_overdue'])}건: " + "; ".join(data["pending_overdue"][:5])]
    lines += ["", "## 글 목록", "", "| 날짜 | 시장 | 제목 | 절 | 시각자료 | 확인 지점 |", "|---|---|---|---:|---:|:---:|"]
    for r in sorted(d + f, key=lambda r: r["date"]):
        lines.append(f"| {r['date']} | {r['market']} | {r['title'][:40]} | {r['sections']} | {r['visuals']} | {'○' if r['has_check'] else '—'} |")
    lines += ["", "## 검색 성적", ""] + (latest_search_report() or ["- 아직 기록 없음 (이 맥의 일요일 22:00 작업 `search_snapshot.py`가 reports/search_<날짜>.md를 만든다)"]) + [""]
    lines += ["## 사장님께", "", "이번 주 가장 좋았던 글 하나와 가장 아쉬웠던 글 하나를 짚어 주세요. 그 판단을 규칙에 넣습니다.", ""]
    summary = [f"지난 한 주({data['start']}~{data['end']}): 시황 {len(d)}편, 기준표·프리뷰 {len(f)}편, 빠진 거래일 {len(data['missed'])}일.",
               f"절 수 {_med(d, 'sections')}(재테크농부 {b('소제목 수')}), 시각자료 {_med(d, 'visuals')}(10), 제목 등락률 {_med(d, 'title_pct')}개(0).",
               (f"성적표 판정 {len(judged)}건, 적중률 {round(100 * (judged.count('hit') + 0.5 * judged.count('mixed')) / len(judged))}%." if judged else "성적표 판정 없음.")]
    if data["pending_overdue"]:
        summary.append(f"판정 안 된 확인 지점 {len(data['pending_overdue'])}건.")
    summary.append("이번 주 최고·최악 글 하나씩 짚어 주세요.")
    return "\n".join(lines), "\n".join(summary)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--week-ending", help="일요일 날짜(YYYY-MM-DD). 기본: 지난 일요일(KST)")
    parser.add_argument("--out", type=Path, help="보고서 폴더(기본 reports/)")
    args = parser.parse_args(argv)
    today = _kst_today()
    if args.week_ending:
        end = dt.date.fromisoformat(args.week_ending)
    else:
        end = today - dt.timedelta(days=(today.weekday() + 1) % 7 or 7)   # 지난 일요일
    data = collect(end)
    report, summary = render(data)
    out_dir = args.out or REPORTS
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"weekly_{end.isoformat()}.md"
    out.write_text(report, encoding="utf-8")
    print(summary)
    print(f"\n보고서: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
