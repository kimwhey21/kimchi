# 운영 규칙 — 본진·시세 수집·예약 작업·맥 (2026-10-05에 CLAUDE.md에서 글자 그대로 옮김)

> 이 파일은 매번 실리지 않는다. 본진 관리자·템플릿·종목 DB, 시세 수집 코드, 예약 작업·클라우드플레어, 맥 작업, 블로그스팟·네이버 동기화를
> 다루는 세션은 **먼저 이 파일을 읽는다.** 규칙을 고치거나 더할 때는 CLAUDE.md와 같은 원칙(규칙만, 이야기는 비공개 기록)을 따르고, 지울 때는
> `python -m scripts.rule_diff docs/ops.md`로 사라진 줄을 말한다.

## 검증 규칙 (반드시 지킬 것)

- **워드프레스 관리자 화면(플러그인 설정 등)의 정확한 위치는 기억으로 추측하지 말고 WebSearch로 확인한 뒤 안내한다.**
- **관리자 화면 경로를 안내하기 전에, 반드시 REST API로 현재 상태를 먼저 조회한다.** 조회로 확인되지 않은 화면 위치는
  안내하지 않는다. **부분적 근거로 추측한 뒤 확인된 사실처럼 보고하지 않는다.**
  - 먼저 조회할 것: `wp/v2/plugins`(설치·활성 플러그인), `wp/v2/settings`, `google-site-kit/v1/core/modules/data/list`(연결 상태),
    `pll/v1/settings`
  - 확인 불가능한 항목은 "확인 못 했다"고 말하고, 사용자에게 한 번만 보면 되는 구체적 확인 지점을 요청한다.
- **REST 액션 이름을 추측해서 호출하지 말 것.** 문서로 확인된 형식만 쓰고, 아니면 사용자에게 넘긴다.
- 화면(홈페이지, 발행된 글, 템플릿 변경사항)을 눈으로 확인해야 할 때는 Playwright 헤드리스 브라우저(`playwright` pip 패키지 +
  Chromium, 이미 이 컴퓨터에 설치돼 있음)로 스크린샷을 찍어서 실제로 본 뒤 결과를 보고한다. curl로 HTML 구조만 확인하고
  "됐다"고 하지 말 것 — 구조가 맞아도 실제로 보면 다를 수 있다.
  - NinjaFirewall이 헤드리스 브라우저 User-Agent를 봇으로 차단할 때가 있다 — 그럴 땐 실제 브라우저 User-Agent 문자열을
    지정하면 통과된다.
  - 워드프레스 템플릿/글을 수정한 뒤에는 항상 `POST /wp-json/wp-super-cache/v1/cache {"delete_cache": true}`로 캐시를 지워야
    변경사항이 바로 보인다.

## 비용/자동 발행 원칙

- **발행 뒤에는 되읽어 확인한다**(`publish_wordpress.verify_published`). 상태·제목·본문 길이가 기대와 다르면 예외로 멈춰
  워크플로가 빨간 X로 끝나게 한다.
- **`publish_check.yml`이 발행 시각 40분 뒤에 그날 글이 실제로 사이트에 있는지 확인한다**(`src/check_publication.py`).
  `verify_published`는 발행 스크립트가 돌았을 때만 확인하므로, 루틴이 원고를 못 써서 아무것도 커밋되지 않은 날은 이 워크플로가
  잡는다. 실패하면 깃허브가 메일을 보낸다. 휴장 판정은 달력이 아니라 지수의 실제 마지막 거래일이고, 글의 신선도는
  **"거래일 이후에 수정됐는가"**로 본다 — "36시간 안에 수정" 창으로 되돌리지 말 것(`tests/test_check_publication.py`).
- **`market_brief.yml`은 시세 수집·커밋·루틴 호출만 한다.** `python -m src.main --fetch-only`로 돌려 규칙 기반 초안은 만들지
  않는다. 시세 파일이 그날 처음 커밋되면 같은 실행이 루틴의 **API 트리거**(`ROUTINE_<MARKET>_FIRE_TOKEN` 시크릿, 루틴별
  `/fire` URL)로 조사·집필 루틴을 즉시 깨운다. 루틴의 자체 예약(cron)은 한 시간 뒤 예비다. 호출 실패는 워크플로를
  실패시키지 않는다. `tests/test_workflows.py`·`tests/test_fetch_only.py`가 이 구조를 고정한다.
- **루틴 샌드박스 네트워크는 전체 열림(Full)이다.** `m.stock.naver.com`은 막힐 때가 있다(9/7 000, 9/25 200) — 한국장 편입 종목
  수집(`fetch_movers`)이라 루틴이 자구책으로 시세를 받는 날만 영향이 있다. 설정은 **루틴 편집 → 지시문 아래 구름 아이콘(Default)
  → 톱니 → Network access**에 있고(문서: code.claude.com/docs/en/routines), 바꾼 뒤에는 점검 루틴을 `RemoteTrigger run`으로 다시
  돌려 확인한다. claude.ai 설정의 "기능 → 네트워크 송신 허용" 토글은 채팅 분석 도구용이라 루틴과 무관하다. 루틴의 사진 검색은
  `--source unsplash`로 고정한다. 루틴 지시문은 `docs/routine_common.md`·`routine_kr.md`·`routine_us.md`에 있고 루틴 프롬프트는
  그 파일을 가리키는 몇 줄뿐이다 — **규칙은 파일에서 고친다.** 같은 환경(Default)의 환경변수에
  `UNSPLASH_ACCESS_KEY`·`FRED_API_KEY`·`ECOS_API_KEY`가 들어 있고 저장소에는 없다. 점검 루틴은 네트워크와 환경변수를 함께 본다.
- **한국어 시황은 본진에 올리지 않고(2026-09-26부터, 그전에는 `private`), 네이버에는 원고를 그대로 옮긴다.** 스위치는
  `publish_editorial.KO_DAILY_TO_WORDPRESS`(끔)와 `KO_DAILY_STATUS`(켜면 `private`) 둘이다. 한국어 그림도 올리지 않지만 본문·인사이트
  **사진은 영어판이 같이 쓰므로 올린다.** 영어판(`-en`)은 그대로 공개다. 그림은
  **절 번호**로 붙이고 4장 상한은 없으며 `editorial_gate`가 본문·인사이트 **사진도 파일로 남긴다**. **영어판 본문 그림은 영어
  명세로 따로 그린다**(`data_graphics.build(lang="en")`, 2026-09-26 — 그전 영어 시황 24편은 그림 자리가 `<img src="">`였다).
  영어 명세의 글자에 한글이 있으면 관문이 막고, 주소가 없는 그림은 태그를 찍지 않는다. **원본이 어디인지 바뀌면 옮기는
  코드의 전제도 같이 바뀐다 — 본문을 어디서 가져오는지(`full`)만 갈아 끼우고 끝내지 말 것.**
