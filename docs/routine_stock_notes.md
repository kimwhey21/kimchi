# 월간 종목 노트 루틴 — 지시문 (2026-09-12, 유입 편성 3번)

> 클라우드 루틴 "종목 노트"의 프롬프트는 이 파일을 읽고 그대로 따르라는 몇 줄뿐입니다.
> 규칙을 고칠 때는 여기를 고치고 커밋하세요.

## 임무

매달 1일 09:00 KST에 종목 허브 페이지(`/stocks/<slug>/`, 37개)의 「최근 흐름」 절을 채우는 노트 파일
`editorial/stocks/notes_<YYYY-MM>.json`을 쓰고 커밋합니다. 커밋되면 `stock_pages.yml`이 페이지를 다시 만듭니다.
글이 아니라 **종목마다 두세 문장**입니다 — 지난달 이 종목에 무슨 일이 있었고 지금 어디에 있는지.

숫자(등락·고저·차트)는 `src/stock_pages.py`가 시세 파일에서 자동으로 채우므로 노트에 등락률을 다시 적을 필요가
없습니다. 노트가 하는 일은 **왜 움직였는지**와 **다음에 볼 것**입니다.

## 읽을 것

1. `config/stock_pages.yaml` — 종목 목록과 회사 소개(노트와 겹치지 않게).
2. 지난달 시황 원고 `editorial/kr_<날짜>.json`·`editorial/us_<날짜>.json`의 제목·소제목·`stock_section`에서 그 종목이
   나온 대목. 지난달 Checkpoint(`editorial/features/`)와 주간 결산(`editorial/weekly/review_*.json`)도 봅니다.
3. `data/price_kr_<최근>.json`·`data/price_us_<최근>.json` — 어느 자리인지 확인(숫자는 페이지가 그립니다).
4. `docs/editorial-style.md`의 「낱말」·「리듬」 절 — 금지 낱말과 문장 길이.

## 절차

1. `pip install -r requirements.txt`
2. 종목마다 지난달 우리 글에 나온 사실로 2~3문장(60~500자)을 씁니다. 우리 글에 한 번도 안 나온 종목은 WebSearch로
   지난달 큰 일(실적·계약·규제) 하나를 **출처 이름과 함께** 적습니다. 없으면 "지난달 우리 시황에 주인공으로 나온 날은
   없었습니다"로 시작해 어느 자리인지만 씁니다.
3. 파일 형식:
   ```json
   {"month": "2026-10", "checked": "2026-10-01",
    "notes": {"005930": "지난달 …. 다음 확인 지점은 …입니다.", "NVDA": "…"}}
   ```
   37개 티커가 모두 있어야 합니다(`config/stock_pages.yaml`의 `ticker`).
4. **검사.** `python -m src.stock_pages --check-notes editorial/stocks/notes_<YYYY-MM>.json` — 통과 전에는
   커밋하지 않습니다(빠진 종목·길이·포지션 화법·마크다운 볼드·"오를 것이다"식 예측을 막습니다).
5. `git add editorial/stocks/notes_<YYYY-MM>.json && git commit -m "종목 노트: <YYYY-MM>" && git push origin HEAD:main`
   (거부되면 `git pull --rebase origin main` 뒤 다시).
6. 휴대폰 알림 한 번(PushNotification): `종목 노트 <YYYY-MM> 커밋 — 몇 분 안에 https://fermata.it.kr/stocks/ 37개 페이지가 갱신됩니다.`

## 절대 규칙

- 예측하지 않습니다. "실적이 예상을 넘으면 X를 본다"처럼 조건으로 씁니다.
- 포지션 화법("제가 매수") 금지. 판단은 "우리는 이렇게 봅니다".
- 등락률·가격은 시세 파일에 있는 값만, 그것도 꼭 필요할 때만. 검색 결과의 숫자를 옮겨 적지 않습니다.
- 커밋하는 것은 노트 JSON 하나뿐입니다.

## 완료 보고

파일 경로, 종목 수, 검사 출력, 커밋 해시. 우리 글에 없어 WebSearch로 채운 종목과 그 출처.
