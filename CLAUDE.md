# market-brief 작업 시 지켜야 할 것

> 이 파일은 **규칙만** 담는다. 규칙이 생긴 사건·날짜·사장님 말·실측은 `docs/decisions.md`에 같은 절·같은 순서로 있다
> (2026-09-25에 갈라 냈다 — 이 파일은 모든 세션·루틴에 자동으로 실리므로 짧아야 한다). 규칙을 새로 적을 때는 규칙 문장을
> 여기에, 이야기를 그쪽에 적는다. 규칙을 지울 때는 `python -m scripts.rule_diff CLAUDE.md`로 사라진 줄을 뽑아 줄마다 말한다.
> `AGENTS.md`는 Codex 등 다른 도구용 사본이고 **네 절이 글자까지 같아야 한다** — `tests/test_rule_files.py`가 확인한다.
> 한쪽만 고치면 다른 도구가 옛 규칙을 읽고 같은 실수를 반복한다.

## 검증 규칙 (반드시 지킬 것)

- **한국어 시황을 작성하거나 고치기 전에 `docs/editorial-style.md`를 읽고 따른다.** 영어 시황 관용구를 직역하거나 시장을
  불필요하게 의인화하지 않는다. 완성된 구조화 원고는 `src/editorial_quality.py`의 검사를 통과해야 한다.
- **제목·소제목 규칙은 `docs/editorial-style.md`의 「제목 문법」·「소제목」 절 하나뿐이고 블로그의 모든 글(시황·기준표·프리뷰·가이드)에
  같다. 검사도 `src/editorial_title.py` 하나다.** 글 종류별로 규칙을 따로 두지 말 것 — 나뉘어 있으면 고칠 때마다 한쪽이 빠진다.
  - 기준은 규칙 문장이 아니라 **사장님이 고른 예문집**(제목 35개 `OWNER_PICKS`, 시황 소제목 세트 S-A6, Checkpoint 세트 S-C1)이다.
    취향은 예문으로, 사실·화면은 장치로(등락률 반올림·둘 이상, 꼬리표, 길이, 금지 낱말, 같은 틀 반복). 재테크농부 통계로 만든
    규칙 문장은 쓰지 않는다 — 취향이 바뀌면 규칙 문장을 새로 적지 말고 예문을 늘린다. 낱개 규칙을 덧붙이는 식으로 고치지 말 것 —
    뼈대 규칙이 그대로면 결과도 그대로다.
  - **루틴은 `python -m src.editorial_gate <원고>`를 통과한 뒤에만 커밋한다.** 발행 단계는 문체·제목·구조를 막지 않고 경고만
    남긴다 — 숫자 대조(`editorial_facts`)만 막는다.
  - 관문이 최근 글과 **뼈대(틀)**를 대조해 막는다(`editorial_title.frame_issues`·`heading_mix_issues`). 같은 지적이 또 오면 낱개
    규칙을 더 얹지 말고 **반복되는 틀**부터 찾을 것. 쓰기 전에 `python -m scripts.recent_titles <kr|us|checkpoint|preview>`로
    최근 다섯 편의 꼴과 "피할 것"을 읽는다.
  - 대조 목록은 `src/title_feed.py`의 **독자 피드 한 줄**(올라가는 시각 순 — 미국장 D는 한국 D+1 아침)이고, 뼈대에 더해
    **같은 주인공은 다섯 편에 둘까지·같은 어구(7자 이상)는 한 번**을 본다(`editorial_title.subject_issues`). 규칙을 검사할 때는
    "무엇을 보나"만이 아니라 **"무엇과 대조하나"**가 독자의 화면과 같은지 본다.
  - 관문은 거르는 문이 아니라 **고르는 문**이다: 원고에 제목 후보 셋 이상을 축을 달리해 적고(`ko.title_candidates`),
    관문(`editorial_title.candidate_issues`)이 독자 피드와의 거리 점수(`title_distance`)가 가장 높은 후보를 제목으로 요구한다.
    루틴은 쓰기 전에 `python -m scripts.title_pick <kr|us|preview|checkpoint|…> "후보1" "후보2" "후보3"`으로 같은 점수를 본다.
    대상은 독자 피드의 글 전부(시황·프리뷰·기준표·주간·이벤트, `CANDIDATE_KINDS`), 가이드는 뺀다. **제목 지적이 또 오면 규칙
    문장을 더하지 말고 점수표(`title_distance`)의 가중치와 후보 요구를 먼저 본다.** **버린 꼴은 소제목에도 같다.**
- **보이는 부분만 깎지 않는다 — 바꾸기 전에 연쇄 목록, 바꾼 뒤에 원본 대조.** 절차 셋이 **의무**다.
  - **연쇄 목록**: 무엇을 바꾸기 전에 그것을 읽는 곳을 `grep`으로 다 찾아 표로 만든다(본진·네이버·표지·성적표·테스트·문서).
    표의 줄마다 '바꿈'·'해당 없음'을 적어 보고에 넣는다. 목록이 없으면 바꾸지 않는다.
  - **원본 대조**: 옮기거나 다시 쓴 것은 기계로 대조한다 — 네이버 글은 `python -m scripts.naver_audit`, 원고→네이버 블록은
    `tests/test_naver_completeness.py`, 문서·지시문을 다시 쓰면 **`python -m scripts.rule_diff <파일>`로 사라진 규칙 줄을 뽑아
    보고에 열거하고 줄마다 '일부러 뺐다'고 말한다.** 말할 수 없는 줄은 도로 넣는다. 사장님이 정한 문구는 테스트
    바늘(`tests/test_preview_series.py`의 needle 등)로 박는다.
  - **보고의 '안 한 것' 칸**: 확인 못 한 것·손대지 않은 것을 보고에 따로 적는다. 비어 있으면 안 한 것이 없다는 뜻이다 —
    빈칸을 채우려 들지 말고, 진짜 없을 때만 비운다.
