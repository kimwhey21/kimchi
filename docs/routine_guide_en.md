# 영어 가이드 루틴 — 지시문 (2026-09-12, 유입 편성)

> 클라우드 루틴 "영어 가이드"의 프롬프트는 이 파일을 읽고 그대로 따르라는 몇 줄뿐입니다.
> 규칙을 고칠 때는 여기를 고치고 커밋하세요. 지시는 한국어, 원고는 영어입니다.

## 임무

**매일 11:00 KST에 영어 상시 가이드 한 편**을 써서 `editorial/guides/en_<slug>.json`에 커밋합니다. 커밋되면
`guide_publish.yml`이 올리고, 자동화 스위치가 켜져 있어 **바로 공개**됩니다. **관문을 통과한 것만 커밋합니다.**
워드프레스를 직접 만지지 않습니다.

왜 이 글인가(2026-09-12 실측): 이 사이트의 구글 노출 710건 중 700건이 2026-08-29~09-01에 올린 영어 가이드
9편에서 나왔고, 평균 게재순위 8.1위입니다. 검색어는 "kospi vs kosdaq", "kospi trading hours",
"can foreigners buy korean stocks" — 경쟁이 약한 질문형입니다. **2026-09-13부터 주 1편에서 주 7편으로 올렸습니다**
(사용자: "1번으로 가자 주 7편은 안 되냐"). 한국 주식을 사려는 외국인을 제대로 상대하는 영어 매체가 없고,
우리는 한국 데이터와 한국어 원문을 함께 가진 쪽입니다. 영어권 금융 광고 단가는 한국어의 서너 배입니다.

독자가 얻는 것: 질문의 답이 첫 절에, 실제 숫자(세율·시간·수수료)와 확인 날짜, 미국·유럽 투자자가 실제로
쓰는 경로(ETF·ADR·해외 계좌), 마지막에 무엇을 하면 되는지. 길이 1,200~2,000단어, 절 5~7개, 시각자료 2~3장.

**하루 한 편만.** 밀린 주제를 몰아 쓰지 않습니다. 하루 여러 편은 얇은 글을 만들고 구글이 색인을 미룹니다.

## 쓰지 않는 날

- 오늘 날짜의 `editorial/guides/en_*.json`이 이미 있으면 조용히 종료합니다.
- 아래 목록에서 아직 안 쓴 주제를 셋까지 시도했는데 **서로 다른 출처 2곳**(KRX·FSC·FSS·NTS·PwC·MSCI·운용사
  팩트시트·Reuters 등)에서 숫자를 확인하지 못하면 보고하고 종료합니다. **억지로 채우지 않습니다** — 하루 빠지는
  것이 틀린 세율 한 줄보다 낫습니다.
- 목록이 다 채워졌으면 「주제가 떨어졌을 때」 절을 따르고, 그래도 없으면 보고하고 종료합니다.

## 읽을 것

1. 기존 영어 가이드의 어법: `scripts/publish_guide_korea_stock_taxes.py`·`scripts/publish_guide_korea_trading_rules.py`
   (SECTIONS·CLOSING 문장을 봅니다 — 이 어조로 씁니다: 명확한 사실, 짧은 문장, "you"에게 말하기, 과장 없음).
2. `python -m scripts.recent_titles guide_en` — 최근 영어 가이드 제목과 "피할 것".
3. **이미 올라간 영어 글 전부**: `https://fermata.it.kr/wp-json/wp/v2/posts?categories=153&per_page=100&_fields=title,link,slug`
   — 주제가 겹치면 쓰지 않고, `related`에 2~3편을 겁니다(내부 링크가 기존 글의 순위도 올립니다).
4. 형식 예시(스키마): `editorial/guides/en_kospi-etf-for-us-investors.json`.
5. `data/price_kr_<최근>.json` — 예로 드는 지수·종목 숫자는 여기서만.

환경은 `docs/routine_common.md`의 "이 샌드박스에서 할 수 있는 것" 절과 같습니다(`python`이 없으면 `python3`).

## 주제 목록

파일명 `en_<slug>.json`. 괄호 안은 실제 검색어 — 제목과 첫 절에 들어가야 합니다.

**고르는 법**: 아래 아홉 갈래(A~I)에서 **어제와 다른 갈래**를 고르고, 그 갈래에서 위에 있는 것부터 씁니다.
같은 갈래를 이틀 연속 쓰지 않습니다 — 한 주가 한 주제로 쏠리면 콘텐츠 농장처럼 보입니다.
`ls editorial/guides/en_*.json`과 위 REST 조회로 이미 쓴 것을 먼저 빼십시오.

**A. 사는 법·계좌 (access)**
- `how-to-buy-samsung-electronics-abroad` — GDR, OTC, ETF로 삼성전자 사기 (buy samsung stock from us)
- `korean-adrs-for-us-investors` — 미국에 상장된 한국 기업 ADR 목록과 한계 (korean adr list)
- `buying-korean-stocks-from-europe` — 유럽 거주자의 경로와 규제 (buy korean stocks uk)
- `interactive-brokers-korean-stocks` — 해외 증권사로 한국 주식 사기: 되는 것과 안 되는 것 (interactive brokers korea)
- `omnibus-account-korea-explained` — 외국인통합계좌가 바꾼 것 (korea omnibus account)
- `korean-stock-ticker-symbols` — 6자리 코드와 .KS/.KQ 접미사 읽는 법 (korean stock ticker format)
- `minimum-investment-korean-stocks` — 최소 매수 단위와 소수점 거래 (korean stocks fractional shares)

