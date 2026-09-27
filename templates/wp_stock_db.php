<?php
// 본진 한국 종목 데이터베이스 — /stocks/ 목록, /stocks/<종목코드>/ 종목 페이지, 홈의 검색창·시장 띠·카드 (2026-09-27, 사장님 "바로 정식버전으로 구현하자").
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
		$active = is_front_page() ? 'market' : ( is_page( 'stocks' ) ? 'stocks' : ( is_page( 76 ) ? 'daily' : ( is_page( 77 ) ? 'guides' : '' ) ) );
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
	$ph = 'Search ' . ( $count ? number_format( $count ) . ' ' : '' ) . 'Korean stocks — Samsung, SK Hynix, HYBE, 005930…';
	return '<div class="fs-search"><span aria-hidden="true">⌕</span><input type="search" id="fs-q" autocomplete="off" placeholder="'
		. fs_esc( $ph ) . '" aria-label="Search Korean stocks"><kbd>/</kbd><ul id="fs-res" hidden></ul></div>';
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

function fs_stock_html( $s, $index_by_code, $related = array() ) {
	$code = $s['code']; $name = $s['name']; $q = isset( $s['q'] ) ? $s['q'] : array();
	$r = isset( $s['r'] ) ? $s['r'] : array(); $c = isset( $s['c'] ) ? $s['c'] : array();
	$guide = isset( FS_GUIDES[ $code ] ) ? FS_GUIDES[ $code ] : FS_GUIDE_DEFAULT;
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
		array( 'Analysts (1–5)', fs_rating( isset( $c['rating'] ) ? $c['rating'] : null ) ),
		array( 'Price target', ( ! empty( $c['target'] ) && ! empty( $q['close'] ) ) ? fs_krw( $c['target'] ) . ' (' . fs_pct( ( $c['target'] / $q['close'] - 1 ) * 100, false ) . ')' : '–' ),
	);
	$last_flow = ! empty( $s['flows'] ) ? $s['flows'][0] : null;
	$rows2 = array(
		array( 'Volume', ( isset( $q['volume'] ) && $q['volume'] !== null ) ? number_format( $q['volume'] ) : '–' ),
		array( 'Trading value', fs_big( isset( $q['value'] ) ? $q['value'] : null ) ),
		array( 'Day’s range', ( isset( $r['low'] ) && $r['low'] ) ? fs_krw( $r['low'] ) . ' – ' . fs_krw( $r['high'] ) : '–' ),
		array( '52-week range', ( isset( $r['low52'] ) && $r['low52'] ) ? fs_krw( $r['low52'] ) . ' – ' . fs_krw( $r['high52'] ) : '–' ),
		array( 'Foreign ownership <span class="fs-kr">KR</span>', fs_x( isset( $r['foreign_ratio'] ) ? $r['foreign_ratio'] : null, '%' ) ),
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
	$h .= '<p class="fs-src">Data: Korea Exchange closing prices, investor flows and foreign ownership via Naver Finance; company information from DART (Financial Supervisory Service). Updated after each Korean market close'
		. ( ! empty( $s['detail_date'] ) ? '; ratios and flows as of ' . fs_date( $s['detail_date'] ) : '' ) . '. Delayed data, not investment advice.</p>';
	return '<div class="fs-page">' . $h . '</div>';
}