- **사용자는 코드를 읽지 않는다. 보고에는 원인·설명·제안을 함께 담는다.** 같은 지적이 두 번 나오면 증상을 고치지 말고
  **그 결과를 만드는 규칙**을 찾아 바꾼다. 보고는 쉬운 말로 넷을 적는다 — 무슨 일이 있었나, 왜 그랬나, 무엇을 바꿨나,
  사용자가 정할 것은 무엇인가. 규칙을 바꾼 뒤에는 **다음 결과물을 직접 보고 벤치마크와 비교한 것**을 보고한다 — "고쳤다"가
  아니라 "이렇게 나왔다"가 보고다.
- **이미지는 쓰기 전에 실제로 다운받아 눈으로 확인한다.** alt text나 검색어만 보고 판단하지 말 것. 대표 이미지(featured image)든
  본문 삽입 이미지든, 발행 전에 `Read` 툴로 다운받은 파일을 직접 봐야 한다.
- **통화/지수 같은 추상적 개념은 이미지 검색이 특히 안 맞을 확률이 높다.** 브랜드/제품처럼 사진으로 명확히 알아볼 수 있는
  대상(개별 종목명, 회사 로고)은 검색이 비교적 안전하지만, "원화", "코스피", "금리" 같은 추상 개념은 사진 자체가 없거나 다른
  나라 것이 섞여 나올 때가 많다. `src/main.py`의 `_featured_image()`가 이 이유로 watchlist(개별 종목)만 대상으로 하고
  macro(지수·환율·금리·원자재)는 일부러 제외한다 — 이 원칙을 다른 이미지 자동화에도 유지할 것.
- **워드프레스 관리자 화면(플러그인 설정 등)의 정확한 위치는 기억으로 추측하지 말고 WebSearch로 확인한 뒤 안내한다.**
- **디버깅할 때 원인을 추측만으로 단정하지 말 것.** 근거가 간접적일 때는 "이건 추측이다"라고 명시하고, 가능하면 실제
  로그/트레이스백을 요청하거나 직접 확인한 뒤 결론을 내릴 것.
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

- 기본 자동 발행은 `src/generate_free.py`를 사용하며 외부 생성형 AI API를 호출하지 않는다. 실제 시세와 RSS 헤드라인만 정해진
  형식으로 조합한다.
- 평일 16:20 한국장 실행은 `--en`으로 한국어판과 영어판을 함께 만든다. `src/generate_free_en.py`가 같은 가격 데이터에서 영어
  문장을 직접 작성하고, 두 언어 품질 검사가 끝난 뒤 워드프레스 업로드 단계로 넘어간다.
- **규칙 기반 생성 결과(`src/main.py` / `generate_free.py`)는 절대 바로 공개하지 않는다.** 이 경로는 검수용 초안까지만 만든다.
  `run(publish_live=True)`는 예외로 멈추게 해 뒀으니 그 가드를 풀지 말 것.
- **`editorial_quality` 통과를 공개 근거로 삼지 말 것.** 문장 길이·금지 표현 같은 형식 검사이지 내용이 그날 장세를 설명하는지
  보지 않는다.
- **`editorial_facts`가 원고의 숫자를 시세와 대조한다**(`publish_editorial`이 한국어·영어 양쪽에 돌린다). 두 가지를 본다 — 원고에
  적힌 종목 등락률이 `price_data`와 맞는지, 그리고 그날 절대 등락 1위 종목이 원고 어디에도 없지는 않은지. 장중 인용·보유율·
  어림수는 일부러 건너뛴다 — 확실할 때만 실패시키는 것이 이 검사의 원칙이다. 이 예외를 좁혀 오탐을 만들지 말 것.
- **발행 뒤에는 되읽어 확인한다**(`publish_wordpress.verify_published`). 상태·제목·본문 길이가 기대와 다르면 예외로 멈춰
  워크플로가 빨간 X로 끝나게 한다.
- **`publish_check.yml`이 발행 시각 40분 뒤에 그날 글이 실제로 사이트에 있는지 확인한다**(`src/check_publication.py`).
  `verify_published`는 발행 스크립트가 돌았을 때만 확인하므로, 루틴이 원고를 못 써서 아무것도 커밋되지 않은 날은 이 워크플로가
  잡는다. 실패하면 깃허브가 메일을 보낸다. 휴장 판정은 달력이 아니라 지수의 실제 마지막 거래일이고, 글의 신선도는
  **"거래일 이후에 수정됐는가"**로 본다 — "36시간 안에 수정" 창으로 되돌리지 말 것(`tests/test_check_publication.py`).
- **테스트는 `tests.yml`이 push마다 돌린다.** 발행이 자동인데 테스트가 수동이면 의미가 없다. 외부 호출이 필요한 테스트는 mock으로
  막아 이 워크플로에서 돌 수 있게 유지할 것.
- **바로 공개해도 되는 것은 조사·집필을 마친 `editorial/*.json` 원고뿐이다.** 원고 커밋(push)으로 `editorial_publish.yml`이
  공개한다. 사람이 원고를 검수한 뒤 커밋하는 것이 곧 검수 단계다.
- 수동 실행(`workflow_dispatch`)과 손으로 돌리는 실행은 종전대로 임시저장이며, 이 기본값(`publish_draft(status="draft")`)을
  바꾸지 말 것.
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
- **매체 목록은 `config/magazine_feeds.yaml` 하나다.** 레이더가 읽는 묶음(`sets`: `magazine`·`ko`)과 시황 루틴이 이름만 쓰는
  목록(`market_media.kr`·`.us`)이 함께 있다. **아침 레이더(`python -m scripts.magazine_radar --set <묶음>`)는 주말
  Checkpoint(`ko,magazine`)·한국어 가이드(`ko`)·영어 가이드(`magazine`)·잡지(`magazine`)에만 붙인다** — 시황과 프리뷰에는 붙이지
  않는다. 레이더에서 얻는 것은 **주제뿐이다**(가이드에서는 목록 안 순서만 바꾼다) — 기사를 옮겨 쓰지 않고 사실은 늘 출처에서
  다시 확인한다. 피드를 더할 때는 **직접 받아 보고 출력까지 읽는다** — 죽은 피드와 잡음은 둘 다 "오늘 화제가 없다"로 보인다.
