<?php
// Code Snippets #10 원본 — 관리 화면에서 고치지 말고 이 파일을 고쳐 `python -m scripts.deploy_snippets`로 올린다.
add_filter( 'render_block', function ( $html, $block ) {
	// 영어 글에서 한국어 전용 블록 두 개를 감춘다 (2026-09-15).
	// 왜: 영어 가이드 아래에 한국어 텔레그램 안내와 한국어 시황 목록이 붙어 있었다.
	// 영어 독자에게 쓸모가 없고, 영어 페이지에 한글이 노출된다.
	// single 템플릿은 건드리지 않는다 - 이 스니펫을 끄면 그대로 돌아온다.
	if ( is_admin() || ! is_singular( 'post' ) ) {
		return $html;
	}
	$post = get_post();
	if ( ! $post ) {
		return $html;
	}
	// 언어 판정은 스니펫 #7(html lang)과 같은 규칙을 쓴다 - 한 곳만 고치면 되도록.
	// 2026-09-26부터 본진의 글은 전부 영어다(한국어 글은 올리지 않는다) — 모든 글에 적용한다. 전에는 slug가 -en이거나
	// 분류 153인 글만 골라, 둘 다 아닌 옛 영어 글 두 편에 한국어 텔레그램 안내가 남았다.
	$name = isset( $block['blockName'] ) ? $block['blockName'] : '';
	if ( 'core/html' === $name && false !== strpos( $html, 'fm-follow' ) ) {
		return '';
	}
	$meta    = isset( $block['attrs']['metadata'] ) ? $block['attrs']['metadata'] : array();
	$pattern = isset( $meta['patternName'] ) ? $meta['patternName'] : '';
	$label   = isset( $meta['name'] ) ? $meta['name'] : '';
	if ( 'core/group' === $name && ( 'twentytwentyfive/more-posts' === $pattern || '더 많은 게시물' === $label ) ) {
		return '';
	}
	return $html;
}, 10, 2 );