function fs_index_html( $index, $market, $page, $per = 100 ) {
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
	$h .= '</div><div class="fs-scroll"><table class="fs-t fs-list"><tr><th>#</th><th>Company</th><th>Market</th><th class="fs-num">Price</th><th class="fs-num">Day</th><th class="fs-num">Market cap</th></tr>';
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

function fs_market_html( $m ) {
	if ( ! is_array( $m ) || empty( $m['index'] ) ) { return ''; }
	$cell = function ( $label, $value ) { return '<div class="fs-cell"><span>' . $label . '</span><b>' . $value . '</b></div>'; };
	$k = $m['index']['KOSPI']; $q = $m['index']['KOSDAQ'];
	$h  = '<div class="fs-strip">';
	$h .= $cell( 'KOSPI · ' . date( 'M j', strtotime( $k['date'] ) ) . ' close', number_format( $k['close'], 2 ) . ' <small>' . fs_pct( $k['pct'], false ) . '</small>' );
	$h .= $cell( 'KOSDAQ', number_format( $q['close'], 2 ) . ' <small>' . fs_pct( $q['pct'], false ) . '</small>' );
	if ( ! empty( $m['usdkrw']['close'] ) ) { $h .= $cell( 'USD/KRW', number_format( $m['usdkrw']['close'], 1 ) . ' <small>' . fs_pct( $m['usdkrw']['pct'], false ) . '</small>' ); }
	if ( ! empty( $m['skhy'] ) ) { $h .= $cell( 'SKHY (Nasdaq) vs Seoul', fs_pct( $m['skhy']['premium_pct'], false ) . ' <small>premium</small>' ); }
	if ( isset( $k['foreign_net_eok'] ) ) { $h .= $cell( 'Foreign net, KOSPI', '<span class="' . ( $k['foreign_net_eok'] >= 0 ? 'fs-up' : 'fs-dn' ) . '">' . fs_eok( $k['foreign_net_eok'] ) . '</span>' ); }
	if ( ! empty( $m['next_holiday'] ) ) { $h .= $cell( 'Next KRX holiday', date( 'M j', strtotime( $m['next_holiday']['date'] ) ) . ' <small>' . fs_esc( $m['next_holiday']['name'] ) . '</small>' ); }
	$h .= '</div><div class="fs-cards">';
	$h .= '<div class="fs-card"><h2>Largest companies<a class="fs-more" href="/stocks/">All ' . number_format( array_sum( $m['counts'] ) ) . ' →</a></h2><table class="fs-t">';
	foreach ( $m['largest'] as $r ) { $h .= '<tr><td><a href="/stocks/' . $r['code'] . '/"><b>' . fs_esc( $r['name'] ) . '</b></a> <span class="fs-code">' . $r['code'] . '</span></td><td class="fs-num">' . fs_krw( $r['close'] ) . '</td><td class="fs-num">' . fs_pct( $r['pct'] ) . '</td></tr>'; }
	$h .= '</table></div><div class="fs-card"><h2>Movers</h2><ul class="fs-mv"><li class="fs-sep">Gainers</li>';
	foreach ( array_slice( $m['gainers'], 0, 4 ) as $r ) { $h .= '<li><a href="/stocks/' . $r['code'] . '/">' . fs_esc( $r['name'] ) . ( ! empty( $r['ipo'] ) ? ' <span class="fs-kr fs-ipo">New listing</span>' : '' ) . '</a>' . fs_pct( $r['pct'] ) . '</li>'; }
	$h .= '<li class="fs-sep">Losers</li>';
	foreach ( array_slice( $m['losers'], 0, 4 ) as $r ) { $h .= '<li><a href="/stocks/' . $r['code'] . '/">' . fs_esc( $r['name'] ) . '</a>' . fs_pct( $r['pct'] ) . '</li>'; }
	$h .= '</ul><p class="fs-mute fs-small">Stocks with at least ₩5B traded. Moves beyond the 30% daily limit are first-day listings, measured from the IPO price.</p></div><div class="fs-card"><h2>Foreign investors <span class="fs-kr">KR data</span></h2><ul class="fs-mv"><li class="fs-sep">Bought most</li>';
	foreach ( array_slice( $m['foreign_buy'], 0, 3 ) as $r ) { $h .= '<li><a href="/stocks/' . $r['code'] . '/">' . fs_esc( $r['name'] ) . '</a><b class="fs-up">+' . fs_big( $r['value'] ) . '</b></li>'; }
	$h .= '<li class="fs-sep">Sold most</li>';
	foreach ( array_slice( $m['foreign_sell'], 0, 3 ) as $r ) { $h .= '<li><a href="/stocks/' . $r['code'] . '/">' . fs_esc( $r['name'] ) . '</a><b class="fs-dn">' . fs_big( $r['value'] ) . '</b></li>'; }
	$h .= '</ul><p class="fs-mute fs-small">Net buying by foreign investors in KRW, ' . date( 'M j', strtotime( ! empty( $m['flow_date'] ) ? $m['flow_date'] : $m['date'] ) ) . ' — ' . number_format( isset( $m['flow_universe'] ) ? $m['flow_universe'] : 0 ) . ' stocks with flow data that day.</p></div></div>';
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
@media (max-width:820px){.fs-two,.fs-stats,.fs-cards{grid-template-columns:1fr}.fs-strip{grid-template-columns:repeat(2,minmax(0,1fr))}.fs-price{font-size:30px}.fs-head h1{font-size:25px}}
CSS;

const FS_JS = <<<'JS'
(function(){var box=document.getElementById('fs-q'),res=document.getElementById('fs-res');if(!box||!res)return;var data=null,sel=-1;
function load(cb){if(data)return cb();try{var c=sessionStorage.getItem('fs-idx');if(c){data=JSON.parse(c);return cb();}}catch(e){}
fetch('/wp-json/fermata/v1/stock-index').then(function(r){return r.json()}).then(function(j){data=j;try{sessionStorage.setItem('fs-idx',JSON.stringify(j))}catch(e){}cb()}).catch(function(){data=[];cb()});}
function show(){var q=box.value.trim().toLowerCase();if(!q){res.hidden=true;return}var out=[];for(var i=0;i<data.length&&out.length<8;i++){var r=data[i];if(r[0].toLowerCase().indexOf(q)===0||r[1].toLowerCase().indexOf(q)>-1)out.push(r)}
res.textContent='';if(!out.length){var e=document.createElement('li');e.style.cssText='padding:9px 12px;color:#8b95a1';e.textContent='No match';res.appendChild(e)}
out.forEach(function(r,i){var li=document.createElement('li'),a=document.createElement('a'),b=document.createElement('b'),n=document.createElement('span'),c=document.createElement('span');
a.setAttribute('href','/stocks/'+r[0]+'/');if(i===sel)a.className='on';b.textContent=r[1];n.appendChild(b);c.style.color='#8b95a1';c.textContent=r[0]+' · '+r[2];a.appendChild(n);a.appendChild(c);li.appendChild(a);res.appendChild(li)});res.hidden=false}
box.addEventListener('input',function(){sel=-1;load(show)});box.addEventListener('focus',function(){load(function(){})});
box.addEventListener('keydown',function(e){var a=res.querySelectorAll('a');if(e.key==='ArrowDown'){sel=Math.min(sel+1,a.length-1);show();e.preventDefault()}else if(e.key==='ArrowUp'){sel=Math.max(sel-1,0);show();e.preventDefault()}else if(e.key==='Enter'&&a.length){location.href=a[Math.max(sel,0)].getAttribute('href')}else if(e.key==='Escape'){res.hidden=true}});
document.addEventListener('keydown',function(e){if(e.key==='/'&&document.activeElement!==box&&!/input|textarea/i.test(document.activeElement.tagName)){box.focus();e.preventDefault()}});
document.addEventListener('click',function(e){if(!e.target.closest('.fs-search'))res.hidden=true});})();
JS;

// ── 워드프레스에 붙이기 ──────────────────────────────────────────────────────────────
if ( ! function_exists( 'add_action' ) ) { return; }   // 이 맥의 PHP 검사에서는 여기까지만 읽는다

function fs_page_id() { $p = get_page_by_path( 'stocks' ); return $p ? (int) $p->ID : 0; }
function fs_current_code() { $c = strtoupper( (string) get_query_var( 'fm_code' ) ); return preg_match( '/^[0-9][0-9A-Z]{5}$/', $c ) ? $c : ''; }
function fs_stock( $code ) { $s = get_option( 'fm_s_' . $code ); return is_array( $s ) ? $s : null; }
function fs_index() { $i = get_option( 'fm_stock_index' ); return is_array( $i ) ? $i : array(); }

add_action( 'init', function () {
	add_rewrite_rule( '^stocks/([0-9][0-9A-Za-z]{5})/?$', 'index.php?pagename=stocks&fm_code=$matches[1]', 'top' );
	if ( get_option( 'fm_stock_rewrite' ) !== '2' ) { flush_rewrite_rules( false ); update_option( 'fm_stock_rewrite', '2' ); }
} );
add_filter( 'query_vars', function ( $v ) { $v[] = 'fm_code'; return $v; } );
// 워드프레스가 /stocks/000660/을 페이지 주소 /stocks/로 '바로잡아' 넘기지 않게
add_filter( 'redirect_canonical', function ( $url ) { return fs_current_code() ? false : $url; } );

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
			// 목록은 한 번에 못 보낸다(카페24가 큰 요청을 끊는다) — 나눠 받아 _next에 쌓고, 마지막 조각의 index_total과 줄 수가 맞을 때만 바꾼다
			if ( isset( $body['index_part'] ) && is_array( $body['index_part'] ) ) {
				$next = ! empty( $body['index_reset'] ) ? array() : get_option( 'fm_stock_index_next', array() );
				$next = array_merge( is_array( $next ) ? $next : array(), $body['index_part'] );
				update_option( 'fm_stock_index_next', $next, false );
				$out['index_next'] = count( $next );
				$total = isset( $body['index_total'] ) ? (int) $body['index_total'] : 0;
				if ( $total && $total === count( $next ) ) { update_option( 'fm_stock_index', $next, false ); delete_option( 'fm_stock_index_next' ); $out['index'] = $total; }
			}
			if ( isset( $body['market'] ) && is_array( $body['market'] ) ) { update_option( 'fm_market', $body['market'], false ); $out['market'] = true; }
			return $out;
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
	if ( $code && ! fs_stock( $code ) ) { global $wp_query; $wp_query->set_404(); status_header( 404 ); nocache_headers(); }
} );

