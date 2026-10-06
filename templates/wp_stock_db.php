<?php
// 본진 한국 종목 데이터베이스 — /stocks/ 목록, /stocks/<종목코드>/ 종목 페이지, 홈의 검색창·시장 띠·카드 (2026-09-27).
// 이 파일이 원본이다 — `python -m scripts.deploy_stock_db`로 Code Snippets에 올린다(관리 화면에서 고치지 말 것).
// 데이터는 `python -m src.stock_db run --push`(깃허브 액션, 매일 장 마감 뒤)가 REST로 넣는다:
//   fm_s_<code>      종목 하나(시세 q, 지표 r, 컨센서스 c, 5일 수급 flows, 재무 fin, 이력 hist, 동종 peers)
//   fm_stock_index   [[code, name, market, close, pct, mcap], ...] 시가총액 순 — 목록·검색
//   fm_market        홈의 시장 띠·카드
// 종목 3,900여 개를 글·페이지로 만들지 않는다(카페24 공유 호스팅) — 실제 페이지는 slug `stocks` 하나이고 주소를 받아 그 자리에서 그린다.

if ( ! defined( 'ABSPATH' ) ) { return; }

const FS_GUIDE_DEFAULT = '/how-foreigners-can-now-buy-korean-stocks-without-a-korean-brokerage-account/';
const FS_GUIDES = array(
	'005930' => '/how-to-buy-samsung-electronics-abroad/',
	'005935' => '/how-to-buy-samsung-electronics-abroad/',
	'000660' => '/sk-hynix-vs-micron/',
);

// ── 숫자 모양 ────────────────────────────────────────────────────────────────────────
function fs_esc( $s ) { return htmlspecialchars( (string) $s, ENT_QUOTES, 'UTF-8' ); }
function fs_krw( $v, $dec = 0 ) { return ( $v === null || $v === '' ) ? '–' : ( (float) $v < 0 ? '−' : '' ) . '₩' . number_format( abs( (float) $v ), $dec ); }
function fs_big( $krw ) {
	if ( $krw === null || $krw === '' ) { return '–'; }
	$v = (float) $krw; $sign = $v < 0 ? '−' : ''; $a = abs( $v );
	if ( $a >= 1e12 ) { return $sign . '₩' . number_format( $a / 1e12, 1 ) . 'T'; }
	if ( $a >= 1e9 )  { return $sign . '₩' . number_format( $a / 1e9, 1 ) . 'B'; }
	if ( $a >= 1e6 )  { return $sign . '₩' . number_format( $a / 1e6, 1 ) . 'M'; }
	return $sign . '₩' . number_format( $a );
}
function fs_eok( $eok ) { return ( $eok === null || $eok === '' ) ? '–' : fs_big( (float) $eok * 1e8 ); }
function fs_pct( $v, $bold = true ) {
	if ( $v === null || $v === '' ) { return '–'; }
	$v = (float) $v; $cls = $v > 0 ? 'fs-up' : ( $v < 0 ? 'fs-dn' : 'fs-fl' );
	$txt = ( $v > 0 ? '+' : ( $v < 0 ? '−' : '' ) ) . number_format( abs( $v ), 2 ) . '%';
	return $bold ? "<b class=\"$cls\">$txt</b>" : "<span class=\"$cls\">$txt</span>";
}
function fs_signed( $v ) {
	if ( $v === null || $v === '' ) { return '–'; }
	$v = (float) $v; $cls = $v > 0 ? 'fs-up' : ( $v < 0 ? 'fs-dn' : 'fs-fl' );
	return "<span class=\"$cls\">" . ( $v > 0 ? '+' : ( $v < 0 ? '−' : '' ) ) . number_format( abs( $v ) ) . '</span>';
}
function fs_x( $v, $suffix = '' ) { return ( $v === null || $v === '' ) ? '–' : ( (float) $v < 0 ? '−' : '' ) . number_format( abs( (float) $v ), 2 ) . $suffix; }
function fs_date( $d ) { $t = strtotime( (string) $d ); return $t ? date( 'M j, Y', $t ) : '–'; }
function fs_rating( $r ) {
	if ( $r === null || $r === '' ) { return '–'; }
	$r = (float) $r;
	$label = $r >= 4.5 ? 'Strong buy' : ( $r >= 3.5 ? 'Buy' : ( $r >= 2.5 ? 'Hold' : ( $r >= 1.5 ? 'Sell' : 'Strong sell' ) ) );
	return number_format( $r, 2 ) . ' · ' . $label;
}

// ── 조각들 ───────────────────────────────────────────────────────────────────────────
// 메뉴 네 화면(Market·Stocks·Daily·Guides)의 메뉴 줄은 여기 한 곳에서만 그린다(2026-09-27 구조 통일) — 홈 템플릿과
// 'fermata-hub' 틀이 [fermata_nav]로 부른다. 지금 어느 화면인지는 스스로 안다($active가 비면).
function fs_nav( $active = '' ) {
	if ( '' === $active && function_exists( 'is_front_page' ) ) {
		// 글·분류 화면도 자기 갈래를 칠한다(2026-09-28 템플릿 통일) — 시황 121·684·685는 Daily, 가이드 153은 Guides
		$daily = array( 121, 684, 685 );
		$in = function ( $cats ) { return is_category( $cats ) || ( is_singular( 'post' ) && in_category( $cats ) ); };
		$active = is_front_page() ? 'market' : ( is_page( 'stocks' ) ? 'stocks' : ( ( is_page( 76 ) || $in( $daily ) ) ? 'daily' : ( ( is_page( 77 ) || $in( array( 153 ) ) ) ? 'guides' : '' ) ) );
	}
	$items = array( 'market' => array( '/', 'Market' ), 'stocks' => array( '/stocks/', 'Stocks' ),
	                'daily' => array( '/daily/', 'Daily' ), 'guides' => array( '/guides/', 'Guides' ) );
	$out = '<div class="fs-navwrap"><div style="display:flex;flex-wrap:wrap;gap:12px 20px">';
	foreach ( $items as $key => $it ) {
		$style = $key === $active ? 'white-space:nowrap;font-weight:700;border-bottom:2px solid #e34948;padding-bottom:6px'
		                          : 'white-space:nowrap;padding-bottom:6px';
		$out .= '<a href="' . $it[0] . '" style="' . $style . '">' . $it[1] . '</a>';
	}
	return $out . '</div></div>';
}

function fs_search_box( $count = null ) {
	$GLOBALS['fs_need_search_js'] = true;
	$ph = 'Search ' . ( $count ? number_format( $count ) . ' ' : '' ) . 'Korean stocks';   // 긴 예시는 휴대폰에서 잘렸다(2026-09-27) — 예시는 aria 설명으로
	$src = function_exists( 'wp_upload_dir' ) ? fs_index_url() : '/wp-json/fermata/v1/stock-index';
	return '<div class="fs-search"><span aria-hidden="true">⌕</span><input type="search" id="fs-q" autocomplete="off" data-src="' . fs_esc( $src ) . '" placeholder="'
		. fs_esc( $ph ) . '" aria-label="Search Korean stocks by name or code, e.g. Samsung, SK Hynix, 005930"><kbd>/</kbd><ul id="fs-res" hidden></ul></div>';
}

function fs_chart( $hist ) {
	$c = isset( $hist['c'] ) ? array_values( array_filter( $hist['c'], 'is_numeric' ) ) : array();
	$n = count( $c );
	if ( $n < 5 ) { return ''; }
	$fr = isset( $hist['fr'] ) ? $hist['fr'] : array();
	$d  = $hist['d'];
	$W = 640; $H = 220; $L = 8; $R = 52; $T = 16; $B = 26;
	$mn = min( $c ); $mx = max( $c ); if ( $mx == $mn ) { $mx = $mn + 1; }
	$x = function ( $i ) use ( $n, $W, $L, $R ) { return $L + ( $W - $L - $R ) * $i / max( 1, $n - 1 ); };
	$y = function ( $v ) use ( $mn, $mx, $H, $T, $B ) { return $T + ( $H - $T - $B ) * ( 1 - ( $v - $mn ) / ( $mx - $mn ) ); };
	$pts = array(); foreach ( $c as $i => $v ) { $pts[] = round( $x( $i ), 1 ) . ',' . round( $y( $v ), 1 ); }
	$up = end( $c ) >= $c[0];
	$col = $up ? 'var(--fs-up)' : 'var(--fs-dn)';
	$area = round( $x( 0 ), 1 ) . ',' . ( $H - $B ) . ' ' . implode( ' ', $pts ) . ' ' . round( $x( $n - 1 ), 1 ) . ',' . ( $H - $B );
	$svg = '<svg viewBox="0 0 ' . $W . ' ' . $H . '" class="fs-chart" role="img" aria-label="Closing price and foreign ownership, last ' . $n . ' trading days">'
		. '<polygon points="' . $area . '" fill="' . $col . '" opacity=".08"/><polyline points="' . implode( ' ', $pts ) . '" fill="none" stroke="' . $col . '" stroke-width="2.2"/>';
	$frv = array_values( array_filter( $fr, 'is_numeric' ) );
	if ( count( $frv ) === $n ) {
		$fmn = min( $frv ); $fmx = max( $frv ); if ( $fmx - $fmn < 0.5 ) { $fmn -= 0.25; $fmx += 0.25; }
		$fp = array(); foreach ( $frv as $i => $v ) { $fp[] = round( $x( $i ), 1 ) . ',' . round( $T + ( $H - $T - $B ) * ( 1 - ( $v - $fmn ) / ( $fmx - $fmn ) ), 1 ); }
		$svg .= '<polyline points="' . implode( ' ', $fp ) . '" fill="none" stroke="var(--fs-green)" stroke-width="1.6" stroke-dasharray="4 3"/>'
			. '<text x="' . ( $W - 4 ) . '" y="' . ( $T + 2 ) . '" class="fs-ax" text-anchor="end">' . number_format( $fmx, 1 ) . '%</text>'
			. '<text x="' . ( $W - 4 ) . '" y="' . ( $H - $B ) . '" class="fs-ax" text-anchor="end">' . number_format( $fmn, 1 ) . '%</text>';
	}
	$svg .= '<text x="' . $L . '" y="' . ( $H - 6 ) . '" class="fs-ax">' . fs_date( $d[ count( $d ) - $n ] ) . '</text>'
		. '<text x="' . ( $W - $R ) . '" y="' . ( $H - 6 ) . '" class="fs-ax" text-anchor="end">' . fs_date( end( $d ) ) . '</text>'
		. '<text x="' . $L . '" y="' . ( $T - 4 ) . '" class="fs-ax">High ' . fs_krw( $mx ) . ' · Low ' . fs_krw( $mn ) . '</text></svg>';
	return $svg . '<p class="fs-legend"><span class="fs-key" style="background:' . $col . '"></span>Close (KRW) <span class="fs-key fs-dash"></span>Foreign ownership, % of shares (right axis)</p>';
}

// 외국인 지분율 — 네이버 '외인소진율'(foreign_ratio)은 한도 대비 사용률이라 한도가 있는 종목에서 지분율과 다르다
// (2026-09-28: KT가 100%로 나왔다 — 실제 지분 49.0%, 한도 49%를 다 채운 것). 실제 지분은 차트 이력(foreignRetentionRate)·5일 수급의 보유율.
function fs_foreign_own( $s ) {
	$fr = isset( $s['hist']['fr'] ) ? array_values( array_filter( $s['hist']['fr'], 'is_numeric' ) ) : array();
	if ( $fr ) { return (float) end( $fr ); }
	if ( ! empty( $s['flows'][0]['fratio'] ) ) { return (float) $s['flows'][0]['fratio']; }
	return null;   // 소진율은 지분율로 쓰지 않는다
}
function fs_foreign_cell( $s ) {
	$own = fs_foreign_own( $s );
	if ( null === $own ) { return '–'; }
	$used = isset( $s['r']['foreign_ratio'] ) ? $s['r']['foreign_ratio'] : null;
	$cell = fs_x( $own, '%' );
	if ( null !== $used && abs( (float) $used - $own ) > 1 ) {   // 외국인 한도가 있는 종목(통신·전력·항공 등)
		$cell .= '<br><span class="fs-mute fs-small">' . number_format( (float) $used, 0 ) . '% of foreign limit used</span>';
	}
	return $cell;
}

