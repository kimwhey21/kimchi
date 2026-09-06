"""벤치마크 채널을 하루 한 번 훑어 새 글 본문을 모읍니다.

    python -m scripts.bench_watch            # 새 글 수집 + 요약 갱신
    python -m scripts.bench_watch --report   # 수집 없이 최근 목록만 출력
    python -m scripts.bench_watch --stats    # 모아 둔 본문의 구조 수치

목록 페이지는 로그인 없이도 읽힙니다. 잠긴 본문만 `scripts.bench_login`으로
저장해 둔 프로필의 세션이 필요합니다. 세션이 풀리면 새 글이 전부 '잠김'으로
잡히므로, 그때는 종료 코드 2로 끝내고 요약 맨 위에 그 사실을 적습니다.

수집물은 저장소가 아니라 `~/.market-brief-bench/`에 쌓입니다 — 유료 콘텐츠라
커밋하지 않습니다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import statistics
import sys
import time

from playwright.sync_api import sync_playwright

from scripts import bench_store as st

LIST_JS = """() => {
  const out = [];
  for (const li of document.querySelectorAll('li')) {
    const a = li.querySelector("a[href*='/contents/']");
    if (!a) continue;
    const m = a.getAttribute('href').match(/\\/contents\\/([0-9a-z]{12,})/);
    if (!m) continue;
    let title = '';
    for (const link of li.querySelectorAll("a[href*='/contents/']")) {
      const t = (link.innerText || '').trim();
      if (t.length > title.length) title = t;
    }
    out.push({id: m[1], title: title.replace(/\\s+/g, ' '),
              text: (li.innerText || '').replace(/\\s+/g, ' ').trim()});
  }
  return out;
}"""

BODY_JS = """() => {
  const root = document.querySelector('.se-main-container') || document.querySelector('#content') || document.body;
  const blocks = [];
  const walk = (el) => {
    for (const node of el.children) {
      const tag = node.tagName.toLowerCase();
      if (tag === 'img') { blocks.push({t:'img'}); }
      else if (tag === 'table') { blocks.push({t:'table', rows: node.querySelectorAll('tr').length}); }
      else if (/^h[1-6]$/.test(tag)) { blocks.push({t:'h', text: node.innerText.trim()}); }
      else if (node.querySelector('img, table')) { walk(node); }
      else {
        const txt = (node.innerText || '').trim();
        if (txt) {
          const cs = getComputedStyle(node);
          blocks.push({t:'p', text: txt,
                       strong: node.querySelectorAll('strong, b').length,
                       size: Math.round(parseFloat(cs.fontSize) || 0),
                       weight: cs.fontWeight});
        }
      }
    }
  };
  walk(root);
  return {title: document.title, blocks,
          locked: (document.body.innerText || '').includes('프리미엄 구독자 전용')};
}"""

_DATE = re.compile(r"(\d{4})\.(\d{2})\.(\d{2})\.")
_MINUTES = re.compile(r"완독 (\d+)분")
_SENTENCE_END = re.compile(r"(다|요)[.!?]?$")


def _parse_row(row: dict) -> dict:
    text = row["text"]
    date_m = _DATE.search(text)
    minutes_m = _MINUTES.search(text)
    category = text.split(" ")[0] if text else ""
    if row["title"] and text.startswith(row["title"]):
        category = ""
    else:
        head = text.split(row["title"])[0].strip() if row["title"] else ""
        category = head or category
    return {
        "id": row["id"],
        "title": row["title"],
        "category": category,
        "date": "-".join(date_m.groups()) if date_m else "",
        "minutes": int(minutes_m.group(1)) if minutes_m else None,
        "locked_in_list": "잠김" in text,
        "free": "무료" in text,
    }


def _summarize(doc: dict) -> dict:
    """소제목과 본문을 나눕니다.

    그쪽 편집기는 여러 문단을 `\n\n`으로 묶어 한 블록으로 내보내고, 소제목에는
    큰 글씨나 굵기를 주지 않습니다. 그래서 글자 크기로 소제목을 찾으면 하나도
    잡히지 않습니다 — **줄바꿈 없는 짧은 단독 블록**이 소제목입니다.
    """
    blocks = [b for b in doc["blocks"] if b["t"] == "p"]
    heads, texts = [], []
    for b in blocks:
        text = b["text"].strip()
        if not text or text == "\u200b":
            continue
        if "\n" not in text and len(text) <= 45:
            heads.append(text)
        else:
            texts += [x.strip() for x in text.split("\n") if x.strip() and x.strip() != "\u200b"]
    paras = texts
    sentences: list[str] = []
    for t in texts:
        for piece in re.split(r"(?<=[.!?])\s+|\n", t):
            piece = piece.strip()
            if piece and _SENTENCE_END.search(piece):
                sentences.append(piece)
    body = "".join(texts)
    return {
        "paragraphs": len(paras),
        "subheads": len(heads),
        "images": sum(1 for b in doc["blocks"] if b["t"] == "img"),
        "tables": sum(1 for b in doc["blocks"] if b["t"] == "table"),
        "chars": len(body),
        "sentences": len(sentences),
        "median_sentence": int(statistics.median([len(s) for s in sentences])) if sentences else 0,
        "seumnida_pct": round(100 * sum(1 for s in sentences if s.rstrip("!?.").endswith("습니다")) / len(sentences)) if sentences else 0,
        "headings": heads[:12],
    }


def _acquire_lock() -> bool:
    if st.LOCK.exists() and time.time() - st.LOCK.stat().st_mtime < 1800:
        return False
    st.LOCK.write_text(str(os.getpid()), encoding="utf-8")
    return True


def collect(limit: int) -> tuple[list[dict], int, int]:
    """목록을 읽고 아직 없는 글의 본문을 받습니다. (목록, 새로 받은 수, 잠긴 수)"""
    index = st.load_index()
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(st.PROFILE), headless=True, user_agent=st.UA,
            viewport={"width": 1000, "height": 1200},
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(st.LIST_URL, wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(2000)
        # 목록은 한 번에 24편만 그립니다. 더 뒤로 가려면 스크롤해서 불러와야 합니다.
        seen = 0
        for _ in range(40):
            rows_now = page.evaluate(LIST_JS)
            if len(rows_now) >= limit or len(rows_now) == seen:
                if len(rows_now) == seen:
                    break
            seen = len(rows_now)
            page.mouse.wheel(0, 20000)
            page.wait_for_timeout(1200)
            if seen >= limit:
                break
        rows = [_parse_row(r) for r in page.evaluate(LIST_JS)][:limit]

        fetched = locked = 0
        for row in rows:
            known = index.get(row["id"], {})
            if known.get("fetched"):
                index[row["id"]] = {**known, **row, "fetched": True}
                continue
            try:
                page.goto(st.POST_URL + row["id"], wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1500)
                doc = page.evaluate(BODY_JS)
            except Exception as exc:                      # 한 편 실패가 전체를 멈추지 않게
                index[row["id"]] = {**known, **row, "fetched": False, "error": type(exc).__name__}
                continue
            paras = [b for b in doc["blocks"] if b["t"] == "p"]
            # 잠긴 글도 도입부 몇 문단은 내려옵니다. 문단 수로만 보면 그 미리보기가
            # 본문으로 저장돼 분량 수치가 통째로 틀어집니다 — 결제벽 문구로 봅니다.
            if doc.get("locked") or len(paras) < 5:
                locked += 1
                index[row["id"]] = {**known, **row, "fetched": False, "locked": True}
                continue
            (st.POSTS / f"{row['id']}.json").write_text(
                json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            index[row["id"]] = {**known, **row, "fetched": True, "locked": False,
                                "summary": _summarize(doc),
                                "collected": dt.date.today().isoformat()}
            fetched += 1
            time.sleep(1.5)                                # 연달아 두드리지 않습니다
        ctx.close()
    st.save_index(index)
    return rows, fetched, locked


def write_digest(rows: list[dict], fetched: int, locked: int, session_dead: bool) -> str:
    index = st.load_index()
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"# 재테크농부 — {now} 기준", ""]
    if session_dead:
        lines += ["> **로그인이 풀렸습니다.** 새 글 본문을 받지 못했습니다.",
                  "> `python -m scripts.bench_login`을 한 번 돌려 주세요.", ""]
    lines.append("문장·글자 수치는 대략값입니다 — 확정 기준값은 `compare_to_benchmark.py`에 있습니다.")
    lines.append("")
    lines.append(f"이번 실행: 새 본문 {fetched}편 · 잠김 {locked}편 · 보관 {sum(1 for v in index.values() if v.get('fetched'))}편")
    lines.append("")
    cutoff = (dt.date.today() - dt.timedelta(days=3)).isoformat()
    recent = [r for r in rows if r["date"] >= cutoff] or rows[:6]
    for row in recent:
        entry = index.get(row["id"], {})
        mark = "O" if entry.get("fetched") else ("잠김" if entry.get("locked") else "-")
        lines.append(f"## [{mark}] {row['date']} {row['title']}")
        lines.append(f"- 분류 {row['category'] or '-'} · 완독 {row['minutes'] or '?'}분 · id `{row['id']}`")
        summary = entry.get("summary")
        if summary:
            lines.append(f"- 문단 {summary['paragraphs']} · 이미지 {summary['images']} · "
                         f"글자 {summary['chars']:,} · 문장 {summary['sentences']} "
                         f"(중앙값 {summary['median_sentence']}자 · 습니다 {summary['seumnida_pct']}%)")
            if summary["headings"]:
                lines.append(f"- 소제목: {' / '.join(summary['headings'][:8])}")
        lines.append("")
    text = "\n".join(lines)
    st.DIGEST.write_text(text, encoding="utf-8")
    return text


def stats() -> None:
    index = st.load_index()
    got = [v["summary"] for v in index.values() if v.get("summary")]
    if not got:
        print("모아 둔 본문이 없습니다.")
        return
    def med(key: str) -> float:
        return statistics.median([g[key] for g in got])
    print(f"본문 {len(got)}편 기준")
    for label, key in [("문단", "paragraphs"), ("이미지", "images"), ("글자", "chars"),
                       ("문장", "sentences"), ("문장 길이(중앙값)", "median_sentence"),
                       ("'습니다' 비율", "seumnida_pct")]:
        values = sorted(g[key] for g in got)
        p25 = values[len(values) // 4]
        p75 = values[3 * len(values) // 4]
        print(f"  {label:<18} 중앙값 {med(key):>8.0f}   p25 {p25:>6}   p75 {p75:>6}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=25, help="목록에서 볼 글 수")
    parser.add_argument("--report", action="store_true", help="수집 없이 마지막 요약 출력")
    parser.add_argument("--stats", action="store_true", help="모아 둔 본문의 구조 수치")
    args = parser.parse_args()

    st.ensure_dirs()
    if args.stats:
        stats()
        return 0
    if args.report:
        print(st.DIGEST.read_text(encoding="utf-8") if st.DIGEST.exists() else "아직 수집 기록이 없습니다.")
        return 0
    if not _acquire_lock():
        print("이미 실행 중입니다.")
        return 0
    try:
        rows, fetched, locked = collect(args.limit)
        session_dead = fetched == 0 and locked >= 3
        print(write_digest(rows, fetched, locked, session_dead))
        log = st.LOGS / f"{dt.date.today().isoformat()}.log"
        log.write_text(f"새 본문 {fetched} · 잠김 {locked} · 목록 {len(rows)}\n", encoding="utf-8")
        return 2 if session_dead else 0
    finally:
        st.LOCK.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