- **영어 가이드의 주제는 뉴스가 아니라 서치콘솔 검색어가 정한다.** 이 맥의 `~/.market-brief-google/gsc_queries.py`가 매일 10:30 KST
  (launchd `kr.it.fermata.gscqueries`)에 검색어를 긁어 `data/search_queries.json`으로 커밋하고, 루틴이 `python -m src.search_queue`로
  "오늘 무엇을 할지"를 읽는다(루틴은 서치콘솔에 로그인할 수 없다). **주 7편은 새 글 5편 + 기존 글 고치기 2편이다.** 큐의
  `gain`은 순서를 매기려고 만든 어림치이니 **글에 적지 말 것**. 영어 가이드에서 레이더(`--set en_kr`)는 주제가 아니라 **상시 글이
  낡았는지**를 보는 자리로만 쓴다. **큐는 검색 의도를 본다** — `search_queue.intent`가 행동(how to·buy·broker·etf·tax·hours)
  1.3배, 정의(what is·difference) 0.7배. 순위 밀린 글은 제목·첫 소제목·첫 문장에 검색어를 그대로 넣는다. `related` 제목은 발행 때
  살아 있는 제목으로 바뀐다(`publish_feature._refresh_related`).
- **한국어 시황은 본진에 `private`로 올리고, 네이버에는 본진 글을 그대로 옮긴다.** 스위치는
  `publish_editorial.KO_DAILY_TO_WORDPRESS`(켬)와 `KO_DAILY_STATUS`(`private`) 둘이다. 영어판(`-en`)은 그대로 공개다. 그림은
  **절 번호**로 붙이고 4장 상한은 없으며 `editorial_gate`가 본문·인사이트 **사진도 파일로 남긴다**. **원본이 어디인지 바뀌면 옮기는
  코드의 전제도 같이 바뀐다 — 본문을 어디서 가져오는지(`full`)만 갈아 끼우고 끝내지 말 것.**
- **프리뷰는 네이버에 본문 전문(링크 없이)으로 나가고, 본진에는 비공개로만 올린다.** 네이버 쪽은 시황과 같은 처리이고, 본진 쪽은
  `publish_feature.LIVE_STATUS`의 한 줄이다. 워드프레스 `private`는 글·주소·분류를 그대로 두고 **사이트맵·목록·피드·익명
  접근(404)에서만 뺀다**. **비공개 글은 텔레그램·스레드에 알리지 않는다** — 알림은 맥의 동기화가 네이버에 올린 뒤 네이버 주소로
  보낸다(`scripts/notify_naver_post.py`).
- **미국장 시황·프리뷰를 저녁 한 편으로 합치는 개편은 보류다**(사용자 결정, 되돌린 커밋은 `11c6ac6`의 revert). 다시 할 때는
  목표 5,500~6,500자 미달·`number_cards` 반복·19분 소요 셋부터 손본다.
- **`publish_check.yml`은 예비 예약까지 끝난 뒤(19:00/10:00 KST)에 돈다.** 루틴보다 먼저 울리면 정상 발행일에도 실패 메일이 온다.
- **코스피·코스닥 일봉은 개별 종목보다 늦게 나온다.** `fetch_kr._apply_final_index_quote`가 네이버 실시간 `ms=CLOSE` 값을
  **전일 종가 + 등락폭 = 확정 종가** 등식이 맞을 때만 오늘 행으로 덧붙인다(휴장일엔 등식이 안 맞아 가짜 행이 생기지 않는다).
  등식 검증을 빼고 "CLOSE면 붙인다"로 느슨하게 만들지 말 것. 일봉이 우리가 이미 커밋한 시세 파일보다 뒤처지면 그 파일의 이력을
  밑바탕으로 쓰고 등식은 그 마지막 종가와 맞춘다(`_latest_committed_index`). `tests/test_price_fetch.py`가 이 날들을 재현한다.
- **한국장 종목 가격·등락률의 기준은 KRX 정규장 확정 종가이고, 시세 파일은 거래일마다 한 번만 쓴다**(2026-09-25).
  `fetch_kr._apply_krx_close`가 네이버 폴링(`SERVICE_ITEM`, `nv`/`pcv`, `ms=CLOSE`일 때만)으로 덮어쓰고, **폴링의 `cr`·`cv`는 부호가
  없다**(부호는 `nv−pcv`에서). 이미 있는 거래일 파일은 가격을 두고 **빈 칸(수급·편입 종목)만 보강**한다(`main._merge_price_file`).
  되돌리지 말 것.
- **루틴 턴 절약 장치 넷**(2026-09-25): ① 첫 명령 `python -m scripts.routine_precheck <kr|us|preview>`(어제 원고 JSON 통째 읽기
  대신 요약) ② 관문·렌더가 그림을 **모음판**(`sheets/sheet-NN.png`, 원본 크기 그대로)으로 이어 붙인다 — **읽는 장수를 줄이지는
  않는다** ③ `graphic_checks.collect_spec_issues`에 `price_data`·`section_body`(제목의 '만·유일·신고가·최고' vs 데이터, 그린 종목이
  절 본문에 하나도 없음, 표 셀 폭; `fact_table`은 19→17→15로 자동 축소) ④ 프리뷰에도 숫자 대조(`editorial_facts.collect_issues_for_preview`,
  목표주가·52주 고점·PER·프리마켓·%포인트는 제외)와 제목 후보의 어림수 검사. 지시문에는 push 뒤 대기·조회 금지, 검색은 사실당 두 번,
  `env` 출력 금지. 관문을 **매일 걸리게** 만들지 말 것.
- 예약 시각을 마감 정각으로 되돌리지 말 것. 16:00/07:00 정각은 시세가 아직 안 채워져 죽는다 — 두 시장 모두 20분 뒤다.
- **대표 이미지는 `src/featured_image.py`가 세 가지 중 하나를 고른다** — 사진(photo)·단독(single)·삼분할(trio). 어느 쪽이든
  **숫자는 실제 마감 시세에서 나오므로 틀린 그림이 붙지 않는다.**