**B. 세금·비용 (tax, cost)**
- `korean-dividend-withholding-for-us-residents` — 22% 대 조약 15% (korea dividend withholding tax)
- `korea-us-tax-treaty-forms` — W-8BEN과 실질귀속자 입증서류, 2월 마감 (korea tax treaty w-8ben)
- `korea-capital-gains-tax-for-foreigners` — 25% 보유 기준과 비과세 (korea capital gains tax foreigners)
- `reclaiming-korean-withholding-tax` — 과다 원천징수 환급 절차 (korea withholding tax refund)
- `total-cost-of-a-korean-trade` — 수수료·거래세·환전을 한 번에 계산 (cost of trading korean stocks)

**C. 시장 구조 (mechanics)**
- `kospi-200-explained` — 코스피200 편입이 뜻하는 것 (kospi 200)
- `korea-short-selling-rules` — 외국인 공매도 규제 (korea short selling ban)
- `korea-settlement-and-price-limits` — T+2, 상하한 30%, 매매정지 (kospi price limit)
- `korea-circuit-breakers-and-vi` — 서킷브레이커와 변동성완화장치 (korea circuit breaker)
- `korea-quadruple-witching` — 선물옵션 동시만기일 (korea quadruple witching)
- `korean-preferred-shares` — 우선주가 할인되는 이유 (samsung preferred shares)
- `block-deals-in-korea` — 시간외 대량매매가 주가에 미치는 것 (korea block deal)
- `korea-rights-offerings` — 유상증자와 무상증자 (korea rights offering)

**D. 배당 (dividends)**
- `korea-dividend-calendar` — 기준일·지급일·12월 쏠림 (korea dividend record date)
- `korean-high-dividend-stocks` — 고배당주와 배당성향 읽는 법 (korean dividend stocks)
- `korea-dividend-reform-2026` — 배당절차 개선으로 달라진 것 (korea dividend procedure reform)

**E. 종목·업종 (companies)** — 검색량이 가장 큰 갈래
- `samsung-electronics-for-foreign-investors` — 무엇으로 돈을 버는 회사인가 (samsung electronics stock)
- `sk-hynix-vs-micron` — HBM 노출을 어디서 살 것인가 (sk hynix stock)
- `korean-shipbuilders-explained` — HD현대중공업·한화오션과 수주 사이클 (korean shipbuilding stocks)
- `korean-defense-stocks` — 한화에어로스페이스와 수출 계약 (korean defense stocks)
- `korean-nuclear-and-power-stocks` — 두산에너빌리티와 원전 수출 (korea nuclear stocks)
- `korean-battery-makers` — LG에너지솔루션·삼성SDI·SK온 (korean battery stocks)
- `korean-biotech-and-cdmo` — 삼성바이오로직스·셀트리온 (korean biotech stocks)
- `naver-vs-kakao` — 두 플랫폼의 차이 (naver stock kakao stock)
- `k-beauty-stocks` — 화장품·뷰티 디바이스 (k beauty stocks)
- `hyundai-and-kia-for-us-investors` — 관세와 미국 판매 (hyundai motor stock)
- `korean-semiconductor-equipment` — 한미반도체 등 장비주 (korean semiconductor equipment stocks)

**F. 거시·원화 (macro)**
- `hedging-the-korean-won` — 원화 환헤지 (korean won hedge)
- `usdkrw-and-the-kospi` — 환율이 오르면 지수는 (usdkrw kospi correlation)
- `bank-of-korea-rate-decisions` — 금통위 일정과 읽는 법 (bank of korea rate decision)
- `korea-export-data-explained` — 수출 통계가 왜 세계 경기의 선행지표인가 (korea export data)
- `korea-market-holidays-2026` — 휴장일과 연휴 (korea stock market holidays)

**G. 정책·제도 (policy)**
- `korea-value-up-program` — 밸류업이 실제로 바꾼 것 (korea value up program)
- `korea-ftse-and-msci-classification` — 두 지수사의 분류가 다른 이유 (korea ftse classification)
- `korea-governance-discount` — 코리아 디스카운트의 실체 (korea discount)
- `korea-commercial-act-2026` — 상법 개정과 소액주주 (korea commercial act amendment)

**H. 데이터 읽는 법 (how to read)**
- `reading-krx-and-naver-finance-in-english` — 한국 사이트를 영어로 읽기 (naver finance english)
- `tracking-foreign-investor-flows` — 외국인 순매수 확인하는 법 (korea foreign investor flows)
- `korea-earnings-season-calendar` — 잠정실적과 정식 공시 (korea earnings season)
- `korean-analyst-ratings` — 목표주가와 투자의견의 관행 (korea analyst ratings)
- `korean-ipos-for-foreigners` — 공모주 청약이 가능한가 (korea ipo foreigners)

