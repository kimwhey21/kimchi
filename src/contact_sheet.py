"""그림 모음판 — 관문·렌더가 남긴 그림 여러 장을 세로로 이어 붙여 몇 장으로 줄인다.

왜: 루틴이 그림을 낱장으로 `Read`하면 한 편에 11턴을 쓴다(2026-09-25 감사, 실행 13건). 그렇다고
읽는 장수를 줄일 수는 없다 — 같은 감사에서 표 글자 겹침 3건·거짓 제목 2건·그림과 본문의 어긋남 2건은
**눈으로만** 잡혔다. 그래서 장수를 줄이는 대신 **한 판에 여러 장**을 원본 크기 그대로 이어 붙인다.

- 낱장의 크기는 줄이지 않는다(폭이 1,200px을 넘는 사진만 1,200px로 줄인다).
- 한 판의 높이는 1,500px 안에서 채운다 — 모델 API가 긴 변 1,568px을 넘는 그림을 줄이므로, 그 안에
  두면 원본 화질 그대로 보인다. 그림이 1,000×450 안팎이니 한 판에 셋 정도, 열한 장이면 네 판이다.
- 모음판은 `<폴더>/sheets/sheet-NN.png`에 둔다. `naver_post`가 그림을 고르는 `glob("*.png")`은
  하위 폴더를 보지 않으므로 모음판이 본문 그림으로 잘못 올라갈 일이 없다.
- 판마다 무엇을 담았는지 파일 이름을 위에 적는다(제목이 아니라 파일 이름 — 어느 절의 그림인지 바로 안다).
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

MAX_HEIGHT = 1500
MAX_WIDTH = 1200
GAP = 14
LABEL_HEIGHT = 26
SUBDIR = "sheets"
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")


def _font():
    try:
        return ImageFont.load_default(size=16)
    except TypeError:  # 옛 Pillow
        return ImageFont.load_default()


def _load(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGB")
    if image.width > MAX_WIDTH:
        ratio = MAX_WIDTH / image.width
        image = image.resize((MAX_WIDTH, max(1, round(image.height * ratio))), Image.LANCZOS)
    if image.height > MAX_HEIGHT - LABEL_HEIGHT:
        ratio = (MAX_HEIGHT - LABEL_HEIGHT) / image.height
        image = image.resize((max(1, round(image.width * ratio)), MAX_HEIGHT - LABEL_HEIGHT), Image.LANCZOS)
    return image


def _flush(items: list[tuple[str, Image.Image]], out: Path) -> None:
    width = max(img.width for _, img in items)
    height = sum(LABEL_HEIGHT + img.height for _, img in items) + GAP * (len(items) - 1)
    canvas = Image.new("RGB", (width, height), "#F3F4F6")
    draw = ImageDraw.Draw(canvas)
    font = _font()
    y = 0
    for name, img in items:
        draw.rectangle([0, y, width, y + LABEL_HEIGHT], fill="#111827")
        draw.text((8, y + 5), name, fill="#F9FAFB", font=font)
        y += LABEL_HEIGHT
        canvas.paste(img, (0, y))
        y += img.height + GAP
    canvas.save(out, "PNG", optimize=True)


def build(files: list[Path], out_dir: Path, *, max_height: int = MAX_HEIGHT) -> list[tuple[Path, list[str]]]:
    """files를 순서대로 모음판에 채워 `out_dir`에 `sheet-NN.png`로 쓴다.

    돌려주는 것: [(모음판 경로, [담긴 파일 이름, ...]), ...]. 있던 모음판은 먼저 지운다 — 관문을 다시
    돌려 그림이 줄었는데 옛 `sheet-04.png`가 남아 있으면 루틴이 옛 그림을 본다.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("sheet-*.png"):
        old.unlink()
    sheets: list[tuple[Path, list[str]]] = []
    pending: list[tuple[str, Image.Image]] = []
    height = 0

    def flush() -> None:
        nonlocal pending, height
        if not pending:
            return
        out = out_dir / f"sheet-{len(sheets) + 1:02d}.png"
        _flush(pending, out)
        sheets.append((out, [name for name, _ in pending]))
        pending, height = [], 0

    for path in files:
        path = Path(path)
        if path.suffix.lower() not in IMAGE_SUFFIXES or not path.exists():
            continue
        image = _load(path)
        need = LABEL_HEIGHT + image.height + (GAP if pending else 0)
        if pending and height + need > max_height:
            flush()
            need = LABEL_HEIGHT + image.height
        pending.append((path.name, image))
        height += need
    flush()
    return sheets


def gather(folder: Path) -> list[Path]:
    """폴더 바로 아래의 그림 파일을 이름순으로(하위 폴더·옛 모음판은 제외)."""
    return sorted(p for p in Path(folder).iterdir()
                  if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)


def describe(sheets: list[tuple[Path, list[str]]]) -> list[str]:
    """관문·렌더 출력에 붙일 줄. 루틴은 이 파일만 Read한다(낱장을 따로 읽지 않는다)."""
    if not sheets:
        return []
    lines = [f"그림 모음판 {len(sheets)}장 — Read 툴로 **이 파일만** 보십시오(낱장은 원본 크기 그대로 이어 붙인 것이라 "
             "따로 읽지 않습니다):"]
    for path, names in sheets:
        lines.append(f"  {path}  ({', '.join(names)})")
    return lines


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("사용법: python -m src.contact_sheet <그림 폴더>  — <폴더>/sheets/sheet-NN.png를 만든다")
        return 2
    folder = Path(args[0])
    if not folder.is_dir():
        print(f"폴더가 없습니다: {folder}")
        return 1
    sheets = build(gather(folder), folder / SUBDIR)
    if not sheets:
        print(f"{folder}에 그림 파일이 없습니다.")
        return 1
    print("\n".join(describe(sheets)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