- **표지 사진은 `config/photo_pool.yaml`에 미리 승인해 둔 것만 쓴다.** 시황은 사람 검수 없이 자동 공개되므로 발행 시점에 검색하면
  안 된다 — **검색은 사람이 미리 하고 자동 실행은 고르기만 한다**(`src/photo_pool.py`). 명세의 `seen` 줄에는 검색어가 아니라
  **사진에 실제로 보이는 것**을 적는다.
  - 사진을 더할 때: `python -m src.photo_search --sheet <이름> <검색어들>` → 대조표를 `Read`로 열어 보고 → `assets/photos/`에
    넣고 → 명세에 항목을 적는다.
  - 업종에 사진이 없는 날은 **사진 없이 그래픽으로 간다.** 억지로 아무 사진이나 붙이면 보관함을 만든 이유가 없어진다.
  - **동적 편입 종목에는 붙이지 않는다.**
  - 같은 업종에 사진이 여럿이면 **그 묶음이 표지 사진을 쓴 횟수**로 차례를 돌린다(`featured_image.cover_turn`이 커밋된 시황
    원고에서 다시 센다, 2026-09-26) — 다섯 장을 다 쓰기 전에는 같은 사진이 안 돌아온다. 날짜÷장수로 돌리지 말 것(사흘 연속만
    다르고 닷새 뒤엔 같은 사진이 왔다). 같은 날 다시 돌리면 같은 사진이 나온다(재실행이 표지를 바꾸면 워드프레스에
    미디어가 중복으로 쌓인다).
  - CC BY 계열은 **저작자 표시가 의무**라 `credit`을 미디어 캡션에 그대로 싣는다. NC·ND는 `photo_search`가 애초에 거른다.
- **`src/fetch_images.py`(Unsplash -> 위키미디어 엔티티 검색)는 자동 발행 경로에서 쓰지 않는다. 검색어로 사진을 자동으로 붙이는
  경로를 다시 만들지 말 것.**
- **인사이트 스토리 사진은 사람이 본 사진에서만 온다.** 경로는 둘뿐이다 — 루틴이 샌드박스에서 Unsplash 후보를 직접 내려받아
  `Read`로 보고 골라 원고의 `image.url`에 적은 것, 아니면 `image_query`의 코어 종목명으로 승인 풀(`config/photo_pool.yaml`)에서
  고른 업종 사진. 발행 시점 실시간 검색은 없다. 코어 종목명 가드(`_concrete_image_query`)는 그대로다. 종목명이 없거나 풀에 업종이
  없으면 사진 없이 표·차트만 나가고 이유가 로그에 남는다. `tests/test_insight_photos.py`가 이 구조를 고정한다.
- **워치리스트는 두 시장 모두 코어(고정) + 동적(그날 편입) 2단 구조다.** 코어는 `config/watchlist_kr.yaml`의 섹터 대표 21종목과
  `config/watchlist_us.yaml`의 16종목이고, 여기에 그날 거래대금 상위 종목이 `source: "dynamic"`으로 붙는다(`src/fetch_movers.py`).
  동적 편입 기준은 **거래대금**이며 등락률로 바꾸지 말 것. 규칙 기반 초안의 종목 카드 6개(`stock_section.featured_tickers`)
  편성 기준은 `docs/editorial-style.md`의 「종목 선정」 절을 따른다 — 등락률 순으로 기계적으로 자르지 않는다.
- **동적 편입 종목에는 사진을 붙이지 않고, 기준일이 코어와 다르면 아예 버린다**(`fetch_kr`/`fetch_us`의 `_fetch_dynamic_tier`).
  이름도 모르는 종목 하나가 그날 발행 전체를 멈추게 하면 안 되기 때문이다. 반대로 대표 이미지의 LARGEST MOVE는 편입 종목도
  후보에 넣는다 — 데이터에서 텍스트를 그리는 것이라 틀린 그림이 붙을 위험이 없다.
- GitHub Actions에는 **Anthropic·OpenAI 키를 전달하지 않는다.** 유료 생성 경로(`generate_post.py`, `translate_post.py`)를 자동
  실행에 다시 연결하지 말 것. Unsplash 키는 Actions 어디에도 넘기지 않는다 — 사진 검색은 루틴 샌드박스에서 사람처럼 보고
  고르는 경로로만 한다.
- **조사·집필은 클라우드 루틴이, 시세 수집은 GitHub Actions가 맡는다.** 예약 실행이 시세를 `data/price_<market>_<거래일>.json`으로
  커밋하고, 루틴이 그 파일을 읽어 원고를 쓴다. 루틴 프롬프트에서 `fetch_kr/fetch_us`를 직접 부르게 만들지 말 것 — 그렇게 두면
  매일 같은 지점에서 멈춘다.
- 무료 생성 결과는 `output/{market}_{trading_date}_generated_free.json`에 캐시된다. 자동 검증하지 못한 시장 원인·전망은 추측해서
  넣지 않는다.
- **`publish_editorial.py --render-only`는 `WORDPRESS_*`가 설정돼 있으면 완전한 dry-run이 아니다.** 본문 그래픽·사진은 실제로
  미디어 라이브러리에 업로드된다. 순수 렌더만 보고 싶으면 `WORDPRESS_URL` 등을 비우고 돌린다(`publish_feature.py --render-only`는
  이 문제가 없다).

## 기준표(feature) 글

도구는 다섯 줄이다. 순서대로 쓴다.

    python -m src.story_engines --list                 # 1. 재료를 먼저 뽑는다
    python -m scripts.title_helper 대비                # 2. 제목은 실제 예문에서
    python -m src.photo_search --sheet 은행 bank ...   # 3. 사진은 한 판에 12장
    python -m src.feature_gate <원고> --graphics <N>   # 4. 검사는 이거 하나
    python -m src.publish_feature <원고>               # 5. 발행도 이거 하나

- **글을 쓸 때 우리는 재테크농부다.** 벤치마크 100편을 실측해 정한 기준이 `docs/feature-style.md`에 있다. 기준표 원고를 쓰거나
  고치기 전에 반드시 읽는다. 일간 시황 기준(`editorial-style.md`)과 별개다.
- 핵심 셋: **제목에 결론을 넣지 않는다**(읽기 전에 답을 알면 누를 이유가 없다), **시각자료 최소 6장**(벤치마크 중앙값 10장),
  **본문에 확인 날짜를 박는다**(글의 수명이 그날까지 늘어난다).
