"""Draw the PWA icons of the browser build (web/icons/) with the game's own sprite code.

    uv run python scripts/make_icons.py

A cat from a fixed seed on a solid background, upscaled nearest-neighbour. The PNGs are committed, so the web build
does not need Pillow. The maskable icon keeps the cat inside the central 60% (the safe zone is a circle of 80%).
"""
import random
from pathlib import Path

from kit_the_cat import engine as E
from kit_the_cat import sprites as S

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "icons"
SEED = 3
BG = (41, 54, 111)   # --dialog of the page: the cat's dark outline stays visible on it
ICONS = {"icon-192.png": (192, 0.80), "icon-512.png": (512, 0.80), "icon-maskable-512.png": (512, 0.58)}


def cat():
    """The cat sprite alone (no background) cropped to its pixels, as a 1:1 RGBA image."""
    Image = S._pil()
    p = E.new_pet(-1, 1, "Kit", "cat", [], random.Random(SEED))
    p.state, p.stage = "alive", 3
    lk = p.look("")
    cv = S.Canvas()
    S.draw(cv, lk, 0)
    xs, ys = [x for x, _ in cv.px], [y for _, y in cv.px]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs) + 1, max(ys) + 1
    im = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
    for (x, y), c in cv.px.items():
        if 0 <= x < cv.w and 0 <= y < cv.h:
            im.putpixel((x - x0, y - y0), (*c[:3], 255))
    return im


def icon(sprite, size: int, fill: float):
    """The sprite scaled by a whole factor to at most `fill` of the icon, centred on BG."""
    Image = S._pil()
    k = max(1, int(size * fill / max(sprite.size)))
    big = sprite.resize((sprite.width * k, sprite.height * k), Image.NEAREST)
    out = Image.new("RGBA", (size, size), (*BG, 255))
    out.alpha_composite(big, ((size - big.width) // 2, (size - big.height) // 2))
    return out.convert("RGB")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sprite = cat()
    for name, (size, fill) in ICONS.items():
        icon(sprite, size, fill).save(OUT / name, optimize=True)
        print("wrote", OUT / name)


if __name__ == "__main__":
    main()