add_filter( 'the_content', function ( $content ) {
	if ( ! is_page( 'stocks' ) || get_the_ID() !== get_queried_object_id() ) { return $content; }
	$code = fs_current_code(); $index = fs_index();
	if ( $code && ( $s = fs_stock( $code ) ) ) {
		$by = array(); foreach ( $index as $r ) { $by[ $r[0] ] = $r; }
		$related = array();
		$qry = new WP_Query( array( 'post_type' => 'post', 'post_status' => 'publish', 's' => $s['name'], 'posts_per_page' => 5, 'category__in' => array( 121, 153 ), 'no_found_rows' => true ) );
		foreach ( $qry->posts as $p ) { $related[] = array( 'title' => html_entity_decode( get_the_title( $p ), ENT_QUOTES, 'UTF-8' ), 'url' => get_permalink( $p ) ); }
		return fs_stock_html( $s, $by, $related );
	}
	$m = isset( $_GET['m'] ) ? strtolower( sanitize_text_field( wp_unslash( $_GET['m'] ) ) ) : '';
	$pg = isset( $_GET['pg'] ) ? (int) $_GET['pg'] : 1;
	return $index ? fs_index_html( $index, in_array( $m, array( 'kospi', 'kosdaq' ), true ) ? $m : '', $pg ) : '<p>Stock data is loading. Please check back after the next Korean market close.</p>';
}, 99 );   // wpautop(10) 뒤 — 앞에 두면 그린 표에 <p>·<br>이 끼어든다

