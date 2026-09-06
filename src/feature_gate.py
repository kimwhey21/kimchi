"""기준표 원고의 흩어진 검사를 한 번에 실행하는 발행 전 관문입니다.

벤치마크 대조 둘은 의도적으로 사람 판단을 남기는 보고 도구다. 따라서 이 모듈은
그 둘도 반드시 실행해 결과를 돌려주되, 고유명사를 0회라고 한 것만으로 발행을
막지는 않는다. 형식·문체·기준표 규칙은 예외로 막는다.
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts import check_against_benchmark, compare_to_benchmark
from src import editorial_quality, editorial_title, feature_checks


class FeatureGateError(ValueError):
    pass


def run(doc: dict, graphics: int, path: Path | None = None) -> dict:
    """다섯 검사를 모두 호출하고, 막아야 할 오류와 참고 보고를 분리한다."""
    ko = doc.get("ko") or doc
    blocking = []
    blocking.extend(editorial_quality.collect_issues(ko))
    blocking.extend(editorial_title.collect_issues(ko))
    blocking.extend(feature_checks.collect_issues(doc, graphics=graphics))

    benchmark_words = []
    if check_against_benchmark.CORPUS.exists():
        benchmark_words = check_against_benchmark.check(
            doc, check_against_benchmark.load_corpus()
        )
    else:
        benchmark_words = ["벤치마크 코퍼스 없음: 단어 대조는 보고만 건너뜀"]

    benchmark_shape = compare_to_benchmark.measure(ko)
    result = {"blocking": blocking, "benchmark_words": benchmark_words,
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
    result = run(doc, args.graphics, Path(args.path))
    print("통합 게이트 통과")
    for issue in result["benchmark_words"]:
        print("[벤치마크 단어 참고] " + issue)
    if result["benchmark_shape"]:
        print("[벤치마크 형태 참고] " + str(result["benchmark_shape"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