- **프리뷰는 네이버에 본문 전문(링크 없이)으로 나가고, 본진에는 올리지 않는다**(2026-09-26부터, 그전에는 비공개). 네이버 쪽은
  시황과 같은 처리이고, 본진 쪽은 `publish_feature.LIVE_STATUS`에서 `private`인 시리즈(한국어 글)를 `KO_TO_WORDPRESS`(끔)가 검사만
  하고 업로드 없이 끝낸다. 켜면 `private`로 올라가는데, 워드프레스 `private`는 글·주소·분류를 그대로 두고 **사이트맵·목록·피드·익명
  접근(404)에서만 뺀다**. **비공개 글은 텔레그램·스레드에 알리지 않는다** — 알림은 맥의 동기화가 네이버에 올린 뒤 네이버 주소로
  보낸다(`scripts/notify_naver_post.py`).
- **`publish_check.yml`은 예비 예약까지 끝난 뒤(19:00/10:00 KST)에 돈다.** 루틴보다 먼저 울리면 정상 발행일에도 실패 메일이 온다.
- **밤 11시 반 증명서**(`daily_proof.yml` → `src/daily_proof.py`, 2026-10-05): 그날 독자가 본 것을 다른 원천으로 다시 계산해 운영 텔레그램에
  한 줄로 보낸다 — 작업(클라우드플레어 표의 깃허브 작업 성공 여부·오늘 커밋된 원고·맥 신호 `state/mac_beats.json`), 숫자(`close_check`),
  화면(종목 페이지 무작위 20개와 홈을 다음·네이버 목록과), 글(본진 `check_publication`, 네이버·블로그스팟 게시 수), 꼬리표(두 원천 확인 수).
  **대조 0건은 성공이 아니다. 증명서가 안 오면 워커가 00:05 KST에 울린다**(`jobs.json` watch `success: true` — 실행 성공 = 텔레그램 전송
  성공이라, 보내지 못하면 1로 끝난다). 저녁 종가 대조는 여기로 합쳤다(publish_check에서 뺐다). 맥 작업은 끝날 때 `~/.market-brief-state/beats/<이름>`을
  만지고(`src/beat.py`, 맥 스크립트는 같은 세 줄 인라인) `scripts/mac_beats.py`(launchd `kr.it.fermata.macbeats`, 23:22)가 커밋한다 — 그 파일이
  없거나 오늘 것이 아니면 맥이 죽은 것이다. **막힌 날 사장님이 "내보내"라고 하면** `gh workflow run market_brief.yml -f market=kr
  -f close_override=naver_snapshot`(또는 `daum`)으로 지목한 원천 값에 `(owner override)` 꼬리표를 달아 내보낸다(`KR_CLOSE_OVERRIDE`, 자동 실행엔 없음).
  새 예약 작업을 만들면 `jobs.json`에 넣는 것으로 증명서의 기대 목록에도 들어간다(따로 적는 표가 없다).
- **코스피·코스닥의 원천은 네이버 지수 일별 목록이다**(`fetch_kr._fetch_index`, 70거래일을 35줄 두 쪽으로, 2026-10-05). FinanceDataReader의
  KS11/KQ11은 개인 개발자의 깃허브 사본이라 그 사람의 거래소 로그인이 끊기면 조용히 멈춘다 — **지수에 다시 쓰지 말 것**(종목 일봉은 그대로
  FinanceDataReader). 발행 점검의 한국장 '마지막 거래일'도 같은 목록에서 묻는다(`fetch_kr.last_closed_trading_day`, 장중에는 오늘을 치지 않는다).
  **`src/close_check.py`가 평일 19:00 발행 점검에서 목록의 정체(2거래일 넘게 뒤처짐)와 한국은행 ECOS 「주식시장(일)」과의 차이를
  운영 대화로 알린다** — 알리기만 하고 발행은 막지 않는다(`continue-on-error`). 빈 날을 메우는 장치를 더할 때는 메웠다는 사실을 알리는
  장치도 같이 둔다(메우는 장치가 원천의 정체를 2주 넘게 가렸다). 목록에 오늘 줄이 아직 없으면 `fetch_kr._apply_final_index_quote`가 네이버 실시간 `ms=CLOSE` 값을
  **전일 종가 + 등락폭 = 확정 종가** 등식이 맞을 때만 오늘 행으로 덧붙인다(휴장일엔 등식이 안 맞아 가짜 행이 생기지 않는다).
  등식 검증을 빼고 "CLOSE면 붙인다"로 느슨하게 만들지 말 것. 목록이 우리가 이미 커밋한 시세 파일보다 뒤처지거나 목록을 못 받으면 그 파일의 이력을
  밑바탕으로 쓰고 등식은 그 마지막 종가와 맞춘다(`_latest_committed_index`). 우리 파일이 며칠 비었으면(건너뛴 거래일) 네이버 지수 일별 목록으로 빈 날을 채우되, 목록의 직전 거래일 종가 + 등락폭 = 확정 종가일 때만이다(`_fill_gap_from_naver_daily`, 2026-09-30). `tests/test_price_fetch.py`가 이 날들을 재현한다.
