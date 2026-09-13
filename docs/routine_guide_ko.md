# 한국어 상시 가이드 루틴 — 지시문 (2026-09-12, 유입 편성)

> 클라우드 루틴 "한국어 가이드"의 프롬프트는 이 파일을 읽고 그대로 따르라는 몇 줄뿐입니다.
> 규칙을 고칠 때는 여기를 고치고 커밋하세요.

## 임무

**매일 13:00 KST에 초보 투자자가 실제로 검색하는 질문 하나에 답하는 상시 가이드 한 편**을 써서
`editorial/guides/ko_<slug>.json`에 커밋합니다. 커밋되면 `guide_publish.yml`이 올리고, 자동화 스위치
(`FERMATA_AUTO_PUBLISH=true`)가 켜져 있어 **바로 공개**됩니다. 그래서 **관문을 통과한 것만 커밋합니다.**
이 세션은 `--publish`를 쓰지 않고 워드프레스를 직접 만지지 않습니다.

왜 이 글인가(2026-09-13 실측): 3개월 동안 구글에서 이름이 잡힌 검색어 21개가 **전부 영어**였습니다. 한국어
시황 43편은 단 한 번도 검색 결과에 보이지 않았습니다 — "코스피"는 하루에도 수만 번 검색되지만 그 자리에는
연합뉴스와 증권사가 있고, 3주 된 사이트가 이길 수 없습니다. **시황은 검색용이 아니라 브랜드와 재방문용입니다.**
한국어에서 검색으로 이길 수 있는 곳은 가이드뿐입니다 — "배당락일" 같은 검색어는 영어 대응어보다 5배 크고,
경쟁자가 언론사가 아니라 다른 블로그라 이길 수 있습니다. 그래서 2026-09-13부터 주 2편 → **주 7편**입니다
(사용자: "한국어 가이드도 매일로 올려").

독자가 얻는 것: 검색한 질문의 답이 첫 절에 바로 나오고, 실제 숫자(세율·시간·수수료·기준일)와 확인 날짜가
있고, 지금 시장의 예(이번 주 시세 파일)로 설명되고, 마지막에 "그래서 무엇을 하면 되나"가 있습니다.
길이는 본문 2,000~3,500자, 절 5~7개, 시각자료 2~4장.

**하루 한 편만.** 밀린 주제를 몰아 쓰지 않습니다. 얇은 글 셋보다 제대로 된 글 하나가 오래 갑니다.

## 쓰지 않는 날

- 오늘 날짜의 `editorial/guides/ko_*.json`이 이미 있으면 조용히 종료합니다.
- 아래 목록에서 아직 안 쓴 주제를 셋까지 시도했는데 **서로 다른 공식 출처 2곳**(국세청·금융감독원·한국거래소·
  금융투자협회·증권사 안내 등)에서 숫자를 확인하지 못하면 보고하고 종료합니다. **억지로 채우지 않습니다** —
  하루 빠지는 것이 틀린 세율 한 줄보다 낫습니다.
- 목록이 다 채워졌으면 「주제가 떨어졌을 때」 절을 따르고, 그래도 없으면 보고하고 종료합니다.

## 읽을 것

1. `docs/editorial-style.md` 전부 — 제목 문법·소제목·낱말·리듬은 모든 글 공통입니다. 가이드 제목도
   「제목 문법」의 꼴 하나로 씁니다(질문 그대로가 아니라 — `코스피와 코스닥, 같은 주식이 아닙니다` /
   `미국주식 양도세 250만원, 넘는 순간 달라지는 것`).
2. `python -m scripts.recent_titles guide` — 최근 가이드의 꼴과 "피할 것".
3. `docs/feature-style.md`의 0절(초보자 설명·포지션 화법 금지)과 4절(확인 날짜).
4. 형식 예시: `editorial/guides/ko_kospi-kosdaq-difference.json`(네이버용 본문까지 들어 있는 첫 편).
5. `data/price_kr_<최근>.json`·`data/price_us_<최근>.json` — 예로 드는 숫자는 여기서만.

환경은 `docs/routine_common.md`의 "이 샌드박스에서 할 수 있는 것" 절과 같습니다(`python`이 없으면 `python3`).

## 주제 목록

파일명은 `ko_<slug>.json`이고 `slug`는 영문 소문자·하이픈입니다. 괄호 안은 **사람들이 실제로 치는 검색어** —
제목이나 첫 절에 그 말이 자연스럽게 들어가야 합니다.