- **독자에게 보이는 이름은 Checkpoint다.** 내부 키(`series: 기준표`)는 그대로 두고 화면에 나가는 곳만 — 워드프레스 분류
  Checkpoint(id 432)와 홈 탭, 글 머리말 `Checkpoint · N월 N일까지 확인할 것`(원고 최상위 `deadline`, 관문이 확인), 표지 kicker.
  제목 글자에 라벨을 넣지 않는다 — 대신 확인 날짜를 제목에 넣는 것이 기본이다.
- **제목·소제목 규칙은 `docs/editorial-style.md` 「제목 문법」·「소제목」 하나이고 모든 글(시황·기준표·프리뷰·가이드)에 같다.
  검사도 `src/editorial_title.py` 하나다.** 글 종류별로 규칙을 따로 두지 말 것.

### 재료를 먼저 뽑는다 (`src/story_engines.py`)

- 엔진 12개가 밸류에이션·등급변경·실적일정·내부자매수·수급·계절성·13F·업종·금리(FRED/ECOS)를 가져온다. **재료 없이 쓰기
  시작하지 않는다.** `src/source_check.py`가 서로 다른 외부 출처 3곳 미만이면 발행을 막는다.
- **엔진이 `⚠ N건을 받지 못했습니다`를 찍으면 그 결과를 쓰지 않는다.** 없는 사실을 쓰게 된다.

### 제목·소제목은 실제 예문에서 가져온다 (`scripts/title_helper.py`)

- 관계(`대비`·`원인`·`질문`·`경고`·`개수`·`시한`)로 벤치마크 실제 제목을 찾아 **그 어법을 그대로 갈아입힌다.** 낱말을 세어 새로
  짓지 않는다.
- **빈도는 그 낱말이 어느 자리에 오는지를 알려주지 않는다.**
- **문서에 적힌 수치를 목표로 삼지 않는다.** `scripts/compare_to_benchmark.py`는 코퍼스를 그 자리에서 다시 재고, 결과를 "맞춰야
  할 기준이 아니다"라고 못박아 출력한다. 코퍼스는 이 컴퓨터에만 있으므로(남의 글을 저장소에 올리지 않는다) 클라우드 루틴은
  `--export-stats`로 내보낸 집계 파일 `data/benchmark_stats.json`을 읽는다 — 이 맥의 야간 작업(`scripts/bench_nightly.sh`, launchd
  23:10)이 집계값이 바뀐 날만 커밋·푸시한다.

### 사진 (`src/photo_search.py`)

- **한 판에 12장을 펼쳐 놓고 번호로 고른다.** `--sheet`가 검색어 여러 개를 한 번에 돌려 대조표를 만든다.
- **그 회사 사진이 없으면 한 단계 넓힌다.** 은행주 글이면 `bank`·`financial district`, 반도체 글이면 `microchip`·`semiconductor`.
  특정 회사가 아니어도 업종이 맞으면 표지로 충분하다. **회사가 식별되는 사진도 괜찮다.**
- 출처는 Openverse(워드프레스 재단 CC 통합검색, 키 불필요)이고 `NC`·`ND`는 거른다. 유니스플래시 한국어 검색과 위키데이터 P18은
  **믿지 않는다**.
- 받은 파일은 **반드시 `Read` 툴로 직접 본다.** 예외 없다.

### 검사와 발행은 각각 하나뿐이다

- `src/feature_gate.py`가 다섯 검사(`editorial_quality`·`editorial_title`·`feature_checks`·`source_check`·벤치마크 대조 둘)를 한
  번에 돌린다. 앞의 넷은 막고, 벤치마크 대조는 보고만 한다. **검사를 따로따로 기억해서 돌리지 않는다.**
- `src/publish_feature.py`가 렌더→그래픽→멱등 업로드→발행/갱신→되읽기를 한 명령으로 끝낸다. 임시 스크립트를 새로 쓰지 않는다.
- **주말 기준표는 루틴이 쓴다**(`docs/routine_feature.md`). 토·일 09:00 KST에 재료를 뽑아 원고를 커밋하면 `feature_draft.yml`이
  올린다. 자동화 스위치가 켜져 있어 커밋 즉시 공개된다. 스위치를 끄면 임시저장으로 돌아가고, 그때 공개는 사람이 "발행"이라고 한
  뒤 `python -m src.publish_feature <원고> --publish` 한 번이다. 루틴이 고른 표지 사진은 `featured_photo.url`로 적고 러너가 받는다 —
  `output/`은 커밋하지 않는다.
- **기준표 성적표**(`data/scoreboard.yaml` → `src/publish_scoreboard.py` → /scoreboard/ 페이지). 기준표마다 "언제 무엇을 확인할지"를
  적고, 날짜가 지나면 실제 결과와 판정(적중·빗나감·절반·확인 전)을 적는다. 틀린 것도 지우지 않는다. 파일이 바뀌면
  `scoreboard_publish.yml`이 페이지 본문만 갱신한다(상태는 안 건드림). 판정에는 반드시 result(숫자)와 checked(날짜)를 함께 적는다 —
  없으면 검사가 막는다. **시황도 성적표에 오른다** — 원고의 `closing.check`(확인 지점)와 `review`(어제 판정)를 발행 워크플로가
  `src/scoreboard_sync.py`로 옮긴다. 관문(`editorial_gate`)이 세 문장 이상의 판단·확인 지점·어제 판정·초보자 설명을
  본다(`src/editorial_judgment.py`) — 발행은 막지 않고 경고만 남긴다.
- **자동화 스위치는 GitHub 저장소 변수 `FERMATA_AUTO_PUBLISH` 하나다.** `true`면 기준표 초안이 커밋 즉시 공개되고 성적표 페이지도
  처음 만들 때부터 공개된다. 성적표 페이지(724)는 그전에 임시저장으로 만들어져 스위치와 무관하게 보류 상태다(`publish_scoreboard`는
  있는 페이지의 상태를 건드리지 않는다) — 공개는 사람이 "발행"이라고 한 뒤. 새 발행 경로를 만들 때는 이 변수를 같은 뜻으로 읽게 만든다 — 스위치를 여럿 두지 않는다.
