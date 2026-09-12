# 일요일 다음 주 일정 루틴 — 지시문 (2026-09-12, 주말 편성)

> 클라우드 루틴 "다음 주 일정"의 프롬프트는 이 파일을 읽고 그대로 따르라는 몇 줄뿐입니다.
> 규칙을 고칠 때는 여기를 고치고 커밋하세요.

## 임무

일요일 20:00 KST에 **「다음 주 일정」 한 편**을 써서 `editorial/weekly/ahead_<KST 오늘>.json`에
커밋합니다. 커밋되면 `weekly_publish.yml`이 **바로 공개**합니다 — 시황·프리뷰와 같은 정책입니다.
그래서 **관문을 통과한 것만 커밋합니다.** 이 세션은 `--publish`를 쓰지 않고 워드프레스를
직접 만지지 않습니다.

왜 이 글인가: 벤치마크(재테크농부)는 다섯 주말 내내 **일요일 밤 21~24시에 "이번주 투자 전략"**을
올렸습니다(「이번주 주식시장 운명, 딱 2가지에 달렸습니다」「이번주 코스피 전망, 반도체와 금리.」).
일요일 밤은 독자가 "이번주 코스피 전망", "다음주 증시 일정"을 검색하는 시간입니다. 우리는
예측 대신 **정해진 일정과 금요일 종가 기준의 볼 자리**를 씁니다 — 평일 밤 프리뷰의 한 주 판입니다.

독자가 얻는 것: 다음 주 무엇이 언제(한국시간) 나오는지, 어느 회사 실적이 있는지, 금요일 종가
기준으로 어디를 보면 되는지, 그래서 확인할 것 세 가지. 길이는 본문 900~1,400자, 절 4개,
시각자료 3~4장.

## 쓰지 않는 날

- `editorial/weekly/ahead_<오늘>.json`이 이미 있으면 조용히 종료합니다(정상입니다).
- 다음 주 일정을 서로 다른 출처 2곳에서 확인하지 못하면 보고하고 종료합니다. **억지로 채우지 않습니다.**

## 읽을 것

1. `docs/editorial-style.md` 전부 — 제목 문법·소제목·낱말·리듬은 모든 글 공통입니다.
2. `python -m scripts.recent_titles weekahead` — 최근 다음 주 일정의 꼴과 "피할 것"
   (첫 편이면 "원고가 없습니다"로 끝납니다. 그러면 `preview`를 한 번 봅니다 — 가장 가까운 꼴입니다).
3. 어제 토요일 주간 결산 `editorial/weekly/review_<어제>.json`의 5절("다음 주로 넘어가는 것")과
   `closing` — 이 글은 그 질문들에 날짜를 붙이는 글입니다. 없으면 금요일 한국장·미국장 시황의
   `outlook`을 씁니다.
4. `data/engines_us_<오늘>.txt`·`data/engines_kr_<오늘>.txt` — 실적 일정(앞으로 21일)·의견 변경·
   금리. GitHub Actions(`story_material.yml`)가 일 08:10 KST에 커밋합니다. 없으면 어제 파일을 씁니다.
   `[실적 일정]`에서 다음 주(월~금)에 드는 것만 고릅니다.
5. `data/price_kr_<금요일>.json`·`data/price_us_<금요일>.json` — 금요일 종가. 가격대 숫자는 여기서만.
6. 형식 예시: `editorial/previews/us_2026-09-11.json`(같은 스키마를 한 주 단위로 씁니다).

환경은 `docs/routine_common.md`의 "이 샌드박스에서 할 수 있는 것" 절과 같습니다
(`python`이 없으면 `python3`).

## 절차

1. `pip install -r requirements.txt && apt-get install -y -qq fonts-nanum`
2. **다음 주 일정.** 월요일부터 금요일까지, 두 시장:
   - 미국: 경제지표(CPI·PPI·소매판매·고용·PCE 등, 발표 시각), FOMC·연준 인사 발언, 주요 실적
     (개장 전/마감 후), 휴장일. WebSearch로 **서로 다른 출처 2곳 이상**에서 확인한 것만 씁니다.
     시각은 한국시간으로 환산합니다(서머타임 중 동부시간 +13시간, 11월 첫째 일요일 이후 +14시간).
   - 한국: 금통위, 수출입 통계(1~10일·월간), 옵션·선물 만기, 주요 실적·공시, 휴장일
     (WebSearch "한국거래소 휴장일 2026" 등 2곳). 추석처럼 연휴가 낀 주는 거래일이 며칠인지 첫 절에 씁니다.
   - 확인되지 않은 일정은 쓰지 않습니다. "예정으로 알려졌다"는 표현도 쓰지 않습니다.