**고르는 법**: 아래 열 갈래(A~J)에서 **어제와 다른 갈래**를 고르고, 그 갈래에서 위에 있는 것부터 씁니다.
한 주가 세금 이야기로만 채워지면 콘텐츠 농장처럼 보입니다. 어제 무엇을 썼는지는
`ls -t editorial/guides/ko_*.json | head -3`으로 봅니다.

**A. 세금** — 한국에서 검색량이 가장 큰 갈래
- `us-stock-capital-gains-tax` — 미국주식 양도소득세 250만원과 5월 신고 (미국주식 양도세)
- `dividend-tax-korea` — 배당소득세 15.4%와 금융소득종합과세 2,000만원 (배당소득세)
- `financial-income-tax` — 금융소득종합과세, 넘으면 실제로 얼마를 더 내나 (금융소득종합과세 기준)
- `us-stock-tax-saving` — 해외주식 절세: 손익통산·연말 손실 확정·증여 (해외주식 절세)
- `trading-fees-and-tax` — 매매 수수료와 증권거래세 0.2% (주식 거래세)
- `isa-tax-benefit` — ISA 비과세 한도와 만기 (ISA 비과세)
- `pension-account-tax` — 연금저축 세액공제와 연금소득세 (연금저축 세액공제)
- `stock-gift-and-inheritance` — 주식 증여·상속세 계산 (주식 증여세)

**B. 계좌·제도**
- `isa-vs-pension-accounts` — ISA·연금저축·IRP 차이와 여는 순서 (ISA 연금저축 차이)
- `open-brokerage-account` — 계좌 개설: 비대면·수수료 이벤트·주의할 것 (주식 계좌 개설)
- `irp-explained` — IRP가 연금저축과 다른 점 (IRP 계좌)
- `account-transfer` — 증권사 옮기기: 주식 이관과 비용 (주식 계좌이체)
- `minor-stock-account` — 미성년 자녀 주식계좌 (미성년자 주식계좌)

**C. 거래 규칙**
- `price-limits-and-vi` — 상한가·하한가 30%와 VI (상한가 하한가)
- `after-hours-and-call-auction` — 동시호가·시간외 단일가 (동시호가 뜻)
- `margin-call-korea` — 반대매매, 신용융자·미수의 위험 (반대매매 뜻)
- `settlement-and-deposit` — 예수금·증거금·D+2 결제 (주식 결제일)
- `short-selling-balance` — 공매도 잔고 보는 법 (공매도 잔고)
- `quadruple-witching-day` — 네 마녀의 날에 생기는 일 (네 마녀의 날)
- `market-holidays-2026` — 2026년 한국·미국 증시 휴장일 (증시 휴장일)
- `nxt-alternative-exchange` — 대체거래소와 달라진 거래시간 (넥스트레이드)

**D. 미국주식** — 한국 개인 투자자의 절반이 검색하는 갈래
- `us-market-hours-kst` — 미국주식 거래시간, 서머타임·프리마켓 (미국주식 거래시간)
- `fx-spread-explained` — 환전 우대율 90%의 실제 비용 (환전 우대율)
- `us-dividend-withholding` — 미국주식 배당 15% 원천징수 (미국주식 배당세)
- `fractional-us-shares` — 소수점 매매의 장단점 (미국주식 소수점)
- `sp500-etf-domestic-vs-overseas` — S&P500, 국내 상장 ETF와 직구 중 무엇이 유리한가 (S&P500 ETF 세금)
- `us-cpi-release-time-kst` — 미국 CPI 발표 시간과 보는 법 (CPI 발표 시간)
- `fomc-schedule-2026-kst` — 2026년 FOMC 일정 한국시간 (FOMC 일정)

**E. 지표 읽기**
- `per-pbr-roe-basics` — PER·PBR·ROE, 코스피 지금 숫자로 (PER 뜻)
- `forward-per-and-eps` — 선행 PER과 EPS는 어디서 오나 (선행 PER)
- `market-cap-and-float` — 시가총액과 유통주식수 (시가총액 계산)
- `financial-statement-basics` — 재무제표 세 장에서 볼 것 (재무제표 보는 법)
- `cash-flow-basics` — 영업활동 현금흐름이 이익보다 중요한 때 (영업활동 현금흐름)

**F. 시장 구조**
- `kospi200-explained` — 코스피200 편입이 뜻하는 것 (코스피200 편입)
- `etf-tracking-error` — 괴리율·추적오차와 레버리지 ETF의 함정 (ETF 괴리율)
- `index-rebalancing` — 지수 정기변경이 주가를 흔드는 이유 (코스피200 정기변경)
- `investor-flows-how-to-read` — 외국인·기관·개인 수급 보는 법 (외국인 순매수 확인)
- `program-trading` — 프로그램 매매와 차익거래 (프로그램 매매 뜻)

