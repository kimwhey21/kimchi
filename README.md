# market-brief

하루 두 번(미국장 마감 / 한국장 마감) 시황을 자동으로 정리해 블로그 초안용 HTML을 만들어주는 스크립트입니다.

## 어떻게 동작하나요

```
fetch_us.py / fetch_kr.py   →   generate_post.py   →   render_html.py
   (실제 시세 수집)              (제목·설명·종목 선별)      (최종 HTML 생성)
```

1. **시세 수집** — `config/watchlist_us.yaml`, `config/watchlist_kr.yaml`에 등록된 지수·종목의
   실제 가격, 등락률, 최근 며칠간의 종가 흐름을 가져옵니다. (미국: yfinance / 한국: FinanceDataReader)
2. **문구 생성** — Claude API에 그 가격 데이터를 통째로 넘기고, 웹 검색 도구로 "왜 그런 움직임이
   나왔는지"를 찾아 앵커 톤 문장으로 정리하게 합니다. 제목, 소제목별 설명, 오늘 다룰 만한 종목 선정,
   다음 주 일정까지 이 단계에서 나옵니다.
3. **HTML 렌더링** — 2번이 고른 종목의 실제 숫자를 1번 데이터에서 다시 채워 넣어 카드+스파크라인
   차트가 있는 HTML 파일로 만듭니다.

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
`ANTHROPIC_API_KEY`를 등록하면 그대로 동작합니다.

- 결과 HTML은 Actions 실행 화면의 "Artifacts"에서 내려받을 수 있습니다.
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

## 아직 안 되어 있는 것 (다음 단계)

- **블로그 자동 게시**: 블로그 플랫폼이 정해지면 `render_html.py` 다음에 "임시저장으로 업로드"
  단계를 추가하고, 텔레그램 등으로 미리보기+게시 버튼을 보내는 단계를 이어 붙이면 됩니다.
  지금은 로컬 HTML 파일로 저장하는 데까지만 구현되어 있습니다.
- **뉴스 소스 다양화**: 지금은 Claude의 웹 검색 도구 하나에만 의존합니다. 특정 언론사 RSS를
  추가로 넣고 싶다면 `generate_post.py`의 프롬프트에 함께 넣어주는 방식으로 확장할 수 있습니다.

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
│   ├── fetch_us.py       # 미국 시세 수집
│   ├── fetch_kr.py       # 한국 시세 수집
│   ├── generate_post.py  # Claude API로 제목/본문/종목선별/캘린더 생성
│   ├── render_html.py    # 최종 HTML 조립
│   └── main.py           # 전체 파이프라인 실행
├── templates/
│   └── post.html.j2
├── .github/workflows/
│   └── market_brief.yml  # 매일 2회 자동 실행
├── requirements.txt
└── .env.example
```
