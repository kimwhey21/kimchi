# 토요일 주간 결산 루틴 — 지시문 (2026-09-12, 주말 편성)

> 클라우드 루틴 "주간 결산"의 프롬프트는 이 파일을 읽고 그대로 따르라는 몇 줄뿐입니다.
> 규칙을 고칠 때는 여기를 고치고 커밋하세요.

## 임무

토요일 10:00 KST에 **「주간 결산」 한 편**을 써서 `editorial/weekly/review_<KST 오늘>.json`에
커밋합니다. 커밋되면 `weekly_publish.yml`이 **바로 공개**합니다 — 시황·프리뷰와 같은 정책입니다.
그래서 **관문을 통과한 것만 커밋합니다.** 이 세션은 `--publish`를 쓰지 않고 워드프레스를
직접 만지지 않습니다.

왜 이 글인가: 벤치마크(재테크농부)는 다섯 주말 24편 가운데 **토요일 아침 미국장 주간 결산**을
다섯 주 내내 같은 자리에 올렸습니다(「이 지표가 다음주 주식 시장을 흔든다!」「금리인상 확률
57%로 급등. 그런데 시장이 버틴 이유」). 우리는 한국장과 미국장을 한 편에 담고, 숫자는 전부
우리가 평일마다 커밋한 시세 파일에서 셉니다 — 그래서 틀린 숫자가 붙을 수 없습니다.

독자가 얻는 것: 한 주가 어떻게 움직였는지 **숫자로 한 장**, 무엇이 올리고 무엇이 막았는지,
그리고 다음 주로 넘어가는 쟁점. 길이는 본문 1,200~1,800자, 절 5~6개, 시각자료 4~6장.

## 쓰지 않는 날

- `python -m scripts.weekly_stats`가 종료 코드 2로 끝나면(어느 시장이든 거래일 3일 미만)
  그 주는 결산을 쓰지 않습니다. 보고하고 종료합니다. **얇은 결산을 억지로 쓰지 않습니다.**
- `editorial/weekly/review_<오늘>.json`이 이미 있으면 조용히 종료합니다(정상입니다).
- 미국장 시세 파일의 마지막 거래일이 이번 주 금요일이 아닌데 금요일이 휴장이 아니었다면
  (WebSearch "NYSE holidays 2026"으로 확인) 금요일 마감 시세가 아직 커밋되지 않은 것입니다.
  `sleep 1800` 뒤 `git pull`을 한 번 더 하고, 그래도 없으면 보고하고 종료합니다.

## 읽을 것

1. `docs/editorial-style.md` 전부 — 제목 문법·소제목·낱말·리듬은 모든 글 공통입니다.
2. `python -m scripts.recent_titles weekly` — 최근 주간 결산의 꼴과 "피할 것"
   (첫 편이면 "원고가 없습니다"로 끝납니다. 그러면 `checkpoint`와 `kr`도 한 번 봅니다).
