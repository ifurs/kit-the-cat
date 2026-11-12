"""The art of the game as PNG files you can redraw (src/kit_the_cat/assets/, see the README there and art.py).

    uv run python scripts/art.py export          # write every asset; a file you redrew is left alone
    uv run python scripts/art.py status          # which files are redrawn, broken or unknown
    uv run python scripts/art.py export --check  # exit 1 if the code draws something the manifest doesn't know (CI)

A redrawn file needs no other step: the bot and the browser build pick it up.
"""
import argparse
import json
import random
import sys
import zlib
from collections.abc import Callable, Iterator

from kit_the_cat import art, card, sprites as S
from kit_the_cat.sprites_bg import BACKGROUNDS
from kit_the_cat.sprites_core import Canvas, N
from kit_the_cat.sprites_gen import GEN, template_params

K = art.KEYS


def strip(frames: list[dict]) -> tuple[int, int, bytes] | None:
    """Four 48×48 frames as one row of RGBA, or a single frame if nothing moves; None if there is nothing on them."""
    if not any(frames):
        return None
    if all(fr == frames[0] for fr in frames):
        frames = frames[:1]
    w = N * len(frames)
    rgba = bytearray(w * N * 4)
    for k, fr in enumerate(frames):
        for (x, y), c in fr.items():
            if 0 <= x < N and 0 <= y < N:
                rgba[(y * w + k * N + x) * 4:(y * w + k * N + x + 1) * 4] = bytes((c[0], c[1], c[2], 255))
    return w, N, bytes(rgba)


def drawn(paint: Callable[[Canvas, int], None], flat: bool = True) -> list[dict]:
    out = []
    for f in range(art.FRAMES):
        cv = Canvas()
        cv.flat = flat  # pets and their things are flat, backgrounds keep their shading
        paint(cv, f)
        out.append(dict(cv.px))
    return out


def head(f: int) -> tuple:
    return S._geom(S.REF, f)[0]


def templated(paint: Callable, palette: Callable[[dict], tuple] = lambda k: tuple(k.values())) -> list[dict]:
    """Frames of a recolourable part: `paint(cv, f, keys)` draws it in the template colours. A colour the code mixes
    from them (a darker ear lining) is snapped to the nearest template colour, so the picture has a clean palette;
    how to tell: it changes when the part is drawn in another palette, while a hard-coded colour (a pink nose) doesn't."""
    keys, other = dict(K), {k: (v[2], v[0], v[1]) for k, v in K.items()}
    allowed = palette(keys)
    a = drawn(lambda cv, f: paint(cv, f, keys))
    b = drawn(lambda cv, f: paint(cv, f, other))
    out = []
    for fa, fb in zip(a, b):
        out.append({p: c if c in allowed or fb.get(p) == c else
                    min(allowed, key=lambda t: sum((x - y) ** 2 for x, y in zip(t, c))) for p, c in fa.items()})
    return out


def gen_palette(k: dict) -> tuple:
    return tuple(S.gen_keys(k["base"], k["accent"]))


