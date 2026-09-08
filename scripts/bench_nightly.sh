#!/bin/bash
# 벤치마크 야간 작업 (이 맥의 launchd가 매일 23:10에 돌립니다 — kr.it.fermata.benchwatch)
#
#   1. scripts.bench_watch          재테크농부 새 글 본문 수집 (~/.market-brief-bench/, 커밋 안 함)
#   2. compare_to_benchmark --export-stats   집계표 data/benchmark_stats.json 갱신
#   3. 집계값이 실제로 바뀐 날만 그 파일 하나를 커밋·푸시 (클라우드 루틴이 이 표를 읽습니다)
#
# 왜: 코퍼스는 유료 콘텐츠라 이 컴퓨터에만 있고, 클라우드 루틴은 집계표만 읽습니다.
# 2026-09-08까지 집계표는 사람이 손으로 내보낼 때만 갱신됐습니다(마지막 9/7).
# 사용자 승인(2026-09-08 "진행해")으로 수집 직후 자동 갱신하게 했습니다.
set -u
cd /Users/mac/Downloads/market-brief || exit 1
PY=/usr/local/bin/python3
GIT=/usr/bin/git
export PATH=/usr/local/bin:/usr/bin:/bin:$PATH

echo "=== $(date '+%Y-%m-%d %H:%M') bench_nightly 시작 ==="
$PY -m scripts.bench_watch
rc=$?
if [ $rc -eq 2 ]; then
  echo "[경고] 벤치마크 로그인 세션이 풀렸습니다 — 'python3 -m scripts.bench_login'으로 다시 저장하십시오. 집계표는 기존 본문으로 갱신합니다."
elif [ $rc -ne 0 ]; then
  echo "[경고] 수집이 종료 코드 $rc 로 끝났습니다. 집계표는 기존 본문으로 갱신합니다."
fi

$PY -m scripts.compare_to_benchmark --export-stats || { echo "[오류] 집계 내보내기 실패"; exit 1; }

# 날짜(measured_at)만 바뀐 날은 커밋하지 않습니다 — 집계값·편수가 바뀐 날만.
if $PY - <<'EOF'
import json, subprocess, sys
new = json.load(open("data/benchmark_stats.json", encoding="utf-8"))
shown = subprocess.run(["/usr/bin/git", "show", "HEAD:data/benchmark_stats.json"],
                       capture_output=True, text=True).stdout
old = json.loads(shown) if shown.strip() else {}
changed = (new.get("stats"), new.get("posts")) != (old.get("stats"), old.get("posts"))
sys.exit(0 if changed else 1)
EOF
then
  $GIT add data/benchmark_stats.json
  $GIT commit -q -F - <<EOF
벤치마크 집계 갱신: $(date +%Y-%m-%d) (야간 자동, scripts/bench_nightly.sh)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
EOF
  for attempt in 1 2 3; do
    if $GIT pull -q --rebase --autostash origin main && $GIT push -q origin HEAD:main; then
      echo "집계표 커밋·푸시 완료 ($(date '+%H:%M'))"
      exit $rc
    fi
    echo "[안내] push 실패 — 재시도 $attempt/3"
    $GIT rebase --abort 2>/dev/null || true
    sleep 20
  done
  echo "[오류] 집계표를 푸시하지 못했습니다. 커밋은 로컬에 남아 있어 다음 날 밤에 다시 올라갑니다."
  exit 1
else
  $GIT checkout -q -- data/benchmark_stats.json
  echo "집계값 변화 없음 — 커밋하지 않습니다 ($(date '+%H:%M'))"
fi
exit $rc
