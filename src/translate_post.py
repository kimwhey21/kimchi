"""한국장(kr) 결과물을 해외 독자를 위한 영어 버전으로 각색합니다.

배경: 외국인통합계좌 제도로 미국 개인투자자가 한국 주식을 직접 살 수 있게 됐지만,
영어로 된 한국 증시 코멘터리는 수요 대비 공급이 적은 니치입니다. 미국장 포스트는
이미 블룸버그·로이터 등과 정면경쟁이라 승산이 없어서, 한국장 포스트만 영문화합니다.

단순 직역이 아니라 한국 시장을 모르는 해외 독자를 가정하고 각색합니다 (예: "코스닥"
-> "KOSDAQ (Korea's tech-heavy secondary board, similar to Nasdaq)"). insight_section은
한국에 특화된 소재만 남기고 나머지는 뺍니다 — 해외 독자에게 실제로 차별화되는 부분이라.

숫자·ticker는 이 단계에서 새로 만들지 않습니다 — generate_post.py가 이미 만든 값을
그대로 옮기도록 프롬프트에 명시합니다. 혹시 옮기는 과정에서 ticker가 틀어지더라도
render_html.py에 이미 있는 "모르는 ticker는 경고 후 카드에서 제외" 안전장치가
크래시 없이 흡수합니다.

실행하려면 ANTHROPIC_API_KEY 환경변수가 필요합니다 (generate_post.py와 동일).
"""
from __future__ import annotations

import json

import anthropic

from src.generate_post import _extract_text, _parse_json_response, _strip_cite_tags

SYSTEM_PROMPT = """당신은 한국 증시 마감 시황을, 한국 시장을 잘 모르는 해외(영어권)
개인투자자를 위해 각색하는 편집자입니다. 사용자가 이미 완성된 한국어 시황 콘텐츠를
JSON으로 통째로 줄 것입니다. 이걸 단순히 직역하지 말고, 아래 규칙에 따라 영어로
다시 씁니다.

# 어떻게 각색할지
- "코스닥"처럼 한국 특유의 용어가 나오면 짧은 설명을 덧붙이세요.
  예: "KOSDAQ (Korea's tech-heavy secondary board, similar to Nasdaq)".
  "사이드카", "매도 사이드카" 같은 한국 특유의 제도·용어도 마찬가지로 짧게
  설명을 곁들이세요.
- 톤은 원문과 동일하게 담백한 뉴스 앵커 톤을 유지하세요. 특정 매매를 추천하거나
  "이렇게 하세요/대응하세요" 식 처방적 조언은 절대 쓰지 마세요 (원문에 이미
  이 원칙이 적용돼 있으니 영어로 옮길 때도 그대로 지키면 됩니다).
- "jumped", "soared like a rocket" 같은 은유적·구어체 표현보다는 "rose/fell",
  "gained/lost", "surged/plunged", "advanced/declined" 같은 표준적인 금융
  영어 표현을 쓰세요.

# 절대 규칙 (숫자·식별자 보존)
- ticker 값(theme_section.highlights[].ticker, stock_section.featured_tickers의
  각 값)은 원문과 정확히 동일한 문자열로 그대로 두세요. 번역·변형하지 마세요.
- insight_section.stories[].image_query 값도 원문 그대로 두세요 (이미 영어
  검색어이며, 사진 검색에 그대로 재사용됩니다).
- insight_section.stories[].icon 값(server, robot, coin, gold, scale, chip,
  battery, shield 중 하나)도 원문 그대로 두세요. 번역하지 마세요.
- chart.data 배열의 숫자는 절대 바꾸지 마세요. chart.labels가 한글이면 영어로
  옮기고, 이미 숫자·영문(예: 티커, 연도)이면 그대로 두세요. chart.unit도 이미
  기호/영문(%, GW 등)이면 그대로 두고, 한글 단위(달러, 원 등)만 영어로 바꾸세요.
- calendar[].date는 날짜 자체는 바꾸지 말고 영어 표기로만 다듬으세요
  (예: "8/27(목)" -> "Aug 27 (Thu)").

# insight_section 필터링 (중요)
insight_section.stories 중 "한국에 특화된 소재"만 골라 번역해서 남기고, 나머지는
아예 빼세요. 예: 반도체특별법, K방산, K배터리, 국내 상장기업(레인보우로보틱스 등)
관련 소재는 포함 대상입니다. 한국 시장과 직접 관련 없는 미국/글로벌 소재는
제외하세요 — 이게 해외 독자에게 실제로 차별화되는 지점입니다. 해당하는 소재가
하나도 없으면 insight_section 전체를 null로 출력하세요.

# 출력 형식
입력받은 JSON과 동일한 최상위 키(title, narrative, theme_section, stock_section,
outlook, closing, insight_section, calendar)를 그대로 유지하고, 텍스트 값만
영어로 채워서 그 JSON 구조 그대로 출력하세요. 다른 설명 없이 JSON만 출력하세요
(마크다운 코드펜스 금지).
"""


def translate(generated: dict, model: str = "claude-sonnet-5") -> dict:
    """한국어 generated dict를 받아 해외 독자용 영어 버전 dict를 돌려줍니다."""
    client = anthropic.Anthropic()

    user_content = (
        "아래는 오늘자 한국장 마감 시황 콘텐츠입니다. 위 규칙에 따라 영어로 "
        f"각색해 주세요.\n\n{json.dumps(generated, ensure_ascii=False)}"
    )

    with client.messages.stream(
        model=model,
        max_tokens=32000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    ) as stream:
        response = stream.get_final_message()

    if response.stop_reason != "end_turn":
        raise RuntimeError(
            f"영어 번역 응답이 끝까지 완료되지 않았습니다 (stop_reason={response.stop_reason!r}). "
            "max_tokens을 늘려서 다시 시도하세요."
        )

    return _strip_cite_tags(_parse_json_response(_extract_text(response)))