def generate() -> Iterator[tuple[str, list[dict]]]:
    """Every replaceable asset: (path inside assets/, frames), drawn for the reference body."""
    for name, (_, _, fn) in S.ITEMS.items():
        yield f"items/{name}.png", drawn(lambda cv, f, fn=fn: fn(cv, S.ref_body(f), f))
    for slot, (fn, kinds) in GEN.items():
        for kind in kinds:
            yield f"generated/{slot}.{kind.key}.png", templated(
                lambda cv, f, k, fn=fn, kind=kind: fn(cv, S.ref_body(f), f, template_params(kind, k["base"], k["accent"])), gen_palette)
    for name, (_, fn) in BACKGROUNDS.items():
        yield f"backgrounds/{name}.png", drawn(lambda cv, f, fn=fn, name=name: fn(cv, f, random.Random(zlib.crc32(name.encode()))), flat=False)
    for style in S.GENES["ears"]:
        ears = S._ears if style in S.BACK_EARS else S._front_ears
        yield f"ears/{style}.png", templated(lambda cv, f, k, e=ears, s=style: e(cv, s, *head(f), k["base"], k["shade"], k["accent"], f))
    for style in S.GENES["tail"]:
        yield f"tail/{style}.png", templated(lambda cv, f, k, s=style: S._tail(cv, s, *S._geom(S.REF, f)[1], k["base"], k["shade"], k["light"], f))
    for style in S.GENES["face"]:
        yield f"face/{style}.png", templated(lambda cv, f, k, s=style: S._snout(cv, s, *head(f), k["light"], k["accent"], k["shade"], f))
    for style in S.GENES["mark"]:
        yield f"mark/{style}.png", drawn(lambda cv, f, s=style: S._mark(cv, s, head(f)[0], head(f)[1], head(f)[3], K["light"], K["second"], f))
    for style in S.GENES["extra"]:
        if style != "wings":  # wings hang on the body, not the head: still code
            yield f"extra/{style}.png", templated(lambda cv, f, k, s=style: _extra(cv, s, f, k))
    for name, (rows, colors) in S.BETWEEN.items():
        yield f"markers/{name}.png", drawn(lambda cv, f, r=rows, c=colors: cv.grid(0, 0, r, c))
    for name, (rows, colors) in card.ICONS.items():
        yield f"icons/{name}.png", drawn(lambda cv, f, r=rows, c=colors: cv.grid(0, 0, r, c))


def _extra(cv: Canvas, style: str, f: int, k: dict) -> None:
    b = S.ref_body(f)
    b.pal = (k["base"], k["shade"], k["light"], k["accent"], k["second"]) + b.pal[5:]
    S._extra(cv, S.replace(S.REF.genes, extra=style), b, k["second"], f)


def fresh() -> dict[str, tuple[int, int, bytes]]:
    """What the code draws, with art.py's lookups off so that a redrawn file can't feed its own export."""
    load, art.load = art.load, lambda kind, name: None
    try:
        return {rel: s for rel, frames in generate() if (s := strip(frames))}
    finally:
        art.load = load


def export(check: bool) -> int:
    old, new = art.manifest(), fresh()
    want = {rel: art.pixel_hash(*s) for rel, s in new.items()}
    if check:
        diff = sorted(set(want.items()) ^ set(old.items()))
        for rel in sorted({r for r, _ in diff})[:20]:
            print(f"stale: {rel}")
        if diff:
            print("run: uv run python scripts/art.py export")
        return 1 if diff else 0
    kept = 0
    for rel, (w, h, rgba) in new.items():
        path = art.ROOT / rel
        if path.exists() and rel in old and _hash_of(path) not in (old[rel], None):
            kept += 1
            print(f"redrawn, left alone: {rel}")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(art.png_encode(w, h, rgba))
    for path in art.ROOT.rglob("*.png"):
        rel = path.relative_to(art.ROOT).as_posix()
        if rel not in new and rel in old and _hash_of(path) == old[rel]:
            path.unlink()  # the code no longer draws it and nobody redrew it
    (art.ROOT / "manifest.json").write_text(json.dumps(want, indent=0, sort_keys=True) + "\n")
    art.reload()
    print(f"{len(new)} assets, {kept} redrawn")
    return 0


def _hash_of(path) -> str | None:
    try:
        return art.pixel_hash(*art.png_decode(path.read_bytes()))
    except Exception:
        return None


def status() -> int:
    old, bad = art.manifest(), 0
    files = sorted(art.ROOT.rglob("*.png"))
    for path in files:
        rel = path.relative_to(art.ROOT).as_posix()
        if rel not in old:
            print(f"unknown (the game won't look for it): {rel}")
            continue
        try:
            w, h, rgba = art.png_decode(path.read_bytes())
            pic = art.slice_frames(w, h, rgba)
            if pic.h != art.CELL or pic.w < art.CELL:
                raise ValueError(f"frames must be {art.CELL} high, got {pic.w}×{pic.h}")
        except Exception as e:  # noqa: BLE001 - a report of every kind of broken file
            bad += 1
            print(f"BROKEN: {rel}: {e}")
            continue
        if art.is_redrawn(rel, w, h, rgba):
            print(f"redrawn: {rel}")
    print(f"{len(files)} files, {bad} broken")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("export", "status"))
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    return export(a.check) if a.cmd == "export" else status()


if __name__ == "__main__":
    sys.exit(main())