3. **볼 자리.** 금요일 종가 기준 지수·주인공 종목의 가격대와 기준선(7,000선·5% 금리 같은 것).
   어제 주간 결산과 금요일 시황이 남긴 질문에 날짜를 붙입니다.
4. **원고.** `editorial/weekly/ahead_<오늘>.json`. 기준표와 같은 스키마에 다음 필드:
   - `kind` "feature", `series` "다음 주 일정", `date` KST 오늘(일요일), `slug` `week-ahead-<오늘>`,
     `category_id` 433(Weekly — 2026-09-12 사용자 결정, 홈 탭 Weekly), `tags`(검색어 2~4개 — 다음 주 주인공
     회사·지표 이름; 나머지는 `src/post_tags.py`가 글에서 뽑습니다), `period` `{"start": "<다음 주 월요일>", "end": "<다음 주 금요일>"}`
     (글 머리말 `다음 주 일정 · 9월 14일~18일`이 이 값으로 그려집니다), `related` 2~3개(어제 주간 결산
     `https://fermata.it.kr/weekly-review-<어제>/`, 금요일 시황 — 주소는
     `https://fermata.it.kr/wp-json/wp/v2/posts?search=<낱말>&_fields=title,link`로 확인).
   - `ko.title`: **앞을 보는 제목** — 「제목 문법」 예문집의 꼴 중 하나로. 다음 주에 무엇이 무엇을
     정하는지 하나, 20~35자, 등락률은 많아야 하나. 예(꼴만 참고): `다음 주 증시, 이 세 가지에
     달렸다` / `다음 주 미국장: 9월 17일 FOMC가 5% 금리의 답을 낸다` / `추석 앞둔 코스피, 사흘
     동안 무엇을 보나`. `recent_titles weekahead`가 보여 준 끝말·꼴은 피합니다.
   - `ko.narrative` 4절: **1. 다음 주 일정 한눈에**(두 시장, 날짜·한국시간) **2. 실적과 발표**
     (회사·날짜·개장 전/후, 무엇을 볼지) **3. 금요일 종가 기준 볼 자리**(가격대와 기준선)
     **4. 확인할 것 세 가지**(무엇이 나오면 무엇을 본다 — 조건문으로). 본문에 `N월 N일`을 씁니다.
     소제목은 32자 이하, 절반쯤은 명사구.
   - `ko.closing`: heading `Fermata's Take`, 두세 문장의 판단.
   - `graphics` 3~4장:
     - `{"kind": "cover", "featured": true, "args": {"kicker": "다음 주 일정 · <기간>", "subject": "<다음 주 핵심 하나>", "left": {"label": "...", "value": "..."}, "right": {...}}, "alt": "..."}`
     - `{"kind": "calendar_strip", "section": 0, "args": {"title": "다음 주 일정", "subtitle": "한국시간 기준", "events": [{"date": "9/15(화) 21:30", "label": "美 8월 소매판매", "highlight": true, "note": "..."}, ...]}, "alt": "..."}` — 4~6개, 가장 중요한 것 하나만 `highlight`.
     - `{"kind": "price_history", "section": 2, "price_file": "data/price_kr_<금요일>.json", "args": {"ticker": "KS11", "title": "코스피, 7,000선 아래에서 한 주를 마쳤다", "guide": 7000, "guide_label": "7,000선"}, "alt": "..."}` — 또는 `^GSPC`·`^TNX`·주인공 종목.
     - `{"kind": "checklist", "section": 3, "args": {"title": "다음 주 확인할 세 가지", "items": [{"label": "...", "why": "..."}, ...]}, "alt": "..."}`
   - 본문에 마크다운 볼드(`**`)를 쓰지 않습니다. 강조는 `<b>…</b>`.
5. **관문.** `python -m src.feature_gate editorial/weekly/<파일>.json --graphics <그래픽 수>`
   — 통과 전에는 커밋하지 않습니다.
   → 통과하면 `WORDPRESS_URL= WORDPRESS_USERNAME= WORDPRESS_APP_PASSWORD= python -m src.publish_feature editorial/weekly/<파일>.json --render-only`
   → `output/features/<slug>/`의 그래픽을 `Read`로 봅니다 → 제목·소제목·그래픽 글자만 따로 읽습니다.
6. `git add editorial/weekly/<파일>.json && git commit -m "다음 주 일정: <제목>" && git push origin HEAD:main`
   (push 거부 시 `git pull --rebase origin main` 뒤 다시). push 뒤 워크플로를 3분 넘게 기다리지 않습니다.
