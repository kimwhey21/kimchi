# 한국어 상시 가이드 루틴 — 지시문 (2026-09-12, 유입 편성)

> 클라우드 루틴 "한국어 가이드"의 프롬프트는 이 파일을 읽고 그대로 따르라는 몇 줄뿐입니다.
> 규칙을 고칠 때는 여기를 고치고 커밋하세요.

## 임무

화·목 09:00 KST에 **초보 투자자가 실제로 검색하는 질문 하나에 답하는 상시 가이드 한 편**을 써서
`editorial/guides/ko_<slug>.json`에 커밋합니다. 커밋되면 `guide_publish.yml`이 올리고, 자동화 스위치
(`FERMATA_AUTO_PUBLISH=true`, 2026-09-12부터)가 켜져 있어 **바로 공개**됩니다. 그래서 **관문을 통과한 것만
커밋합니다.** 이 세션은 `--publish`를 쓰지 않고 워드프레스를 직접 만지지 않습니다.

왜 이 글인가(2026-09-12 실측): 구글 노출 710건 중 700건이 영어 가이드 9편에서 나왔고, 한국어 시황 43편은
0건이었습니다. 시황은 그날 하루만 검색되고 연합뉴스·증권사가 상단을 차지합니다. "코스피 코스닥 차이",
"미국주식 양도세 계산"처럼 **매일 검색되는 질문**은 한 번 쓰면 계속 사람을 데려옵니다. 재테크농부도 118편 중
절반이 종목·질문·전략형입니다(「SK하이닉스 언제 팔아야 할까」「지금 환전할까?」「9월에는 주식을 매수해야 하나?」).

독자가 얻는 것: 검색한 질문의 답이 첫 절에 바로 나오고, 실제 숫자(세율·시간·수수료·기준일)와 확인 날짜가
있고, 지금 시장의 예(이번 주 시세 파일)로 설명되고, 마지막에 "그래서 무엇을 하면 되나"가 있습니다.
길이는 본문 2,000~3,500자, 절 5~7개, 시각자료 2~4장.

## 쓰지 않는 날

- 아래 후보 목록의 주제가 전부 이미 있으면(`ls editorial/guides/ko_*.json`) 보고하고 종료합니다.
- 규정·숫자를 **서로 다른 공식 출처 2곳**(국세청·금융감독원·한국거래소·증권사 안내·금융투자협회 등)에서
  확인하지 못하면 보고하고 종료합니다. **억지로 채우지 않습니다.** 틀린 세율 한 줄이 글 전체의 신뢰를 깎습니다.

## 읽을 것

1. `docs/editorial-style.md` 전부 — 제목 문법·소제목·낱말·리듬은 모든 글 공통입니다. 가이드 제목도
   「제목 문법」의 꼴 하나로 씁니다(질문 그대로가 아니라 — `코스피와 코스닥, 같은 주식이 아닙니다` /
   `미국주식 양도세 250만원, 넘는 순간 달라지는 것`).
2. `python -m scripts.recent_titles guide` — 최근 가이드의 꼴과 "피할 것"(첫 편이면 "원고가 없습니다").
3. `docs/feature-style.md`의 0절(초보자 설명·포지션 화법 금지)과 4절(확인 날짜).
4. 형식 예시: `editorial/features/kr_2026-09-08_foreign_buying_reversal.json`(같은 스키마).
5. `data/price_kr_<최근>.json`·`data/price_us_<최근>.json` — 예로 드는 숫자는 여기서만.

환경은 `docs/routine_common.md`의 "이 샌드박스에서 할 수 있는 것" 절과 같습니다(`python`이 없으면 `python3`).

## 주제 후보 (위에서부터, 아직 없는 것을 고른다)

파일명은 `ko_<slug>.json`이고 `slug`는 영문 소문자·하이픈입니다. 괄호 안은 **사람들이 실제로 치는 검색어** —
제목이나 첫 절에 그 말이 자연스럽게 들어가야 합니다.

