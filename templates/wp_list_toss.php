<?php
// 본진 홈·목록 토스피드 A안 3색 판 + 목록용 정사각 썸네일 (2026-09-27, 사장님 "썸네일 4번 3색판으로 가자").
// 이 파일이 원본이다 — 워드프레스 Code Snippets 14번에 `python -m scripts.deploy_list_style`로 올린다(관리 화면에서 고치지 말 것).
// 하는 일 셋: 1) 글 메타 fermata_square_thumb(정사각 썸네일 미디어 id)를 REST에 연다(발행 코드가 적는다)
// 2) 목록 화면에서만 대표 이미지 옆에 네모 그림을 끼운다(가로 표지는 공유·디스커버용으로 그대로) 3) 목록 화면에만 스타일.
// 되돌리기: 이 조각을 끄면 홈·목록이 예전 모습으로 돌아간다(분류·메타는 남아도 해가 없다).

add_action( 'init', function () {
	register_post_meta( 'post', 'fermata_square_thumb', array(
		'type'          => 'integer',
		'single'        => true,
		'default'       => 0,
		'show_in_rest'  => true,
		'auth_callback' => function () { return current_user_can( 'edit_posts' ); },
	) );
} );

function fermata_list_view() {
	return is_front_page() || is_home() || is_page( array( 76, 77, 105, 'stocks' ) ) || is_category() || is_tag() || is_search();   // stocks: 종목 데이터베이스(2026-09-27) — 메뉴 네 화면의 배경·글꼴을 같게
}

add_filter( 'render_block_core/post-featured-image', function ( $html, $block, $instance ) {
	if ( is_admin() || ! fermata_list_view() || '' === $html ) {
		return $html;
	}
	$post_id = isset( $instance->context['postId'] ) ? (int) $instance->context['postId'] : 0;
	$square  = $post_id ? (int) get_post_meta( $post_id, 'fermata_square_thumb', true ) : 0;
	if ( ! $square ) {
		return $html;
	}
	$url = wp_get_attachment_image_url( $square, 'medium' );
	if ( ! $url ) {
		$url = wp_get_attachment_image_url( $square, 'full' );
	}
	if ( ! $url ) {
		return $html;
	}
	$img  = sprintf( '<img class="fm-sq" src="%s" alt="" width="300" height="300" loading="lazy" decoding="async">', esc_url( $url ) );
	$html = preg_replace( '/(<img\b[^>]*>)/', '$1' . $img, $html, 1 );
	return preg_replace( '/class="wp-block-post-featured-image/', 'class="wp-block-post-featured-image has-fm-sq', $html, 1 );
}, 10, 3 );

add_action( 'wp_head', function () {
	if ( ! fermata_list_view() ) {
		return;
	}
	echo '<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">' . "\n";
	echo '<style id="fermata-list-toss">' . FERMATA_LIST_CSS . '</style>' . "\n";
}, 20 );

