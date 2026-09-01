# market-brief

하루 두 번(미국장 마감 / 한국장 마감) 시황을 자동으로 정리해 블로그 초안용 HTML을 만들어주는 스크립트입니다.

## 어떻게 동작하나요

```
fetch_us.py / fetch_kr.py   →   generate_free.py   →   render_html.py   →   publish_wordpress.py
   (실제 시세 수집)              (무료 시황 초안 생성)        (최종 HTML 생성)      (워드프레스 임시저장)
                                      ↑
                              fetch_news.py (언론사 RSS 헤드라인)
```

1. **시세 수집** — `config/watchlist_us.yaml`, `config/watchlist_kr.yaml`에 등록된 지수·종목의
   실제 가격, 등락률, 최근 며칠간의 종가 흐름을 가져옵니다. (미국: yfinance / 한국: FinanceDataReader)
2. **무료 시황 생성** — 가격 데이터와 언론사 RSS(`fetch_news.py`)의 최근 헤드라인을 정해진
   형식으로 조합합니다. 외부 생성형 AI API를 호출하지 않으며, 확인하지 못한 시장 원인이나
   전망은 추측하지 않습니다. 한국장 예약 실행은 같은 시세에서 한국어판과 영어판을 각각
   직접 작성합니다. 영어판은 한국어 원고를 번역하는 방식이 아닙니다.
3. **HTML·대표 이미지 렌더링** — 실제 가격·등락률을 카드에 채워 HTML 파일을 만들고,
   같은 수치로 1200×630 대표 이미지를 제작합니다. 검증되지 않은 사진 검색 결과를 자동 사용하지 않습니다.
4. **워드프레스 업로드** — `.env`에 `WORDPRESS_*` 값이 설정돼 있으면, 완성된 HTML을 워드프레스에
   **임시저장(draft)**으로 자동 업로드합니다. 발행 여부는 사람이 검수 후 워드프레스 관리자
    화면에서 직접 결정합니다 (자동으로 바로 공개 발행되지 않음).

한국장에서는 코스피·코스닥과 관심 종목의 거래일이 일치하는지 업로드 전에 검사합니다.
16시 직후 데이터가 아직 섞여 있으면 45초 간격으로 다시 확인하며, 끝내 맞지 않으면 잘못된
수치를 섞어 올리는 대신 실행을 실패 처리합니다. 환율만 기준일이 다르면 카드와 문장에 기준일을 표시합니다.

한국어 제목과 소제목은 `docs/editorial-style.md`를 기준으로 작성하며,
`src/editorial_quality.py`가 대표적인 번역투·의인화 표현을 임시저장 전에 차단합니다.

**중요 — 숫자와 설명의 출처**: 가격/등락률 숫자는 항상 1번(실시간 시세)에서만 나옵니다. 시장 원인을
자동으로 만들어내지 않으며, 뉴스는 출처가 표시된 RSS 헤드라인으로만 제공합니다.

## 설치

```bash
git clone <이 저장소>
cd market-brief
pip install -r requirements.txt
cp .env.example .env   # 워드프레스 임시저장을 쓰려면 WORDPRESS_* 값을 채우세요
```

자동 시황 생성에는 Anthropic·OpenAI 등 생성형 AI API 키가 필요하지 않습니다.

## 결과물의 시각 구성

- **지수 카드** → 표(table)
- **업종·테마** → 카드
- **주요 종목** → 막대 차트
- **최신 뉴스 헤드라인** → 출처와 함께 표시되는 RSS 제목 목록
- **대표 이미지** → 지수·환율·관심 종목 최대 등락을 담은 1200×630 데이터 그래픽

한국장 지수는 네이버 금융 실시간 응답에서 장 상태가 `CLOSE`로 확인된 확정값만
사용합니다. 원/달러는 서울 외환시장 종가로 오인하지 않도록 하나은행 최신 고시환율과
기준시각을 함께 표시합니다.

## 실행

```bash
python -m src.main --market us   # 미국장
python -m src.main --market kr --en   # 한국장 한국어판 + 영어판
python -m src.main --market kr --en --dry-run   # 업로드 없이 파일·품질만 검사
```

`output/us_2026-08-21.html` 같은 파일이 생성됩니다. 브라우저로 열어서 확인하고, 마음에 들면
내용을 복사해서 블로그에 붙여넣으면 됩니다.

## 자동 스케줄 (GitHub Actions)

`.github/workflows/market_brief.yml`에 평일 기준 한국시간 07:00(미국장)/16:00(한국장) 두 번
자동 실행되도록 cron이 설정되어 있습니다. 16:00 한국장 실행은 한국어판과 영어판을 모두
만들어 워드프레스에 임시저장합니다. GitHub 저장소의 Settings → Secrets → Actions에
아래 값을 등록하면 그대로 동작합니다.

