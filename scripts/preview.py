"""Render a quick sprite sheet to look at while drawing: every species (or one) × stages, with items/role/background.

    uv run python scripts/preview.py --items cap,vyshyvanka --bg kyiv~night -o /tmp/p.png
    uv run python scripts/preview.py --role vampire --species fox --stages 1,2,3,4
    uv run python scripts/preview.py --all-items head           # every fixed item of a slot on one species
    uv run python scripts/preview.py --smoke                    # draw every item × species × stage, report crashes

Needs the `images` extra (Pillow). Seeds are fixed, so the same command gives the same picture.
"""
import argparse
import random
import traceback

from PIL import Image

from kit_the_cat import sprites as S

CELL = S.N * 4


def sheet(looks: list[S.Look], cols: int) -> Image.Image:
    rows = (len(looks) + cols - 1) // cols
    img = Image.new("RGBA", (cols * CELL, rows * CELL), (0, 0, 0, 0))
    for i, lk in enumerate(looks):
        img.paste(S.frames(lk, 1)[0].resize((CELL, CELL), Image.NEAREST), ((i % cols) * CELL, (i // cols) * CELL))
    return img


def smoke() -> int:
    bad = 0
    rng = random.Random(1)
    items = list(S.ITEMS) + [S.random_item(slot, rng) for slot in S.GEN_SLOTS for _ in range(8)]
    for sp in S.SPECIES:
        g = S.random_genome(sp, random.Random(sp))
        for stage in (1, 2, 3, 4):
            for it in items:
                try:
                    S.frame_canvases(S.Look(genes=g, stage=stage, items=[it]), 4)
                except Exception:
                    bad += 1
                    print(f"FAIL {sp} stage {stage} item {it}\n{traceback.format_exc(limit=3)}")
    for bg in S.BACKGROUNDS:
        try:
            S.frame_canvases(S.Look(background=bg), 2)
        except Exception:
            bad += 1
            print(f"FAIL background {bg}\n{traceback.format_exc(limit=3)}")
    print(f"smoke: {len(items)} items × {len(S.SPECIES)} species × 4 stages, {len(S.BACKGROUNDS)} backgrounds — "
          f"{'OK' if not bad else f'{bad} failures'}")
    return bad


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--species", help="one species (default: all)")
    ap.add_argument("--stages", default="3", help="comma list, e.g. 1,2,3,4")
    ap.add_argument("--items", default="", help="comma list of item ids (id@tint, gen:slot:code ok)")
    ap.add_argument("--all-items", metavar="SLOT", help="one cell per fixed item of this slot")
    ap.add_argument("--role", default="")
    ap.add_argument("--bg", default="meadow")
    ap.add_argument("--mood", default="happy")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("-o", "--out", default="preview.png")
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    if a.smoke:
        raise SystemExit(1 if smoke() else 0)
    species = [a.species] if a.species else S.SPECIES
    stages = [int(s) for s in a.stages.split(",")]
    items = [i for i in a.items.split(",") if i]
    rng = random.Random(a.seed)
    looks = []
    if a.all_items:
        g = S.random_genome(species[0], rng)
        for it, (_, slot, _) in S.ITEMS.items():
            if slot == a.all_items:
                looks.append(S.Look(genes=g, stage=stages[-1], items=[it] + items, background=a.bg, mood=a.mood, role=a.role))
    else:
        for sp in species:
            g = S.random_genome(sp, rng)
            looks += [S.Look(genes=g, stage=st, items=items, background=a.bg, mood=a.mood, role=a.role) for st in stages]
    cols = len(stages) if not a.all_items else 6
    sheet(looks, cols).save(a.out)
    print(f"wrote {a.out}: {len(looks)} sprites")


if __name__ == "__main__":
    main()
