#!/bin/bash
# 더블클릭으로 실행하는 런처.
# 1) 미국장/한국장을 고르면 시황을 생성하고
# 2) 블로그용 텍스트를 클립보드에 복사하고
# 3) 미리보기 HTML을 브라우저로 엽니다.
set -e

cd "$(dirname "$0")/.."

echo "어떤 시장을 생성할까요?"
select MARKET in "미국장 (us)" "한국장 (kr)"; do
  case $REPLY in
    1) MARKET_CODE="us"; break ;;
    2) MARKET_CODE="kr"; break ;;
    *) echo "1 또는 2를 입력하세요." ;;
  esac
done

echo ""
echo "▶ $MARKET_CODE 시황 생성을 시작합니다... (1~2분 정도 걸릴 수 있어요)"
echo ""

python3 -m src.main --market "$MARKET_CODE"

DATE_STR=$(date +%Y-%m-%d)
HTML_PATH="output/${MARKET_CODE}_${DATE_STR}.html"
TEXT_PATH="output/${MARKET_CODE}_${DATE_STR}.txt"

if [ -f "$TEXT_PATH" ]; then
  pbcopy < "$TEXT_PATH"
  echo ""
  echo "✅ 블로그용 텍스트를 클립보드에 복사했습니다. 이제 붙여넣기(Cmd+V)만 하면 됩니다."
fi

if [ -f "$HTML_PATH" ]; then
  open "$HTML_PATH"
  echo "🖼  미리보기 페이지를 브라우저로 열었습니다: $HTML_PATH"
fi

echo ""
echo "아무 키나 누르면 창이 닫힙니다..."
read -n 1 -s
