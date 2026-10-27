"""Render sprite sheets into docs/sprites/ — species, hybrids, roles, items, backgrounds, groups…

    uv run python scripts/gallery.py
"""
import random
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from kit_the_cat import sprites as S
from kit_the_cat.sprites import Look

OUT = Path(__file__).resolve().parent.parent / "docs" / "sprites"
CELL = 192  # 48px * 4
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
try:
    FONT = ImageFont.truetype(FONT_PATH, 12)
    TITLE = ImageFont.truetype(FONT_PATH, 18)
except OSError:
    FONT = TITLE = None
LABEL = 32 if FONT else 0


def _wrap(text: str, width: int = 28) -> list[str]:
    out, cur = [], ""
    text = "".join(ch for ch in text if ch.isalnum() or ch in " -:'«»~+.,()@")  # DejaVu has no emoji
    for w in text.split():
        if len(cur) + len(w) + 1 > width and cur:
            out.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    return (out + [cur])[:2]


def sheet(name: str, rows: list[list[tuple[str, Look | Image.Image]]], title: str = "") -> None:
    w = max(len(r) for r in rows)
    head = 28 if title and TITLE else 0
    img = Image.new("RGB", (w * CELL, head + len(rows) * (CELL + LABEL)), (250, 248, 244))
    draw = ImageDraw.Draw(img)
    if head:
        draw.text((8, 4), title, fill=(40, 30, 40), font=TITLE)
    for y, row in enumerate(rows):
        for x, (caption, lk) in enumerate(row):
            frame = lk if isinstance(lk, Image.Image) else S.frames(lk, 1)[0]
            top = head + y * (CELL + LABEL)
            img.paste(frame.resize((CELL, CELL), Image.NEAREST), (x * CELL, top))
            if FONT:
                for i, ln in enumerate(_wrap(caption)):
                    draw.text((x * CELL + 4, top + CELL + 2 + i * 14), ln, fill=(40, 30, 40), font=FONT)
    OUT.mkdir(parents=True, exist_ok=True)
    img.save(OUT / f"{name}.png")
    print("wrote", OUT / f"{name}.png", img.size)


def g(species: str, seed: int, mut: float = 0.07) -> S.Genome:
    return S.random_genome(species, random.Random(seed), mut)