- **한국장 종목 가격·등락률의 기준은 KRX 정규장 확정 종가이고, 시세 파일은 거래일마다 한 번만 쓴다**(2026-09-25).
  **오늘 값은 서로 다른 두 원천이 같아야 쓴다**(`fetch_kr._resolve_krx_close`, 2026-10-05): 네이버 폴링 사진 — **네이버 폴링으로 정규장 종가를 읽을 수 있는 때는 15:31~15:59뿐이라**(16:00부터 `nv`는 KRX 시간외 단일가를 따라 움직이고 `ms`는 넥스트레이드 때문에 20:00까지 OPEN, 2026-09-28) `krx_close.yml`(15:32·15:40·15:48)이 `data/krx_close/<날짜>.json`에 남긴다 — 과
  **다음 금융**(`regularTradePrice`·`basePrice`, 장 마감 뒤 언제든 정규장 값이 따로 있다). 둘 다 있으면 종가·기준가가 같아야 하고(다르면 멈춘다),
  하나만 있으면 그것을 쓰고, 둘 다 없으면 멈춘다. 창 밖의 폴링은 아예 쓰지 말 것('CLOSE면 받아들이기'도 안 된다 — 시간외 가격이 종가로 나간다), **폴링의 `cr`·`cv`는 부호가
  없다**(부호는 `nv−pcv`에서). **종목 이력은 다음 일별 시세(KRX 정규장 종가, 70거래일)에서 받는다**(`_fetch_stock`) — 네이버 일봉·모바일 일별 목록·basic·
  FinanceDataReader는 KRX+넥스트레이드 통합값이라 종목 값에 쓰지 말 것(10/5 대조: 사진 600건 중 486건이 달랐고, 다음은 600건 모두 같았다). 다음이 막힌 날만 이력을 FinanceDataReader로 받고 `history_source`에 적는다(오늘 값은 사진 하나로, `close_check`가 알린다).
  **한국장 종목은 코어든 편입이든 하나도 빼지 않는다** — 받지 못하거나 두 원천이 다르면 종목 이름을 모두 적고 멈춘다(재시도 예약이 다시 돈다).
  예전의 '코어 80%까지 빠져도 쓴다'·'편입 종목은 조용히 뺀다'로 되돌리지 말 것. **다음 장의 네이버 '전일'(`pcv`)이 세 번째 눈이다** —
  `close_check`가 평일 19:00에 `pcv`가 가리키는 날(마지막 장 바로 앞 거래일)의 파일과 대조한다(`pcv`는 새 장이 열려야 넘어간다). 이미 있는 거래일 파일은 가격을 두고 **빈 칸(수급·편입 종목)만 보강**한다(`main._merge_price_file`).
  **종목별 수급은 다음 날 아침 미국장 수집이 전 거래일 파일에 채운다**(`scripts/fill_kr_flows.py`, 2026-09-26) — 마감 직후에는
  네이버가 전날 줄만 줘서 그날 파일은 늘 빈다. 한국장 글은 전 거래일 파일의 수급을 날짜를 밝혀 '어제'로 쓰고 그림은 `"day": "previous"`.
  되돌리지 말 것.
- **루틴 턴 절약 장치 넷**(2026-09-25; 2026-10-05에 `docs/routine_common.md` 맨 위 「턴을 쓰는 다섯 가지」 상자와 `scripts/commit_push`를 더했다 —
  관문 코드 읽기·옛 원고 전문 읽기·원고 커밋의 unittest·푸시 거부 뒤 업스트림 탐색·JS 화면 WebFetch·글자 수 채우기): ① 첫 명령 `python -m scripts.routine_precheck <kr|us|preview>`(어제 원고 JSON 통째 읽기
  대신 요약) ② 관문·렌더가 그림을 **모음판**(`sheets/sheet-NN.png`, 원본 크기 그대로)으로 이어 붙인다 — **읽는 장수를 줄이지는
  않는다** ③ `graphic_checks.collect_spec_issues`에 `price_data`·`section_body`(제목의 '만·유일·신고가·최고' vs 데이터, 그린 종목이
  절 본문에 하나도 없음, 표 셀 폭; `fact_table`은 19→17→15로 자동 축소) ④ 프리뷰에도 숫자 대조(`editorial_facts.collect_issues_for_preview`,
  목표주가·52주 고점·PER·프리마켓·%포인트는 제외)와 제목 후보의 어림수 검사. 지시문에는 push 뒤 대기·조회 금지, 검색은 사실당 두 번,
  `env` 출력 금지. 관문을 **매일 걸리게** 만들지 말 것.
- **시세 수집 방식을 바꾸면 실제 거래일 그 시각에 한 번 돌려 본 뒤에 믿는다**(2026-09-28 — 9/25에 바꾼 한국장 종가 확정 장치가 휴장 뒤 첫 거래일 저녁에 처음 돌며 멈췄다. 과거 자료·낮 시각 응답으로 한 시험은 16시 이후 넥스트레이드·시간외 거래를 보지 못했다).
- **예약 작업의 알람은 Cloudflare Workers `fermata-backup-cron`이고 깃허브 예약은 예비다**(2026-09-29 — 깃허브 예약이 평소 18~22분 늦고, 이날은 반나절 통째로 빠져 종가 사진·한국장 수집·종목 DB가 모두 안 돌았다). 매분 깨어나 `cloudflare/backup_cron/jobs.json`의 시각에 실행 버튼을 누르고(종가 사진은 깃허브보다 1분 이른 15:31·15:39·15:47 KST, 나머지는 깃허브 cron과 같은 시각), 누르기가 실패하면 운영 텔레그램으로 알린다. 시세 수집의 재시도(:27·:34)는 깃허브 예약에만 있다. **늦게 온 깃허브 예약은 `skip_guard.yml`이 최근 60분 안에 같은 작업이 있으면 건너뛴다** — 시세 수집은 성공한 실행만, 발행 점검은 실패한 실행도, 나머지는 성공·진행 중을 센다. **예약 시각보다 2시간 넘게 늦게 온 깃허브 예약도 건너뛴다**(9/29 밤 15:32 종가 사진 예약이 22:16에 몰려와 실패 알림 셋). 손으로 누른 실행과 조회 실패는 늘 돈다. **워크플로의 cron을 바꾸거나 새로 만들면 이 표도 같이 고치고 skip_guard를 붙인다**(`tests/test_backup_cron.py`가 대조한다). 올리기는 `python -m scripts.deploy_backup_cron`이고 열쇠(`~/.cloudflare_workers_token`·`~/.github_dispatch_token` — kimchi 저장소 Actions만)는 이 맥에만 있다.
- **저장소는 `~/market-brief`(비공개 기록은 `~/kimchi-notes`)이고 다운로드·문서·데스크톱 폴더에 두지 않는다**(2026-09-30 — 맥이 보호하는 폴더라 Claude Code가 자동 업데이트되자 '다운로드 폴더 접근 허용' 창이 떠 8시간 넘게 아무도 누르지 못했고, 그동안 이 맥의 예약 작업(네이버·블로그스팟 동기화)이 저장소를 읽다 멈췄다). 이 맥의 예약 작업·스크립트는 이 경로를 쓴다. **예약 작업이 막히면 알린다** — 블로그스팟 동기화는 25분을 넘으면 스스로 멈추고, 네이버 동기화는 받기(git pull) 실패를 처음 한 번과 한 시간마다 알린다. **이 맥의 자동화 브라우저는 창 없이(headless, 실제 크롬 `channel="chrome"`) 돈다**(2026-10-02 — 창을 띄우면 맥이 크롬을 앞으로 가져와 사장님의 전체화면이 풀린다). 스위치는 `browser_mode.headless()`(`~/.market-brief-naver/`·`~/.market-brief-google/` 두 사본에 같은 함수)이고 `touch ~/.market-brief-naver/show_browser`가 창 보이기다. 예약 작업에 창 있는 브라우저를 다시 넣지 말 것(로그인 대기 `login_wait`만 예외).
- 예약 시각을 마감 정각으로 되돌리지 말 것. 16:00/07:00 정각은 시세가 아직 안 채워져 죽는다 — 두 시장 모두 20분 뒤다.
- **`src/fetch_images.py`(Unsplash -> 위키미디어 엔티티 검색)는 자동 발행 경로에서 쓰지 않는다. 검색어로 사진을 자동으로 붙이는
  경로를 다시 만들지 말 것.**
