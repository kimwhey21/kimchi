<?php
// Code Snippets #9 원본 — 관리 화면에서 고치지 말고 이 파일을 고쳐 `python -m scripts.deploy_snippets`로 올린다.
add_action( 'wp_enqueue_scripts', function () {
	wp_enqueue_script(
		'fermata-adsense',
		'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-4531037537218466',
		array(), null, false
	);
} );

add_filter( 'script_loader_tag', function ( $tag, $handle ) {
	if ( 'fermata-adsense' === $handle ) {
		$tag = str_replace( ' src=', ' async crossorigin="anonymous" src=', $tag );
	}
	return $tag;
}, 10, 2 );
