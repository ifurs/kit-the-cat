# Art of Kit the Cat

Everything here can be redrawn. Open a PNG in any pixel editor (Aseprite, Piskel, GIMP, LibreSprite), draw over it, save
it under the same name. The game uses the new picture straight away, in the bot and in the browser build. A file that
was not changed is ignored, and the code keeps drawing that asset.

To go back to the original: `git checkout -- <file>`.

## The format

- Height 48. One frame is 48×48 (or wider for a background). A strip of 4 frames in a row is the animation: 192×48.
  A picture can be a single frame even if the original had four.
- Transparency is real transparency (alpha below 50% counts as empty). No smoothing or anti-aliasing: hard pixels.
- 8-bit PNG (RGB, RGBA, greyscale or indexed), not interlaced.
- Outline colour of the game: `#2b1a26`.

## What is where

| Folder | What | How it lands in the game |
|---|---|---|
| `backgrounds/` | scenes (31) | fills the scene; no transparency. Night, snow and rain are added on top automatically. A two-pet scene is wider: the picture continues mirrored. A frame may be drawn wider than 48 |
| `items/` | wearable items (75) | drawn on the reference body, see below. Colour variants (`@N`) are derived from your picture |
| `generated/` | shapes of shop items: `<slot>.<kind>.png` (108) | same as items; **template colours**. Patterns, ornaments and trims of that kind are no longer drawn once it is redrawn |
| `ears/` `tail/` `face/` `extra/` | body parts by gene (53) | **template colours** |
| `mark/` | marks on the forehead (10) | the main colour is a template colour |
| `markers/` | what floats between two pets: heart, fight, chat, gift, music | drawn from the top left corner, about 7×7 |
| `icons/` | small icons of the life card | drawn from the top left corner, 7×7 |

**The reference body.** Items and parts are drawn for a grown cat with a round head and body, standing where the file
shows them. On another pet they are moved and stretched to its head or body, so one hat fits a piglet and a horse:

| Slot | Hangs on | Stretched by |
|---|---|---|
| head | the top of the head | head width |
| face, ears, extra | the middle of the head | head size |
| neck | the chin | head width |
| outfit, back | the middle of the body | body size |
| held | the paw | no |
| aura, tail | the body | no |
| fg | the whole frame | no |

**Template colours** are replaced by the colours of this particular pet or item. Use exactly these values; any other
colour stays as you drew it:

| Colour | Value | On a pet | On a generated item |
|---|---|---|---|
| base | `#e8a860` | main fur | main colour |
| shade | `#b87838` | fur in shadow | main colour, shaded (`#ab7a4d` too) |
| light | `#f8d8a8` | light fur | main colour, lit (`#f1ca9f` too) |
| accent | `#d05050` | inner ear, nose | second colour |
| second | `#5070c0` | pattern colour | — |

## Still drawn by code

Head and body shapes, fur patterns, eyes and mouths (they depend on the mood), wings as a gene, the supernatural
role overlays and eggs. The generator combines them per pet, so a pet stays unique.

The interface is in `web/`: icons in `web/icons/` (`scripts/make_icons.py`), the font in `web/fonts/`, colours in the
`:root` block at the top of `web/index.html` and `sandbox/static/index.html`.

## Commands

```bash
uv run python scripts/art.py status   # what is redrawn, what is broken
uv run python scripts/art.py export   # after a change in the sprite code: refresh the originals (keeps redrawn files)
uv run python scripts/preview.py --items crown --stages 1,2,3,4 -o crown.png   # see an item on every age
```