- GitHub Actions에는 **Anthropic·OpenAI 키를 전달하지 않는다.** 유료 생성 경로(옛 `generate_post.py`·`translate_post.py`, 2026-10-05에
  지웠다)를 자동 실행에 다시 만들지 말 것. Unsplash 키는 Actions 어디에도 넘기지 않는다 — 사진 검색은 루틴 샌드박스에서 사람처럼 보고
  고르는 경로로만 한다.
- 무료 생성 결과는 `output/{market}_{trading_date}_generated_free.json`에 캐시된다. 자동 검증하지 못한 시장 원인·전망은 추측해서
  넣지 않는다.
- **`publish_editorial.py --render-only`는 `WORDPRESS_*`가 설정돼 있으면 완전한 dry-run이 아니다.** 본문 그래픽·사진은 실제로
  미디어 라이브러리에 업로드된다. 순수 렌더만 보고 싶으면 `WORDPRESS_URL` 등을 비우고 돌린다(`publish_feature.py --render-only`는
  이 문제가 없다).

## 발행 워크플로우

- **오래된 원고 파일은 발행 전에 실제 라이브 slug를 조회해서 doc의 `slug` 필드로 명시한다.** `publish_feature.py`의 `_slug()`는
  `doc["slug"]`가 없으면 파일명으로 slug를 만든다. 발행 후 결과의 `id`가 예상한 값인지 반드시 확인한다.
- **헤더·푸터·`single` 같은 사이트 전역 템플릿은 글 하나가 아니라 사이트 전체에 영향을 준다.** 건드리기 전에 반드시 사용자에게
  먼저 확인한다.
- **카테고리·태그는 이름으로 찾되, 같은 이름이 둘이면 발행을 멈춘다**(`publish_wordpress._get_or_create_term_id`). 첫 번째를 고르고
  넘어가는 코드로 되돌리지 말 것. Polylang은 꺼져 있다.
- **검색어 태그는 `src/post_tags.py`가 글에서 뽑는다.** 고정어 + 원고의 `tags` + 본문에 나오는 종목(시황은 2% 이상 움직인 것) +
  주제어 사전 + 달(`9월증시`), 15개까지. 네이버(`scripts/naver_post.py`)와 워드프레스 한국어 글(`publish_editorial`·`publish_feature`)이
  같은 목록을 쓴다. 이름은 낱말 경계로 찾는다. 이미 올라간 글은 `python -m scripts.retag_wordpress --apply`(워드프레스)와
  `~/.market-brief-naver/retag_post.py`(네이버)로 고친다.
- **본진 앞에는 Cloudflare(무료)가 있다**(2026-09-28). 방문자 화면을 2시간 보관하는 캐시 규칙 하나(관리자·로그인·`/wp-json`·wp-cron·미리보기·로그인 쿠키 제외), 보안 수준 `essentially_off`·브라우저 검사 끔(깃허브 액션·루틴의 REST 요청이 확인 화면에 막히지 않게), SSL은 `Full`(카페24 인증서 갱신이 실패해도 화면이 살도록 — `strict`로 올리지 말 것). 워드프레스 캐시를 지우는 곳은 **Cloudflare 창고도 같이 비운다**(`src/cloudflare.purge_all`, 실제 사이트 주소일 때만·실패해도 멈추지 않음) — 새로 캐시를 지우는 코드를 만들면 여기도 부른다. 열쇠는 `CLOUDFLARE_API_TOKEN`(이 맥 `.env`·깃허브 비밀, 이 영역만). **카페24 스팸 SHIELD(보안관리)는 꺼 둔다 — 그 봇 검사(cupid.js)는 Cloudflare 경유와 맞지 않는다** — 켜지면 검사 화면이 200으로 오고 브라우저는 세 번 다시 부른 뒤 403이다(2026-10-01 08:00~15:58 방문자 전부, 사장님이 스팸 SHIELD를 끄자 풀렸다). 본진을 읽는 코드는 `src/site_block.is_bot_challenge`로 먼저 가려 "본진 막힘" 한 줄로 말한다(맥 스크립트는 같은 판정을 복사해 쓰고, 네이버 동기화는 한 시간에 한 번만 알린다). 메일(MX mw-002.cafe24.com·SPF)은 Cloudflare DNS에 그대로 옮겨 두었다. **관리자 화면(`/wp-admin`·`/wp-login.php`)은 Cloudflare 사용자 지정 규칙 「관리자 화면 한국만」이 한국 밖에서 막는다**(2026-09-30 — 카페24의 「디렉토리 접속설정」 /wp-admin 한국만 규칙은 Cloudflare 경유를 해외로 봐서 사장님까지 403이라 지웠다; 카페24에 같은 규칙을 다시 걸지 말 것). 규칙은 REST(`rulesets/phases/http_request_firewall_custom/entrypoint`)로 넣고 열쇠는 이 맥의 `~/.cloudflare_waf_token`(Zone WAF Edit, 이 영역만)뿐이다. `scripts/site_health.py`가 실행 장소 나라(`/cdn-cgi/trace`)에 맞춰 매일 두 번 확인한다.
- **사이트맵은 워드프레스 기본(`/wp-sitemap.xml`)이다.** Rank Math 사이트맵 모듈은 꺼 두었고 옛 `/sitemap_index.xml`은 404다.
  **다시 켜지 말 것** — 켜져도 16번 조각의 `option_rank_math_modules` 필터가 늘 끈다(켜지면 종목 사이트맵이 404가 된다). Rank Math에서 켜 둔 기능은
  링크 집계·SEO 분석·구조화 데이터·Instant Indexing(글 수정도 빙에 알림)·지역 SEO·리디렉션(옛 `/en/` 주소 5개)·404 기록 일곱뿐이다(2026-09-28). 켜고 끌 때는
  Rank Math 자체 주소 `rankmath/v1/saveModule`(플러그인 소스에서 확인)로 하고, 상태는 관리자 진단 주소 `fermata/v1/diag`로 본다. 네이버 서치어드바이저에는 새 주소를 제출했고, 구글 서치콘솔은 사용자 계정으로 제출한다. 새 글마다
  `~/.market-brief-naver/nsa_request.py`가 네이버 수집 요청을 넣는다(10분 동기화에 붙어 있음).
