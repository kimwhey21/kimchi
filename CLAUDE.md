# market-brief 작업 시 지켜야 할 것

## 검증 규칙 (반드시 지킬 것)

- **이미지는 쓰기 전에 실제로 다운받아 눈으로 확인한다.** alt text나 검색어만
  보고 판단하지 말 것. 실제로 있었던 일: Unsplash에서 "Korean won
  currency"/"Korean won banknote"로 검색했는데 결과가 중국 위안화(마오쩌둥
  초상) 사진이었다. alt text는 "assorted banknotes"처럼 그럴듯해 보였지만
  실제 사진은 완전히 틀렸다. 대표 이미지(featured image)든 본문 삽입
  이미지든, 발행 전에 `Read` 툴로 다운받은 파일을 직접 봐야 한다.
- **통화/지수 같은 추상적 개념은 이미지 검색이 특히 안 맞을 확률이 높다.**
  브랜드/제품처럼 사진으로 명확히 알아볼 수 있는 대상(개별 종목명, 회사
  로고)은 검색이 비교적 안전하지만, "원화", "코스피", "금리" 같은 추상
  개념은 사진 자체가 없거나 다른 나라 것이 섞여 나올 때가 많다.
  `src/main.py`의 `_featured_image()`가 이 이유로 watchlist(개별 종목)만
  대상으로 하고 macro(지수·환율·금리·원자재)는 일부러 제외한다 — 이 원칙을
  다른 이미지 자동화에도 유지할 것.
- **워드프레스 관리자 화면(플러그인 설정 등)의 정확한 위치는 기억으로
  추측하지 말고 WebSearch로 확인한 뒤 안내한다.** 실제로 있었던 일: Rank
  Math의 OpenGraph 썸네일 설정 위치를 세 번 잘못 추측했다가(존재하지 않는
  탭 이름들) 검색해서야 정확한 위치("Titles & Meta → Global Meta" 탭)를
  찾았다. 게다가 알고 보니 그 설정은 이미 올바르게 되어 있었다 — 확인
  없이 추측한 게 완전히 시간 낭비였다.
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
  필요가 없다.** 지금 대화 중인 Claude Code 세션이 직접 조사하고 써서
  `src/publish_guide.py`로 바로 발행하면 별도 API 비용이 들지 않는다
  (Claude Code 구독과 Anthropic Console API 크레딧은 별개 과금이기
  때문). CSS만 바꾸는 등 코드만 고칠 때도 API를 다시 호출할 필요 없이
  캐시된 HTML을 패치하면 된다.

## 발행 워크플로우

- 새 글이든 기존 글 수정이든, 사용자가 명시적으로 "발행해"라고 하기 전엔
  워드프레스에 **임시저장(draft)**으로 올린다. 검수 후 상태를 `publish`로
  바꾼다.
- 같은 초안을 여러 번 고칠 땐 새 글을 또 만들지 말고
  `publish_wordpress.update_draft()` / `publish_guide.py`의 `post_id`
  인자로 같은 글을 덮어쓴다 — 임시저장 글이 중복으로 쌓이는 걸 방지.
- git 커밋은 사용자가 명시적으로 요청할 때만 한다.
