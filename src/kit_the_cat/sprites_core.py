"""Raster core shared by sprites*.py: colours, cached shape rasterisers, Canvas, Body anchors."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # Pillow is optional at runtime (extra `images`)
    from PIL import Image

import colorsys
from dataclasses import dataclass
from functools import lru_cache


N = 48
SCALE = 8
OUTLINE = (43, 26, 38)
WHITE = (255, 255, 255)
BLACK = (24, 18, 28)
BLUSH = (255, 140, 160)
GOLD, GOLD_D = (255, 210, 50), (205, 150, 30)
RED, BLUE, YELLOW = (220, 50, 50), (50, 110, 220), (255, 210, 40)

Px = set[tuple[int, int]]


@lru_cache(maxsize=4096)
def ellipse(cx: float, cy: float, rx: float, ry: float) -> frozenset:
    out = set()
    for y in range(int(cy - ry) - 1, int(cy + ry) + 2):
        for x in range(int(cx - rx) - 1, int(cx + rx) + 2):
            if ((x + 0.5 - cx) / rx) ** 2 + ((y + 0.5 - cy) / ry) ** 2 <= 1:
                out.add((x, y))
    return frozenset(out)


def poly(points) -> frozenset:
    return _poly(tuple((float(x), float(y)) for x, y in points))


@lru_cache(maxsize=4096)
def _poly(points: tuple) -> frozenset:
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    out = set()
    n = len(points)
    for y in range(int(min(ys)) - 1, int(max(ys)) + 2):
        py = y + 0.5
        for x in range(int(min(xs)) - 1, int(max(xs)) + 2):
            px, inside, j = x + 0.5, False, n - 1
            for i in range(n):
                xi, yi = points[i]
                xj, yj = points[j]
                if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi) + xi:
                    inside = not inside
                j = i
            if inside:
                out.add((x, y))
    return frozenset(out)


def rect(x0: float, y0: float, x1: float, y1: float) -> Px:
    return {(x, y) for x in range(int(x0), int(x1) + 1) for y in range(int(y0), int(y1) + 1)}


def line(x0: float, y0: float, x1: float, y1: float) -> Px:
    x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
    out, dx, dy = set(), abs(x1 - x0), -abs(y1 - y0)
    sx, sy, err = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1), abs(x1 - x0) - abs(y1 - y0)
    while True:
        out.add((x0, y0))
        if x0 == x1 and y0 == y1:
            return out
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def dilate(px) -> Px:
    return {(x + dx, y + dy) for x, y in px for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))} - set(px)


def mix(a: tuple, b: tuple, t: float) -> tuple:
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))


def hsv(h: float, s: float, v: float) -> tuple:
    r, gg, b = colorsys.hsv_to_rgb(h % 1, min(1, max(0, s)), min(1, max(0, v)))
    return int(r * 255), int(gg * 255), int(b * 255)


def lum(c: tuple) -> float:
    return c[0] * 0.3 + c[1] * 0.59 + c[2] * 0.11


def shade_of(c: tuple) -> tuple:
    return mix(c, OUTLINE, 0.32)


def light_of(c: tuple) -> tuple:
    return mix(c, WHITE, 0.4)



def _pil():
    """Pillow is only needed to encode images (extra `images`); drawing on Canvas works without it."""
    try:
        from PIL import Image
    except ImportError as e:
        raise RuntimeError("Encoding images needs Pillow: pip install 'kit-the-cat[images]'") from e
    return Image


class Canvas:
    def __init__(self, w: int = N, h: int = N, ox: int = 0):
        self.w, self.h, self.ox = w, h, ox
        self.px: dict[tuple[int, int], tuple] = {}
        self.base: dict | None = None  # read-only backdrop (e.g. background under a pet layer)
        self.bx = 0                    # backdrop x offset

    def get(self, x: int, y: int) -> tuple | None:
        """Colour visible at local (x, y): own pixels first, then the backdrop."""
        c = self.px.get((x + self.ox, y))
        if c is None and self.base is not None:
            c = self.base.get((x + self.bx, y))
        return c

    def paint(self, pixels, color: tuple) -> None:
        w, h, ox, d = self.w, self.h, self.ox, self.px
        for x, y in pixels:
            x += ox
            if 0 <= x < w and 0 <= y < h:
                d[(x, y)] = color

    def part(self, pixels, fill: tuple, shade: tuple | None = None, light: tuple | None = None,
             outline: tuple | None = OUTLINE):
        if not pixels:
            return pixels
        if outline:
            self.paint(dilate(pixels), outline)
        if not shade:
            self.paint(pixels, fill)
            return pixels
        xs, ys = [p[0] for p in pixels], [p[1] for p in pixels]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        cx, cy = (x0 + x1 + 1) / 2, (y0 + y1 + 1) / 2
        rx, ry = max(1, (x1 - x0 + 1) / 2), max(1, (y1 - y0 + 1) / 2)
        w, h, ox, d = self.w, self.h, self.ox, self.px
        for x, y in pixels:
            nx, ny = (x + 0.5 - cx) / rx, (y + 0.5 - cy) / ry
            if nx * 0.35 + ny * 0.9 > 0.62:
                c = shade
            elif light and -nx * 0.5 - ny * 0.8 > 0.55:
                c = light
            else:
                c = fill
            if 0 <= x + ox < w and 0 <= y < h:
                d[(x + ox, y)] = c
        return pixels

    def grid(self, x0: float, y0: float, rows: list[str], colors: dict[str, tuple], outline: bool = False) -> None:
        """Hand-drawn mini sprite: each char is a colour key, '.' is transparent."""
        pts = {(int(x0) + dx, int(y0) + dy): ch for dy, r in enumerate(rows) for dx, ch in enumerate(r) if ch != "."}
        if outline:
            self.paint(dilate(set(pts)), OUTLINE)
        for p, ch in pts.items():
            self.paint((p,), colors[ch])

    def raw(self) -> Image.Image:
        """1:1 RGB image (needs Pillow)."""
        Image = _pil()
        w, h = self.w, self.h
        data = bytearray(w * h * 3)
        for (x, y), c in self.px.items():
            if 0 <= x < w and 0 <= y < h:
                i = (y * w + x) * 3
                data[i], data[i + 1], data[i + 2] = c[0], c[1], c[2]
        return Image.frombytes("RGB", (w, h), bytes(data))

    def image(self, scale: int = SCALE) -> Image.Image:
        return self.raw().resize((self.w * scale, self.h * scale), _pil().NEAREST)


@dataclass
class Body:
    head: tuple
    body: tuple
    ex: int
    head_px: Px
    body_px: Px
    pal: tuple
    stage: int = 3

    @property
    def hand(self) -> tuple[int, int]:
        bx, by, brx, _ = self.body
        return int(bx + brx - 1), int(by - 1)


def _top(b: Body) -> tuple[int, int, int]:
    hx, hy, hrx, hry = b.head
    return hx, hy - hry, hrx


def _eye_xy(b: Body, s: int) -> tuple[int, int]:
    hx, hy, _, _ = b.head
    return hx + s * b.ex - (1 if s < 0 else 0), hy - 1


def _held(cv: Canvas, b: Body, rows: list[str], colors: dict, dx: int = 0, dy: int = 0) -> None:
    x, y = b.hand
    cv.grid(x + dx, y - len(rows) + 3 + dy, rows, colors, outline=True)