function fs_stock_html( $s, $index_by_code, $related = array(), $lists = array(), $skhy = null ) {
	$code = $s['code']; $name = $s['name']; $q = isset( $s['q'] ) ? $s['q'] : array();
	$r = isset( $s['r'] ) ? $s['r'] : array(); $c = isset( $s['c'] ) ? $s['c'] : array();
	$guide = isset( FS_GUIDES[ $code ] ) ? FS_GUIDES[ $code ] : FS_GUIDE_DEFAULT;
	$common = substr( $code, 0, 5 ) . '0';
	$pref_of = ( ! empty( $s['pref'] ) && $common !== $code && isset( $index_by_code[ $common ] ) ) ? $common : '';
	$mkt = $s['market'] === 'KOSDAQ' ? 'KOSDAQ' : 'KOSPI';
	$h  = '<nav class="fs-crumb"><a href="/stocks/">Stocks</a> › <a href="/stocks/?m=' . strtolower( $mkt ) . '">' . $mkt . '</a> › ' . fs_esc( $name ) . '</nav>';
	$h .= '<div class="fs-head"><div><h1>' . fs_esc( $name ) . '</h1><div class="fs-tick">KRX: ' . fs_esc( $code ) . ' · ' . $mkt
		. ( ! empty( $s['industry'] ) ? ' · ' . fs_esc( $s['industry'] ) : '' ) . '</div>'
		. '<div class="fs-price">' . fs_krw( isset( $q['close'] ) ? $q['close'] : null ) . ' <small>' . fs_signed( isset( $q['chg'] ) ? $q['chg'] : null ) . ' (' . fs_pct( isset( $q['pct'] ) ? $q['pct'] : null, false ) . ')</small></div>'
		. '<div class="fs-mute">At close: ' . fs_date( isset( $q['date'] ) ? $q['date'] : '' ) . ' · KRW · Korea Exchange</div></div>'
		. '<div class="fs-btns"><a class="fs-btn" href="' . $guide . '">How to buy from abroad →</a></div></div>';
	// 이동 버튼은 그 칸이 있을 때만 — 재무·동종이 없는 종목에서 눌러도 아무 데도 안 가던 버튼이 14종목에 있었다(2026-09-27 전수 점검)
	$chart = fs_chart( isset( $s['hist'] ) ? $s['hist'] : array() );
	$peers = array_values( array_filter( isset( $s['peers'] ) ? $s['peers'] : array(), function ( $p ) use ( $index_by_code ) { return isset( $index_by_code[ $p['code'] ] ); } ) );   // 목록에 없는 종목(ETF 등)은 404라 뺀다
	$tabs = array( 'overview' => 'Overview' );
	if ( $chart ) { $tabs['chart'] = 'Chart'; }
	if ( ! empty( $s['flows'] ) ) { $tabs['flows'] = 'Foreign flows'; }
	if ( ! empty( $s['fin']['cols'] ) ) { $tabs['financials'] = 'Financials'; }
	if ( $peers ) { $tabs['peers'] = 'Peers'; }
	$tabs['about'] = 'About';
	$h .= fs_in_lists( $code, $lists );
	if ( '000660' === $code && $skhy ) {
		$lp = $skhy['rows'][ count( $skhy['rows'] ) - 1 ]['prem'];
		$h .= '<div class="fs-inlists"><a href="/stocks/skhy-premium/">Also on the Nasdaq as SKHY: ' . ( $lp >= 0 ? '+' : '−' ) . number_format( abs( $lp ), 1 ) . '% vs Seoul →</a></div>';
	}
	$h .= '<div class="fs-tabs">';
	foreach ( $tabs as $id => $label ) { $h .= '<a href="#' . $id . '">' . $label . '</a>'; }
	$h .= '</div>';
	$rows1 = array(
		array( 'Market cap', fs_big( isset( $q['mcap'] ) ? $q['mcap'] : null ) ),
		array( 'PE ratio', fs_x( isset( $r['per'] ) ? $r['per'] : null ) ),
		array( 'Forward PE', fs_x( isset( $r['fper'] ) ? $r['fper'] : null ) ),
		array( 'PB ratio', fs_x( isset( $r['pbr'] ) ? $r['pbr'] : null ) ),
		array( 'EPS', fs_krw( isset( $r['eps'] ) ? $r['eps'] : null ) ),
		array( 'Dividend (yield)', ( isset( $r['dps'] ) && $r['dps'] !== null ? fs_krw( $r['dps'] ) . ' (' . fs_x( isset( $r['div_yield'] ) ? $r['div_yield'] : null, '%' ) . ')' : '–' ) ),
		// 우선주 화면의 컨센서스는 보통주 것이다 — 우선주 값과 비교하면 +290%처럼 틀린 숫자가 된다(2026-09-27 전수 점검, 005387)
		$pref_of ? array( 'Analysts (1–5)', 'See <a href="/stocks/' . $pref_of . '/">common shares</a>' )
		         : array( 'Analysts (1–5)', fs_rating( isset( $c['rating'] ) ? $c['rating'] : null ) ),
		$pref_of ? array( 'Price target', 'See <a href="/stocks/' . $pref_of . '/">common shares</a>' )
		         : array( 'Price target', ( ! empty( $c['target'] ) && ! empty( $q['close'] ) ) ? fs_krw( $c['target'] ) . ' (' . fs_pct( ( $c['target'] / $q['close'] - 1 ) * 100, false ) . ')' : '–' ),
	);
	$last_flow = ! empty( $s['flows'] ) ? $s['flows'][0] : null;
	$rows2 = array(
		array( 'Volume', ( isset( $q['volume'] ) && $q['volume'] !== null ) ? number_format( $q['volume'] ) : '–' ),
		array( 'Trading value', fs_big( isset( $q['value'] ) ? $q['value'] : null ) ),
		// 당일 범위는 매일 받는 시세(q, KRX 정규장)에서만 — 상세(r)의 고가·저가는 넥스트레이드 합산이고 7일에 한 번만 새로 받는다(2026-10-06)
		array( 'Day’s range', ( ! empty( $q['dlow'] ) && ! empty( $q['dhigh'] ) ) ? fs_krw( $q['dlow'] ) . ' – ' . fs_krw( $q['dhigh'] ) : '–' ),
		// 액면병합 뒤 52주 값이 조정되지 않은 종목이 있다(009310: 가격 5,330 vs 864~1,705) — 가격과 모순되면 숨긴다
		array( '52-week range', ( ! empty( $r['low52'] ) && ! empty( $r['high52'] ) && ! empty( $q['close'] ) && $q['close'] >= $r['low52'] * 0.7 && $q['close'] <= $r['high52'] * 1.3 ) ? fs_krw( $r['low52'] ) . ' – ' . fs_krw( $r['high52'] ) : '–' ),
		array( 'Foreign ownership <span class="fs-kr">KR</span>', fs_foreign_cell( $s ) ),
		array( 'Foreign net buy' . ( $last_flow ? ' (' . date( 'M j', strtotime( $last_flow['d'] ) ) . ')' : '' ) . ' <span class="fs-kr">KR</span>',
		       $last_flow && $last_flow['foreign'] !== null ? fs_signed( $last_flow['foreign'] ) . ' sh' : '–' ),
		array( 'Book value / share', fs_krw( isset( $r['bps'] ) ? $r['bps'] : null ) ),
		array( 'Founded', ! empty( $s['founded'] ) ? fs_esc( $s['founded'] ) : '–' ),
	);
	$tbl = function ( $rows ) { $o = '<table class="fs-kv">'; foreach ( $rows as $x ) { $o .= '<tr><td>' . $x[0] . '</td><td>' . $x[1] . '</td></tr>'; } return $o . '</table>'; };
	$h .= '<section id="overview" class="fs-two"><div class="fs-stats">' . $tbl( $rows1 ) . $tbl( $rows2 ) . '</div>'
		. ( $chart ? '<div id="chart">' . $chart . '</div>' : '<div></div>' ) . '</section>';
	if ( ! empty( $s['flows'] ) ) {
		$h .= '<section id="flows" class="fs-sec"><h2>Foreign, institutional and retail net buying <span class="fs-kr">KR data</span></h2>'
			. '<p class="fs-note">Shares by trading day; positive means net buying. Korea publishes investor-type flows for every stock — global sites such as Yahoo or StockAnalysis do not show them.</p>'
			. '<div class="fs-scroll"><table class="fs-t"><tr><th>Date</th><th class="fs-num">Close</th><th class="fs-num">Foreigners</th><th class="fs-num">Institutions</th><th class="fs-num">Retail</th><th class="fs-num">Foreign ownership</th></tr>';
		foreach ( $s['flows'] as $f ) {
			$h .= '<tr><td>' . date( 'M j', strtotime( $f['d'] ) ) . '</td><td class="fs-num">' . fs_krw( $f['close'] ) . '</td><td class="fs-num">' . fs_signed( $f['foreign'] )
				. '</td><td class="fs-num">' . fs_signed( $f['inst'] ) . '</td><td class="fs-num">' . fs_signed( $f['retail'] ) . '</td><td class="fs-num">' . fs_x( $f['fratio'], '%' ) . '</td></tr>';
		}
		$h .= '</table></div></section>';
	}
	if ( ! empty( $s['fin']['cols'] ) ) {
		$fin = $s['fin']; $labels = array( 'revenue' => 'Revenue', 'op' => 'Operating income', 'net' => 'Net income', 'opm' => 'Operating margin',
			'roe' => 'Return on equity', 'debt' => 'Debt-to-equity', 'eps' => 'EPS', 'dps' => 'Dividend per share' );
		$h .= '<section id="financials" class="fs-sec"><h2>Financials</h2><p class="fs-note">Annual, consolidated where available, KRW. Columns ending in E are analyst consensus estimates. Source: company filings (DART) via Naver Finance.</p>'
			. '<div class="fs-scroll"><table class="fs-t"><tr><th>Item</th>';
		foreach ( $fin['cols'] as $col ) { $h .= '<th class="fs-num">' . fs_esc( $col ) . '</th>'; }
		$h .= '</tr>';
		foreach ( $labels as $key => $label ) {
			if ( empty( $fin['rows'][ $key ] ) ) { continue; }
			$h .= '<tr><td>' . $label . '</td>';
			foreach ( $fin['rows'][ $key ] as $v ) {
				if ( in_array( $key, array( 'revenue', 'op', 'net' ), true ) ) { $cell = fs_eok( $v ); }
				elseif ( in_array( $key, array( 'eps', 'dps' ), true ) ) { $cell = fs_krw( $v ); }
				else { $cell = fs_x( $v, '%' ); }
				$h .= '<td class="fs-num">' . $cell . '</td>';
			}
			$h .= '</tr>';
		}
		$h .= '</table></div></section>';
	}
	$h .= '<div class="fs-two fs-sec">';
	if ( $peers ) {
		$h .= '<section id="peers"><h2>Peers</h2><table class="fs-t">';
		foreach ( $peers as $p ) {
			$i = isset( $index_by_code[ $p['code'] ] ) ? $index_by_code[ $p['code'] ] : null;
			$h .= '<tr><td><a href="/stocks/' . fs_esc( $p['code'] ) . '/"><b>' . fs_esc( $p['name'] ) . '</b></a> <span class="fs-code">' . fs_esc( $p['code'] ) . '</span></td>'
				. '<td class="fs-num">' . ( $i ? fs_krw( $i[3] ) : '–' ) . '</td><td class="fs-num">' . ( $i ? fs_pct( $i[4] ) : '–' ) . '</td></tr>';
		}
		$h .= '</table></section>';
	}
	$about = fs_esc( ! empty( $s['en'] ) ? $s['en'] : $name ) . ' is listed on the ' . $mkt . ' market of the Korea Exchange under the ticker ' . fs_esc( $code ) . '.'
		. ( ! empty( $s['industry'] ) ? ' Industry: ' . fs_esc( $s['industry'] ) . '.' : '' ) . ( ! empty( $s['founded'] ) ? ' Founded in ' . fs_esc( $s['founded'] ) . '.' : '' );
	if ( ! empty( $s['about'] ) ) {   // 회사 소개(2026-09-28) 뒤에 상장 정보 한 줄 — 설립 연도는 소개 쪽만(DART 설립일과 다른 회사가 있다: 재설립·분할)
		$about = fs_esc( $s['about'] ) . '</p><p class="fs-mute fs-small">' . fs_esc( ! empty( $s['en'] ) ? $s['en'] : $name ) . ' is listed on the ' . $mkt . ' market of the Korea Exchange under the ticker ' . fs_esc( $code ) . '.' . ( ! empty( $s['industry'] ) ? ' Industry: ' . fs_esc( $s['industry'] ) . '.' : '' );
	}
	// DART 주소는 대개 앞머리 없이 온다 — https://를 붙이면 옛 회사 사이트 다수가 인증서 오류였다(2026-09-27, 표본 40 중 32가 http://로 열림)
	$web = ! empty( $s['web'] ) ? ( preg_match( '#^https?://#', $s['web'] ) ? $s['web'] : 'http://' . $s['web'] ) : '';
	$h .= '<section id="about"><h2>About</h2><p>' . $about . '</p>' . ( $web ? '<p><a href="' . fs_esc( $web ) . '" rel="nofollow noopener" target="_blank">' . fs_esc( preg_replace( '#^https?://#', '', $web ) ) . '</a></p>' : '' );
	if ( $related ) {
		$h .= '<h3>' . fs_esc( $name ) . ' in our notes</h3><ul class="fs-rel">';
		foreach ( $related as $rel ) { $h .= '<li><a href="' . fs_esc( $rel['url'] ) . '">' . fs_esc( $rel['title'] ) . '</a></li>'; }
		$h .= '</ul>';
	}
	$h .= '</section></div>';
	$h .= '<div class="fs-cta"><div><b>Want to own ' . fs_esc( $name ) . ' from outside Korea?</b><br><span>Direct KRX access through a global broker, a US-listed ADR where one exists, or a Korea ETF — compared in our guide.</span></div><a class="fs-btn" href="' . $guide . '">Read the guide</a></div>';
	$h .= '<p class="fs-src">Data: Korea Exchange regular-session closing prices, volume and day’s range via Daum Finance, checked against a Naver Finance snapshot at the close; investor flows, foreign ownership and ratios via Naver Finance; company information from DART (Financial Supervisory Service). Updated after each Korean market close'
		. ( ! empty( $s['detail_date'] ) ? '; ratios as of ' . fs_date( $s['detail_date'] ) : '' )
		. ( ! empty( $s['flow_date'] ) ? '; investor flows as of ' . fs_date( $s['flow_date'] ) : '' ) . '. Delayed data, not investment advice.</p>';
	return '<div class="fs-page">' . $h . '</div>';
}

