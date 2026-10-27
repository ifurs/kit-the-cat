"""Backgrounds + procedural variants.

Background id format: ``base`` or ``base~mod~mod…`` (e.g. ``meadow~night``, ``kyiv~rain``,
``farm~winter~snow``). Mods are applied in order season → time → weather, unknown mods are ignored,
unknown base falls back to meadow. Rendered pixels are cached per (id, frame, width).
"""
import colorsys
import math
import random
import zlib
from collections.abc import Callable
from functools import lru_cache

from .sprites_core import (BLACK, GOLD, GOLD_D, OUTLINE, RED, WHITE, YELLOW, Canvas, dilate, ellipse,
                                        hsv, line, mix, poly, rect)


def _sky(cv: Canvas, top: tuple, bottom: tuple, ground: tuple, ground2: tuple, horizon: int = 40) -> None:
    for y in range(cv.h):
        c = mix(top, bottom, y / horizon) if y < horizon else (ground if (y - horizon) % 3 else ground2)
        cv.px.update({(x, y): c for x in range(cv.w)})


def _clouds(cv: Canvas, f: int) -> None:
    for x0 in range(4, cv.w, 28):
        x = x0 + (f // 2) % 2
        cv.paint(ellipse(x + 4, 7, 4, 2) | ellipse(x + 7, 6, 3, 2.5), WHITE)


def _stars(cv: Canvas, f: int, rng: random.Random, n: int = 14, maxy: int = 36) -> None:
    for i in range(n):
        x, y = rng.randrange(cv.w), rng.randrange(maxy)
        if (i + f) % 4:
            cv.paint({(x, y)}, (255, 250, 200))


def _wall(cv: Canvas, wall: tuple, wall2: tuple, floor: tuple, floor2: tuple, horizon: int = 38) -> None:
    for y in range(cv.h):
        for x in range(cv.w):
            if y < horizon:
                c = wall2 if (x // 3 + y // 6) % 5 == 0 else wall
            else:
                c = floor2 if (x // 6 + y) % 2 else floor
            cv.px[(x, y)] = c


def _tree(cv: Canvas, x: int, y: int, h: int, col=(40, 110, 60), snow: bool = False) -> None:
    """Fir tree, base at (x, y)."""
    cv.paint(rect(x, y - 1, x, y), (90, 60, 40))
    for i in range(3):
        w, yy = 4 - i, y - 2 - i * h // 3
        cv.part(poly([(x - w, yy), (x + 0.5, yy - h // 2 - 1), (x + w + 1, yy)]), col, mix(col, OUTLINE, 0.3))
        if snow:
            cv.paint({(x, yy - h // 2), (x - 1, yy - h // 2 + 1)}, WHITE)


def bg_meadow(cv, f, rng):
    _sky(cv, (150, 210, 255), (210, 240, 255), (120, 200, 100), (100, 180, 90))
    _clouds(cv, f)


def bg_toxic(cv, f, rng):
    _sky(cv, (30, 50, 30), (60, 90, 40), (90, 170, 40), (120, 200, 60))
    for i in range(6):
        x, y = (7 + i * 13) % (cv.w - 2), 44 - ((f * 2 + i * 5) % 9)
        cv.paint(ellipse(x, y, 1.5, 1.5), (160, 230, 90))
    for x in (6, cv.w - 8):
        cv.part(rect(x - 2, 34, x + 2, 40), (230, 200, 40), (190, 160, 20))
        cv.paint({(x, 36), (x - 1, 37), (x + 1, 37)}, BLACK)


def bg_casino(cv, f, rng):
    _sky(cv, (60, 10, 30), (110, 20, 50), (40, 120, 60), (30, 100, 50))
    for i in range(cv.w // 4):
        cv.paint({(2 + i * 4, 2)}, (255, 220, 80) if (i + f) % 3 == 0 else (140, 90, 40))
    for x in (6, cv.w - 8):
        cv.paint(ellipse(x, 44, 2.5, 1.5), GOLD)
        cv.paint({(x, 44)}, GOLD_D)
    cv.grid(3, 10, ["aaa", "aba", "aaa", "aaa"], {"a": WHITE, "b": RED}, outline=True)


def bg_cemetery(cv, f, rng):
    _sky(cv, (20, 14, 36), (54, 34, 70), (40, 44, 40), (34, 36, 34))
    cv.paint(ellipse(39, 7, 4, 4), (230, 226, 200))
    cv.paint(ellipse(41, 6, 3.5, 3.5), (22, 15, 38))
    for x in (5, cv.w - 5):
        cv.paint(rect(x - 2, 33, x + 2, 40) | ellipse(x, 33, 2.5, 2), (90, 90, 100))
        cv.paint(rect(x, 34, x, 37) | rect(x - 1, 35, x + 1, 35), (60, 60, 70))
    if f % 2:
        cv.paint({(12, 20), (13, 19), (14, 20)}, (200, 220, 255))


def bg_club(cv, f, rng):
    _sky(cv, (20, 16, 50), (40, 20, 70), (60, 40, 90), (80, 50, 110))
    colors = [(255, 80, 160), (80, 220, 255), (255, 230, 80), (140, 255, 120)]
    for i in range(10):
        x, y = (i * 17 + f * 3) % (cv.w - 2) + 1, (i * 11) % 30 + 2
        cv.paint({(x, y), (x + 1, y)}, colors[(i + f) % 4])
    cv.part(ellipse(24, 3, 3, 2.5), (200, 200, 220), (150, 150, 170))


def bg_field(cv, f, rng):
    _sky(cv, (40, 110, 210), (110, 180, 250), (250, 210, 40), (230, 180, 20), horizon=38)
    cv.paint(ellipse(8, 7, 3, 3), (255, 240, 150))
    for x in range(1, cv.w, 4):
        cv.paint({(x, 37), (x, 36 - (x + f) % 2)}, (240, 200, 40))


def bg_kitchen(cv, f, rng):
    for y in range(cv.h):
        for x in range(cv.w):
            cv.px[(x, y)] = (250, 240, 220) if ((x // 4) + (y // 4)) % 2 else (230, 210, 180)
    cv.paint(rect(0, 41, cv.w - 1, cv.h - 1), (150, 100, 70))
    cv.paint(rect(0, 41, cv.w - 1, 41), (120, 80, 56))
    cv.part(rect(37, 8, 44, 14), (200, 220, 240))  # window
    cv.paint(rect(40, 8, 40, 14) | rect(37, 11, 44, 11), OUTLINE)


def bg_love(cv, f, rng):
    _sky(cv, (255, 200, 220), (255, 230, 240), (250, 170, 200), (240, 150, 190))
    heart = [".a.a.", "aaaaa", "aaaaa", ".aaa.", "..a.."]
    for i, (x, y) in enumerate([(3, 4), (39, 8), (6, 26), (40, 28), (20, 1)]):
        cv.grid(x, y + (f + i) % 2, heart, {"a": (255, 110, 150)})


def bg_mystic(cv, f, rng):
    _sky(cv, (14, 10, 40), (50, 30, 90), (40, 26, 70), (56, 36, 90))
    _stars(cv, f, rng)
    cv.paint(ellipse(8, 8, 3.5, 3.5), (250, 240, 180))
    cv.paint(ellipse(10, 7, 3, 3), (24, 16, 54))


def bg_khrushchovka(cv, f, rng):
    _wall(cv, (200, 180, 140), (186, 164, 124), (150, 100, 60), (136, 90, 54))
    carpet = rect(4, 6, 20, 24)  # килим на стіні
    cv.part(carpet, (160, 40, 50))
    for x in range(5, 20, 3):
        for y in range(7, 24, 3):
            cv.paint({(x, y)}, (230, 190, 80) if (x + y) % 2 else (40, 60, 120))
    cv.part(rect(33, 6, 44, 18), (170, 210, 240))
    cv.paint(rect(38, 6, 38, 18) | rect(33, 12, 44, 12), (240, 240, 240))


def bg_office(cv, f, rng):
    _wall(cv, (210, 214, 220), (200, 204, 210), (120, 124, 136), (110, 114, 126))
    cv.part(rect(30, 6, 44, 16), (30, 40, 60))  # monitor-ish window with chart
    cv.paint(line(31, 14, 35, 11) | line(35, 11, 38, 13) | line(38, 13, 43, 7), (80, 220, 120) if f % 2 else RED)
    cv.part(ellipse(6, 33, 3, 3), (60, 160, 70))  # plant
    cv.part(rect(4, 35, 8, 40), (180, 100, 60))


def bg_farm(cv, f, rng):
    _sky(cv, (160, 210, 255), (220, 240, 250), (110, 170, 70), (100, 150, 60))
    cv.part(poly([(32, 22), (39, 15), (46, 22)]), (180, 50, 40))
    cv.part(rect(33, 22, 45, 38), (200, 70, 50))
    cv.part(rect(37, 30, 41, 38), (120, 70, 40))
    for x in range(0, 30, 3):
        cv.paint({(x, 38), (x, 39)}, (150, 110, 70))


def bg_space(cv, f, rng):
    for y in range(cv.h):
        cv.px.update({(x, y): (8, 6, 24) for x in range(cv.w)})
    _stars(cv, f, rng, 22, cv.h)
    cv.part(ellipse(40, 40, 10, 10), (60, 120, 220), (40, 90, 180))
    cv.paint(ellipse(37, 37, 3, 2) | ellipse(43, 42, 2, 2), (90, 180, 90))
    cv.part(ellipse(7, 7, 3, 3), (220, 220, 210), (180, 180, 170))


def bg_mountains(cv, f, rng):
    _sky(cv, (120, 180, 240), (200, 230, 250), (70, 140, 70), (60, 120, 60))
    cv.part(poly([(-4, 40), (12, 14), (28, 40)]), (90, 110, 120), (70, 90, 100))
    cv.part(poly([(20, 40), (36, 10), (52, 40)]), (100, 120, 130), (80, 100, 110))
    cv.paint(poly([(33, 15), (36, 10), (39, 15)]) | poly([(10, 18), (12, 14), (14, 18)]), WHITE)
    for x in (4, 44):
        cv.part(poly([(x - 3, 40), (x, 30), (x + 3, 40)]), (40, 110, 60))


def bg_sea(cv, f, rng):
    _sky(cv, (120, 200, 250), (200, 235, 255), (240, 220, 160), (230, 210, 150), horizon=40)
    for y in range(30, 40):
        cv.px.update({(x, y): (40, 120, 200) if (x + y + f) % 7 else (200, 230, 255) for x in range(cv.w)})
    cv.paint(ellipse(38, 8, 4, 4), (255, 230, 120))
    cv.paint(line(6, 26, 12, 26) | line(8, 22, 8, 26) | poly([(9, 21), (9, 26), (13, 25)]), WHITE)


def bg_prison(cv, f, rng):
    _wall(cv, (110, 110, 120), (100, 100, 110), (80, 80, 86), (74, 74, 80))
    cv.part(rect(34, 6, 42, 12), (40, 60, 90))
    cv.paint({(36, y) for y in range(6, 13)} | {(39, y) for y in range(6, 13)}, (60, 60, 64))
    cv.paint(line(4, 10, 4, 16) | line(6, 10, 6, 16) | line(8, 10, 8, 16) | line(10, 10, 10, 16) | line(2, 13, 12, 13),
             (200, 200, 210))  # tally marks


def bg_hospital(cv, f, rng):
    _wall(cv, (220, 240, 236), (210, 232, 228), (180, 200, 196), (170, 190, 186))
    cv.part(rect(36, 6, 44, 14), WHITE)
    cv.paint(rect(39, 7, 41, 13) | rect(37, 9, 43, 11), RED)
    cv.paint(line(2, 20, 8, 20) | line(8, 20, 10, 15) | line(10, 15, 12, 24) | line(12, 24, 14, 20) | line(14, 20, 20, 20),
             (60, 200, 90) if f % 2 else (30, 140, 60))


def bg_palace(cv, f, rng):
    _wall(cv, (120, 30, 50), (140, 40, 60), (230, 200, 120), (210, 180, 100))
    for x in (5, cv.w - 6):
        cv.part(rect(x - 2, 4, x + 2, 38), (240, 230, 210), (210, 200, 180))
    cv.part(ellipse(24, 4, 4, 2), GOLD, GOLD_D)
    for i in range(4):
        cv.paint({(16 + i * 5, 6 + (f + i) % 2)}, (255, 240, 160))


def bg_bunker(cv, f, rng):
    _wall(cv, (120, 118, 110), (110, 108, 100), (90, 88, 82), (84, 82, 76))
    cv.paint(line(0, 5, cv.w, 5), (60, 60, 60))
    cv.part(ellipse(24, 6, 2, 2), (255, 240, 180) if f % 2 else (180, 170, 120))  # flickering bulb
    cv.grid(36, 14, ["aaaaaa", "abbbba", "abbbba", "aaaaaa"], {"a": (80, 90, 60), "b": (100, 110, 70)}, outline=True)


def bg_kyiv(cv, f, rng):
    _sky(cv, (20, 24, 60), (70, 50, 110), (50, 50, 60), (44, 44, 54))
    _stars(cv, f, rng, 8, 16)
    sil = (30, 30, 46)
    for x0, w, h in ((0, 6, 14), (7, 5, 20), (13, 7, 10), (31, 6, 22), (38, 4, 12), (43, 5, 17)):
        cv.paint(rect(x0, 40 - h, x0 + w, 39), sil)
        for wy in range(40 - h + 2, 38, 3):
            if (wy + x0 + f) % 4 == 0:
                cv.paint({(x0 + 2, wy)}, (255, 220, 120))
    cv.paint(rect(22, 12, 23, 39) | poly([(18, 39), (22.5, 30), (27, 39)]), sil)  # Батьківщина-мати-ish
    cv.paint(line(23, 12, 26, 7), (200, 200, 220))


def bg_ruins(cv, f, rng):
    _sky(cv, (90, 80, 80), (150, 130, 120), (100, 90, 80), (90, 80, 70))
    for x0, h in ((2, 18), (12, 10), (34, 20), (42, 12)):
        cv.part(rect(x0, 40 - h, x0 + 5, 39), (130, 120, 115), (110, 100, 96))
        cv.paint({(x0 + 2, 40 - h + 4), (x0 + 3, 40 - h + 8)}, (60, 50, 50))
    for i in range(3):
        cv.paint(ellipse(10 + i * 14, 6 + (f + i) % 3, 2.5, 1.5), (120, 110, 110))


# --- new backgrounds -------------------------------------------------------------------------

def bg_chornobyl(cv, f, rng):  # ЧАЕС + колесо огляду Прип'яті
    _sky(cv, (150, 160, 120), (200, 200, 150), (110, 120, 70), (96, 106, 60))
    rust, conc = (150, 90, 60), (150, 150, 140)
    wheel = ellipse(10, 17, 8, 8) - ellipse(10, 17, 7, 7)
    cv.paint(wheel, rust)
    for a in range(6):
        cv.paint(line(10, 17, 10 + 7 * math.cos(a * 1.05), 17 + 7 * math.sin(a * 1.05)), mix(rust, OUTLINE, 0.3))
    cv.paint(line(10, 17, 6, 39) | line(10, 17, 14, 39), mix(rust, OUTLINE, 0.4))
    cv.part(rect(28, 22, 46, 39), conc, (120, 120, 112))  # саркофаг
    cv.part(poly([(28, 22), (33, 16), (46, 16), (46, 22)]), (170, 170, 160), (140, 140, 130))
    cv.part(rect(39, 6, 41, 16), (200, 200, 200), (160, 160, 160))  # труба
    cv.paint(rect(39, 8, 41, 8) | rect(39, 12, 41, 12), RED)
    cv.part(rect(31, 26, 35, 30), YELLOW)
    cv.paint({(33, 27), (32, 29), (34, 29), (33, 28)}, BLACK)
    for i in range(4):  # radioactive dust
        x, y = (i * 13 + f * 3) % cv.w, 30 + (i * 5 + f) % 9
        cv.paint({(x, y)}, (190, 240, 90))


def bg_metro(cv, f, rng):  # станція метро
    for y in range(cv.h):
        for x in range(cv.w):
            if y < 34:
                c = (225, 215, 190) if (x // 4 + y // 3) % 2 else (210, 200, 175)
            elif y < 36:
                c = (240, 200, 40) if x % 4 < 2 else (40, 40, 40)  # жовта лінія
            else:
                c = (120, 110, 110) if (x // 5 + y) % 2 else (110, 100, 100)
            cv.px[(x, y)] = c
    for x0 in (2, 30):  # arches
        arch = rect(x0, 10, x0 + 15, 33) | ellipse(x0 + 8, 10, 8, 6)
        cv.paint(arch, (70, 60, 80))
        cv.paint(dilate(arch), (180, 150, 90))
    cv.part(rect(17, 3, 30, 7), (40, 90, 200))
    cv.paint(rect(19, 5, 28, 5), WHITE)
    cv.grid(23, 4, ["aaa", "a.a"], {"a": RED})
    for i, x in enumerate(range(6, 44, 10)):
        cv.paint(ellipse(x, 1, 2, 1), (255, 240, 180) if (i + f) % 5 else (200, 190, 140))
    if f % 4 in (1, 2):  # поїзд проїжджає в арці
        cv.paint(rect(31, 16, 46, 32), (60, 120, 70))
        cv.paint(rect(33, 19, 44, 23), (200, 230, 240))


def bg_bukovel(cv, f, rng):  # гірськолижний схил
    _sky(cv, (90, 160, 240), (190, 220, 250), (240, 245, 255), (225, 232, 245), horizon=30)
    cv.paint(poly([(-2, 30), (14, 8), (30, 30)]), (230, 236, 248))
    cv.paint(poly([(18, 30), (36, 4), (52, 30)]), (215, 225, 245))
    cv.paint(poly([(34, 8), (36, 4), (38, 8)]) | poly([(12, 11), (14, 8), (16, 11)]), WHITE)
    for y in range(30, cv.h):  # slope
        for x in range(cv.w):
            if (x * 3 + y * 7) % 23 == 0:
                cv.px[(x, y)] = (200, 210, 230)
    cv.paint(line(0, 6, cv.w, 22), (60, 60, 70))  # канатна дорога
    for i, x in enumerate((10, 32)):
        xx = x + f % 2
        y = 6 + xx * 16 // cv.w
        cv.paint(line(xx, y, xx, y + 3), (60, 60, 70))
        cv.part(rect(xx - 2, y + 4, xx + 2, y + 5), (220, 60, 60) if i else (60, 120, 220))
    for x, y in ((3, 40), (44, 38), (40, 44)):
        _tree(cv, x, y, 9, (30, 100, 60), snow=True)


def bg_village(cv, f, rng):  # хата-мазанка, тин, соняшник
    _sky(cv, (130, 200, 250), (210, 240, 255), (110, 180, 80), (96, 166, 70))
    _clouds(cv, f)
    cv.part(rect(22, 22, 44, 38), (250, 248, 238), (226, 222, 210))  # білена стіна
    cv.paint(rect(22, 37, 44, 38), (90, 70, 120))  # призьба
    cv.part(poly([(19, 23), (33, 11), (47, 23)]), (200, 170, 90), (170, 140, 70))  # стріха
    cv.paint({(x, 21) for x in range(20, 47, 2)}, (150, 120, 60))
    cv.part(rect(26, 26, 31, 31), (120, 190, 230))  # вікно з лиштвою
    cv.paint(rect(28, 26, 28, 31) | rect(26, 28, 31, 28), (60, 90, 160))
    cv.paint(rect(25, 25, 32, 25) | rect(25, 32, 32, 32), (60, 90, 160))
    cv.part(rect(35, 27, 40, 38), (140, 90, 50))  # двері
    for x in range(0, 20, 3):  # тин
        cv.paint(line(x, 33, x, 40), (130, 90, 50))
    cv.paint(line(0, 35, 19, 35) | line(0, 38, 19, 38), (110, 76, 44))
    cv.paint(line(8, 40, 8, 22), (70, 130, 50))  # соняшник
    sway = f % 2
    cv.part(ellipse(8 + sway, 21, 3.5, 3.5), YELLOW, (230, 160, 30))
    cv.paint(ellipse(8 + sway, 21, 1.6, 1.6), (90, 60, 30))
    cv.grid(4, 6, [".a", "aa"], {"a": (230, 230, 230)})  # лелека далеко


def bg_atb(cv, f, rng):  # супермаркет-дискаунтер
    _wall(cv, (235, 235, 230), (225, 225, 220), (200, 200, 196), (190, 190, 186))
    cv.paint(rect(0, 2, cv.w - 1, 5), (30, 60, 160))
    cv.paint({(x, 3) for x in range(3, cv.w - 3, 5)} | {(x + 1, 4) for x in range(3, cv.w - 3, 5)}, (250, 210, 40))
    prods = [(220, 60, 50), (250, 200, 40), (60, 150, 70), (240, 240, 240), (120, 80, 50), (80, 140, 220)]
    for sx in (1, 33):
        cv.part(rect(sx, 8, sx + 13, 37), (170, 170, 180), (140, 140, 150))
        for k, sy in enumerate(range(10, 36, 7)):
            cv.paint(rect(sx + 1, sy + 5, sx + 12, sy + 5), (110, 110, 120))
            for i in range(4):
                c = prods[(sx + k * 3 + i) % len(prods)]
                cv.part(rect(sx + 1 + i * 3, sy + 1, sx + 2 + i * 3, sy + 4), c, outline=None)
            cv.paint({(sx + 2, sy + 6)}, YELLOW)  # цінник
    cv.part(rect(17, 30, 29, 33), (170, 170, 180))  # візок
    cv.paint({(19, 35), (27, 35)}, OUTLINE)
    cv.paint(rect(16 + f % 2, 28, 18, 29) & rect(15, 28, 18, 29), (255, 80, 80))  # «акція»


def bg_wedding(cv, f, rng):  # весільна зала
    _wall(cv, (250, 236, 240), (244, 226, 232), (200, 160, 120), (186, 146, 108))
    for x in range(0, cv.w, 4):  # гірлянда
        y = 3 + int(2 * math.sin(x / 5))
        cv.paint({(x, y)}, (255, 240, 160) if (x // 4 + f) % 2 else (255, 180, 210))
    arch = {p for p in ellipse(24, 24, 17, 18) - ellipse(24, 24, 14, 15) if p[1] < 39}
    cv.part(arch, (110, 170, 100), (80, 140, 80))
    for i, a in enumerate(range(0, 181, 15)):
        x, y = 24 + 15.5 * math.cos(math.radians(180 + a)), 24 + 16.5 * math.sin(math.radians(180 + a))
        cv.part(ellipse(x, y, 1.5, 1.5), ((255, 110, 150), WHITE, (255, 190, 210))[i % 3], outline=None)
    for x in (8, 39):
        cv.paint({(x, y) for y in range(26, 39, 3)}, (255, 110, 150))
    for x in (4, 43):  # столи з тортом/келихами
        cv.part(rect(x - 3, 33, x + 3, 37), WHITE, (220, 220, 230), outline=(190, 150, 160))
        cv.paint({(x - 1, 31), (x - 1, 32), (x + 1, 31), (x + 1, 32)}, (250, 220, 120))
    cv.part(rect(6, 26, 8, 30) | rect(5, 29, 9, 31), (255, 250, 240), (230, 220, 210))


def bg_court(cv, f, rng):  # зала суду
    _wall(cv, (150, 100, 60), (136, 90, 54), (120, 80, 50), (110, 72, 44))
    for x in range(2, cv.w, 8):
        cv.paint(rect(x, 0, x, 30), (120, 78, 44))
    cv.part(rect(10, 22, 38, 31), (110, 66, 36), (90, 52, 28))  # суддівський стіл
    cv.paint(rect(10, 22, 38, 22), (170, 120, 70))
    cv.part(ellipse(24, 9, 5, 5), (240, 220, 120), (200, 170, 70))  # герб-ish щит
    cv.paint(rect(24, 6, 24, 12) | rect(21, 8, 27, 8), (60, 90, 180))
    cv.paint(line(21, 8, 20, 11) | line(27, 8, 28, 11), (60, 90, 180))  # терези
    cv.paint({(19, 11), (20, 11), (21, 11), (27, 11), (28, 11), (29, 11)}, (60, 90, 180))
    cv.part(rect(30, 18 - f % 2, 33, 20 - f % 2), (140, 90, 50))  # молоток
    cv.paint(line(33, 19 - f % 2, 36, 21), (140, 90, 50))
    cv.part(rect(2, 14, 7, 20), WHITE)
    cv.paint(rect(3, 16, 6, 16) | rect(3, 18, 5, 18), (120, 120, 120))


def bg_school(cv, f, rng):  # клас з дошкою
    _wall(cv, (170, 210, 190), (160, 200, 180), (170, 120, 80), (156, 108, 70))
    cv.part(rect(6, 6, 41, 22), (40, 80, 60), (34, 70, 52))
    cv.paint(rect(5, 23, 42, 23), (140, 90, 50))
    cv.paint(line(9, 10, 13, 10) | line(15, 10, 16, 10) | line(18, 9, 18, 11) | line(17, 10, 19, 10)
             | line(21, 10, 23, 10) | line(26, 9, 27, 11), (230, 230, 230))  # 2+2=…
    cv.grid(29, 9, ["aa", ".a", "a.", "aa"] if f % 2 else ["a.", "a.", "a.", "aa"], {"a": (250, 240, 120)})
    cv.paint(line(9, 16, 22, 16) | line(9, 18, 18, 18), (200, 200, 200))
    cv.part(ellipse(44, 6, 2.5, 2.5), WHITE)  # годинник
    cv.paint({(44, 5), (44, 6), (45, 6)}, BLACK)


def bg_marshrutka(cv, f, rng):  # салон маршрутки
    _wall(cv, (200, 200, 190), (190, 190, 180), (90, 90, 96), (80, 80, 86))
    bump = f % 2
    for x0 in (2, 26):
        cv.part(rect(x0, 6 + bump, x0 + 19, 18 + bump), (150, 200, 230))
        cv.paint(rect(x0 + 1, 15 + bump, x0 + 18, 18 + bump), (110, 160, 90))  # пейзаж за вікном
        cv.paint({(x0 + 4 + (f * 5) % 14, 16 + bump), (x0 + 5 + (f * 5) % 14, 15 + bump)}, (60, 110, 60))
    cv.paint(line(0, 3, cv.w, 3), (170, 170, 170))  # поручень
    cv.paint(rect(10, 4, 10, 6) | rect(36, 4, 36, 6), (170, 170, 170))
    cv.part(rect(17, 21, 31, 27), (255, 255, 230))  # табличка з номером маршруту
    cv.grid(19, 22, ["aaa.aaa.aaa", "..a.a.a.a.a", "aaa.a.a.aaa", "a...a.a.a.a", "aaa.aaa.aaa"], {"a": (200, 30, 40)})
    for x0 in (0, 34):
        cv.part(rect(x0, 30, x0 + 13, 38), (150, 40, 50), (120, 30, 40))


def bg_dacha(cv, f, rng):  # дача з грядками
    _sky(cv, (140, 205, 250), (215, 240, 255), (110, 80, 50), (96, 70, 44), horizon=38)
    _clouds(cv, f)
    cv.part(rect(30, 18, 46, 37), (90, 150, 210), (70, 120, 180))  # будиночок
    cv.part(poly([(28, 19), (38, 11), (48, 19)]), (170, 60, 50))
    cv.part(rect(34, 24, 38, 28), (240, 230, 160))
    for x in range(0, 28, 4):  # грядки
        cv.paint({(x, 37), (x + 1, 36), (x + 2, 37)}, (70, 160, 60))
        if x % 8 == 0:
            cv.paint({(x + 1, 38)}, (240, 120, 40))
    cv.part(ellipse(8, 22, 6, 6), (60, 150, 60), (40, 120, 50))  # яблуня
    cv.paint(rect(8, 28, 9, 37), (110, 76, 44))
    cv.paint({(5, 20), (10, 24), (7, 25), (11, 19)}, RED)


BACKGROUNDS: dict[str, tuple[str, Callable]] = {
    "meadow": ("🌿 Галявина", bg_meadow), "khrushchovka": ("🏚 Хрущовка з килимом", bg_khrushchovka),
    "toxic": ("☢️ Токсичне болото", bg_toxic), "casino": ("🎰 Казино", bg_casino),
    "cemetery": ("🪦 Кладовище", bg_cemetery), "club": ("🪩 Нічний клуб", bg_club),
    "field": ("🌾 Пшеничне поле", bg_field), "kitchen": ("🍳 Кухня", bg_kitchen),
    "love": ("💗 Рожевий світ", bg_love), "mystic": ("🌙 Містична ніч", bg_mystic),
    "office": ("🏢 Офіс", bg_office), "farm": ("🚜 Ферма", bg_farm), "space": ("🚀 Космос", bg_space),
    "mountains": ("🏔 Карпати", bg_mountains), "sea": ("🌊 Одеське море", bg_sea),
    "prison": ("⛓ В'язниця", bg_prison), "hospital": ("🏥 Лікарня", bg_hospital),
    "palace": ("🏛 Палац (Межигір'я)", bg_palace), "bunker": ("🧱 Бункер", bg_bunker),
    "kyiv": ("🌃 Нічний Київ", bg_kyiv), "ruins": ("🏚 Руїни", bg_ruins),
    "chornobyl": ("☢️ Зона відчуження", bg_chornobyl), "metro": ("🚇 Станція метро", bg_metro),
    "bukovel": ("⛷ Буковель", bg_bukovel), "village": ("🌻 Село, хата-мазанка", bg_village),
    "atb": ("🛒 Дискаунтер «АТБ»", bg_atb), "wedding": ("💒 Весільна зала", bg_wedding),
    "court": ("⚖️ Зала суду", bg_court), "school": ("🏫 Шкільний клас", bg_school),
    "marshrutka": ("🚐 Маршрутка", bg_marshrutka), "dacha": ("🥒 Дача", bg_dacha),
}
OUTDOOR = {"meadow", "toxic", "cemetery", "field", "mystic", "farm", "mountains", "sea", "kyiv", "ruins", "chornobyl",
           "bukovel", "village", "dacha"}

# --- variants (mods) -------------------------------------------------------------------------


def _hsvp(c):
    return colorsys.rgb_to_hsv(c[0] / 255, c[1] / 255, c[2] / 255)


def _is_light(c) -> bool:  # windows, bulbs, stars keep glowing at night
    return c[0] > 200 and c[1] > 170 and c[2] < 190


def _is_green(c) -> bool:
    h, s, v = _hsvp(c)
    return 0.17 < h < 0.5 and s > 0.25 and v > 0.2


def _recolor(cv: Canvas, fn) -> None:
    cache: dict = {}
    px = cv.px
    for p, c in px.items():
        r = cache.get(c)
        if r is None:
            r = cache[c] = fn(c)
        px[p] = r


def _is_sky(c) -> bool:
    return c[2] > c[0] and c[2] >= c[1] and c[2] > 120


def m_night(cv, f, rng, sky):
    _recolor(cv, lambda c: c if _is_light(c) else (int(c[0] * 0.28 + 6), int(c[1] * 0.32 + 8), int(c[2] * 0.5 + 24)))
    if sky:
        for i in range(16):
            x, y = rng.randrange(cv.w), rng.randrange(26)
            if (x, y) in sky and (i + f) % 4:
                cv.px[(x, y)] = (255, 250, 210)
        spot = next((q for q in ((38, 7), (9, 7), (30, 5), (16, 4)) if q in sky and (q[0] - 3, q[1]) in sky), None)
        if spot:
            x, y = spot
            moon = ellipse(x, y, 3.5, 3.5) - ellipse(x + 2, y - 1, 3, 3)
            cv.paint(moon, (240, 236, 200))


def m_blackout(cv, f, rng, sky):
    _recolor(cv, lambda c: (int(c[0] * 0.18 + 4), int(c[1] * 0.2 + 4), int(c[2] * 0.3 + 12)))
    x, y = 6, 40  # свічка
    cv.paint(rect(x, y - 3, x + 1, y), (240, 236, 220))
    cv.paint({(x, y - 4 - f % 2), (x + 1, y - 4)}, (255, 200, 60))
    for p in ellipse(x + 0.5, y - 3, 7, 6):
        if p in cv.px:
            cv.px[p] = mix(cv.px[p], (255, 170, 60), 0.28)


def m_dusk(cv, f, rng, sky):
    _recolor(cv, lambda c: mix((int(c[0] * 0.95), int(c[1] * 0.7), int(c[2] * 0.66)), (255, 120, 90), 0.22))
    for p in sky:
        cv.px[p] = mix(cv.px[p], (250, 120, 130), max(0, 0.5 - p[1] / 60))


def m_dawn(cv, f, rng, sky):
    _recolor(cv, lambda c: mix(c, (255, 200, 210), 0.2))
    for p in sky:
        cv.px[p] = mix(cv.px[p], (255, 210, 170), p[1] / 50)


def _rain(cv, f, n, col):
    for i in range(n):
        x, y = (i * 11 + f * 2) % cv.w, (i * 7 + f * 6) % cv.h
        cv.paint({(x, y), (x - 1, y + 1), (x - 1, y + 2)}, col)


def m_rain(cv, f, rng, sky):
    _recolor(cv, lambda c: mix(c, (100, 110, 130), 0.3))
    _rain(cv, f, 22, (160, 190, 235))


def m_storm(cv, f, rng, sky):
    flash = f % 4 == 2
    _recolor(cv, lambda c: mix(c, (200, 200, 230) if flash else (40, 40, 60), 0.5))
    _rain(cv, f, 30, (170, 190, 240))
    if flash:
        cv.paint(line(30, 0, 27, 7) | line(27, 7, 31, 8) | line(31, 8, 26, 18), (255, 255, 200))


def m_snow(cv, f, rng, sky):
    _recolor(cv, lambda c: mix(c, (230, 236, 250), 0.12))
    for i in range(20):
        x, y = (i * 13 + (f + i) % 3) % cv.w, (i * 9 + f * 2) % cv.h
        cv.paint({(x, y)} if i % 3 else {(x, y), (x + 1, y), (x - 1, y), (x, y - 1), (x, y + 1)}, WHITE)


def m_fog(cv, f, rng, sky):
    for (x, y), c in cv.px.items():
        cv.px[(x, y)] = mix(c, (214, 218, 224), 0.2 + 0.4 * y / cv.h + 0.06 * math.sin(x / 5 + f))


def m_wind(cv, f, rng, sky):
    for i in range(9):
        x, y = (i * 17 + f * 7) % cv.w, (i * 11) % 40 + 2
        cv.paint({(x, y), (x + 1, y)}, ((120, 180, 70), (230, 150, 50), (200, 210, 220))[i % 3])
        cv.paint({(x + 3, y - 1), (x + 6, y - 1)}, (230, 236, 240))


def _season(cv, fn):
    _recolor(cv, lambda c: fn(c) if _is_green(c) else c)


def m_winter(cv, f, rng, sky):
    _season(cv, lambda c: mix((236, 242, 252), (180, 196, 222), 1 - _hsvp(c)[2]))
    _recolor(cv, lambda c: mix(c, (200, 220, 255), 0.12))


def m_autumn(cv, f, rng, sky):
    _season(cv, lambda c: hsv(0.06 + 0.05 * (c[0] % 3) / 2, 0.75, _hsvp(c)[2] * 0.95))
    for i in range(6):
        x, y = (i * 19 + f) % cv.w, (i * 13 + f * 3) % cv.h
        cv.paint({(x, y), (x + 1, y + 1)}, ((220, 120, 40), (190, 70, 40), (240, 190, 60))[i % 3])


def m_spring(cv, f, rng, sky):
    _season(cv, lambda c: hsv(0.28, 0.6, min(1, _hsvp(c)[2] * 1.1)))
    for (x, y), c in list(cv.px.items()):
        if _is_green(c) and (x * 7 + y * 13) % 29 == 0:
            cv.px[(x, y)] = (255, 190, 220) if (x + y) % 2 else WHITE
    for i in range(5):
        cv.paint({((i * 23 + f * 2) % cv.w, (i * 11 + f * 3) % 44)}, (255, 200, 225))


def m_summer(cv, f, rng, sky):
    def sat(c):
        h, s, v = _hsvp(c)
        return hsv(h, min(1, s * 1.2), min(1, v * 1.04))
    _recolor(cv, sat)


# mod id -> (ukr name, order, fn); order: 0 season, 1 time, 2 weather
BG_MODS: dict[str, tuple[str, int, Callable]] = {
    "spring": ("весна", 0, m_spring), "summer": ("літо", 0, m_summer), "autumn": ("осінь", 0, m_autumn),
    "winter": ("зима", 0, m_winter),
    "dawn": ("світанок", 1, m_dawn), "dusk": ("захід сонця", 1, m_dusk), "night": ("ніч", 1, m_night),
    "blackout": ("блекаут", 1, m_blackout),
    "rain": ("дощ", 2, m_rain), "storm": ("гроза", 2, m_storm), "snow": ("снігопад", 2, m_snow),
    "fog": ("туман", 2, m_fog), "wind": ("вітер", 2, m_wind),
}


def bg_parse(bg: str) -> tuple[str, list[str]]:
    base, *mods = (bg or "meadow").split("~")
    if base not in BACKGROUNDS:
        base = "meadow"
    mods = sorted(dict.fromkeys(m for m in mods if m in BG_MODS), key=lambda m: BG_MODS[m][1])
    return base, mods


def bg_name(bg: str) -> str:
    base, mods = bg_parse(bg)
    return " · ".join([BACKGROUNDS[base][0]] + [BG_MODS[m][0] for m in mods])


def random_background(rng: random.Random, mods: float = 0.5, outdoor_only: bool = False) -> str:
    """Random id; with probability `mods` adds a season/time/weather mod (one per group)."""
    pool = sorted(OUTDOOR) if outdoor_only else list(BACKGROUNDS)
    base, out = rng.choice(pool), []
    for order in (0, 1, 2):
        if rng.random() < mods * (0.6 if base in OUTDOOR else 0.25 if order == 1 else 0):
            out.append(rng.choice([m for m, (_, o, _) in BG_MODS.items() if o == order]))
    return "~".join([base] + out)


@lru_cache(maxsize=384)
def _bg_pixels(bg: str, f: int, w: int, h: int) -> dict:
    base, mods = bg_parse(bg)
    cv = Canvas(w, h)
    seed = zlib.crc32(base.encode())
    BACKGROUNDS[base][1](cv, f, random.Random(seed))
    if mods:
        sky = {p for p, c in cv.px.items() if p[1] < 36 and _is_sky(c)} if base in OUTDOOR else set()
        for m in mods:
            BG_MODS[m][2](cv, f, random.Random(seed + 7), sky)
    return cv.px


def paint_bg(cv: Canvas, bg: str, f: int) -> None:
    cv.px.update(_bg_pixels(bg, f, cv.w, cv.h))