- **홈 제목·설명·언어 표시와 검색 제외 페이지는 Code Snippets 11번("SEO: 홈·영어 목록 영어 표시…")이 정한다**(2026-09-26).
  관리자 Rank Math '홈페이지' 칸의 한국어 값은 이 조각이 덮어쓰므로 **홈 제목은 조각의 문구를 고친다.** **작은 조각 #5~#12의 원본은 `templates/wp_snippets/*.php`이고 `python -m scripts.deploy_snippets`로 올린다**(2026-09-28 — 관리 화면에서 고치면 다음 배포가 덮어쓴다; #13은 맥의 `redirect_sync.py`가 만든다). 홈·Daily(76)·Guides(77)·
  전체(105)와 영어 글은 `lang="en"`·`og:locale en_US`, 빈 한국어 목록(1047·1610·1439)과 threads-callback(1604)은 noindex·사이트맵 제외.
  영어 시황 끝에는 관련 영어 가이드 링크가 최대 3개 붙는다(`publish_editorial._guide_links`).
- **공개된 한국어 글은 텔레그램 채널 `@fermata_kr`과 스레드 `@fermata.it.kr`에 자동으로 올린다**(`src/notify_telegram.py`·
  `src/notify_threads.py`, `publish_feature`·`publish_editorial`이 공개 직후 부른다). 표지 + 제목 + Take 두 문장 + 링크. 다시 올린
  글(최초 공개와 수정이 10분 넘게 벌어진 글)과 영어 글은 보내지 않는다. 토큰은 GitHub 시크릿(`TELEGRAM_BOT_TOKEN`,
  `THREADS_ACCESS_TOKEN`, `THREADS_USER_ID`)과 로컬 `.env`에만 — 저장소에 적지 않는다. 스레드 토큰은 60일짜리라 이 맥의
  launchd(`kr.it.fermata.threadsrefresh`, 일 21:30)가 `scripts/threads_auth.py refresh`로 갱신한다(launchd PATH에는 gh가 없어 `_gh_path`로 찾는다 — 2026-09-27 깃허브 시크릿 저장이 조용히 실패했다). 알림 실패는 발행을 실패시키지
  않고 `[텔레그램 실패]`·`[스레드 실패]`로만 찍는다.
- **본진은 영어 사이트다**(2026-09-26). 메뉴는 Market(`/`)·Stocks(`/stocks/`)·Daily·Guides
  넷이고(2026-09-27, 그전엔 All·Daily·Guides — 105 all 페이지는 남아 있고 메뉴에서만 빠졌다), **메뉴 줄은 한 곳에서만 그린다** — `templates/wp_stock_db.php`의
  `fs_nav`(`[fermata_nav]`, 지금 화면을 스스로 알아 버튼을 칠한다 — 시황 글·분류는 Daily, 가이드는 Guides)를 **사이트의 모든 블록
  템플릿**이 main 맨 앞에서 부른다(2026-09-28 — 글·분류·검색·소개·404에는 메뉴가 없고 크림 배경·명조였다;
  2026-09-27엔 메뉴 네 화면이 다섯 곳에 손으로 복제돼 높이가 272·319·361px로 달랐다). **템플릿 원본은 `templates/wp_site/*.html`이고
  `python -m scripts.deploy_templates`로 올린다**(사이트 편집기에서 고치면 다음 배포가 덮어쓴다). 목록 페이지(76·77·105·3228)는
  `fermata-hub` 틀, 분류·태그·작성자·검색은 Daily 목록과 같은 두 줄 목록이다. 흰 배경·Pretendard·메뉴 버튼은 14번 조각의
  `FERMATA_BASE_CSS`가 모든 화면에, 글 목록 모양은 `FERMATA_LIST_CSS`가 목록 화면에만 싣는다. 네이버로 가던 Weekly·Checkpoint·가이드 탭과 그 목록 페이지 1047·1439·1610은
  없앴다. 페이지 본문에 메뉴 줄을 다시 쓰지 말 것. 소개·연락처는 `page-no-title` 그대로다(메뉴 없음). 원본 백업은
  `~/.market-brief-backups/home_nav_before_20260927.json`·`hub_template_before_20260927.json`. 배경·글꼴·버튼 모양은 14번 조각
  (`fermata_list_view`에 Stocks 포함)이 정하고, 여백을 덧대 높이를 맞추지 않는다. 템플릿·메뉴·목록 스타일을
  고친 뒤에는 **`python -m scripts.nav_check`**(14화면 × 1440·390px 실측, 다르면 실패)를 돌린다 — 한 폭 캡처만 보고 "됐다"고 하지 말 것. **점검 브라우저(`nav_check`·`site_ui_audit`)는 구글 태그·광고 요청을 끊는다**(`src/quiet_browser.block_trackers`, 2026-09-30 — 점검이 GA4 방문자·애드센스 조회로 잡혀 이틀에 1,600명이 쌓였다). 브라우저로 본진을 여는 새 스크립트도 같은 함수를 부른다. 태그가 실려 있는지는 `site_health`가 HTML로 본다. `flex-wrap`을 건드리지 말 것 — 모바일에서 탭 줄이 두
  줄로 접혀야 가로가 넘치지 않는다. **홈·목록(76·77·105·분류)의 겉모습은 토스피드 A안 3색 판이다**(2026-09-27) — 원본은 `templates/wp_list_toss.php`, `python -m scripts.deploy_list_style`로 Code Snippets 14번에 올린다(관리
  화면에서 고치지 말 것). 이름표 색은 분류다: 영어 시황은 Daily(121) **그대로 두고** 하위 분류 Korea Close(684)·Wall Street
  Close(685)를 더한다(`publish_editorial.MARKET_CATEGORY_IDS`), 가이드는 Guides(153). 목록 썸네일은 **정사각 그림을 따로**
  그린다(`featured_image.create_square`·`feature_graphics.cover_square`, 글 메타 `fermata_square_thumb`) — 가로 표지(1200×630)는
  공유·디스커버용 대표 이미지로 그대로다. 네모 그림이 없는 글은 가로 표지를 틀 안에 통째로 넣는다. Daily 분류 주소는
  `/category/daily/`다(전에는 한국어 '시황'). **사이트 언어는 영어다 — REST로는 `"language": ""`(빈 값)로 보낸다.** 워드프레스는 영어를 빈 값으로
  저장하고 `"en_US"`는 설치된 언어 목록에 없다며 옛 값으로 되돌린다(200이 오고도 안 바뀐다). 사장님 계정 언어는 `ko_KR`로 고정해
  관리자 화면은 한국어다. **Code Snippets 12번**이 방문자 화면의 `locale`→`en_US`와 태그라인을 한 번 더 못박는다. 영어 글의 출처 칸은
  한국 매체를 영어 이름(모르면 주소)과 `Korean-language article`로 그리고(`src/english_sources.py`), 영어 이름을 못 찾은 편입 종목은
  종목 코드로 쓴다(`render_html._display_name`·`data_graphics.localized`).
  날짜 형식은 `F j, Y`, 템플릿에 글자로 저장된 문구(Previous·Next·By 등)도 영어다. 한국어 소개·연락처·개인정보처리방침(697·698·226)은
  페이지는 남기고 메뉴에서만 뺐다. 네이버 카테고리 번호는 추측하지 말고 `PostList.naver?blogId=fermata49`를 받아 `categoryNo=`로
  확인한다(시황 1·Checkpoint 6·가이드 7·Weekly 8).
