"""Bake the bitmap font of the life card (src/kit_the_cat/cardfont.py) from a Spleen BDF file.

    uv run python scripts/bake_font.py path/to/spleen-6x12.bdf

Spleen (https://github.com/fcambus/spleen, BSD-2-Clause) is a real pixel font, so the card needs no font file, no
Pillow and no browser font: a glyph is a few bytes. It has no «є/Є» — they are the mirrored «э/Э», as in every
Cyrillic bitmap font. The licence text goes into the module header.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "src" / "kit_the_cat" / "cardfont.py"
KEEP = (set(range(0x20, 0x7F)) | set(range(0x410, 0x450)) | {0x401, 0x451, 0x404, 0x454, 0x406, 0x456, 0x407, 0x457, 0x490, 0x491}
        | {0xAB, 0xBB, 0xB7, 0xD7, 0x2013, 0x2014, 0x2026, 0x2019, 0x2022})


def parse(text: str) -> tuple[int, int, int, dict[int, list[int]]]:
    """-> (cell width, cell height, baseline row, {codepoint: rows}); each row is an int, bit w-1 = leftmost pixel."""
    w, h, _, yoff = map(int, re.search(r"^FONTBOUNDINGBOX (-?\d+) (-?\d+) (-?\d+) (-?\d+)", text, re.M).groups())
    ascent = h + yoff
    glyphs = {}
    for blk in text.split("STARTCHAR")[1:]:
        enc = int(re.search(r"^ENCODING (-?\d+)", blk, re.M).group(1))
        bw, bh, bx, by = map(int, re.search(r"^BBX (-?\d+) (-?\d+) (-?\d+) (-?\d+)", blk, re.M).groups())
        rows = re.search(r"^BITMAP\n(.*?)\nENDCHAR", blk, re.M | re.S).group(1).split()
        cell = [0] * h
        top = ascent - (by + bh)  # row of the glyph's first line inside the cell
        for i, hx in enumerate(rows):
            bits = int(hx, 16) >> (len(hx) * 4 - bw)  # bw pixels, leftmost is the high bit
            if 0 <= top + i < h:
                cell[top + i] = bits << max(0, w - bw - bx) if bx >= 0 else bits
        glyphs[enc] = cell
    return w, h, ascent, glyphs


def mirror(rows: list[int], w: int) -> list[int]:
    return [int(format(r, f"0{w}b")[::-1], 2) for r in rows]


REDRAWN = {  # Spleen draws «т» as an italic «m» and «я» with straight legs, so a «підняти» reads as «підмами»
    0x442: ["#####.", "..#...", "..#...", "..#...", "..#...", "..#..."],
    0x44F: [".####.", "#...#.", "#...#.", ".####.", "..#.#.", ".#..#."],
}


def redraw(w: int, h: int, ascent: int, g: dict) -> dict[int, list[int]]:
    """Lower-case letters of six rows (x-height) sit on the baseline: rows ascent-6 .. ascent-1."""
    out = {}
    for c, rows in REDRAWN.items():
        cell = [0] * h
        for i, r in enumerate(rows):
            cell[ascent - len(rows) + i] = int(r.replace(".", "0").replace("#", "1").ljust(w, "0"), 2)
        out[c] = cell
    return out


def punctuation(w: int, h: int, ascent: int, g: dict) -> dict[int, list[int]]:
    """Spleen has no dashes, ellipsis, typographic apostrophe or bullet: drawn here, same cell."""
    def at(*rows: tuple[int, int]) -> list[int]:  # (row above the baseline, bits)
        cell = [0] * h
        for up, bits in rows:
            cell[ascent - up] |= bits
        return cell
    full = (1 << w) - 1
    inner = full & ~(1 << (w - 1)) & ~1
    dots = sum(1 << (w - 1 - x) for x in range(0, w, 2))
    mid = 0b11 << (w // 2 - 1)
    return {0x2014: at((4, full)), 0x2013: at((4, inner)), 0x2026: at((1, dots)), 0x2019: list(g[0x27]),
            0x2022: at((5, mid), (6, mid))}


def main() -> None:
    src = Path(sys.argv[1])
    w, h, ascent, g = parse(src.read_text())
    g[0x454], g[0x404] = mirror(g[0x44D], w), mirror(g[0x42D], w)  # є Є = flipped э Э
    g.update(punctuation(w, h, ascent, g))
    g.update(redraw(w, h, ascent, g))
    g = {c: g[c] for c in sorted(KEEP) if c in g}
    missing = sorted(KEEP - set(g))
    lic = (src.parent / "LICENSE-spleen").read_text().strip() if (src.parent / "LICENSE-spleen").exists() else ""
    lines = ['"""Bitmap font of the life card, baked by scripts/bake_font.py from Spleen %dx%d (BSD-2-Clause).' % (w, h), "",
             "Spleen: https://github.com/fcambus/spleen", *("    " + x if x else "" for x in lic.splitlines()), '"""',
             f"CELL_W, CELL_H, ASCENT = {w}, {h}, {ascent}", "# codepoint: hex rows, one per line of the cell, left pixel = high bit",
             "GLYPHS = {"]
    digits = (w + 3) // 4
    for c, rows in g.items():
        lines.append(f'    {c}: "{"".join(format(r, f"0{digits}x") for r in rows)}",')
    lines.append("}")
    OUT.write_text("\n".join(lines) + "\n")
    print(f"{len(g)} glyphs {w}x{h}, missing: {[chr(c) for c in missing]} -> {OUT}")


if __name__ == "__main__":
    main()