add_shortcode( 'fermata_market', function () { return fs_market_html( get_option( 'fm_market' ) ); } );
add_shortcode( 'fermata_search', function () { return fs_search_box( count( fs_index() ) ); } );
add_shortcode( 'fermata_nav', function ( $a ) { $a = shortcode_atts( array( 'active' => '' ), $a ); return fs_nav( $a['active'] ); } );
// 'fermata-hub' 틀을 쓰는 페이지 — 메뉴 줄 CSS가 여기에 필요하다
function fs_hub_view() { return is_front_page() || is_page( array( 'stocks', 76, 77, 105 ) ); }

// 제목·설명·주소(Rank Math가 그리는 머리)
function fs_meta_title() {
	$code = fs_current_code(); if ( ! $code || ! ( $s = fs_stock( $code ) ) ) { return is_page( 'stocks' ) ? 'Korean Stocks: All KOSPI and KOSDAQ Companies by Market Cap | Fermata' : null; }
	return $s['name'] . ' (' . $code . ') Stock Price, Foreign Ownership & Financials | Fermata';
}
function fs_meta_desc() {
	$code = fs_current_code(); if ( ! $code || ! ( $s = fs_stock( $code ) ) ) { return is_page( 'stocks' ) ? 'Every stock on the Korea Exchange in English: prices, market caps, foreign ownership and investor flows, updated after each close.' : null; }
	$q = $s['q']; $fr = isset( $s['r']['foreign_ratio'] ) ? $s['r']['foreign_ratio'] : null;
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
add_filter( 'rank_math/frontend/canonical', function ( $u ) { $c = fs_current_code(); return ( $c && fs_stock( $c ) ) ? home_url( '/stocks/' . $c . '/' ) : $u; }, 99 );
add_filter( 'get_canonical_url', function ( $u ) { $c = fs_current_code(); return ( $c && fs_stock( $c ) ) ? home_url( '/stocks/' . $c . '/' ) : $u; }, 99 );

// 사이트맵: 종목 페이지 전부
add_action( 'wp_sitemaps_init', function ( $sitemaps ) {
	if ( ! class_exists( 'FS_Stock_Sitemap' ) ) {
		class FS_Stock_Sitemap extends WP_Sitemaps_Provider {
			public function __construct() { $this->name = 'stocks'; $this->object_type = 'stocks'; }
			public function get_url_list( $page_num, $object_subtype = '' ) {
				$rows = array_slice( fs_index(), ( $page_num - 1 ) * 2000, 2000 ); $out = array();
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
	if ( ! fs_hub_view() ) { return; }   // 글꼴(Pretendard)은 14번 조각이 같은 화면에 싣는다
	echo '<style id="fermata-stock-db">' . FS_CSS . '</style>' . "\n";
}, 21 );
add_action( 'wp_footer', function () {
	if ( empty( $GLOBALS['fs_need_search_js'] ) ) { return; }
	wp_print_inline_script_tag( FS_JS );   // 글자로 script 태그를 쓰면 NinjaFirewall이 조각 저장을 403으로 막는다(2026-09-27)
} );
