<?php
// Code Snippets #12 원본 — 관리 화면에서 고치지 말고 이 파일을 고쳐 `python -m scripts.deploy_snippets`로 올린다.
// 2026-09-26. 본진을 영어 사이트로 바꾸면서.
// 사이트 언어(ko_KR)와 태그라인을 REST 설정으로 바꾸면 200이 오고도 값이 그대로였다(date_format만 바뀜 — 원인은 확인하지 못했다).
// 그래서 **방문자 화면만** 영어로 보이게 한다. 관리자 화면·REST·AJAX는 그대로(관리자 계정 언어는 ko_KR).
// 워드프레스 코어 필터(locale, option_blogdescription)만 쓴다.
add_filter( 'locale', function ( $locale ) {
	if ( is_admin() || wp_doing_ajax() || ( defined( 'REST_REQUEST' ) && REST_REQUEST ) ) {
		return $locale;
	}
	return 'en_US';
} );
add_filter( 'option_blogdescription', function ( $value ) {
	if ( is_admin() ) {
		return $value;
	}
	return 'One beat, held at the close. Daily notes on the KOSPI and Wall Street.';
} );
