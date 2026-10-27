"""Procedural items: ``gen:<slot>:<n>`` where n is base36 (e.g. ``gen:head:1z4k``).

n is decoded mixed-radix into kind × colour × colour2 × pattern/ornament/lens/pendant/trim/motion…,
so every id below ``gen_count(slot)`` is a distinct item (ids above wrap around). Tints still work:
``gen:head:1z4k@3``. Names are generated in Ukrainian with gender agreement, e.g.
"🎩 Фіолетовий циліндр у рожевий горошок з пером".
"""
import math
import random
from dataclasses import dataclass
from functools import lru_cache
from types import SimpleNamespace

from .sprites_core import (BLACK, GOLD, OUTLINE, WHITE, YELLOW, N, Body, Canvas, _eye_xy, _top, dilate,
                                        ellipse, hsv, light_of, line, mix, poly, rect, shade_of)

# --- colours with Ukrainian adjective forms ---------------------------------------------------
GCOL = [
    ("червон", 0, (220, 50, 50)), ("помаранчев", 0, (245, 140, 40)), ("жовт", 0, (250, 210, 50)),
    ("салатов", 0, (160, 220, 70)), ("зелен", 0, (50, 160, 80)), ("бірюзов", 0, (40, 195, 185)),
    ("блакитн", 0, (110, 190, 250)), ("син", 1, (50, 90, 210)), ("фіолетов", 0, (140, 70, 200)),
    ("рожев", 0, (250, 130, 180)), ("малинов", 0, (200, 40, 110)), ("бордов", 0, (130, 30, 50)),
    ("коричнев", 0, (140, 90, 50)), ("бежев", 0, (225, 200, 160)), ("чорн", 0, (52, 48, 60)),
    ("біл", 0, (246, 246, 246)), ("сір", 0, (150, 150, 160)), ("золот", 0, (255, 205, 50)),
    ("срібн", 0, (205, 210, 220)), ("м'ятн", 0, (160, 235, 200)),
]
_END = {0: dict(m="ий", f="а", n="е", p="і", im="им", if_="ою", ip="ими", af="у"),
        1: dict(m="ій", f="я", n="є", p="і", im="ім", if_="ьою", ip="іми", af="ю")}
INS = {"m": "im", "n": "im", "f": "if_", "p": "ip"}


def adj(stem_soft: tuple, form: str) -> str:
    return stem_soft[0] + _END[stem_soft[1]][form]


def cadj(ci: int, form: str) -> str:
    return adj(GCOL[ci], form)


def z(word: str) -> str:
    """Preposition з/із before an instrumental phrase."""
    return ("із " if word[:1].lower() in "зсцчшщж" else "з ") + word


# --- shared patterns ---------------------------------------------------------------------------
PAT = [  # key, phrase(c2 index)
    ("plain", None), ("stripes", lambda c: "у " + cadj(c, "af") + " смужку"),
    ("dots", lambda c: "у " + cadj(c, "m") + " горошок"), ("checks", lambda c: "у " + cadj(c, "af") + " клітинку"),
    ("zigzag", lambda c: z(cadj(c, "im") + " зигзагом")), ("stars", lambda c: z(cadj(c, "ip") + " зірочками")),
    ("hearts", lambda c: z(cadj(c, "ip") + " сердечками")), ("ornament", lambda c: z(cadj(c, "im") + " орнаментом")),
    ("band", lambda c: z(cadj(c, "if_") + " стрічкою")),
]