function fs_index_html( $index, $market, $page, $per = 100, $lists = array(), $flows = null, $skhy = null ) {
	$rows = $index;
	if ( $market === 'kospi' || $market === 'kosdaq' ) {
		$rows = array_values( array_filter( $index, function ( $r ) use ( $market ) { return strtolower( $r[2] ) === $market; } ) );
	}
	$total = count( $rows ); $pages = max( 1, (int) ceil( $total / $per ) ); $page = max( 1, min( $pages, (int) $page ) );
	$slice = array_slice( $rows, ( $page - 1 ) * $per, $per );
	$h  = '<div class="fs-head"><div><h1>Korean Stocks</h1><p class="fs-mute">All ' . number_format( count( $index ) ) . ' stocks listed on the KOSPI and KOSDAQ, ranked by market capitalization. Updated after each close.</p></div></div>';
	$h .= fs_search_box( count( $index ) );
	$h .= '<div class="fs-pills">';
	foreach ( array( '' => 'All', 'kospi' => 'KOSPI', 'kosdaq' => 'KOSDAQ' ) as $k => $label ) {
		$h .= '<a href="/stocks/' . ( $k ? '?m=' . $k : '' ) . '"' . ( $market === $k ? ' class="on"' : '' ) . '>' . $label . '</a>';
	}
	$h .= '</div>' . ( 1 === (int) $page && '' === $market ? fs_list_cards( $lists, $flows, $skhy ) : '' ) . '<div class="fs-scroll"><table class="fs-t fs-list"><tr><th>#</th><th>Company</th><th>Market</th><th class="fs-num">Price</th><th class="fs-num">Day</th><th class="fs-num">Market cap</th></tr>';
	foreach ( $slice as $n => $r ) {
		$h .= '<tr><td class="fs-mute">' . ( ( $page - 1 ) * $per + $n + 1 ) . '</td><td><a href="/stocks/' . fs_esc( $r[0] ) . '/"><b>' . fs_esc( $r[1] ) . '</b></a> <span class="fs-code">' . fs_esc( $r[0] ) . '</span></td>'
			. '<td>' . fs_esc( $r[2] ) . '</td><td class="fs-num">' . fs_krw( $r[3] ) . '</td><td class="fs-num">' . fs_pct( $r[4] ) . '</td><td class="fs-num">' . fs_big( $r[5] ) . '</td></tr>';
	}
	$h .= '</table></div><nav class="fs-pager">';
	$q = $market ? '&m=' . $market : '';
	if ( $page > 1 ) { $h .= '<a href="/stocks/?pg=' . ( $page - 1 ) . $q . '">← Previous</a>'; }
	$h .= '<span>Page ' . $page . ' of ' . $pages . '</span>';
	if ( $page < $pages ) { $h .= '<a href="/stocks/?pg=' . ( $page + 1 ) . $q . '">Next →</a>'; }
	return '<div class="fs-page">' . $h . '</nav></div>';
}

// ── 순위표 /stocks/lists/<slug>/ (2026-09-28) ─────────────────────────────────────────
const FS_LIST_GUIDE = array(
	'highest-dividend-yield' => array( '/korea-us-tax-treaty-forms/', 'Holding these from abroad?', 'Korea withholds 22% on dividends unless your broker has your treaty paperwork on file.', 'Dividend tax guide' ),
	'most-foreign-owned' => array( FS_GUIDE_DEFAULT, 'Want to own Korean stocks from abroad?', 'Global brokers, US-listed ADRs and Korea ETFs compared.', 'How to buy' ),
	'cheapest-by-pb' => array( '/korea-value-up-program/', 'Why so many Korean stocks trade below book', 'The Value-Up program, in plain English.', 'Value-Up guide' ),
	'largest-kosdaq' => array( '/kospi-vs-kosdaq-what-the-board-a-korean-stock-trades-on-actually-tells-you/', 'KOSPI or KOSDAQ?', 'What the board a Korean stock trades on actually tells you.', 'Read the guide' ),
);
function fs_list_rows( $slug, $rows ) {
	$h = '';
	foreach ( $rows as $i => $r ) {
		$name = '<a href="/stocks/' . fs_esc( $r['code'] ) . '/"><b>' . fs_esc( $r['name'] ) . '</b></a>' . ( ! empty( $r['reit'] ) ? ' <span class="fs-kr fs-reit">REIT</span>' : '' )
			. '<span class="fs-code">' . fs_esc( $r['code'] ) . '</span>' . ( ! empty( $r['industry'] ) ? '<div class="fs-ind">' . fs_esc( $r['industry'] ) . '</div>' : '' );
		if ( ! empty( $r['flags'] ) ) { foreach ( $r['flags'] as $f ) { $name .= '<span class="fs-flag">' . fs_esc( $f ) . '</span>'; } }
		$h .= '<tr><td class="fs-mute">' . ( $i + 1 ) . '</td><td>' . $name . '</td>';
		if ( 'highest-dividend-yield' === $slug ) {
			$h .= '<td class="fs-num">' . fs_krw( $r['close'] ) . '</td><td class="fs-num"><b>' . fs_x( $r['yld'], '%' ) . '</b></td><td class="fs-num">' . fs_krw( $r['dps'] ) . ( ! empty( $r['npay'] ) && $r['npay'] > 1 ? '<div class="fs-ind">' . (int) $r['npay'] . ' payouts in last 12 months</div>' : '' )
				. '</td><td class="fs-num">' . ( isset( $r['prev'] ) && $r['prev'] ? fs_krw( $r['prev'] ) : '–' ) . '</td><td class="fs-num">' . fs_big( $r['mcap'] ) . '</td>';
		} elseif ( 'most-foreign-owned' === $slug ) {
			$cap = ( isset( $r['fused'] ) && null !== $r['fused'] && abs( $r['fused'] - $r['fown'] ) > 1 ) ? '<div class="fs-ind">' . number_format( $r['fused'], 0 ) . '% of cap used</div>' : '';
			$h .= '<td class="fs-num"><b>' . fs_x( $r['fown'], '%' ) . '</b>' . $cap . '</td><td class="fs-num">' . fs_pct( $r['pct'] ) . '</td><td class="fs-num">' . fs_big( $r['mcap'] ) . '</td>';
		} elseif ( 'cheapest-by-pb' === $slug ) {
			$h .= '<td class="fs-num"><b>' . fs_x( $r['pbr'] ) . '</b></td><td class="fs-num">' . fs_x( isset( $r['per'] ) ? $r['per'] : null ) . '</td><td class="fs-num">' . fs_x( isset( $r['roe'] ) ? $r['roe'] : null, '%' ) . '</td><td class="fs-num">' . fs_big( $r['mcap'] ) . '</td>';
		} else {
			$h .= '<td class="fs-num">' . fs_krw( $r['close'] ) . '</td><td class="fs-num">' . fs_pct( $r['pct'] ) . '</td><td class="fs-num"><b>' . fs_big( $r['mcap'] ) . '</b></td>';
		}
		$h .= '</tr>';
	}
	return $h;
}
function fs_list_html( $slug, $l, $lists ) {
	$heads = array(
		'highest-dividend-yield' => '<th class="fs-num">Price</th><th class="fs-num">Yield</th><th class="fs-num">Dividend / share</th><th class="fs-num">Year before</th><th class="fs-num">Market cap</th>',
		'most-foreign-owned' => '<th class="fs-num">Foreign-owned</th><th class="fs-num">Day</th><th class="fs-num">Market cap</th>',
		'cheapest-by-pb' => '<th class="fs-num">P/B</th><th class="fs-num">P/E</th><th class="fs-num">ROE</th><th class="fs-num">Market cap</th>',
		'largest-kosdaq' => '<th class="fs-num">Price</th><th class="fs-num">Day</th><th class="fs-num">Market cap</th>',
	);
	$h  = '<nav class="fs-crumb"><a href="/stocks/">Stocks</a> › <a href="/stocks/#lists">Lists</a> › ' . fs_esc( $l['short'] ) . '</nav>';
	$h .= '<div class="fs-head"><div><h1>' . fs_esc( $l['title'] ) . '</h1><p class="fs-lead">' . fs_esc( $l['lead'] ) . '</p></div></div>';
	$h .= '<div class="fs-chips"><span>' . number_format( $l['count'] ) . ' stocks qualify</span><span>Top ' . count( $l['rows'] ) . ' shown</span><span>Data as of ' . fs_date( $l['date'] ) . '</span></div>';
	$h .= '<div class="fs-scroll"><table class="fs-t fs-listtab fs-lt-' . fs_esc( $slug ) . '"><tr><th>#</th><th>Company</th>' . $heads[ $slug ] . '</tr>' . fs_list_rows( $slug, $l['rows'] ) . '</table></div>';
	if ( isset( FS_LIST_GUIDE[ $slug ] ) ) {
		$g = FS_LIST_GUIDE[ $slug ];
		$h .= '<div class="fs-cta"><div><b>' . fs_esc( $g[1] ) . '</b><br><span>' . fs_esc( $g[2] ) . '</span></div><a class="fs-btn" href="' . $g[0] . '">' . fs_esc( $g[3] ) . ' →</a></div>';
	}
	$other = '';
	foreach ( $lists as $k => $x ) { if ( $k !== $slug ) { $other .= '<a href="/stocks/lists/' . $k . '/">' . fs_esc( $x['short'] ) . '</a>'; } }
	$h .= '<div class="fs-sec"><h2>Other lists</h2><div class="fs-pills">' . $other . '</div></div>';
	$src = 'highest-dividend-yield' === $slug ? 'Dividends: each company\'s latest annual filing on DART (Financial Supervisory Service), cash dividend per common share. Prices: Korea Exchange regular-session close via Daum Finance.'
		: 'Data: Korea Exchange regular-session closing prices via Daum Finance; ratios and foreign ownership via Naver Finance; latest annual results for ROE.';
	return '<div class="fs-page">' . $h . '<p class="fs-src">' . $src . ' Updated after each Korean market close. Delayed data, not investment advice.</p></div>';
}
function fs_list_cards( $lists, $flows = null, $skhy = null ) {
	if ( ! $lists && ! $flows && ! $skhy ) { return ''; }
	$h = '<div class="fs-listcards" id="lists">';
	foreach ( $lists as $k => $x ) { $h .= '<a href="/stocks/lists/' . $k . '/"><b>' . fs_esc( $x['short'] ) . '</b><span>' . fs_esc( $x['blurb'] ) . '</span></a>'; }
	if ( $flows ) { $h .= '<a href="/stocks/foreign-flows/"><b>Foreign flows</b><span>What foreigners bought and sold on ' . date( 'M j', strtotime( $flows['date'] ) ) . '</span></a>'; }
	if ( $skhy ) { $h .= '<a href="/stocks/skhy-premium/"><b>SKHY premium</b><span>SK Hynix on the Nasdaq vs Seoul, every day</span></a>'; }
	return $h . '</div>';
}

