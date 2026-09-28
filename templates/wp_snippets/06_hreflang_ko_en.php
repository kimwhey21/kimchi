<?php
// Code Snippets #6 원본 — 관리 화면에서 고치지 말고 이 파일을 고쳐 `python -m scripts.deploy_snippets`로 올린다.
add_action( 'wp_head', function () {
	if ( ! is_singular( 'post' ) ) {
		return;
	}
	$post = get_post();
	$slug = $post->post_name;
	if ( substr( $slug, -3 ) === '-ko' ) {
		$self_lang = 'ko';
		$twin_slug = substr( $slug, 0, -3 ) . '-en';
		$twin_lang = 'en';
	} elseif ( substr( $slug, -3 ) === '-en' ) {
		$self_lang = 'en';
		$twin_slug = substr( $slug, 0, -3 ) . '-ko';
		$twin_lang = 'ko';
	} else {
		return;
	}
	$twin = get_page_by_path( $twin_slug, OBJECT, 'post' );
	if ( ! $twin || 'publish' !== $twin->post_status ) {
		return;
	}
	$self_url = get_permalink( $post );
	$twin_url = get_permalink( $twin );
	printf( '<link rel="alternate" hreflang="%s" href="%s" />' . "\n", $self_lang, esc_url( $self_url ) );
	printf( '<link rel="alternate" hreflang="%s" href="%s" />' . "\n", $twin_lang, esc_url( $twin_url ) );
	$default = ( 'ko' === $self_lang ) ? $self_url : $twin_url;
	printf( '<link rel="alternate" hreflang="x-default" href="%s" />' . "\n", esc_url( $default ) );
}, 5 );
