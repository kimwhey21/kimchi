# market-brief 작업 시 지켜야 할 것

이 파일은 이 저장소에서 작업하는 모든 AI 코딩 에이전트(Codex, Claude Code 등)가
공통으로 따라야 할 규칙입니다. Claude Code를 쓸 때는 `CLAUDE.md`도 동일한
내용을 담고 있습니다 — 둘 중 하나만 있어도 되게 일부러 중복해뒀습니다.

## 검증 규칙 (반드시 지킬 것)

- **이미지는 쓰기 전에 실제로 다운받아 눈으로 확인한다.** alt text나 검색어만
  보고 판단하지 말 것. 실제로 있었던 일: Unsplash에서 "Korean won
  currency"/"Korean won banknote"로 검색했는데 결과가 중국 위안화(마오쩌둥
  초상) 사진이었다. alt text는 "assorted banknotes"처럼 그럴듯해 보였지만
  실제 사진은 완전히 틀렸다. 대표 이미지(featured image)든 본문 삽입
  이미지든, 발행 전에 다운받은 파일을 직접 봐야 한다.
- **통화/지수 같은 추상적 개념은 이미지 검색이 특히 안 맞을 확률이 높다.**
  브랜드/제품처럼 사진으로 명확히 알아볼 수 있는 대상(개별 종목명, 회사
  로고)은 검색이 비교적 안전하지만, "원화", "코스피", "금리" 같은 추상
  개념은 사진 자체가 없거나 다른 나라 것이 섞여 나올 때가 많다.
  `src/main.py`의 `_featured_image()`가 이 이유로 watchlist(개별 종목)만
  대상으로 하고 macro(지수·환율·금리·원자재)는 일부러 제외한다 — 이 원칙을
  다른 이미지 자동화에도 유지할 것.
- **워드프레스 관리자 화면(플러그인 설정 등)의 정확한 위치는 기억으로
  추측하지 말고 실제로 검색해서 확인한 뒤 안내한다.** 실제로 있었던 일: Rank
  Math의 OpenGraph 썸네일 설정 위치를 세 번 잘못 추측했다가(존재하지 않는
  탭 이름들) 검색해서야 정확한 위치("Titles & Meta → Global Meta" 탭)를
  찾았다. 게다가 알고 보니 그 설정은 이미 올바르게 되어 있었다 — 확인
  없이 추측한 게 완전히 시간 낭비였다.
- **디버깅할 때 원인을 추측만으로 단정하지 말 것.** 실제로 있었던 일: 발행이
  안 됐던 원인을 GitHub Actions 실행 시간(4초 만에 실패)만 보고 "yfinance가
  클라우드 IP를 막았을 것"으로 추측해서 안내했는데, 실제 로그를 보니 전혀
  무관한 Anthropic 콘솔 API 크레딧 소진이 원인이었다. 근거가 간접적일 때는
  "이건 추측이다"라고 명시하고, 가능하면 실제 로그/트레이스백을 요청하거나
  직접 확인한 뒤 결론을 내릴 것.
- 화면(홈페이지, 발행된 글, 템플릿 변경사항)을 눈으로 확인해야 할 때는
  Playwright 헤드리스 브라우저(`playwright` pip 패키지 + Chromium, 이미
  이 컴퓨터에 설치돼 있음)로 스크린샷을 찍어서 실제로 본 뒤 결과를
  보고한다. curl로 HTML 구조만 확인하고 "됐다"고 하지 말 것 — 구조가
  맞아도 실제로 보면 다를 수 있다(예: 페이지 제목이 두 번 겹쳐 보이는
  버그는 curl로는 안 보이고 스크린샷으로만 발견됨).
  - NinjaFirewall이 헤드리스 브라우저 User-Agent를 봇으로 차단할 때가
    있다 — 그럴 땐 실제 브라우저 User-Agent 문자열을 지정하면 통과된다.
  - 워드프레스 템플릿/글을 수정한 뒤에는 항상
    `POST /wp-json/wp-super-cache/v1/cache {"delete_cache": true}`로
    캐시를 지워야 변경사항이 바로 보인다.

## 비용/토큰 관리

- **아직 정식 운영 전(수정 단계)이므로 Anthropic API 크레딧을 최대한
  아낀다.** 같은 날 같은 market으로 재실행하면 `output/{market}_{date}_
  generated.json` 캐시를 재사용해 Claude API를 다시 호출하지 않는다 —
  이 캐시 파일을 지우기 전엔 재생성되지 않는다는 걸 기억할 것.
- **시황(daily) 글은 `generate_post.py`/`translate_post.py`를 통해
  Anthropic API로 문구를 생성하지만, 상시(evergreen) 가이드 글은 그럴
  필요가 없다.** 코딩 에이전트가 직접 조사하고 써서 `src/publish_guide.py`로
  바로 발행하면 별도 API 비용이 들지 않는다 (에이전트 구독과 Anthropic
  Console API 크레딧은 별개 과금이기 때문). CSS만 바꾸는 등 코드만 고칠
  때도 API를 다시 호출할 필요 없이 캐시된 HTML을 패치하면 된다.