1. `kospi-kosdaq-difference` — 코스피와 코스닥의 차이 (코스피 코스닥 차이, 코스닥 상장 조건)
2. `us-stock-capital-gains-tax` — 미국주식 양도소득세 계산 (미국주식 세금, 양도세 250만원, 5월 신고)
3. `dividend-tax-korea` — 배당소득세 15.4%와 금융소득종합과세 2,000만원 (배당세금, 금융소득종합과세 기준)
4. `us-market-hours-kst` — 미국주식 거래시간 한국시간, 서머타임·프리마켓·애프터마켓 (미국주식 거래시간)
5. `fx-spread-explained` — 환전 우대율 90%의 뜻과 실제 환전 비용 계산 (환전 우대율, 환전 수수료)
6. `isa-vs-pension-accounts` — ISA·연금저축·IRP 차이와 순서 (ISA 계좌, 연금저축 세액공제)
7. `ipo-subscription-how-to` — 공모주 청약 방법: 균등배정·비례배정·청약 증거금 (공모주 청약 방법)
8. `quadruple-witching-day` — 네 마녀의 날(선물옵션 동시만기)에 무슨 일이 생기나 (네 마녀의 날 뜻)
9. `per-pbr-roe-basics` — PER·PBR·ROE 보는 법, 코스피 지금 숫자로 (PER 뜻, PBR 1배)
10. `trading-fees-and-tax` — 주식 매매 수수료와 증권거래세 0.2%: 한 번 사고팔 때 드는 돈 (주식 거래세)
11. `dividend-record-date` — 배당기준일과 배당락일: 배당을 받으려면 언제 사야 하나 (배당락일, 배당기준일)
12. `price-limits-and-vi` — 상한가·하한가 30%와 VI(변동성완화장치) (상한가 하한가, VI 발동)
13. `after-hours-and-call-auction` — 동시호가·시간외 단일가·NXT (동시호가 뜻, 시간외 거래)
14. `fractional-us-shares` — 미국주식 소수점 거래의 장단점 (소수점 매매)
15. `open-brokerage-account` — 주식 계좌 개설: 비대면 개설·수수료 이벤트·주의할 것 (주식 계좌 개설)
16. `etf-tracking-error` — ETF 괴리율·추적오차·레버리지 ETF의 함정 (ETF 괴리율, 레버리지 ETF 위험)
17. `kospi200-explained` — 코스피200이 무엇이고 편입되면 무슨 일이 생기나 (코스피200 편입)
18. `short-selling-balance` — 공매도 뜻과 공매도 잔고 보는 법 (공매도 잔고 확인)
19. `us-cpi-release-time-kst` — 미국 CPI 발표 시간 한국시간과 보는 법 (CPI 발표 시간)
20. `fomc-schedule-2026-kst` — 2026년 FOMC 일정 한국시간과 결과 읽는 법 (FOMC 일정 2026)
21. `margin-call-korea` — 반대매매 뜻, 신용융자·미수거래의 위험 (반대매매 뜻)
22. `stock-split-explained` — 액면분할이 주가에 미치는 것 (액면분할 뜻)
23. `rights-vs-bonus-issue` — 유상증자와 무상증자 차이, 주가에는 어떻게 (유상증자 무상증자 차이)
24. `buyback-and-cancellation` — 자사주 매입·소각이 주가를 올리는 원리 (자사주 소각 효과)
25. `us-10y-yield-and-stocks` — 미국 10년물 국채금리가 오르면 주식은 (국채금리 주식 영향)
26. `usdkrw-and-stocks` — 원/달러 환율이 오르면 코스피는 (환율 상승 주식)
27. `market-holidays-2026` — 2026년 한국·미국 증시 휴장일 (증시 휴장일 2026)
28. `us-stock-tax-saving` — 해외주식 양도세 절세: 손익통산·연말 손실 확정·증여 (해외주식 절세)
29. `dividend-yield-screening` — 배당수익률 보는 법과 고배당주 고르는 기준 (고배당주 찾는 법)
30. `preferred-shares-explained` — 우선주와 보통주의 차이, 괴리율 (우선주 뜻)

목록이 다 채워지면 "후보가 없습니다"라고 보고하고 종료합니다 — 사람이 목록을 늘립니다.

## 절차

1. `pip install -r requirements.txt && apt-get install -y -qq fonts-nanum`
2. **주제.** `ls editorial/guides/ko_*.json`으로 이미 쓴 것을 빼고 목록에서 가장 위의 것을 고릅니다.
   `https://fermata.it.kr/wp-json/wp/v2/posts?search=<검색어>&_fields=title,link`로 같은 주제의 글이 이미
   있는지 봅니다(Checkpoint에 같은 질문이 있으면 다음 주제로).
3. **조사.** WebSearch·WebFetch로 규정·숫자를 **서로 다른 공식 출처 2곳 이상**에서 확인합니다. 출처 이름
   (국세청·금융감독원·한국거래소·금융투자협회·증권사 이름·언론사)을 본문에 그대로 적습니다 — 관문이 셉니다.
   세율·기준·시간처럼 바뀌는 숫자는 "2026년 9월 기준"이라고 본문에 박습니다.