- **본진 종목 데이터베이스**(2026-09-27): 코스피·코스닥 전 종목(주식만,
  2,765개)을 영어 데이터 페이지 `/stocks/<종목코드>/`로, 목록 `/stocks/`(시가총액 순 100개씩), 홈 첫 화면에 검색창·시장 띠·카드 셋을 둔다.
  **종목마다 글·페이지를 만들지 않는다** — 실제 페이지는 slug `stocks`(id 3228) 하나이고 Code Snippets 16번(원본 `templates/wp_stock_db.php`,
  `python -m scripts.deploy_stock_db`로 올린다)이 주소를 받아 워드프레스 옵션(`fm_s_<코드>`·`fm_stock_index`·`fm_market`)으로 그 자리에서
  그린다. 사이트맵은 기본 사이트맵에 `stocks` 묶음이 붙는다. 데이터는 `python -m src.stock_db run --push`(`stock_db.yml`, 17:05 KST 시세·다음 날
  07:50 KST 수급(월~토 — 토요일은 금요일 수급); 장중 09:00~15:30에는 스스로 멈추고, 목록이 어제보다 3% 넘게 적으면 다시 받고, 목록에서 빠진 종목은 네이버에 하나씩 물어 아직 있으면 지우지 않는다)가 REST `fermata/v1/stocks`로 넣는다 — 상세는 시가총액 상위 300 + 나머지의 7분의 1(요일 순번). 원천은 네이버 모바일 증권
  API(비공식)와 DART(`DART_API_KEY`: 이 맥 `.env`와 깃허브 시크릿) 영문명·업종(`data/stock_meta.json`, 커밋한다). **종목 페이지의 가격(종가·등락·거래량·
  거래대금·시가총액·차트·52주 범위)은 KRX 정규장 값이다**(2026-10-05 — 그전에는 네이버 통합값을 'At close · Korea Exchange'로 보여 줬다): 다음 일별 시세
  (`stock_db.Daum`, 종목마다)를 쓰고 15:3x 전 종목 사진(`data/krx_close/<날짜>.json`의 `close`)과 종가·기준가가 같아야 올린다 — 한 종목이라도 다르거나
  두 원천 모두 없으면 올리지 않는다. 다음이 막히면 사진 하나로 쓰고(다음이 5번 연달아 실패하면 더 묻지 않는다) 운영 대화로 알린다. 네이버 목록은
  종목 목록·이름·거래 상태에만 쓴다. **화면 글자에 한글이 들어가면
  올리지 않는다**(`stock_db.hangul_problems`) — 이름은 DART 영문명을 다듬고(`clean_name`), 틀린 대형주 이름은 `NAME_FIX`에 사람이 적는다;
  규칙을 고치면 `python -m src.stock_db rename`. 카페24가 큰 요청을 502로 끊으므로 **한 번에 50KB 이하로** 보내고 목록은 나눠 보내 다 모인
  뒤에만 바꾼다. 조각에 글자로 script 태그를 쓰면 NinjaFirewall이 저장을 403으로 막는다(`wp_print_inline_script_tag`를 쓴다).
  **영어 시황·가이드 본문의 종목 이름은 워드프레스가 글을 그릴 때 종목 페이지로 잇는다**(`fs_link_apply`, 글마다 첫 언급만·15개까지, 제목·기존 링크 안은 건드리지 않음) — 영어 낱말과 같은 이름·그룹 이름(`FS_LINK_EXCLUDE`)과 300위 밖 한 낱말 이름은 잇지 않는다. 원고에 링크를 손으로 넣지 말 것. **외국인 수급 페이지**(`/stocks/foreign-flows/`)는 `stock_db.build_flows`가 가장 최근 **종목 수급 날짜**(다음 날 아침 확정)로 만들어 옵션 `fm_flows`로 넣는다 — 순위는 상세를 받는 시가총액 상위 300종목 안, 금액은 외국인 순매수 주식 수×그날 종가, **등락률은 종목 페이지와 같은 목록 값만**(수급 줄·일봉의 종가로 나누지 말 것 — 네이버 일봉 종가는 넥스트레이드 애프터마켓까지 합친 값이고 등락률 기준은 KRX 종가다), 지분 변화에서 우선주는 뺀다. 코스피 외국인 합계는 `data/foreign_history.json`에 **날짜별로 합쳐** 쌓고(지수 수급과 종목 수급은 날짜가 다르다 — 덮어쓰지 말 것) 5일 이상 모이면 20거래일 그래프를 그린다. 들어가는 문은 `/stocks/` 카드 줄 다섯 번째·홈 외국인 카드의 See all·"Stock lists" 줄이고 맨 위 메뉴는 그대로다. **회사 소개(About)는 `data/stock_about.json`**(2026-09-28, 루틴이 아니라 세션에서 사람 손으로 쓴 영어 두세 문장): 근거는 데이터 제공처의 한국어 기업개요이고 문장은 새로 쓴다(옮겨 쓰지 않는다, 근거 원문은 저장소에 넣지 않는다). 근거에 없는 사실·숫자, 한글 이름의 음역, 만·억 단위 환산을 쓰지 않고 회사 자신의 주장은 'says'로 밝힌다 — `stock_db.about_issues`가 기계로 보고 `tests/test_stock_db.py`가 파일을 확인한다. 상세 항목과 함께 실리고(한 번에 싣기 `python -m src.stock_db about-push`), 소개가 없는 새 종목은 예전 한 줄 그대로 나간다. **SKHY 프리미엄**(`/stocks/skhy-premium/`)은 `stock_db.build_skhy`가 나스닥 SKHY·서울 SK하이닉스(KRX 정규장 종가 — 다음 일별 시세)·원달러(야후 KRW=X)를 **같은 날짜끼리만** 짝지어(ADR 1주 = 원주 0.1주) 옵션 `fm_skhy`로 넣고, 홈 띠의 SKHY 칸도 그 마지막 줄을 쓴다 — 날짜가 다른 값을 섞지 말 것. **홈의 코스피·코스닥과 코스피 외국인 합계도 종목 목록과 같은 거래일 값만 싣는다**(`market_index(day)` — 장 전 07:50에 네이버 지수는 날짜만 오늘로 넘기고 값은 전일·0이라, 2026-09-30 홈에 'Sep 30 close 6,870.81 0.00%'·'KOSPI ₩0'이 나갔다). 장 전에는 그날 지수를 **커밋한 한국장 시세 파일**(`_index_from_price_file`)에서 읽는다 — 2026-10-01 장 전 실행이 네이버 지수 일별 목록에서 전 거래일 줄을 찾지 못해 죽었다(목록이 멈춘 것은 아니다, 장 전에 왜 없었는지는 확인 못 함). **순위표 네 개**(`/stocks/lists/<slug>/`: 배당수익률·외국인 지분·P/B·코스닥 시가총액, 각 50위)는 `stock_db.build_lists`가 매일 만들어 옵션 `fm_lists`로 넣는다 — 전 종목 지표는 `data/stock_metrics.json`에 이어 쓴다(상세를 받은 종목만 그날 값으로). **배당은 DART 사업보고서 공시값**(`data/stock_dividends.json`, 한 달에 한 번 `python -m src.stock_db dividends`; 최근 1년 안의 결산을 모두 더한다)이고 **네이버 값과 15% 안으로 맞을 때만 싣는다**(공시는 결산 뒤 액면분할을 반영하지 않고 가끔 총액이 잘못 들어간다). 튄 배당·이익보다 많은 배당·적자 배당은 숨기지 않고 공시 숫자로 표시한다. 외국인 지분은 실제 지분율(차트 이력)이고, 네이버 '외인소진율'은 한도 대비 사용률이라 따로 보인다. **새 주소는 빙에 IndexNow로 알린다**(`src/indexnow.py`, 영어 글 공개 직후·종목이 새로 생기거나 빠질 때 자동, 전체는 `python -m src.indexnow --sitemap`; 열쇠 파일은 16번 조각이 내놓는다). **한 달에 한 번(1일 03:30, 이 맥의 launchd `kr.it.fermata.monthlyaudit`) `scripts/monthly_audit.py`가 `site_crawl`·`site_ui_audit`·`nav_check`를 차례로 돌려 텔레그램으로 알린다.** **`scripts/site_health.py`가 매일 두 번(`publish_check.yml`, 19:00·10:00) 사이트맵·핵심 페이지·데이터 날짜를 보고 틀리면 텔레그램으로 알린다.** 휴장일 표 `stock_db.KRX_HOLIDAYS`의 2027년은 계산값이다 — 12월 거래소 공고와 대조한다. 구글 색인 요청은 이 맥의 `~/.market-brief-google/gsc_daily_index.py`(launchd `kr.it.fermata.gscindex`, 매일 15:10, 10/31까지 — 색인 요청 한도는 **계정 하나에 하루 10건 안팎을 두 사이트가 나눠 쓴다**: 본진 5건(새 페이지·순위표 먼저, 그다음 시가총액 순 종목) + 블로그스팟 5건(가이드→잡지→Checkpoint·주간→시황), 할당량 초과분은 다음 날 다시). `tests/test_stock_db.py`가 이것들을 고정한다.
