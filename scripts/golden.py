"""황금 파일 — 코드를 정리하기 전과 후의 결과물이 같은지 기계로 대조한다 (2026-10-05).

    python -m scripts.golden record            # 지금 코드로 표본 원고를 렌더해 지문을 output/golden/record.json에
    python -m scripts.golden check             # 다시 렌더해 지문을 대조 — 하나라도 다르면 어디가 다른지 찍고 1로 끝난다

무엇을 렌더하나: 원고 종류마다 최근 것을 골라 독자에게 가는 길을 전부 —
관문(`editorial_gate`·`feature_gate`)의 판정 출력, 본진 렌더(`publish_editorial`·`publish_feature --render-only`)가 만든
HTML·그림, 네이버 블록(`naver_post build`), 블로그스팟 HTML(`blogger_post --no-upload`). 워드프레스 설정은 비우고 돌린다
(아무것도 올리지 않는다). 지문은 파일 내용의 sha256이고, 출력 글자에서는 이 맥의 절대 경로와 시간을 지운다.

같은 코드로 두 번 돌려 같아야 쓸모가 있다 — `record`를 두 번 돌려 `check`가 통과하는지 먼저 본다(결정성).
editorial/이 바뀌면(루틴이 새 원고를 올리면) 관문의 '최근 제목 피드'가 달라지므로 record와 check 사이에 pull하지 않는다.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "golden"
RECORD = OUT / "record.json"
PY = sys.executable

DAILY = ["editorial/kr_2026-10-02.json", "editorial/us_2026-10-02.json", "editorial/kr_2026-10-01.json", "editorial/us_2026-09-30.json"]
FEATURE = ["editorial/previews/us_2026-10-02.json", "editorial/previews/us_2026-10-01.json",
           "editorial/weekly/review_2026-10-03.json", "editorial/weekly/ahead_2026-10-04.json",
           "editorial/guides/ko_dividend-tax-korea.json", "editorial/guides/ko_buyback-and-cancellation.json",
           "editorial/guides/en_korea-short-selling-rules.json", "editorial/guides/en_korea-vs-taiwan-semiconductors.json",
           "editorial/features/kr_2026-10-04_trading-value-checkpoint.json", "editorial/features/us_2026-09-27_13f_playbook.json",
           "editorial/events/2026-09-27_jobs-report.json"]
MAGAZINE = ["editorial/magazine/2026-10-05_musk-debt-robots-bet.json", "editorial/magazine/2026-10-05_ramsey-dividend-income-debate.json"]


def _env() -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("WORDPRESS_", "TELEGRAM_", "THREADS_", "CLOUDFLARE_"))}
    env["WORDPRESS_URL"] = env["WORDPRESS_USERNAME"] = env["WORDPRESS_APP_PASSWORD"] = ""
    env["PYTHONHASHSEED"] = "0"
    env["MPLBACKEND"] = "Agg"
    return env


def _clean(text: str) -> str:
    text = text.replace(str(ROOT), "<ROOT>").replace(str(Path.home()), "<HOME>")
    text = re.sub(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?([+-]\d{2}:?\d{2}|Z)?", "<TIME>", text)
    text = re.sub(r"\b\d+(\.\d+)?\s*(초|s|ms)\b", "<DUR>", text)
    return text


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def _run(args: list[str]) -> str:
    r = subprocess.run([PY, *args], cwd=ROOT, env=_env(), capture_output=True, text=True, timeout=600)
    return _clean(f"exit={r.returncode}\n{r.stdout}\n--stderr--\n{r.stderr}")


def _tree(folder: Path) -> dict[str, str]:
    if not folder.exists():
        return {}
    return {str(p.relative_to(folder)): _sha(p.read_bytes()) for p in sorted(folder.rglob("*")) if p.is_file()}


def _feature_slug(path: str) -> str:
    doc = json.loads((ROOT / path).read_text(encoding="utf-8"))
    return str(doc.get("slug") or Path(path).stem)


def snapshot() -> dict:
    snap: dict[str, dict] = {}
    for path in DAILY:
        stem = Path(path).stem
        for d in (ROOT / "output" / "gate" / stem,):
            shutil.rmtree(d, ignore_errors=True)
        gate = _run(["-m", "src.editorial_gate", path])
        render = _run(["-m", "src.publish_editorial", path, "--render-only"])
        outputs = {p.name: _sha(p.read_bytes()) for p in sorted((ROOT / "output").glob(f"{stem}_editorial*")) if p.is_file()}
        snap[path] = {"gate": _sha(gate.encode()), "gate_text": gate[-4000:], "render": _sha(render.encode()),
                      "gate_files": _tree(ROOT / "output" / "gate" / stem), "outputs": outputs}
    for path in FEATURE + MAGAZINE:
        slug = _feature_slug(path)
        shutil.rmtree(ROOT / "output" / "features" / slug, ignore_errors=True)
        doc = json.loads((ROOT / path).read_text(encoding="utf-8"))
        n = len([g for g in doc.get("graphics") or [] if isinstance(g, dict)])
        gate = _run(["-m", "src.feature_gate", path, "--graphics", str(n)])
        render = _run(["-m", "src.publish_feature", path, "--render-only"]) if path not in MAGAZINE else ""
        snap[path] = {"gate": _sha(gate.encode()), "gate_text": gate[-4000:], "render": _sha(render.encode()),
                      "files": _tree(ROOT / "output" / "features" / slug)}
    for path in DAILY[:2] + FEATURE + MAGAZINE:
        gdir = ROOT / "output" / ("gate/" + Path(path).stem if path in DAILY else "features/" + _feature_slug(path))
        naver_out, blog_out = OUT / "tmp_naver.json", OUT / "tmp_blogger.json"
        for f in (naver_out, blog_out):
            f.unlink(missing_ok=True)
        OUT.mkdir(parents=True, exist_ok=True)
        naver = _run(["-m", "scripts.naver_post", "build", path, "--graphics", str(gdir), "--out", str(naver_out)])
        blog = _run(["-m", "scripts.blogger_post", path, "--graphics", str(gdir), "--out", str(blog_out), "--no-upload"])
        entry = snap.setdefault(path, {})
        entry["naver"] = _sha(_clean(naver_out.read_text(encoding="utf-8")).encode()) if naver_out.exists() else "없음:" + naver[-300:]
        entry["blogger"] = _sha(_clean(blog_out.read_text(encoding="utf-8")).encode()) if blog_out.exists() else "없음:" + blog[-300:]
    return snap


def diff(old: dict, new: dict) -> list[str]:
    out = []
    for path in sorted(set(old) | set(new)):
        a, b = old.get(path) or {}, new.get(path) or {}
        for key in sorted(set(a) | set(b)):
            if key == "gate_text":
                continue
            if a.get(key) != b.get(key):
                if isinstance(a.get(key), dict) or isinstance(b.get(key), dict):
                    fa, fb = a.get(key) or {}, b.get(key) or {}
                    names = sorted(n for n in set(fa) | set(fb) if fa.get(n) != fb.get(n))
                    out.append(f"{path} [{key}] 다른 파일 {len(names)}개: {', '.join(names[:8])}")
                else:
                    out.append(f"{path} [{key}] {a.get(key)} → {b.get(key)}")
                    if key == "gate":
                        out.append("   전: " + (a.get("gate_text") or "")[-600:].replace("\n", " | "))
                        out.append("   후: " + (b.get("gate_text") or "")[-600:].replace("\n", " | "))
    return out


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    cmd = argv[0] if argv else "check"
    snap = snapshot()
    if cmd == "record":
        OUT.mkdir(parents=True, exist_ok=True)
        RECORD.write_text(json.dumps(snap, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
        files = sum(len(v.get("files") or {}) + len(v.get("gate_files") or {}) + len(v.get("outputs") or {}) for v in snap.values())
        print(f"황금 파일 기록: 원고 {len(snap)}편, 그림·HTML {files}개 → {RECORD.relative_to(ROOT)}")
        return 0
    old = json.loads(RECORD.read_text(encoding="utf-8"))
    problems = diff(old, snap)
    if problems:
        print("\n".join(problems))
        print(f"황금 파일 불일치 {len(problems)}건")
        return 1
    print(f"황금 파일 일치: 원고 {len(snap)}편 전부 같습니다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