// ── SKHY 프리미엄 /stocks/skhy-premium/ (2026-09-28) ──────────────────────────────────
// src/stock_db.build_skhy가 나스닥 SKHY와 서울 SK하이닉스를 같은 날짜끼리 짝지어 fm_skhy에 넣는다(ADR 1주 = 원주 10분의 1주).
function fs_skhy_chart( $rows ) {
	$n = count( $rows ); $max = 1; $neg = false; foreach ( $rows as $r ) { $max = max( $max, abs( $r['prem'] ) ); $neg = $neg || $r['prem'] < 0; }
	$bw = 100 / $n; $base = $neg ? 50 : 100; $span = $neg ? 48 : 96;   // 할인(음수)이 한 번이라도 있으면 0선을 가운데로
	$svg = '<svg class="fs-fchart" viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="SKHY premium to Seoul shares by day">' . ( $neg ? '<line x1="0" x2="100" y1="50" y2="50" stroke="#d7dbe2" stroke-width="1" vector-effect="non-scaling-stroke"/>' : '' );
	foreach ( $rows as $i => $r ) {
		$v = (float) $r['prem']; $bh = max( 0.5, abs( $v ) / $max * $span );
		$svg .= '<rect x="' . round( $i * $bw + $bw * 0.15, 2 ) . '" y="' . round( $v >= 0 ? $base - $bh : $base, 2 ) . '" width="' . round( $bw * 0.7, 2 ) . '" height="' . round( $bh, 2 ) . '" fill="' . ( $v >= 0 ? '#d9480f' : '#1b64da' ) . '"><title>' . date( 'M j', strtotime( $r['d'] ) ) . ': ' . ( $v > 0 ? '+' : '' ) . number_format( $v, 1 ) . '%</title></rect>';
	}
	return '<div class="fs-fax"><span>' . ( $max > 0 ? '+' : '' ) . number_format( $max, 0 ) . '%</span></div>' . $svg . '</svg><div class="fs-fax"><span>' . date( 'M j', strtotime( $rows[0]['d'] ) ) . '</span><span>' . date( 'M j', strtotime( $rows[ $n - 1 ]['d'] ) ) . '</span></div>';
}
function fs_skhy_html( $p ) {
	$last = $p['rows'][ count( $p['rows'] ) - 1 ]; $day = date( 'M j', strtotime( $last['d'] ) );
	$signed = function ( $v ) { return ( $v > 0 ? '+' : ( $v < 0 ? '−' : '' ) ) . number_format( abs( $v ), 1 ) . '%'; };
	$cell = function ( $label, $value, $small ) { return '<div class="fs-cell"><span>' . $label . '</span><b>' . $value . '</b><small class="fs-mute">' . $small . '</small></div>'; };
	$h  = '<nav class="fs-crumb"><a href="/stocks/">Stocks</a> › <a href="/stocks/000660/">SK Hynix</a> › SKHY premium</nav>';
	$h .= '<div class="fs-head"><div><h1>SKHY vs SK Hynix: The Nasdaq Premium to Seoul</h1><p class="fs-lead">How much more SK Hynix costs on the Nasdaq (SKHY) than in Seoul, every trading day since the ADR listed on ' . date( 'F j, Y', strtotime( $p['rows'][0]['d'] ) ) . '. One SKHY ADR represents one-tenth of an SK Hynix common share.</p></div></div>';
	$h .= '<div class="fs-strip fs-strip4">';
	$h .= $cell( 'SKHY premium · ' . $day, '<span class="' . ( $last['prem'] >= 0 ? 'fs-up' : 'fs-dn' ) . '">' . $signed( $last['prem'] ) . '</span>', 'over the Seoul price' );
	$h .= $cell( 'SKHY close (Nasdaq)', '$' . number_format( $last['usd'], 2 ), $day . ', New York' );
	$h .= $cell( 'Seoul price per ADR', '$' . number_format( $last['seoul_usd'], 2 ), '₩' . number_format( $last['krw'] ) . ' ÷ 10 at ₩' . number_format( $last['fx'], 1 ) . '/$' );
	$h .= $cell( 'Average since listing', $signed( $p['avg'] ), $p['days'] . ' trading days' );
	$h .= '</div>';
	$h .= '<div class="fs-sec"><h2>The premium, day by day</h2><p class="fs-note">SKHY closing price over the Seoul closing price converted to dollars per ADR. Highest ' . $signed( $p['high']['prem'] ) . ' (' . date( 'M j', strtotime( $p['high']['d'] ) ) . '), lowest ' . $signed( $p['low']['prem'] ) . ' (' . date( 'M j', strtotime( $p['low']['d'] ) ) . ').</p>' . fs_skhy_chart( $p['rows'] ) . '</div>';
	$h .= '<div class="fs-sec"><h2>Last 20 trading days</h2><div class="fs-scroll"><table class="fs-t fs-skhytab"><tr><th>Date</th><th class="fs-num">SKHY</th><th class="fs-num">Seoul close</th><th class="fs-num">USD/KRW</th><th class="fs-num">Seoul per ADR</th><th class="fs-num">Premium</th></tr>';
	foreach ( array_reverse( array_slice( $p['rows'], -20 ) ) as $r ) {
		$h .= '<tr><td>' . date( 'M j, Y', strtotime( $r['d'] ) ) . '</td><td class="fs-num">$' . number_format( $r['usd'], 2 ) . '</td><td class="fs-num">₩' . number_format( $r['krw'] ) . '</td><td class="fs-num">' . number_format( $r['fx'], 1 ) . '</td><td class="fs-num">$' . number_format( $r['seoul_usd'], 2 ) . '</td><td class="fs-num"><b class="' . ( $r['prem'] >= 0 ? 'fs-up' : 'fs-dn' ) . '">' . $signed( $r['prem'] ) . '</b></td></tr>';
	}
	$h .= '</table></div></div>';
	$h .= '<div class="fs-two fs-sec"><div><h2>How we calculate it</h2><p class="fs-note">Premium = SKHY close × 10 × USD/KRW ÷ SK Hynix Seoul close − 1. Both closes are from the same calendar day, so the Nasdaq close comes about 13 hours after the Seoul close — news in between moves one and not the other. Days when either market was shut are left out.</p></div>';
	$h .= '<div><h2>Why the two prices can differ</h2><p class="fs-note">An ADR only tracks its home share as closely as investors can swap one for the other. New ADRs are created by depositing Seoul shares with the depositary bank, which takes time, fees and access to the Korean market. When US demand for SKHY outruns that process, the ADR can trade above the Seoul price for long stretches.</p></div></div>';
	$h .= '<div class="fs-cta"><div><b>Buying SK Hynix from abroad?</b><br><span>Seoul shares, the SKHY ADR and Korea ETFs compared.</span></div><a class="fs-btn" href="/korean-adrs-for-us-investors/">Korean ADRs explained →</a></div>';
	$h .= '<p class="fs-src">Data: SKHY closing prices from Yahoo Finance, checked against Nasdaq; SK Hynix Korea Exchange regular-session closes via Daum Finance; USD/KRW is the rate at the Nasdaq close (4 p.m. New York, Yahoo Finance hourly), the same moment as the SKHY close. Each ADR = 0.1 common share. Updated after each Korean close. Delayed data, not investment advice. See also <a href="/sk-hynix-vs-micron/">SK Hynix vs Micron</a>.</p>';
	return '<div class="fs-page">' . $h . '</div>';
}

// ── 외국인 수급 /stocks/foreign-flows/ (2026-09-28) ───────────────────────────────────
// 종목별 수급은 다음 날 아침에 확정된다 — src/stock_db.build_flows가 가장 최근 수급 날짜로 만들어 fm_flows에 넣는다.
function fs_flow_rows( $rows, $sell = false ) {
	$h = '';
	foreach ( $rows as $i => $r ) {
		$h .= '<tr><td class="fs-mute">' . ( $i + 1 ) . '</td><td><a href="/stocks/' . fs_esc( $r['code'] ) . '/"><b>' . fs_esc( $r['name'] ) . '</b></a><span class="fs-code">' . fs_esc( $r['code'] ) . '</span></td>'
			. '<td class="fs-num"><b class="' . ( $sell ? 'fs-dn' : 'fs-up' ) . '">' . ( $sell ? '' : '+' ) . fs_big( $r['val'] ) . '</b></td><td class="fs-num">' . fs_pct( $r['pct'], false ) . '</td><td class="fs-num">' . fs_x( $r['own'], '%' ) . '</td></tr>';
	}
	return $h;
}
function fs_own_rows( $rows, $date ) {
	$max = 0; foreach ( $rows as $r ) { $max = max( $max, abs( $r['diff'] ) ); }
	$h = '';
	foreach ( $rows as $r ) {
		$up = $r['diff'] >= 0; $w = $max > 0 ? max( 3, round( abs( $r['diff'] ) / $max * 62 ) ) : 3;
		$h .= '<tr><td><a href="/stocks/' . fs_esc( $r['code'] ) . '/"><b>' . fs_esc( $r['name'] ) . '</b></a><span class="fs-code">' . fs_esc( $r['code'] ) . '</span>' . ( $r['industry'] ? '<div class="fs-ind">' . fs_esc( $r['industry'] ) . '</div>' : '' ) . '</td>'
			. '<td class="fs-num">' . number_format( $r['from'], 1 ) . '%</td><td class="fs-num"><b>' . number_format( $r['to'], 1 ) . '%</b></td>'
			. '<td class="fs-barcell"><span class="fs-bar ' . ( $up ? 'fs-bup' : 'fs-bdn' ) . '" style="width:' . $w . '%"></span><b class="' . ( $up ? 'fs-up' : 'fs-dn' ) . '">' . ( $up ? '+' : '−' ) . number_format( abs( $r['diff'] ), 1 ) . 'pt</b></td></tr>';
	}
	return $h;
}
function fs_flow_chart( $series ) {   // 코스피 외국인 순매수, 날마다 막대 하나. 글자는 그림 밖에 둔다 — 휴대폰에서 그림이 줄면 글자도 같이 작아졌다
	$n = count( $series ); $max = 1; foreach ( $series as $p ) { $max = max( $max, abs( $p['kospi_eok'] ) ); }
	$bw = 100 / $n;
	$svg = '<svg class="fs-fchart" viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="KOSPI foreign net buying, last ' . $n . ' trading days"><line x1="0" x2="100" y1="50" y2="50" stroke="#d7dbe2" stroke-width="1" vector-effect="non-scaling-stroke"/>';
	foreach ( $series as $i => $p ) {
		$v = (float) $p['kospi_eok']; $bh = max( 0.5, abs( $v ) / $max * 48 );
		$svg .= '<rect x="' . round( $i * $bw + $bw * 0.18, 2 ) . '" y="' . round( $v >= 0 ? 50 - $bh : 50, 2 ) . '" width="' . round( $bw * 0.64, 2 ) . '" height="' . round( $bh, 2 ) . '" fill="' . ( $v >= 0 ? '#d9480f' : '#1b64da' ) . '"><title>' . date( 'M j', strtotime( $p['d'] ) ) . ': ' . ( $v > 0 ? '+' : '' ) . fs_eok( $v ) . '</title></rect>';
	}
	return '<div class="fs-fax"><span>±' . fs_eok( $max ) . '</span></div>' . $svg . '</svg><div class="fs-fax"><span>' . date( 'M j', strtotime( $series[0]['d'] ) ) . '</span><span>' . date( 'M j', strtotime( $series[ $n - 1 ]['d'] ) ) . '</span></div>';
}
function fs_flows_html( $f ) {
	$day = date( 'M j', strtotime( $f['date'] ) );
	$cell = function ( $label, $value, $small ) { return '<div class="fs-cell"><span>' . $label . '</span><b>' . $value . '</b><small class="fs-mute">' . $small . '</small></div>'; };
	$series = isset( $f['series'] ) ? $f['series'] : array(); $ns = count( $series );
	$h  = '<nav class="fs-crumb"><a href="/stocks/">Stocks</a> › Foreign flows</nav>';
	$h .= '<div class="fs-head"><div><h1>What Foreign Investors Bought and Sold in Korea</h1><p class="fs-lead">Net buying by overseas investors in Korean stocks, from Korea Exchange investor-type data — published for every stock in Korea, and rarely shown in English. Latest trading day: ' . date( 'l, M j, Y', strtotime( $f['date'] ) ) . '.</p></div></div>';
	$h .= '<div class="fs-strip fs-strip4">';
	$h .= $cell( 'KOSPI, foreign net · ' . $day, null === $f['kospi_eok'] ? '–' : '<span class="' . ( $f['kospi_eok'] >= 0 ? 'fs-up' : 'fs-dn' ) . '">' . ( $f['kospi_eok'] > 0 ? '+' : '' ) . fs_eok( $f['kospi_eok'] ) . '</span>', 'whole market' );
	$h .= $cell( 'Bought (' . (int) $f['universe'] . ' largest)', '<span class="fs-up">+' . fs_big( $f['buy_total'] ) . '</span>', number_format( $f['n_buy'] ) . ' stocks' );
	$h .= $cell( 'Sold (' . (int) $f['universe'] . ' largest)', '<span class="fs-dn">' . fs_big( $f['sell_total'] ) . '</span>', number_format( $f['n_sell'] ) . ' stocks' );
	if ( $ns >= 5 ) {
		$sum = 0; foreach ( $series as $p ) { $sum += $p['kospi_eok']; }
		$h .= $cell( 'KOSPI, last ' . $ns . ' trading days', '<span class="' . ( $sum >= 0 ? 'fs-up' : 'fs-dn' ) . '">' . ( $sum > 0 ? '+' : '' ) . fs_eok( $sum ) . '</span>', 'foreign net, total' );
	} else {
		$h .= '<div class="fs-cell fs-soon"><span>Last 20 trading days</span><b class="fs-mute">builds daily</b><small class="fs-mute">' . $ns . ' of 20 days so far</small></div>';
	}
	$h .= '</div>';
	if ( $ns >= 5 ) { $h .= '<div class="fs-sec"><h2>Foreign net buying, KOSPI</h2><p class="fs-note">Whole-market total by day, last ' . $ns . ' trading days. Orange: net bought. Blue: net sold.</p>' . fs_flow_chart( $series ) . '</div>'; }
	$head = '<tr><th>#</th><th>Company</th><th class="fs-num">%s</th><th class="fs-num">Day</th><th class="fs-num">Foreign-owned</th></tr>';
	$h .= '<div class="fs-two fs-sec"><div><h2>Bought most <span class="fs-kr">KR data</span></h2><p class="fs-note">Foreign net buying, KRW · ' . $day . '</p><div class="fs-scroll"><table class="fs-t fs-flowtab">' . sprintf( $head, 'Net bought' ) . fs_flow_rows( $f['buy'] ) . '</table></div></div>';
	$h .= '<div><h2>Sold most <span class="fs-kr">KR data</span></h2><p class="fs-note">Foreign net selling, KRW · ' . $day . '</p><div class="fs-scroll"><table class="fs-t fs-flowtab">' . sprintf( $head, 'Net sold' ) . fs_flow_rows( $f['sell'], true ) . '</table></div></div></div>';
	if ( ! empty( $f['streak'] ) ) {
		$since = date( 'M j', strtotime( $f['streak'][0]['since'] ) );
		$h .= '<div class="fs-sec"><h2>Bought five days in a row</h2><p class="fs-note">Stocks foreigners net-bought on each of the last five trading days (' . $since . '–' . $day . '), with the five-day total and the change in foreign ownership.</p><div class="fs-scroll"><table class="fs-t fs-flowtab fs-streak"><tr><th>#</th><th>Company</th><th class="fs-num">5-day net bought</th><th class="fs-num">Foreign ownership</th></tr>';
		foreach ( $f['streak'] as $i => $r ) {
			$h .= '<tr><td class="fs-mute">' . ( $i + 1 ) . '</td><td><a href="/stocks/' . fs_esc( $r['code'] ) . '/"><b>' . fs_esc( $r['name'] ) . '</b></a><span class="fs-code">' . fs_esc( $r['code'] ) . '</span></td><td class="fs-num"><b class="fs-up">+' . fs_big( $r['val'] ) . '</b></td><td class="fs-num"><span class="fs-from">' . fs_x( $r['from'], '%' ) . ' → </span>' . fs_x( $r['to'], '%' ) . '</td></tr>';
		}
		$h .= '</table></div></div>';
	}
	if ( ! empty( $f['up'] ) && ! empty( $f['since'] ) ) {
		$from = date( 'M j', strtotime( $f['since'] ) ); $own = '<tr><th>Company</th><th class="fs-num">' . $from . '</th><th class="fs-num">' . $day . '</th><th>Change</th></tr>';
		$h .= '<div class="fs-two fs-sec"><div><h2>Foreign ownership rising</h2><p class="fs-note">Biggest increase in the share held by foreigners since ' . date( 'M j, Y', strtotime( $f['since'] ) ) . '</p><table class="fs-t fs-owntab">' . $own . fs_own_rows( $f['up'], $f['date'] ) . '</table></div>';
		$h .= '<div><h2>Foreign ownership falling</h2><p class="fs-note">Biggest decrease since ' . date( 'M j, Y', strtotime( $f['since'] ) ) . '</p><table class="fs-t fs-owntab">' . $own . fs_own_rows( $f['down'], $f['date'] ) . '</table></div></div>';
	}
	$h .= '<div class="fs-cta"><div><b>Want to buy what foreigners are buying?</b><br><span>Direct KRX access, US-listed ADRs and Korea ETFs compared.</span></div><a class="fs-btn" href="' . FS_GUIDE_DEFAULT . '">How to buy Korean stocks →</a></div>';
	$h .= '<p class="fs-src">Data: Korea Exchange investor-type trading and foreign ownership via Naver Finance. Rankings cover the ' . (int) $f['universe'] . ' largest companies (about 94% of market value); the KOSPI total covers the whole market. Values are foreign net shares × closing price. Updated each morning for the previous trading day. Delayed data, not investment advice.</p>';
	return '<div class="fs-page">' . $h . '</div>';
}
function fs_in_lists( $code, $lists ) {   // 종목 페이지 "이 종목이 든 순위표"
	$out = array();
	foreach ( $lists as $k => $x ) {
		foreach ( $x['rows'] as $i => $r ) { if ( $r['code'] === $code ) { $out[] = '<a href="/stocks/lists/' . $k . '/">#' . ( $i + 1 ) . ' in ' . fs_esc( $x['short'] ) . '</a>'; break; } }
	}
	return $out ? '<div class="fs-inlists">' . implode( '', $out ) . '</div>' : '';
}

