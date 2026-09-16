"""네이버에 **실제로 올라간 글**이 원고를 다 담았는지 대조한다 (2026-09-16).

    python -m scripts.naver_audit              # 올라간 글 전부
    python -m scripts.naver_audit <logNo> ...  # 몇 편만

`tests/test_naver_completeness.py`는 만들어지는 원고를 보고, 이 스크립트는 **네이버에 올라간
화면**을 본다. 둘 다 필요하다 — 2026-09-15에 코드는 맞았지만 이미 올라간 글은 옛 서식이었고,
그걸 알아챈 것은 사람이 글을 열어 봤기 때문이었다.

빠진 것이 있으면 0이 아닌 값으로 끝난다. 원고의 덩어리(절·outlook·insight·표·Take·확인 지점·
출처)를 하나씩 찾아보고, 그림 수와 본진 링크 유무도 함께 보고한다.
"""
import html as html_mod
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def plain(x):
    """태그를 떼고 공백을 고른다. 네이버는 따옴표를 &#x27;로 내보내므로 **엔티티를 먼저 푼다** —
    풀지 않으면 멀쩡히 실린 문장이 '빠짐'으로 잡힌다(2026-09-16에 실제로 그랬다)."""
    text = str(x or "")
    for _ in range(3):                       # &amp;#x27; 처럼 두 번 감싸인 경우까지
        new = html_mod.unescape(text)
        if new == text:
            break
        text = new
    text = text.replace("\u200b", " ")          # 네이버가 문단 사이에 넣는 폭 0 공백
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()


def fetch(logno):
    url = f"https://blog.naver.com/PostView.naver?blogId=fermata49&logNo={logno}&redirect=Dlog"
    html = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=90).read()
    return html.decode("utf-8", "replace")


def squash(x) -> str:
    """공백을 전부 없앤 꼴로 견준다. 원고의 `<b>`를 양쪽이 다르게 떼기 때문이다 —
    `naver_post._plain`은 태그를 빈 문자열로, 이 파일은 공백으로 지운다. 공백을 없애면 같아진다."""
    return re.sub(r"\s+", "", plain(x))


def probe_of(value) -> str:
    """대조용 표본: **첫 문단의 앞 40자**. 문단을 걸치면 네이버가 사이에 넣는 빈 줄 때문에
    멀쩡히 실린 글도 안 맞는다(2026-09-16에 실제로 오탐이 났다)."""
    first = str(value or "").split("\n\n")[0]
    return plain(first)[:40]


def check(manuscript: Path, logno: str) -> list[str]:
    doc = json.loads(manuscript.read_text(encoding="utf-8"))
    ko = doc.get("ko") or {}
    html = fetch(logno)
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S)
    text = squash(body)
    imgs = len(re.findall(r'<img[^>]+postfiles|<img[^>]+blogfiles', body)) or len(re.findall(r"<img", body))

    missing = []
    checked = 0
    for i, sec in enumerate(ko.get("narrative") or []):
        for label, value in (("소제목", sec.get("heading")), ("본문", sec.get("body"))):
            probe = probe_of(value)
            if label == "소제목":
                # 네이버 쪽은 `1. `처럼 앞에 붙은 번호를 뗀다(naver_post가 그렇게 싣는다).
                probe = re.sub(r"^\s*\d{1,2}\.\s*", "", probe)
            probe = squash(probe[:40])
            if probe:
                checked += 1
                if probe not in text:
                    missing.append(f"narrative[{i}] {label}")
    for label, value in (("outlook", (ko.get("outlook") or {}).get("body")),
                         ("closing(Take)", (ko.get("closing") or {}).get("body")),
                         ("확인 지점", ((ko.get("closing") or {}).get("check") or {}).get("what"))):
        probe = squash(probe_of(value))
        if probe:
            checked += 1
            if probe not in text:
                missing.append(label)
    for i, story in enumerate((ko.get("insight_section") or {}).get("stories") or []):
        probe = squash(probe_of(story.get("body")))
        if probe:
            checked += 1
            if probe not in text:
                missing.append(f"insight[{i}]")
        for r in story.get("table") or []:
            if r.get("label") and squash(r["label"]) not in text:
                missing.append(f"insight[{i}] 표 {r['label']}")
    srcs = [x for x in (ko.get("sources") or doc.get("sources") or []) if isinstance(x, dict) and x.get("name")]
    for x in srcs:
        checked += 1
        if squash(x["name"]) not in text:
            missing.append(f"출처 {x['name']}")
    link = "있음" if re.search(r'href="[^"]*fermata\.it\.kr', body) else "없음"
    print(f"{manuscript.name:34s} 대조 {checked}개 · 빠진 것 {len(missing)}개 · 그림 {imgs} · 본진 링크 {link}")
    for m in missing:
        print("    빠짐:", m)
    return missing


if __name__ == "__main__":
    posted = json.loads((Path.home() / ".market-brief-naver" / "posted.json").read_text(encoding="utf-8"))
    wanted = sys.argv[1:] or None
    bad = 0
    for k, v in sorted(posted.items(), key=lambda kv: kv[0]):
        rel = k.replace("\\", "/").split("market-brief/")[-1]
        path = ROOT / rel
        if not path.exists() or "/magazine/" in rel or "/guides/" in rel or "/weekly/" in rel or "/events/" in rel:
            continue
        if wanted and v["logNo"] not in wanted:
            continue
        try:
            bad += len(check(path, v["logNo"]))
        except Exception as exc:  # noqa: BLE001
            print(f"{path.name}: 확인 실패 — {exc}")
            bad += 1
    print("\n빠진 항목 합계:", bad)
    sys.exit(1 if bad else 0)
