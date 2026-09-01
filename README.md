# market-brief

하루 두 번(미국장 마감 / 한국장 마감) 시황을 자동으로 정리해 블로그 초안용 HTML을 만들어주는 스크립트입니다.

## 어떻게 동작하나요

```
fetch_us.py / fetch_kr.py   →   generate_post.py   →   render_html.py   →   publish_wordpress.py
   (실제 시세 수집)              (제목·설명·종목 선별)      (최종 HTML 생성)      (워드프레스 임시저장)
                                      ↑
                              fetch_news.py (언론사 RSS 헤드라인)
```

1. **시세 수집** — `config/watchlist_us.yaml`, `config/watchlist_kr.yaml`에 등록된 지수·종목의
   실제 가격, 등락률, 최근 며칠간의 종가 흐름을 가져옵니다. (미국: yfinance / 한국: FinanceDataReader)
2. **문구 생성** — Claude API에 그 가격 데이터와, 언론사 RSS(`fetch_news.py`)에서 모은 최근
   헤드라인 목록을 함께 넘기고, 웹 검색 도구로 "왜 그런 움직임이 나왔는지"를 찾아 앵커 톤
   문장으로 정리하게 합니다. 제목, 소제목별 설명, 오늘 다룰 만한 종목 선정, 다음 주 일정까지
   이 단계에서 나옵니다.
3. **HTML 렌더링** — 2번이 고른 종목의 실제 숫자를 1번 데이터에서 다시 채워 넣어 카드+스파크라인
   차트가 있는 HTML 파일로 만듭니다.
4. **워드프레스 업로드** — `.env`에 `WORDPRESS_*` 값이 설정돼 있으면, 완성된 HTML을 워드프레스에
   **임시저장(draft)**으로 자동 업로드합니다. 발행 여부는 사람이 검수 후 워드프레스 관리자
   화면에서 직접 결정합니다 (자동으로 바로 공개 발행되지 않음).

**중요 — 숫자의 출처**: 가격/등락률 숫자는 항상 1번(실시간 시세)에서만 나옵니다. Claude는 "어떤 종목을
다룰지"와 "왜 그랬는지 설명"만 맡고, 숫자 자체를 새로 만들어내는 데는 관여하지 않습니다. 그래야
"팩트만" 원칙이 자동화 이후에도 유지됩니다.

## 설치

```bash
git clone <이 저장소>
cd market-brief
pip install -r requirements.txt
cp .env.example .env   # .env를 열어서 ANTHROPIC_API_KEY 값을 채워주세요
```

**Anthropic API 키는 claude.ai 구독과는 별개입니다.** platform.claude.com(콘솔)에서
Settings → API keys로 새로 발급받아야 하고, 사용한 만큼 별도로 과금됩니다.

**사진을 넣으려면 Unsplash API 키도 필요합니다** (선택사항). unsplash.com/developers 에서
무료로 발급받을 수 있습니다. 비워두면 인사이트 섹션이 사진 없이 텍스트만으로 나옵니다.

## 결과물의 시각 구성

- **지수 카드** → 표(table)
- **업종·테마** → 카드
- **주요 종목** → 막대 차트
- **인사이트 소재** → 소재별 사진 1장 + 출처 표기 (Unsplash API 사용, 사진작가 크레딧 자동 표기)
- **캘린더** → 리스트

## 실행

```bash
python -m src.main --market us   # 미국장
python -m src.main --market kr   # 한국장
```

`output/us_2026-08-21.html` 같은 파일이 생성됩니다. 브라우저로 열어서 확인하고, 마음에 들면
내용을 복사해서 블로그에 붙여넣으면 됩니다.

## 자동 스케줄 (GitHub Actions)

`.github/workflows/market_brief.yml`에 평일 기준 한국시간 07:00(미국장)/16:00(한국장) 두 번
자동 실행되도록 cron이 설정되어 있습니다. GitHub 저장소의 Settings → Secrets → Actions에
아래 값을 등록하면 그대로 동작합니다.

- `ANTHROPIC_API_KEY` — 필수
- `UNSPLASH_ACCESS_KEY` — 선택 (없으면 사진 없이 렌더링)
- `WORDPRESS_URL`, `WORDPRESS_USERNAME`, `WORDPRESS_APP_PASSWORD` — 선택 (없으면 워드프레스
  업로드 단계만 건너뛰고, 로컬 HTML 생성까지는 그대로 진행)