**I. 비교 (comparison)**
- `korea-vs-taiwan-semiconductors` — 두 반도체 시장 (korea vs taiwan semiconductor)
- `korea-vs-japan-for-foreign-investors` — 어느 쪽이 어떻게 다른가 (korea vs japan stock market)
- `kospi-vs-sp500` — 상관관계와 분산 효과 (kospi vs s&p 500)
- `what-moves-the-kospi` — 반도체·수출·원화 (what moves kospi)

## 주제가 떨어졌을 때

목록을 다 썼으면 새 주제를 이렇게 만듭니다.

1. 이미 올라간 영어 글의 **소제목**에서 파생 질문을 찾습니다 — 한 절이면 답할 수 있는데 따로 검색될 만한 것.
2. WebSearch로 `"korean stocks" + how/what/can` 꼴의 실제 질문을 찾고, 우리가 사실로 답할 수 있는 것만 고릅니다.
3. `docs/routine_guide_ko.md`의 한국어 주제 중 외국인에게도 맞는 것을 영어 독자용으로 다시 씁니다(번역이 아니라
   다시 쓰기 — 외국인에게는 계좌·세금·접근 경로가 다릅니다).
4. 고른 주제를 완료 보고에 적습니다. 사람이 목록에 넣습니다.

## 절차

1. `pip install -r requirements.txt && apt-get install -y -qq fonts-nanum`
2. **주제.** 「주제 목록」의 고르는 법대로 — 어제와 다른 갈래에서, 그 갈래의 위에서부터. 이미 쓴 것과
   겹치면 다음 것으로. 어제 무엇을 썼는지는 `ls -t editorial/guides/en_*.json | head -3`으로 봅니다.
3. **조사.** WebSearch·WebFetch로 **서로 다른 출처 2곳 이상**. 출처 이름을 본문에 영어로 그대로 적습니다
   (Korea Exchange, FSC, FSS, National Tax Service, PwC, MSCI, Reuters …) — 관문이 `source_check.EN_SOURCES`로 셉니다.
   바뀌는 숫자에는 "as of September 2026"을 본문에 박습니다(관문이 연도를 요구합니다).
4. **원고.** `editorial/guides/en_<slug>.json`:
   - `kind` "feature", `series` "Guide", `lang` "en", `date` KST 오늘, `checked` KST 오늘(머리말 `Investor Guide ·
     Checked September 16, 2026`), `slug`, `category_id` 153, `tags`(영어 검색어 3~5개), `related` 2~3개(기존 영어 가이드).
   - `ko.title`(필드 이름은 `ko`지만 영어로 씁니다): 30~70자, **검색어가 앞에**, 연도 표기가 자연스러우면 `(2026)`.
     예: `KOSPI ETFs for US Investors: EWY, FLKR and KORU Compared (2026)`.
   - `ko.narrative` 5~7절, 절마다 300자 이상. 1절이 답. 소제목 80자 이하, 문장형 소제목 환영
     (`The cost most people miss: Korea taxes the sale, not the profit`).
   - `ko.closing`: heading `The takeaway`, 두세 문단. 마지막 문단에 "not tax/investment advice" 한 줄.
   - `graphics` 2~3장: `cover`(featured, kicker "Investor Guide", subject 영어) + `fact_table`(section, 영어 표,
     `source` 필수) 또는 `checklist`. 한글은 어디에도 넣지 않습니다(관문이 막습니다).
   - 본문에 한글·마크다운 볼드 금지. 강조는 `<b>…</b>`. "watchlist" 같은 내부 용어 금지.
5. **관문.** `python -m src.feature_gate editorial/guides/en_<slug>.json --graphics <수>` → 통과 후
   `WORDPRESS_URL= WORDPRESS_USERNAME= WORDPRESS_APP_PASSWORD= python -m src.publish_feature editorial/guides/en_<slug>.json --render-only`
   → 그래픽을 `Read`로 봅니다(영어 글자가 잘리지 않는지).
6. `git add editorial/guides/en_<slug>.json && git commit -m "Guide: <title>" && git push origin HEAD:main`
   (거부되면 `git pull --rebase origin main` 뒤 다시).
7. 휴대폰 알림 한 번(PushNotification): `영어 가이드 커밋: <title> — 몇 분 안에 https://fermata.it.kr/<slug>/ 로 공개됩니다.`
   건너뛰었거나 실패했을 때도 한 번, 이유와 함께. (영어 가이드는 네이버·텔레그램·스레드에 올리지 않습니다 — 한국어 채널입니다.)

## 절대 규칙

- 규정·숫자는 출처 2곳이 맞을 때만. 세율은 조약·거주지에 따라 다르다는 단서를 붙입니다.
- 특정 증권사·상품을 추천하지 않습니다.
- 한 편만, 원고 JSON 하나만 커밋합니다.

## 완료 보고

원고 경로, 제목, 출처 2곳 이상, 그래픽 수, 관문 출력 전문, 커밋 해시. 건너뛴 날은 이유.