4. **원고.** `editorial/guides/ko_<slug>.json`, 기준표와 같은 스키마에:
   - `kind` "feature", `series` "가이드", `date` KST 오늘, `checked` KST 오늘(머리말 `가이드 · 2026년 9월 16일 확인`이
     이 값으로 그려집니다), `slug`, `category_id` 153(Guides), `tags`(검색어 3~5개 — 목록의 괄호 안 검색어를
     띄어쓰기 없이), `related` 2~3개(관련 시황·Checkpoint — 주소는 REST로 확인).
   - `ko.title`: 「제목 문법」 예문집의 꼴 하나, 20~35자, **검색어가 앞쪽에**. 결론을 다 말하지 않습니다.
   - `ko.narrative` 5~7절: **1절이 답입니다**(검색한 사람은 첫 화면에서 답을 봐야 합니다). 이어서 원리 →
     실제 숫자·표 → 지금 시장의 예(시세 파일) → 자주 하는 실수 → 그래서 할 것. 소제목 32자 이하, 절반은 명사구.
     PER·HBM 같은 말이 셋 이상 나오면 `초보자 설명:` 문단 하나.
   - `ko.closing`: heading `Fermata's Take`, 두세 문장의 판단(우리는 이렇게 봅니다).
   - `graphics` 2~4장:
     - `{"kind": "cover", "featured": true, "args": {"kicker": "가이드", "subject": "<질문 한 줄>", "left": {"label": "...", "value": "..."}, "right": {...}}, "alt": "..."}`
     - `{"kind": "fact_table", "section": 1, "args": {"title": "...", "rows": [["항목", "값", "비고"], ...], "columns": ["항목", "값", "비고"], "source": "국세청"}, "alt": "..."}` — 규정·세율·시간표는 이 표로.
     - `{"kind": "checklist", "section": 4, "args": {"title": "...", "items": [{"label": "...", "why": "..."}, ...]}, "alt": "..."}`
     - 시세 예가 있으면 `{"kind": "price_history", "section": 3, "price_file": "data/price_kr_<날짜>.json", "args": {"ticker": "KS11", "title": "..."}, "alt": "..."}`
   - 본문에 마크다운 볼드(`**`)를 쓰지 않습니다. 강조는 `<b>…</b>`. 포지션 화법("제가 매수") 금지.
5. **관문.** `python -m src.feature_gate editorial/guides/ko_<slug>.json --graphics <그래픽 수>` — 통과 전에는
   커밋하지 않습니다. → `WORDPRESS_URL= WORDPRESS_USERNAME= WORDPRESS_APP_PASSWORD= python -m src.publish_feature
   editorial/guides/ko_<slug>.json --render-only` → `output/features/<slug>/`의 그래픽을 `Read`로 봅니다.
6. `git add editorial/guides/ko_<slug>.json && git commit -m "가이드: <제목>" && git push origin HEAD:main`
   (거부되면 `git pull --rebase origin main` 뒤 다시). push 뒤 워크플로를 3분 넘게 기다리지 않습니다.
7. 휴대폰 알림 한 번(PushNotification): `가이드 커밋: <제목> — 몇 분 안에 https://fermata.it.kr/<slug>/ 로 공개되고,
   네이버에는 20분 안에 요약본이 올라갑니다.` 건너뛰었거나 실패했을 때도 한 번, 이유와 함께.

## 네이버용 본문 (2026-09-12, 사용자: "네이버도 애드포스트가 있고 본진만큼 중요하다")

이 시리즈는 네이버 블로그에 요약본이 아니라 **완전한 글**로 갑니다. 애드포스트 수익과 네이버 검색은 네이버 글 자체가
끝까지 읽히는지를 봅니다. 그래서 원고 최상위에 `naver`를 넣습니다:

```json
"naver": {"narrative": [{"heading": "코스피와 코스닥은 무엇이 다른가", "body": "…"}, …]}
```

- 절 4~6개, 본문 합계 1,200~3,000자. 소제목에는 네이버에서 실제로 치는 검색어를 넣습니다(번호 없이).
- **본진(`ko.narrative`)과 같은 문장을 쓰지 않습니다.** 같은 사실을 다른 문장으로 다시 씁니다 — 관문이 25자 이상 같은
  문장을 찾으면 막습니다(유사문서 방지). 숫자·출처는 같아야 합니다.
- 문단은 2~3문장, 짧게. 독자는 휴대폰으로 읽습니다. 마무리 판단은 `ko.closing`이 인용구로 자동으로 들어갑니다.
- 그림은 본진 그래픽이 절마다 하나씩(네 장까지) 자동으로 붙습니다. 그림 설명을 문장에 넣지 않습니다.
- 마크다운 볼드(`**`)·포지션 화법 금지. 관문(`feature_gate`)이 이 절도 검사합니다.

## 절대 규칙

- 규정·숫자는 공식 출처 2곳이 맞을 때만. 예로 드는 시세는 시세 파일에서만.
- 특정 증권사·상품을 추천하지 않습니다. 비교는 공개된 수수료·조건으로만.
- 한 편만 씁니다. 커밋하는 것은 원고 JSON 하나뿐입니다(`output/`·`data/` 커밋 금지).
- 금지 낱말(`editorial_quality`): 눌리다, 등락률이 N배 갈렸다, 넉 달·석 달·닷새(숫자로), 볼 것 셋·둘·넷(→ 세 가지).

## 완료 보고

원고 경로, 제목, 출처 2곳 이상(무엇을 어디서), 그래픽 수와 종류, 관문 출력 전문, 커밋 해시. 건너뛴 날은 이유.
