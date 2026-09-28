<?php
// Code Snippets #17 원본 — 관리 화면에서 고치지 말고 이 파일을 고쳐 `python -m scripts.deploy_snippets`로 올린다.
// 성능(2026-09-28 속도 점검): 워드프레스 기본 이모지 스크립트·스타일을 모든 화면에서 뺀다 — 쓰는 곳이 없고 화면마다 6KB 스크립트를 받았다.
// 워드프레스 코어 함수 이름 그대로(print_emoji_detection_script, print_emoji_styles).
remove_action( 'wp_head', 'print_emoji_detection_script', 7 );
remove_action( 'wp_print_styles', 'print_emoji_styles' );
add_filter( 'emoji_svg_url', '__return_false' );