- **밤 9시 반 미국장 프리뷰는 시리즈 "프리뷰"로 기준표 파이프라인을 쓰되, 그날 미국장의 메인 글이다.** 평일 21:30 KST 루틴이
  `editorial/previews/us_<날짜>.json`을 커밋하면 `preview_publish.yml`이 본진에 **비공개**로 올리고 맥이 네이버에 전문을 올린다.
  구성은 `docs/routine_preview.md`의 12절. 문턱은 절 10·시각자료 8·출처 4(`editorial_title.SECTION_FLOORS`,
  `feature_checks.SERIES_LIMITS`, `source_check.SERIES_MIN_SOURCES`)에 더해 절당 400자, 같은 그래픽 종류 2장, 초보자 설명 둘 이상.
  지시문의 **22:00 마감**. 아침 마감 시황은 그대로다(판정·성적표·한국 연결 담당) — 합치지 않는다. **「월가 리포트」
  엔진**(`story_engines.street`)이 MarketBeat에서 시장 전체의 등급 전→후·목표가 전→후를 읽고, 막히면 야후로 S&P 500을 돌린다.
  '핵심 내용'은 원천에 없으니 루틴이 상위 몇 건만 출처를 열어 한 줄로 붙인다 — 지어내지 않는다. `story_material.yml`의
  `all --market us`에 들어 있다.
- **주말 편성**: 토 10:00 KST 「주간 결산」(`docs/routine_week_review.md`, `editorial/weekly/review_<토요일>.json`, 시리즈 "주간 결산")과
  일 20:00 KST 「다음 주 일정」(`docs/routine_week_ahead.md`, `editorial/weekly/ahead_<일요일>.json`, 시리즈 "다음 주 일정")은 기준표
  파이프라인을 그대로 쓰고 `weekly_publish.yml`이 **바로 공개**한다. 분류는 Weekly(id 433, 목록 페이지 `/weekly/`, 홈 탭; 네이버에도
  같은 이름). 지수·종목·환율·금리 숫자는 `python -m scripts.weekly_stats`에서만 온다 — 검색 결과의 등락률을 옮겨 적지 않는다.
  그래픽은 `number_cards`·`movers_list`에 `"period": "week"`를 넣어 달력 주간 등락으로 그린다. 문턱은 주간 결산 절 5·시각자료 4·출처 2,
  다음 주 일정 절 4·시각자료 3·출처 2. 머리말은 최상위 `period`로 `주간 결산 · 9월 7일~11일`. 거래일 3일 미만인 주는 결산을 쓰지
  않는다. 지난주 판정(맞음·빗나감)은 이 글에 넣지 않는다 — 사용자가 아직 정하지 않았다.
- **유입 편성**: 새 시리즈 셋이 기준표 파이프라인에 표 한 줄씩으로 있다 — **가이드**(한국어 상시, 매일 13:00 KST, 주 7편,
  `docs/routine_guide_ko.md`, `editorial/guides/ko_<slug>.json`, 분류 **509**(`/guide/`), 머리말은 최상위 `checked` 날짜),
  **Guide**(영어, 매일 11:00 KST, 주 7편, `docs/routine_guide_en.md`, `editorial/guides/en_<slug>.json`, `lang: "en"` — 관문이 한국어
  검사 대신 영어 검사(`feature_checks.collect_issues_en`)와 영어 출처 목록(`source_check.EN_SOURCES`)을 쓴다, 분류 **153**(`/guides/`);
  주제 60개를 아홉 갈래로 나눠 어제와 다른 갈래에서 고른다), **이벤트**(일요일 다음 주 일정 루틴이 그 주의 큰 이벤트 하나를
  `editorial/events/<날짜>_<slug>.json`으로 더 쓴다, 분류 Weekly, 머리말은 `event_date`). 한 목록에 두 언어를 섞지 않는다.
  `guide_publish.yml`·`weekly_publish.yml`이 자동화 스위치대로 공개한다. 문턱은 가이드 절 5·시각자료 2·출처 2, Guide 절 5·2·2, 이벤트
  절 4·2·2. **종목 허브 페이지** `/stocks/<slug>/` 37개(`config/stock_pages.yaml`, `src/stock_pages.py`, `stock_pages.yml` 토 11:30 KST):
  숫자는 시세 파일에서만, 「최근 흐름」은 매월 1일 루틴의 `editorial/stocks/notes_<YYYY-MM>.json`(`docs/routine_stock_notes.md`,
  `--check-notes` 통과 후 커밋). 홈·목록 탭에 Stocks. 한국어 가이드·이벤트는 네이버에 전문, 본진은 비공개(아래 「발행 워크플로우」).
- 그림을 그린 뒤에는 **`Read` 툴로 직접 본다.** 축을 한 종목이 독차지하거나 이름이 막대와 어긋나는 것은 코드만 봐서는 안 보인다.
  `src/graphic_checks.py`가 그림의 데이터와 제목이 어긋나는 것을 잡지만 전부는 아니다.

### 조용한 실패를 만들지 않는다

실패했는데 성공처럼 보이던 것들이다.

- 단독 실행 모듈에 `load_dotenv()`가 빠져 있으면 "업로드 안 함"으로 조용히 끝난다.
- 한글 폰트가 없으면 두부(□)로 그리고도 테스트가 통과한다(CI에 폰트가 없었다).
- 설정이 없으면 빈 dict를 돌려주고 "건너뜁니다"라고만 찍는다.
- 엔진이 예외를 삼키면 "못 받았다"와 "0건"이 같은 화면으로 나온다.

**새 코드에서 `except: continue`를 쓸 때는 반드시 센다.** 세지 않을 거면 삼키지 않는다. 마찬가지로 `if not 설정: return`은 쓰지
않는다 — 예외로 올린다.

## 발행 워크플로우

- 새 글이든 기존 글 수정이든, 사용자가 명시적으로 "발행해"라고 하기 전엔 워드프레스에 **임시저장(draft)**으로 올린다. 검수 후
  상태를 `publish`로 바꾼다.
- 같은 초안을 여러 번 고칠 땐 새 글을 또 만들지 말고 `publish_wordpress.update_draft()` / `publish_guide.py`의 `post_id` 인자로
  같은 글을 덮어쓴다 — 임시저장 글이 중복으로 쌓이는 걸 방지.
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
- **사이트맵은 워드프레스 기본(`/wp-sitemap.xml`)이다.** Rank Math 사이트맵 모듈은 꺼 두었고 옛 `/sitemap_index.xml`은 404다.
  **다시 켜지 말 것.** 네이버 서치어드바이저에는 새 주소를 제출했고, 구글 서치콘솔은 사용자 계정으로 제출한다. 새 글마다
  `~/.market-brief-naver/nsa_request.py`가 네이버 수집 요청을 넣는다(10분 동기화에 붙어 있음).
