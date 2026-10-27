"""기준표 원고의 흩어진 검사를 한 번에 실행하는 발행 전 관문입니다.

벤치마크 대조 둘은 의도적으로 사람 판단을 남기는 보고 도구다. 따라서 이 모듈은
그 둘도 반드시 실행해 결과를 돌려주되, 고유명사를 0회라고 한 것만으로 발행을
막지는 않는다. 형식·문체·기준표 규칙은 예외로 막는다.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts import check_against_benchmark, compare_to_benchmark
from src import editorial_facts, editorial_quality, editorial_title, evidence_check, feature_checks, source_check, title_feed, unsplash_ping

ROOT = Path(__file__).resolve().parent.parent
# 시리즈가 사는 폴더. 같은 목록에 나란히 보이는 최근 제목과 뼈대를 대조할 때 쓴다.
SERIES_FOLDER = {"기준표": "features", "프리뷰": "previews",
                 "주간 결산": "weekly", "다음 주 일정": "weekly",   # 주말 편성(2026-09-12)
                 "가이드": "guides", "Guide": "guides", "이벤트": "events",   # 유입 편성(2026-09-12)
                 "매거진": "magazine",                                  # 두 번째 네이버 블로그(2026-09-13)
                 "칼럼": "columns"}                                     # 오늘의 한 편(2026-10-13, 시황 블로그 하루 한 편)


class FeatureGateError(ValueError):
    pass


def column_price_files(doc: dict, root: Path = ROOT) -> tuple[Path | None, Path | None]:
    """칼럼이 대조할 시세 파일 — (그날 한국장, 원고 날짜 전 닷새 안의 가장 최근 미국장). 없으면 None.
    주말·휴장일(2026-10-17부터 칼럼이 매일 돈다)에는 그날 한국장 파일이 없으므로 사흘 안의 가장 최근 한국장 파일(대개 금요일)과 대조한다."""
    import datetime as dt
    day = str(doc.get("date") or "")
    kr = root / "data" / f"price_kr_{day}.json"
    try:
        floor = (dt.date.fromisoformat(day) - dt.timedelta(days=5)).isoformat()
        kr_floor = (dt.date.fromisoformat(day) - dt.timedelta(days=3)).isoformat()
    except ValueError:
        return (kr if kr.exists() else None), None
    if not kr.exists():
        recent = sorted(q for q in (root / "data").glob("price_kr_*.json") if f"price_kr_{kr_floor}" <= q.stem < f"price_kr_{day}")
        kr = recent[-1] if recent else kr
    us = sorted(q for q in (root / "data").glob("price_us_*.json") if f"price_us_{floor}" <= q.stem < f"price_us_{day}")
    return (kr if kr.exists() else None), (us[-1] if us else None)


def recent_titles(doc: dict, path: Path | None = None, count: int = 5) -> list[str]:
    """독자가 보는 최근 제목들. 프리뷰·기준표·주간·이벤트는 네이버 피드 한 줄(`title_feed` — 한국장·미국장 시황과
    섞여 보인다, 2026-09-18), 가이드·잡지는 같은 시리즈 목록. 이 원고 자신(같은 파일·같은 slug)은 뺀다(2026-09-09)."""
    import json
    series = str(doc.get("series") or "기준표")
    if series in title_feed.FEED_SERIES:
        return title_feed.feed_titles(doc, path, count, root=ROOT)
    folder = ROOT / "editorial" / SERIES_FOLDER.get(series, "features")
    rows: list[tuple[str, str]] = []
    for candidate in sorted(folder.glob("*.json")):
        if path is not None and candidate.resolve() == Path(path).resolve():
            continue
        try:
            other = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if doc.get("slug") and other.get("slug") == doc.get("slug"):
            continue
        if str(other.get("series") or "기준표") != series:
            continue   # 한 폴더에 시리즈가 둘일 수 있다(주간 결산·다음 주 일정, 한국어·영어 가이드) — 틀 대조는 시리즈별
        title = str((other.get("ko") or {}).get("title", ""))
        if title:
            rows.append((str(other.get("date", "")), title))
    rows.sort()
    return [title for _, title in rows[-count:]]


def placement_issues(doc: dict) -> list[str]:
    """그림 자리(2026-10-27). 발행(`publish_feature._build_graphics`)은 한 절에 두 장이면 멈추고, 없는 절 번호면
    본진·네이버 모두 그 그림을 조용히 뺀다 — 10/26 칼럼이 세 장을 4절에 몰아 네이버에 못 올라갔고, 지난 원고 29편은
    마지막 그림을 절 수와 같은 번호에 붙여 그 그림이 빠진 채 나갔다. 커밋 전에 여기서 막는다."""
    if str(doc.get("series") or "") == "매거진":
        return []   # 잡지는 publish_feature를 거치지 않는다(표지 사진 한 장)
    count = len((doc.get("ko") or doc).get("narrative") or [])
    issues, seen, featured = [], {}, 0
    for index, spec in enumerate(doc.get("graphics") or [], 1):
        if spec.get("featured"):
            featured += 1
        if "section" not in spec:
            if not spec.get("featured"):
                issues.append(f"그림 {index}({spec.get('kind')}) — section도 featured도 없습니다")
            continue
        try:
            section = int(spec["section"])
        except (TypeError, ValueError):
            issues.append(f"그림 {index}({spec.get('kind')}) — section이 숫자가 아닙니다: {spec['section']!r}")
            continue
        if not 0 <= section < count:
            issues.append(f"그림 {index}({spec.get('kind')}) — section {section}은 없는 절입니다(절은 0~{count - 1}, 0부터 셉니다) — "
                          "이대로면 그림이 빠진 채 나갑니다")
        elif section in seen:
            issues.append(f"그림 {index}({spec.get('kind')}) — {section}절에 그림 {seen[section]}이 이미 있습니다 — 한 절에 한 장, 다른 절로 옮기십시오")
        else:
            seen[section] = index
    if featured > 1:
        issues.append(f"대표 그림(featured)이 {featured}장입니다 — 하나만 둡니다")
    return [f"그림 자리 — {i}" for i in issues]


def run(doc: dict, graphics: int, path: Path | None = None) -> dict:
    """다섯 검사를 모두 호출하고, 막아야 할 오류와 참고 보고를 분리한다."""
    ko = doc.get("ko") or doc
    blocking = []
    notes: list[str] = []
    blocking.extend(placement_issues(doc))
    if not str(doc.get("series") or "").strip():
        # 시리즈 칸이 없으면 머리말·태그·관문은 기준표(Checkpoint)로 보는데 발행은 공개로 올린다(2026-09-26 점검) —
        # 한국어 Checkpoint가 본진에 공개로 나가고 알림까지 갈 수 있으므로 커밋 전에 막는다.
        blocking.append("series가 없습니다 — \"기준표\"·\"프리뷰\"·\"가이드\"·\"Guide\" 등 시리즈를 적으십시오.")
    if path is not None and str(doc.get("series") or "") != "매거진":
        # 글 주소(2026-09-26): 한글이 섞였거나 비면 발행이 멈춘다 — 커밋 전에 여기서 먼저 막는다.
        from src import publish_feature
        try:
            publish_feature._slug(doc, Path(path))
        except ValueError as exc:
            blocking.append(f"주소 — {exc}")
    if str(doc.get("lang") or "ko") == "en":
        # 영어 가이드(2026-09-12): 한국어 문체·제목 문법 검사는 맞지 않는다. 영어 전용 검사 + 출처 수만 막는다.
        blocking.extend(feature_checks.collect_issues_en(doc, graphics=graphics))
        blocking.extend(source_check.collect_issues(doc))
        if blocking:
            raise FeatureGateError("English guide gate failed:\n- " + "\n- ".join(blocking))
        return {"blocking": [], "notes": notes, "sources": source_check.collect(doc),
                "benchmark_words": [], "benchmark_shape": None}
    blocking.extend(editorial_quality.collect_issues(ko))
    blocking.extend(editorial_title.collect_issues(
        ko, kind=str(doc.get("series") or "기준표"), notes_out=notes,
        recent_titles=recent_titles(doc, path), date=str(doc.get("date") or "")))   # 제목·소제목, 모든 글 공통 (같은 목록의 최근 제목과 뼈대 대조)
    blocking.extend(feature_checks.collect_issues(doc, graphics=graphics, notes_out=notes))
    if str(doc.get("series") or "") == "매거진":
        blocking.extend(feature_checks.magazine_issues(doc))   # 잡지 꼴(브리핑·코너·출처·사진), 2026-09-13
    if str(doc.get("series") or "") == "칼럼":
        blocking.extend(feature_checks.hook_issues(doc))   # 잡지와 같은 훅 꼴 — 소제목 없는 도입·물음·길안내 없음
        # 숫자 대조(시황과 같은 검사, 1위 종목 누락은 보지 않는다): 그날 한국장 시세 파일과, 칼럼이 미국장도 다루므로(2026-10-16)
        # 어젯밤 미국장 시세 파일(원고 날짜 전 가장 최근 것)과도. 미국장 파일은 프리뷰처럼 '오늘'을 다른 날로 본다. 둘 다 없으면 막는다.
        kr_file, us_file = column_price_files(doc)
        if kr_file is None and us_file is None:
            blocking.append(f"숫자 — 대조할 시세 파일이 없습니다(한국장 {doc.get('date')}·그 전 닷새 안의 미국장) — 장이 열린 날에만 씁니다")
        if kr_file is not None:
            found = editorial_facts.collect_issues(ko, json.loads(kr_file.read_text(encoding="utf-8")), lang="ko", require_lead=False)
            blocking.extend(f"숫자 — [{kr_file.stem}] {i}" for i in found)
        if us_file is not None:
            found = editorial_facts.collect_issues(ko, json.loads(us_file.read_text(encoding="utf-8")), lang="ko",
                                                   other_day=editorial_facts._OTHER_DAY_PREVIEW, require_lead=False)
            blocking.extend(f"숫자 — [{us_file.stem}] {i}" for i in found)
    blocking.extend(feature_checks.naver_issues(doc))   # 네이버용 본문(2026-09-12): 오래 읽히는 시리즈는 완전한 글로
    if str(doc.get("series") or "") == "프리뷰":
        # 숫자 대조(2026-09-25). 프리뷰에는 이 검사가 없었다 — 9/23·9/24 프리뷰가 덮어써진 시세로 나갔고 아무도 몰랐다.
        # 시황과 같은 원칙으로 막는다(숫자만 막는다). 밸류에이션 문장(목표주가 대비·52주 고점·PER·프리마켓·%포인트)은
        # 등락률이 아니므로 건너뛴다(editorial_facts._NOT_A_MOVE). 시세 파일을 못 찾은 것도 막는다 — 조용히 통과시키지 않는다.
        try:
            files = editorial_facts.preview_price_files(doc)
            blocking.extend(f"숫자 — {i}" for i in editorial_facts.collect_issues_for_preview(doc, files, notes_out=notes))
        except ValueError as exc:
            blocking.append(f"숫자 — {exc}")
    # 오늘 이 글이 막힌 이유는 문장이 아니라 재료였습니다. 재료를 안 뽑고 쓴 글은
    # 여기서 멈춥니다 — 사람이 엔진 돌리기를 기억하는 데 기대지 않습니다.
    if str(doc.get("series") or "") == "주간 결산":
        # 2026-10-06: 주간 숫자의 바탕(시세 파일 이력)이 날마다 확인한 종가와 같은지, 원고의 주간 등락률이 그 계산과 같은지
        try:
            blocking.extend(f"주간 숫자 — {i}" for i in editorial_facts.weekly_issues(doc))
        except (OSError, ValueError, KeyError) as exc:
            blocking.append(f"주간 숫자 — 대조하지 못했습니다: {exc}")
    # 2026-10-06(감사 F-030·F-052): 'M월 D일 코스피는 N%'처럼 날짜가 박힌 숫자를 그날 두 원천으로 확인한 시세 파일과 대조
    blocking.extend(f"날짜 숫자 — {i}" for i in editorial_facts.dated_issues(doc))
    blocking.extend(f"사진 — {i}" for i in unsplash_ping.missing_ids(doc))   # Unsplash 사진은 번호와 함께(2026-10-06)
    blocking.extend(f"목표주가 — {i}" for i in editorial_facts.target_phrase_issues(doc))   # 2026-10-06: 뜻이 뒤집힌 문장 83곳
    blocking.extend(f"내부 이름 — {i}" for i in editorial_facts.internal_name_issues(doc))   # 2026-10-06: 'story_engines' 등 16편
    # 인용·숫자의 출처 원문(2026-10-06, 감사: 잡지 9편 중 6편에서 출처에 없는 숫자·인용) — 잡지는 숫자·인용 모두, 나머지는 인용만
    blocking.extend(f"근거 — {i}" for i in evidence_check.evidence_issues(
        doc, numbers=str(doc.get("series") or "") == "매거진",
        events=str(doc.get("series") or "") in ("다음 주 일정", "이벤트")))   # 사건 낱말 문장에도 근거(감사 F-029)
    blocking.extend(source_check.collect_issues(doc))

    benchmark_words = []
    if check_against_benchmark.CORPUS.exists():
        benchmark_words = check_against_benchmark.check(
            doc, check_against_benchmark.load_corpus()
        )
    else:
        benchmark_words = ["벤치마크 코퍼스 없음: 단어 대조는 보고만 건너뜀"]

    benchmark_shape = compare_to_benchmark.measure(ko)
    result = {"blocking": blocking, "notes": notes,
              "sources": source_check.collect(doc),
              "benchmark_words": benchmark_words,
              "benchmark_shape": benchmark_shape}
    if blocking:
        raise FeatureGateError("기준표 발행 검사 실패:\n- " + "\n- ".join(blocking))
    return result


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--graphics", required=True, type=int)
    args = parser.parse_args(argv)
    doc = json.loads(Path(args.path).read_text(encoding="utf-8"))
    # 사람이 읽는 화면에 파이썬 스택트레이스를 뱉지 않습니다. 어디가 어긋났는지만
    # 보여주고 종료 코드로 실패를 알립니다.
    try:
        result = run(doc, args.graphics, Path(args.path))
    except FeatureGateError as error:
        print(str(error))
        return 1

    print("통합 게이트 통과")
    sources = result["sources"]
    print(f"[외부 출처] {sources['distinct']}곳 — " + " · ".join(
        f"{k}: {', '.join(v)}" for k, v in sources["found"].items()) or "없음")
    for note in result["notes"]:
        print("[참고] " + note)
    for issue in result["benchmark_words"]:
        print("[벤치마크 단어 참고] " + issue)
    if result["benchmark_shape"]:
        print("[벤치마크 형태 참고] " + str(result["benchmark_shape"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