def _apply_pat(cv: Canvas, px, key: str, c2: tuple, band: list[int]) -> None:
    if key == "plain" or not px:
        return
    px = set(px)
    if key == "stripes":
        sel = {p for p in px if p[1] % 3 == 0}
    elif key == "dots":
        sel = {p for p in px if p[1] % 3 == 1 and (p[0] + (p[1] // 3) * 2) % 4 == 0}
    elif key == "checks":
        sel = {p for p in px if (p[0] // 2 + p[1] // 2) % 2 == 0}
    elif key == "zigzag":
        sel = {p for p in px if (p[1] - abs(p[0] % 4 - 2)) % 5 == 0}
    elif key == "ornament":
        sel = {p for p in px if (p[1] // 3) % 2 == 0 and ((p[0] + p[1]) % 4 == 0 or (p[0] - p[1]) % 4 == 0)}
    elif key == "band":
        sel = {p for p in px if p[1] in band} if band else {p for p in px if p[1] == max(q[1] for q in px) - 1}
    else:  # stars / hearts — tiny motifs on a grid
        rows = [".a.", "aaa", ".a."] if key == "stars" else ["a.a", "aaa", ".a."]
        sel = set()
        for x, y in px:
            if x % 5 == 0 and y % 5 == (2 if (x // 5) % 2 else 0):
                sel |= {(x + dx - 1, y + dy) for dy, r in enumerate(rows) for dx, ch in enumerate(r) if ch == "a"}
        sel &= px
    cv.paint(sel, c2)


# --- hats --------------------------------------------------------------------------------------

def _hat(kind: str, b: Body, f: int) -> dict:
    hx, top, hrx = _top(b)
    hy = b.head[1]
    d = dict(crown=set(), brim=[], band=[], side=(hx - 4, top), top=(hx, top - 4), pat=True)
    if kind == "tophat":
        d.update(crown=rect(hx - 5, top - 8, hx + 4, top + 1), brim=[(rect(hx - 8, top + 1, hx + 7, top + 2), None)],
                 band=[top - 1, top], side=(hx - 4, top - 1), top=(hx, top - 9))
    elif kind == "bowler":
        d.update(crown={p for p in ellipse(hx, top - 0.5, 6, 5) if p[1] <= top + 1},
                 brim=[(ellipse(hx, top + 1.5, 9, 1.6), None)], band=[top, top - 1], side=(hx - 4, top - 1),
                 top=(hx, top - 6))
    elif kind == "beret":
        d.update(crown=ellipse(hx - 1, top + 0.5, 9, 3), brim=[(rect(hx - 1, top - 3, hx, top - 2), None)],
                 band=[top + 2], side=(hx + 5, top), top=(hx - 1, top - 3))
    elif kind == "beanie":
        d.update(crown={p for p in ellipse(hx, top + 4, hrx, 7) if p[1] <= top + 3}, band=[top + 2, top + 3],
                 side=(hx - 5, top + 1), top=(hx, top - 3))
    elif kind == "cone":
        d.update(crown=poly([(hx - 5, top + 2), (hx + 1, top - 11), (hx + 5, top + 2)]), band=[top + 1],
                 side=(hx - 2, top - 1), top=(hx + 1, top - 11))
    elif kind == "crown":
        d.update(crown=poly([(hx - 6, top + 2), (hx - 6, top - 4), (hx - 3, top - 1), (hx, top - 5), (hx + 3, top - 1),
                             (hx + 6, top - 4), (hx + 6, top + 2)]), band=[top + 1], side=(hx, top - 1),
                 top=(hx, top - 6), pat=False)
    elif kind == "witch":
        d.update(crown=poly([(hx - 5, top + 2), (hx + 3, top - 11), (hx + 5, top + 2)]) | line(hx + 3, top - 11, hx + 6, top - 9),
                 brim=[(ellipse(hx, top + 2, 12, 1.8), None)], band=[top, top + 1], side=(hx - 3, top),
                 top=(hx + 6, top - 9))
    elif kind == "cap":
        d.update(crown={p for p in ellipse(hx, top + 3, hrx - 1, 6) if p[1] <= top + 3},
                 brim=[(ellipse(hx + 3, top + 4, 8, 1.6), None)], side=(hx - 5, top + 1), top=(hx, top - 3))
    elif kind == "tiara":
        d.update(crown=rect(hx - 6, top + 1, hx + 6, top + 2) | poly([(hx - 3, top + 1), (hx, top - 4), (hx + 3, top + 1)])
                 | poly([(hx - 7, top + 1), (hx - 5, top - 2), (hx - 3, top + 1)])
                 | poly([(hx + 3, top + 1), (hx + 5, top - 2), (hx + 7, top + 1)]),
                 side=(hx, top - 1), top=(hx, top - 4), pat=False)
    elif kind == "panama":
        d.update(crown=poly([(hx - 5, top + 1.5), (hx - 4, top - 4), (hx + 4, top - 4), (hx + 5, top + 1.5)]),
                 brim=[(poly([(hx - 10, top + 4), (hx - 6, top + 1), (hx + 6, top + 1), (hx + 10, top + 4)]), None)],
                 band=[top, top - 1], side=(hx - 3, top - 1), top=(hx, top - 5))
    elif kind == "fez":
        tassel = line(hx, top - 6, hx + 4, top - 4) | rect(hx + 4, top - 4, hx + 4, top - 1 + f % 2)
        d.update(crown=poly([(hx - 4, top + 1.5), (hx - 3, top - 6), (hx + 3, top - 6), (hx + 4, top + 1.5)]),
                 brim=[(tassel, BLACK)], band=[top, top - 1], side=(hx - 2, top - 2), top=(hx - 1, top - 6))
    elif kind == "sombrero":
        d.update(crown={p for p in ellipse(hx, top - 2, 5, 5.5) if p[1] <= top + 1},
                 brim=[(ellipse(hx, top + 2, 15, 2.2), None)], band=[top, top - 1], side=(hx - 3, top - 1),
                 top=(hx, top - 7))
    elif kind == "ushanka":
        flaps = rect(hx - hrx - 1, top + 3, hx - hrx + 2, hy + 1) | rect(hx + hrx - 3, top + 3, hx + hrx, hy + 1)
        fur = rect(hx - hrx, top + 1, hx + hrx - 1, top + 4)
        d.update(crown={p for p in ellipse(hx, top + 3, hrx + 1, 7) if p[1] <= top + 2},
                 brim=[(flaps, "fur"), (fur, "fur")], side=(hx - 1, top - 1), top=(hx, top - 4))
    elif kind == "viking":
        horns = set()
        for s in (-1, 1):
            horns |= poly([(hx + s * (hrx - 2), top + 2), (hx + s * (hrx + 4), top - 6), (hx + s * (hrx + 2), top - 6),
                           (hx + s * (hrx + 1), top - 1), (hx + s * (hrx - 4), top)])
        d.update(crown={p for p in ellipse(hx, top + 4, hrx + 1, 7) if p[1] <= top + 4},
                 brim=[(horns, (240, 232, 205)), (rect(hx - hrx - 1, top + 4, hx + hrx, top + 4), None)],
                 band=[top + 2], side=(hx, top), top=(hx, top - 3))
    elif kind == "bandana":
        crown = {p for p in b.head_px if top <= p[1] <= top + 3} or rect(hx - hrx + 2, top, hx + hrx - 2, top + 3)
        knot = poly([(hx + hrx - 2, top + 2), (hx + hrx + 4, top + 3 + f % 2), (hx + hrx + 3, top + 7)])
        d.update(crown=crown, brim=[(knot, "c")], side=(hx - 4, top + 1), top=(hx, top - 1))
    elif kind == "cowboy":
        d.update(crown=rect(hx - 5, top - 5, hx + 5, top + 1) - {(hx, top - 5), (hx - 1, top - 5)},
                 brim=[(ellipse(hx, top + 1.5, 11, 1.8), None)], band=[top - 1], side=(hx - 3, top - 1),
                 top=(hx, top - 6))
    elif kind == "grad":  # академічна шапочка
        board = poly([(hx - 10, top - 2), (hx, top - 6), (hx + 10, top - 2), (hx, top + 2)])
        tassel = line(hx, top - 2, hx + 7, top) | rect(hx + 7, top, hx + 7, top + 4 + f % 2)
        d.update(crown=rect(hx - 5, top - 1, hx + 5, top + 2), brim=[(board, None), (tassel, GOLD)], band=[top + 1],
                 side=(hx - 3, top + 1), top=(hx, top - 5))
    return d


ORN = [  # key, noun instrumental, gender, anchor
    ("none", "", "", ""), ("feather", "пером", "n", "side"), ("flower", "квіткою", "f", "side"),
    ("star", "зіркою", "f", "side"), ("bow", "бантиком", "m", "side"), ("pompom", "помпоном", "m", "top"),
    ("skull", "черепом", "m", "side"), ("heart", "сердечком", "n", "side"), ("trident", "тризубом", "m", "side"),
    ("crystal", "кристалом", "m", "top"), ("propeller", "пропелером", "m", "top"), ("horns", "ріжками", "p", "top"),
    ("antenna", "антенкою", "f", "top"),
]


def _ornament(cv: Canvas, key: str, x: int, y: int, c2: tuple, f: int) -> None:
    sh = shade_of(c2)
    if key == "feather":
        cv.part(line(x, y, x - 2, y - 6) | line(x + 1, y, x - 1, y - 6) | {(x - 2, y - 7)}, c2, outline=OUTLINE)
        cv.paint(line(x, y, x - 2, y - 6), sh)
    elif key == "flower":
        cv.grid(x - 1, y - 1, [".a.", "aba", ".a."], {"a": c2, "b": YELLOW}, outline=True)
    elif key == "star":
        cv.grid(x - 2, y - 2, ["..a..", "aaaaa", ".aaa.", ".a.a."], {"a": c2}, outline=True)
    elif key == "bow":
        cv.grid(x - 2, y - 1, ["aa.aa", "abbba", "aa.aa"], {"a": c2, "b": sh}, outline=True)
    elif key == "pompom":
        cv.part(ellipse(x + 0.5, y - 1, 2.3, 2.3), c2, sh, light_of(c2))
    elif key == "skull":
        cv.grid(x - 1, y - 2, ["aaa", "bab", "aaa", "a.a"], {"a": c2, "b": BLACK}, outline=True)
    elif key == "heart":
        cv.grid(x - 1, y - 1, ["a.a", "aaa", ".a."], {"a": c2}, outline=True)
    elif key == "trident":
        cv.grid(x - 2, y - 2, ["a.a.a", "a.a.a", "aaaaa", "..a.."], {"a": c2}, outline=True)
    elif key == "crystal":
        cv.part(poly([(x - 2, y - 2), (x + 0.5, y - 6), (x + 3, y - 2), (x + 0.5, y + 1)]), c2, sh, light_of(c2))
    elif key == "propeller":
        cv.paint(line(x, y, x, y - 2), OUTLINE)
        cv.part(rect(x - 3, y - 3, x + 3, y - 3) if f % 2 else rect(x - 1, y - 3, x + 1, y - 3), c2)
    elif key == "horns":
        for s in (-1, 1):
            cv.part(poly([(x + s * 2, y + 3), (x + s * 5, y - 3), (x + s * 4.5, y + 3)]), c2, sh)
    elif key == "antenna":
        cv.paint(line(x, y, x + 2, y - 4), OUTLINE)
        cv.part(ellipse(x + 2.5, y - 5, 1.4, 1.4), c2 if f % 2 else light_of(c2))


def draw_hat(cv, b, f, p):
    g = _hat(p.kind, b, f)
    c = p.c
    cv.part(g["crown"], c, shade_of(c), light_of(c))
    if g["pat"]:
        _apply_pat(cv, g["crown"], p.pat, p.c2, g["band"])
    for px, col in g["brim"]:
        col = mix(c, WHITE, 0.55) if col == "fur" else c if col == "c" else col
        cv.part(px, col or c, shade_of(col or c))
    if p.orn != "none":
        anchor = ORN[[o[0] for o in ORN].index(p.orn)][3]
        _ornament(cv, p.orn, *g[anchor], p.c2, f)
    if p.kind in ("crown", "tiara"):  # gems
        x, y = g["side"]
        cv.part(ellipse(x + 0.5, y + 0.5, 1.2, 1.2), p.c2, outline=None)


# --- glasses / face ----------------------------------------------------------------------------
LENS = [("темн", 0, (36, 36, 52), 1.0), ("прозор", 0, (215, 235, 250), 0.3), ("червон", 0, (230, 60, 60), 0.6),
        ("син", 1, (70, 120, 230), 0.6), ("зелен", 0, (80, 200, 110), 0.6), ("рожев", 0, (255, 140, 200), 0.6),
        ("жовт", 0, (255, 215, 70), 0.55), ("дзеркальн", 0, (180, 205, 230), 1.0), ("райдужн", 0, None, 1.0)]


def _lens(cv: Canvas, px, li: int, f: int) -> None:
    _, _, col, alpha = LENS[li]
    for x, y in px:
        c = hsv((x + y + f * 2) / 9, 0.7, 1.0) if col is None else col
        under = cv.get(x, y)
        cv.paint({(x, y)}, mix(under, c, alpha) if under and alpha < 1 else c)
    if alpha >= 1 and px:
        x0, y0 = min(px, key=lambda q: (q[1], q[0]))
        cv.paint({(x0 + 1, y0 + 1)} & set(px) or {(x0, y0)}, WHITE)


def draw_glasses(cv, b, f, p):
    hx, hy, hrx, _ = b.head
    c, k = p.c, p.kind
    ey = hy - 1
    eyes = [_eye_xy(b, s) for s in (-1, 1)]
    if k == "visor":
        lens = rect(hx - hrx + 2, ey - 2, hx + hrx - 3, ey + 1)
        cv.part(lens, c, outline=OUTLINE)
        inner = rect(hx - hrx + 3, ey - 1, hx + hrx - 4, ey)
        _lens(cv, inner, p.lens, f)
        cv.paint({(hx - hrx + 3 + (f * 3) % (2 * hrx - 6), ey - 1)}, WHITE)
        return
    if k == "mask":
        m = set()
        for x, y in eyes:
            m |= ellipse(x + 0.5, y + 0.5, 3.6, 2.6)
        m |= rect(eyes[0][0], ey - 1, eyes[1][0], ey + 1)
        m |= poly([(hx - 9, ey - 1), (hx - 11, ey - 5), (hx - 6, ey - 2)]) | poly([(hx + 8, ey - 1), (hx + 10, ey - 5), (hx + 5, ey - 2)])
        holes = set().union(*(rect(x - 1, y - 1, x + 1, y + 1) for x, y in eyes))
        saved = {q: cv.get(*q) for q in holes}
        cv.part(m, c, shade_of(c), light_of(c))
        for q, col in saved.items():
            if col:
                cv.paint({q}, col)
        spark = LENS[p.lens][2] or hsv(f / 4, 0.7, 1)
        cv.paint({(hx - 9, ey - 4), (hx + 9, ey - 4), (hx, ey - 2)} & m, spark)
        return
    if k == "goggles":
        cv.paint(line(hx - hrx, ey - 1, hx + hrx - 1, ey - 1) | line(hx - hrx, ey, hx + hrx - 1, ey), shade_of(c))
    pair = [eyes[1]] if k == "monocle" else eyes
    for i, (x, y) in enumerate(pair):
        s = -1 if (k != "monocle" and i == 0) else 1
        cx, cy = x + 0.5, y + 0.5
        if k in ("round", "pincenez", "monocle"):
            r = 2.0 if k == "pincenez" else 2.6
            lens = ellipse(cx, cy, r, r)
        elif k == "square":
            lens = rect(x - 2, y - 2, x + 2, y + 1)
        elif k == "aviator":
            lens = poly([(x - 2.5, y - 2), (x + 3.5, y - 2), (x + 3, y + 1.5), (x + 0.5, y + 2.8), (x - 2, y + 1.5)])
        elif k == "cateye":
            lens = ellipse(cx, cy, 2.6, 2.0) | {(x + s * 3, y - 2), (x + s * 2, y - 2)}
        elif k == "heart":
            lens = {(x - 2 + dx, y - 2 + dy) for dy, r in enumerate(["aa.aa", "aaaaa", ".aaa.", "..a.."])
                    for dx, ch in enumerate(r) if ch == "a"}
        elif k == "star":
            lens = {(x - 2 + dx, y - 2 + dy) for dy, r in enumerate(["..a..", "aaaaa", ".aaa.", ".a.a."])
                    for dx, ch in enumerate(r) if ch == "a"}
        elif k == "hex":
            lens = poly([(cx - 3, cy), (cx - 1.5, cy - 2.6), (cx + 1.5, cy - 2.6), (cx + 3, cy), (cx + 1.5, cy + 2.6),
                         (cx - 1.5, cy + 2.6)])
        else:  # goggles
            lens = ellipse(cx, cy, 3, 2.6)
        frame = dilate(lens)
        if k == "goggles":
            frame |= dilate(frame | lens)
        cv.paint(frame, c)
        _lens(cv, lens, p.lens, f)
    if k == "monocle":
        x, y = eyes[1]
        cv.paint(line(x + 2, y + 3, x + 3, y + 8), c)
        return
    (lx, _), (rx, _) = eyes
    cv.paint(line(lx + 3, ey - 1, rx - 3, ey - 1), c)
    if k == "pincenez":
        cv.paint(line(rx + 2, ey + 2, rx + 4, ey + 7), GOLD)
    elif k != "goggles":
        cv.paint(line(lx - 3, ey - 1, hx - hrx + 1, ey - 2) | line(rx + 3, ey - 1, hx + hrx - 2, ey - 2), c)


# --- neck --------------------------------------------------------------------------------------
PEND = [  # key, instrumental noun, gender, rows
    ("none", "", "", None), ("heart", "сердечком", "n", ["a.a", "aaa", ".a."]),
    ("star", "зіркою", "f", [".a.", "aaa", "a.a"]), ("skull", "черепом", "m", ["aaa", "bab", ".a."]),
    ("crystal", "кристалом", "m", [".a.", "aab", ".b."]), ("coin", "монетою", "f", [".a.", "aba", ".a."]),
    ("key", "ключем", "m", [".a.", "a.a", ".a.", ".aa"]), ("tooth", "зубом", "m", ["aaa", "aaa", "a.a"]),
    ("trident", "тризубом", "m", ["a.a.a", "aaaaa", "..a.."]), ("moon", "місяцем", "m", [".aa", "a..", ".aa"]),
    ("horseshoe", "підковою", "f", ["a.a", "a.a", "aaa"]), ("eye", "оком", "n", [".a.", "aba", ".a."]),
    ("acorn", "жолудем", "m", ["bbb", "aaa", ".a."]),
]


def _arc(hx: int, ny: int, w: int = 6) -> list[tuple[int, int]]:
    return [(hx + dx, ny - 1 + abs(dx) // 3) for dx in range(-w, w + 1)]


def draw_neck(cv, b, f, p):
    hx, hy, hrx, hry = b.head
    ny = hy + hry
    c, c2, k = p.c, p.c2, p.kind
    sh, li = shade_of(c), light_of(c)
    py = ny + 1
    if k == "chain":
        for i, q in enumerate(_arc(hx, ny)):
            cv.paint({q}, c if i % 2 else sh)
    elif k == "beads":
        for i, q in enumerate(_arc(hx, ny)):
            cv.paint({q}, li if i % 2 else c)
            cv.paint({(q[0], q[1] + 1)}, OUTLINE if i % 2 == 0 else sh)
    elif k == "choker":
        arc = _arc(hx, ny - 1, 7)
        cv.paint(set(arc) | {(x, y + 1) for x, y in arc}, c)
        cv.paint({(x, y + 2) for x, y in arc}, OUTLINE)
    elif k == "ribbon":
        cv.paint(set(_arc(hx, ny, 7)), c)
        cv.grid(hx - 9, ny - 1, ["aa.aa", "abbba", "aa.aa"], {"a": c, "b": sh}, outline=True)
    elif k == "collar":
        arc = _arc(hx, ny - 1, 7)
        cv.part(set(arc) | {(x, y + 1) for x, y in arc}, c, outline=OUTLINE)
        cv.paint({q for i, q in enumerate(arc) if i % 3 == 1}, (230, 230, 240))
        py = ny + 2
    elif k == "scarf":
        y = ny - 1
        cv.part(rect(hx - 7, y, hx + 6, y + 1), c)
        end = rect(hx + 3, y + 2, hx + 5, y + 8 + f % 2)
        cv.part(end, c)
        cv.paint({q for q in end | rect(hx - 7, y, hx + 6, y + 1) if q[0] % 3 == 0 or q[1] % 3 == 0}, c2)
        return
    elif k == "tie":
        tie = poly([(hx - 1, ny), (hx + 1, ny), (hx + 2.5, ny + 7), (hx, ny + 9.5), (hx - 2.5, ny + 7)])
        cv.part(tie, c, sh)
        cv.paint({q for q in tie if (q[0] + q[1]) % 3 == 0}, c2)
        return
    elif k == "bowtie":
        cv.grid(hx - 3, ny, ["aa.aa", "abcba", "aa.aa"], {"a": c, "b": c2, "c": sh}, outline=True)
        return
    elif k == "jabot":
        for i in range(3):
            cv.part(ellipse(hx, ny + 1 + i * 2, 3 - i * 0.5, 1.4), li if i % 2 else c, outline=OUTLINE)
        return
    elif k == "kerchief":
        tri = poly([(hx - 7, ny - 1), (hx + 7, ny - 1), (hx, ny + 6)])
        cv.part(tri, c, sh)
        cv.paint({q for q in tri if q[1] % 2 == 0 and (q[0] + q[1] // 2) % 3 == 0}, c2)
        return
    elif k == "boa":
        for i, (x, y) in enumerate(_arc(hx, ny, 8)[::2]):
            cv.part(ellipse(x, y + 0.5, 1.8, 1.6), c if i % 2 else li, outline=None)
        cv.paint({(hx + 9, ny + 3 + f % 2), (hx - 9, ny + 3 + (f + 1) % 2)}, c)
        return
    elif k == "medal":
        cv.paint(line(hx - 3, ny - 1, hx, ny + 3) | line(hx + 3, ny - 1, hx, ny + 3), c2)
        cv.part(ellipse(hx, ny + 5, 2, 2), c, sh, li)
        cv.paint({(hx, ny + 5)}, sh)
        return
    rows = PEND[[q[0] for q in PEND].index(p.pend)][3]
    if rows:
        cv.grid(hx - len(rows[0]) // 2, py, rows, {"a": c2, "b": BLACK if p.pend in ("skull", "eye") else shade_of(c2)},
                outline=True)


# --- held --------------------------------------------------------------------------------------

def draw_held(cv, b, f, p):
    x, y = b.hand
    c, c2, k = p.c, p.c2, p.kind
    sh, li = shade_of(c), light_of(c)
    wood = (130, 86, 48)
    if k == "sword":
        blade = line(x + 2, y, x + 7, y - 9) | line(x + 3, y, x + 8, y - 9)
        cv.part(blade, c, outline=OUTLINE)
        cv.paint(line(x + 3, y, x + 7, y - 8), li)
        cv.part(line(x, y - 1, x + 4, y + 1), c2)
        cv.paint({(x + 1, y + 2), (x + 1, y + 3)}, wood)
    elif k == "axe":
        cv.part(line(x + 1, y + 3, x + 5, y - 8), c2)
        cv.part(poly([(x + 4, y - 8), (x + 9, y - 10), (x + 9, y - 3), (x + 5, y - 4)]), c, sh, li)
    elif k == "hammer":
        cv.part(line(x + 1, y + 3, x + 4, y - 6), c2)
        cv.part(rect(x + 1, y - 9, x + 7, y - 6), c, sh, li)
    elif k == "spear":
        cv.part(line(x + 1, y + 6, x + 6, y - 10), c2)
        cv.part(poly([(x + 5, y - 9), (x + 8, y - 15), (x + 8, y - 9)]), c, sh)
    elif k == "staff":
        cv.part(line(x + 2, y + 6, x + 4, y - 9), c)
        cv.part(ellipse(x + 4.5, y - 11, 2.2, 2.2), c2, shade_of(c2), WHITE if f % 2 else light_of(c2))
    elif k == "wand":
        cv.part(line(x + 1, y + 1, x + 5, y - 5), c)
        cv.grid(x + 4, y - 9, [".a.", "aaa", ".a."], {"a": c2 if f % 2 else light_of(c2)}, outline=True)
    elif k == "shield":
        sh_px = poly([(x - 1, y - 6), (x + 7, y - 6), (x + 7, y), (x + 3, y + 4), (x - 1, y)])
        cv.part(sh_px, c, sh, li)
        em = p.var
        rows = {0: [".a.", "aaa", ".a."], 1: ["a.a.a", "a.a.a", "aaaaa", "..a.."], 2: ["aaaaa"],
                3: [".a.", "a.a", ".a."], 4: ["a.a", "aaa", ".a."]}[em]
        cv.grid(x + 3 - len(rows[0]) // 2, y - 4 + (1 if em == 2 else 0), rows, {"a": c2})
    elif k == "umbrella":
        cv.paint(line(x + 3, y - 6, x + 3, y + 3) | {(x + 2, y + 3)}, OUTLINE)
        can = {q for q in ellipse(x + 3, y - 6, 7, 4) if q[1] <= y - 6}
        cv.part(can, c, sh, li)
        if p.var == 1:
            cv.paint({q for q in can if (q[0] - x) % 4 < 2}, c2)
        elif p.var == 2:
            cv.paint({q for q in can if (q[0] + q[1]) % 3 == 0 and q[1] % 2 == 0}, c2)
        else:
            cv.paint({(x + 2, y + 3), (x + 2, y + 2)}, c2)
    elif k == "flag":
        cv.paint(line(x + 1, y + 4, x + 1, y - 12), wood)
        fl = rect(x + 2, y - 12 + f % 2, x + 9, y - 7 + f % 2)
        cv.part(fl, c)
        cv.paint({q for q in fl if (q[1] >= y - 9 + f % 2 if p.var == 0 else q[0] >= x + 6)}, c2)
    elif k == "lantern":
        cv.paint(line(x + 3, y - 6, x + 3, y - 4), OUTLINE)
        cv.part(rect(x + 1, y - 4, x + 5, y + 1), c)
        cv.paint(rect(x + 2, y - 3, x + 4, y), c2 if f % 2 else light_of(c2))
    elif k == "icecream":
        cv.part(poly([(x, y), (x + 5, y), (x + 2.5, y + 6)]), (220, 170, 90), (190, 140, 70))
        for i in range(p.var + 1):
            cv.part(ellipse(x + 2.5, y - 1 - i * 3, 2.8, 2), c2 if i % 2 else c, outline=OUTLINE)
    elif k == "lollipop":
        cv.paint(line(x + 2, y + 4, x + 3, y - 2), WHITE)
        cand = ellipse(x + 3, y - 5, 3, 3)
        cv.part(cand, c)
        cv.paint({q for q in cand if (math.atan2(q[1] - y + 5, q[0] - x - 3) * 2 + math.hypot(q[0] - x - 3, q[1] - y + 5)) % 3 < 1.2}, c2)
    elif k == "donut":
        ring = ellipse(x + 2.5, y, 3.5, 3) - ellipse(x + 2.5, y, 1, 1)
        cv.part(ring, (210, 160, 90))
        glaze = {q for q in ring if q[1] <= y + 1}
        cv.paint(glaze, c)
        cv.paint({q for q in glaze if (q[0] * 3 + q[1]) % 4 == 0}, c2)
    elif k == "cupcake":
        cv.part(poly([(x, y), (x + 6, y), (x + 5, y + 4), (x + 1, y + 4)]), c, sh)
        cv.part(ellipse(x + 3, y - 1, 3.5, 2.2), c2, outline=OUTLINE)
        cv.paint({(x + 3, y - 4), (x + 3, y - 3)}, (220, 30, 50))
    elif k == "drink":
        cv.paint(line(x + 4, y - 4, x + 6, y - 7), c2)
        cv.part(poly([(x, y - 3), (x + 6, y - 3), (x + 5, y + 4), (x + 1, y + 4)]), c, sh, li)
        cv.paint(rect(x + 1, y - 1, x + 5, y), WHITE)
    elif k == "balloon":
        cv.paint(line(x + 1, y + 1, x + 3, y - 10), c2)
        cv.part(ellipse(x + 3, y - 14 + f % 2, 3, 3.6), c, sh, li)
    elif k == "flower":
        cv.paint(line(x + 2, y + 3, x + 3, y - 4), (60, 150, 60))
        cv.grid(x + 1, y - 7, [".a.", "aba", ".a."], {"a": c, "b": c2}, outline=True)
    elif k == "teddy":
        cv.part(ellipse(x + 3, y + 1, 2.6, 2.6), c, sh)
        cv.part(ellipse(x + 3, y - 3, 2.4, 2.2) | ellipse(x + 1, y - 5, 1, 1) | ellipse(x + 5, y - 5, 1, 1), c, sh)
        cv.paint({(x + 2, y - 3), (x + 4, y - 3)}, BLACK)
        cv.paint({(x + 2, y - 1), (x + 4, y - 1), (x + 3, y - 1)}, c2)
    elif k == "fish":
        cv.part(ellipse(x + 3, y, 3.5, 2) | poly([(x + 6, y), (x + 9, y - 2), (x + 9, y + 2)]), c, sh, li)
        cv.paint({(x + 1, y - 1)}, BLACK)
        cv.paint({(x + 3, y - 2), (x + 4, y - 2), (x + 8, y), (x + 3, y + 2)}, c2)
    elif k == "guitar":
        cv.part(ellipse(x + 1, y + 3, 3, 2.5) | ellipse(x + 2, y, 2.2, 1.8), c, sh)
        cv.part(line(x + 2, y, x + 7, y - 8), c2)
        cv.paint({(x + 1, y + 3)}, BLACK)
    elif k == "torch":
        cv.part(line(x + 2, y + 4, x + 3, y - 3), c)
        fl = poly([(x + 1, y - 3), (x + 3 + f % 2, y - 9), (x + 5, y - 3)])
        cv.part(fl, c2, outline=None)
        cv.paint({(x + 3, y - 4), (x + 3, y - 5)}, YELLOW)


# --- aura ---------------------------------------------------------------------------------------
PARTS = {  # key: rows
    "stars": [".a.", "aba", ".a."], "hearts": ["a.a", "aaa", ".a."], "notes": [".aa", ".a.", "aa."],
    "bubbles": [".a.", "a.a", ".a."], "leaves": [".a", "ab"], "snow": ["a.a", ".a.", "a.a"], "sparks": ["a"],
    "skulls": ["aaa", "bab"], "gems": [".a.", "aba", ".a."], "fire": [".a.", "aba"], "butterflies": ["a.a", ".b.", "a.a"],
    "petals": ["aa", ".a"], "bolts": [".a", "a.", ".a"], "code": ["a.", "a.", "a."], "rings": ["aa", "aa"],
}
MOTION = [("orbit", "кружляють"), ("rise", "здіймаються"), ("fall", "падають"), ("twinkle", "мерехтять")]


def draw_aura(cv, b, f, p):
    hx, hy, _, _ = b.head
    rows = PARTS[p.kind]
    n = 4 if p.den == 0 else 7
    cols = {"a": p.c, "b": light_of(p.c) if p.kind != "skulls" else BLACK}
    if p.kind == "fire":
        cols["b"] = YELLOW
    for i in range(n):
        if p.mot == "orbit":
            a = i * 2 * math.pi / n + f * (math.pi / 2) / n * 2
            x, y = hx + 16 * math.cos(a), hy + 5 + 10 * math.sin(a)
        elif p.mot in ("rise", "fall"):
            col_x = [-17, 15, -13, 18, -20, 12, 20][i]
            t = (f * 4 + i * 7) % 16
            x, y = hx + col_x, (hy + 14 - t * 2) if p.mot == "rise" else (hy - 14 + t * 2)
        else:
            x, y = hx + [-16, 15, -13, 17, -18, 13, 19][i], hy + [-8, -4, 8, 10, 0, -12, 2][i]
            if (i + f) % 2:
                continue
        r = rows if p.kind != "code" else (["a.", "a.", "a."] if (i + f) % 2 else ["aaa", "a.a", "aaa"])
        cv.grid(int(x), int(y), r, cols)


# --- outfit ------------------------------------------------------------------------------------
TRIM = [("none", ""), ("collar", "з комірцем"), ("buttons", "з ґудзиками"), ("belt", "з поясом"),
        ("pocket", "з кишенею"), ("emblem", "з емблемою"), ("lampas", "з лампасами"), ("fringe", "з бахромою")]


def draw_outfit(cv, b, f, p):
    bx, by, brx, bry = b.body
    c, c2, k = p.c, p.c2, p.kind
    sh, li = shade_of(c), light_of(c)
    top = by - bry
    clip = {q for q in b.body_px if q[1] <= by + bry - 3}
    region = set(clip)
    extra_outline = set()
    if k == "tshirt":
        for s in (-1, 1):
            region |= ellipse(bx + s * (brx - 0.5), top + 4, 2.2, 2.2)
        extra_outline = region - set(b.body_px)
    elif k == "vest":
        region = {q for q in clip if abs(q[0] + 0.5 - bx) > 2.5}
    elif k == "overalls":
        region = {q for q in clip if q[1] >= by - 1} | {q for q in clip if abs(abs(q[0] + 0.5 - bx) - 3.5) < 1}
    elif k == "dress":
        skirt = poly([(bx - brx + 1, by), (bx + brx - 1, by), (bx + brx + 2, by + bry - 1), (bx - brx - 2, by + bry - 1)])
        region = clip | skirt
        extra_outline = skirt - set(b.body_px)
    elif k == "poncho":
        region = poly([(bx - brx - 2, by + 3), (bx - 3, top + 1), (bx + 3, top + 1), (bx + brx + 2, by + 3)])
        extra_outline = region - set(b.body_px)
    elif k == "toga":
        region = {q for q in clip if (q[0] - bx) < (q[1] - top) * 0.9 - 1}
    if extra_outline:
        cv.paint(dilate(region) - region, OUTLINE)
    cv.part(region, c, sh, outline=None)
    _apply_pat(cv, region, p.pat, c2, [by + 1, by + 2])
    if k == "sweater":
        cv.paint({q for q in region if q[1] >= by + bry - 4}, sh)
        cv.paint({q for q in region if q[1] <= top + 1}, sh)
    elif k == "shirt":
        cv.paint(poly([(bx - 4, top), (bx, top + 3), (bx - 1, top + 4), (bx - 4, top + 2)])
                 | poly([(bx + 4, top), (bx, top + 3), (bx + 1, top + 4), (bx + 4, top + 2)]), li)
        cv.paint({(bx, y) for y in range(top + 4, by + bry - 3, 2)} & region, sh)
    elif k == "kimono":
        cv.paint(line(bx - 4, top + 1, bx + 2, by + 1) & region, sh)
        cv.paint(rect(bx - brx, by + 1, bx + brx, by + 2) & region, mix(c, OUTLINE, 0.5))
    elif k == "jacket":
        cv.paint({q for q in region if abs(q[0] + 0.5 - bx) <= (q[1] - top) / 2 and q[1] < by + 2}, WHITE)
        cv.paint(line(bx, top + 3, bx, by + 2) & region, OUTLINE)
    elif k == "chainmail":
        cv.paint({q for q in region if (q[0] + q[1]) % 2 == 0}, sh)
    elif k == "hoodie":
        for s in (-1, 1):
            cv.paint(line(bx + s * 2, top + 1, bx + s * 2, top + 4) & region, li)
        cv.paint(rect(bx - 3, by + 2, bx + 2, by + 4) & region, sh)
        cv.part(ellipse(bx, top + 0.5, 6, 2) - ellipse(bx, top - 0.5, 4, 1.5), sh, outline=None)
    elif k == "raincoat":
        cv.paint({q for q in region if q[0] == int(bx - brx / 2)}, li)
        cv.paint({(bx + 1, y) for y in range(top + 3, by + bry - 3, 3)} & region, OUTLINE)
    elif k == "poncho":
        cv.paint({q for q in region if q[1] == by + 2 and q[0] % 2}, sh)
    t = p.trim
    if t == "collar":
        cv.part(poly([(bx - 4, top), (bx, top + 3), (bx + 4, top)]) & (region | dilate(region)), WHITE, outline=None)
    elif t == "buttons":
        cv.paint({(bx, y) for y in range(top + 3, by + bry - 3, 3)} & region, GOLD)
    elif t == "belt":
        cv.paint(rect(bx - brx, by + 2, bx + brx, by + 2) & region, (60, 40, 30))
        cv.paint({(bx, by + 2), (bx - 1, by + 2)} & region, GOLD)
    elif t == "pocket":
        cv.part(rect(bx - brx + 3, by + 1, bx - brx + 5, by + 3) & region, sh)
    elif t == "emblem":
        cv.grid(bx + brx // 2 - 1, by - 3, [".a.", "aaa", ".a."], {"a": GOLD})
    elif t == "lampas":
        for s in (-1, 1):
            cv.paint({q for q in region if abs(q[0] + 0.5 - bx - s * (brx - 2.5)) < 0.6}, WHITE)
    elif t == "fringe":
        bot = max(q[1] for q in region)
        cv.paint({(x, bot + 1) for x, y in region if y == bot and x % 2 == 0}, sh)


# --- back ---------------------------------------------------------------------------------------

def draw_back(cv, b, f, p):
    hx, hy, hrx, hry = b.head
    bx, by, brx, bry = b.body
    c, c2, k = p.c, p.c2, p.kind
    sh, li = shade_of(c), light_of(c)
    flap = f % 2
    if k == "cape":
        cv.part(poly([(bx - brx + 1, hy + hry - 1), (bx + brx - 1, hy + hry - 1), (bx + brx + 3 + flap, by + bry),
                      (bx - brx - 3 - flap, by + bry)]), c, sh)
        for s in (-1, 1):
            cv.paint(line(bx + s * (brx - 1), hy + hry, bx + s * (brx + 3 + flap), by + bry - 1), c2)
    elif k in ("butterfly", "fairy"):
        for s in (-1, 1):
            up = ellipse(bx + s * (brx + 4), by - 7 - flap, 5.5, 4.5)
            lo = ellipse(bx + s * (brx + 3), by + 1, 3.5, 3)
            if k == "fairy":
                cv.paint(dilate(up | lo) - (up | lo), mix(c, OUTLINE, 0.3))
                for q in up | lo:
                    under = cv.get(*q)
                    cv.paint({q}, mix(under, li, 0.55) if under else li)
                cv.paint({(bx + s * (brx + 4), by - 8 - flap), (bx + s * (brx + 6), by - 6 - flap)}, c2)
            else:
                cv.part(up | lo, c, sh)
                cv.paint(ellipse(bx + s * (brx + 5), by - 8 - flap, 1.6, 1.6) | ellipse(bx + s * (brx + 3), by + 1, 1, 1), c2)
    elif k == "dragon":
        for s in (-1, 1):
            w = poly([(bx + s * brx * 0.4, by - 4), (bx + s * (brx + 9), by - 12 - flap), (bx + s * (brx + 8), by - 3),
                      (bx + s * (brx + 5), by - 1), (bx + s * (brx + 2), by + 1)])
            cv.part(w, c2, shade_of(c2))
            cv.paint(line(bx + s * brx * 0.4, by - 4, bx + s * (brx + 9), by - 12 - flap)
                     | line(bx + s * (brx + 9), by - 12 - flap, bx + s * (brx + 5), by - 1), c)
    elif k == "feather":
        for s in (-1, 1):
            w = ellipse(bx + s * (brx + 3), by - 5 - flap, 5, 3.5) | ellipse(bx + s * (brx + 1), by - 2, 4, 3)
            cv.part(w, c, sh, li)
            cv.paint({q for q in w if abs(q[0] - bx) >= brx + 6 or q[1] <= by - 8 - flap}, c2)
    elif k == "mech":
        for s in (-1, 1):
            for i in range(3):
                cv.part(rect(min(bx + s * (brx - 1), bx + s * (brx + 6 - i)), by - 8 + i * 3 - flap * (2 - i),
                             max(bx + s * (brx - 1), bx + s * (brx + 6 - i)), by - 7 + i * 3 - flap * (2 - i)), c, sh)
            cv.paint({(bx + s * (brx + 1), by - 4)}, c2 if f % 2 else light_of(c2))
    elif k == "backpack":
        cv.part(rect(bx - brx - 3, by - 6, bx - brx + 3, by + 3), c, sh)
        cv.part(rect(bx - brx - 2, by - 1, bx - brx + 1, by + 2), c2)
    elif k == "shell":
        sh_px = ellipse(bx, by - 1, brx + 2, bry + 1)
        cv.part(sh_px, c, sh)
        cv.paint({q for q in sh_px if (q[0] // 3 + q[1] // 3) % 2 == 0 and abs(q[0] - bx) > brx - 2}, c2)
    elif k == "jetpack":
        for s in (-1, 1):
            x = bx + s * (brx - 1)
            cv.part(rect(x - 2, by - 7, x + 1, by + 1), c, sh, li)
            cv.paint({(x - 1, by + 2), (x, by + 2), (x - 1 + f % 2, by + 3)}, c2)
    elif k == "quiver":
        x = bx - brx
        cv.part(poly([(x - 3, by + 2), (x + 3, by - 9), (x + 6, by - 7), (x, by + 4)]), c, sh)
        for i in range(3):
            cv.paint({(x + 3 + i, by - 10 - i % 2), (x + 4 + i, by - 11 - i % 2)}, c2)
    elif k == "flag":
        x = bx - brx - 1
        cv.paint(line(x, by + 2, x, hy - hry - 8), (120, 80, 40))
        fl = rect(x - 8, hy - hry - 8 + flap, x - 1, hy - hry - 3 + flap)
        cv.part(fl, c)
        cv.paint({q for q in fl if q[1] >= hy - hry - 5 + flap}, c2)


# --- foreground --------------------------------------------------------------------------------

def draw_fg(cv, b, f, p):
    c, c2, k = p.c, p.c2, p.kind
    W = H = N
    if k == "confetti":
        for i in range(16):
            x, y = (i * 13 + f * (1 + i % 3)) % W, (i * 7 + f * 4) % H
            cv.paint({(x, y), (x + (i % 2), y + 1 - i % 2)}, c if i % 2 else c2)
    elif k == "frame":
        cv.paint(rect(0, 0, W - 1, 1) | rect(0, H - 2, W - 1, H - 1) | rect(0, 0, 1, H - 1) | rect(W - 2, 0, W - 1, H - 1), c)
        cv.paint(rect(2, 2, W - 3, 2) | rect(2, H - 3, W - 3, H - 3) | rect(2, 2, 2, H - 3) | rect(W - 3, 2, W - 3, H - 3),
                 shade_of(c))
        for x, y in ((0, 0), (W - 4, 0), (0, H - 4), (W - 4, H - 4)):
            cv.paint(rect(x, y, x + 3, y + 3), c2)
    elif k == "bubbles":
        for i in range(6):
            x, y = (i * 17 + 5) % W, (H - (f * 3 + i * 9) % (H + 6))
            cv.paint(ellipse(x, y, 1.6, 1.6) - ellipse(x, y, 0.8, 0.8), c)
            cv.paint({(x - 1, y - 1)}, WHITE)
    elif k == "petals":
        for i in range(9):
            x, y = (i * 11 + f * 2) % W, (i * 13 + f * 3) % H
            cv.paint({(x, y), (x + 1, y)}, c if i % 2 else light_of(c))
    elif k == "rays":
        for x in range(W):
            for y in range(H):
                under = cv.get(x, y)
                if under and (x + y + f) % 9 < 2 and x + y < 40:
                    cv.paint({(x, y)}, mix(under, c, 0.35))
    elif k == "vignette":
        for q in rect(0, 0, W - 1, H - 1):
            d = max(abs(q[0] - 23.5), abs(q[1] - 23.5))
            if d > 19:
                cv.paint({q}, c if d > 22 else mix(c, WHITE, 0.3) if (q[0] + q[1]) % 2 else c)
    elif k == "heartrain":
        for i in range(7):
            x, y = (i * 13 + 2) % W, (i * 11 + f * 4) % H
            cv.grid(x, y, ["a.a", "aaa", ".a."], {"a": c})
    elif k == "starfall":
        for i in range(4):
            x, y = (i * 15 + f * 4) % W, (i * 9 + f * 3) % 30
            cv.paint(line(x, y, x - 3, y - 3), mix(c, WHITE, 0.4))
            cv.paint({(x, y), (x + 1, y), (x, y + 1)}, c)


# --- registry ----------------------------------------------------------------------------------


@dataclass
class Kind:
    key: str
    noun: str
    g: str           # m f n p
    emoji: str
    axes: tuple      # axis names
    detail: str = ""  # held/back: instrumental noun for c2 (gender in detail_g)
    detail_g: str = "m"
    var: tuple = ()  # kind-specific variant names


H = ("c", "c2", "pat", "orn")
GEN: dict[str, tuple] = {
    "head": (draw_hat, [
        Kind("tophat", "циліндр", "m", "🎩", H), Kind("bowler", "котелок", "m", "🎩", H),
        Kind("beret", "берет", "m", "🎨", H), Kind("beanie", "шапка", "f", "🧶", H),
        Kind("cone", "ковпак", "m", "🥳", H), Kind("crown", "корона", "f", "👑", ("c", "c2", "orn")),
        Kind("witch", "капелюх відьми", "m", "🧙", H), Kind("cap", "кепка", "f", "🧢", H),
        Kind("tiara", "діадема", "f", "👸", ("c", "c2")), Kind("panama", "панама", "f", "👒", H),
        Kind("fez", "феска", "f", "🎩", H), Kind("sombrero", "сомбреро", "n", "🪅", H),
        Kind("ushanka", "вушанка", "f", "🧢", H), Kind("viking", "шолом вікінга", "m", "⛑", H),
        Kind("bandana", "бандана", "f", "🏴", H), Kind("cowboy", "ковбойський капелюх", "m", "🤠", H),
        Kind("grad", "академічна шапочка", "f", "🎓", ("c", "c2", "orn")),
    ]),
    "face": (draw_glasses, [
        Kind(k, n, g, e, ("c", "lens")) for k, n, g, e in (
            ("round", "круглі окуляри", "p", "👓"), ("square", "квадратні окуляри", "p", "👓"),
            ("aviator", "окуляри-авіатори", "p", "🕶"), ("cateye", "окуляри «лисички»", "p", "🕶"),
            ("heart", "окуляри-сердечка", "p", "😍"), ("star", "окуляри-зірочки", "p", "🤩"),
            ("hex", "шестикутні окуляри", "p", "👓"), ("visor", "кібер-візор", "m", "🥽"),
            ("goggles", "гоглі", "p", "🥽"), ("mask", "маскарадна маска", "f", "🎭"),
            ("pincenez", "пенсне", "n", "🧐"), ("monocle", "монокль", "m", "🧐"))]),
    "neck": (draw_neck, [
        Kind("chain", "ланцюжок", "m", "⛓", ("c", "c2", "pend")), Kind("beads", "намисто", "n", "📿", ("c", "c2", "pend")),
        Kind("choker", "чокер", "m", "🖤", ("c", "c2", "pend")), Kind("ribbon", "стрічка", "f", "🎀", ("c", "c2", "pend")),
        Kind("collar", "нашийник", "m", "🔔", ("c", "c2", "pend")),
        Kind("scarf", "шарф", "m", "🧣", ("c", "c2"), "смужками", "p"), Kind("tie", "краватка", "f", "👔", ("c", "c2"), "смужками", "p"),
        Kind("bowtie", "метелик", "m", "🎀", ("c", "c2"), "вузликом", "m"), Kind("jabot", "жабо", "n", "🤵", ("c",)),
        Kind("kerchief", "хустка", "f", "🧣", ("c", "c2"), "цятками", "p"), Kind("boa", "боа", "n", "🪶", ("c",)),
        Kind("medal", "медаль", "f", "🏅", ("c", "c2"), "стрічкою", "f"),
    ]),
    "held": (draw_held, [
        Kind("sword", "меч", "m", "🗡", ("c", "c2"), "ефесом", "m"), Kind("axe", "сокира", "f", "🪓", ("c", "c2"), "руків'ям", "n"),
        Kind("hammer", "молот", "m", "🔨", ("c", "c2"), "руків'ям", "n"), Kind("spear", "спис", "m", "🔱", ("c", "c2"), "древком", "n"),
        Kind("staff", "посох", "m", "🪄", ("c", "c2"), "кристалом", "m"), Kind("wand", "паличка", "f", "🪄", ("c", "c2"), "зіркою", "f"),
        Kind("shield", "щит", "m", "🛡", ("c", "c2", "var"), "", "m",
             (("зіркою", "f"), ("тризубом", "m"), ("смугою", "f"), ("колом", "n"), ("сердечком", "n"))),
        Kind("umbrella", "парасолька", "f", "☂️", ("c", "c2", "var"), "", "m",
             (("ручкою", "f"), ("смужками", "p"), ("цятками", "p"))),
        Kind("flag", "прапорець", "m", "🚩", ("c", "c2", "var"), "", "m", (("смугою", "f"), ("половиною", "f"))),
        Kind("lantern", "ліхтар", "m", "🏮", ("c", "c2"), "вогником", "m"),
        Kind("icecream", "морозиво", "n", "🍦", ("c", "c2", "var"), "кулькою", "f", ("", "подвійне", "потрійне")),
        Kind("lollipop", "льодяник", "m", "🍭", ("c", "c2"), "спіраллю", "f"),
        Kind("donut", "пончик", "m", "🍩", ("c", "c2"), "посипкою", "f"), Kind("cupcake", "кекс", "m", "🧁", ("c", "c2"), "кремом", "m"),
        Kind("drink", "стаканчик", "m", "🥤", ("c", "c2"), "трубочкою", "f"), Kind("balloon", "кулька", "f", "🎈", ("c", "c2"), "ниткою", "f"),
        Kind("flower", "квітка", "f", "🌷", ("c", "c2"), "серединкою", "f"), Kind("teddy", "ведмедик", "m", "🧸", ("c", "c2"), "бантиком", "m"),
        Kind("fish", "рибка", "f", "🐟", ("c", "c2"), "плавцями", "p"), Kind("guitar", "гітара", "f", "🎸", ("c", "c2"), "грифом", "m"),
        Kind("torch", "смолоскип", "m", "🔥", ("c", "c2"), "полум'ям", "n"),
    ]),
    "aura": (draw_aura, [
        Kind(k, n, "p", e, ("c", "mot", "den")) for k, n, e in (
            ("stars", "зірочки", "✨"), ("hearts", "сердечка", "💕"), ("notes", "ноти", "🎵"), ("bubbles", "бульбашки", "🫧"),
            ("leaves", "листочки", "🍃"), ("snow", "сніжинки", "❄️"), ("sparks", "іскри", "💥"), ("skulls", "черепки", "💀"),
            ("gems", "кристали", "💎"), ("fire", "вогники", "🔥"), ("butterflies", "метелики", "🦋"), ("petals", "пелюстки", "🌸"),
            ("bolts", "блискавки", "⚡"), ("code", "нулі й одиниці", "💾"), ("rings", "конфеті", "🎊"))]),
    "outfit": (draw_outfit, [
        Kind(k, n, g, e, ("c", "c2", "pat", "trim")) for k, n, g, e in (
            ("tshirt", "футболка", "f", "👕"), ("sweater", "светр", "m", "🧶"), ("shirt", "сорочка", "f", "👔"),
            ("kimono", "кімоно", "n", "🥋"), ("vest", "жилет", "m", "🦺"), ("jacket", "піджак", "m", "🧥"),
            ("overalls", "комбінезон", "m", "👖"), ("dress", "сукня", "f", "👗"), ("poncho", "пончо", "n", "🪅"),
            ("toga", "тога", "f", "🏛"), ("chainmail", "кольчуга", "f", "⚔️"), ("hoodie", "худі", "n", "🧥"),
            ("raincoat", "дощовик", "m", "🧥"))]),
    "back": (draw_back, [
        Kind("cape", "плащ", "m", "🦸", ("c", "c2"), "підкладкою", "f"),
        Kind("butterfly", "крила метелика", "p", "🦋", ("c", "c2"), "плямками", "p"),
        Kind("dragon", "крила дракона", "p", "🐉", ("c", "c2"), "перетинками", "p"),
        Kind("fairy", "крила феї", "p", "🧚", ("c", "c2"), "блискітками", "p"),
        Kind("feather", "пір'яні крила", "p", "🪽", ("c", "c2"), "кінчиками", "p"),
        Kind("mech", "механічні крила", "p", "🤖", ("c", "c2"), "світлом", "n"),
        Kind("backpack", "рюкзак", "m", "🎒", ("c", "c2"), "кишенею", "f"),
        Kind("shell", "панцир", "m", "🐢", ("c", "c2"), "візерунком", "m"),
        Kind("jetpack", "реактивний ранець", "m", "🚀", ("c", "c2"), "полум'ям", "n"),
        Kind("quiver", "сагайдак", "m", "🏹", ("c", "c2"), "стрілами", "p"),
        Kind("flag", "прапор за спиною", "m", "🚩", ("c", "c2"), "смугою", "f"),
    ]),
    "fg": (draw_fg, [
        Kind("confetti", "конфеті", "p", "🎊", ("c", "c2"), "блискітками", "p"),
        Kind("frame", "рамка", "f", "🖼", ("c", "c2"), "кутиками", "p"),
        Kind("bubbles", "бульбашки", "p", "🫧", ("c",)), Kind("petals", "пелюстки", "p", "🌸", ("c",)),
        Kind("rays", "промені", "p", "🌅", ("c",)), Kind("vignette", "віньєтка", "f", "🌑", ("c",)),
        Kind("heartrain", "дощ із сердечок", "m", "💘", ("c",)), Kind("starfall", "зорепад", "m", "🌠", ("c",)),
    ]),
}
GEN_SLOTS = list(GEN)
_USERS = ("pat", "orn", "pend")  # axes that make c2 visible (if a kind has any of them)


def _axis_size(kind: Kind, a: str) -> int:
    return {"c": len(GCOL), "c2": len(GCOL), "pat": len(PAT), "orn": len(ORN), "lens": len(LENS), "pend": len(PEND),
            "trim": len(TRIM), "mot": len(MOTION), "den": 2, "var": len(kind.var)}[a]


def _kind_size(kind: Kind) -> int:
    return math.prod(_axis_size(kind, a) for a in kind.axes)


def gen_count(slot: str | None = None, distinct: bool = True) -> int:
    """Number of generated items in a slot (all slots if None). distinct=True skips ids whose c2 is invisible."""
    if slot is None:
        return sum(gen_count(s, distinct) for s in GEN)
    total = 0
    for k in GEN[slot][1]:
        size = _kind_size(k)
        users = [] if k.key == "crown" else [a for a in k.axes if a in _USERS]
        if distinct and users and "c2" in k.axes:
            no_c2 = size // len(GCOL)
            zero = no_c2 // math.prod(_axis_size(k, a) for a in users)
            size = (no_c2 - zero) * len(GCOL) + zero
        total += size
    return total


def _b36(n: int) -> str:
    s = ""
    while True:
        n, r = divmod(n, 36)
        s = "0123456789abcdefghijklmnopqrstuvwxyz"[r] + s
        if not n:
            return s


@lru_cache(maxsize=4096)
def decode(slot: str, code: str) -> tuple[Kind, dict] | None:
    if slot not in GEN:
        return None
    try:
        n = int(code, 36) % gen_count(slot, distinct=False)
    except ValueError:
        return None
    for k in GEN[slot][1]:
        size = _kind_size(k)
        if n < size:
            vals = {}
            for a in k.axes:
                n, vals[a] = divmod(n, _axis_size(k, a))
            return k, vals
        n -= size
    return None


def _params(k: Kind, v: dict) -> SimpleNamespace:
    return SimpleNamespace(
        kind=k.key, c=GCOL[v.get("c", 0)][2], c2=GCOL[v.get("c2", 0)][2], pat=PAT[v.get("pat", 0)][0],
        orn=ORN[v.get("orn", 0)][0], lens=v.get("lens", 0), pend=PEND[v.get("pend", 0)][0],
        trim=TRIM[v.get("trim", 0)][0], mot=MOTION[v.get("mot", 0)][0], den=v.get("den", 0), var=v.get("var", 0))


def gen_name(slot: str, k: Kind, v: dict) -> str:
    c, c2 = v.get("c", 0), v.get("c2", 0)
    g = k.g
    first = cadj(c, g)
    if slot == "held" and k.key == "icecream" and v["var"]:
        first += " " + k.var[v["var"]]
    parts = [k.emoji, first[:1].upper() + first[1:], k.noun]
    if slot == "face":
        lens = adj(LENS[v["lens"]], "ip" if k.key not in ("monocle", "visor") else "im")
        parts.append(z(lens + (" скельцем" if k.key == "monocle" else " склом" if k.key == "visor" else
                               " блискітками" if k.key == "mask" else " скельцями")))
    elif slot == "aura":
        parts = [k.emoji, ("Рій: " if v["den"] else "") + first[:1].upper() + first[1:], k.noun, MOTION[v["mot"]][1]]
    else:
        pat, orn, pend, trim = v.get("pat", 0), v.get("orn", 0), v.get("pend", 0), v.get("trim", 0)
        if pat:
            parts.append(PAT[pat][1](c2))
        if orn:
            _, noun, og, _ = ORN[orn]
            parts.append(z(noun) if pat else z(cadj(c2, INS[og]) + " " + noun))
        if pend:
            _, noun, pg, _ = PEND[pend]
            parts.append(z(cadj(c2, INS[pg]) + " " + noun))
        if trim:
            parts.append(TRIM[trim][1])
        if "var" in k.axes and k.key != "icecream":
            noun, dg = k.var[v["var"]]
            parts.append(z(cadj(c2, INS[dg]) + " " + noun))
        elif k.detail and "c2" in k.axes:
            parts.append(z(cadj(c2, INS[k.detail_g]) + " " + k.detail))
        elif k.key in ("tiara", "crown") and not orn:
            parts.append(z(cadj(c2, "ip") + " каменями"))
    return " ".join(parts)


@lru_cache(maxsize=4096)
def gen_item(item: str):
    """'gen:<slot>:<code>' -> (name, slot, draw_fn) or None."""
    try:
        _, slot, code = item.split(":")
    except ValueError:
        return None
    d = decode(slot, code)
    if not d:
        return None
    k, v = d
    p = _params(k, v)
    fn = GEN[slot][0]
    return gen_name(slot, k, v), slot, (lambda cv, b, f: fn(cv, b, f, p))


def random_item(slot: str | None, rng: random.Random) -> str:
    """Random generated item id for a slot (any generated slot if None)."""
    slot = slot if slot in GEN else rng.choice(GEN_SLOTS)
    return f"gen:{slot}:{_b36(rng.randrange(gen_count(slot, distinct=False)))}"
