<?php
// Code Snippets #8 원본 — 관리 화면에서 고치지 말고 이 파일을 고쳐 `python -m scripts.deploy_snippets`로 올린다.
add_action( 'init', function () {
	$uri = isset( $_SERVER['REQUEST_URI'] ) ? strtok( $_SERVER['REQUEST_URI'], '?' ) : '';
	if ( '/ads.txt' !== rtrim( $uri, '/' ) && '/ads.txt' !== $uri ) {
		return;
	}
	header( 'Content-Type: text/plain; charset=utf-8' );
	echo "google.com, pub-4531037537218466, DIRECT, f08c47fec0942fa0\n";
	exit;
}, 0 );
