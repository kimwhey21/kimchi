"""검색되는 말 후보의 크기를 잰다 — 한 달에 몇 번 검색되는지(수요)와 그 말로 쓴 블로그 글이 몇 편인지(경쟁).

    python -m scripts.phrase_size "후보1" "후보2" "후보3"      # 고를 말부터 차례로
    python -m scripts.phrase_size --related "씨앗 낱말"         # 그 낱말의 연관 검색어를 검색 수 순으로 재어 준다
    python -m scripts.phrase_size --json "후보1" "후보2"

쓰는 자리: 「실험」 절의 검색되는 말 고르기(`docs/routine_magazine.md`·`routine_column.md`).
넓은 말(글이 십만 편 안팎부터)로는 새 글이 앞에 서지 못하고, 찾는 사람이 없는 말은 앞에 서도 아무도 오지 않는다 —
**좁은 말 가운데 검색 수가 가장 많은 말**을 고른다(좁음에 없으면 보통에서).
원천은 둘 다 공식 API다(화면을 긁지 않는다): 경쟁 글 수는 NAVER API HUB 블로그 검색(`NAVER_CLIENT_ID`·`NAVER_CLIENT_SECRET`),
월 검색 수는 네이버 검색광고 키워드 도구(`SEARCHAD_CUSTOMER_ID`·`SEARCHAD_API_KEY`·`SEARCHAD_SECRET`). 환경변수에서 읽고,
이 맥에서는 `~/.market-brief-naver/naver_api.env`. 열쇠 값은 어디에도 찍지 않는다. 검색광고 열쇠가 없으면 경쟁만 재고 그렇다고 알린다.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://naverapihub.apigw.ntruss.com/search/v1/blog"
KEY_FILE = Path.home() / ".market-brief-naver" / "naver_api.env"
# 띠의 문턱(경쟁 글 수). 실측으로 정했다 — 내력은 비공개 기록. 바꿀 때는 그 뒤 올린 글의 순위를 다시 보고 바꾼다.
NARROW, MIDDLE = 15_000, 60_000
BANDS = ("좁음", "보통", "넓음")
# 한 번에 받는 건수. **30을 넘기지 않는다** — 100건을 한 번에 받으면 맨 앞 30건이 31~60번째로 밀려 나와 순위가 30씩 틀린다
# (2026-11-10 실측: 10건씩 세 쪽과 30건 한 쪽은 순서가 같고, 100건 한 번은 다르다).
PAGE = 30
AD_API, AD_URI = "https://api.searchad.naver.com", "/keywordstool"
MIN_SEARCHES = 100      # 월 검색이 이보다 적은 말은 앞에 서도 올 사람이 없다(잠정 — 순위 기록이 쌓이면 고친다)
RELATED_TOP = 15        # --related가 경쟁까지 재는 연관어 수(연관어마다 호출 한 번)


class NoKeys(RuntimeError):
    """열쇠가 없다 — 조용히 넘어가지 않고 알린다."""


def _env(names: tuple[str, ...]) -> tuple[str, ...]:
    vals = [os.environ.get(n, "") for n in names]
    if not all(vals) and KEY_FILE.exists():
        f = dict(line.strip().split("=", 1) for line in KEY_FILE.read_text(encoding="utf-8").splitlines() if "=" in line)
        vals = [os.environ.get(n) or f.get(n, "") for n in names]
    return tuple(vals)


def load_keys() -> tuple[str, str]:
    cid, sec = _env(("NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET"))
    if not (cid and sec):
        raise NoKeys("NAVER_CLIENT_ID·NAVER_CLIENT_SECRET가 없습니다 — 환경변수(루틴) 또는 ~/.market-brief-naver/naver_api.env(맥)")
    return cid, sec


def load_ad_keys() -> tuple[str, str, str] | None:
    """검색광고 열쇠(고객 번호, 액세스라이선스, 비밀키). 없으면 None — 부르는 쪽이 '검색 수는 못 쟀다'고 알린다."""
    vals = _env(("SEARCHAD_CUSTOMER_ID", "SEARCHAD_API_KEY", "SEARCHAD_SECRET"))
    return vals if all(vals) else None


def _norm(phrase: str) -> str:
    """키워드 도구의 표기: 띄어쓰기 없이, 로마자는 대문자."""
    return re.sub(r"\s+", "", phrase).upper()


def _count(v) -> int:
    """월 검색 수 칸. 10 미만은 문자열 '< 10'으로 온다 — 0으로 센다."""
    return v if isinstance(v, int) else 0


def keyword_tool(hints: list[str], ad_keys: tuple[str, str, str]) -> list[dict]:
    """키워드 도구 한 번(힌트 다섯 개까지). [{keyword, searches}] — searches는 PC+모바일 월 검색 수."""
    customer, api_key, secret = ad_keys
    ts = str(int(time.time() * 1000))
    sig = base64.b64encode(hmac.new(secret.encode(), f"{ts}.GET.{AD_URI}".encode(), hashlib.sha256).digest()).decode()
    url = AD_API + AD_URI + "?" + urllib.parse.urlencode({"hintKeywords": ",".join(_norm(h) for h in hints), "showDetail": 1})
    req = urllib.request.Request(url, headers={"X-Timestamp": ts, "X-API-KEY": api_key, "X-Customer": customer, "X-Signature": sig})
    with urllib.request.urlopen(req, timeout=30) as r:
        rows = json.loads(r.read()).get("keywordList") or []
    return [{"keyword": str(k.get("relKeyword", "")), "searches": _count(k.get("monthlyPcQcCnt")) + _count(k.get("monthlyMobileQcCnt"))} for k in rows]


def volumes(phrases: list[str], ad_keys: tuple[str, str, str]) -> dict[str, int]:
    """말마다 월 검색 수. 도구가 돌려주지 않은 말은 0(검색이 거의 없는 말)."""
    out: dict[str, int] = {}
    for i in range(0, len(phrases), 5):
        chunk = phrases[i:i + 5]
        got = {r["keyword"].upper(): r["searches"] for r in keyword_tool(chunk, ad_keys)}
        for p in chunk:
            out[p] = got.get(_norm(p), 0)
        time.sleep(0.5)
    return out


def related(seed: str, ad_keys: tuple[str, str, str]) -> list[dict]:
    """씨앗 낱말의 연관 검색어(씨앗의 낱말을 하나라도 품은 것만), 검색 수 많은 순."""
    tokens = [t.upper() for t in seed.split() if len(t) >= 2] or [_norm(seed)]
    rows = [r for r in keyword_tool([seed], ad_keys) if any(t in r["keyword"].upper() for t in tokens)]
    return sorted(rows, key=lambda r: -r["searches"])


def search(query: str, start: int = 1, display: int = PAGE, keys: tuple[str, str] | None = None) -> dict:
    """블로그 검색 한 쪽(관련도순). 실패는 예외로 올린다. display는 PAGE 이하로만 쓴다(위 PAGE 설명)."""
    cid, sec = keys or load_keys()
    url = API + "?" + urllib.parse.urlencode({"query": query, "display": display, "start": start, "sort": "sim"})
    req = urllib.request.Request(url, headers={"X-NCP-APIGW-API-KEY-ID": cid, "X-NCP-APIGW-API-KEY": sec})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def band(total: int) -> str:
    return BANDS[0] if total <= NARROW else BANDS[1] if total <= MIDDLE else BANDS[2]


def size(query: str, keys: tuple[str, str] | None = None) -> dict:
    """그 말의 경쟁 글 수와 띠."""
    total = int(search(query, display=1, keys=keys).get("total") or 0)
    return {"phrase": query, "total": total, "band": band(total)}


def rank(query: str, blog_pattern: str, depth: int = 300, keys: tuple[str, str] | None = None) -> dict:
    """그 말로 검색했을 때 `blog_pattern`(정규식, 블로그 주소에 대조)에 맞는 첫 글의 순위. depth 안에 없으면 rank는 None."""
    keys = keys or load_keys()
    pat, total = re.compile(blog_pattern), 0
    for start in range(1, depth + 1, PAGE):
        page = search(query, start=start, display=PAGE, keys=keys)
        total = int(page.get("total") or 0)
        items = page.get("items") or []
        for i, it in enumerate(items):
            if pat.search(str(it.get("link", ""))) or pat.search(str(it.get("bloggerlink", ""))):
                return {"phrase": query, "total": total, "band": band(total), "rank": start + i,
                        "title": re.sub(r"<[^>]+>", "", str(it.get("title", ""))), "link": str(it.get("link", ""))}
        if len(items) < PAGE:
            break
        time.sleep(0.15)
    return {"phrase": query, "total": total, "band": band(total), "rank": None, "title": "", "link": ""}


def pick(rows: list[dict]) -> dict | None:
    """고를 말: 월 검색이 MIN_SEARCHES를 넘는 말 가운데 좁음 띠에서 검색 수가 가장 많은 것, 좁음에 없으면 보통 띠에서.
    넓음 띠는 고르지 않는다. 검색 수를 못 쟀으면 None. (보통 띠의 검색 많은 말은 센 글이 몰려 있어 좁음을 먼저 본다.)"""
    for b in BANDS[:2]:
        ok = [r for r in rows if r["band"] == b and r.get("searches") is not None and r["searches"] >= MIN_SEARCHES]
        if ok:
            return max(ok, key=lambda r: (r["searches"], -r["total"]))
    return None


def _order(r: dict) -> tuple:
    return (BANDS.index(r["band"]), -(r.get("searches") or 0), r["total"])


def main(argv: list[str]) -> int:
    as_json, want_related = "--json" in argv, "--related" in argv
    phrases = [a for a in argv if not a.startswith("--")]
    if not phrases:
        print(__doc__.strip())
        return 2
    try:
        keys = load_keys()
    except NoKeys as e:
        print(f"⚠ {e}", file=sys.stderr)
        return 2
    ad_keys = load_ad_keys()
    failed: list[tuple[str, str]] = []
    vol: dict[str, int] = {}
    if want_related:
        if not ad_keys:
            print("⚠ --related는 검색광고 열쇠(SEARCHAD_*)가 있어야 합니다", file=sys.stderr)
            return 2
        seed = " ".join(phrases)
        try:
            rel = [r for r in related(seed, ad_keys) if r["searches"] >= MIN_SEARCHES]
        except (urllib.error.URLError, ValueError, TimeoutError) as e:
            print(f"⚠ 받지 못했습니다: 연관 검색어 ({type(e).__name__}: {e})", file=sys.stderr)
            return 3
        if len(rel) > RELATED_TOP:
            print(f"(연관 검색어 {len(rel)}개 중 검색 수 상위 {RELATED_TOP}개만 잽니다)")
        vol = {r["keyword"]: r["searches"] for r in rel[:RELATED_TOP]}
        phrases = list(vol)
        if not phrases:
            print(f"연관 검색어가 없습니다(월 검색 {MIN_SEARCHES}회 이상): {seed} — 새 이름·사건은 도구에 아직 없을 수 있습니다. 후보를 직접 적어 재 보십시오.")
            return 0
    elif ad_keys:
        try:
            vol = volumes(phrases, ad_keys)
        except (urllib.error.URLError, ValueError, TimeoutError) as e:
            failed.append(("월 검색 수", f"{type(e).__name__}: {e}"))
    rows = []
    for p in phrases:
        try:
            rows.append({**size(p, keys), "searches": vol.get(p) if vol else None})
        except (urllib.error.URLError, ValueError, TimeoutError) as e:
            failed.append((p, f"{type(e).__name__}: {e}"))
        if want_related:
            time.sleep(0.15)
    rows.sort(key=_order)
    best = pick(rows)
    if as_json:
        print(json.dumps({"rows": rows, "pick": best and best["phrase"], "failed": [p for p, _ in failed]}, ensure_ascii=False))
    else:
        for r in rows:
            s_txt = "      –" if r["searches"] is None else f"{r['searches']:>7,}"
            print(f"{r['band']}  월 검색 {s_txt}회  경쟁 글 {r['total']:>9,}편  {r['phrase']}")
        if not vol:
            print("(월 검색 수는 재지 못했습니다 — 검색광고 열쇠 SEARCHAD_*가 없습니다. 경쟁 글 수만으로 고르십시오.)")
            narrow = [r["phrase"] for r in rows if r["band"] == BANDS[0]]
            print(f"→ 좁은 말: {', '.join(narrow)}" if narrow else
                  "→ 좁은 말이 없습니다. 같은 이야기의 더 좁힌 말(이름+사건, 이름+제도, 낯선 고유명사)을 두세 개 더 재 보십시오.")
        elif best:
            print(f"→ 고를 말: {best['phrase']} (월 검색 {best['searches']:,}회 · 경쟁 글 {best['total']:,}편 · {best['band']})")
        elif rows:
            print(f"→ 고를 말이 없습니다 — 앞에 설 수 있는 말(좁음·보통) 가운데 월 검색 {MIN_SEARCHES}회를 넘는 것이 없습니다. "
                  "다른 꼴(이름+사건, 이름+제도)을 더 재거나 `--related \"씨앗\"`으로 사람들이 실제로 치는 꼴을 찾으십시오.")
    for p, why in failed:
        print(f"⚠ 받지 못했습니다: {p} ({why})", file=sys.stderr)
    return 3 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