- **Anthropic Console API 크레딧은 claude.ai/ChatGPT 등 구독과 완전히
  별개로 과금되고, 소진되면 GitHub Actions 자동 발행이 조용히 실패한다.**
  실패 로그에 `Your credit balance is too low`가 보이면 코드 문제가
  아니라 https://console.anthropic.com (platform.claude.com) → Plans &
  Billing에서 충전이 필요하다는 뜻이다. 실패 시점이 `generated.json` 캐시
  저장/`history.append()` 이전이라, 충전 후 다음 스케줄에 자동으로 다시
  시도되며 "이미 발행한 걸로" 잘못 기록되지 않는다.

## 발행 워크플로우

- 새 글이든 기존 글 수정이든, 사용자가 명시적으로 "발행해"라고 하기 전엔
  워드프레스에 **임시저장(draft)**으로 올린다. 검수 후 상태를 `publish`로
  바꾼다.
- 같은 초안을 여러 번 고칠 땐 새 글을 또 만들지 말고
  `publish_wordpress.update_draft()` / `publish_guide.py`의 `post_id`
  인자로 같은 글을 덮어쓴다 — 임시저장 글이 중복으로 쌓이는 걸 방지.
- git 커밋은 사용자가 명시적으로 요청할 때만 한다.

## 워드프레스 연동 시 주의할 것 (`src/publish_wordpress.py`)

- 사이트: `.env`의 `WORDPRESS_URL`(현재 `https://fermata.it.kr`).
  `WORDPRESS_APP_PASSWORD`는 로그인 비밀번호가 아니라 워드프레스 관리자
  프로필의 "응용 프로그램 비밀번호"여야 한다 — 로그인 비밀번호를 쓰면
  `rest_cannot_create` 401로 실패한다.
- **Polylang(다국어)**: 카테고리/태그는 언어별로 다른 term id를 가진다.
  `POST /wp/v2/posts?lang=en`으로 글을 생성해야 실제로 해당 언어로
  태깅된다 (`GET .../posts?lang=en` 목록 필터링은 이 사이트의 무료판에서
  무시됨).
- 완성된 HTML을 그대로 글 본문에 넣으면 워드프레스의 `wpautop` 자동 서식이
  `<style>` 블록 중간에 `<br>`을 끼워넣어 깨진다 — `<!-- wp:html -->`
  Custom HTML 블록으로 감싸서 우회한다 (`_to_wordpress_content` 참고).
- NinjaFirewall이 본문에 `<script>` 태그가 있으면 POST 자체를 403으로
  막는다 — 그래서 Chart.js 차트는 워드프레스 버전에서 전부 제거된다.
- CSS는 반드시 `.mb-post` 래퍼로 스코프한다 (`_scope_css`). 클래스 이름은
  `grid`, `card`, `up`, `down` 같은 일반 단어를 쓰지 말 것 — 이 테마의
  기존 스타일과 충돌해서 레이아웃이 깨진다. 항상 `mb-` 접두사를 쓴다
  (`mb-grid`, `mb-card` 등).
- 카드 그리드는 `grid-template-columns: repeat(auto-fill, minmax(...))`을
  쓴다 (`auto-fit` 아님) — `auto-fit`은 마지막 줄에 카드가 몇 개 남으면
  그 카드들을 옆으로 늘려버린다.

## 뉴스 소스 RSS (`src/fetch_news.py`)

- 한국장: 한국경제, 연합뉴스, 이데일리 / 미국장: CNBC, Yahoo Finance,
  Investing.com. 매일경제(mk.co.kr)는 Cloudflare 봇 차단이 걸려 있어
  제외했다 (2026-08-31 확인).
- `feedparser.parse(url)`은 자체 타임아웃이 없다 — 반드시 `requests.get(url,
  timeout=...)`으로 먼저 받아온 바이트를 `feedparser.parse()`에 넘길 것.
  URL을 직접 넘기면 느린 서버 하나 때문에 파이프라인 전체가 멈출 수 있다.

## 알려진 개선 여지 (당장 급하진 않음)

- `--en`(영어판) 생성이 실패하면 이미 성공한 한국어 글 발행과 무관하게
  `main.py` 전체가 예외로 죽어서 GitHub Actions 잡이 실패로 표시된다.
  스케줄 기본값은 `--en` 꺼짐이라 당장 영향은 없다.
- 자동화된 테스트(`tests/`)가 없다 — 지금까지 검증은 전부 수동
  (스크린샷/직접 다운로드 확인) 방식이다.

## 참고: 프로젝트 구조·실행 방법

전체 파이프라인 설명, 폴더 구조, 실행 명령어, 비용 대략치는 `README.md`를
참고할 것 (이 파일과 중복 설명하지 않음).