- `WORDPRESS_URL`, `WORDPRESS_USERNAME`, `WORDPRESS_APP_PASSWORD` — 선택 (없으면 워드프레스
  업로드 단계만 건너뛰고, 로컬 HTML 생성까지는 그대로 진행)
- `SUBSCRIBE_FORM_ACTION` — 선택 (구독 폼 액션 URL)

- 결과 HTML은 Actions 실행 화면의 "Artifacts"에서 백업용으로도 내려받을 수 있습니다.
- cron 시간은 대략적인 값입니다. 정확한 장마감 타이밍과 살짝 오차가 있을 수 있어 필요하면
  조정하세요.

## 뉴스 소스 (언론사 RSS)

`src/fetch_news.py`가 시장별로 지정된 언론사 RSS를 조회해 최근 헤드라인 목록을 모읍니다.
자동 글에는 출처와 제목만 표시하며, 기사 본문을 읽지 않은 상태에서 시장 원인을 추론하지
않습니다.

- 기본 소스: 한국장 — 한국경제 증권, 연합뉴스 경제, 이데일리 주식·펀드 / 미국장 — CNBC, Yahoo Finance, Investing.com
- 장 마감·지수·환율·수급과 직접 관련된 제목을 먼저 거르고, 매체별로 번갈아 최대 두 건씩 골라 관련성과 출처 다양성을 함께 지킵니다.
- 소스를 추가/삭제하려면 `src/fetch_news.py`의 `FEEDS` 딕셔너리를 수정하면 됩니다.
- RSS 요청은 무료입니다. 특정 피드가 그날 응답하지 않아도
  개별적으로 건너뛰고 파이프라인은 계속 진행됩니다.
- 매일경제(mk.co.kr)는 Cloudflare 봇 차단이 걸려 있어 목록에서 제외했습니다.

## 아직 안 되어 있는 것 (다음 단계)

- **발행 알림**: 지금은 워드프레스에 임시저장까지만 자동으로 올라가고, 검수는 사람이
  워드프레스 관리자 화면에 직접 들어가서 합니다. 텔레그램 등으로 "새 임시저장 글이
  올라왔습니다 + 미리보기 링크"를 보내는 알림 단계를 붙이면 검수 과정이 더 편해집니다.
- **번역 연결 검수**: 영어판은 Polylang의 영어 글로 저장되지만, 한국어 원문과 영어판을
  번역 쌍으로 묶는 관리자 화면 연결은 사이트 설정에 따라 수동 확인이 필요할 수 있습니다.

## 종목 목록 수정

`config/watchlist_us.yaml`, `config/watchlist_kr.yaml`을 열어서 지수·종목을 추가/삭제하면
됩니다. 여기 있는 종목 중 등락 폭이 큰 최대 6개를 자동으로 보여줍니다.

## 비용 대략치

시세 수집(yfinance/FinanceDataReader)과 RSS 조회는 무료입니다. 기본 자동 발행은 외부 생성형
AI API를 호출하지 않으므로 실행당 API 사용료가 발생하지 않습니다.

## 폴더 구조

```
market-brief/
├── config/
│   ├── watchlist_us.yaml
│   └── watchlist_kr.yaml
├── src/
│   ├── fetch_us.py            # 미국 시세 수집
│   ├── fetch_kr.py            # 한국 시세 수집
│   ├── fetch_foreign_flows.py # 외국인 매매동향 수집 (한국장)
│   ├── fetch_news.py          # 언론사 RSS 최근 헤드라인 수집
│   ├── generate_free.py       # API 비용 없는 시황 초안 생성
│   ├── generate_free_en.py    # 같은 시세에서 영어 시황 직접 생성
│   ├── editorial_quality.py   # 한국어 번역투·의인화 표현 검사
│   ├── editorial_quality_en.py # 영어 원고 언어·구조 검사
│   ├── render_html.py         # 최종 HTML 조립
│   ├── render_text.py         # 텍스트(.txt) 버전 조립
│   ├── publish_wordpress.py   # 워드프레스 임시저장 업로드
│   ├── publish_guide.py       # 상시(evergreen) 가이드 글 발행
│   ├── history.py             # 최근 제목/발행 이력 기록 (중복 발행 방지)
│   └── main.py                # 전체 파이프라인 실행
├── templates/
│   └── post.html.j2
├── .github/workflows/
│   └── market_brief.yml  # 매일 2회 자동 실행
├── requirements.txt
└── .env.example
```