3. 이번 주 시황 원고 다섯 편 안팎: `editorial/kr_<날짜>.json`·`editorial/us_<날짜>.json`
   (이번 주 월~금). 각 원고의 `closing`(Fermata's Take)과 `outlook`을 읽습니다 —
   한 주의 이야기는 이 다섯 편이 이미 하루씩 해 두었습니다. 결산은 그것을 **한 주 단위로
   다시 묶는 것**이지 새로 조사하는 것이 아닙니다.
4. `data/engines_kr_<오늘>.txt`·`data/engines_us_<오늘>.txt` — 금리(FRED·ECOS)·의견 변경.
   GitHub Actions(`story_material.yml`)가 토 08:10 KST에 커밋합니다. 없으면 금요일 파일을 씁니다.
5. 형식 예시: `editorial/previews/us_2026-09-11.json`(같은 스키마) — 아래 4절이 주간 결산에서
   다른 필드를 적습니다.

환경은 `docs/routine_common.md`의 "이 샌드박스에서 할 수 있는 것" 절과 같습니다
(`python`이 없으면 `python3`).

## 절차

1. `pip install -r requirements.txt && apt-get install -y -qq fonts-nanum`(샌드박스에는 한글 폰트가
   없어 이걸 빼면 그래픽 렌더가 첫 번에 실패합니다)
2. **숫자.** `python -m scripts.weekly_stats --json output/weekly/<오늘>.json` — 두 시장의 지수·
   환율·금리(주간 등락, 날짜별 등락, 주중 최고·최저), 종목 폭, 업종(한국장 코어 종목 평균),
   주간 상승·하락 상위, 전체 종목 주간 등락. **지수·종목 등락은 이 출력에서만 가져옵니다.**
   검색 결과의 "코스피 주간 3% 상승" 같은 숫자를 옮겨 적지 않습니다 — 기준일이 다르면
   숫자가 다릅니다. `(동적 편입)` 표시가 붙은 종목은 그날 거래대금으로 들어온 종목이라 이름을
   본문에 쓸 때 어떤 회사인지 확인하고 씁니다.
3. **밖의 사실 둘 이상.** 한 주를 움직인 원인(물가·고용·연준 발언·실적·수급)은 이번 주 시황
   원고에 이미 출처와 함께 있습니다. 거기서 가져오되, 기관·매체 이름을 그대로 남깁니다
   (`source_check`가 서로 다른 출처 2곳 미만이면 막습니다). 외국인·기관 주간 순매수를 쓰려면
   WebSearch로 매체 2곳이 같은 숫자를 말할 때만 씁니다 — 아니면 쓰지 않습니다.
4. **원고.** `editorial/weekly/review_<오늘>.json`. 기준표와 같은 스키마에 다음 필드:
   - `kind` "feature", `series` "주간 결산", `date` KST 오늘(토요일), `slug` `weekly-review-<오늘>`,
     `category_id` 433(Weekly — 2026-09-12 사용자 결정, 홈 탭 Weekly), `tags`(검색어 2~4개 — 이 주의 주인공
     종목·주제어; 나머지는 `src/post_tags.py`가 글에서 뽑습니다), `period` `{"start": "<월요일>", "end": "<마지막 거래일>"}`
     (`weekly_stats` 출력의 `week`와 같게 — 글 머리말 `주간 결산 · 9월 7일~11일`이 이 값으로 그려집니다),
     `related` 2~3개(이번 주 금요일 한국장·미국장 시황: 주소는
     `https://fermata.it.kr/editorial-kr-<날짜>-ko/`·`https://fermata.it.kr/editorial-us-<날짜>-ko/`,
     `https://fermata.it.kr/wp-json/wp/v2/posts?search=<낱말>&_fields=title,link`로 확인).
   - `ko.title`: 「제목 문법」의 예문집(사장님이 고른 35개) 중 하나의 꼴로. 한 주를 한 이야기로 —
     등락률은 많아야 하나, 종목 둘을 나란히 세우지 않음, 20~35자. 예(꼴만 참고):
     `코스피가 한 주에 3% 오른 이유는 반도체가 아니었다` / `이번 주 미국장: 금리 5% 앞에서 나흘
     내리고 하루 올랐다` / `이번 주 증시, 무엇이 올리고 무엇이 막았나`.
     `python -m scripts.recent_titles weekly`가 보여 준 끝말·꼴은 피합니다.
   - `ko.narrative` 5~6절, 순서는 이렇게: **1. 한 주를 숫자로**(두 시장 지수 주간 등락과 날짜별
     흐름 — 어느 날이 한 주를 정했나) **2. 한국장: 무엇이 올리고 무엇이 막았나**(업종·종목,
     `weekly_stats`의 업종·상위 목록) **3. 미국장: …**(지수·종목·금리) **4. 금리·환율·유가**
     (10년물·원/달러·WTI·금 — 주간 변화와 그것이 다음 주에 뜻하는 것) **5. 다음 주로 넘어가는
     것**(이번 주가 답하지 못한 질문 둘셋과 그 답이 나올 날짜 — 본문에 `N월 N일`을 씁니다.
     판정은 하지 않습니다. "우리가 맞았다/틀렸다"는 이 글의 일이 아닙니다).
     소제목은 「소제목」의 두 세트 어느 어법이든, 32자 이하. 절마다 하나만 말합니다.
   - `ko.closing`: heading `Fermata's Take`, 세 문장 안팎의 **판단**(요약이 아니라 "우리는
     이렇게 봅니다"). 포지션 화법("저는 샀다")은 관문이 막습니다.
   - `graphics` 4~6장 — 숫자는 시세 파일에서만 나옵니다(`price_file`은 그 시장의 금요일 파일):
     - `{"kind": "cover", "featured": true, "args": {"kicker": "주간 결산 · <기간>", "subject": "<한 주의 핵심 한 문장>", "left": {"label": "코스피 주간", "value": "+3.33%"}, "right": {"label": "S&P500 주간", "value": "-0.80%"}}, "alt": "..."}`
     - `{"kind": "number_cards", "section": 0, "price_file": "data/price_kr_<금요일>.json", "args": {"tickers": ["KS11", "KQ11", "USD/KRW"], "period": "week", "title": "이번 주 한국장을 정한 숫자"}, "alt": "..."}`
       — `"period": "week"`가 하루가 아니라 **달력 주간** 등락을 적습니다("주간 +3.33%"; 휴장이 낀 주에도
       전주 마지막 종가 대비). 잊으면 하루 등락이 주간처럼 나가므로 반드시 넣습니다. `period_days: 5`는
       5거래일 전 대비라 휴장 주에 틀립니다 — 쓰지 않습니다. 미국장은 `["^GSPC", "^IXIC", "^TNX"]`처럼.
     - `{"kind": "movers_list", "section": 1, "price_file": "data/price_kr_<금요일>.json", "args": {"top_n": 6, "period": "week", "title": "이번 주 많이 움직인 종목"}, "alt": "..."}` — 미국장도 같은 식으로 2절에.
     - `{"kind": "price_history", "section": 3, "price_file": "data/price_us_<금요일>.json", "args": {"ticker": "^TNX", "title": "美 10년물, 5% 앞", "guide": 5.0, "guide_label": "5%"}, "alt": "..."}` —
       4절에는 금리나 환율의 3개월 흐름을, 또는 지수(`KS11`·`^GSPC`)의 흐름을 붙입니다.
     - 절마다 그림은 한 장까지(`section` 번호가 겹치면 발행이 멈춥니다).
   - 본문에 마크다운 볼드(`**`)를 쓰지 않습니다. 강조는 `<b>…</b>`.
5. **관문.** `python -m src.feature_gate editorial/weekly/<파일>.json --graphics <그래픽 수>`
   — 통과 전에는 커밋하지 않습니다(제목·소제목·문체·시각자료·출처를 한 번에 봅니다).
   → 통과하면 `WORDPRESS_URL= WORDPRESS_USERNAME= WORDPRESS_APP_PASSWORD= python -m src.publish_feature editorial/weekly/<파일>.json --render-only`
   → `output/features/<slug>/`의 그래픽을 **한 장씩 `Read`로 봅니다** — 주간 카드에 "주간"이 찍혔는지,
   종목 이름이 막대와 맞는지. → 제목·소제목·그래픽 글자만 따로 모아 다시 읽습니다.
6. `git add editorial/weekly/<파일>.json && git commit -m "주간 결산: <제목>" && git push origin HEAD:main`
   (push 거부 시 `git pull --rebase origin main` 뒤 다시). push 뒤 워크플로를 3분 넘게 기다리지 않습니다.
7. 휴대폰 알림을 한 번 보냅니다(PushNotification):
   `주간 결산 커밋: <제목> — 몇 분 안에 https://fermata.it.kr/<slug>/ 로 공개되고, 네이버에는 20분 안에 요약본이 올라갑니다.`
   건너뛰었거나 실패했을 때도 한 번, 이유와 함께.

## 절대 규칙

- 지수·종목·환율·금리 숫자는 `weekly_stats` 출력과 시세 파일에서만. 검색 결과의 등락률을 옮겨 적지 않습니다.
- 예측하지 않습니다. 다음 주 이야기는 "N월 N일에 무엇이 나오면 무엇을 본다"로 씁니다.
- 판정하지 않습니다(맞았다·틀렸다). 그 자리는 따로 있습니다.
- 한 편만 씁니다. 커밋하는 것은 원고 JSON 하나뿐입니다(`output/`·`data/` 커밋 금지).
- 금지 낱말(`editorial_quality`): 눌리다, 등락률이 N배 갈렸다, 넉 달·석 달·닷새(숫자로), 볼 것 셋·둘·넷(→ 세 가지).

## 완료 보고

원고 경로, 제목, `weekly_stats`가 준 두 시장의 지수 주간 등락과 거래일 수, 출처(관문 출력의
sources), 그래픽 수와 종류, 관문 출력 전문, 커밋 해시. 건너뛴 날은 이유(거래일 부족·시세 미도착).