- `SUBSCRIBE_FORM_ACTION` — 선택 (구독 폼 액션 URL)

- 결과 HTML은 Actions 실행 화면의 "Artifacts"에서 백업용으로도 내려받을 수 있습니다.
- cron 시간은 대략적인 값입니다. 정확한 장마감 타이밍과 살짝 오차가 있을 수 있어 필요하면
  조정하세요.

## 인사이트 섹션 사진

`insight_section` 각 소재에는 Unsplash에서 가져온 사진이 자동으로 붙습니다 (일반 이미지
검색과 달리 Unsplash는 사진작가가 자유 이용을 허락한 사진만 모아둔 곳이라 저작권 걱정 없이
블로그에 쓸 수 있습니다). 이 기능을 쓰려면:

1. https://unsplash.com/developers 에서 무료 가입 (심사 없음, 즉시 발급)
2. "New Application" 생성 → Access Key 발급
3. `.env`에 `UNSPLASH_ACCESS_KEY=발급받은키` 추가

키가 없어도 파이프라인은 멈추지 않습니다 — 사진 없이 아이콘만으로 렌더링됩니다.

## 뉴스 소스 (언론사 RSS)

`src/fetch_news.py`가 시장별로 지정된 언론사 RSS를 조회해 최근 헤드라인 목록을 모읍니다.
Claude의 웹 검색 도구 하나에만 의존하던 것을 보완하는 용도로, 문구 생성 프롬프트에
"참고용 헤드라인 목록"으로 함께 들어갑니다 — Claude가 그날 실제로 어떤 기사가 나왔는지
먼저 훑어보고, 그중 관련 있는 것만 web_search로 사실관계를 재확인한 뒤 씁니다(헤드라인
문구를 그대로 베끼지 않음).

- 기본 소스: 한국장 — 한국경제, 연합뉴스, 이데일리 / 미국장 — CNBC, Yahoo Finance, Investing.com
- 소스를 추가/삭제하려면 `src/fetch_news.py`의 `FEEDS` 딕셔너리를 수정하면 됩니다.
- RSS 요청은 무료라 Claude API 비용에 영향이 없습니다. 특정 피드가 그날 응답하지 않아도
  개별적으로 건너뛰고 파이프라인은 계속 진행됩니다.
- 매일경제(mk.co.kr)는 Cloudflare 봇 차단이 걸려 있어 목록에서 제외했습니다.

## 아직 안 되어 있는 것 (다음 단계)

- **발행 알림**: 지금은 워드프레스에 임시저장까지만 자동으로 올라가고, 검수는 사람이
  워드프레스 관리자 화면에 직접 들어가서 합니다. 텔레그램 등으로 "새 임시저장 글이
  올라왔습니다 + 미리보기 링크"를 보내는 알림 단계를 붙이면 검수 과정이 더 편해집니다.
- **미국장 영어/한국장 영어 이외의 다국어**: 지금은 한국장(kr) 결과물만 `--en` 옵션으로
  영어판을 함께 만듭니다 (`translate_post.py`). 미국장은 원문이 이미 영어 자료 기반이라
  별도 번역판이 없습니다.

## 종목 목록 수정

`config/watchlist_us.yaml`, `config/watchlist_kr.yaml`을 열어서 지수·종목을 추가/삭제하면
됩니다. 여기 있는 종목이 전부 게시되는 게 아니라, 이 중에서 Claude가 "그날 의미 있었던 종목"만
최대 8개 골라서 보여줍니다.

## 비용 대략치

시세 수집 자체는 무료(yfinance/FinanceDataReader)지만, 문구 생성 단계는 Claude API 사용량만큼
과금됩니다. Sonnet 5 기준 입력 $2 / 출력 $10 (100만 토큰당, 2026년 8월 기준)에 웹 검색 1,000회당
$10이 별도로 붙습니다. 한 번 실행에 검색 5~8회 정도면 회당 대략 몇십~백원대 수준일 것으로
예상되지만, 정확한 금액은 회차마다 다르고 요금 체계도 바뀔 수 있으니 실제 청구는 콘솔의 사용량
페이지에서, 최신 단가는 https://platform.claude.com/docs/en/about-claude/pricing 에서 확인하세요.

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
│   ├── fetch_images.py        # Unsplash 인사이트 사진 검색
│   ├── generate_post.py       # Claude API로 제목/본문/종목선별/캘린더 생성
│   ├── translate_post.py      # 한국장 결과물의 영어 번역판 생성 (--en)
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