function fs_market_html( $m, $lists = array(), $flows = null, $skhy = null ) {
	if ( ! is_array( $m ) || empty( $m['index'] ) ) { return ''; }
	$cell = function ( $label, $value ) { return '<div class="fs-cell"><span>' . $label . '</span><b>' . $value . '</b></div>'; };
	$k = $m['index']['KOSPI']; $q = $m['index']['KOSDAQ'];
	$h  = '<div class="fs-strip">';
	$h .= $cell( 'KOSPI · ' . date( 'M j', strtotime( $k['date'] ) ) . ' close', number_format( $k['close'], 2 ) . ' <small>' . fs_pct( $k['pct'], false ) . '</small>' );
	$h .= $cell( 'KOSDAQ', number_format( $q['close'], 2 ) . ' <small>' . fs_pct( $q['pct'], false ) . '</small>' );
	if ( ! empty( $m['usdkrw']['close'] ) ) { $h .= $cell( 'USD/KRW', number_format( $m['usdkrw']['close'], 1 ) . ' <small>' . fs_pct( $m['usdkrw']['pct'], false ) . '</small>' ); }
	if ( ! empty( $m['skhy'] ) ) { $h .= $cell( $skhy ? '<a href="/stocks/skhy-premium/">SKHY (Nasdaq) vs Seoul →</a>' : 'SKHY (Nasdaq) vs Seoul', fs_pct( $m['skhy']['premium_pct'], false ) . ' <small>premium</small>' ); }
	if ( isset( $k['foreign_net_eok'] ) ) { $h .= $cell( 'Foreign net, KOSPI', '<span class="' . ( $k['foreign_net_eok'] >= 0 ? 'fs-up' : 'fs-dn' ) . '">' . fs_eok( $k['foreign_net_eok'] ) . '</span>' ); }
	if ( ! empty( $m['next_holiday'] ) ) { $h .= $cell( 'Next KRX holiday', date( 'M j', strtotime( $m['next_holiday']['date'] ) ) . ' <small>' . fs_esc( $m['next_holiday']['name'] ) . '</small>' ); }
	$h .= '</div><div class="fs-cards">';
	$h .= '<div class="fs-card"><h2>Largest companies<a class="fs-more" href="/stocks/">All ' . number_format( array_sum( $m['counts'] ) ) . ' →</a></h2><table class="fs-t">';
	foreach ( $m['largest'] as $r ) { $h .= '<tr><td><a href="/stocks/' . $r['code'] . '/"><b>' . fs_esc( $r['name'] ) . '</b></a> <span class="fs-code">' . $r['code'] . '</span></td><td class="fs-num">' . fs_krw( $r['close'] ) . '</td><td class="fs-num">' . fs_pct( $r['pct'] ) . '</td></tr>'; }
	$h .= '</table></div><div class="fs-card"><h2>Movers</h2><ul class="fs-mv"><li class="fs-sep">Gainers</li>';
	foreach ( array_slice( $m['gainers'], 0, 4 ) as $r ) { $h .= '<li><a href="/stocks/' . $r['code'] . '/">' . fs_esc( $r['name'] ) . ( ! empty( $r['ipo'] ) ? ' <span class="fs-kr fs-ipo">New listing</span>' : ( ! empty( $r['nolimit'] ) ? ' <span class="fs-kr fs-ipo">No price limit</span>' : '' ) ) . '</a>' . fs_pct( $r['pct'] ) . '</li>'; }
	$h .= '<li class="fs-sep">Losers</li>';
	foreach ( array_slice( $m['losers'], 0, 4 ) as $r ) { $h .= '<li><a href="/stocks/' . $r['code'] . '/">' . fs_esc( $r['name'] ) . '</a>' . fs_pct( $r['pct'] ) . '</li>'; }
	$h .= '</ul><p class="fs-mute fs-small">Stocks with at least ₩5B traded. Moves beyond the 30% daily limit happen only without a price limit — a first day of trading (from the IPO price) or a delisting sale.</p></div><div class="fs-card"><h2>Foreign investors <span class="fs-kr">KR data</span>' . ( $flows ? '<a class="fs-more" href="/stocks/foreign-flows/">See all →</a>' : '' ) . '</h2><ul class="fs-mv"><li class="fs-sep">Bought most</li>';
	foreach ( array_slice( $m['foreign_buy'], 0, 3 ) as $r ) { $h .= '<li><a href="/stocks/' . $r['code'] . '/">' . fs_esc( $r['name'] ) . '</a><b class="fs-up">+' . fs_big( $r['value'] ) . '</b></li>'; }
	$h .= '<li class="fs-sep">Sold most</li>';
	foreach ( array_slice( $m['foreign_sell'], 0, 3 ) as $r ) { $h .= '<li><a href="/stocks/' . $r['code'] . '/">' . fs_esc( $r['name'] ) . '</a><b class="fs-dn">' . fs_big( $r['value'] ) . '</b></li>'; }
	$h .= '</ul><p class="fs-mute fs-small">Net buying by foreign investors in KRW, ' . date( 'M j', strtotime( ! empty( $m['flow_date'] ) ? $m['flow_date'] : $m['date'] ) ) . ' — ' . number_format( isset( $m['flow_universe'] ) ? $m['flow_universe'] : 0 ) . ' stocks with flow data that day.</p></div></div>';
	if ( $lists ) {   // 홈 카드 밑 순위표 링크(2026-09-28)
		$h .= '<div class="fs-morelists"><span>Stock lists</span>';
		foreach ( $lists as $k => $x ) { $h .= '<a href="/stocks/lists/' . $k . '/">' . fs_esc( $x['short'] ) . '</a>'; }
		if ( $flows ) { $h .= '<a href="/stocks/foreign-flows/">Foreign flows</a>'; }
		if ( $skhy ) { $h .= '<a href="/stocks/skhy-premium/">SKHY premium</a>'; }
		$h .= '</div>';
	}
	return $h;
}