- **공개된 한국어 글은 텔레그램 채널 `@fermata_kr`과 스레드 `@fermata.it.kr`에 자동으로 올린다**(`src/notify_telegram.py`·
  `src/notify_threads.py`, `publish_feature`·`publish_editorial`이 공개 직후 부른다). 표지 + 제목 + Take 두 문장 + 링크. 다시 올린
  글(최초 공개와 수정이 10분 넘게 벌어진 글)과 영어 글은 보내지 않는다. 토큰은 GitHub 시크릿(`TELEGRAM_BOT_TOKEN`,
  `THREADS_ACCESS_TOKEN`, `THREADS_USER_ID`)과 로컬 `.env`에만 — 저장소에 적지 않는다. 스레드 토큰은 60일짜리라 이 맥의
  launchd(`kr.it.fermata.threadsrefresh`, 일 21:30)가 `scripts/threads_auth.py refresh`로 갱신한다. 알림 실패는 발행을 실패시키지
  않고 `[텔레그램 실패]`·`[스레드 실패]`로만 찍는다.
- **네이버 제목은 본진 제목 그대로다.** 검색어·날짜 머리도 `| 투자 체크포인트` 꼬리도 붙이지 않는다 —
  `scripts/naver_post.naver_title()`은 본진 제목을 그대로 돌려주고, 이미 올라간 글은 `~/.market-brief-naver/retitle_sync.py`로 맞춘다.
  **제목에 검색어를 넣는 일은 제목 문법의 몫이다**(`docs/editorial-style.md` 「제목 문법」). 네이버 쪽 검색 작업은 블로그에 건다.
  예문집에 시간·질문·감춤 이유·독자·내 돈·1인칭·인용 축이 있고(`editorial_title.AXIS_PICKS`), 관문(`axis_issues`)이 최근 네 편에 없는
  축을 이번 제목이 채우는지 보며 답 노출형은 다섯 편에 한 번만 둔다. 1인칭 제목은 「판단」 절의 **대응 원칙**(추천이 아니라 조건이
  붙은 우리 원칙)과 짝이다.
- **네이버에 가는 요약본은 본진과 다른 문장으로 다시 쓴다.** 네이버는 겹치는 글을 유사문서로 걸러 내고, 걸리면 **네이버 통로가
  통째로 막힌다**. 규칙은 `feature_checks.naver_spec()` 한 곳이다: 가이드·주간 결산·다음 주 일정·이벤트는 절 4~6·1,200~3,000자,
  시황은 절 3~5·900~2,200자(분량을 늘리는 것이 목적이 아니라 겹침을 없애는 것이 목적이다). 25자 이상 같은 문장이 있으면 관문이
  막는다 — 기준표 계열은 `feature_gate`, 시황은 `editorial_gate`. 루틴 지시문은 `docs/routine_common.md`의 「네이버용 본문」 절이고,
  규칙을 바꾸면 그 문서도 같이 고친다. **전문이 가는 글은 본진과 같은 차례다 — 표지 → 본문 → Fermata's Take → 다음 확인 지점.** **표지는 원고에 `featured_photo.url`
  사진이 있으면 그 사진이 먼저 가고, 남색·베이지 cover 그래픽은 그 다음에 그대로 간다**(Checkpoint·프리뷰·가이드·주간·이벤트 전부,
  2026-09-26 사장님 "1번으로 해, 사진 다음에 틀" — 그전에는 잡지만 사진이고 나머지는 전부 틀뿐이었다. 틀은 9/8에 사장님이 여섯 안 중
  고른 것이라 빼지 않는다). 맥의 `naver_sync.render`가 `00-photo-cover.jpg`로 내려받고 `blogger_post`는 원본 주소를 쓴다.
  Take를 두 문장만 뽑아 맨 위 인용구로 올리는 것은 **요약본**의 규칙이다. `tests/test_naver_post.py`가 양쪽을 다 고정한다.
- **Checkpoint도 본진에는 비공개로만 올라가고 네이버에 본문 전문이 나간다.** 프리뷰와 같은 처리다 — `publish_feature.LIVE_STATUS`에
  `"기준표": "private"` 한 줄. 성적표의 본진 주소는 네이버 주소로 갈아 끼운다(`scripts/scoreboard_naver_urls.py`가 빈 칸을 채울 뿐
  아니라 비공개가 된 주소도 바꾼다). 바꾸지 않으면 `publish_scoreboard.only_live`가 404를 보고 그 항목을 성적표에서 통째로 뺀다.
- **홈·목록의 Checkpoint 탭은 네이버 블로그 카테고리로 간다.** 탭은 그대로 두고 `href`만
  `https://blog.naver.com/fermata49?Redirect=Category&categoryNo=6`으로 바꿨다(`target="_blank"`). 고친 곳은 **페이지 6개(76 daily·77
  guides·105 all·1047 checkpoint·1439 weekly·1610 guide) + `twentytwentyfive//home` 템플릿** — 이 일곱이 탭 줄이 복제돼 있는 전부다
  (724 scoreboard·1479 stocks의 'Checkpoint'는 본문 글자이지 탭이 아니다). `flex-wrap`을 건드리지 말 것 — 모바일에서 탭 줄이 두
  줄로 접혀야 가로가 넘치지 않는다. `/checkpoint/` 페이지의 `query-no-results` 블록은 네이버 안내이고 목록이 다시 채워지면 저절로
  사라진다. 네이버 카테고리 번호는 추측하지 말고 `PostList.naver?blogId=fermata49`를 받아 `categoryNo=`로 확인한다(시황 1·Checkpoint
  6·가이드 7·Weekly 8).