- **한국어 글은 전부 본진에 없고 네이버 전문이다**(2026-09-22 비공개로, 2026-09-26부터는 아예 올리지 않는다 — 사장님 결정:
  한국어는 네이버가 주력, 올려 두던 비공개 글은 휴지통). 시황·프리뷰·Checkpoint에
  이어 **한국어 가이드·주간 결산·다음 주 일정·이벤트**도 같은 처리다 — `publish_feature.LIVE_STATUS`에 네 줄, `naver_post`는 잡지를
  뺀 모든 글을 `ko.narrative` 전문·링크 없음으로 옮기고, `feature_checks.NAVER_FULL_ENDED`(2026-09-23)부터 네이버용 본문(`naver`)을
  요구하지 않는다. **영어 가이드("Guide")만 본진에 공개다.** 본진의 가이드·Weekly·Checkpoint 탭은 2026-09-26에 뺐다(위
  「본진은 영어 사이트다」). 되돌리려면 `LIVE_STATUS` 네 줄을 지우고 `naver_post`의 `full_body = not magazine`을 옛 조건으로 되돌린다.
  본진에 다시 (비공개로) 올리려면 `publish_feature.KO_TO_WORDPRESS`·`publish_editorial.KO_DAILY_TO_WORDPRESS`를 `True`로.
  **본진에서 사라진 한국어 글 주소는 사본으로 301 이동한다**(2026-09-26 — 구글이 색인해 둔 28쪽이 404였다). Code Snippets 13번이
  **404일 때만** 움직이고, 표는 이 맥의 `~/.market-brief-google/redirect_sync.py`가 만든다(블로그스팟 사본 → 네이버 사본 → 옛
  시황은 같은 날 영어판, 한국어 목록은 블로그스팟 이름표 목록). `blogger_sync`가 글을 올릴 때마다 다시 돌려 네이버로 보내던
  주소를 블로그스팟으로 바꾼다. 13번 조각을 손으로 고치지 말 것 — 다음 실행이 덮어쓴다.
  **시황 블로그(fermata49) 게시는 2026-09-26부터 멈춰 있다**(사장님 결정). 스위치는 이 맥의
  `~/.market-brief-naver/fermata49_pause.json` 하나이고 `naver_sync`가 읽는다(잡지는 그대로 올라간다). 그동안 한국어 원고는
  블로그스팟에만 나가고, 텔레그램·스레드 알림은 **블로그스팟 주소로** 나간다 — 맥의 `blogger_sync`가 올린 직후
  `scripts/notify_blogger_post.py`를 부른다(멈춤 스위치가 켜져 있을 때만, 오늘·어제 원고만, 잡지·영어 제외). 다시 켤 때는 `"paused": false`와
  `"resume_from"` 날짜를 적는다 — 멈춘 동안 쌓인 글을 한꺼번에 올리지 않는다. 멈춘 동안 이 계정에서는 자동 활동(서로이웃·공감·제보·올라간 글 고치기)을 하지 않고, 새 계정으로 우회하지 않는다. 이 맥의 `~/.market-brief-naver/weekly_expose.py`(launchd `kr.it.fermata.exposeweekly`, 월 08:30)가 두 블로그의 검색 노출을 대조군과 함께 재 운영 텔레그램으로 보낸다(판단선 10/10·10/24).