const FS_CSS = <<<'CSS'
:root{--fs-ink:#191f28;--fs-sub:#4e5968;--fs-mute:#8b95a1;--fs-line:#eef0f3;--fs-pill:#f2f4f6;--fs-blue:#1b64da;--fs-up:#d9480f;--fs-dn:#1b64da;--fs-green:#2b8a3e;--fs-gb:#e9f8ec;--fs-bb:#e7f5ff}
.fs-up{color:var(--fs-up)}.fs-dn{color:var(--fs-dn)}.fs-fl{color:var(--fs-mute)}.fs-num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.fs-mute{color:var(--fs-mute)}.fs-small{font-size:12.5px;margin:10px 0 0}.fs-code{color:var(--fs-mute);font-size:11.5px;margin-left:4px}
.fs-kr{background:var(--fs-gb);color:var(--fs-green);font-size:11px;font-weight:700;border-radius:6px;padding:2px 6px;vertical-align:middle}.fs-kr.fs-ipo{background:#fff4e6;color:#d9480f}
.fs-page,.fs-strip,.fs-cards,.fs-search{font-family:Pretendard,-apple-system,"Segoe UI",sans-serif;color:var(--fs-ink)}
/* 테마가 본문을 약 650px로 묶는다 — 최대 폭만 넓히고 가운데 정렬은 테마의 auto 여백에 맡긴다(옮기기로 넓히면 1280px 밖에서 오른쪽으로 밀렸다, 2026-09-27) */
.fs-page{max-width:1200px!important;width:auto;margin-left:auto!important;margin-right:auto!important;box-sizing:border-box}
.fs-page p,.fs-page li{font-size:15px;line-height:1.6}.fs-page h1,.fs-page h2,.fs-page h3{font-family:Pretendard,-apple-system,sans-serif;letter-spacing:-.01em;line-height:1.3}.fs-page h3{font-size:16px;font-weight:800;margin:18px 0 6px}
.fs-page a,.fs-cards a{color:inherit;text-decoration:none}.fs-page a:hover,.fs-cards a:hover{text-decoration:underline}
/* 메뉴 줄 — 네 화면이 같은 틀(홈 템플릿·fermata-hub)에서 이것 하나로 그려진다. 폭은 목록과 같은 1200px */
main .fs-navwrap.fs-navwrap:not(.alignfull):not(.alignwide){max-width:1200px!important;margin:0 auto 22px!important;padding:20px 0;border-bottom:1px solid var(--fs-line);box-sizing:border-box}
.fs-crumb{font-size:13px;color:var(--fs-mute);margin:0 0 10px}
.fs-head{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;align-items:flex-end;margin:0 0 6px}.fs-head h1{margin:0;font-size:30px;font-weight:800;letter-spacing:-.01em}
.fs-tick{color:var(--fs-mute);font-size:13.5px;margin:4px 0 6px}.fs-price{font-size:38px;font-weight:800;letter-spacing:-.02em;line-height:1.1}.fs-price small{font-size:18px;font-weight:700;margin-left:6px}
.fs-btn{display:inline-block;background:var(--fs-blue);color:#fff!important;border-radius:10px;padding:10px 15px;font-weight:700;font-size:14px}
.fs-tabs{display:flex;gap:4px;border-bottom:1px solid var(--fs-line);margin:18px 0 16px;overflow-x:auto}.fs-tabs a{padding:9px 12px;font-weight:600;color:var(--fs-sub);white-space:nowrap}
.fs-two{display:grid;grid-template-columns:1fr 1fr;gap:28px}.fs-stats{display:grid;grid-template-columns:1fr 1fr;gap:0 20px}
table.fs-kv,table.fs-t{width:100%;border-collapse:collapse;font-size:14px;margin:0}.fs-kv td,.fs-t td,.fs-t th{padding:8px 6px;border-top:1px solid var(--fs-line);text-align:left}
.fs-kv td:last-child{text-align:right;font-weight:600;font-variant-numeric:tabular-nums}.fs-t th{color:var(--fs-mute);font-weight:600;font-size:12.5px;border-top:0}.fs-t .fs-num{text-align:right}.fs-scroll .fs-t td,.fs-scroll .fs-t th{white-space:nowrap}
.fs-chart{width:100%;height:auto}.fs-ax{font-size:11px;fill:var(--fs-mute)}.fs-legend{font-size:12.5px;color:var(--fs-mute);margin:6px 0 0}
.fs-key{display:inline-block;width:14px;height:3px;vertical-align:middle;margin:0 6px 0 0}.fs-dash{background:repeating-linear-gradient(90deg,var(--fs-green) 0 4px,transparent 4px 7px);margin-left:14px}
.fs-sec{margin-top:30px}.fs-sec h2,.fs-two h2{font-size:18px;font-weight:800;margin:0 0 6px}.fs-note{color:var(--fs-sub);font-size:13.5px;margin:0 0 10px}
.fs-scroll{overflow-x:auto}.fs-rel{padding-left:18px;margin:6px 0 0}.fs-rel li{margin:4px 0}
.fs-listcards{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px;margin:4px 0 18px}.fs-listcards a{border:1px solid var(--fs-line);border-radius:14px;padding:12px 14px;display:block}.fs-listcards a b{display:block;font-size:14.5px;margin-bottom:3px}.fs-listcards a span{font-size:12.5px;color:var(--fs-mute);line-height:1.45}.fs-listcards a:hover{border-color:var(--fs-blue);text-decoration:none!important}
.fs-lead{color:var(--fs-sub);font-size:14.5px;line-height:1.6;max-width:75ch;margin:6px 0 0}.fs-chips{display:flex;flex-wrap:wrap;gap:6px;margin:12px 0 14px}.fs-chips span{background:var(--fs-pill);border-radius:8px;padding:4px 9px;font-size:12.5px;color:var(--fs-sub)}
.fs-ind{color:var(--fs-mute);font-size:11.5px;margin-top:2px}.fs-flag{display:inline-block;background:#fff4e6;color:#b35c00;border-radius:6px;font-size:11px;font-weight:600;padding:2px 6px;margin:4px 4px 0 0}.fs-kr.fs-reit{background:#e7f5ff;color:#1864ab}
.fs-scroll .fs-listtab td:nth-child(2){white-space:normal;min-width:190px}.fs-inlists{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0 0}.fs-inlists a{background:#e7f5ff;color:#1864ab!important;border-radius:999px;padding:5px 11px;font-size:12.5px;font-weight:600}
.fs-morelists{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:4px 0 8px;font-size:13.5px}.fs-morelists span{color:var(--fs-mute);font-weight:700;margin-right:4px}.fs-morelists a,.fs-listcards a,.fs-inlists a{text-decoration:none!important}.fs-morelists a{background:var(--fs-pill);border-radius:999px;padding:6px 12px;font-weight:600;color:var(--fs-sub)}
.fs-cta{background:var(--fs-bb);border-radius:14px;padding:16px 18px;margin-top:28px;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:center}.fs-cta span{color:var(--fs-sub);font-size:13.5px}
.fs-src{color:var(--fs-mute);font-size:12.5px;margin-top:22px}
.fs-pills{display:flex;gap:8px;margin:14px 0}.fs-pills a{background:var(--fs-pill);border-radius:999px;padding:7px 14px;font-weight:600;font-size:13.5px;color:var(--fs-sub)}.fs-pills a.on{background:var(--fs-ink);color:#fff}
.fs-pager{display:flex;gap:16px;justify-content:center;align-items:center;margin:18px 0}.fs-pager a{background:#3182f6;color:#fff!important;border-radius:999px;padding:8px 16px;font-weight:600}
.fs-search{position:relative;display:flex;align-items:center;gap:10px;background:var(--fs-pill);border-radius:999px;padding:4px 18px;margin:14px auto 16px!important;max-width:680px!important;box-sizing:border-box}
/* 홈 템플릿의 'main .is-layout-constrained>:not(.alignfull):not(.alignwide){max-width:1200px!important}'보다 구체적이어야 680px가 먹는다 */
main div.fs-search.fs-search:not(.alignfull):not(.alignwide){max-width:680px!important}
.fs-search input{flex:1;border:0;background:transparent;font:15px Pretendard,sans-serif;padding:10px 0;color:var(--fs-ink);outline:none}.fs-search kbd{border:1px solid #d7dbe2;border-radius:6px;padding:1px 7px;font-size:12px;color:var(--fs-mute);font-family:inherit}
.fs-search ul{position:absolute;left:0;right:0;top:calc(100% + 6px);background:#fff;border:1px solid var(--fs-line);border-radius:14px;box-shadow:0 12px 30px rgba(0,0,0,.08);list-style:none;margin:0;padding:6px;z-index:50}
.fs-search li a{display:flex;justify-content:space-between;padding:9px 12px;border-radius:10px;color:var(--fs-ink);text-decoration:none}.fs-search li a:hover,.fs-search li a.on{background:var(--fs-pill)}
.fs-strip{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px;margin:18px 0}.fs-cell{border:1px solid var(--fs-line);border-radius:14px;padding:11px 13px}
.fs-cell>span{display:block;font-size:12px;color:var(--fs-mute)}.fs-cell b{font-size:18px;display:block;font-variant-numeric:tabular-nums}.fs-cell b small{font-size:12.5px;font-weight:600;margin-left:4px;color:var(--fs-sub)}.fs-cell b small .fs-up{color:var(--fs-up)}.fs-cell b small .fs-dn{color:var(--fs-dn)}
.fs-cards{display:grid;grid-template-columns:1.25fr 1fr 1fr;gap:16px;margin:0 0 10px}.fs-card{border:1px solid var(--fs-line);border-radius:16px;padding:16px 18px}
.fs-card h2{margin:0 0 10px;font-size:16px;display:flex;align-items:center;gap:8px}.fs-more{margin-left:auto;font-size:12.5px;color:var(--fs-blue)!important;font-weight:600}
.fs-mv{list-style:none;margin:0;padding:0}.fs-mv li{display:flex;justify-content:space-between;gap:10px;padding:7px 0;border-top:1px solid var(--fs-line);font-size:14px}.fs-mv li.fs-sep{color:var(--fs-mute);font-size:12.5px;font-weight:700;padding-top:10px;border-top:0}
.fs-strip.fs-strip4{grid-template-columns:repeat(4,minmax(0,1fr))}.fs-cell small{display:block;font-size:12px;margin-top:1px}.fs-cell.fs-soon{background:#f8f9fb;border-style:dashed}
.fs-scroll .fs-flowtab td:nth-child(2){white-space:normal;min-width:170px}.fs-owntab td:first-child{min-width:0}.fs-barcell{width:34%;white-space:nowrap}.fs-bar{display:inline-block;height:9px;border-radius:5px;vertical-align:middle;margin-right:6px;max-width:62%}.fs-fchart{display:block;width:100%;height:210px}.fs-fax{display:flex;justify-content:space-between;font-size:12px;color:var(--fs-mute);margin:4px 0}.fs-bup{background:#ffd8c2}.fs-bdn{background:#cfe0ff}.fs-barcell b{font-size:12.5px}
@media (max-width:600px){.fs-flowtab:not(.fs-streak) th:nth-child(4),.fs-flowtab:not(.fs-streak) td:nth-child(4),.fs-flowtab:not(.fs-streak) th:nth-child(5),.fs-flowtab:not(.fs-streak) td:nth-child(5),.fs-owntab th:nth-child(2),.fs-owntab td:nth-child(2){display:none}.fs-flowtab td,.fs-flowtab th,.fs-owntab td,.fs-owntab th{padding-left:4px!important;padding-right:4px!important}.fs-scroll .fs-flowtab td:nth-child(2){min-width:0}.fs-streak td:nth-child(4){font-size:13px}.fs-from{display:none}.fs-streak th{white-space:normal!important}.fs-fchart{height:150px}.fs-barcell{width:auto}.fs-bar{display:none}}
@media (max-width:340px){.fs-flowtab .fs-code,.fs-owntab .fs-code{display:none}}
@media (max-width:600px){.fs-skhytab th:nth-child(3),.fs-skhytab td:nth-child(3),.fs-skhytab th:nth-child(4),.fs-skhytab td:nth-child(4){display:none}.fs-skhytab td,.fs-skhytab th{padding-left:4px!important;padding-right:4px!important}}
.fs-cell>span a{color:inherit;text-decoration:none}
@media (max-width:380px){.fs-lt-most-foreign-owned th:nth-child(4),.fs-lt-most-foreign-owned td:nth-child(4),.fs-lt-largest-kosdaq th:nth-child(4),.fs-lt-largest-kosdaq td:nth-child(4){display:none}}
@media (max-width:600px){.fs-listtab td,.fs-listtab th{padding-left:4px!important;padding-right:4px!important}.fs-listtab .fs-ind{white-space:normal}.fs-listtab td.fs-num{font-size:13px}}
@media (max-width:600px){.fs-lt-highest-dividend-yield th:nth-child(3),.fs-lt-highest-dividend-yield td:nth-child(3),.fs-lt-highest-dividend-yield th:nth-child(5),.fs-lt-highest-dividend-yield td:nth-child(5),.fs-lt-highest-dividend-yield th:nth-child(6),.fs-lt-highest-dividend-yield td:nth-child(6),.fs-lt-highest-dividend-yield th:nth-child(7),.fs-lt-highest-dividend-yield td:nth-child(7),.fs-lt-most-foreign-owned th:nth-child(5),.fs-lt-most-foreign-owned td:nth-child(5),.fs-lt-cheapest-by-pb th:nth-child(4),.fs-lt-cheapest-by-pb td:nth-child(4),.fs-lt-cheapest-by-pb th:nth-child(6),.fs-lt-cheapest-by-pb td:nth-child(6),.fs-lt-largest-kosdaq th:nth-child(3),.fs-lt-largest-kosdaq td:nth-child(3){display:none}.fs-listtab td:nth-child(2){min-width:0!important}}
@media (max-width:600px){.fs-list th:nth-child(3),.fs-list td:nth-child(3),.fs-list th:nth-child(6),.fs-list td:nth-child(6){display:none}
.fs-scroll .fs-list td:nth-child(2){white-space:normal}.fs-search kbd{display:none}.fs-tabs{flex-wrap:wrap;overflow:visible}.fs-tabs a{padding:7px 9px}}
@media (max-width:820px){.fs-two,.fs-stats,.fs-cards{grid-template-columns:1fr}.fs-strip,.fs-strip.fs-strip4{grid-template-columns:repeat(2,minmax(0,1fr))}.fs-price{font-size:30px}.fs-head h1{font-size:25px}}
CSS;

const FS_JS = <<<'JS'
(function(){var box=document.getElementById('fs-q'),res=document.getElementById('fs-res');if(!box||!res)return;
var src=box.getAttribute('data-src')||'/wp-json/fermata/v1/stock-index',key='fs-idx:'+src,data=null,loading=false,waiting=[],sel=-1;
function note(t){res.textContent='';var e=document.createElement('li');e.style.cssText='padding:9px 12px;color:#8b95a1';e.textContent=t;res.appendChild(e);res.hidden=false}
function load(cb){if(data)return cb();try{var c=sessionStorage.getItem(key);if(c){data=JSON.parse(c);if(data)return cb();}}catch(e){}
waiting.push(cb);if(loading)return;loading=true;
fetch(src).then(function(r){if(!r.ok)throw r.status;return r.json()}).then(function(j){data=Array.isArray(j)?j:[];try{sessionStorage.setItem(key,JSON.stringify(data))}catch(e){}})
.catch(function(){data=null}).then(function(){loading=false;var w=waiting;waiting=[];if(!data){note('Search is unavailable right now — try again');return}w.forEach(function(f){f()})})}
function show(){var q=box.value.trim().toLowerCase();if(!q){res.hidden=true;return}if(!data){note('Loading…');return}
var out=[];for(var i=0;i<data.length&&out.length<8;i++){var r=data[i];if(r[0].toLowerCase().indexOf(q)===0||r[1].toLowerCase().indexOf(q)>-1)out.push(r)}
sel=Math.min(sel,out.length-1);res.textContent='';if(!out.length){note('No match');return}
out.forEach(function(r,i){var li=document.createElement('li'),a=document.createElement('a'),b=document.createElement('b'),n=document.createElement('span'),c=document.createElement('span');
a.setAttribute('href','/stocks/'+r[0]+'/');if(i===sel)a.className='on';b.textContent=r[1];n.appendChild(b);c.style.color='#8b95a1';c.textContent=r[0]+' · '+r[2];a.appendChild(n);a.appendChild(c);li.appendChild(a);res.appendChild(li)});res.hidden=false}
function warm(){load(function(){})}
box.addEventListener('input',function(){sel=-1;show();load(show)});box.addEventListener('focus',warm);box.addEventListener('pointerenter',warm);
box.addEventListener('keydown',function(e){if(e.key==='Escape'){res.hidden=true;return}if(!data)return;var a=res.querySelectorAll('a');
if(e.key==='ArrowDown'){sel=Math.min(sel+1,a.length-1);show();e.preventDefault()}else if(e.key==='ArrowUp'){sel=Math.max(sel-1,0);show();e.preventDefault()}
else if(e.key==='Enter'&&a.length){e.preventDefault();location.href=a[Math.max(sel,0)].getAttribute('href')}});
document.addEventListener('keydown',function(e){if(e.key==='/'&&document.activeElement!==box&&!/input|textarea/i.test(document.activeElement.tagName)){box.focus();e.preventDefault()}});
document.addEventListener('click',function(e){if(!e.target.closest('.fs-search'))res.hidden=true});})();
JS;

// ── 글 속 종목 이름 → 종목 페이지 (2026-09-28) ─────────────────────
// 영어 시황·가이드 본문에 나온 종목 이름을 처음 한 번만 /stocks/<코드>/로 잇는다. 워드프레스가 글을 그릴 때 붙이므로 이미 올라간
// 글에도 다시 발행 없이 걸린다. 엉뚱한 연결이 가장 큰 위험이다 — 영어 낱말과 같은 이름(Solid·Union·Russell 2000의 Russell)과
// 그룹 이름(Lotte·Hanwha·Doosan — 글에서는 대개 그룹 전체를 말한다)은 잇지 않는다. 한 낱말 이름은 시가총액 300위 안만.
const FS_LINK_EXCLUDE = array( 'acryl', 'alchera', 'alt', 'artist', 'asta', 'auk', 'auto', 'barrel', 'biodyne', 'booster', 'caelum', 'cap', 'carry', 'daewoo', 'dap', 'device', 'di', 'dit', 'doosan', 'dual', 'ecopro', 'encell', 'episode', 'esteem', 'eugene', 'finger', 'flask', 'freet', 'genic', 'genome', 'graphy', 'handsome', 'hankook', 'hanwha', 'hyosung', 'hyper', 'hyundai', 'ich', 'igloo', 'incross', 'kolon', 'kumbi', 'lemon', 'linked', 'lotte', 'mercury', 'mico', 'mot', 'nable', 'neptune', 'nexus', 'nine', 'orion', 'paradise', 'pavonine', 'photon', 'pie', 'posco', 'ray', 'refine', 'russell', 'samsung', 'sec', 'shinsegae', 'solid', 'solum', 'sphere', 'union', 'unison', 'ust', 'vessel', 'wiz', 'wot', 'yas', 'yest', 'ym', 'zeus' );
const FS_LINK_SHORT_OK = array( 'Kia', 'HMM' );   // 4자 미만인데 글에 자주 나오고 헷갈릴 일이 없는 이름
const FS_LINK_MAX = 15;

function fs_link_build( $index ) {
	$map = array();
	foreach ( array_values( $index ) as $rank => $r ) {
		$name = trim( (string) $r[1] );
		if ( '' === $name || false !== strpos( $name, '(' ) || isset( $map[ $name ] ) ) { continue; }   // 우선주는 잇지 않는다
		$single = false === strpos( $name, ' ' );
		if ( in_array( strtolower( $name ), FS_LINK_EXCLUDE, true ) ) { continue; }
		if ( $single && ! in_array( $name, FS_LINK_SHORT_OK, true ) && ( $rank >= 300 || strlen( $name ) < 4 ) ) { continue; }
		if ( ! $single && strlen( $name ) < 5 ) { continue; }
		$map[ $name ] = $r[0];
	}
	$names = array_keys( $map );
	usort( $names, function ( $a, $b ) { return strlen( $b ) - strlen( $a ); } );   // 긴 이름 먼저 — "Ecopro BM"이 "Ecopro"보다 먼저
	$alts = array_map( function ( $n ) { return preg_quote( $n, '/' ); }, $names );
	return array( 're' => $alts ? '/(?<![\\w&\\-])(' . implode( '|', $alts ) . ')(?![\\w&\\-])(?! Group\\b)/u' : '', 'map' => $map );
}

function fs_link_apply( $html, $built, $max = FS_LINK_MAX ) {
	if ( empty( $built['re'] ) ) { return $html; }
	$parts = preg_split( '/(<[^>]+>)/', $html, -1, PREG_SPLIT_DELIM_CAPTURE );
	$skip = 0; $done = array(); $count = 0;
	foreach ( $parts as $i => $part ) {
		if ( '' === $part ) { continue; }
		if ( '<' === $part[0] ) {
			if ( preg_match( '#^<(/?)(a|h[1-6]|script|style|svg|button|figcaption|title|textarea)\b#i', $part, $m ) ) {
				$skip += ( '/' === $m[1] ) ? -1 : 1;
				if ( $skip < 0 ) { $skip = 0; }
			}
			continue;
		}
		if ( $skip > 0 || $count >= $max ) { continue; }
		$parts[ $i ] = preg_replace_callback( $built['re'], function ( $m ) use ( $built, &$done, &$count, $max ) {
			$code = $built['map'][ $m[1] ];
			if ( isset( $done[ $code ] ) || $count >= $max ) { return $m[0]; }
			$done[ $code ] = true; $count++;
			return '<a class="fs-stock-link" href="/stocks/' . $code . '/">' . $m[1] . '</a>';
		}, $part );
	}
	return implode( '', $parts );
}

// ── 워드프레스에 붙이기 ──────────────────────────────────────────────────────────────
if ( ! function_exists( 'add_action' ) ) { return; }   // 이 맥의 PHP 검사에서는 여기까지만 읽는다

function fs_page_id() { $p = get_page_by_path( 'stocks' ); return $p ? (int) $p->ID : 0; }
function fs_current_code() { $c = strtoupper( (string) get_query_var( 'fm_code' ) ); return preg_match( '/^[0-9][0-9A-Z]{5}$/', $c ) ? $c : ''; }
function fs_stock( $code ) { $s = get_option( 'fm_s_' . $code ); return is_array( $s ) ? $s : null; }
function fs_index() { $i = get_option( 'fm_stock_index' ); return is_array( $i ) ? $i : array(); }
function fs_lists() { $l = get_option( 'fm_lists' ); return is_array( $l ) ? $l : array(); }
function fs_flows() { $f = get_option( 'fm_flows' ); return ( is_array( $f ) && ! empty( $f['date'] ) ) ? $f : null; }
function fs_skhy() { $p = get_option( 'fm_skhy' ); return ( is_array( $p ) && ! empty( $p['rows'] ) ) ? $p : null; }
function fs_is_skhy() { return '1' === (string) get_query_var( 'fm_skhy' ); }
function fs_is_flows() { return '1' === (string) get_query_var( 'fm_flows' ); }
function fs_current_list() { $l = (string) get_query_var( 'fm_list' ); $all = fs_lists(); return ( preg_match( '/^[a-z0-9-]+$/', $l ) && isset( $all[ $l ] ) ) ? $l : ''; }
// 검색창이 받는 목록은 고정 파일로 — REST로 받으면 방문자마다 워드프레스가 돌고(0.5~0.8초) 첫 검색이 비었다(2026-09-27 버튼 점검)
function fs_index_file() { $u = wp_upload_dir(); return array( $u['basedir'] . '/fermata/stock-index.json', $u['baseurl'] . '/fermata/stock-index.json' ); }
function fs_index_write( $index ) {
	list( $path ) = fs_index_file();
	wp_mkdir_p( dirname( $path ) );
	$rows = array(); foreach ( $index as $r ) { $rows[] = array( $r[0], $r[1], $r[2] ); }
	return false !== file_put_contents( $path, wp_json_encode( $rows ) );
}
function fs_index_url() {
	list( $path, $url ) = fs_index_file();
	if ( ! file_exists( $path ) && fs_index() ) { fs_index_write( fs_index() ); }
	return file_exists( $path ) ? set_url_scheme( $url, 'relative' ) . '?v=' . filemtime( $path ) : '/wp-json/fermata/v1/stock-index';
}

add_action( 'init', function () {
	add_rewrite_rule( '^stocks/lists/([a-z0-9-]+)/?$', 'index.php?pagename=stocks&fm_list=$matches[1]', 'top' );
	add_rewrite_rule( '^stocks/foreign-flows/?$', 'index.php?pagename=stocks&fm_flows=1', 'top' );
	add_rewrite_rule( '^stocks/skhy-premium/?$', 'index.php?pagename=stocks&fm_skhy=1', 'top' );
	add_rewrite_rule( '^stocks/([0-9][0-9A-Za-z]{5})/?$', 'index.php?pagename=stocks&fm_code=$matches[1]', 'top' );
	if ( get_option( 'fm_stock_rewrite' ) !== '6' ) { flush_rewrite_rules( false ); update_option( 'fm_stock_rewrite', '6' ); }   // '6': SKHY 프리미엄 주소 // '5': 외국인 수급 주소 // '4': 순위표 주소(2026-09-28)   // '3': Rank Math 사이트맵을 끈 뒤 한 번 더(2026-09-28)
} );
add_filter( 'query_vars', function ( $v ) { $v[] = 'fm_code'; $v[] = 'fm_list'; $v[] = 'fm_flows'; $v[] = 'fm_skhy'; return $v; } );
// IndexNow(빙) 열쇠 파일 — 사이트 주인 확인용 공개 값(src/indexnow.py의 KEY와 같아야 한다, 2026-09-28)
const FS_INDEXNOW_KEY = 'f388cd4cbbadc90870c3c0fb1dfdc730';
add_action( 'parse_request', function () {
	if ( isset( $_SERVER['REQUEST_URI'] ) && strtok( $_SERVER['REQUEST_URI'], '?' ) === '/' . FS_INDEXNOW_KEY . '.txt' ) {
		status_header( 200 ); header( 'Content-Type: text/plain; charset=utf-8' ); echo FS_INDEXNOW_KEY; exit;
	}
}, 0 );
// 워드프레스가 /stocks/000660/을 페이지 주소 /stocks/로 '바로잡아' 넘기지 않게
add_filter( 'redirect_canonical', function ( $url ) { return ( fs_current_code() || get_query_var( 'fm_list' ) || fs_is_flows() || fs_is_skhy() ) ? false : $url; } );

add_action( 'rest_api_init', function () {
	register_rest_route( 'fermata/v1', '/stocks', array( 'methods' => 'POST', 'permission_callback' => function () { return current_user_can( 'edit_posts' ); },
		'callback' => function ( $req ) {
			$body = $req->get_json_params(); $saved = 0;
			foreach ( ( isset( $body['items'] ) ? $body['items'] : array() ) as $it ) {
				$code = strtoupper( (string) ( isset( $it['code'] ) ? $it['code'] : '' ) );
				if ( ! preg_match( '/^[0-9A-Z]{6}$/', $code ) || ! is_array( $it['data'] ) ) { continue; }
				$data = $it['data']; $old = get_option( 'fm_s_' . $code );
				if ( ! empty( $it['merge'] ) && is_array( $old ) ) { $data = array_merge( $old, $data ); }
				update_option( 'fm_s_' . $code, $data, false ); $saved++;
			}
			$out = array( 'saved' => $saved );
			if ( isset( $body['delete'] ) && is_array( $body['delete'] ) ) {   // 상장폐지·제외 종목
				$out['deleted'] = 0;
				foreach ( $body['delete'] as $code ) { $code = strtoupper( (string) $code ); if ( preg_match( '/^[0-9A-Z]{6}$/', $code ) && delete_option( 'fm_s_' . $code ) ) { $out['deleted']++; } }
			}
			// 목록은 한 번에 못 보낸다(카페24가 큰 요청을 끊는다) — 나눠 받아 _next에 쌓고, 마지막 조각의 index_total과 줄 수가 맞을 때만 바꾼다
			if ( isset( $body['index_part'] ) && is_array( $body['index_part'] ) ) {
				$next = ! empty( $body['index_reset'] ) ? array() : get_option( 'fm_stock_index_next', array() );
				$next = array_merge( is_array( $next ) ? $next : array(), $body['index_part'] );
				update_option( 'fm_stock_index_next', $next, false );
				$out['index_next'] = count( $next );
				$total = isset( $body['index_total'] ) ? (int) $body['index_total'] : 0;
				if ( $total && $total === count( $next ) ) { update_option( 'fm_stock_index', $next, false ); delete_option( 'fm_stock_index_next' ); $out['index'] = $total; $out['index_file'] = fs_index_write( $next ); delete_transient( 'fs_link_v1' ); }
			}
			if ( isset( $body['list']['slug'], $body['list']['data'] ) && preg_match( '/^[a-z0-9-]+$/', $body['list']['slug'] ) && is_array( $body['list']['data'] ) ) {
				$all = fs_lists(); $all[ $body['list']['slug'] ] = $body['list']['data'];
				update_option( 'fm_lists', $all, false ); $out['list'] = $body['list']['slug'];
			}
			if ( isset( $body['skhy']['rows'] ) && is_array( $body['skhy']['rows'] ) ) { update_option( 'fm_skhy', $body['skhy'], false ); $out['skhy'] = $body['skhy']['date']; }
			if ( isset( $body['flows']['date'] ) && is_array( $body['flows'] ) ) { update_option( 'fm_flows', $body['flows'], false ); $out['flows'] = $body['flows']['date']; }
			if ( isset( $body['market'] ) && is_array( $body['market'] ) ) { update_option( 'fm_market', $body['market'], false ); $out['market'] = true; }
			return $out;
		} ) );
	// 진단(관리자만): 필터를 거치지 않은 DB 값 — Rank Math 기능 목록·플러그인 자동 업데이트·Rank Math 버전(2026-09-28 Rank Math 사이트맵이 다시 켜진 일)
	register_rest_route( 'fermata/v1', '/diag', array( 'methods' => 'GET', 'permission_callback' => function () { return current_user_can( 'manage_options' ); },
		'callback' => function () {
			global $wpdb;
			$raw = $wpdb->get_var( $wpdb->prepare( "SELECT option_value FROM {$wpdb->options} WHERE option_name = %s", 'rank_math_modules' ) );
			return array(
				'rank_math_modules_raw' => maybe_unserialize( $raw ),
				'rank_math_modules_filtered' => get_option( 'rank_math_modules' ),
				'auto_update_plugins' => get_site_option( 'auto_update_plugins', array() ),
				'rank_math_version' => defined( 'RANK_MATH_VERSION' ) ? RANK_MATH_VERSION : null,
				'rank_math_db_version' => get_option( 'rank_math_db_version' ),
				'rank_math_install_date' => get_option( 'rank_math_install_date' ),
				'wp_sitemaps_enabled' => (bool) apply_filters( 'wp_sitemaps_enabled', (bool) get_option( 'blog_public' ) ),
				'rank_math_tables' => $wpdb->get_results( $wpdb->prepare( "SELECT table_name AS t, table_rows AS n, ROUND((data_length+index_length)/1048576,1) AS mb FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name LIKE %s", $wpdb->esc_like( $wpdb->prefix . 'rank_math' ) . '%' ) ),
				'rank_math_option_names' => $wpdb->get_col( "SELECT option_name FROM {$wpdb->options} WHERE option_name LIKE 'rank\\_math\\_%' ORDER BY option_name" ),
				'rank_math_redirections' => $wpdb->get_results( "SELECT id, sources, url_to, header_code, status, hits FROM {$wpdb->prefix}rank_math_redirections" ),
				'db_total_mb' => $wpdb->get_var( "SELECT ROUND(SUM(data_length+index_length)/1048576,1) FROM information_schema.tables WHERE table_schema = DATABASE()" ),
			);
		} ) );
	register_rest_route( 'fermata/v1', '/stock-index', array( 'methods' => 'GET', 'permission_callback' => '__return_true',
		'callback' => function () {
			$rows = array(); foreach ( fs_index() as $r ) { $rows[] = array( $r[0], $r[1], $r[2] ); }
			$res = new WP_REST_Response( $rows ); $res->header( 'Cache-Control', 'public, max-age=3600' ); return $res;
		} ) );
} );

// 없는 종목 코드는 404
add_action( 'template_redirect', function () {
	$code = fs_current_code();
	$bad_list = ( get_query_var( 'fm_list' ) && ! fs_current_list() ) || ( fs_is_flows() && ! fs_flows() ) || ( fs_is_skhy() && ! fs_skhy() );
	if ( ( $code && ! fs_stock( $code ) ) || $bad_list ) { global $wp_query; $wp_query->set_404(); status_header( 404 ); nocache_headers(); }
} );

add_filter( 'the_content', function ( $content ) {
	if ( ! is_page( 'stocks' ) || get_the_ID() !== get_queried_object_id() ) { return $content; }
	$code = fs_current_code(); $index = fs_index(); $lists = fs_lists();
	if ( $slug = fs_current_list() ) { return fs_list_html( $slug, $lists[ $slug ], $lists ); }
	if ( fs_is_flows() && ( $f = fs_flows() ) ) { return fs_flows_html( $f ); }
	if ( fs_is_skhy() && ( $k = fs_skhy() ) ) { return fs_skhy_html( $k ); }
	if ( $code && ( $s = fs_stock( $code ) ) ) {
		$by = array(); foreach ( $index as $r ) { $by[ $r[0] ] = $r; }
		$related = array();
		$qry = new WP_Query( array( 'post_type' => 'post', 'post_status' => 'publish', 's' => $s['name'], 'posts_per_page' => 5, 'category__in' => array( 121, 153 ), 'no_found_rows' => true ) );
		foreach ( $qry->posts as $p ) { $related[] = array( 'title' => html_entity_decode( get_the_title( $p ), ENT_QUOTES, 'UTF-8' ), 'url' => get_permalink( $p ) ); }
		return fs_stock_html( $s, $by, $related, $lists, '000660' === $code ? fs_skhy() : null );
	}
	$m = isset( $_GET['m'] ) ? strtolower( sanitize_text_field( wp_unslash( $_GET['m'] ) ) ) : '';
	$pg = isset( $_GET['pg'] ) ? (int) $_GET['pg'] : 1;
	return $index ? fs_index_html( $index, in_array( $m, array( 'kospi', 'kosdaq' ), true ) ? $m : '', $pg, 100, $lists, fs_flows(), fs_skhy() ) : '<p>Stock data is loading. Please check back after the next Korean market close.</p>';
}, 99 );   // wpautop(10) 뒤 — 앞에 두면 그린 표에 <p>·<br>이 끼어든다

// 영어 시황(121·684·685)과 가이드(153) 본문에서 종목 이름을 잇는다 — 목록이 바뀌면 다시 만든다(REST가 transient를 지운다)
add_filter( 'the_content', function ( $content ) {
	if ( is_admin() || ! is_singular( 'post' ) || ! in_the_loop() || ! is_main_query() || ! in_category( array( 121, 684, 685, 153 ) ) ) { return $content; }
	$built = get_transient( 'fs_link_v1' );
	if ( ! is_array( $built ) ) { $built = fs_link_build( fs_index() ); set_transient( 'fs_link_v1', $built, DAY_IN_SECONDS ); }
	return fs_link_apply( $content, $built );
}, 98 );

add_shortcode( 'fermata_market', function () { return fs_market_html( get_option( 'fm_market' ), fs_lists(), fs_flows(), fs_skhy() ); } );
add_shortcode( 'fermata_search', function () { return fs_search_box( count( fs_index() ) ); } );
add_shortcode( 'fermata_nav', function ( $a ) { $a = shortcode_atts( array( 'active' => '' ), $a ); return fs_nav( $a['active'] ); } );
// 'fermata-hub' 틀을 쓰는 페이지 — 메뉴 줄 CSS가 여기에 필요하다
function fs_hub_view() { return is_front_page() || is_page( array( 'stocks', 76, 77, 105 ) ); }

// 제목·설명·주소(Rank Math가 그리는 머리)
function fs_meta_title() {
	if ( fs_is_skhy() && ( $k = fs_skhy() ) ) { return 'SKHY vs SK Hynix: Nasdaq ADR Premium to Seoul Shares (' . date( 'M j', strtotime( $k['date'] ) ) . ') | Fermata'; }
	if ( fs_is_flows() && ( $f = fs_flows() ) ) { return 'What Foreign Investors Bought and Sold in Korean Stocks (' . date( 'M j', strtotime( $f['date'] ) ) . ') | Fermata'; }
	if ( $l = fs_current_list() ) { $x = fs_lists()[ $l ]; return $x['title'] . ' (' . date( 'Y', strtotime( $x['date'] ) ) . ') | Fermata'; }
	$code = fs_current_code(); if ( ! $code || ! ( $s = fs_stock( $code ) ) ) { return is_page( 'stocks' ) ? 'Korean Stocks: All KOSPI and KOSDAQ Companies by Market Cap | Fermata' : null; }
	return $s['name'] . ' (' . $code . ') Stock Price, Foreign Ownership & Financials | Fermata';
}
function fs_meta_desc() {
	if ( fs_is_skhy() && ( $k = fs_skhy() ) ) {
		$l = $k['rows'][ count( $k['rows'] ) - 1 ];
		return 'SKHY closed at $' . number_format( $l['usd'], 2 ) . ' on ' . fs_date( $l['d'] ) . ', ' . number_format( abs( $l['prem'] ), 1 ) . '% ' . ( $l['prem'] >= 0 ? 'above' : 'below' ) . ' SK Hynix\'s Seoul price per ADR. Daily premium since the Nasdaq listing, with the math.';
	}
	if ( fs_is_flows() && ( $f = fs_flows() ) ) {
		$nm = function ( $rows ) { return implode( ', ', array_map( function ( $r ) { return $r['name']; }, array_slice( $rows, 0, 3 ) ) ); };
		return 'Foreign net buying in Korean stocks on ' . fs_date( $f['date'] ) . ( null !== $f['kospi_eok'] ? ': KOSPI foreign net ' . ( $f['kospi_eok'] > 0 ? '+' : '' ) . fs_eok( $f['kospi_eok'] ) : '' ) . '. Bought most: ' . $nm( $f['buy'] ) . '. Sold most: ' . $nm( $f['sell'] ) . '. Updated every trading day.';
	}
	if ( $l = fs_current_list() ) { $x = fs_lists()[ $l ]; $top = array_slice( $x['rows'], 0, 3 ); return $x['short'] . ' among Korean stocks, updated after each close (' . fs_date( $x['date'] ) . '). Top: ' . implode( ', ', array_map( function ( $r ) { return $r['name']; }, $top ) ) . '.'; }
	$code = fs_current_code(); if ( ! $code || ! ( $s = fs_stock( $code ) ) ) { return is_page( 'stocks' ) ? 'Every stock on the Korea Exchange in English: prices, market caps, foreign ownership and investor flows, updated after each close.' : null; }
	$q = $s['q']; $fr = fs_foreign_own( $s );
	return $s['name'] . ' (KRX: ' . $code . ') closed at ₩' . number_format( (float) $q['close'] ) . ' on ' . fs_date( $q['date'] ) . '. Market cap ' . fs_big( $q['mcap'] )
		. ( $fr !== null ? ', foreign ownership ' . number_format( $fr, 2 ) . '%' : '' ) . '. Daily foreign and institutional flows, financials and peers.';
}
foreach ( array( 'rank_math/frontend/title', 'pre_get_document_title', 'rank_math/opengraph/facebook/og_title', 'rank_math/opengraph/twitter/title' ) as $hook ) {
	add_filter( $hook, function ( $t ) { $x = fs_meta_title(); return $x ? $x : $t; }, 99 );
}
foreach ( array( 'rank_math/frontend/description', 'rank_math/opengraph/facebook/og_description', 'rank_math/opengraph/twitter/description' ) as $hook ) {
	add_filter( $hook, function ( $t ) { $x = fs_meta_desc(); return $x ? $x : $t; }, 99 );
}
add_filter( 'rank_math/frontend/robots', function ( $r ) {
	if ( is_page( 'stocks' ) && ! fs_current_code() && ( ! empty( $_GET['pg'] ) || ! empty( $_GET['m'] ) ) ) { $r['index'] = 'noindex'; $r['follow'] = 'follow'; }
	return $r;
}, 99 );
function fs_canonical( $u ) {
	if ( $l = fs_current_list() ) { return home_url( '/stocks/lists/' . $l . '/' ); }
	if ( fs_is_flows() && fs_flows() ) { return home_url( '/stocks/foreign-flows/' ); }
	if ( fs_is_skhy() && fs_skhy() ) { return home_url( '/stocks/skhy-premium/' ); }
	$c = fs_current_code(); return ( $c && fs_stock( $c ) ) ? home_url( '/stocks/' . $c . '/' ) : $u;
}
add_filter( 'rank_math/frontend/canonical', 'fs_canonical', 99 );
add_filter( 'get_canonical_url', 'fs_canonical', 99 );

// Rank Math 사이트맵 기능은 언제나 끈다(2026-09-28) — 켜지면 /wp-sitemap.xml을 제 사이트맵으로 돌려보내 종목 사이트맵이 404가 된다.
// 9/12에 껐는데 9/28 다시 켜져 있었다(누가·왜 켰는지는 확인 못 함). Rank Math는 켜진 기능을 옵션 rank_math_modules에 두고
// 기능 이름은 'sitemap'이다(플러그인 1.0.279 소스 includes/helpers/class-conditional.php·module/class-manager.php에서 확인).
add_filter( 'option_rank_math_modules', function ( $modules ) {
	return is_array( $modules ) ? array_values( array_diff( $modules, array( 'sitemap' ) ) ) : $modules;
} );

// 사이트맵: 종목 페이지 전부
add_action( 'wp_sitemaps_init', function ( $sitemaps ) {
	if ( ! class_exists( 'FS_Stock_Sitemap' ) ) {
		class FS_Stock_Sitemap extends WP_Sitemaps_Provider {
			public function __construct() { $this->name = 'stocks'; $this->object_type = 'stocks'; }
			public function get_url_list( $page_num, $object_subtype = '' ) {
				$rows = array_slice( fs_index(), ( $page_num - 1 ) * 2000, 2000 ); $out = array();
				if ( 1 === (int) $page_num ) {
					foreach ( array_keys( fs_lists() ) as $k ) { $out[] = array( 'loc' => home_url( '/stocks/lists/' . $k . '/' ) ); }
					if ( fs_flows() ) { $out[] = array( 'loc' => home_url( '/stocks/foreign-flows/' ) ); }
					if ( fs_skhy() ) { $out[] = array( 'loc' => home_url( '/stocks/skhy-premium/' ) ); }
				}
				foreach ( $rows as $r ) { $out[] = array( 'loc' => home_url( '/stocks/' . $r[0] . '/' ) ); }
				return $out;
			}
			public function get_max_num_pages( $object_subtype = '' ) { return max( 1, (int) ceil( count( fs_index() ) / 2000 ) ); }
		}
	}
	$sitemaps->registry->add_provider( 'stocks', new FS_Stock_Sitemap() );
} );

// 모양 + 검색창 스크립트
add_action( 'wp_head', function () {
	// 메뉴 줄은 이제 모든 화면에 있다(2026-09-28 템플릿 통일) — 모양도 모든 화면에 싣는다. 글꼴(Pretendard)은 14번 조각이 싣는다
	echo '<style id="fermata-stock-db">' . FS_CSS . '</style>' . "\n";
}, 21 );
add_action( 'wp_footer', function () {
	if ( empty( $GLOBALS['fs_need_search_js'] ) ) { return; }
	wp_print_inline_script_tag( FS_JS );   // 글자로 script 태그를 쓰면 NinjaFirewall이 조각 저장을 403으로 막는다(2026-09-27)
} );