const FERMATA_LIST_CSS = <<<'CSS'
:root{--fa-ink:#191f28;--fa-sub:#4e5968;--fa-mute:#8b95a1;--fa-line:#eef0f3;--fa-pill:#f2f4f6}
body{background:#fff!important;font-family:Pretendard,-apple-system,"Segoe UI",sans-serif!important;color:var(--fa-ink)}
header .wp-block-site-title a{font-family:Pretendard,sans-serif!important;letter-spacing:.02em;color:var(--fa-ink)!important}
header .wp-block-site-tagline{font-family:Pretendard,sans-serif!important;color:var(--fa-mute)!important;font-size:14px!important}
/* 탭 → 알약 */
main div[style*="flex-wrap:wrap"]{gap:8px!important}
main div[style*="flex-wrap:wrap"]>a{background:var(--fa-pill);border:0!important;border-radius:999px;padding:9px 16px!important;
  font:600 14px/1 Pretendard,sans-serif!important;color:var(--fa-sub)!important;text-decoration:none!important}
main div[style*="flex-wrap:wrap"]>a[style*="font-weight:700"],
.page-id-77 main div[style*="flex-wrap:wrap"]>a[href="/guides/"]{background:var(--fa-ink);color:#fff!important}
/* Guides 목록(77)만 탭 줄에 "지금 보는 탭" 표시가 빠져 있다(원래부터) — 페이지 본문 대신 여기서 칠한다 */
main div[style*="border-bottom-width:1px"]{border-bottom-color:var(--fa-line)!important}
/* 메뉴 네 화면(홈·Stocks·Daily·Guides)의 메뉴 줄 높이를 같게 — 일반 페이지 틀은 본문 위에 70px 빈칸을 더 둬서
   메뉴가 홈보다 89px 아래에 있었다(2026-09-27 실측 272·319·361). 홈과 같은 자리로 올린다 */
body.page main>.wp-block-group.alignfull:first-child{padding-top:0!important}
body.page .wp-block-post-content>div.wp-block-group:first-of-type{margin-top:0!important}   /* 본문 맨 앞에 style 태그가 있어 :first-child가 안 걸린다 */
/* 글 목록: 글자 왼쪽, 네모 썸네일 오른쪽, 두 줄 */
.wp-block-post-template.is-layout-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:36px 56px!important}
.wp-block-post-template>li>.wp-block-group{display:grid!important;grid-template-columns:minmax(0,1fr) 124px;column-gap:22px;
  grid-template-areas:"label thumb" "title thumb" "snip thumb" "meta thumb";grid-template-rows:auto auto auto 1fr;align-items:start;padding-bottom:0!important}
.wp-block-post-template>li>.wp-block-group>*{margin:0!important}
.wp-block-post-template>li .wp-block-post-featured-image{grid-area:thumb;width:112px;height:112px;margin:6px!important;border-radius:20px;overflow:hidden;
  box-shadow:0 0 0 6px var(--tile,#f2f4f6)}
.wp-block-post-template>li .wp-block-post-featured-image img{aspect-ratio:1/1!important;object-fit:cover;object-position:center;border-radius:0!important;width:100%;height:100%}
/* 정사각 썸네일이 있는 글: 목록에서는 네모 그림, 첫 글(큰 카드)은 가로 표지 */
.wp-block-post-template>li:not(:first-child) .has-fm-sq img.wp-post-image,.wp-block-post-template>li:first-child img.fm-sq{display:none!important}
/* 네모 그림이 없는 글(옛 글·사진 표지): 가로 표지를 틀 안에 통째로 */
.wp-block-post-template>li:not(:first-child) .wp-block-post-featured-image:not(.has-fm-sq){background:var(--tile,#f2f4f6)}
.wp-block-post-template>li:not(:first-child) .wp-block-post-featured-image:not(.has-fm-sq) a{display:flex;align-items:center;height:100%}
.wp-block-post-template>li:not(:first-child) .wp-block-post-featured-image:not(.has-fm-sq) img{aspect-ratio:1200/630!important;object-fit:contain!important;height:auto!important;border-radius:6px!important}
.wp-block-post-template>li .has-accent-4-color{grid-area:label}
.wp-block-post-template>li .wp-block-post-title{grid-area:title;margin-top:8px!important}
.wp-block-post-template>li .wp-block-post-title a{font:700 19px/1.4 Pretendard,sans-serif!important;color:var(--fa-ink)!important;letter-spacing:-.01em;text-decoration:none}
.wp-block-post-template>li .wp-block-post-excerpt{grid-area:snip;margin-top:6px!important}
.wp-block-post-template>li .wp-block-post-excerpt p{font:400 15px/1.6 Pretendard,sans-serif!important;color:var(--fa-sub);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;margin:0}
.wp-block-post-template>li .wp-block-post-date{grid-area:meta;margin-top:12px!important}
.wp-block-post-template>li .wp-block-post-date a{font:400 13px Pretendard,sans-serif!important;color:var(--fa-mute)!important;text-decoration:none}
/* 코너 이름표(알약) */
.wp-block-post-terms a{display:inline-block;font:700 12.5px/1 Pretendard,sans-serif!important;padding:6px 10px;border-radius:999px;
  background:var(--lb,#f2f4f6);color:var(--lf,#4e5968)!important;text-decoration:none!important}
li.category-guides{--lb:#e7f5ff;--lf:#1864ab;--tile:#e7f5ff}
li.category-daily,li.category-korea-close{--lb:#e9f8ec;--lf:#2b8a3e;--tile:#e9f8ec}
li.category-wall-street-close{--lb:#fff0e5;--lf:#d9480f;--tile:#fff0e5}
/* 시황은 Daily와 하위 분류를 함께 단다 — 이름표는 하위 분류(한국장·미국장) 하나만 보인다 */
.wp-block-post-terms__separator{display:none}
.wp-block-post-terms:has(a[href*="/korea-close/"]) a[href$="/category/daily/"],
.wp-block-post-terms:has(a[href*="/wall-street-close/"]) a[href$="/category/daily/"]{display:none}
/* 첫 글: 파랑→보라 카드, 큰 그림 왼쪽 */
.wp-block-post-template>li:first-child{grid-column:1/-1}
.wp-block-post-template>li:first-child>.wp-block-group{background:linear-gradient(135deg,#eef4ff 0%,#f4efff 100%);border-radius:28px;padding:28px!important;
  grid-template-columns:minmax(0,1.15fr) minmax(0,1fr)!important;column-gap:36px;
  grid-template-areas:"thumb label" "thumb title" "thumb snip" "thumb meta" "thumb .";grid-template-rows:auto auto auto auto 1fr}
.wp-block-post-template>li:first-child .wp-block-post-featured-image{width:auto;height:auto;margin:0!important;box-shadow:none;border-radius:18px;align-self:center}
.wp-block-post-template>li:first-child .wp-block-post-featured-image img{aspect-ratio:1200/630!important;object-position:center;object-fit:cover!important;height:auto}
.wp-block-post-template>li:first-child .wp-block-post-featured-image{grid-row:1/-1}
.wp-block-post-template>li:first-child .has-accent-4-color{margin-top:18px!important}
.wp-block-post-template>li:first-child .wp-block-post-title a{font-size:30px!important;line-height:1.3}
.wp-block-post-template>li:first-child .wp-block-post-excerpt p{-webkit-line-clamp:4}
.wp-block-post-template>li:nth-child(2)::before{content:"Latest";display:block;font:800 24px Pretendard,sans-serif;color:var(--fa-ink);margin:0 0 22px}
.wp-block-post-template>li:nth-child(3)::before{content:"\00a0";display:block;font:800 24px Pretendard,sans-serif;margin:0 0 22px}
.wp-block-query-pagination a,.wp-block-query-pagination .current{border-radius:999px;padding:6px 12px;font-family:Pretendard,sans-serif}
.wp-block-query-pagination-next,.wp-block-query-pagination-previous{background:#3182f6;color:#fff!important;border-radius:999px;padding:8px 16px}
@media (max-width:781px){
  .wp-block-post-template.is-layout-grid{grid-template-columns:1fr!important;gap:30px!important}
  .wp-block-post-template>li>.wp-block-group{grid-template-columns:minmax(0,1fr) 94px;column-gap:14px}
  .wp-block-post-template>li .wp-block-post-featured-image{width:84px;height:84px;border-radius:16px;box-shadow:0 0 0 5px var(--tile,#f2f4f6)}
  .wp-block-post-template>li .wp-block-post-title a{font-size:17px!important}
  .wp-block-post-template>li .wp-block-post-excerpt p{font-size:14px!important}
  .wp-block-post-template>li:first-child>.wp-block-group{grid-template-columns:1fr!important;grid-template-areas:"thumb" "label" "title" "snip" "meta";grid-template-rows:auto!important;padding:16px 16px 22px!important;border-radius:22px}
  .wp-block-post-template>li:first-child .wp-block-post-featured-image{margin:0 0 14px!important;grid-row:auto}
  .wp-block-post-template>li:first-child .has-accent-4-color{margin-top:0!important}
  .wp-block-post-template>li:first-child .wp-block-post-title a{font-size:22px!important}
  .wp-block-post-template>li:nth-child(3)::before{display:none}
  main div[style*="flex-wrap:wrap"]>a{padding:7px 13px!important;font-size:13px!important}
}
CSS;
