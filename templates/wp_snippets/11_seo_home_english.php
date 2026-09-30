<?php
// Code Snippets #11 원본 — 관리 화면에서 고치지 말고 이 파일을 고쳐 `python -m scripts.deploy_snippets`로 올린다.
// 2026-09-26. 필터 이름은 Rank Math 개발자 문서(rankmath.com/kb/filters-hooks-api-developer)와
// 워드프레스 코어(wp_sitemaps_posts_query_args, language_attributes)에서 확인한 것만 쓴다.

// 4번: 거의 빈 한국어 목록 페이지(한국어 글이 본진 비공개라 목록이 비었다)와 스레드 연결용 기술 페이지를
// 검색에서 뺀다. 탭 링크는 그대로 — 사람은 들어갈 수 있고 검색엔진만 등록하지 않는다.
function fermata_noindex_pages() {
	return array( 1047, 1610, 1439, 1604, 697, 698, 226 ); // checkpoint, guide(한국어), weekly, threads-callback, 한국어 소개·연락처·개인정보(2026-09-27 전수 점검 — 영어 사이트 사이트맵에 한국어 쪽이 있었다)
}
add_filter( 'rank_math/frontend/robots', function ( $robots ) {
	if ( is_page( fermata_noindex_pages() ) ) {
		$robots['index'] = 'noindex';
	}
	return $robots;
} );
add_filter( 'wp_sitemaps_posts_query_args', function ( $args, $post_type ) {
	if ( 'page' === $post_type ) {
		$old = isset( $args['post__not_in'] ) ? (array) $args['post__not_in'] : array();
		$args['post__not_in'] = array_merge( $old, fermata_noindex_pages() );
	}
	return $args;
}, 10, 2 );

// 3번: 공개 글은 전부 영어인데 홈 제목·설명·언어 표시가 한국어였다. 홈과 영어 목록 페이지(Daily 76·Guides 77·전체 105)를
// 영어로 표시한다. 관리자 화면 Rank Math '홈페이지' 칸에는 옛 한국어 값이 남아 있지만 이 조각이 덮어쓴다 —
// 홈 제목을 바꾸려면 이 조각의 문구를 고친다.
function fermata_is_english_listing() {
	return is_front_page() || is_home() || is_page( array( 76, 77, 105 ) );
}
function fermata_is_english_post() {
	if ( ! is_singular( 'post' ) ) {
		return false;
	}
	$post = get_post();
	return ( substr( $post->post_name, -3 ) === '-en' ) || has_category( 153, $post );
}
add_filter( 'rank_math/frontend/title', function ( $title ) {
	if ( is_front_page() || is_home() ) {
		return 'Korean Stocks in English: Prices, Foreign Flows & Guides | Fermata';
	}
	return $title;
} );
add_filter( 'rank_math/frontend/description', function ( $description ) {
	if ( is_front_page() || is_home() ) {
		return 'Every KOSPI and KOSDAQ stock in English: prices, foreign ownership and daily foreign flows, plus market notes and guides for foreign investors.';
	}
	return $description;
} );
add_filter( 'rank_math/opengraph/facebook/og_title', function ( $content ) {
	if ( is_front_page() || is_home() ) {
		return 'Korean Stocks in English: Prices, Foreign Flows & Guides | Fermata';
	}
	return $content;
} );
add_filter( 'rank_math/opengraph/facebook/og_description', function ( $content ) {
	if ( is_front_page() || is_home() ) {
		return 'Every KOSPI and KOSDAQ stock in English: prices, foreign ownership and daily foreign flows, plus market notes and guides for foreign investors.';
	}
	return $content;
} );
add_filter( 'rank_math/opengraph/facebook/og_locale', function ( $content ) {
	if ( fermata_is_english_listing() || fermata_is_english_post() ) {
		return 'en_US';
	}
	return $content;
} );
add_filter( 'language_attributes', function ( $output ) {
	if ( is_page( array( 697, 698, 226 ) ) ) {   // 남겨 둔 한국어 페이지는 한국어로 표시(2026-09-27)
		return preg_replace( '/lang="[^"]*"/', 'lang="ko"', $output );
	}
	if ( ! fermata_is_english_listing() ) {
		return $output;
	}
	return preg_replace( '/lang="[^"]*"/', 'lang="en"', $output );
} );

// 구글 서치콘솔 소유권 확인(URL 접두어 https://fermata.it.kr/, HTML 태그 방식, 2026-09-30).
// 소유권이 풀려 서치콘솔이 '이 속성에 액세스할 수 없습니다'를 냈다 — 태그를 지우면 다시 풀린다.
add_action( 'wp_head', function () {
	echo '<meta name="google-site-verification" content="JIeASdJsofbK9544PedRfBXTPt0Ps6bICTsmrUki38E" />' . "\n";
}, 1 );
