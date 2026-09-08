# 미국장 프리뷰 루틴 — 지시문

> 클라우드 루틴 "미국장 프리뷰"의 프롬프트는 이 파일을 읽고 그대로 따르라는 몇
> 줄뿐입니다. 규칙을 고칠 때는 여기를 고치고 커밋하세요.

## 임무

평일 21:30 KST에 **"오늘 밤 미국장 프리뷰" 한 편**을 써서
`editorial/previews/us_<KST 오늘 날짜>.json`에 커밋합니다. 커밋되면
`preview_publish.yml`이 **바로 공개**합니다 — 22시가 지나면 가치가 사라지는 글이라
시황과 같은 정책으로 사람 검수를 기다리지 않습니다. 그래서 **관문을 통과한 것만
커밋합니다.**

재테크농부가 하루 중 가장 많이 발행하는 시각이 22시입니다(34일 103편 중 24편).
독자가 자기 전에 "오늘 밤 뭘 보면 되는지" 세 가지를 알고 잠드는 글입니다.
길지 않습니다(본문 600~900자, 절 3개, 시각자료 3장).

## 쓰지 않는 날

- 오늘 밤(미국 동부 시간 오늘)이 미국 증시 휴장일이면 씁니다 대신 보고하고
  종료합니다. WebSearch로 "NYSE holidays 2026"을 확인합니다.
- `editorial/previews/us_<오늘>.json`이 이미 있으면 **알림 없이 조용히** 종료합니다(정상입니다).
- 어제 미국장 원고도, 재료 파일도, 확인된 일정도 없으면 보고하고 종료합니다.
  **억지로 채우지 않습니다.**

## 읽을 것

1. `docs/editorial-style.md` 전부 — 이 글도 시황 문체입니다(제목 문법·낱말·리듬).
2. 어제 미국장 원고 `editorial/us_<가장 최근 날짜>.json`의 `outlook`("다음 거래일에
   확인할 것")과 `narrative` — 오늘 밤은 그 연장선입니다.
3. `data/engines_us_<KST 오늘>.txt` — 실적 일정(앞으로 21일)·등급 변경·금리.
   GitHub Actions(`story_material.yml`)가 21:10 KST에 커밋합니다. 없으면
   `python -m src.story_engines earnings --market us --days 3`을 시도하되, 샌드박스에서는
   야후 연결이 끊겨 실패할 수 있습니다 — 그러면 WebSearch로 일정을 확인합니다.
4. `data/price_us_<가장 최근>.json` — 어제 종가. 가격대 숫자는 여기서만 가져옵니다.
5. 형식 예시: `editorial/features/us_2026-09-06_deere_upgrade.json` (같은 스키마를
   더 짧게 씁니다).

환경은 `docs/routine_common.md`의 "이 샌드박스에서 할 수 있는 것" 절과 같습니다.

## 절차

1. `pip install -r requirements.txt && apt-get install -y -qq fonts-nanum`(샌드박스에는 한글 폰트가 없어 이걸 빼면 그래픽 렌더가 첫 번에 실패합니다)
2. **오늘 밤 일정.** 실적 발표(어느 회사, 개장 전/마감 후), 경제지표(발표 시각),
   연준 인사 발언·FOMC. WebSearch로 **서로 다른 출처 2곳 이상**에서 확인한 것만
   씁니다. 시각은 한국시간으로 환산해 적습니다(서머타임 중 동부시간 +13시간, 11월
   첫째 일요일 이후 +14시간).
3. **이어지는 쟁점.** 어제 원고의 `outlook`에서 오늘 밤에 걸리는 것을 잇습니다.
   어제 종가 기준 가격대(지수·주인공 종목)를 적습니다.
4. **원고.** 기준표와 같은 스키마입니다.
   - `kind` "feature", `series` "프리뷰", `date` KST 오늘, `slug` `us-<date>-preview`,
     `category_id` 121(Daily), `related` 2개(어제 미국장 글 + 관련 기준표. 주소는
     `https://fermata.it.kr/wp-json/wp/v2/posts?search=<낱말>&_fields=title,link`로 확인)
   - `ko.title`: **앞을 보는 제목** — 오늘 밤 무엇이 무엇을 정하는지. 존댓말 종결·꼬리표
     금지, `왜 ~했을까?` 금지. 후킹 장치(개수·시한·대비·질문·경고) 하나는 넣습니다.
     예: `오늘 밤 미국장, 8월 물가가 반도체 랠리의 두 번째 근거를 정한다`,
     `오늘 밤 확인할 세 가지 — 마이크론 실적과 국채금리 4.8%`
   - `ko.narrative` 3절: **1. 오늘 밤 일정**(회사·지표·시각 KST) **2. 어제에서 이어지는
     쟁점과 가격대** **3. 확인할 것 셋**(무엇이 나오면 무엇을 본다). 본문에 날짜
     (`N월 N일`)를 씁니다.
   - `ko.closing`: heading `Fermata's Take`, 두 문장.
   - `graphics` 3장: `{"kind": "cover", "featured": true, ...}`(표지 — 오늘 밤 핵심
     하나), `calendar_strip`(`section` 0, 오늘 밤 일정 KST), `checklist`(`section` 2,
     확인할 것 셋). 인자 형식은 예시 원고와 `src/feature_graphics.py`.
   - 예측하지 않습니다. "물가가 예상보다 높게 나오면 X를 본다"처럼 조건으로 씁니다.
5. **검사.** `python -m src.feature_gate editorial/previews/<파일>.json --graphics 3`
   → 통과하면 `WORDPRESS_URL= WORDPRESS_USERNAME= WORDPRESS_APP_PASSWORD= python -m src.publish_feature editorial/previews/<파일>.json --render-only`
   → `output/features/<slug>/`의 그래픽 3장을 `Read`로 봅니다 → 제목·소제목·그래픽
   글자만 따로 읽습니다.
6. `git add editorial/previews/<파일>.json && git commit -m "프리뷰: <제목>" && git push origin HEAD:main`
   push 뒤 워크플로를 3분 넘게 기다리지 않습니다. **알림은 보내지 않습니다**(시황과
   같습니다). 건너뛰었거나 실패했을 때만 휴대폰 알림 한 번.

## 절대 규칙

- 숫자는 시세 파일·재료 파일·확인한 기사에서만. 일정 시각은 출처 2곳이 맞을 때만.
- 본문에 마크다운 볼드(`**`)를 쓰지 않습니다. 강조는 `<b>…</b>`.
- 한 편만 씁니다. 커밋하는 것은 원고 JSON 하나뿐입니다(`output/`·`data/` 커밋 금지).

## 완료 보고

원고 경로, 제목, 일정 출처 2곳, 그래픽 3장(종류), 관문 출력 전문, 커밋 해시.
건너뛴 날은 이유(휴장·재료 없음).
