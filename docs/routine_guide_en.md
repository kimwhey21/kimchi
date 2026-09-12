# 영어 가이드 루틴 — 지시문 (2026-09-12, 유입 편성)

> 클라우드 루틴 "영어 가이드"의 프롬프트는 이 파일을 읽고 그대로 따르라는 몇 줄뿐입니다.
> 규칙을 고칠 때는 여기를 고치고 커밋하세요. 지시는 한국어, 원고는 영어입니다.

## 임무

수요일 09:00 KST에 **외국인 투자자가 검색하는 질문 하나에 답하는 영어 상시 가이드 한 편**을 써서
`editorial/guides/en_<slug>.json`에 커밋합니다. 커밋되면 `guide_publish.yml`이 올리고, 자동화 스위치가 켜져
있어 **바로 공개**됩니다. **관문을 통과한 것만 커밋합니다.** 워드프레스를 직접 만지지 않습니다.

왜 이 글인가(2026-09-12 실측): 이 사이트의 구글 클릭 4건·노출 710건 중 700건이 2026-08-29~09-01에 올린
영어 가이드 9편에서 나왔고, 평균 게재순위 8.1위입니다. 검색어는 "kospi vs kosdaq", "kospi trading hours",
"can foreigners buy korean stocks", "korean brokerage account" — 경쟁이 약한 질문형 검색어입니다. 10편을 더해
1페이지 상단을 노립니다. 영어 금융 광고 단가가 한국어보다 높아 수익도 이쪽이 먼저 납니다.

독자가 얻는 것: 질문의 답이 첫 절에, 실제 숫자(세율·시간·수수료)와 확인 날짜, 미국·유럽 투자자가 실제로
쓰는 경로(ETF·ADR·해외 계좌), 마지막에 무엇을 하면 되는지. 길이 1,200~2,000단어, 절 5~7개, 시각자료 2~3장.

## 쓰지 않는 날

- 후보 목록이 다 쓰였으면(`ls editorial/guides/en_*.json`) 보고하고 종료합니다.
- 규정·숫자를 **서로 다른 공식 출처 2곳**(KRX·FSC·FSS·NTS·PwC·MSCI·증권사 안내·Reuters 등)에서 확인하지
  못하면 보고하고 종료합니다. 틀린 세율 한 줄이 글 전체의 신뢰를 깎습니다.

## 읽을 것

1. 기존 영어 가이드의 어법: `scripts/publish_guide_korea_stock_taxes.py`·`scripts/publish_guide_korea_trading_rules.py`
   (SECTIONS·CLOSING 문장을 봅니다 — 이 어조로 씁니다: 명확한 사실, 짧은 문장, "you"에게 말하기, 과장 없음).
2. `python -m scripts.recent_titles guide_en` — 최근 영어 가이드 제목(첫 편이면 "원고가 없습니다").
3. 이미 올라간 9편의 제목·주소: `https://fermata.it.kr/wp-json/wp/v2/posts?categories=153&per_page=20&_fields=title,link`
   — 겹치는 주제는 쓰지 않고, `related`에 2~3편을 겁니다(내부 링크가 9편의 순위도 올립니다).
4. 형식 예시(스키마): `editorial/features/us_2026-09-06_deere_upgrade.json`.
5. `data/price_kr_<최근>.json` — 예로 드는 지수·종목 숫자는 여기서만.

환경은 `docs/routine_common.md`의 "이 샌드박스에서 할 수 있는 것" 절과 같습니다(`python`이 없으면 `python3`).

## 주제 후보 (위에서부터, 아직 없는 것을 고른다)

파일명 `en_<slug>.json`. 괄호 안은 실제 검색어 — 제목과 첫 절에 들어가야 합니다.

1. `kospi-etf-for-us-investors` — KOSPI ETFs for US investors: EWY vs FLKR vs KORU (kospi etf, korea etf)
2. `how-to-buy-samsung-electronics-abroad` — How to buy Samsung Electronics from abroad: GDR, OTC, ETFs (buy samsung stock)
3. `korean-dividend-withholding-for-us-residents` — Korean dividend withholding for US residents: 22% vs 15% treaty rate (korea dividend withholding tax)
4. `korea-stock-market-holidays-2026` — Korea stock market holidays 2026 (korea market holidays, krx holidays 2026)
5. `kospi-200-explained` — KOSPI 200 explained: what is in it and why it moves (kospi 200)
6. `hedging-the-korean-won` — Hedging the Korean won as a foreign stockholder (korean won hedge)
7. `reading-krx-and-naver-finance-in-english` — Reading KRX and Naver Finance data in English (naver finance english)
8. `sk-hynix-vs-micron-hbm-exposure` — SK Hynix vs Micron: how foreigners get HBM exposure (sk hynix stock buy)
9. `korea-short-selling-rules` — Korea's short-selling rules for foreign investors (korea short selling ban)
10. `korea-value-up-program` — Korea's Value-Up program explained (korea value up program)
11. `korean-ipos-for-foreigners` — Korean IPOs: can foreigners subscribe? (korea ipo foreigners)
12. `what-moves-the-kospi` — What moves the KOSPI: chips, exporters and the won (what moves kospi)
13. `korean-preferred-shares` — Korean preferred shares: why Samsung "pref" trades at a discount (samsung preferred shares)
14. `korea-dividend-calendar` — How Korean dividends work: record dates, payout timing, the December cliff (korea dividend record date)
15. `korea-t2-settlement-and-price-limits` — Settlement, price limits and halts on the Korean market (kospi price limit)

## 절차

1. `pip install -r requirements.txt && apt-get install -y -qq fonts-nanum`
2. **주제.** 목록에서 아직 없는 가장 위의 것. 기존 9편과 겹치면 다음으로.
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
   건너뛰었거나 실패했을 때도 한 번, 이유와 함께. (영어 가이드는 네이버에 올리지 않습니다.)

## 절대 규칙

- 규정·숫자는 출처 2곳이 맞을 때만. 세율은 조약·거주지에 따라 다르다는 단서를 붙입니다.
- 특정 증권사·상품을 추천하지 않습니다.
- 한 편만, 원고 JSON 하나만 커밋합니다.

## 완료 보고

원고 경로, 제목, 출처 2곳 이상, 그래픽 수, 관문 출력 전문, 커밋 해시. 건너뛴 날은 이유.