def main() -> None:
    t0 = time.perf_counter()
    sheet("species", [[(f"{sp} {S.rarity(gg)[1][2:]}", Look(genes=gg, stage=3, mood="happy" if i % 3 else "ok"))
                       for i, gg in enumerate(g(sp, k * 13 + len(sp) * 101) for k in range(8))] for sp in S.SPECIES],
          "Species × random genomes (adult)")

    rng = random.Random(5)
    rows = []
    for a_sp, b_sp in (("pig", "cat"), ("dog", "fox"), ("horse", "axolotl"), ("cat", "axolotl"), ("fox", "horse")):
        a, b = g(a_sp, rng.randrange(999)), g(b_sp, rng.randrange(999))
        rows.append([(f"parent {a_sp}", Look(genes=a, stage=3)), (f"parent {b_sp}", Look(genes=b, stage=3))] +
                    [(f"child {i + 1}", Look(genes=S.breed(a, b, rng), stage=2, mood="happy")) for i in range(6)])
    sheet("hybrids", rows, "Breeding: two parents → children")

    roles = list(S.ROLES)
    sheet("roles", [[(f"{r}: {sp}", Look(genes=g(sp, 40 + i), stage=3, role=r, mood="ok" if i % 2 else "happy"))
                     for i, sp in enumerate(S.SPECIES)] +
                    [(f"{r}: baby", Look(genes=g("cat", 7), stage=1, role=r)),
                     (f"{r}: elder+items", Look(genes=g("dog", 9), stage=4, role=r, items=["wizard", "chain", "cane"]))]
                    for r in roles], "Roles on every species / stage")

    ids = list(S.ITEMS)
    rows, row = [], []
    for i, it in enumerate(ids):
        sp = S.SPECIES[i % len(S.SPECIES)]
        row.append((S.item_name(it), Look(genes=g(sp, i), stage=(3, 2, 1, 4)[i % 4], items=[it])))
        if len(row) == 10:
            rows.append(row)
            row = []
    rows.append(row) if row else None
    sheet("items", rows, "Every fixed item (stages rotate: adult/teen/baby/elder)")

    rng = random.Random(11)
    rows = []
    for slot in S.GEN_SLOTS:
        row = []
        for i in range(8):
            it = S.random_item(slot, rng)
            row.append((S.item_name(it), Look(genes=g(S.SPECIES[i % 6], i + 3), stage=(3, 2, 1, 4)[i % 4], items=[it],
                                              background="meadow")))
        rows.append(row)
    sheet("generated_items", rows, f"Generated items gen:<slot>:<base36> — {S.gen_count():,} distinct")

    tint_items = ["cowboy", "hoodie", "cape", "sunglasses", "gen:head:2ab", "gen:outfit:1k3"]
    sheet("tints", [[(f"{S.item_name(it + (f'@{v}' if v else ''))}", Look(genes=g("cat", 3), stage=3,
                                                                          items=[it + (f"@{v}" if v else "")]))
                     for v in range(len(S.TINTS))] for it in tint_items], "Item tints item@N")

    bgs = list(S.BACKGROUNDS)
    rows = [[(f"{b}", Look(genes=g(S.SPECIES[i % 6], i), stage=3, background=b, mood="happy"))
             for i, b in enumerate(bgs[k:k + 8], k)] for k in range(0, len(bgs), 8)]
    sheet("backgrounds", rows, "Backgrounds")
    mods = list(S.BG_MODS)
    bases = ["meadow", "kyiv", "farm", "village", "khrushchovka", "bukovel"]
    rows = [[(f"{base}~{m}", Look(genes=g("fox", 2), stage=3, background=f"{base}~{m}")) for m in mods[:7]] +
            [(f"{base}~{m}", Look(genes=g("fox", 2), stage=3, background=f"{base}~{m}")) for m in mods[7:]]
            for base in bases]
    rows += [[(c, Look(genes=g("cat", 5), stage=3, background=c)) for c in
              ("farm~winter~snow", "meadow~autumn~wind", "village~spring~dawn", "kyiv~night~rain", "field~summer~dusk",
               "chornobyl~fog", "sea~storm", "dacha~autumn~dusk", "mountains~winter~night", "metro~blackout")]]
    sheet("backgrounds_variants", rows, "Background variants base~mod~mod")

    moods = ["happy", "ok", "sad", "angry", "sick", "sleep", "dead"]
    rows = []
    for sp in ("cat", "horse", "axolotl"):
        gg = g(sp, 21)
        rows.append([("egg", Look(genes=gg, stage=0)), ("egg cracked", Look(genes=gg, stage=0, egg_cracks=2))] +
                    [(f"stage {st}", Look(genes=gg, stage=st, mood="happy")) for st in (1, 2, 3, 4)] +
                    [("dirty+hungry", Look(genes=gg, stage=2, dirty=True, hungry=True)),
                     ("ghost", Look(genes=gg, stage=3, ghost=True))])
        rows.append([(m, Look(genes=gg, stage=2, mood=m)) for m in moods] +
                    [("fat", Look(genes=gg, stage=3, fat=1.0))])
    rows.append([(S.EGG_PATTERNS[s % len(S.EGG_PATTERNS)], Look(genes=S.Genome(seed=s), stage=0)) for s in range(12)][:8])
    rows.append([(S.EGG_PATTERNS[s % len(S.EGG_PATTERNS)], Look(genes=S.Genome(seed=s), stage=0, egg_cracks=1))
                 for s in range(8, 12)])
    sheet("moods_stages", rows, "Stages, moods, eggs")

    gene_rows = []
    for gene in ("pattern", "mark", "extra", "color"):
        vals = list(S.GENES[gene])
        for k in range(0, len(vals), 8):
            gene_rows.append([(f"{gene}: {v}", Look(genes=S.Genome(**{**g("cat", 4).to_dict(), gene: v}), stage=3))
                              for v in vals[k:k + 8]])
    sheet("genes", gene_rows, "Gene values (cat base)")

    rng = random.Random(64)
    cells = []
    for i in range(64):
        gg = S.random_genome(rng.choice(S.SPECIES), rng, 0.15)
        items = [S.random_item(s, rng) if rng.random() < 0.5 else rng.choice([k for k, v in S.ITEMS.items() if v[1] == s])
                 for s in ("head", "face", "neck", "outfit", "held", "back", "aura") if rng.random() < 0.35]
        lk = Look(genes=gg, stage=rng.choice((1, 2, 3, 3, 4)), items=items, background=S.random_background(rng),
                  mood=rng.choice(("happy", "ok", "sad", "angry")), role=rng.choice([""] * 6 + list(S.ROLES)))
        cells.append((f"{S.dna_code(gg)} {lk.role}", lk))
    sheet("random_64", [cells[k:k + 8] for k in range(0, 64, 8)], "64 random pets")

    pair = [Look(genes=g("cat", 1), stage=3, mood="happy", items=["flowers"]), Look(genes=g("pig", 2), stage=3, mood="happy")]
    fight = [Look(genes=g("dog", 3), stage=3, mood="angry", items=["sabre"], role="werewolf"),
             Look(genes=g("fox", 4), stage=3, mood="angry", role="vampire")]
    for name, data in (("group_love", S.render_group(pair, "love", between="heart")),
                       ("group_fight", S.render_group(fight, "ruins~storm", between="fight")),
                       ("group_chat", S.render_group(pair, "kitchen", between="chat", labels=["Мурка", "Хрюша"]))):
        (OUT / f"{name}.png").write_bytes(data)
        print("wrote", OUT / f"{name}.png")
    rng = random.Random(12)
    zoo = [Look(genes=S.random_genome(rng.choice(S.SPECIES), rng), stage=rng.choice((1, 2, 3, 4)), mood="happy",
                items=[S.random_item("head", rng)] if i % 3 == 0 else [], role=rng.choice([""] * 4 + list(S.ROLES)))
           for i in range(12)]
    (OUT / "group_zoo.png").write_bytes(S.render_group(zoo, "meadow", labels=[f"Пет {i + 1}" for i in range(12)]))
    (OUT / "group_zoo7.png").write_bytes(S.render_group(zoo[:7], "farm~autumn"))
    (OUT / "group_pair.gif").write_bytes(S.render_group(pair, "meadow~dusk", between="heart", gif=True))
    print("wrote groups")
    (OUT / "sample.gif").write_bytes(S.render_gif(Look(genes=g("fox", 7), stage=3, role="angel", mood="happy",
                                                       items=["gen:held:2nj", "crown"], background="mystic")))
    (OUT / "quantum.gif").write_bytes(S.render_gif(Look(genes=g("cat", 8), stage=3, role="quantum", background="space")))
    print(f"gallery done in {time.perf_counter() - t0:.1f}s")


if __name__ == "__main__":
    main()
