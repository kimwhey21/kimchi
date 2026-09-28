<?php
// Code Snippets #7 원본 — 관리 화면에서 고치지 말고 이 파일을 고쳐 `python -m scripts.deploy_snippets`로 올린다.
add_filter( 'language_attributes', function ( $output ) {
	if ( ! is_singular( 'post' ) ) {
		return $output;
	}
	$post = get_post();
	$is_en = ( substr( $post->post_name, -3 ) === '-en' ) || has_category( 153, $post );
	if ( ! $is_en ) {
		return $output;
	}
	return preg_replace( '/lang="[^"]*"/', 'lang="en"', $output );
} );