**G. 배당**
- `dividend-record-date` — 배당기준일과 배당락일, 언제 사야 받나 (배당락일)
- `dividend-yield-screening` — 배당수익률과 배당성향 보는 법 (고배당주 찾는 법)
- `quarterly-dividend-korea` — 분기배당 하는 한국 회사 (분기배당 종목)
- `dividend-reform-2026` — 배당절차 개선으로 달라진 것 (배당절차 개선)

**H. 기업 이벤트**
- `ipo-subscription-how-to` — 공모주 청약: 균등·비례·증거금 (공모주 청약 방법)
- `stock-split-explained` — 액면분할이 주가에 미치는 것 (액면분할)
- `rights-vs-bonus-issue` — 유상증자와 무상증자 (유상증자 무상증자 차이)
- `buyback-and-cancellation` — 자사주 매입·소각의 원리 (자사주 소각)
- `delisting-and-watchlist` — 관리종목과 상장폐지 신호 (관리종목 뜻)
- `spinoff-types` — 인적분할과 물적분할 (물적분할 뜻)
- `convertible-bonds` — 전환사채·신주인수권부사채가 주주에게 뜻하는 것 (전환사채 뜻)

**I. 거시**
- `us-10y-yield-and-stocks` — 미국 10년물 금리가 오르면 주식은 (국채금리 주식)
- `usdkrw-and-stocks` — 원/달러 환율이 오르면 코스피는 (환율 주식 영향)
- `base-rate-and-stocks` — 기준금리와 주식, 금통위 보는 법 (기준금리 주식)
- `oil-price-and-korea` — 유가가 한국 증시에 오는 경로 (유가 주식 영향)
- `export-data-and-kospi` — 수출 통계가 코스피의 선행지표인 이유 (수출 지표 코스피)

**J. 실전**
- `preferred-shares-explained` — 우선주와 보통주, 괴리율 (우선주 뜻)
- `averaging-down` — 물타기와 분할매수는 무엇이 다른가 (분할매수 방법)
- `stop-loss-rules` — 손절 기준을 숫자로 세우는 법 (손절 기준)
- `portfolio-rebalancing` — 리밸런싱, 언제 얼마나 (리밸런싱 방법)
- `trading-journal` — 매매일지에 적을 다섯 가지 (매매일지 작성법)

## 주제가 떨어졌을 때

1. 이미 올라간 글의 **소제목**에서 파생 질문을 찾습니다 — 한 절이면 답할 수 있는데 따로 검색될 만한 것.
2. WebSearch로 네이버 지식iN·증권사 Q&A에 실제로 올라오는 질문을 찾고, 우리가 사실로 답할 수 있는 것만 고릅니다.
3. `docs/routine_guide_en.md`의 영어 주제 중 한국 투자자에게도 맞는 것을 다시 씁니다(번역이 아니라 다시 쓰기 —
   한국 투자자에게는 계좌·세금·접근 경로가 다릅니다).
4. 고른 주제를 완료 보고에 적습니다. 사람이 목록에 넣습니다.

## 절차

1. `pip install -r requirements.txt && apt-get install -y -qq fonts-nanum`
2. **주제.** 「주제 목록」의 고르는 법대로 — 어제와 다른 갈래에서, 그 갈래의 위에서부터. 이미 쓴 것은 뺍니다.
   `https://fermata.it.kr/wp-json/wp/v2/posts?search=<검색어>&_fields=title,link`로 같은 주제의 글이 이미
   있는지 봅니다(Checkpoint에 같은 질문이 있으면 다음 주제로).
3. **조사.** WebSearch·WebFetch로 규정·숫자를 **서로 다른 공식 출처 2곳 이상**에서 확인합니다. 출처 이름
   (국세청·금융감독원·한국거래소·금융투자협회·증권사 이름·언론사)을 본문에 그대로 적습니다 — 관문이 셉니다.
   세율·기준·시간처럼 바뀌는 숫자는 "2026년 9월 기준"이라고 본문에 박습니다.
4. **원고.** `editorial/guides/ko_<slug>.json`, 기준표와 같은 스키마에:
   - `kind` "feature", `series` "가이드", `date` KST 오늘, `checked` KST 오늘(머리말 `가이드 · 2026년 9월 16일 확인`이
     이 값으로 그려집니다), `slug`, `category_id` **509**(가이드 — 한국어 전용, 목록 페이지 `/guide/`; 153 Guides는 영어 전용입니다), `tags`(검색어 3~5개 — 목록의 괄호 안 검색어를
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
