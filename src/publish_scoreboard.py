"""Checkpoint(기준표) 성적표 페이지를 `data/scoreboard.yaml`에서 만들어 워드프레스에 올립니다.

왜 있는가
---------
기준표는 "언제 무엇을 확인할지"를 날짜와 함께 적는 글입니다(docs/feature-style.md 4절).
그 약속을 모아 두고 날짜가 지나면 실제 결과를 적는 곳이 없으면, 글은 그날로 끝납니다.
재테크농부의 계좌인증이 하는 일(자기 판단에 책임지기)을 우리는 이 페이지로 합니다 —
틀린 것도 남깁니다.

무엇을 하는가
-------------
1. `data/scoreboard.yaml`을 읽어 검증한다(판정 값·날짜 형식·주소).
2. `templates/scoreboard.html.j2`로 페이지 본문(HTML 블록)을 만든다.
3. 워드프레스에서 slug `scoreboard` 페이지를 찾아 **본문만 갱신**한다. 상태는 건드리지
   않는다(공개면 공개, 임시저장이면 임시저장). 없으면 **임시저장**으로 만든다 —
   처음 공개는 사람이 "발행"이라고 한 뒤다(CLAUDE.md 「발행 워크플로우」).

사용법
------
    python -m src.publish_scoreboard                # 워드프레스 갱신
    python -m src.publish_scoreboard --render-only  # output/scoreboard.html만

판정 값은 `hit`(적중)·`miss`(빗나감)·`mixed`(절반)·`pending`(확인 전) 넷뿐이다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, select_autoescape

# 단독 실행 모듈이라 여기서 .env를 읽는다. 없으면 "설정 없음"으로 조용히 끝나는 일이
# 있었다(2026-09-06) — 그래서 아래에서 설정이 없으면 예외로 멈춘다.
load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "scoreboard.yaml"
OUTPUT = ROOT / "output" / "scoreboard.html"
SLUG = "scoreboard"
TIMEOUT = 30
VERDICTS = {"hit": "적중", "miss": "빗나감", "mixed": "절반", "pending": "확인 전"}
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ScoreboardError(ValueError):
    pass


def load(path: Path = DATA) -> list[dict]:
    """파일을 읽고 형식을 검사한다. 틀린 값이 있으면 페이지를 만들지 않는다."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(raw, list) or not raw:
        raise ScoreboardError(f"{path.name}: 기준표 목록이 비어 있습니다.")
    problems: list[str] = []
    for i, a in enumerate(raw, start=1):
        for key in ("title", "url", "date", "checks"):
            if not a.get(key):
                problems.append(f"{i}번 글: {key}가 없습니다.")
        if a.get("date") and not _DATE.match(str(a["date"])):
            problems.append(f"{i}번 글: date는 YYYY-MM-DD여야 합니다 ({a['date']}).")
        if a.get("url") and not str(a["url"]).startswith("https://fermata.it.kr/"):
            problems.append(f"{i}번 글: url은 fermata.it.kr 주소여야 합니다 ({a['url']}).")
        for j, c in enumerate(a.get("checks") or [], start=1):
            if not c.get("what"):
                problems.append(f"{i}번 글 {j}번 확인 지점: what이 없습니다.")
            if not c.get("due") and not c.get("due_label"):
                problems.append(f"{i}번 글 {j}번 확인 지점: due(YYYY-MM-DD) 또는 due_label이 없습니다.")
            if c.get("due") and not _DATE.match(str(c["due"])):
                problems.append(f"{i}번 글 {j}번 확인 지점: due는 YYYY-MM-DD여야 합니다 ({c['due']}).")
            verdict = c.get("verdict", "pending")
            if verdict not in VERDICTS:
                problems.append(f"{i}번 글 {j}번 확인 지점: verdict는 {sorted(VERDICTS)} 중 하나여야 합니다 ({verdict}).")
            if verdict != "pending" and not (c.get("result") and c.get("checked")):
                problems.append(f"{i}번 글 {j}번 확인 지점: 판정을 적었으면 result와 checked(확인한 날짜)도 있어야 합니다.")
            if c.get("checked") and not _DATE.match(str(c["checked"])):
                problems.append(f"{i}번 글 {j}번 확인 지점: checked는 YYYY-MM-DD여야 합니다 ({c['checked']}).")
    if problems:
        raise ScoreboardError("scoreboard.yaml 검사 실패:\n- " + "\n- ".join(problems))
    return raw


def _is_live(url: str) -> bool:
    """공개된 글만 싣는다. 임시저장 글의 주소는 방문자에게 404다."""
    try:
        response = requests.head(url, allow_redirects=True, timeout=TIMEOUT,
                                 headers={"User-Agent": "Mozilla/5.0 (fermata scoreboard)"})
        return response.status_code == 200
    except requests.RequestException:
        return False


