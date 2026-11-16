"""루틴 샌드박스를 그림을 그릴 수 있는 상태로 만든다 — `python -m scripts.sandbox_ready`.

한 줄 설치 명령이 조용히 실패하는 꼴 둘을 여기서 맡는다.

- **Pillow**: `pip`가 `python`과 다른 판본의 것이면 설치가 엉뚱한 곳에 들어가고, 시스템에 깔린 다른 판본용 Pillow가
  먼저 잡혀 `from PIL import Image`가 죽는다. 지금 도는 `python`의 pip로, 깔려 있어도 다시 깐다.
- **한글 폰트**: 꾸러미 목록이 비어 있으면 `apt-get install fonts-nanum`이 "찾을 수 없음"으로 끝난다. 목록을 먼저 받는다.

마지막 줄이 `준비됨`이면 종료 코드 0, 아니면 무엇이 안 됐는지 적고 1. 이미 되어 있으면 아무것도 깔지 않는다.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# `src.data_graphics`의 폰트 목록과 같은 자리(그 모듈은 Pillow를 불러서 여기서 가져올 수 없다).
FONTS = ("/System/Library/Fonts/AppleSDGothicNeo.ttc", "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
         "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/System/Library/Fonts/Supplemental/AppleGothic.ttf")


def _run(command: list[str], timeout: int = 300) -> bool:
    try:
        return subprocess.run(command, capture_output=True, timeout=timeout).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def pillow_works() -> bool:
    """새 프로세스에서 본다 — 이 프로세스가 이미 깨진 PIL을 불러 뒀을 수 있다."""
    return _run([sys.executable, "-c", "from PIL import Image, ImageDraw, ImageFont"], timeout=60)


def has_font() -> bool:
    return any(Path(path).exists() for path in FONTS)


def fix_pillow() -> None:
    pip = [sys.executable, "-m", "pip", "install", "-q", "--ignore-installed", "pillow"]
    if not _run(pip) or not pillow_works():
        _run(pip + ["--break-system-packages"])


def fix_font() -> None:
    if not shutil.which("apt-get"):
        return
    install = ["apt-get", "install", "-y", "-qq", "fonts-nanum"]
    if not _run(install) or not has_font():
        _run(["apt-get", "update", "-qq"])
        _run(install)


def main() -> int:
    did = []
    requirements = ROOT / "requirements.txt"
    try:
        import yaml  # noqa: F401 - 의존성이 깔려 있는지 보는 표본
    except ImportError:
        _run([sys.executable, "-m", "pip", "install", "-q", "-r", str(requirements)], timeout=600)
        did.append("의존성 설치")
    if not pillow_works():
        fix_pillow()
        did.append("Pillow 다시 설치")
    if not has_font():
        fix_font()
        did.append("한글 폰트 설치")
    problems = []
    if not pillow_works():
        problems.append(f"Pillow를 불러오지 못합니다({sys.executable}) — 그림도 관문도 돌지 않습니다")
    if not has_font():
        problems.append("한글 폰트가 없습니다 — 그림을 그릴 수 없습니다(관문은 돕니다)")
    if did:
        print("한 일: " + ", ".join(did))
    if problems:
        print("준비 안 됨: " + " / ".join(problems))
        return 1
    print("준비됨")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
