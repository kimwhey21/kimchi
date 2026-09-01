"""[예시] 영문 외국인 순매매 표 페이지를 어떻게 만들지 보여주는 프로토타입.

발행하지 않습니다. 실제로 만들 때 어떤 모양이 되는지 눈으로 보려고 만든
스크립트이며, 오늘(2026-09-01) 이미 수집된 데이터를 그대로 씁니다.

왜 글이 아니라 페이지인가
-------------------------
시황 글은 하루 지나면 가치가 0이 되지만, 이런 표는 같은 주소에서 매일
갱신되면 사람들이 북마크하고 다시 옵니다. 그래서 워드프레스 **글(post)**이
아니라 **페이지(page)** 하나를 만들어 두고 매일 그 페이지의 본문만 갈아
끼우는 구조를 제안합니다 — add_series_nav.py가 이미 쓰고 있는 방식과 같습니다.

데이터는 새로 받지 않습니다
---------------------------
src/fetch_foreign_flows.py가 평일 16:00 한국장 실행에서 이미 워치리스트
10종목의 외국인 순매매량·보유율을 받아 price_data에 넣고 있습니다. 이 페이지는
그 값을 다시 쓰는 것이라 API 호출이 추가로 들지 않습니다.

추정치를 명시하는 이유
----------------------
네이버 금융이 주는 건 순매매 **수량**입니다. 종목마다 주가가 100배 넘게 차이
나서(에코프로 8.7만원 vs SK하이닉스 169.3만원) 수량만으로는 비교가 안 됩니다.
그래서 '수량 × 종가'로 대략의 금액을 계산해 정렬합니다. 실제 체결 금액이
아니므로 표에 estimate라고 밝힙니다.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "editorial" / "kr_2026-09-01.json"
OUT = ROOT / "output" / "foreign_flows_demo.html"

_CSS = """
:root{--mb-up:#e34948;--mb-down:#2a78d6;--mb-bg:#fafaf9;--mb-card:#fff;
--mb-border:#e5e3dd;--mb-text:#17171a;--mb-text-muted:#6b6a66}
*{box-sizing:border-box}
body{font-family:'Pretendard',-apple-system,BlinkMacSystemFont,sans-serif;
background:var(--mb-bg);color:var(--mb-text);max-width:820px;margin:0 auto;
padding:32px 20px 80px;line-height:1.7}
.mb-eyebrow{font-size:13px;color:var(--mb-text-muted);margin-bottom:8px}
h1{font-size:26px;font-weight:700;line-height:1.4;margin:0 0 10px}
.mb-lede{font-size:15px;color:var(--mb-text-muted);margin:0 0 24px}
.mb-strip{display:flex;gap:10px;flex-wrap:wrap;margin:0 0 22px}
.mb-chip{flex:1;min-width:150px;background:var(--mb-card);border:1px solid var(--mb-border);
border-radius:12px;padding:12px 14px}
.mb-chip .mb-label{font-size:12px;color:var(--mb-text-muted)}
.mb-chip .mb-value{font-size:19px;font-weight:700}
.mb-chip .mb-delta{font-size:13px;font-weight:600}
.mb-summary{background:var(--mb-card);border:1px solid var(--mb-border);border-radius:12px;
padding:16px 18px;margin:0 0 22px;font-size:15px}
.mb-summary strong{font-weight:700}
.mb-table-wrap{overflow-x:auto;margin:0 0 10px}
table{width:100%;min-width:640px;border-collapse:collapse}
th,td{padding:10px 12px;text-align:right;border-bottom:1px solid var(--mb-border);font-size:14px;
white-space:nowrap}
th{color:var(--mb-text-muted);font-weight:600;font-size:12px;border-bottom:1px solid #d9d7d0}
th:first-child,td:first-child{text-align:left;white-space:normal}
td.mb-up{color:var(--mb-up);font-weight:600}
td.mb-down{color:var(--mb-down);font-weight:600}
.mb-ticker{display:block;font-size:12px;color:var(--mb-text-muted)}
tr.mb-net-buy td:first-child{box-shadow:inset 3px 0 0 var(--mb-up)}
tr.mb-net-sell td:first-child{box-shadow:inset 3px 0 0 var(--mb-down)}
.mb-note{font-size:12px;color:var(--mb-text-muted);margin:14px 0 0}
footer{margin-top:40px;font-size:12px;color:var(--mb-text-muted);
border-top:1px solid var(--mb-border);padding-top:16px}
"""


def _fmt_signed(value: int) -> str:
    return f"{value:+,}"


def _cls(value: float) -> str:
    return "mb-up" if value > 0 else ("mb-down" if value < 0 else "")


def build(data: dict) -> str:
    price = data["price_data"]
    macro, watchlist = price["macro"], price["watchlist"]
    date = price["trading_date"]
    usdkrw = macro["USD/KRW"]["price"]

    rows = []
    for ticker, item in watchlist.items():
        net = item.get("foreign_net")
        if net is None:
            continue
        value_krw = net * item["price"]
        rows.append({**item, "ticker": ticker, "net": net, "value_krw": value_krw})
    rows.sort(key=lambda r: r["value_krw"], reverse=True)

    total = sum(r["value_krw"] for r in rows)
    bought = [r for r in rows if r["net"] > 0]
    sold = [r for r in rows if r["net"] < 0]

    chips = []
    for key in ("KS11", "KQ11", "USD/KRW"):
        m = macro[key]
        chips.append(
            f'<div class="mb-chip"><div class="mb-label">{m["name_en"]}</div>'
            f'<div class="mb-value">{m["price"]:,.2f}</div>'
            f'<div class="mb-delta {_cls(m["change_pct"])}">{m["change_pct"]:+.2f}%</div></div>'
        )

    body_rows = []
    for r in rows:
        krw_bn = r["value_krw"] / 1_000_000_000
        usd_m = r["value_krw"] / usdkrw / 1_000_000
        row_cls = "mb-net-buy" if r["net"] > 0 else "mb-net-sell"
        body_rows.append(
            f'<tr class="{row_cls}">'
            f'<td>{r["name_en"]}<span class="mb-ticker">{r["ticker"]}</span></td>'
            f'<td>₩{r["price"]:,.0f}</td>'
            f'<td class="{_cls(r["change_pct"])}">{r["change_pct"]:+.2f}%</td>'
            f'<td class="{_cls(r["net"])}">{_fmt_signed(r["net"])}</td>'
            f'<td class="{_cls(r["net"])}">₩{krw_bn:+,.1f}bn</td>'
            f'<td class="{_cls(r["net"])}">${usd_m:+,.1f}m</td>'
            f'<td>{r["foreign_ratio"]:.2f}%</td>'
            f"</tr>"
        )

    direction = "net sellers" if total < 0 else "net buyers"
    summary = (
        f'<div class="mb-summary">Across the ten stocks tracked here, foreign investors were '
        f"<strong>{direction} of about ₩{abs(total)/1_000_000_000:,.0f} billion "
        f"(${abs(total)/usdkrw/1_000_000:,.0f} million)</strong> on {date} — buying "
        f"{len(bought)} of them and selling {len(sold)}. The largest single move was "
        f'<strong>{rows[0]["name_en"] if total >= 0 else rows[-1]["name_en"]}</strong>.</div>'
    )

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Foreign Investor Flows in Korean Stocks</title>
<style>{_CSS}</style></head><body>
  <div class="mb-eyebrow">Updated daily after the Korean close · {date}</div>
  <h1>Foreign Investor Flows in Korean Stocks</h1>
  <p class="mb-lede">Who foreign investors bought and sold today, by stock, in English.
  Net share counts come straight from the exchange data; the won and dollar figures are
  estimates so that names at very different share prices can be compared.</p>
  <div class="mb-strip">{"".join(chips)}</div>
  {summary}
  <div class="mb-table-wrap"><table>
    <thead><tr>
      <th>Company</th><th>Close</th><th>Day</th><th>Foreign net (shares)</th>
      <th>Est. value</th><th>Est. USD</th><th>Foreign held</th>
    </tr></thead>
    <tbody>{"".join(body_rows)}</tbody>
  </table></div>
  <p class="mb-note">Estimated value is net shares multiplied by the closing price, not
  actual traded value. Coverage is the ten stocks on this site's watchlist, not the whole
  market. Foreign ownership is the percentage of shares outstanding held by foreign
  investors. Source: Naver Finance, {date} close.</p>
  <footer>For informational purposes only. Not investment advice.</footer>
</body></html>"""


def main() -> None:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    OUT.write_text(build(data), encoding="utf-8")
    print(f"완료: {OUT}")


if __name__ == "__main__":
    main()
