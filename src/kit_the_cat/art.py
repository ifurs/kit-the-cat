"""Redrawable art: PNG files in `kit_the_cat/assets/` that replace the code-drawn sprites, one asset at a time.

`scripts/art.py export` writes every replaceable asset to a PNG and records a hash of its pixels in `manifest.json`.
A file whose pixels still match the manifest is ignored, so the code keeps drawing it; redraw a file and the game
uses the picture. Drawing an asset stays cheap: nothing is read until the asset is first needed, then it is cached.

Layout of a file: one row of frames, 4 frames (a 192×48 strip) or 1 (48×48). See `assets/README.md`.
Stdlib only (the browser build has no Pillow). A broken file is logged and the code-drawn art is used instead.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import struct
import zlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

log = logging.getLogger(__name__)
ROOT = Path(__file__).parent / "assets"
CELL = 48
FRAMES = 4
# template colours of the recolourable parts: a pixel of exactly this colour takes the pet's own colour of that name
KEYS = {"base": (232, 168, 96), "shade": (184, 120, 56), "light": (248, 216, 168), "accent": (208, 80, 80),
        "second": (80, 112, 192)}
# the build bundles redrawn files here for the browser, which has no assets directory: {"items/crown.png": base64}
try:
    from .art_bundle import DATA as BUNDLE  # type: ignore[import-not-found]
except ImportError:
    BUNDLE = None


# --- PNG -----------------------------------------------------------------------------------------

def png_encode(w: int, h: int, rgba: bytes) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))
    raw = b"".join(b"\0" + rgba[y * w * 4:(y + 1) * w * 4] for y in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def _unfilter(raw: bytes, h: int, stride: int, bpp: int) -> bytes:
    out, prev, pos = bytearray(), bytearray(stride), 0
    for _ in range(h):
        kind, line = raw[pos], bytearray(raw[pos + 1:pos + 1 + stride])
        pos += stride + 1
        for i in range(stride):
            a, b, c = line[i - bpp] if i >= bpp else 0, prev[i], prev[i - bpp] if i >= bpp else 0
            if kind == 1:
                line[i] = (line[i] + a) & 255
            elif kind == 2:
                line[i] = (line[i] + b) & 255
            elif kind == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif kind == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
            elif kind != 0:
                raise ValueError(f"bad PNG filter {kind}")
        out += line
        prev = line
    return bytes(out)


def png_decode(data: bytes) -> tuple[int, int, bytes]:
    """(width, height, RGBA) of any non-interlaced 8-bit-or-less PNG: what pixel editors save."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    pos, idat, plte, trns, head = 8, bytearray(), b"", b"", None
    while pos < len(data):
        n, tag = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        pos += n + 12
        if tag == b"IHDR":
            head = struct.unpack(">IIBBBBB", body)
        elif tag == b"PLTE":
            plte = body
        elif tag == b"tRNS":
            trns = body
        elif tag == b"IDAT":
            idat += body
        elif tag == b"IEND":
            break
    if not head:
        raise ValueError("PNG without a header")
    w, h, depth, color, _, _, interlace = head
    if interlace or depth > 8 or color not in (0, 2, 3, 4, 6):
        raise ValueError("save the PNG as 8-bit, not interlaced")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
    stride = (w * channels * depth + 7) // 8
    raw = _unfilter(zlib.decompress(bytes(idat)), h, stride, max(1, channels * depth // 8))
    out = bytearray(w * h * 4)
    for y in range(h):
        row = raw[y * stride:(y + 1) * stride]
        for x in range(w):
            if depth == 8:
                s = row[x * channels:(x + 1) * channels]
            else:  # 1, 2 or 4 bits: grey or palette, packed from the high bits
                bit = x * depth
                s = bytes([(row[bit // 8] >> (8 - depth - bit % 8)) & ((1 << depth) - 1)])
            if color == 3:
                i = s[0]
                r, g, b = plte[i * 3:i * 3 + 3]
                a = trns[i] if i < len(trns) else 255
            elif color == 6:
                r, g, b, a = s
            elif color == 2:
                r, g, b = s
                a = 0 if trns and struct.pack(">HHH", r, g, b) == trns else 255
            else:
                r = g = b = s[0] if depth == 8 else s[0] * 255 // ((1 << depth) - 1)
                a = s[1] if color == 4 else 255
            out[(y * w + x) * 4:(y * w + x + 1) * 4] = bytes((r, g, b, a))
    return w, h, bytes(out)


# --- files ---------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Art:
    """Decoded frames: each is {(x, y): (r, g, b)}, without the transparent pixels."""
    w: int
    h: int
    frames: tuple

    def frame(self, f: int) -> dict:
        return self.frames[f % len(self.frames)]


def pixel_hash(w: int, h: int, rgba: bytes) -> str:
    """Of what the picture looks like, not of the file: an editor re-saving an untouched file changes nothing."""
    flat = bytearray(rgba)
    for i in range(3, len(flat), 4):  # invisible pixels may keep any colour
        if flat[i] < 128:
            flat[i - 3:i + 1] = b"\0\0\0\0"
        else:
            flat[i] = 255
    return hashlib.sha256(struct.pack(">II", w, h) + bytes(flat)).hexdigest()[:16]


def slice_frames(w: int, h: int, rgba: bytes) -> Art:
    """A strip of 4 frames (at least 192 wide) or one frame; alpha under 128 counts as transparent."""
    n = FRAMES if w >= CELL * FRAMES and w % FRAMES == 0 else 1
    fw = w // n
    frames = []
    for k in range(n):
        px = {}
        for y in range(h):
            for x in range(fw):
                i = (y * w + k * fw + x) * 4
                if rgba[i + 3] >= 128:
                    px[(x, y)] = (rgba[i], rgba[i + 1], rgba[i + 2])
        frames.append(px)
    return Art(fw, h, tuple(frames))


@lru_cache(maxsize=1)
def manifest() -> dict:
    try:
        return json.loads((ROOT / "manifest.json").read_text())
    except (OSError, ValueError):
        return {}


def _read(rel: str) -> bytes | None:
    if BUNDLE is not None:
        return base64.b64decode(BUNDLE[rel]) if rel in BUNDLE else None
    try:
        return (ROOT / rel).read_bytes()
    except OSError:
        return None


def is_redrawn(rel: str, w: int, h: int, rgba: bytes) -> bool:
    return pixel_hash(w, h, rgba) != manifest().get(rel)


@lru_cache(maxsize=None)
def load(kind: str, name: str) -> Art | None:
    """The redrawn picture of an asset, or None: not redrawn (the usual case), no file or a broken one."""
    rel = f"{kind}/{name}.png"
    data = _read(rel)
    if data is None:
        return None
    try:
        w, h, rgba = png_decode(data)
        if BUNDLE is None and not is_redrawn(rel, w, h, rgba):
            return None
        art = slice_frames(w, h, rgba)
        if art.h != CELL or art.w < CELL:
            raise ValueError(f"expected frames {CELL} high and at least {CELL} wide, got {art.w}×{art.h}")
        return art
    except (ValueError, IndexError, struct.error, zlib.error) as e:
        log.warning("art %s ignored: %s", rel, e)
        return None


def redrawn_files() -> list[str]:
    """Every art file that differs from what the code draws (the build bundles these for the browser)."""
    out = []
    for path in sorted(ROOT.rglob("*.png")):
        rel = path.relative_to(ROOT).as_posix()
        try:
            w, h, rgba = png_decode(path.read_bytes())
        except (ValueError, IndexError, struct.error, zlib.error):
            continue
        if is_redrawn(rel, w, h, rgba):
            out.append(rel)
    return out


def reload() -> None:
    manifest.cache_clear()
    load.cache_clear()


# --- placing a picture on a pet ------------------------------------------------------------------

def place(cv, px: dict, ref: tuple, at: tuple, keys: dict | None = None) -> None:
    """Paint `px` onto `cv`. ref and at are (x, y, sx, sy): an anchor point and a size in the picture and on this pet.
    The picture is stretched by at/ref around the anchor, so a hat drawn for a grown cat fits a piglet. `keys` maps
    template colours to the pet's colours."""
    if not px:
        return
    ax, ay, asx, asy = at
    rx, ry, rsx, rsy = ref
    kx, ky = (asx / rsx if rsx else 1), (asy / rsy if rsy else 1)
    xs, ys = [p[0] for p in px], [p[1] for p in px]
    x0, x1 = sorted((ax + (min(xs) - rx) * kx, ax + (max(xs) + 1 - rx) * kx))
    y0, y1 = sorted((ay + (min(ys) - ry) * ky, ay + (max(ys) + 1 - ry) * ky))
    out = {}
    for y in range(int(y0) - 1, int(y1) + 2):
        for x in range(int(x0) - 1, int(x1) + 2):
            c = px.get((_floor(rx + (x + 0.5 - ax) / kx), _floor(ry + (y + 0.5 - ay) / ky)))
            if c is not None:
                out[(x, y)] = keys.get(c, c) if keys else c
    for p, c in out.items():
        cv.paint((p,), c)


def _floor(v: float) -> int:
    return int(v // 1)


def fill(cv, art: Art, f: int) -> None:
    """A background: the picture covers the canvas; a wider scene continues it mirrored, tile after tile."""
    px = art.frame(f)
    for y in range(min(cv.h, art.h)):
        for x in range(cv.w):
            tile, col = divmod(x, art.w)
            c = px.get((art.w - 1 - col if tile % 2 else col, y))
            if c is not None:
                cv.px[(x, y)] = c