def only_live(articles: list[dict], is_live=_is_live) -> list[dict]:
    kept = []
    for a in articles:
        if is_live(a["url"]):
            kept.append(a)
        else:
            print(f"[안내] 아직 공개되지 않아 성적표에서 뺍니다: {a['title']} ({a['url']})")
    if not kept:
        raise ScoreboardError("공개된 기준표가 하나도 없어 페이지를 만들지 않습니다.")
    return kept


def _due_label(check: dict) -> str:
    if check.get("due_label"):
        return str(check["due_label"])
    d = dt.date.fromisoformat(str(check["due"]))
    return f"{d.month}/{d.day}"


def build(articles: list[dict], today: dt.date | None = None) -> str:
    today = today or dt.date.today()
    tally = {"hit": 0, "miss": 0, "mixed": 0, "pending": 0, "total": 0}
    view = []
    for a in sorted(articles, key=lambda x: str(x["date"]), reverse=True):
        checks = []
        for c in a["checks"]:
            verdict = c.get("verdict", "pending")
            tally[verdict] += 1
            tally["total"] += 1
            checks.append({
                "due_label": _due_label(c), "what": c["what"], "verdict": verdict,
                "verdict_label": VERDICTS[verdict], "result": c.get("result", ""),
                "checked": c.get("checked", ""),
            })
        view.append({"title": a["title"], "url": a["url"], "date": str(a["date"]),
                     "summary": a.get("summary", ""), "checks": checks})
    env = Environment(loader=FileSystemLoader(str(ROOT / "templates")),
                      autoescape=select_autoescape(["html", "j2"]))
    template = env.get_template("scoreboard.html.j2")
    return template.render(articles=view, tally=tally, updated=today.isoformat())


def _find_page(base: str, auth: tuple[str, str]) -> dict | None:
    response = requests.get(
        f"{base}/wp-json/wp/v2/pages", auth=auth, timeout=TIMEOUT,
        params=[("slug", SLUG), ("context", "edit"), ("per_page", "1"),
                *(("status[]", s) for s in ("publish", "draft", "pending", "private"))],
    )
    response.raise_for_status()
    pages = response.json()
    return pages[0] if pages else None


def publish(html: str) -> dict:
    """slug 'scoreboard' 페이지의 본문만 갱신한다. 없으면 임시저장으로 만든다."""
    url = os.environ.get("WORDPRESS_URL")
    user = os.environ.get("WORDPRESS_USERNAME")
    password = os.environ.get("WORDPRESS_APP_PASSWORD")
    if not (url and user and password):
        raise ScoreboardError("워드프레스 설정이 없어 올리지 못했습니다. WORDPRESS_URL·"
                              "WORDPRESS_USERNAME·WORDPRESS_APP_PASSWORD를 확인하십시오.")
    base, auth = url.rstrip("/"), (user, password)
    page = _find_page(base, auth)
    if page:
        response = requests.post(f"{base}/wp-json/wp/v2/pages/{page['id']}", auth=auth,
                                 json={"content": html}, timeout=TIMEOUT)
        action = f"갱신 (상태 {page.get('status')})"
    else:
        # 자동화 스위치(FERMATA_AUTO_PUBLISH=true)가 켜져 있으면 바로 공개, 아니면 임시저장.
        auto = os.environ.get("FERMATA_AUTO_PUBLISH", "").strip().lower() == "true"
        response = requests.post(f"{base}/wp-json/wp/v2/pages", auth=auth, timeout=TIMEOUT,
                                 json={"title": "Checkpoint 성적표", "slug": SLUG,
                                       "status": "publish" if auto else "draft",
                                       "template": "page-no-title", "content": html})
        action = "새로 만듦 (바로 공개)" if auto else "새로 만듦 (임시저장 — 공개는 사람이 '발행'이라고 한 뒤)"
    if response.status_code >= 400:
        raise ScoreboardError(f"페이지 저장 실패 (HTTP {response.status_code}): {response.text[:300]}")
    result = response.json()
    # 되읽어 확인 — 저장했다고 믿지 않는다.
    check = requests.get(f"{base}/wp-json/wp/v2/pages/{result['id']}", auth=auth,
                         params={"context": "edit"}, timeout=TIMEOUT)
    check.raise_for_status()
    if "Checkpoint 성적표" not in check.json()["content"]["raw"]:
        raise ScoreboardError("저장 뒤 되읽었더니 본문이 다릅니다.")
    print(f"성적표 페이지 {action}: id={result['id']} {result.get('link', '')}")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Checkpoint 성적표 페이지를 만들어 올립니다")
    parser.add_argument("--render-only", action="store_true", help="output/scoreboard.html만 만든다")
    parser.add_argument("--no-live-check", action="store_true",
                        help="주소가 살아 있는지 확인하지 않는다(오프라인 렌더 확인용)")
    args = parser.parse_args(argv)
    articles = load()
    if not args.no_live_check:
        articles = only_live(articles)
    html = build(articles)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"렌더: {OUTPUT}")
    if not args.render_only:
        publish(html)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ScoreboardError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
