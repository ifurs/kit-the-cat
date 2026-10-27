---
name: kit-sprite-artist
description: Draw new pixel-art for the Kit the Cat game — wearable items (hats, outfits, held things, auras), generated item kinds, genes (ears, tails, faces, patterns, marks), role overlays, species parts, eggs and backgrounds (48×48 procedural sprites in sprites.py / sprites_gen.py / sprites_bg.py). Use whenever the user wants a new item, outfit, accessory, look, background, location, sprite, animation or visual tweak, says something like "add a вишиванка variant", "намалюй фон Нової пошти", "the hat looks off", or when an event needs an item/background that doesn't exist yet.
---

# Drawing Kit the Cat sprites

Everything is code-drawn on a 48×48 canvas, 4 animation frames, scaled ×8. Art must read at small size in a
Telegram chat, fit every species and stage, and stay deterministic (no unseeded randomness while drawing).

## Where things live

| What | File | Registry |
|---|---|---|
| fixed items | `sprites.py`, `it_<id>(cv, b, f)` functions | `ITEMS = {id: ("emoji Назва", slot, fn)}`; slots in `SLOTS` (back, outfit, neck, face, head, held, aura, fg — draw order) |
| generated items | `sprites_gen.py` (`Kind`s per slot, colours/patterns/ornaments with gendered Ukrainian names) | `GEN` |
| genes | `sprites.py` `GENES[gene][value] = ("назва", species or None)`; drawing in `_ears`, `_tail`, `_snout`, `_pattern`, `_mark`, `_extra` | — |
| roles | `ROLE_TINT`, `ROLE_EYE`, `_role_back/_body/_head/_top/_aura` | `ROLES` |
| backgrounds | `sprites_bg.py`, `bg_<id>(cv, f, rng)` (rng is seeded per id — deterministic) | `BACKGROUNDS = {id: ("emoji Назва", fn)}`, modifiers `~night ~winter ~rain…` |

Read two similar existing pieces before drawing (e.g. `it_cap`, `it_vyshyvanka`, `bg_khrushchovka`) and reuse their
helpers.

## Drawing kit

- Geometry comes from `b: Body`: `b.head = (hx, hy, hrx, hry)`, `b.body = (bx, by, brx, bry)`, `b.hand`,
  `_top(b)` → (hx, top, …) for hats, `_eye_xy(b, side)` for face items, `b.stage` (babies are smaller).
  Always anchor to these — never to absolute pixels — so the item fits a tiny piglet and a tall horse.
- Shapes: `ellipse(cx, cy, rx, ry)`, `poly([...])`, `rect(x0, y0, x1, y1)`, `line(...)` return pixel sets.
- Paint: `cv.part(px, fill, shade, light)` (auto outline + shading — use for solid objects), `cv.paint(px, color)`
  (flat pixels, details), `cv.grid(x, y, rows, colors)` for tiny hand-drawn glyphs, `_held(...)` for things in
  the hand.
- Animation: `f` is the frame 0–3; small sways (`f % 2`), blinking lights, orbiting particles. Keep it subtle.
- Palette: saturated but not neon; outline `OUTLINE`; shade with `shade_of(c)`, highlight `light_of(c)`. Items
  are tintable via `id@N`, so a base colour that tints well (mid-lightness) is better than near-black/white.
- Ukrainian name with an emoji, short (shows on buttons and in the shop).

## Ukrainian reality palette (ideas that land)

Items: вишиванка variants, кепка-восьмиклинка, бронік, каска, пакет з пакетами, кільце ковбаси, термос, павербанк,
посилка Нової пошти, номерок ЦНАПу, бабусина хустка, спортивка з трьома смужками, шльопанці з носками, сало.
Backgrounds: Нова пошта, ЦНАП, маршрутка зсередини, плацкарт Укрзалізниці, АТБ, дача з картоплею, під'їзд з
поштовими скриньками, генератор біля кав'ярні, Андріївський узвіз. Respect: military items are worn with dignity
(no mocking defenders); the enemy can be a joke.

## Verify

```bash
uv run python scripts/preview.py --items <id> --stages 1,2,3,4 -o <scratchpad>/item.png   # look at it (Read the PNG)
uv run python scripts/preview.py --all-items head -o <scratchpad>/heads.png               # next to its peers
uv run python scripts/preview.py --bg <id>~night --stages 3 -o <scratchpad>/bg.png
uv run python scripts/preview.py --smoke                                                  # every item × species × stage
uv run python scripts/gen_dsl_docs.py && uv run pytest -q
uv run python scripts/gallery.py      # refresh docs/sprites/ sheets when adding visible content
```

Look at the PNG yourself (Read it) and check: readable at 1×, doesn't cover the eyes (unless it's a mask), no
gaps or stray pixels across species and stages, animation doesn't jitter. For new genes also run
`uv run python scripts/uniqueness.py` — the 200-pet chat must still have 0 look-alikes.

Then wire it into content if asked (`item="id"`, `home=`/`bg=`), and add a line to `CHANGELOG.md` under Unreleased.