- **블로그스팟(fermata49.blogspot.com, "Fermata 매거진")은 구글용 한국어 창구다**(2026-09-25). 새 글을 쓰지 않고 원고를 그대로
  옮긴다 — 잡지·한국어 가이드·Checkpoint(확인 날짜가 안 지난 것)·주간 결산·다음 주 일정·이벤트 전부, 시황·프리뷰는 2026-09-25
  이후 것만(디스커버 4주 시험). 영어 가이드는 본진과 겹치므로 올리지 않는다. 렌더는 `scripts/blogger_post.py`(네이버와 같은
  블록 → HTML, 그림은 본진 미디어에 멱등 업로드, 잡지 표지는 Unsplash 주소, 글 끝 고정 줄: 텔레그램(시황 블로그 이웃 추가 줄은 게시 멈춤과 함께 뺐다),
  잡지는 퍼플썸 네이버로만 안내하고 페르마타 이름을 쓰지 않는다), 올리기는 이 맥의 `~/.market-brief-google/blogger_sync.py`
  (launchd `kr.it.fermata.bloggersync`, 10분, 하루 10편 상한(밀린 옛 글·잡지는 7편까지, 그날 새 시황·프리뷰는 옛 글과 따로 3편까지 — 자정에 옛 글이 상한을 다 써도 그날 글은 제때 올라간다, 2026-09-29), 공개 스위치 `~/.market-brief-google/blogger_publish_on`이 있을 때만
  게시, 같은 크롬 프로필을 쓰는 작업이 돌면 건너뜀). 블로거 설정은 맞춤 robots.txt·자료실/검색 페이지
  noindex·공식 테마(Contempo)다 — **맞춤 robots.txt를 바꾸지 말 것**(이유는 비공개 기록). 네이버에 올리는 시각은
  바꾸지 않는다. 판정은 11월 30일 서치콘솔(검색·디스커버 따로)과 애드센스로 하고, 잡지의 네이버 노출이 떨어지면 그날 멈춘다.
  `tests/test_blogger_post.py`가 렌더를 고정한다. **테마 겉모습은 토스피드 풍 + C안(크림 바탕·검은 테두리 카드·코너 색 이름표)이다**(2026-09-26) —
  Contempo 위에 스타일·Pretendard 글꼴·메뉴(매거진·가이드·Checkpoint·Weekly·시황)를 얹은 것이고, 이 맥의
  `~/.market-brief-google/blogger_theme_toss.py`가 넣는다(스타일만 `--update-css`, 되돌리기 `--restore`, 원본은
  `blogger_tmp/theme_before_toss_20260926.xml`). **글머리 한 줄과 표지 사진 출처는 글 끝에 둔다** — 블로거는 본문 첫 글자로 홈
  목록 요약을 만들어, 맨 위에 두면 요약이 "과학 사진: Unsplash …"로 시작한다(`blogger_post.render`).
- **네이버 글이 원고를 다 담았는지 두 곳에서 확인한다.** `tests/test_naver_completeness.py`는 만들어지는 원고를 절·outlook·insight·표·
  Take·확인 지점·출처까지 하나씩 세고, 그림이 **자기 절 밑에** 붙는지와 4장 상한이 되살아나지 않았는지 본다. `python -m
  scripts.naver_audit`은 **네이버에 올라간 화면**을 받아 같은 대조를 한다(빠지면 0이 아닌 값으로 끝난다). 둘 다 필요하다. **`chars >
  N` 같은 바닥값을 완결성 검사로 쓰지 말 것.** 이미 올라간 글의 제목은 `~/.market-brief-naver/retitle_sync.py`가 맞춘다 —
  `refill_all.py`는 본문만 다시 채운다. **맥의 `naver_sync`는 올리기 전에 그림 수를 센다**(2026-09-26) — 모자라면 10분 간격 세
  번까지 다시 그리고, 그래도 모자라면 올리지 않고 운영 텔레그램으로 알린다(네이버 글은 고치지 않으므로 빠진 채로 올리지 않는다).
  git 받기 실패는 로그에 이유를 남기고, 크롬 프로필을 다른 작업이 쓰는 중이면 기다렸다가 건너뛴다.
- **두 번째 네이버 블로그는 잡지다.** 시리즈 `매거진`, 원고는 `editorial/magazine/<날짜>_<slug>.json`, 루틴은
  `docs/routine_magazine.md`(매일 02:00 KST에 세 편 집필 — 다른 루틴이 없는 시각, 게시는 이 맥이 07:30·12:30·19:30 한 편씩, 코너 일곱:
  시장 읽기·시장의 역사·투자 심리·기업과 기술·과학·돈의 상식·만약에). **워드프레스에는 가지 않는다** — 발행 워크플로가 없고 이
  맥의 `naver_sync.py`가 `blogs.json`대로 두 번째 블로그에만 올린다(아이디가 비어 있으면 건드리지 않는다). 꼴은 제목 → 본문 → 자료
  출처. 외국 기사 전문 번역은 저작권 문제라 하지 않는다 — 출처 둘 이상을 종합해 우리 문장으로 쓴다 — 기자의 문장은 옮기지 않되 **기사 속 사람의 말은 누가 어디서 했는지 밝혀 따옴표로 옮긴다**(원문에서 확인한 말만). 잡지의 출처 검사는 원고
  `sources` 가운데 **본문에 이름이 실제로 나온 것**만 센다(`source_check.collect`), 첫머리에 '번역'이 있으면 막고, 사진 한
  장(`featured_photo.url`)을 요구한다(`feature_checks.magazine_issues`). 기준표용 '확인 날짜' 규칙은 잡지에 걸리지 않고, **간단
  브리핑도 Fermata's Take도 없다** — 표지 → 본문 → 자료 출처만. **브랜드는 퍼플썸이다** — 잡지 글의 태그·본문에 페르마타가 나가면
  안 된다(고정 태그 `퍼플썸매거진`). 형식 예시는 `tests/fixtures/magazine_sample.json`(관문 통과본, 루틴 프롬프트가 이 이름을 읽는다; 옛 꼴은 `magazine_sample_classic.json`). **2026-10-03부터 기본 꼴은 피우스형이다**(사장님 결정): 소제목 없이 한두 문장 문단(170자), 2,400~4,800자, 사람의 말을 그대로 옮긴 문단 하나 이상, **같은 문단 반복 금지**(`feature_checks.pius_issues`·`duplicate_paragraph_issues`; 옛 꼴은 `form: classic`만). 주제는 이름난 사람·회사의 결정·주장이 있는 기사를 먼저 고르고, 주장·근거·반론·숫자·독자의 돈으로 짜며 우리가 권하지는 않는다 — 지시문 「글의 꼴과 재미」, 견본 `tests/fixtures/magazine_sample.json`. 간단 브리핑은 싣지 않는다.