7. 휴대폰 알림을 한 번 보냅니다(PushNotification):
   `다음 주 일정 커밋: <제목> — 몇 분 안에 https://fermata.it.kr/<slug>/ 로 공개되고, 네이버에는 20분 안에 요약본이 올라갑니다.`
   건너뛰었거나 실패했을 때도 한 번, 이유와 함께.

## 이벤트 글 (2026-09-12, 유입 편성 — 사용자 승인 "4번 진행")

다음 주 일정을 커밋한 뒤, **그 주의 가장 큰 이벤트 하나**를 골라 「이벤트」 글을 한 편 더 씁니다.
"FOMC 결과 발표 시간 한국시간", "CPI 발표 시간", "네 마녀의 날", "옵션 만기일"은 매달 되풀이되는 검색어라
시황보다 수명이 깁니다(2026-09-12 서치콘솔 실측: 한국어 시황 43편의 구글 노출 0건).

- **고르는 순서**(위에 있을수록 먼저): FOMC 결과 → 미국 CPI → 미국 고용보고서 → 한국 금통위 → 선물옵션
  동시만기(네 마녀의 날) → 삼성전자 잠정실적 → 엔비디아 실적 → 한국 수출입 통계(1~10일). 이 목록에 없는 주는
  쓰지 않습니다. 같은 이벤트의 글이 이미 있으면(`ls editorial/events/`, `event_name`과 `event_date`가 같음) 쓰지 않습니다.
- **원고.** `editorial/events/<KST 오늘>_<slug>.json`(예: `2026-09-13_fomc.json`). 기준표 스키마에:
  `kind` "feature", `series` "이벤트", `date` KST 오늘, `event_date` 이벤트 날짜(한국시간 기준 날짜),
  `event_name`(예: `9월 FOMC`), `slug`(예: `fomc-2026-09`), `category_id` 433, `tags` 3~5개(예: `FOMC`, `금리결정`,
  `9월FOMC`), `period` 없음, `related` 2개(방금 쓴 다음 주 일정 `https://fermata.it.kr/week-ahead-<오늘>/` + 관련 시황).
  - `ko.title`: 이벤트 이름과 **날짜·한국시간**이 들어간 「제목 문법」 꼴 하나, 20~35자.
    예(꼴만): `9월 FOMC, 17일 새벽 3시에 확인할 것 세 가지` / `8월 CPI 발표 밤 9시 30분, 무엇을 보나`.
  - `ko.narrative` 4~5절: **1. 언제 나오나**(한국시간, 어디서 보나) **2. 무엇이 나오나**(예상값·지난번 값 — 출처 2곳)
    **3. 시장은 어떻게 반응했나**(지난 발표 때 지수·금리·환율 — 시세 파일 이력에서만) **4. 이번에 볼 것**(조건문으로)
    (5. 초보자 설명 — 필요할 때). 본문에 `N월 N일`.
  - `ko.closing`: heading `Fermata's Take`, 두세 문장.
  - `graphics` 2~3장: `cover`(featured, kicker `이벤트 · <N월 N일>`) + `fact_table`(section 1: 지난 값·예상값,
    `source` 필수) 또는 `calendar_strip`(section 0) + 있으면 `price_history`(section 2, `price_file`).
- **관문.** `python -m src.feature_gate editorial/events/<파일>.json --graphics <수>` → 통과하면 렌더 확인 →
  `git add editorial/events/<파일>.json && git commit -m "이벤트: <제목>" && git push origin HEAD:main`.
  `weekly_publish.yml`이 다음 주 일정과 같은 정책으로 **바로 공개**하고, 네이버에는 20분 안에 요약본이 갑니다.
- 다음 주 일정을 못 쓴 날(재료 부족)에는 이벤트 글도 쓰지 않습니다. 알림은 두 글을 한 번에 보냅니다.

## 절대 규칙

- 일정은 출처 2곳이 맞을 때만. 가격대 숫자는 시세 파일에서만.
- 예측하지 않습니다. "물가가 예상보다 높게 나오면 X를 본다"처럼 조건으로 씁니다.
- 한 편만 씁니다. 커밋하는 것은 원고 JSON 하나뿐입니다(`output/`·`data/` 커밋 금지).
- 금지 낱말(`editorial_quality`): 눌리다, 등락률이 N배 갈렸다, 넉 달·석 달·닷새(숫자로), 볼 것 셋·둘·넷(→ 세 가지).

## 완료 보고

원고 경로, 제목, 일정 출처 2곳 이상(무엇을 어디서), 그래픽 수와 종류, 관문 출력 전문, 커밋 해시.
건너뛴 날은 이유.
