"""시황 원고의 판단(Fermata's Take)과 어제 판정을 성적표(data/scoreboard.yaml)에 옮깁니다.

왜 (2026-09-08, 사용자 승인 — "1~3번 진행하자")
------------------------------------------------
재테크농부와의 남은 차이는 "사람이 판단하고 책임지는 글"이다. 그래서 시황도 매일
**판단 + 확인 지점**을 남기고(`closing.check`), 다음 날 글이 그 확인 지점을 실제 결과로
판정한다(`review`). 이 모듈이 그 둘을 성적표에 적는다 — 루틴이 YAML을 손으로 고치지
않아도 되게. 발행 워크플로가 글을 올린 뒤 이 모듈을 돌리고 성적표를 커밋한다.

원고 필드
---------
    "closing": {"heading": "Fermata's Take", "body": "...",
                "check": {"due": "2026-09-10", "what": "코스피가 7,000선을 종가로 넘는지"}}
    "review":  {"of_date": "2026-09-07", "verdict": "hit|miss|mixed", "result": "실제로 나온 것(숫자와 함께)"}

    python -m src.scoreboard_sync editorial/kr_2026-09-08.json [...]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCOREBOARD = ROOT / "data" / "scoreboard.yaml"
VERDICTS = {"hit", "miss", "mixed"}


def post_url(market: str, date_str: str) -> str:
    return f"https://fermata.it.kr/editorial-{market}-{date_str}-ko/"


def _load() -> list[dict]:
    data = yaml.safe_load(SCOREBOARD.read_text(encoding="utf-8")) or []
    if not isinstance(data, list):
        raise ValueError("scoreboard.yaml은 글 목록이어야 합니다.")
    return data


def _dump(articles: list[dict]) -> None:
    header = []
    for line in SCOREBOARD.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            header.append(line)
        else:
            break
    body = yaml.safe_dump(articles, allow_unicode=True, sort_keys=False, width=100)
    SCOREBOARD.write_text("\n".join(header) + "\n\n" + body, encoding="utf-8")


def upsert_check(articles: list[dict], doc: dict) -> str | None:
    """이 원고의 확인 지점을 성적표에 넣는다(주소로 찾아 있으면 갱신). 없으면 None."""
    ko = doc.get("ko") or {}
    check = (ko.get("closing") or {}).get("check") or {}
    if not (check.get("due") and check.get("what")):
        return None
    url = post_url(doc["market"], doc["date"])
    entry = next((a for a in articles if a.get("url") == url), None)
    if entry is None:
        entry = {"title": ko.get("title", ""), "url": url, "date": doc["date"], "summary": "", "checks": []}
        articles.insert(0, entry)
    entry["title"] = ko.get("title", entry.get("title", ""))
    entry["summary"] = str(check.get("summary") or ko.get("excerpt") or entry.get("summary") or
                           (ko.get("closing") or {}).get("body", "").split("\n\n")[0][:120])
    existing = next((c for c in entry["checks"] if str(c.get("due")) == str(check["due"])), None)
    if existing is None:
        entry["checks"].append({"due": str(check["due"]), "what": str(check["what"]), "verdict": "pending"})
        return f"확인 지점 추가: {url} — {check['due']} {check['what'][:40]}"
    if existing.get("verdict", "pending") == "pending":
        existing["what"] = str(check["what"])
        return f"확인 지점 갱신: {url} — {check['due']}"
    return None


def apply_review(articles: list[dict], doc: dict, today: str | None = None) -> str | None:
    """어제 글의 확인 지점을 이 원고의 `review`로 판정한다."""
    review = doc.get("review") or {}
    if not review:
        return None
    verdict = str(review.get("verdict", "")).strip()
    if verdict not in VERDICTS:
        raise ValueError(f"review.verdict는 {sorted(VERDICTS)} 중 하나여야 합니다: {verdict!r}")
    if not str(review.get("result", "")).strip():
        raise ValueError("review.result(실제로 나온 것, 숫자와 함께)가 비어 있습니다.")
    target = post_url(doc["market"], str(review.get("of_date", "")))
    entry = next((a for a in articles if a.get("url") == target), None)
    if entry is None:
        return f"판정 건너뜀: {target}에 성적표 항목이 없습니다(옛 형식 글)."
    today = today or doc.get("date") or dt.date.today().isoformat()
    pending = [c for c in entry.get("checks", []) if c.get("verdict", "pending") == "pending"
               and str(c.get("due", "")) <= today]
    if not pending:
        return f"판정 건너뜀: {target}에 기한이 지난 미판정 확인 지점이 없습니다."
    for check in pending:
        check["verdict"] = verdict
        check["result"] = str(review["result"])
        check["checked"] = today
    return f"판정 적음: {target} — {verdict} ({len(pending)}개)"


def sync(paths: list[Path]) -> list[str]:
    articles = _load()
    notes: list[str] = []
    for path in paths:
        doc = json.loads(path.read_text(encoding="utf-8"))
        if "price_data" not in doc:
            notes.append(f"{path.name}: 시황 원고가 아니라 건너뜁니다.")
            continue
        for line in (apply_review(articles, doc), upsert_check(articles, doc)):
            if line:
                notes.append(f"{path.name}: {line}")
    _dump(articles)
    return notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args(argv)
    for line in sync(args.paths):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
