<?php
/*
 * NinjaFirewall 설정 파일(.htninja) — 본진이 Cloudflare 뒤에 있을 때 방화벽이 실제 방문자 주소를 보게 한다 (2026-09-28).
 *
 * 둘 곳: 카페24 서버의 /kimwhey21/.htninja (웹사이트 폴더 /kimwhey21/www 의 한 칸 위 — 밖에서 열 수 없다).
 *        NinjaFirewall은 DOCUMENT_ROOT/.htninja 와 그 한 칸 위를 찾는다(플러그인 lib/firewall.php 50~51행).
 * 원본: 플러그인에 딸린 .htninja.sample의 Cloudflare 예시. 예시는 CF-Connecting-IP를 무조건 믿는데, 서버 주소로 직접 들어와
 *       가짜 머리를 보내면 속는다 — 그래서 요청이 **Cloudflare 주소에서 왔을 때만** 바꾼다.
 * Cloudflare 주소 목록: https://www.cloudflare.com/ips-v4 · ips-v6 (2026-09-28 받음). 목록이 바뀌면 여기도 고친다.
 */
$fermata_cf_ranges = array(
	'173.245.48.0/20', '103.21.244.0/22', '103.22.200.0/22', '103.31.4.0/22', '141.101.64.0/18', '108.162.192.0/18',
	'190.93.240.0/20', '188.114.96.0/20', '197.234.240.0/22', '198.41.128.0/17', '162.158.0.0/15', '104.16.0.0/13',
	'104.24.0.0/14', '172.64.0.0/13', '131.0.72.0/22',
	'2400:cb00::/32', '2606:4700::/32', '2803:f800::/32', '2405:b500::/32', '2405:8100::/32', '2a06:98c0::/29', '2c0f:f248::/32',
);
$fermata_in_range = function ( $ip, $cidr ) {
	list( $net, $bits ) = explode( '/', $cidr );
	$ip_bin = @inet_pton( $ip ); $net_bin = @inet_pton( $net );
	if ( false === $ip_bin || false === $net_bin || strlen( $ip_bin ) !== strlen( $net_bin ) ) { return false; }
	$bytes = intdiv( (int) $bits, 8 ); $rest = (int) $bits % 8;
	if ( substr( $ip_bin, 0, $bytes ) !== substr( $net_bin, 0, $bytes ) ) { return false; }
	if ( 0 === $rest ) { return true; }
	$mask = chr( ( 0xff << ( 8 - $rest ) ) & 0xff );
	return ( $ip_bin[ $bytes ] & $mask ) === ( $net_bin[ $bytes ] & $mask );
};
if ( ! empty( $_SERVER['HTTP_CF_CONNECTING_IP'] ) && filter_var( $_SERVER['HTTP_CF_CONNECTING_IP'], FILTER_VALIDATE_IP )
	&& ! empty( $_SERVER['REMOTE_ADDR'] ) ) {
	foreach ( $fermata_cf_ranges as $fermata_cidr ) {
		if ( $fermata_in_range( $_SERVER['REMOTE_ADDR'], $fermata_cidr ) ) {
			$_SERVER['REMOTE_ADDR'] = $_SERVER['HTTP_CF_CONNECTING_IP'];
			break;
		}
	}
}
