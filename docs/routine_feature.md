# 주말 기준표 루틴 — 지시문

> 클라우드 루틴 "주말 기준표 집필"의 프롬프트는 이 파일을 읽고 그대로 따르라는
> 몇 줄뿐입니다. 규칙을 고칠 때는 여기를 고치고 커밋하세요.

## 임무

토·일 아침에 **기준표(feature) 글 한 편**을 써서 `editorial/features/`에 커밋합니다.
커밋되면 `feature_draft.yml`이 워드프레스에 **임시저장**으로 올립니다. **공개는
사람이 합니다** — 이 세션은 절대 공개하지 않고, 워드프레스를 직접 만지지 않습니다.

기준표는 일간 시황과 다릅니다. 시황은 그날을 설명하고 다음 날이면 잊히지만,
기준표는 "무엇을 언제 확인할지"를 숫자와 날짜로 세워 두어 그 날짜까지 읽힙니다.
평일 시황 열 편보다 잘 쓴 기준표 한 편이 검색으로 더 오래 사람을 데려옵니다.

- **토요일**: 미국장 재료 우선(금요일 장 마감 뒤라 등급 변경·13F·내부자 매수가 신선합니다).
- **일요일**: 한국장 재료 우선(DART 내부자·수급·밸류에이션).
- 다른 요일에 떴다면(시험 실행) 두 시장 재료를 다 뽑아 더 좋은 쪽을 씁니다.
- 우선 시장의 재료가 약하면 다른 시장으로 바꿔도 됩니다. **약한 재료로 억지로
  쓰지 않습니다** — 재료가 없으면 그 사실을 보고하고 종료하는 것이 정답입니다.

## 반드시 먼저 읽을 것

1. `AGENTS.md`의 「기준표(feature) 글」 절 전부 — 도구 다섯 줄과 그 이유
2. `docs/feature-style.md` 전부 — 제목·시각자료·사진 순서·절 골격·내보내기 전 확인
3. 형식 예시: `editorial/features/us_2026-09-06_deere_upgrade.json` (필드와 그래픽
   인자를 이 파일과 똑같은 형태로 씁니다)
4. `src/feature_graphics.py` — 그래픽 종류와 인자(`valuation_bars`·`gap_bars`·
   `calendar_strip`·`checklist`·`cover`·`sector_breadth`·`rate_compare`)
5. `src/feature_gate.py` 상단 — 발행 전 관문이 무엇을 막는지

환경은 `docs/routine_common.md`의 "이 샌드박스에서 할 수 있는 것" 절과 같습니다
(네트워크 전체 열림, `python`이 없으면 `python3`, `UNSPLASH_ACCESS_KEY`·
`FRED_API_KEY`·`ECOS_API_KEY` 환경변수 있음).

## 절차

1. `pip install -r requirements.txt`
2. **재료.** 먼저 `ls data/engines_*_$(TZ=Asia/Seoul date +%F).txt`를 봅니다. GitHub
   Actions(`story_material.yml`)가 토·일 08:10 KST에 두 시장의 엔진 출력을 이 파일로
   커밋해 둡니다 — **이 파일을 읽으세요.** 샌드박스에서는 야후 파이낸스 연결이
   끊겨 밸류에이션·등급변경·실적일정·계절성 엔진이 실패합니다(2026-09-07 실측).
   파일이 없을 때만 `python -m src.story_engines all --market us`(토) 또는
   `--market kr`(일)을 직접 돌립니다(DART·ECOS·FRED·수급 엔진은 샌드박스에서도 됩니다).
   결과를 훑어 **하나의 이야기**를 고릅니다. 기준은 셋입니다 — 시세만 봐서는
   모르는 새 사실인가, 숫자가 있는가, 날짜를 박을 확인 지점이 있는가.
   `⚠ N건을 받지 못했습니다`가 찍힌 엔진의 결과는 쓰지 않습니다. 고른 이야기를
   WebSearch로 서로 다른 출처 3곳 이상에서 교차 확인합니다(`source_check`가
   출처 개수를 세어 3곳 미만이면 막습니다).
3. **제목.** `python -m scripts.title_helper <관계>`(대비·원인·질문·경고·개수·시한)로
   벤치마크 실제 제목을 보고 **그 어법을 그대로 갈아입힙니다.** 결론을 제목에
   넣지 않습니다(읽기 전에 답을 알면 누를 이유가 없습니다). 이 도구가 코퍼스가
   없다며 실패하면(샌드박스에는 코퍼스가 없습니다) `docs/feature-style.md` 1절의
   후킹 유형표로 짓고, 완료 보고에 "코퍼스 없이 지은 제목"이라고 적습니다.