- **한국어 글은 전부 본진 비공개·네이버 전문이다**(2026-09-22, 사장님 결정: 네이버가 한국어 주력). 시황·프리뷰·Checkpoint에
  이어 **한국어 가이드·주간 결산·다음 주 일정·이벤트**도 같은 처리다 — `publish_feature.LIVE_STATUS`에 네 줄, `naver_post`는 잡지를
  뺀 모든 글을 `ko.narrative` 전문·링크 없음으로 옮기고, `feature_checks.NAVER_FULL_ENDED`(2026-09-23)부터 네이버용 본문(`naver`)을
  요구하지 않는다. **영어 가이드("Guide")만 본진에 공개다.** 가이드·Weekly 탭도 네이버 카테고리 7·8로 간다(Checkpoint 탭과 같은
  방식, 같은 일곱 곳). 되돌리려면 `LIVE_STATUS` 네 줄을 지우고 `naver_post`의 `full_body = not magazine`을 옛 조건으로 되돌린다.
- **블로그스팟(fermata49.blogspot.com, "Fermata 매거진")은 구글용 한국어 창구다**(2026-09-25). 새 글을 쓰지 않고 원고를 그대로
  옮긴다 — 잡지·한국어 가이드·Checkpoint(확인 날짜가 안 지난 것)·주간 결산·다음 주 일정·이벤트 전부, 시황·프리뷰는 2026-09-25
  이후 것만(디스커버 4주 시험). 영어 가이드는 본진과 겹치므로 올리지 않는다. 렌더는 `scripts/blogger_post.py`(네이버와 같은
  블록 → HTML, 그림은 본진 미디어에 멱등 업로드, 잡지 표지는 Unsplash 주소, 글 끝 고정 줄: 네이버 이웃·텔레그램·종목 페이지,
  잡지는 퍼플썸 네이버로만 안내하고 페르마타 이름을 쓰지 않는다), 올리기는 이 맥의 `~/.market-brief-google/blogger_sync.py`
  (launchd `kr.it.fermata.bloggersync`, 10분, 하루 10편 상한, 공개 스위치 `~/.market-brief-google/blogger_publish_on`이 있을 때만
  게시, 같은 크롬 프로필을 쓰는 작업이 돌면 건너뜀). 블로거 설정은 네이버 봇 `Yeti` 차단(맞춤 robots.txt)·자료실/검색 페이지
  noindex·공식 테마(Contempo)다 — **네이버가 이 사본을 보면 유사문서로 거르므로 Yeti 차단을 풀지 말 것.** 네이버에 올리는 시각은
  바꾸지 않는다. 판정은 11월 30일 서치콘솔(검색·디스커버 따로)과 애드센스로 하고, 잡지의 네이버 노출이 떨어지면 그날 멈춘다.
  `tests/test_blogger_post.py`가 렌더를 고정한다.
- **네이버 글이 원고를 다 담았는지 두 곳에서 확인한다.** `tests/test_naver_completeness.py`는 만들어지는 원고를 절·outlook·insight·표·
  Take·확인 지점·출처까지 하나씩 세고, 그림이 **자기 절 밑에** 붙는지와 4장 상한이 되살아나지 않았는지 본다. `python -m
  scripts.naver_audit`은 **네이버에 올라간 화면**을 받아 같은 대조를 한다(빠지면 0이 아닌 값으로 끝난다). 둘 다 필요하다. **`chars >
  N` 같은 바닥값을 완결성 검사로 쓰지 말 것.** 이미 올라간 글의 제목은 `~/.market-brief-naver/retitle_sync.py`가 맞춘다 —
  `refill_all.py`는 본문만 다시 채운다.
- **두 번째 네이버 블로그는 잡지다.** 시리즈 `매거진`, 원고는 `editorial/magazine/<날짜>_<slug>.json`, 루틴은
  `docs/routine_magazine.md`(매일 02:00 KST에 세 편 집필 — 다른 루틴이 없는 시각, 게시는 이 맥이 07:30·12:30·19:30 한 편씩, 코너 일곱:
  시장 읽기·시장의 역사·투자 심리·기업과 기술·과학·돈의 상식·만약에). **워드프레스에는 가지 않는다** — 발행 워크플로가 없고 이
  맥의 `naver_sync.py`가 `blogs.json`대로 두 번째 블로그에만 올린다(아이디가 비어 있으면 건드리지 않는다). 꼴은 제목 → 본문 → 자료
  출처. 외국 기사 전문 번역은 저작권 문제라 하지 않는다 — 출처 둘 이상을 종합해 우리 문장으로 쓴다. 잡지의 출처 검사는 원고
  `sources` 가운데 **본문에 이름이 실제로 나온 것**만 센다(`source_check.collect`), 첫머리에 '번역'이 있으면 막고, 사진 한
  장(`featured_photo.url`)을 요구한다(`feature_checks.magazine_issues`). 기준표용 '확인 날짜' 규칙은 잡지에 걸리지 않고, **간단
  브리핑도 Fermata's Take도 없다** — 표지 → 본문 → 자료 출처만. **브랜드는 퍼플썸이다** — 잡지 글의 태그·본문에 페르마타가 나가면
  안 된다(고정 태그 `퍼플썸매거진`). 형식 예시는 `tests/fixtures/magazine_sample.json`(관문 통과본).
- **고친 것이 있으면 곧바로 커밋·푸시한다.** 클라우드 루틴이 규칙과 관문 코드를 **깃허브에서** 받아 가기 때문이다 — 맥에서만 고쳐
  두면 루틴은 옛 규칙으로 계속 돈다. 대상은 `main`이다(작업 브랜치를 만들지 않는다 — 발행 워크플로가 `main` 푸시로만 돈다).
  - **푸시 전에 `python -m unittest discover -s tests`를 돌려 통과한 것만 올린다.** 실패하면 올리지 않고 보고한다.
  - **`editorial/**`·`data/scoreboard.yaml`·`config/stock_pages.yaml` 같은 발행 트리거 경로가 섞였는지 먼저 본다**
    (`.github/workflows`의 `paths`). 섞였다면 그 커밋은 글을 공개시키므로, 의도한 발행이 아니면 나눠서 올린다.
  - 비밀값(`.env`, 토큰)과 `output/`·벤치마크 코퍼스는 어떤 경우에도 커밋하지 않는다.
  - 커밋 메시지는 무엇을 왜 바꿨는지 한국어 한 줄로 적는다.
