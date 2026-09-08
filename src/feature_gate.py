"""기준표 원고의 흩어진 검사를 한 번에 실행하는 발행 전 관문입니다.

벤치마크 대조 둘은 의도적으로 사람 판단을 남기는 보고 도구다. 따라서 이 모듈은
그 둘도 반드시 실행해 결과를 돌려주되, 고유명사를 0회라고 한 것만으로 발행을
막지는 않는다. 형식·문체·기준표 규칙은 예외로 막는다.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts import check_against_benchmark, compare_to_benchmark
from src import editorial_quality, editorial_title, feature_checks, source_check


class FeatureGateError(ValueError):
    pass


def run(doc: dict, graphics: int, path: Path | None = None) -> dict:
    """다섯 검사를 모두 호출하고, 막아야 할 오류와 참고 보고를 분리한다."""
    ko = doc.get("ko") or doc
    blocking = []
    notes: list[str] = []
    blocking.extend(editorial_quality.collect_issues(ko))
    blocking.extend(editorial_title.collect_issues(
        ko, kind=str(doc.get("series") or "기준표"), notes_out=notes))   # 제목·소제목, 모든 글 공통
    blocking.extend(feature_checks.collect_issues(doc, graphics=graphics, notes_out=notes))
    # 오늘 이 글이 막힌 이유는 문장이 아니라 재료였습니다. 재료를 안 뽑고 쓴 글은
    # 여기서 멈춥니다 — 사람이 엔진 돌리기를 기억하는 데 기대지 않습니다.
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