4. **원고.** `editorial/features/<market>_<YYYY-MM-DD>_<slug>.json`. 필드는 예시
   파일과 같게: `kind` "feature", `series` "기준표", `date`, `slug`(파일명의
   `<market>-<date>-<slug>`와 같게 영문 소문자·하이픈), `category_id` 153,
   `related`(기존 글 2~3편, `https://fermata.it.kr/wp-json/wp/v2/posts?search=<낱말>&_fields=title,link`로
   찾은 실제 주소만), `ko.title`, `ko.narrative` 6~7절(절 골격은 feature-style 4절,
   본문에 **확인 날짜**를 박습니다), `ko.closing`(heading은 `Fermata's Take`),
   `graphics` 6장 이상(각각 `section` 번호, 두 소제목마다 하나 이상).
5. **표지 사진.** `python -m src.photo_search --sheet cover --source unsplash "<회사 영어명 + 제품·현장>" "<업종 영어명>"`
   → `output/photos/sheet_cover.png`를 **`Read`로 열어 보고** 고릅니다. 로고·워드마크,
   다른 회사가 식별되는 것, 글자 가득한 것, 소재와 무관한 것은 버립니다. 고른
   번호의 정보를 `output/photos/sheet_cover.json`에서 읽어 원고에 적습니다 —
   파일은 커밋하지 않고 URL만:
   `"featured_photo": {"url": "<row.url>", "alt": "<사진에 실제로 보이는 것>", "credit": "사진: <row.creator> / Unsplash", "credit_url": "<row.page>"}`
   쓸 만한 사진이 없으면 `featured_photo`를 빼고 `cover` 그래픽으로 갑니다.
   억지로 아무 사진이나 붙이지 않습니다.
6. **검사.** `python -m src.feature_gate editorial/features/<파일>.json --graphics <그래픽 수>`
   — 막히면 고쳐서 다시. 통과하면
   `WORDPRESS_URL= WORDPRESS_USERNAME= WORDPRESS_APP_PASSWORD= python -m src.publish_feature editorial/features/<파일>.json --render-only`
   로 렌더하고, `output/features/<slug>/` 아래 그래픽 PNG를 **하나씩 `Read`로
   봅니다.** 축을 한 종목이 독차지하거나 이름이 막대와 어긋나는 것은 코드만
   봐서는 안 보입니다(실제로 두 번 겪었습니다).
7. **제목·소제목·그래픽 글자(`kicker`·`subject`·`label`)만 따로 모아 다시
   읽습니다.** 본문과 떼어 놓고 읽어야 어색한 것이 보입니다.
8. **성적표.** `data/scoreboard.yaml`(형식은 파일 머리의 주석)에 두 가지를 합니다.
   - 새 원고의 확인 지점을 `verdict: pending`으로 추가합니다(글 주소는
     `https://fermata.it.kr/<slug>/`, 공개 전이라도 적습니다 — 페이지는 공개된 글만
     자동으로 싣습니다).
   - `due`가 지났는데 `pending`인 항목을 조사해 `result`(숫자와 함께)·`checked`(오늘)·
     `verdict`를 적습니다. 시세는 `data/price_*.json`, 나머지는 WebSearch로 확인합니다.
     판정은 글이 가리킨 방향과 실제가 맞았는지만 봅니다. 모르면 `pending`으로 두고
     보고에 이유를 적습니다. `python -m src.publish_scoreboard --render-only --no-live-check`로
     형식 검사를 통과해야 합니다.
9. `git add editorial/features/<파일>.json data/scoreboard.yaml && git commit -m "기준표 원고: <제목>" && git push origin HEAD:main`
   push 뒤 워크플로를 3분 넘게 기다리지 않습니다.
10. 휴대폰 알림을 한 번 보냅니다: `주말 기준표 초안: <제목> — 워드프레스 임시저장. 보시고 "발행"이라고 답해 주세요.`

## 하지 않는 것

- 공개 발행. `--publish`를 쓰지 않습니다. 워드프레스 REST로 상태를 바꾸지 않습니다.
- 한 번에 두 편. 한 편만 씁니다.
- 숫자 지어내기, 못 받은 엔진 결과 쓰기, 검색 결과를 보지 않고 사진 URL 적기.
- `output/` 커밋. 커밋하는 것은 원고 JSON과 `data/scoreboard.yaml` 둘뿐입니다.
  `data/`의 다른 파일(시세·재료)은 건드리지 않습니다.

## 완료 보고

원고 경로, 제목, 어느 시장 재료였는지와 고른 이유, 출처 개수(`feature_gate`
출력의 sources), 그래픽 수와 종류, 사진을 골랐는지·왜 그것인지(또는 왜 없이
갔는지), 관문 출력 전문(benchmark_shape 포함), 성적표에 추가한 확인 지점 수와
판정을 적은 항목(무엇을 근거로), 커밋 해시. 재료가 없어 쓰지 않았다면 무엇을
봤고 왜 약했는지.
