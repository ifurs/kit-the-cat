"""Procedural pixel-art sprites for pets.

Each pet is drawn on a 48x48 grid (scaled ×8 with nearest-neighbour, like a real tamagotchi screen)
as a stack of layers, back to front:

    background → shadow → role back (cape/wings) → back items → tail → back ears → feet/body → outfit
    → head → species face → pattern → role head overlay → eyes/mouth (mood, role) → neck → face items
    → head items → held item → aura → role aura → [composite: glow/ghost/quantum glitch] → fg

The pet is painted on its own transparent 48x48 layer and then composited onto the background, so
it can be mirrored (groups), glow (angel), be translucent (ghost) or glitch (quantum).

Ids used by the engine:
  * items: fixed ids from ITEMS (``cowboy``), tinted ``cowboy@6`` (TINTS index), and generated
    ``gen:<slot>:<base36>`` (see sprites_gen; ``random_item(slot, rng)``), also tintable ``gen:head:1z4k@3``.
  * backgrounds: ``base`` or ``base~mod~mod`` — mods: spring summer autumn winter | dawn dusk night
    blackout | rain storm snow fog wind (e.g. ``meadow~night``, ``kyiv~rain``, ``farm~winter~snow``).
  * roles (Look.role): vampire werewolf zombie demon angel cyborg alien quantum; combine with "+",
    e.g. ``vampire+cyborg``.

Hybrids: ears, face, tail and body can come from different species, so a child of a pig and a cat
may have a pig body, cat ears and a dog tail. Palette and pattern are seeded per pet. Every part is
painted "outline first, then fill", which gives the classic pixel-art look.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # Pillow is optional at runtime (extra `images`)
    from PIL import Image

import colorsys
import io
import math
import random
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, replace


from .sprites_bg import (BACKGROUNDS, BG_MODS, OUTDOOR, bg_name, bg_parse, paint_bg,  # noqa: F401
                                      random_background)
from .sprites_core import _pil  # noqa: F401
from .sprites_core import (BLACK, BLUE, BLUSH, GOLD, GOLD_D, N, OUTLINE, RED, SCALE, WHITE,  # noqa: F401
                                        YELLOW, Body, Canvas, Px, _eye_xy, _held, _top, dilate, ellipse, hsv,
                                        light_of, line, lum, mix, poly, rect, shade_of)
from .sprites_gen import GEN, GEN_SLOTS, gen_count, gen_item, random_item  # noqa: F401

# --- genome ----------------------------------------------------------------------------------
# A pet's look is a Genome. Natural genes come from the species; each gene can mutate into a
# foreign/rare value. Breeding mixes parents gene-by-gene. Colours are continuous (HSV + jitter),
# so even "the same" combination of discrete genes rarely produces the same pet twice.

SPECIES = ["pig", "cat", "dog", "fox", "horse", "axolotl"]
GHOST = ("привид", (220, 232, 255), (176, 192, 230), (245, 250, 255), (190, 205, 240))

# natural base colours (h, s, v) per species
NATURAL = {
    "pig": [(0.97, 0.31, 1.0), (0.0, 0.12, 0.29), (0.05, 0.16, 0.98), (0.06, 0.6, 0.92), (0.95, 0.23, 1.0),
            (0.08, 0.35, 0.75), (0.02, 0.45, 0.6)],
    "cat": [(0.08, 0.71, 0.96), (0.69, 0.26, 0.27), (0.64, 0.11, 0.7), (0.1, 0.02, 0.97), (0.1, 0.29, 0.94),
            (0.07, 0.45, 0.55), (0.6, 0.15, 0.5), (0.05, 0.35, 0.8)],
    "dog": [(0.07, 0.58, 0.71), (0.1, 0.53, 0.93), (0.95, 0.09, 0.26), (0.1, 0.05, 0.96), (0.0, 0.0, 0.6),
            (0.06, 0.6, 0.45), (0.09, 0.3, 0.85), (0.04, 0.5, 0.35)],
    "fox": [(0.07, 0.8, 0.95), (0.03, 0.75, 0.85), (0.6, 0.03, 0.98), (0.7, 0.1, 0.45), (0.1, 0.35, 0.95),
            (0.05, 0.6, 0.6)],
    "horse": [(0.05, 0.6, 0.6), (0.04, 0.55, 0.4), (0.7, 0.1, 0.18), (0.1, 0.03, 0.97), (0.0, 0.0, 0.65),
              (0.11, 0.45, 0.95), (0.07, 0.3, 0.75)],
    "axolotl": [(0.95, 0.25, 1.0), (0.25, 0.3, 0.4), (0.12, 0.5, 1.0), (0.7, 0.15, 0.2), (0.55, 0.35, 0.85),
                (0.78, 0.2, 0.85), (0.97, 0.15, 0.95)],
}
# gene -> {value: (ukr name, natural species or None for mutation-only)}
GENES = {
    "ears": {
        "cat_pointy": ("гострі котячі", "cat"), "cat_big": ("великі котячі", "cat"),
        "cat_lynx": ("рисячі з китичками", "cat"), "cat_fold": ("висловухі", "cat"),
        "dog_floppy": ("звислі", "dog"), "dog_pointy": ("хаскі", "dog"), "dog_round": ("ведмежі", "dog"),
        "dog_long": ("бассет-вуха", "dog"), "pig_floppy": ("свинячі звислі", "pig"), "pig_up": ("свинячі стирчаки", "pig"),
        "fox_ears": ("лисячі", "fox"), "fennec": ("фенек-локатори", "fox"), "horse_ears": ("конячі з гривою", "horse"),
        "unicorn_mane": ("грива з чубом", "horse"), "gills": ("зябра", "axolotl"), "gills_big": ("пишні зябра", "axolotl"),
        "bunny": ("заячі", None), "devil": ("кажанячі", None),
    },
    "tail": {
        "cat_long": ("довгий", "cat"), "cat_fluffy": ("пухнастий", "cat"), "bobtail": ("куций", "cat"),
        "dog_wag": ("виляючий", "dog"), "dog_curl": ("бублик", "dog"), "pig_curl": ("закрутка", "pig"),
        "pig_straight": ("пряма мотузочка", "pig"), "fox": ("лисячий", "fox"), "horse_tail": ("кінський", "horse"),
        "axo_fin": ("плавник", "axolotl"), "devil_tail": ("чортячий", None),
    },
    "face": {
        "cat": ("котячий носик", "cat"), "dog": ("собачий ніс", "dog"), "dog_muzzle": ("світла морда", "dog"),
        "pig": ("п'ятачок", "pig"), "pig_big": ("великий п'ятак", "pig"), "fox_snout": ("лисяча мордочка", "fox"),
        "horse_muzzle": ("кінська морда", "horse"), "axo_smile": ("усмішка аксолотля", "axolotl"),
        "heart_nose": ("ніс-сердечко", None),
    },
    "head": {"round": ("кругла", 0), "wide": ("широка", 0), "tall": ("видовжена", 0), "small": ("маленька", 0),
             "big": ("велика", 0)},
    "body": {"round": ("кругле", 0), "chubby": ("пухке", 0), "slim": ("худорляве", 0), "tall": ("витягнуте", 0)},
    "eyes": {
        "dot": ("намистинки", 0), "big": ("аніме", 0), "slit": ("котячі зіниці", 0), "sleepy": ("сонні", 0),
        "button": ("ґудзики", 0), "hetero": ("різнокольорові", None), "cyclops": ("циклоп", None),
        "three": ("третє око", None), "star": ("зірочки", None),
    },
    "pattern": {
        "none": ("без візерунка", 0), "spots": ("плями", 0), "patch": ("пляма на оці", 0), "tabby": ("смугастий", 0),
        "tuxedo": ("смокінг", 0), "calico": ("трикольоровий", 0), "socks": ("шкарпетки", 0), "mask": ("маска єнота", 0),
        "gradient": ("темна спинка", 0), "saddle": ("сідло", 0), "dalmatian": ("далматинець", 0),
        "tiger": ("тигрові смуги", 0), "leopard": ("леопардові розетки", 0), "points": ("сіамський окрас", 0),
        "pinto": ("пінто", 0),
    },
    "mark": {"none": ("без мітки", 0), "star": ("зірка на лобі", 0), "heart": ("сердечко", 0), "moon": ("місяць", 0),
             "diamond": ("ромбик", 0), "lightning": ("блискавка", None), "trident": ("тризуб", None),
             "sun": ("сонечко", 0), "drop": ("крапля", 0), "flame": ("вогник", None), "spiral": ("спіраль", None)},
    "extra": {"none": ("—", 0), "freckles": ("веснянки", 0), "tongue": ("висолоплений язик", 0), "mohawk": ("ірокез", 0),
              "curl": ("чубчик", 0), "fangs": ("ікла", None), "antennae": ("вусики-антени", None),
              "unicorn": ("ріг єдинорога", None), "whiskers": ("довгі вуса", 0),
              "fluff": ("пухнастий комір", 0), "beard": ("борідка", 0), "brows": ("густі брови", 0),
              "horns": ("ріжки", None), "wings": ("крильця", None)},
    "color": {"natural": ("природний", 0), "neon": ("неоновий", None), "albino": ("альбінос", None),
              "melanistic": ("меланіст", None), "shiny": ("золотий", None), "rainbow": ("райдужний", None),
              "galaxy": ("галактичний", None), "pastel": ("пастельний", None), "zombie": ("зомбі", None),
              "frost": ("крижаний", None), "sunset": ("захід сонця", None)},
}
# natural pattern colours: black, white, dark brown, ginger, grey, cream
SECOND = [(0.0, 0.0, 0.12), (0.0, 0.0, 0.98), (0.07, 0.55, 0.3), (0.07, 0.75, 0.9), (0.0, 0.0, 0.5), (0.1, 0.25, 0.95)]
IRIS = [(80, 200, 90), (70, 140, 240), (240, 170, 40), (140, 90, 50), (170, 90, 230), (230, 50, 60), (60, 220, 220)]
VISIBLE = ["ears", "tail", "face", "head", "body", "eyes", "pattern", "mark", "extra", "color"]


@dataclass
class Genome:
    species: str = "cat"
    ears: str = "cat_pointy"
    tail: str = "cat_long"
    face: str = "cat"
    head: str = "round"
    body: str = "round"
    eyes: str = "dot"
    pattern: str = "none"
    mark: str = "none"
    extra: str = "none"
    color: str = "natural"
    hue: float = 0.08
    sat: float = 0.7
    val: float = 0.95
    hue2: float = 0.0       # pattern colour
    sat2: float = 0.0
    val2: float = 0.2
    iris: int = 0
    iris2: int = 1
    seed: int = 0           # pattern placement

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Genome":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def _natural(gene: str, species: str) -> list[str]:
    vals = GENES[gene]
    own = [k for k, (_, sp) in vals.items() if sp == species]
    common = [k for k, (_, sp) in vals.items() if sp == 0]
    return own or common


def _mutant(gene: str) -> list[str]:
    """Rare or foreign values; genes without rare values mutate into any value."""
    return [k for k, (_, sp) in GENES[gene].items() if sp != 0] or list(GENES[gene])


def _pick(gene: str, species: str, rng: random.Random, mut: float) -> str:
    if rng.random() < mut:
        return rng.choice(_mutant(gene) if gene not in ("head", "body") else list(GENES[gene]))
    nat = _natural(gene, species)
    if gene in ("pattern", "mark", "extra") and rng.random() < 0.35:
        return "none"
    return rng.choice(nat)


def random_genome(species: str, rng: random.Random, mut: float = 0.07) -> Genome:
    h, s, v = rng.choice(NATURAL[species])
    color = rng.choice(_mutant("color")) if rng.random() < mut else "natural"
    g = Genome(
        species=species, color=color,
        hue=(h + rng.uniform(-0.03, 0.03)) % 1, sat=min(1, max(0, s + rng.uniform(-0.1, 0.1))),
        val=min(1, max(0.15, v + rng.uniform(-0.1, 0.08))),
        **dict(zip(("hue2", "sat2", "val2"), rng.choice(SECOND) if color == "natural"
                   else (rng.random(), rng.uniform(0.3, 0.8), rng.uniform(0.4, 1.0)))),
        iris=rng.randrange(len(IRIS)), iris2=rng.randrange(len(IRIS)), seed=rng.randrange(1 << 30),
    )
    for gene in ("ears", "tail", "face", "head", "body", "eyes", "pattern", "mark", "extra"):
        setattr(g, gene, _pick(gene, species, rng, mut))
    return g


def breed(a: Genome, b: Genome, rng: random.Random, mut: float = 0.1) -> Genome:
    """Child: each gene from a random parent, colours blended with jitter, extra chance to mutate."""
    species = rng.choice([a.species, b.species])
    child = random_genome(species, rng, mut)
    for gene in ("ears", "tail", "face", "head", "body", "eyes", "pattern", "mark", "extra", "color"):
        if rng.random() > mut:
            setattr(child, gene, getattr(rng.choice((a, b)), gene))
    t = rng.random()
    dh = ((b.hue - a.hue + 0.5) % 1) - 0.5
    child.hue = (a.hue + dh * t + rng.uniform(-0.02, 0.02)) % 1
    child.sat = min(1, max(0, a.sat + (b.sat - a.sat) * t + rng.uniform(-0.05, 0.05)))
    child.val = min(1, max(0.15, a.val + (b.val - a.val) * t + rng.uniform(-0.05, 0.05)))
    p2 = rng.choice((a, b))
    child.hue2, child.sat2, child.val2 = p2.hue2, p2.sat2, p2.val2
    return child


def distance(a: Genome, b: Genome) -> float:
    d = sum(getattr(a, g) != getattr(b, g) for g in VISIBLE) + (a.species != b.species)
    dh = min(abs(a.hue - b.hue), 1 - abs(a.hue - b.hue))
    d += min(2.0, dh * 10 + abs(a.val - b.val) * 4 + abs(a.sat - b.sat) * 2)
    return d


def visible_key(g: Genome) -> tuple:
    """Discrete look of a pet; two pets in a chat never share it (see unique_genome)."""
    return (g.species,) + tuple(getattr(g, x) for x in VISIBLE)


def unique_genome(species: str, others: list[Genome], rng: random.Random, min_dist: float = 4.0,
                  parents: tuple[Genome, Genome] | None = None) -> Genome:
    """Reroll until the pet differs enough from every pet already in the chat.

    Never returns a pet whose discrete look (visible_key) duplicates another one in `others`.
    """
    taken = {visible_key(o) for o in others}
    best, best_d = None, -1.0
    for attempt in range(200):
        mut = 0.07 + attempt * 0.005  # get weirder if the chat is crowded
        g = breed(*parents, rng, 0.1 + attempt * 0.005) if parents else random_genome(species, rng, mut)
        d = min((distance(g, o) for o in others), default=99.0)
        if d >= min_dist and visible_key(g) not in taken:
            return g
        if d > best_d and visible_key(g) not in taken:
            best, best_d = g, d
    g = best or random_genome(species, rng, 0.5)
    while visible_key(g) in taken:  # extremely crowded: force a random gene to change
        gene = rng.choice(VISIBLE)
        setattr(g, gene, rng.choice(list(GENES[gene])))
    return g


def rarity(g: Genome) -> tuple[int, str]:
    score = 0
    for gene in ("ears", "tail", "face", "eyes", "mark", "extra", "color"):
        sp = GENES[gene][getattr(g, gene)][1]
        if sp is None:
            score += 3 if gene == "color" else 2
        elif sp not in (0, g.species):
            score += 1  # foreign part = hybrid
    if g.color in ("rainbow", "galaxy", "shiny"):
        score += 2
    tier = ("⚪ Звичайний" if score < 2 else "🟢 Незвичайний" if score < 4 else "🔵 Рідкісний" if score < 6
            else "🟣 Епічний" if score < 9 else "🟠 Легендарний")
    return score, tier


def describe(g: Genome) -> list[str]:
    return [f"{gene}: {GENES[gene][getattr(g, gene)][0]}" for gene in VISIBLE]


def dna_code(g: Genome) -> str:
    """Short human-readable code, e.g. CAT-7F3A-…"""
    parts = [g.species[:1].upper()] + [f"{list(GENES[x]).index(getattr(g, x)):X}" for x in VISIBLE]
    return "".join(parts) + f"-{int(g.hue * 255):02X}{int(g.val * 255):02X}{g.seed % 4096:03X}"


# --- roles -----------------------------------------------------------------------------------
ROLES = {"vampire": "🧛 Вампір", "werewolf": "🐺 Перевертень", "zombie": "🧟 Зомбі", "demon": "😈 Демон",
         "angel": "😇 Ангел", "cyborg": "🤖 Кіборг", "alien": "👽 Прибулець", "quantum": "⚛️ Квантовий"}
ROLE_EYE = {"vampire": (235, 30, 50), "werewolf": (255, 205, 40), "demon": (255, 130, 20), "zombie": (205, 215, 150)}


def _grey(c: tuple) -> tuple:
    v = int(lum(c))
    return v, v, v


ROLE_TINT: dict[str, Callable] = {
    "vampire": lambda c: mix(_grey(c), (228, 226, 244), 0.5),
    "werewolf": lambda c: mix((int(c[0] * 0.72), int(c[1] * 0.68), int(c[2] * 0.66)), (80, 60, 50), 0.22),
    "zombie": lambda c: mix(c, (120, 160, 104), 0.6),
    "demon": lambda c: mix(c, (205, 40, 40), 0.52),
    "angel": lambda c: mix(c, (255, 252, 242), 0.5),
    "alien": lambda c: mix(c, (90, 212, 172), 0.58),
}


def roles_of(lk) -> set[str]:
    r = {x for x in (lk.role or "").split("+") if x in ROLES}
    if lk.quantum:
        r.add("quantum")
    return r


def role_name(role: str) -> str:
    return " + ".join(ROLES.get(r, r) for r in role.split("+") if r)


def palette(g: Genome, role: str = "") -> tuple:
    """-> base, shade, light, accent, second, iris_l, iris_r"""
    h, s, v = g.hue, g.sat, g.val
    c = g.color
    if c == "neon":
        s, v = 1.0, 1.0
    elif c == "albino":
        h, s, v = 0.0, 0.03, 1.0
    elif c == "melanistic":
        s, v = s * 0.4, 0.22
    elif c == "shiny":
        h, s, v = 0.13, 0.75, 1.0
    elif c == "pastel":
        s, v = s * 0.35 + 0.1, 1.0
    elif c == "zombie":
        h, s, v = 0.28, 0.35, 0.62
    elif c == "galaxy":
        h, s, v = 0.72, 0.6, 0.3
    elif c == "frost":
        h, s, v = 0.55, 0.25, 1.0
    elif c == "sunset":
        h, s, v = 0.04, 0.7, 1.0
    base = hsv(h, s, v)
    shade = hsv(h, s * 1.1 + 0.05, v * 0.76)
    light = hsv(h, s * 0.6, min(1, v * 1.12 + 0.06))
    if g.species == "dog":
        accent = hsv(h, min(1, s + 0.1), v * 0.6)
    elif g.species == "fox":
        accent = (250, 244, 236)
    elif g.species == "horse":
        accent = hsv(h, min(1, s + 0.15), v * 0.45)
    elif g.species == "axolotl":
        accent = hsv(0.97, 0.65, 0.95) if v > 0.5 else hsv(0.9, 0.45, 0.55)
    elif v < 0.35:
        accent = (255, 150, 170)
    else:
        accent = hsv(0.96, 0.42, 1.0) if v > 0.5 else (200, 120, 140)
    second = hsv(g.hue2, g.sat2, g.val2)
    il, ir = IRIS[g.iris], IRIS[g.iris2 if g.eyes == "hetero" else g.iris]
    if c == "albino":
        il = ir = (230, 60, 80)
    for r in (role or "").split("+"):
        if r in ROLE_TINT:
            base, shade, light, accent, second = (ROLE_TINT[r](x) for x in (base, shade, light, accent, second))
        if r in ROLE_EYE:
            il = ir = ROLE_EYE[r]
    return base, shade, light, accent, second, il, ir


# stage geometry: head (cx, cy, rx, ry), body (cx, cy, rx, ry), eye dx
GEOM = {
    1: dict(head=(24, 23, 11, 10), body=(24, 35, 8, 6), ex=4),
    2: dict(head=(24, 20, 10, 9), body=(24, 33, 10, 8), ex=4),
    3: dict(head=(24, 17, 10, 9), body=(24, 31, 12, 10), ex=4),
    4: dict(head=(24, 18, 10, 9), body=(24, 32, 12, 9), ex=4),  # elder: a bit hunched
}
HEAD_SHAPE = {"round": (0, 0), "wide": (2, -1), "tall": (-1, 1), "small": (-1, -1), "big": (1, 1)}
BODY_SHAPE = {"round": (0, 0), "chubby": (3, 1), "slim": (-3, 0), "tall": (-1, 2)}


@dataclass
class Look:
    """Everything needed to draw one pet at one moment."""
    genes: Genome = field(default_factory=Genome)
    stage: int = 1                  # 0 egg, 1 baby, 2 teen, 3 adult, 4 elder
    mood: str = "ok"                # happy | ok | sad | sick | sleep | dead | angry
    items: list[str] = field(default_factory=list)   # equipped item ids, optional "@variant"
    background: str = "meadow"      # "base" or "base~mod~mod" (see module docstring)
    fat: float = 0.0                # 0..1
    dirty: bool = False
    hungry: bool = False
    ghost: bool = False
    egg_cracks: int = 0
    quantum: bool = False           # Schrödinger: flickers between alive and ghost
    role: str = ""                  # supernatural role overlay: vampire, werewolf, zombie, demon, angel, cyborg, alien, quantum


def _geom(lk: Look, f: int) -> tuple[tuple, tuple, int]:
    g = lk.genes
    st = GEOM[lk.stage]
    bob = (1 if f % 2 else 0) - (3 if lk.ghost else 0)
    hx, hy, hrx, hry = st["head"]
    bx, by, brx, bry = st["body"]
    dhx, dhy = HEAD_SHAPE.get(g.head, (0, 0))
    dbx, dby = BODY_SHAPE.get(g.body, (0, 0))
    hrx, hry = hrx + dhx, hry + dhy
    brx, bry = brx + dbx + round(lk.fat * 4), bry + dby + round(lk.fat * 1.5)
    hy, by = hy + bob, by + bob + (dby if g.body == "tall" else 0)
    if g.body == "tall":
        hy += 1
    return (hx, hy, hrx, hry), (bx, by, brx, bry), st["ex"]


# --- creature ------------------------------------------------------------------------------

BACK_EARS = {"cat_pointy", "cat_big", "cat_lynx", "pig_floppy", "pig_up", "dog_pointy", "dog_round", "bunny", "devil",
             "fox_ears", "fennec", "horse_ears", "unicorn_mane", "gills", "gills_big"}


def _ears(cv: Canvas, style: str, hx, hy, hrx, hry, base, shade, accent, f):
    top = hy - hry
    for s in (-1, 1):
        if style in ("cat_pointy", "cat_big", "cat_lynx"):
            k = 1.35 if style == "cat_big" else 1.0
            tip = (hx + s * 8 * k, top - 4 * k)
            cv.part(poly([(hx + s * 9.5, hy - 2), tip, (hx + s * 2, top + 1)]), base, shade)
            cv.paint(poly([(hx + s * 8, hy - 3), (hx + s * 7.6 * k, top - 1.5 * k), (hx + s * 4, top + 1.5)]), accent)
            if style == "cat_lynx":
                cv.paint(line(tip[0], tip[1], tip[0] + s, tip[1] - 3), OUTLINE)
        elif style == "dog_pointy":
            cv.part(poly([(hx + s * 9, hy - 1), (hx + s * 7, top - 6), (hx + s * 2, top + 1)]), base, shade)
            cv.paint(poly([(hx + s * 7, hy - 2), (hx + s * 6.5, top - 3), (hx + s * 3.5, top + 1.5)]), mix(base, WHITE, 0.5))
        elif style == "pig_floppy":
            cv.part(poly([(hx + s * 2.5, top + 1.5), (hx + s * 10.5, top - 1.5), (hx + s * 9.5, top + 5.5)]), base, shade)
            cv.paint(poly([(hx + s * 4.5, top + 1.8), (hx + s * 9, top - 0.2), (hx + s * 8.5, top + 3.5)]), accent)
        elif style == "pig_up":
            cv.part(ellipse(hx + s * 6, top, 2.5, 3.5), base, shade)
            cv.paint(ellipse(hx + s * 6, top + 0.5, 1.2, 2), accent)
        elif style == "dog_round":
            cv.part(ellipse(hx + s * 7.5, top + 1, 3.2, 3.2), base, shade)
            cv.paint(ellipse(hx + s * 7.5, top + 1.5, 1.6, 1.6), accent)
        elif style == "bunny":
            sway = (f % 2) * s
            cv.part(ellipse(hx + s * 4 + sway, top - 6, 2.5, 7), base, shade)
            cv.paint(ellipse(hx + s * 4 + sway, top - 6, 1, 5), accent)
        elif style in ("fox_ears", "fennec"):
            k = 1.5 if style == "fennec" else 1.15
            tip = (hx + s * 8.5 * (1.1 if style == "fennec" else 1), top - 5 * k)
            cv.part(poly([(hx + s * 9.5, hy - 1), tip, (hx + s * 2, top + 1)]), base, shade)
            cv.paint(poly([(hx + s * 8, hy - 2.5), (tip[0] - s * 0.8, tip[1] + 3), (hx + s * 4, top + 1.5)]), accent)
            cv.paint(poly([(tip[0] - s * 2, tip[1] + 2.5), tip, (tip[0] + s * 0.5, tip[1] + 3)]) | {(int(tip[0]), int(tip[1]))},
                     OUTLINE if style == "fox_ears" else shade)
        elif style in ("horse_ears", "unicorn_mane"):
            cv.part(poly([(hx + s * 2.5, top + 2), (hx + s * 5.5, top - 5), (hx + s * 7.5, top + 2)]), base, shade)
            cv.paint(poly([(hx + s * 4, top + 1.5), (hx + s * 5.5, top - 2.5), (hx + s * 6.5, top + 1.5)]), accent)
        elif style in ("gills", "gills_big"):
            n = 4 if style == "gills_big" else 3
            for i in range(n):
                ang = -0.9 + i * (1.6 / (n - 1))
                x0, y0 = hx + s * (hrx - 1), hy - 1 + i * 2
                x1, y1 = x0 + s * (6 + (1 if style == "gills_big" else 0)) * math.cos(ang), y0 + 6 * math.sin(ang)
                cv.part(line(x0, y0, x1, y1) | ellipse(x1, y1, 1.3, 1.3), accent, outline=OUTLINE)
                cv.paint({(int((x0 + x1) / 2) + s, int((y0 + y1) / 2) - 1)}, accent)
        elif style == "devil":
            cv.part(poly([(hx + s * 5, top + 3), (hx + s * 14, top - 3), (hx + s * 11, top + 2), (hx + s * 12, top + 5),
                          (hx + s * 8, top + 6)]), shade, mix(shade, OUTLINE, 0.3))


def _front_ears(cv: Canvas, style: str, hx, hy, hrx, hry, base, shade, accent, f):
    flap = (0, 0, 1, 0)[f % 4]
    for s in (-1, 1):
        if style == "dog_floppy":
            cv.part(ellipse(hx + s * (hrx - 0.5), hy + 1 + flap, 3, 5.5), accent, mix(accent, OUTLINE, 0.3))
        elif style == "dog_long":
            cv.part(ellipse(hx + s * (hrx - 1), hy + 4 + flap, 3, 8), accent, mix(accent, OUTLINE, 0.3))
        elif style == "cat_fold":
            cv.part(poly([(hx + s * 7.5, hy - hry + 1), (hx + s * 3, hy - hry + 1.5), (hx + s * 6.5, hy - hry + 4.5)]),
                    base, shade)


def _tail(cv: Canvas, style: str, bx, by, brx, bry, base, shade, light, f):
    wag = (0, 1, 0, -1)[f % 4]
    x0 = bx + brx - 1
    if style in ("cat_long", "cat_fluffy"):
        r = 2.4 if style == "cat_fluffy" else 1.6
        pts = [(x0 + i * 0.9, by + 2 - i * 1.6 + wag * i / 6) for i in range(7)]
        cv.part(set().union(*(ellipse(x, y, r, r) for x, y in pts)), base, shade)
        if style == "cat_fluffy":
            cv.paint(ellipse(*pts[-1], r - 0.5, r - 0.5), light)
    elif style == "bobtail":
        cv.part(ellipse(x0 + 1, by + 1, 2.2, 2.2), base, shade)
    elif style == "dog_wag":
        cv.part(poly([(x0 - 1, by - 1), (x0 + 5 + wag * 2, by - 7), (x0 + 2, by + 1)]), base, shade)
    elif style == "dog_curl":
        ring = ellipse(x0 + 1, by - 5, 3.2, 3.2) - ellipse(x0 + 1, by - 5, 1.4, 1.4)
        cv.part(ring, base, shade)
    elif style == "pig_curl":
        cv.grid(x0, by - 2 + f % 2, [".aa", "a.a", ".a."], {"a": shade}, outline=True)
    elif style == "pig_straight":
        cv.paint(line(x0, by, x0 + 4, by - 2 + wag), OUTLINE)
    elif style == "fox":
        pts = [(x0 + i * 1.1, by + 1 - i * 1.2 + wag * i / 5) for i in range(6)]
        px = set().union(*(ellipse(x, y, 1.5 + i * 0.5, 1.5 + i * 0.5) for i, (x, y) in enumerate(pts)))
        cv.part(px, base, shade)
        cv.paint(ellipse(*pts[-1], 2.2, 2.2) & px, WHITE)
    elif style == "horse_tail":
        hair = mix(shade, OUTLINE, 0.45)
        px = poly([(x0 - 1, by - 3), (x0 + 3, by - 4), (x0 + 6 + wag, by + 6), (x0 + 4 + wag, by + 9), (x0 + 1, by + 3)])
        cv.part(px, hair)
        cv.paint({q for q in px if (q[0] + q[1]) % 3 == 0}, mix(hair, OUTLINE, 0.3))
    elif style == "axo_fin":
        px = ellipse(x0 + 4, by + 2, 6, 2.5)
        cv.part(px, base, shade)
        cv.paint({q for q in px if q[1] < by + 1}, mix(base, WHITE, 0.45))
    elif style == "devil_tail":
        cv.paint(line(x0, by + 1, x0 + 5, by - 4 + wag) | line(x0 + 5, by - 4 + wag, x0 + 7, by - 8), OUTLINE)
        cv.part(poly([(x0 + 5, by - 8), (x0 + 9, by - 10), (x0 + 8, by - 6)]), RED)


def _snout(cv: Canvas, style: str, hx, hy, hrx, hry, light, accent, shade):
    if style in ("pig", "pig_big"):
        r = 5.2 if style == "pig_big" else 4.2
        cv.part(ellipse(hx, hy + 3, r, 3 + (0.6 if style == "pig_big" else 0)), accent, mix(accent, shade, 0.5))
        cv.paint({(hx - 2, hy + 3), (hx + 1, hy + 3)}, mix(accent, OUTLINE, 0.6))
    elif style == "cat":
        cv.paint({(hx - 1, hy + 2), (hx, hy + 2), (hx, hy + 3)}, (255, 150, 170))
    elif style == "dog_muzzle":
        cv.part(ellipse(hx, hy + 3.5, 4, 3), mix(light, WHITE, 0.4), outline=None)
        cv.part(ellipse(hx, hy + 2.5, 2.2, 1.6), BLACK, outline=None)
    elif style == "fox_snout":
        cv.part(poly([(hx - 5, hy + 1), (hx + 5, hy + 1), (hx + 1, hy + 6), (hx - 1, hy + 6)]), accent, outline=None)
        cv.part(ellipse(hx, hy + 2.3, 1.6, 1.2), BLACK, outline=None)
    elif style == "horse_muzzle":  # long muzzle that sticks out under the head
        my = hy + hry - 2.5
        cv.part(ellipse(hx, my, 5, 3.8), mix(light, WHITE, 0.3), mix(light, shade, 0.5))
        cv.paint({(hx - 3, int(my)), (hx + 2, int(my))}, OUTLINE)
    elif style == "axo_smile":
        pass
    elif style == "heart_nose":
        cv.grid(hx - 2, hy + 1, ["a.a", "aaa", ".a."], {"a": (240, 70, 120)})
    else:
        cv.part(ellipse(hx, hy + 2.5, 2.2, 1.6), BLACK, outline=None)
        cv.paint({(hx - 1, hy + 2)}, (120, 110, 130))


def _pattern(cv: Canvas, g: Genome, head_px: Px, body_px: Px, hx, hy, hrx, hry, bx, by, brx, bry, shade, second):
    prng = random.Random(g.seed)
    skin = head_px | body_px
    dark = mix(second, OUTLINE, 0.25)
    p = g.pattern
    if p == "spots":
        for _ in range(5):
            x, y = prng.choice(sorted(skin))
            cv.paint(ellipse(x, y, 1.7, 1.4) & skin, dark)
    elif p == "dalmatian":
        for _ in range(14):
            x, y = prng.choice(sorted(skin))
            cv.paint({(x, y), (x + 1, y)} & skin, BLACK)
    elif p == "patch":
        s = prng.choice((-1, 1))
        cv.paint(ellipse(hx + s * 4, hy - 1, 3.5, 3) & head_px, dark)
    elif p == "tabby":
        st = mix(shade, OUTLINE, 0.3)
        for dx in (-2, 0, 2):
            cv.paint(line(hx + dx, hy - hry + 1, hx + dx, hy - hry + 3) & head_px, st)
        for dy in range(-bry + 2, bry - 1, 3):
            cv.paint((line(bx + brx - 4, by + dy, bx + brx, by + dy) | line(bx - brx, by + dy, bx - brx + 4, by + dy))
                     & body_px, st)
    elif p == "tiger":
        for dx in (-3, 0, 3):
            cv.paint(line(hx + dx, hy - hry, hx + dx + (1 if dx > 0 else -1 if dx < 0 else 0), hy - hry + 3) & head_px, dark)
        for s in (-1, 1):
            for dy in (0, 3):
                cv.paint(line(hx + s * hrx, hy + dy, hx + s * (hrx - 3), hy + dy + 1) & head_px, dark)
        for i, dy in enumerate(range(-bry + 2, bry - 1, 3)):
            for s in (-1, 1):
                x0 = bx + s * brx
                cv.paint((line(x0, by + dy, x0 - s * 3, by + dy + 1) | line(x0 - s * 3, by + dy + 1, x0 - s * (5 + i % 2), by + dy))
                         & body_px, dark)
    elif p == "leopard":
        for _ in range(8):
            x, y = prng.choice(sorted(skin))
            cv.paint({(x - 1, y), (x - 1, y - 1), (x, y - 1), (x + 1, y), (x + 1, y + 1), (x, y + 1)} & skin, dark)
            cv.paint({(x, y)} & skin, mix(shade, second, 0.25))
    elif p == "points":
        pc = mix(shade, OUTLINE, 0.4)
        cv.paint(ellipse(hx, hy + 3, 5, 4) & head_px, mix(pc, shade, 0.3))
        cv.paint({q for q in head_px if q[1] < hy - hry + 2}, mix(shade, pc, 0.5))
    elif p == "pinto":
        for _ in range(3):
            x, y = prng.choice(sorted(skin))
            cv.paint((ellipse(x, y, 4.5, 3.5) | ellipse(x + 2, y + 2, 3, 2.5)) & skin, second)
    elif p == "calico":
        for col in (second, mix(shade, OUTLINE, 0.4)):
            for _ in range(2):
                x, y = prng.choice(sorted(skin))
                cv.paint(ellipse(x, y, 3.2, 2.6) & skin, col)
    elif p == "mask":
        cv.paint(rect(hx - hrx + 1, hy - 3, hx + hrx - 1, hy) & head_px, dark)
    elif p == "gradient":
        cv.paint({q for q in head_px if q[1] < hy - hry + 4} | {q for q in body_px if q[1] < by - bry + 3}, shade)
    elif p == "saddle":  # dark sides, light front
        cv.paint({q for q in body_px if abs(q[0] + 0.5 - bx) > brx * 0.55}, dark)
    elif p == "tuxedo":
        cv.paint(ellipse(hx, hy + 4, 5, 3.5) & head_px, WHITE)


def _rainbow_galaxy(cv: Canvas, g: Genome, px: Px, f: int) -> None:
    if g.color == "rainbow":
        for x, y in px:
            cv.paint({(x, y)}, hsv((x + y + f * 3) / 30, 0.55, 1.0))
    elif g.color == "galaxy":
        rng = random.Random(g.seed)
        for q in rng.sample(sorted(px), min(len(px), len(px) // 9)):
            if (q[0] + f) % 3:
                cv.paint({q}, (255, 250, 210) if rng.random() < 0.7 else (150, 200, 255))
    elif g.color == "sunset" and px:
        y0, y1 = min(q[1] for q in px), max(q[1] for q in px)
        for x, y in px:
            t = (y - y0) / max(1, y1 - y0)
            cv.paint({(x, y)}, mix((255, 205, 90), (215, 60, 120), t))
    elif g.color == "frost":
        rng = random.Random(g.seed)
        for q in rng.sample(sorted(px), min(len(px), len(px) // 14)):
            cv.paint({q}, WHITE if (q[1] + f) % 3 else (170, 220, 255))


def _mark(cv: Canvas, mark: str, hx, hy, hry, light, second):
    y = hy - hry + 2
    col = GOLD if mark in ("trident", "lightning") else mix(light, WHITE, 0.5) if lum(light) < 200 else mix(second, OUTLINE, 0.3) \
        if lum(second) < 170 else (150, 120, 200)
    rows = {
        "star": [".a.", "aaa", ".a."], "heart": ["a.a", "aaa", ".a."], "moon": [".aa", "a..", ".aa"],
        "diamond": [".a.", "a.a", ".a."], "lightning": [".a", "a.", ".a"], "trident": ["a.a.a", "a.a.a", "aaaaa", "..a.."],
        "sun": ["a.a.a", ".aaa.", "aa.aa", ".aaa."], "drop": [".a.", "aaa", "aaa"], "spiral": ["aaa", "..a", "a.a", "aaa"],
        "flame": [".a.", "aab", "aba"],
    }.get(mark)
    if rows:
        cols = {"a": col, "b": col}
        if mark == "sun":
            cols["a"] = (255, 200, 60)
        elif mark == "drop":
            cols["a"] = (110, 180, 255)
        elif mark == "flame":
            cols = {"a": (255, 120, 30), "b": YELLOW}
        elif mark == "spiral":
            cols["a"] = (190, 120, 255)
        cv.grid(hx - len(rows[0]) // 2, y - (1 if len(rows) > 3 else 0), rows, cols)


def _eye(cv: Canvas, style: str, x: int, ey: int, iris: tuple, mood: str, f: int, s: int):
    """One open eye (neutral/sad/angry moods)."""
    if style == "big":
        cv.paint(rect(x - 1, ey - 2, x + 1, ey + 1), BLACK)
        cv.paint({(x - 1, ey - 2), (x + 1, ey)}, WHITE)
    elif style in ("slit", "hetero"):
        cv.paint(rect(x - 1, ey - 1, x + 1, ey + 1), iris)
        cv.paint({(x, ey - 1), (x, ey), (x, ey + 1)} if style == "slit" else {(x, ey)}, BLACK)
        cv.paint(dilate(rect(x - 1, ey - 1, x + 1, ey + 1)) - {(x - 2, ey - 2)}, OUTLINE)
    elif style == "sleepy":
        cv.paint(rect(x, ey, x + 1, ey + 1), BLACK)
        cv.paint({(x - 1, ey - 1), (x, ey - 1), (x + 1, ey - 1), (x + 2, ey - 1)}, OUTLINE)
    elif style == "button":
        cv.paint(rect(x, ey - 1, x + 1, ey), BLACK)
    elif style == "star":
        cv.paint({(x, ey - 2), (x - 1, ey), (x, ey), (x + 1, ey), (x, ey - 1), (x, ey + 1),
                  (x - 1, ey - 1 + f % 2), (x + 1, ey + 1 - f % 2)}, iris)
    else:  # dot, three
        cv.paint(rect(x, ey - 1, x + 1, ey + 1), BLACK)
        cv.paint({(x, ey - 1)}, WHITE)
    if mood == "angry":
        cv.paint({(x - 1, ey - 3), (x + 1, ey - 2)} if s < 0 else {(x + 1, ey - 3), (x - 1, ey - 2)}, OUTLINE)
    if mood == "sad" and s > 0:
        cv.paint({(x + 1, ey + 2), (x + 1, ey + 3 + f % 2)}, (90, 170, 255))


ALIEN_EYE = ["aaaa...", "aaaaaa.", "abaaaaa", ".aaaaaa", "...aaa."]


def _eyes_mouth(cv: Canvas, lk: Look, b: Body, f: int, roles: set[str]) -> None:
    g = lk.genes
    hx, hy, hrx, hry = b.head
    base, shade, *_, il, ir = b.pal
    mood = "dead" if lk.ghost else lk.mood
    blink = f == 3 and mood in ("ok", "happy")
    ey, ex = hy - 1, b.ex
    face = g.face
    pigface = face in ("pig", "pig_big")
    open_eyes = mood not in ("dead", "sleep", "sick", "happy") and not blink
    positions = [(hx, 0)] if g.eyes == "cyclops" else [(hx + s * ex - (1 if s < 0 else 0), s) for s in (-1, 1)]
    eye = Canvas(cv.w, cv.h, cv.ox)
    if "alien" in roles and open_eyes:
        for s in (-1, 1):
            rows = [r[::-1] for r in ALIEN_EYE] if s > 0 else ALIEN_EYE
            eye.grid(hx - 8 if s < 0 else hx + 1, ey - 3, rows, {"a": BLACK, "b": (140, 240, 210)})
            eye.paint({(hx - 7, ey - 2) if s < 0 else (hx + 6, ey - 2)}, WHITE)
    else:
        for x, s in positions:
            if mood == "dead":
                eye.paint({(x - 1, ey - 1), (x + 1, ey - 1), (x, ey), (x - 1, ey + 1), (x + 1, ey + 1)}, OUTLINE)
            elif mood in ("sleep", "sick") or blink:
                eye.paint({(x - 1, ey + 1), (x, ey + 1), (x + 1, ey + 1)}, OUTLINE)
            elif mood == "happy":
                eye.paint({(x - 1, ey + 1), (x, ey), (x + 1, ey + 1)}, OUTLINE)
            elif g.eyes == "cyclops":
                eye.part(ellipse(hx, ey, 3, 2.6), WHITE)
                eye.paint(ellipse(hx, ey, 1.6, 1.6), il)
                eye.paint({(hx, ey)}, BLACK)
            else:
                _eye(eye, g.eyes, x, ey, il if s < 0 else ir, mood, f, s)
        if g.eyes == "three" and mood not in ("dead",):
            eye.paint({(hx, ey - 4), (hx - 1, ey - 4)}, il if mood not in ("sleep", "sick") else OUTLINE)
        role_eye = next((ROLE_EYE[r] for r in ("vampire", "demon", "werewolf", "zombie") if r in roles), None)
        if role_eye and open_eyes and g.eyes in ("dot", "big", "button", "sleepy", "three"):
            eye.px = {p: (role_eye if c == BLACK else c) for p, c in eye.px.items()}
    if open_eyes and lum(base) < 80 and "alien" not in roles:  # dark fur: light rim so eyes stay readable
        rim = dilate({(x - eye.ox, y) for x, y in eye.px}) - {(x - eye.ox, y) for x, y in eye.px}
        cv.paint({q for q in rim if q[1] >= ey - 3}, mix(base, WHITE, 0.45))
    cv.px.update(eye.px)
    if "zombie" in roles and mood not in ("dead",):  # one droopy eye
        x = positions[0][0]
        cv.paint(rect(x - 1, ey - 2, x + 1, ey - 1), shade)
        cv.paint({(x - 1, ey), (x, ey), (x + 1, ey), (x + 2, ey - 1)}, OUTLINE)
    if "cyborg" in roles and mood != "dead":  # red LED eye
        x = hx + ex
        cv.part(rect(x - 1, ey - 1, x + 1, ey + 1), (120, 10, 20), outline=OUTLINE)
        cv.paint({(x, ey)} | ({(x - 1, ey), (x + 1, ey), (x, ey - 1), (x, ey + 1)} if f % 2 else set()), (255, 60, 50))
    blush = not roles & {"vampire", "zombie", "cyborg", "alien", "demon"}
    if mood in ("happy", "ok") and face not in ("dog", "dog_muzzle") and blush:
        for x, s in positions:
            if s:
                cv.paint({(x - 1 + (2 if s > 0 else 0), ey + 2 + (2 if pigface else 1))}, BLUSH)
    if mood == "sick":
        cv.paint({(hx - ex - 2, hy + 1), (hx + ex + 1, hy + 1)}, (150, 210, 110))

    my = hy + 6 if pigface else hy + hry - 1 if face == "horse_muzzle" else hy + 4
    if face == "axo_smile" and mood in ("happy", "ok"):
        cv.paint({(hx - 4, my - 1), (hx - 3, my), (hx - 2, my), (hx - 1, my), (hx, my), (hx + 1, my), (hx + 2, my - 1)}, OUTLINE)
    elif mood == "happy":
        cv.paint({(hx - 2, my), (hx + 1, my)} | rect(hx - 1, my + 1, hx, my + 1), OUTLINE)
        if face in ("dog", "dog_muzzle") or g.extra == "tongue":
            cv.paint({(hx - 1, my + 2), (hx, my + 2), (hx, my + 3 - f % 2)}, (255, 120, 140))
    elif mood in ("sad", "sick", "dead", "angry"):
        cv.paint({(hx - 2, my + 1), (hx - 1, my), (hx, my), (hx + 1, my + 1)}, OUTLINE)
    elif face == "cat":
        cv.paint({(hx - 2, my), (hx - 1, my + 1), (hx, my + 1), (hx + 1, my)}, OUTLINE)
    else:
        cv.paint({(hx - 1, my), (hx, my)}, OUTLINE)
    if g.extra == "tongue" and mood not in ("happy", "dead"):
        cv.paint({(hx, my + 1), (hx, my + 2)}, (255, 120, 140))
    if "vampire" in roles and mood != "dead":
        cv.paint({(hx - 2, my + 1), (hx - 2, my + 2), (hx + 1, my + 1), (hx + 1, my + 2)}, WHITE)
        cv.paint({(hx - 2, my + 3), (hx + 1, my + 3)}, (200, 20, 40) if f % 2 else WHITE)
    elif "werewolf" in roles or g.extra == "fangs":
        cv.paint({(hx - 2, my + 1), (hx + 1, my + 1)}, WHITE)
    if "zombie" in roles:
        cv.paint({(hx - 2, my - 1), (hx, my - 1), (hx + 2, my - 1)} - set(), mix(shade, OUTLINE, 0.5))
    if mood == "sleep":
        cv.grid(hx + 10, hy - 12 - f % 2, ["aaa", ".a.", "aaa"], {"a": WHITE}, outline=True)


def _extra(cv: Canvas, g: Genome, b: Body, second, f):
    hx, hy, hrx, hry = b.head
    base, shade, light = b.pal[:3]
    top = hy - hry
    e = g.extra
    if e == "freckles":
        for s in (-1, 1):
            cv.paint({(hx + s * 5, hy + 2), (hx + s * 6, hy + 3), (hx + s * 4, hy + 3)}, mix(second, OUTLINE, 0.4))
    elif e == "mohawk":
        for i, dx in enumerate(range(-3, 4, 2)):
            cv.part(poly([(hx + dx - 1, top + 1), (hx + dx, top - 4 - (i % 2) * 2), (hx + dx + 1.5, top + 1)]),
                    hsv(g.hue2, 0.8, 0.9))
    elif e == "curl":
        cv.paint({(hx, top), (hx + 1, top - 1), (hx + 2, top - 2), (hx + 1, top - 3), (hx, top - 2)}, OUTLINE)
    elif e == "antennae":
        for s in (-1, 1):
            cv.paint(line(hx + s * 2, top + 1, hx + s * 5, top - 6), OUTLINE)
            cv.part(ellipse(hx + s * 5.5, top - 7 + f % 2, 1.5, 1.5), hsv(g.hue2, 0.8, 1))
    elif e == "unicorn":
        px = poly([(hx - 1.5, top + 2), (hx + 0.5, top - 8), (hx + 2, top + 2)])
        cv.part(px, (255, 240, 200))
        cv.paint({q for q in px if (q[1] + q[0]) % 3 == 0}, (255, 170, 210))
    elif e == "whiskers":
        for s in (-1, 1):
            cv.paint(line(hx + s * (hrx - 3), hy + 2, hx + s * (hrx + 5), hy + 1 - f % 2), OUTLINE)
    elif e == "fluff":  # пухнастий комір
        y = hy + hry
        fl = set()
        for i, dx in enumerate(range(-9, 10, 3)):
            fl |= ellipse(hx + dx + 0.5, y - abs(dx) // 4 + 0.5, 2.2, 1.6)
            fl |= poly([(hx + dx - 1, y + 1), (hx + dx + 2, y + 1), (hx + dx + 0.5, y + 3 + i % 2)])
        col = mix(light, second, 0.35) if lum(light) > 200 else light
        cv.part(fl, col, mix(col, shade, 0.6), outline=None)
        cv.paint({q for q in fl if (q[0], q[1] + 1) not in fl or (q[0] - 1, q[1]) not in fl and q[1] > y}, mix(col, OUTLINE, 0.45))
    elif e == "beard":
        cv.part(poly([(hx - 2.5, hy + hry - 2), (hx + 2.5, hy + hry - 2), (hx + 0.5, hy + hry + 4)]), mix(second, shade, 0.5))
    elif e == "brows":
        for s in (-1, 1):
            x = hx + s * b.ex - (1 if s < 0 else 0)
            cv.paint(rect(x - 1, hy - 5, x + 2, hy - 4) - {(x - 1 if s < 0 else x + 2, hy - 5)}, mix(second, OUTLINE, 0.5))
    elif e == "horns":
        for s in (-1, 1):
            cv.part(poly([(hx + s * 3, top + 2), (hx + s * 5.5, top - 4), (hx + s * 6.5, top + 2)]), (238, 228, 200),
                    (196, 180, 150))


def _gene_wings(cv: Canvas, b: Body, f: int) -> None:
    bx, by, brx, _ = b.body
    light = b.pal[2]
    for s in (-1, 1):
        w = ellipse(bx + s * (brx + 2), by - 4 - f % 2, 3.5, 2.6) | ellipse(bx + s * (brx + 1), by - 1, 2.6, 2)
        cv.part(w, light, mix(light, OUTLINE, 0.25))


# --- role overlays -------------------------------------------------------------------------

def _role_back(cv: Canvas, roles: set[str], b: Body, f: int) -> None:
    hx, hy, hrx, hry = b.head
    bx, by, brx, bry = b.body
    sway = f % 2
    if "vampire" in roles:
        black, red = (34, 24, 40), (176, 22, 44)
        cv.part(poly([(bx - brx, hy + hry - 2), (bx + brx, hy + hry - 2), (bx + brx + 4 + sway, by + bry),
                      (bx - brx - 4 - sway, by + bry)]), black, (24, 16, 30))
        for s in (-1, 1):
            collar = poly([(hx + s * (hrx - 4), hy + hry + 1), (hx + s * (hrx + 4), hy - 4), (hx + s * (hrx + 1), hy + hry + 2)])
            cv.part(collar, red, (130, 14, 34))
            cv.paint(line(hx + s * (hrx + 4), hy - 4, hx + s * (hrx + 1), hy + hry + 2), black)
    if "angel" in roles:
        for s in (-1, 1):
            w = ellipse(bx + s * (brx + 4), by - 7 - sway, 6, 4) | ellipse(bx + s * (brx + 2), by - 3, 4.5, 3.2)
            cv.part(w, WHITE, (214, 220, 240), (255, 255, 255))
            cv.paint({(bx + s * (brx + 6), by - 6 - sway), (bx + s * (brx + 4), by - 4 - sway)}, (220, 226, 244))
    if "demon" in roles:
        for s in (-1, 1):
            cv.part(poly([(bx + s * brx * 0.5, by - 3), (bx + s * (brx + 6), by - 9 - sway), (bx + s * (brx + 5), by - 2),
                          (bx + s * (brx + 2), by)]), (90, 20, 30), (60, 12, 20))


def _role_body(cv: Canvas, roles: set[str], b: Body, f: int) -> None:
    """After body, before outfit: claws, fur, stitches, bolts."""
    bx, by, brx, bry = b.body
    base, shade, light = b.pal[:3]
    if "werewolf" in roles:
        for s in (-1, 1):
            x = int(bx + s * brx * 0.55)
            cv.paint({(x - 2, by + bry + 1), (x, by + bry + 2), (x + 2, by + bry + 1)}, (245, 240, 225))
            cv.part(poly([(bx + s * (brx - 1), by - 3), (bx + s * (brx + 3), by - 1), (bx + s * (brx - 0.5), by + 1),
                          (bx + s * (brx + 2), by + 3), (bx + s * (brx - 1), by + 4)]), base, shade)
        cv.paint({(bx + dx, by - bry + 2 + abs(dx) % 2) for dx in range(-3, 4)}, light)
    if "zombie" in roles:
        x = bx - brx // 2
        cv.paint(line(x, by - bry + 3, x + 1, by + 3), mix(shade, OUTLINE, 0.5))
        cv.paint({(x - 1, y) for y in range(by - bry + 4, by + 3, 2)} | {(x + 2, y) for y in range(by - bry + 4, by + 3, 2)},
                 mix(shade, OUTLINE, 0.5))
    if "cyborg" in roles:
        for s in (-1, 1):
            x = bx + s * (brx - 2)
            cv.part(rect(x - 1 if s > 0 else x, by - bry + 2, x if s > 0 else x + 1, by - bry + 3), (170, 176, 190))


def _role_head(cv: Canvas, roles: set[str], b: Body, f: int) -> None:
    """After head/pattern/ears, before snout & eyes."""
    hx, hy, hrx, hry = b.head
    base, shade, light = b.pal[:3]
    top = hy - hry
    if "cyborg" in roles:
        metal, metal_d = (176, 182, 196), (130, 136, 152)
        plate = {q for q in b.head_px if q[0] >= hx and q[1] <= hy + 3}
        cv.part(plate, metal, metal_d, (214, 220, 230), outline=None)
        cv.paint(line(hx, top + 1, hx, hy + 3) | line(hx, hy + 3, hx + hrx - 1, hy + 3), OUTLINE)
        cv.paint({(hx + 2, top + 3), (hx + hrx - 3, top + 4), (hx + 2, hy + 1), (hx + hrx - 2, hy)} & plate, (96, 100, 116))
    if "werewolf" in roles:
        for s in (-1, 1):
            cv.part(poly([(hx + s * (hrx - 2), hy - 1), (hx + s * (hrx + 3), hy + 1), (hx + s * (hrx - 1), hy + 2),
                          (hx + s * (hrx + 2), hy + 4), (hx + s * (hrx - 3), hy + 5)]), base, shade)
        for i, dx in enumerate((-2, 0, 2)):
            cv.part(poly([(hx + dx - 1.5, top + 2), (hx + dx + 0.5, top - 2 - i % 2), (hx + dx + 1.5, top + 2)]), shade)
    if "zombie" in roles:
        st = mix(shade, OUTLINE, 0.55)
        x0, y0 = hx + 2, top + 2
        cv.paint(line(x0, y0, x0 + 5, y0 + 3), st)
        cv.paint({(x0 + i, y0 + i * 3 // 5 - 1) for i in range(0, 6, 2)} | {(x0 + i, y0 + i * 3 // 5 + 1) for i in range(0, 6, 2)}, st)


def _role_top(cv: Canvas, roles: set[str], b: Body, f: int) -> None:
    """After extras, before items: horns, antennae."""
    hx, hy, hrx, hry = b.head
    top = hy - hry
    if "demon" in roles:
        for s in (-1, 1):
            cv.part(poly([(hx + s * 2.5, top + 2), (hx + s * 6, top - 2), (hx + s * 9, top - 7), (hx + s * 8, top - 1),
                          (hx + s * 6.5, top + 3)]), (70, 20, 30), (40, 10, 18), (130, 40, 50))
    if "alien" in roles:
        for s in (-1, 1):
            cv.paint(line(hx + s * 3, top + 1, hx + s * 6, top - 6), OUTLINE)
            cv.part(ellipse(hx + s * 6.5, top - 7 + (f + (s > 0)) % 2, 1.6, 1.6), (150, 255, 120) if f % 2 else (220, 255, 190))
    if "cyborg" in roles:
        cv.paint(line(hx + 4, top + 1, hx + 6, top - 6), (110, 116, 130))
        cv.part(ellipse(hx + 6.5, top - 7, 1.3, 1.3), (255, 60, 50) if f % 2 else (120, 20, 20))


def _role_aura(cv: Canvas, roles: set[str], b: Body, f: int) -> None:
    hx, hy, hrx, hry = b.head
    bx, by, brx, bry = b.body
    top = hy - hry
    if "angel" in roles:
        y = top - 5 + f % 2
        cv.paint(ellipse(hx, y, 6, 2) - ellipse(hx, y, 4, 1), (255, 236, 110))
        cv.paint({(hx - 5, y), (hx + 5, y)}, (255, 250, 200))
        it_sparkles(cv, b, f)
    if "zombie" in roles:
        it_flies(cv, b, f)
    if "demon" in roles:
        for i, dx in enumerate(range(-brx - 1, brx + 2, 4)):
            h = 1 + (i + f) % 3
            cv.paint(poly([(bx + dx - 1.5, by + bry + 1), (bx + dx, by + bry - h), (bx + dx + 1.5, by + bry + 1)]), (255, 110, 30))
            cv.paint({(bx + dx, by + bry)}, YELLOW)
    if "vampire" in roles:
        for i, (dx, dy) in enumerate(((-16, -9), (13, -12))):
            rows = ["a...a", "aa.aa", ".aaa."] if (f + i) % 2 else ["..a..", "aaaaa", "a...a"]
            cv.grid(hx + dx, hy + dy + (f + i) % 2, rows, {"a": (40, 26, 50)})
            cv.paint({(hx + dx + 2, hy + dy + (f + i) % 2 + 1)}, (255, 60, 60))


def creature(cv: Canvas, lk: Look, f: int, roles: set[str] | None = None) -> Body:
    g = lk.genes
    roles = set() if lk.ghost else (roles or set())
    pal = palette(g, "+".join(sorted(roles)))
    base, shade, light, accent, second, il, ir = pal
    if lk.ghost:
        _, base, shade, light, accent = GHOST
        pal = (base, shade, light, accent, second, il, ir)
    (hx, hy, hrx, hry), (bx, by, brx, bry), ex = _geom(lk, f)
    b = Body((hx, hy, hrx, hry), (bx, by, brx, bry), ex, set(), set(), pal, lk.stage)
    horse = g.ears in ("horse_ears", "unicorn_mane") and not lk.ghost
    pointc = mix(shade, OUTLINE, 0.4) if g.pattern == "points" and not lk.ghost else None

    if g.extra == "wings" and not lk.ghost:
        _gene_wings(cv, b, f)
    _tail(cv, "devil_tail" if "demon" in roles else g.tail, bx, by, brx, bry, pointc or base, shade, light, f)
    if horse:  # mane flows down the back of the neck
        mane = mix(accent, OUTLINE, 0.2)
        px = poly([(hx + 1, hy - hry - 1), (hx + hrx - 1, hy - hry + 1), (hx + hrx + 3, hy + 1), (hx + hrx + 2, hy + hry + 3),
                   (hx + hrx - 3, hy + hry + 1)])
        cv.part(px, mane)
        cv.paint({q for q in px if (q[0] * 2 + q[1]) % 5 == 0}, mix(mane, OUTLINE, 0.35))
    if g.ears in BACK_EARS:
        _ears(cv, g.ears, hx, hy, hrx, hry, pointc or base, shade, accent, f)

    body_px = ellipse(bx, by, brx, bry)
    if lk.ghost:
        body_px = {p for p in body_px if p[1] < by + bry - 2 or (p[0] + f) % 4 < 2}
    else:
        paw = WHITE if g.pattern in ("socks", "tuxedo") else pointc or shade
        for s in (-1, 1):
            cv.part(ellipse(bx + s * (brx * 0.55), by + bry - 1, 2.6, 2), paw)
    cv.part(body_px, base, shade, light)
    belly = ellipse(bx, by + 1, brx * (0.65 if g.pattern == "tuxedo" else 0.55), bry * 0.6) & body_px
    cv.paint(belly, WHITE if g.pattern == "tuxedo" else light)
    b.body_px = body_px
    if roles:
        _role_body(cv, roles, b, f)

    for it in lk.items:
        if _item(it)[1] == "outfit" and not lk.ghost:
            _draw_item(cv, it, b, f)

    head_px = ellipse(hx, hy, hrx, hry)
    b.head_px = head_px
    cv.part(head_px, base, shade, light)
    if not lk.ghost and not roles & set(ROLE_TINT):
        _rainbow_galaxy(cv, g, head_px | {p for p in body_px if p not in belly}, f)
        _pattern(cv, g, head_px, body_px, hx, hy, hrx, hry, bx, by, brx, bry, shade, second)
        _mark(cv, g.mark, hx, hy, hry, light, second)
    if horse:  # forelock
        mane = mix(accent, OUTLINE, 0.2)
        cv.part(poly([(hx - 3, hy - hry - 1), (hx + 2, hy - hry - 1), (hx + 1, hy - hry + 3), (hx - 1, hy - hry + 4)]), mane)
        if g.ears == "unicorn_mane":
            cv.part(ellipse(hx - 2, hy - hry + 1, 2.5, 1.8), hsv(g.hue2, 0.7, 0.95))
    if g.ears not in BACK_EARS:
        _front_ears(cv, g.ears, hx, hy, hrx, hry, base, shade, accent if g.species == "dog" else shade, f)
    if roles:
        _role_head(cv, roles, b, f)
    _snout(cv, g.face, hx, hy, hrx, hry, light, accent, shade)
    _eyes_mouth(cv, lk, b, f, roles)
    if not lk.ghost:
        _extra(cv, g, b, second, f)
    if roles:
        _role_top(cv, roles, b, f)
    if lk.stage == 4 and not lk.ghost:
        for s in (-1, 1):
            x = hx + s * ex - (1 if s < 0 else 0)
            cv.paint({(x - 1, hy - 4), (x, hy - 4), (x + 1, hy - 4)}, (220, 220, 225))
    return b


# --- items ---------------------------------------------------------------------------------
# Each item: (name, slot, draw(cv, body, frame)). Slots: back, outfit, neck, face, head, held, aura, fg.

def _clip_outfit(cv: Canvas, b: Body, color: tuple, shade: tuple, sleeves: bool = True) -> Px:
    bx, by, brx, bry = b.body
    px = {p for p in b.body_px if p[1] <= by + bry - 3}
    cv.part(px, color, shade, outline=None)
    return px


# head
def it_horns(cv, b, f):
    hx, top, _ = _top(b)
    for s in (-1, 1):
        cv.part(poly([(hx + s * 3, top + 2), (hx + s * 7, top - 4), (hx + s * 6.5, top + 2.5)]), RED, (160, 20, 30))


def it_vinok(cv, b, f):
    hx, top, hrx = _top(b)
    cols = [RED, YELLOW, BLUE, WHITE, RED]
    for i, dx in enumerate(range(-8, 9, 4)):
        y = top + 1 + abs(dx) // 3
        cv.part(ellipse(hx + dx, y, 2, 1.8), cols[i])
        cv.paint({(hx + dx, y)}, (255, 240, 160))
    for s, col in ((-1, BLUE), (1, YELLOW)):
        x = hx + s * (hrx + 1)
        cv.paint(line(x, top + 4, x + s, top + 12 + f % 2), col)


def it_bow(cv, b, f):
    hx, top, _ = _top(b)
    cv.grid(hx + 3, top - 1, ["aa.aa", "abbba", "aa.aa"], {"a": (255, 110, 170), "b": (220, 60, 130)}, outline=True)


def it_wizard(cv, b, f):
    hx, top, _ = _top(b)
    cv.part(poly([(hx - 7, top + 3), (hx + 1, top - 12), (hx + 7, top + 3)]), (110, 60, 190), (80, 40, 150))
    cv.part(rect(hx - 9, top + 2, hx + 8, top + 3), (90, 50, 170))
    cv.paint({(hx, top - 4), (hx - 1, top - 3), (hx + 1, top - 3), (hx, top - 2)}, (255, 230, 90))


def it_crown(cv, b, f):
    hx, top, _ = _top(b)
    cv.part(poly([(hx - 6, top + 2), (hx - 6, top - 4), (hx - 3, top - 1), (hx, top - 5), (hx + 3, top - 1),
                  (hx + 6, top - 4), (hx + 6, top + 2)]), GOLD, GOLD_D)
    cv.paint({(hx, top - 1)}, RED)
    cv.paint({(hx - 4, top), (hx + 4, top)}, BLUE)


def it_cap(cv, b, f):  # кепка-восьмиклинка
    hx, top, _ = _top(b)
    cv.part(ellipse(hx, top + 2, 8, 3.5), (90, 90, 96), (66, 66, 72))
    cv.part(rect(hx - 1, top + 4, hx + 10, top + 5), (70, 70, 76))
    cv.paint({(hx, top - 1)}, (60, 60, 66))


def it_helmet(cv, b, f):  # каска
    hx, top, hrx = _top(b)
    px = {p for p in ellipse(hx, top + 4, hrx + 1, 7) if p[1] <= top + 4}
    cv.part(px, (96, 110, 70), (74, 86, 52))
    cv.paint(rect(hx - hrx - 1, top + 4, hx + hrx, top + 4), (74, 86, 52))


def it_chef(cv, b, f):
    hx, top, _ = _top(b)
    cv.part(ellipse(hx - 3, top - 4, 3.5, 3.5) | ellipse(hx + 3, top - 4, 3.5, 3.5) | ellipse(hx, top - 6, 3.5, 3.5)
            | rect(hx - 5, top - 3, hx + 5, top + 2), WHITE, (220, 220, 230))


def it_cowboy(cv, b, f):
    hx, top, _ = _top(b)
    cv.part(rect(hx - 5, top - 5, hx + 5, top + 1) | ellipse(hx, top + 1.5, 11, 1.8), (150, 100, 60), (120, 76, 44))
    cv.paint(rect(hx - 5, top - 1, hx + 5, top - 1), (90, 50, 30))


def it_party(cv, b, f):
    hx, top, _ = _top(b)
    px = poly([(hx - 5, top + 2), (hx + 2, top - 11), (hx + 5, top + 2)])
    cv.part(px, (80, 200, 255))
    cv.paint({p for p in px if (p[0] + p[1]) % 4 == 0}, (255, 90, 160))
    cv.paint(ellipse(hx + 2, top - 11, 1.5, 1.5), YELLOW)


def it_halo(cv, b, f):
    hx, top, _ = _top(b)
    ring = ellipse(hx, top - 4 + f % 2, 6, 2) - ellipse(hx, top - 4 + f % 2, 4, 1)
    cv.paint(ring, (255, 240, 120))


def it_beanie(cv, b, f):  # шапка з помпоном
    hx, top, hrx = _top(b)
    px = {p for p in ellipse(hx, top + 4, hrx, 7) if p[1] <= top + 3}
    cv.part(px, (220, 60, 60))
    cv.paint({p for p in px if p[1] == top + 2 or p[1] == top + 3}, WHITE)
    cv.part(ellipse(hx, top - 4, 2, 2), WHITE)


def it_headphones(cv, b, f):
    hx, hy, hrx, _ = b.head
    _, top, _ = _top(b)
    cv.paint({p for p in ellipse(hx, hy, hrx + 2, 11) - ellipse(hx, hy, hrx + 1, 10) if p[1] < hy - 2}, (50, 50, 60))
    for s in (-1, 1):
        cv.part(rect(hx + s * hrx - 1, hy - 2, hx + s * hrx + 1, hy + 2), (230, 60, 90))


def it_oseledets(cv, b, f):  # козацький чуб
    hx, top, _ = _top(b)
    cv.part(ellipse(hx, top, 2, 1.5) | line(hx + 1, top, hx + 5, top - 2) | line(hx + 5, top - 2, hx + 8, top + 3 + f % 2),
            (40, 30, 30))


def it_foil(cv, b, f):  # шапочка з фольги
    hx, top, _ = _top(b)
    px = poly([(hx - 7, top + 3), (hx - 2, top - 8), (hx + 1, top - 3), (hx + 4, top - 9), (hx + 7, top + 3)])
    cv.part(px, (200, 205, 215), (160, 165, 175), WHITE)


def it_flower(cv, b, f):
    hx, top, _ = _top(b)
    cv.grid(hx - 8, top - 1, [".a.", "aba", ".a."], {"a": (255, 140, 200), "b": YELLOW}, outline=True)


# face
def it_sunglasses(cv, b, f):
    for s in (-1, 1):
        x, ey = _eye_xy(b, s)
        cv.part(rect(x - 2, ey - 2, x + 2, ey + 1), BLACK)
        cv.paint({(x - 1, ey - 1)}, (120, 200, 255))
    hx, ey = b.head[0], b.head[1] - 1
    cv.paint(line(hx - 2, ey - 1, hx + 1, ey - 1), BLACK)


def it_eyepatch(cv, b, f):
    hx, hy, hrx, _ = b.head
    x, ey = _eye_xy(b, -1)
    cv.paint(line(hx - hrx, ey - 4, hx + hrx - 1, ey - 2), BLACK)
    cv.part(ellipse(x + 0.5, ey + 0.5, 2.5, 2.2), BLACK)


def it_scar(cv, b, f):
    x, ey = _eye_xy(b, 1)
    cv.paint(line(x + 2, ey - 3, x - 1, ey + 3), (200, 60, 70))


def it_monocle(cv, b, f):
    x, ey = _eye_xy(b, 1)
    cv.paint(ellipse(x + 0.5, ey + 0.5, 2.5, 2.5) - ellipse(x + 0.5, ey + 0.5, 1.6, 1.6), GOLD)
    cv.paint(line(x + 2, ey + 3, x + 3, ey + 8), GOLD_D)


def it_nerd(cv, b, f):
    for s in (-1, 1):
        x, ey = _eye_xy(b, s)
        cv.paint(ellipse(x + 0.5, ey + 0.5, 2.6, 2.6) - ellipse(x + 0.5, ey + 0.5, 1.7, 1.7), BLACK)
    hx, ey = b.head[0], b.head[1] - 1
    cv.paint(line(hx - 1, ey, hx, ey), BLACK)


def it_mustache(cv, b, f):  # козацькі вуса
    hx, hy, _, _ = b.head
    y = hy + 4
    cv.part(line(hx - 1, y, hx - 4, y + 1) | line(hx - 4, y + 1, hx - 6, y + 5) | line(hx, y, hx + 3, y + 1)
            | line(hx + 3, y + 1, hx + 5, y + 5), (60, 40, 30), outline=None)


def it_clown(cv, b, f):
    hx, hy, _, _ = b.head
    cv.part(ellipse(hx, hy + 2.5, 2.2, 2.2), RED, (180, 30, 30), (255, 140, 140))


def it_mask(cv, b, f):
    hx, hy, hrx, _ = b.head
    cv.part(rect(hx - 4, hy + 1, hx + 3, hy + 6), (170, 220, 240), (140, 190, 210))
    cv.paint(line(hx - 4, hy + 2, hx - hrx, hy) | line(hx + 3, hy + 2, hx + hrx - 1, hy), WHITE)


def it_plaster(cv, b, f):
    hx, hy, _, _ = b.head
    cv.paint(line(hx + 4, hy + 1, hx + 7, hy - 2) | line(hx + 5, hy + 1, hx + 7, hy - 1), (240, 210, 170))


def it_tears(cv, b, f):  # tattoo tears — gangsta
    x, ey = _eye_xy(b, -1)
    cv.paint({(x, ey + 3), (x, ey + 5)}, (40, 60, 120))


def it_vr(cv, b, f):
    hx, hy, hrx, _ = b.head
    cv.part(rect(hx - 7, hy - 4, hx + 6, hy + 1), (40, 40, 50), (30, 30, 36))
    cv.paint(line(hx - 5, hy - 2, hx + 4, hy - 2), (80, 220, 255) if f % 2 else (180, 80, 255))


# neck
def it_chain(cv, b, f):
    hx, hy, _, hry = b.head
    ny = hy + hry
    for i, dx in enumerate(range(-6, 7, 2)):
        cv.paint({(hx + dx, ny - 1 + abs(dx) // 3)}, GOLD if i % 2 else GOLD_D)
    cv.part(ellipse(hx, ny + 4, 2.5, 2.5), GOLD, GOLD_D)
    cv.paint({(hx, ny + 3), (hx, ny + 5)}, (150, 100, 20))


def it_bib(cv, b, f):
    hx, hy, _, hry = b.head
    ny = hy + hry - 1
    cv.part(poly([(hx - 6, ny), (hx + 6, ny), (hx, ny + 8)]), WHITE, (220, 220, 230))
    cv.paint({(hx - 3, ny + 1), (hx + 2, ny + 2), (hx - 1, ny + 4)}, (230, 60, 70))


def it_bowtie(cv, b, f):
    hx, hy, _, hry = b.head
    cv.grid(hx - 3, hy + hry, ["aa.aa", "abbba", "aa.aa"], {"a": RED, "b": (160, 20, 30)}, outline=True)


def it_tie(cv, b, f):
    hx, hy, _, hry = b.head
    cv.part(poly([(hx - 1, hy + hry), (hx + 1, hy + hry), (hx + 2, hy + hry + 7), (hx, hy + hry + 9),
                  (hx - 2, hy + hry + 7)]), (40, 60, 160), (30, 40, 120))


def it_scarf(cv, b, f):
    hx, hy, hrx, hry = b.head
    y = hy + hry - 1
    cv.part(rect(hx - 7, y, hx + 6, y + 1), BLUE, outline=OUTLINE)
    cv.paint(rect(hx - 7, y + 1, hx + 6, y + 1), YELLOW)
    cv.part(rect(hx + 3, y + 2, hx + 5, y + 7 + f % 2), BLUE)
    cv.paint(rect(hx + 3, y + 5, hx + 5, y + 7 + f % 2), YELLOW)


def it_medal(cv, b, f):
    hx, hy, _, hry = b.head
    y = hy + hry
    cv.paint(line(hx - 2, y, hx, y + 3) | line(hx + 2, y, hx, y + 3), BLUE)
    cv.part(ellipse(hx, y + 5, 2, 2), GOLD, GOLD_D)


def it_bell(cv, b, f):
    hx, hy, hrx, hry = b.head
    y = hy + hry
    cv.paint(rect(hx - 6, y - 1, hx + 5, y - 1), RED)
    cv.part(ellipse(hx, y + 2, 2, 2), GOLD, GOLD_D)


def it_korali(cv, b, f):  # намисто-коралі
    hx, hy, _, hry = b.head
    for r, c in ((0, RED), (2, (240, 80, 60))):
        for dx in range(-6, 7, 2):
            cv.part({(hx + dx, hy + hry - 1 + r + abs(dx) // 3)}, c, outline=None)


# outfit (drawn over the body)
def it_vyshyvanka(cv, b, f):
    bx, by, _, _ = b.body
    px = _clip_outfit(cv, b, (250, 248, 240), (220, 216, 206))
    cv.paint({p for p in px if abs(p[0] - bx) <= 1 and (p[1] + p[0]) % 2 == 0}, RED)
    cv.paint({p for p in px if abs(p[0] - bx) == 2 and p[1] % 2 == 0}, BLACK)
    cv.paint({p for p in px if p[1] == by + 3 and p[0] % 2}, RED)


def it_suit(cv, b, f):
    bx, by, _, bry = b.body
    px = _clip_outfit(cv, b, (50, 54, 70), (36, 40, 52))
    cv.paint({p for p in px if abs(p[0] - bx) <= (p[1] - (by - bry)) // 2 and p[1] < by + 2}, WHITE)


def it_hoodie(cv, b, f):
    bx, by, _, _ = b.body
    px = _clip_outfit(cv, b, (120, 120, 130), (96, 96, 106))
    cv.paint(rect(bx - 3, by + 2, bx + 2, by + 4) & px, (100, 100, 110))
    cv.paint({(bx - 1, by - 3), (bx, by - 3), (bx - 1, by - 2), (bx, by - 1)} & px, WHITE)


def it_tracksuit(cv, b, f):  # спортивка з трьома смужками
    bx, by, brx, _ = b.body
    px = _clip_outfit(cv, b, (40, 60, 160), (30, 44, 120))
    for dx in (-brx + 2, -brx + 4, brx - 3, brx - 5):
        cv.paint({p for p in px if p[0] == bx + dx}, WHITE)


def it_bronik(cv, b, f):
    bx, by, _, _ = b.body
    px = _clip_outfit(cv, b, (96, 110, 70), (74, 86, 52))
    cv.part(rect(bx - 4, by - 2, bx + 3, by + 3) & px, (110, 124, 80))
    cv.grid(bx - 1, by - 1, ["ab", "ba"], {"a": BLUE, "b": YELLOW})


def it_prison(cv, b, f):
    px = _clip_outfit(cv, b, (240, 240, 240), (210, 210, 210))
    cv.paint({p for p in px if p[1] % 3 == 0}, BLACK)


def it_coat(cv, b, f):  # лікарський халат
    bx, by, _, _ = b.body
    px = _clip_outfit(cv, b, WHITE, (220, 226, 230))
    cv.paint(line(bx, by - 6, bx, by + 6) & px, (190, 196, 200))
    cv.paint({(bx - 4, by - 1), (bx - 3, by - 1), (bx - 4, by)} & px, RED)


def it_apron(cv, b, f):
    bx, by, _, _ = b.body
    cv.part(rect(bx - 4, by - 3, bx + 3, by + 6) & b.body_px, (240, 240, 230), (210, 210, 200))
    cv.paint({(bx - 2, by + 2), (bx + 1, by + 4)}, RED)


def it_robe(cv, b, f):  # мантія сектанта
    bx, by, _, _ = b.body
    px = _clip_outfit(cv, b, (90, 30, 60), (66, 20, 44))
    cv.paint({p for p in px if p[0] == bx or p[0] == bx - 1}, GOLD)


def it_spacesuit(cv, b, f):
    bx, by, _, _ = b.body
    px = _clip_outfit(cv, b, (236, 236, 240), (200, 200, 210))
    cv.part(rect(bx - 3, by - 2, bx + 2, by + 1) & px, (60, 60, 70))
    cv.paint({(bx - 2, by - 1), (bx + 1, by)}, (80, 220, 120) if f % 2 else RED)


# back (drawn behind the creature)
def it_cape(cv, b, f):
    hx, hy, _, hry = b.head
    bx, by, brx, bry = b.body
    sway = f % 2
    cv.part(poly([(bx - brx + 1, hy + hry - 1), (bx + brx - 1, hy + hry - 1), (bx + brx + 3 + sway, by + bry),
                  (bx - brx - 3 - sway, by + bry)]), (180, 30, 40), (130, 20, 30))


def it_angel_wings(cv, b, f):
    bx, by, brx, _ = b.body
    flap = f % 2
    for s in (-1, 1):
        cv.part(ellipse(bx + s * (brx + 3), by - 5 - flap, 5, 3.5) | ellipse(bx + s * (brx + 1), by - 2, 4, 3), WHITE,
                (220, 220, 235))


def it_bat_wings(cv, b, f):
    bx, by, brx, _ = b.body
    flap = f % 2
    for s in (-1, 1):
        cv.part(poly([(bx + s * brx * 0.5, by - 4), (bx + s * (brx + 9), by - 10 - flap), (bx + s * (brx + 7), by - 2),
                      (bx + s * (brx + 4), by), (bx + s * brx, by + 1)]), (60, 30, 70), (40, 20, 50))


def it_jetpack(cv, b, f):
    bx, by, brx, _ = b.body
    for s in (-1, 1):
        x = bx + s * (brx - 1)
        cv.part(rect(x - 2, by - 7, x + 1, by + 1), (170, 170, 180), (130, 130, 140))
        cv.paint({(x - 1, by + 2), (x, by + 2), (x - 1 + f % 2, by + 3)}, (255, 150, 40))


def it_backpack(cv, b, f):
    bx, by, brx, _ = b.body
    cv.part(rect(bx - brx - 3, by - 6, bx - brx + 3, by + 3), (200, 120, 50), (160, 90, 30))


# held (in the right "hand")
def it_coffee(cv, b, f):
    _held(cv, b, [".s.", "aaa", "aab", "aaa"], {"a": WHITE, "b": WHITE, "s": (200, 200, 200) if f % 2 else (230, 230, 230)})


def it_mic(cv, b, f):
    _held(cv, b, ["aa", "aa", ".b", ".b", ".b"], {"a": (90, 90, 100), "b": BLACK})


def it_sabre(cv, b, f):  # шабля
    x, y = b.hand
    cv.part(line(x + 1, y + 2, x + 6, y - 9) | line(x + 2, y + 2, x + 7, y - 8), (220, 225, 235), outline=OUTLINE)
    cv.paint(rect(x, y + 1, x + 3, y + 1), GOLD)


def it_phone(cv, b, f):
    _held(cv, b, ["aaa", "aba", "aba", "aaa"], {"a": BLACK, "b": (90, 200, 255) if f % 2 else (120, 220, 255)})


def it_bottle(cv, b, f):
    _held(cv, b, [".a.", ".a.", "bbb", "bcb", "bbb"], {"a": (60, 120, 60), "b": (90, 160, 80), "c": WHITE})


def it_moneybag(cv, b, f):
    _held(cv, b, [".a.", "bbb", "bcb", "bbb"], {"a": (120, 80, 40), "b": (200, 160, 90), "c": (60, 140, 60)}, dy=2)


def it_book(cv, b, f):
    _held(cv, b, ["aaaa", "abba", "aaaa"], {"a": (60, 90, 170), "b": YELLOW})


def it_flowers(cv, b, f):
    _held(cv, b, ["a.c", ".b.", ".b."], {"a": RED, "c": (255, 140, 200), "b": (60, 150, 60)})


def it_guitar(cv, b, f):
    x, y = b.hand
    cv.part(ellipse(x + 1, y + 3, 3, 2.5), (200, 120, 50), (160, 90, 30))
    cv.part(line(x + 2, y + 2, x + 7, y - 6), (110, 70, 40))
    cv.paint({(x + 1, y + 3)}, BLACK)


def it_balloon(cv, b, f):
    x, y = b.hand
    cv.paint(line(x + 1, y + 1, x + 3, y - 12), (220, 220, 220))
    cv.part(ellipse(x + 3, y - 15 + f % 2, 3, 3.5), RED, (170, 30, 30), (255, 140, 140))


def it_cane(cv, b, f):
    x, y = b.hand
    cv.part(line(x + 2, y - 2, x + 2, y + 11) | {(x + 1, y - 3), (x, y - 2)}, (140, 90, 50))


def it_drone(cv, b, f):
    hx, top, _ = _top(b)
    y = max(2, top - 10) + f % 2
    cv.part(rect(hx + 6, y, hx + 11, y + 1), (60, 64, 60))
    cv.paint({(hx + 5 + f % 2 * 2, y - 1), (hx + 10 + f % 2 * 2, y - 1)}, (200, 200, 200))
    cv.paint({(hx + 8, y + 2)}, RED if f % 2 else (100, 20, 20))


def it_wand(cv, b, f):
    x, y = b.hand
    cv.part(line(x + 1, y + 1, x + 5, y - 5), (60, 40, 30))
    cv.paint({(x + 6, y - 6), (x + 5, y - 7), (x + 7, y - 7), (x + 6, y - 8)} if f % 2 else {(x + 6, y - 6)}, YELLOW)


def it_laptop(cv, b, f):
    _held(cv, b, ["aaaaa", "abbba", "abbba", "ccccc"], {"a": (60, 60, 70), "b": (120, 200, 255), "c": (160, 160, 170)},
          dx=-1, dy=2)


def it_sausage(cv, b, f):  # кільце ковбаси
    x, y = b.hand
    ring = ellipse(x + 2, y + 1, 3, 3) - ellipse(x + 2, y + 1, 1.5, 1.5)
    cv.part(ring, (170, 70, 60), (130, 50, 40))


def it_cards(cv, b, f):
    _held(cv, b, ["ab.", "abb", ".bb"], {"a": WHITE, "b": (250, 240, 240)})
    x, y = b.hand
    cv.paint({(x, y + 1), (x + 2, y + 2)}, RED)


# aura & foreground
def it_sparkles(cv, b, f):
    hx, hy, _, _ = b.head
    for i, (dx, dy) in enumerate(((-14, -8), (13, -4), (-12, 8), (14, 10))):
        if (i + f) % 2:
            cv.paint({(hx + dx, hy + dy), (hx + dx - 1, hy + dy), (hx + dx + 1, hy + dy), (hx + dx, hy + dy - 1),
                      (hx + dx, hy + dy + 1)}, (255, 250, 180))


def it_hearts(cv, b, f):
    hx, hy, _, _ = b.head
    for i, (dx, dy) in enumerate(((-15, -6), (12, -10), (14, 6))):
        cv.grid(hx + dx, hy + dy - (f + i) % 3, [".a.a", "aaaa", ".aa."], {"a": (255, 90, 140)})


def it_flames(cv, b, f):
    bx, by, brx, bry = b.body
    for i, dx in enumerate(range(-brx - 2, brx + 3, 4)):
        h = 3 + (i + f) % 3
        cv.paint(poly([(bx + dx - 2, by + bry + 1), (bx + dx, by + bry - h), (bx + dx + 2, by + bry + 1)]), (255, 120, 30))
        cv.paint({(bx + dx, by + bry - 1)}, YELLOW)


def it_money_rain(cv, b, f):
    for i in range(7):
        x, y = (i * 7 + 3) % 46, (i * 9 + f * 4) % 40
        cv.part(rect(x, y, x + 2, y + 1), (110, 190, 110), outline=None)


def it_storm(cv, b, f):
    hx, top, _ = _top(b)
    cv.part(ellipse(hx - 2, top - 8, 5, 2.5) | ellipse(hx + 3, top - 9, 4, 3), (110, 110, 130), (90, 90, 110))
    for i in range(3):
        if (i + f) % 2:
            cv.paint({(hx - 4 + i * 4, top - 5), (hx - 5 + i * 4, top - 3)}, (120, 170, 255))


def it_notes(cv, b, f):
    hx, hy, _, _ = b.head
    for i, (dx, dy) in enumerate(((-15, -4), (12, -9))):
        cv.grid(hx + dx, hy + dy - f % 2, [".aa", ".a.", "aa."], {"a": BLACK})


def it_flies(cv, b, f):
    hx, hy, _, _ = b.head
    for i in range(3):
        a = f * 1.4 + i * 2.1
        cv.paint({(int(hx + math.cos(a) * 14), int(hy - 6 + math.sin(a) * 5))}, BLACK)


def it_bars(cv, b, f):  # fg: prison bars over everything
    for x in range(2, cv.w, 6):
        cv.paint(rect(x, 0, x + 1, cv.h - 1), (70, 70, 80))
        cv.paint(rect(x, 0, x, cv.h - 1), (110, 110, 120))


def it_rain(cv, b, f):
    for i in range(18):
        x, y = (i * 11 + f) % cv.w, (i * 7 + f * 5) % cv.h
        cv.paint({(x, y), (x, y + 1)}, (140, 170, 230))


ITEMS: dict[str, tuple[str, str, Callable]] = {
    # head
    "horns": ("😈 Роги", "head", it_horns), "vinok": ("🌺 Вінок", "head", it_vinok), "bow": ("🎀 Бантик", "head", it_bow),
    "wizard": ("🧙 Капелюх мага", "head", it_wizard), "crown": ("👑 Корона", "head", it_crown),
    "cap": ("🧢 Кепка-восьмиклинка", "head", it_cap), "helmet": ("🪖 Каска", "head", it_helmet),
    "chef": ("👨‍🍳 Ковпак кухаря", "head", it_chef), "cowboy": ("🤠 Ковбойський капелюх", "head", it_cowboy),
    "partyhat": ("🥳 Святковий ковпак", "head", it_party), "halo": ("😇 Німб", "head", it_halo),
    "beanie": ("🧶 Шапка з помпоном", "head", it_beanie), "headphones": ("🎧 Навушники", "head", it_headphones),
    "oseledets": ("🪶 Оселедець", "head", it_oseledets), "foil": ("🛸 Шапочка з фольги", "head", it_foil),
    "flower": ("🌸 Квітка за вухом", "head", it_flower),
    # face
    "sunglasses": ("🕶 Окуляри", "face", it_sunglasses), "eyepatch": ("🏴‍☠️ Пов'язка на око", "face", it_eyepatch),
    "scar": ("⚔️ Шрам", "face", it_scar), "monocle": ("🧐 Монокль", "face", it_monocle),
    "nerd": ("🤓 Окуляри ботана", "face", it_nerd), "mustache": ("🥸 Козацькі вуса", "face", it_mustache),
    "clown": ("🤡 Клоунський ніс", "face", it_clown), "mask": ("😷 Маска", "face", it_mask),
    "plaster": ("🩹 Пластир", "face", it_plaster), "tears": ("💧 Тату-сльози", "face", it_tears),
    "vr": ("🥽 VR-окуляри", "face", it_vr),
    # neck
    "chain": ("⛓ Золотий ланцюг", "neck", it_chain), "bib": ("🍼 Слинявчик", "neck", it_bib),
    "bowtie": ("🎀 Метелик", "neck", it_bowtie), "tie": ("👔 Краватка", "neck", it_tie),
    "scarf": ("🇺🇦 Шарф", "neck", it_scarf), "medal": ("🏅 Медаль", "neck", it_medal),
    "bell": ("🔔 Нашийник з дзвіночком", "neck", it_bell), "korali": ("📿 Коралі", "neck", it_korali),
    # outfit
    "vyshyvanka": ("🇺🇦 Вишиванка", "outfit", it_vyshyvanka), "suit": ("🤵 Костюм", "outfit", it_suit),
    "hoodie": ("🧥 Худі", "outfit", it_hoodie), "tracksuit": ("🏃 Спортивка з 3 смужками", "outfit", it_tracksuit),
    "bronik": ("🦺 Бронік", "outfit", it_bronik), "prison": ("🦓 Тюремна роба", "outfit", it_prison),
    "coat": ("🥼 Халат лікаря", "outfit", it_coat), "apron": ("🍳 Фартух", "outfit", it_apron),
    "robe": ("🕯 Мантія сектанта", "outfit", it_robe), "spacesuit": ("👨‍🚀 Скафандр", "outfit", it_spacesuit),
    # back
    "cape": ("🦸 Плащ", "back", it_cape), "angel_wings": ("🪽 Крила ангела", "back", it_angel_wings),
    "bat_wings": ("🦇 Крила кажана", "back", it_bat_wings), "jetpack": ("🚀 Реактивний ранець", "back", it_jetpack),
    "backpack": ("🎒 Рюкзак", "back", it_backpack),
    # held
    "coffee": ("☕ Кава", "held", it_coffee), "mic": ("🎤 Мікрофон", "held", it_mic), "sabre": ("🗡 Шабля", "held", it_sabre),
    "phone": ("📱 Смартфон", "held", it_phone), "bottle": ("🍾 Пляшка", "held", it_bottle),
    "moneybag": ("💰 Мішок грошей", "held", it_moneybag), "book": ("📘 Книга", "held", it_book),
    "flowers": ("💐 Букет", "held", it_flowers), "guitar": ("🎸 Гітара", "held", it_guitar),
    "balloon": ("🎈 Кулька", "held", it_balloon), "cane": ("🦯 Ціпок", "held", it_cane),
    "drone": ("🛩 Дрон", "held", it_drone), "wand": ("🪄 Чарівна паличка", "held", it_wand),
    "laptop": ("💻 Ноутбук", "held", it_laptop), "sausage": ("🌭 Кільце ковбаси", "held", it_sausage),
    "cards": ("🃏 Карти", "held", it_cards),
    # aura
    "sparkles": ("✨ Сяйво", "aura", it_sparkles), "hearts": ("💕 Сердечка", "aura", it_hearts),
    "flames": ("🔥 Полум'я", "aura", it_flames), "money_rain": ("💸 Грошовий дощ", "aura", it_money_rain),
    "storm": ("🌧 Хмаринка депресії", "aura", it_storm), "notes": ("🎵 Ноти", "aura", it_notes),
    "flies": ("🪰 Мухи", "aura", it_flies),
    # foreground
    "bars": ("⛓ Ґрати", "fg", it_bars), "rain": ("🌧 Дощ", "fg", it_rain),
}
SLOTS = ["back", "outfit", "neck", "face", "head", "held", "aura", "fg"]



# --- item colour variants ------------------------------------------------------------------
# "cowboy@6" = cowboy hat recoloured to variant 6. Any item works, so 80 items × 12 tints.

TINTS = [("", None), ("червоний", 0.0), ("помаранчевий", 0.07), ("жовтий", 0.14), ("зелений", 0.33),
         ("бірюзовий", 0.48), ("синій", 0.62), ("фіолетовий", 0.77), ("рожевий", 0.9), ("золотий", "gold"),
         ("чорний", "black"), ("срібний", "silver")]


def _split(item: str) -> tuple[str, int]:
    base, _, var = item.partition("@")
    return base, int(var) if var.isdigit() and int(var) < len(TINTS) else 0


def _item(item: str) -> tuple[str, str, Callable | None]:
    base = _split(item)[0]
    if base.startswith("gen:"):
        return gen_item(base) or ("?", "", None)
    return ITEMS.get(base, ("?", "", None))


def item_name(item: str) -> str:
    base, v = _split(item)
    name = _item(base)[0] if base in ITEMS or base.startswith("gen:") else base
    return f"{name} ({TINTS[v][0]})" if v else name


def item_slot(item: str) -> str:
    return _item(item)[1]


def _tint(c: tuple, mode) -> tuple:
    if c == OUTLINE:
        return c
    h, s, v = colorsys.rgb_to_hsv(*(x / 255 for x in c))
    if mode == "black":
        return hsv(h, s * 0.3, v * 0.3 + 0.05)
    if mode == "silver":
        return hsv(h, 0.04, 0.55 + v * 0.4)
    if s < 0.18:
        return c
    if mode == "gold":
        return hsv(0.13, 0.8, max(v, 0.75))
    return hsv(mode, max(s, 0.5), v)


def _draw_item(cv: Canvas, item: str, b: Body, f: int) -> None:
    _, _, fn = _item(item)
    if not fn:
        return
    v = _split(item)[1]
    if not v:
        fn(cv, b, f)
        return
    tmp = Canvas(cv.w, cv.h, cv.ox)
    tmp.base, tmp.bx = cv.px, 0
    fn(tmp, b, f)
    mode = TINTS[v][1]
    cv.px.update({p: _tint(c, mode) for p, c in tmp.px.items() if cv.px.get(p) != c})


# --- special sprites -----------------------------------------------------------------------
EGG_PATTERNS = ["spots", "stripes", "zigzag", "stars", "hearts", "dots", "two_tone", "speckle", "pysanka", "galaxy",
                "band", "checks"]


def egg(cv: Canvas, lk: Look, f: int) -> None:
    rng = random.Random(lk.genes.seed)
    shell = rng.choice([(250, 244, 226), (230, 240, 255), (255, 236, 236), (236, 255, 236), (245, 235, 255),
                        (255, 248, 210), (220, 230, 240)])
    spot = rng.choice([(255, 150, 170), (120, 170, 255), (250, 180, 60), (150, 110, 220), (90, 190, 120), (230, 80, 80),
                       (60, 160, 170)])
    kind = EGG_PATTERNS[lk.genes.seed % len(EGG_PATTERNS)]
    wob = (0, 1, 0, -1)[f % 4] if lk.egg_cracks else (0, 0, 1, 0)[f % 4]
    cx, cy = 24 + wob, 30
    if kind == "galaxy":
        shell, spot = (50, 40, 90), (255, 250, 200)
    elif kind == "pysanka":
        shell, spot = (200, 40, 40), (250, 220, 80)
    px = ellipse(cx, cy, 9, 11)
    cv.part(px, shell, mix(shell, OUTLINE, 0.18), mix(shell, WHITE, 0.6))
    srng = random.Random(lk.genes.seed + 3)
    sel: set = set()
    if kind in ("spots", "galaxy", "speckle"):
        n, r = {"spots": (6, 1.6), "galaxy": (14, 0.6), "speckle": (22, 0.6)}[kind]
        for _ in range(n):
            x, y = srng.choice(sorted(px))
            sel |= ellipse(x + 0.5, y + 0.5, r, r * 0.9) if r > 1 else {(x, y)}
    elif kind == "stripes":
        sel = {q for q in px if (q[1] - cy) % 5 in (0, 1)}
    elif kind == "zigzag":
        sel = {q for q in px if (q[1] - abs((q[0] % 6) - 3)) % 6 == 0 or (q[1] - abs((q[0] % 6) - 3)) % 6 == 1}
    elif kind == "dots":
        sel = {q for q in px if q[1] % 4 == 0 and (q[0] + q[1] // 2) % 4 == 0}
    elif kind == "two_tone":
        sel = {q for q in px if q[1] > cy + (2 if (q[0] // 2) % 2 else 0)}
    elif kind == "band":
        sel = {q for q in px if abs(q[1] - cy) <= 1}
        sel |= {q for q in px if abs(q[1] - cy) == 3 and q[0] % 2}
    elif kind == "checks":
        sel = {q for q in px if (q[0] // 3 + q[1] // 3) % 2 == 0}
    elif kind in ("stars", "hearts"):
        rows = [".a.", "aaa", ".a."] if kind == "stars" else ["a.a", "aaa", ".a."]
        for x0, y0 in ((cx - 5, cy - 6), (cx + 2, cy - 3), (cx - 4, cy + 3), (cx + 3, cy + 5), (cx - 1, cy - 1)):
            sel |= {(x0 + dx, y0 + dy) for dy, r in enumerate(rows) for dx, ch in enumerate(r) if ch == "a"}
    elif kind == "pysanka":  # band of zigzags and dots, black lines
        sel = {q for q in px if abs(q[1] - cy) <= 3 and (q[1] - cy - abs((q[0] % 4) - 2)) % 4 == 0}
        sel |= {q for q in px if q[1] in (cy - 7, cy + 7) and q[0] % 2 == 0}
        cv.paint({q for q in px if abs(q[1] - cy) in (4, 5)} | {q for q in px if q[0] == cx and abs(q[1] - cy) > 5}, BLACK)
    cv.paint(sel & px, spot)
    if lk.egg_cracks:
        crack = [(cx - 6, cy - 3), (cx - 3, cy - 1), (cx - 1, cy - 4), (cx + 2, cy - 1), (cx + 5, cy - 3)]
        for a, b in zip(crack, crack[1:]):
            cv.paint(line(*a, *b) & px, OUTLINE)
        if lk.egg_cracks > 1:
            cv.paint(line(cx + 1, cy + 2, cx + 4, cy + 6) & px, OUTLINE)


FONT = {"R": ["aa.", "a.a", "aa.", "a.a", "a.a"], "I": ["aaa", ".a.", ".a.", ".a.", "aaa"],
        "P": ["aa.", "a.a", "aa.", "a..", "a.."]}


def grave(cv: Canvas) -> None:
    px = rect(30, 30, 44, 42) | ellipse(37, 30, 7.5, 6)
    cv.part(px, (150, 150, 162), (112, 112, 124), (186, 186, 196))
    for i, ch in enumerate("RIP"):
        cv.grid(32 + i * 4, 29, FONT[ch], {"a": (70, 70, 80)})
    cv.paint(rect(28, 42, 46, 43), (60, 90, 50))


# --- compositing ---------------------------------------------------------------------------

def _shadow(layer: Canvas, cx: float, cy: float, rx: float, ry: float = 1.6) -> None:
    for x, y in ellipse(cx, cy, rx, ry):
        under = layer.get(x, y)
        if under:
            layer.paint({(x, y)}, mix(under, BLACK, 0.28))


def pet_layer(lk: Look, f: int, base: dict | None = None, bx: int = 0) -> tuple[Canvas, Body | None]:
    """The pet alone on a transparent 48x48 layer (+ the Body anchors). `base` = backdrop pixels for translucency."""
    layer = Canvas(N, N)
    layer.base, layer.bx = base, bx
    layer.fg, layer.ghost = [], False
    if lk.stage == 0:
        _shadow(layer, 24, 41, 9)
        egg(layer, lk, f)
        return layer, None
    roles = roles_of(lk)
    if "quantum" in roles and f % 2:
        lk = replace(lk, ghost=True)
    if lk.ghost:
        roles = set()
    items = [] if lk.ghost else [i for i in lk.items if _item(i)[2]]
    by_slot = {s: [i for i in items if _item(i)[1] == s] for s in SLOTS}
    head, body, ex = _geom(lk, f)
    if not lk.ghost:
        _shadow(layer, body[0], body[1] + body[3] + 0.5, body[2] + 1)
    pre = Body(head, body, ex, ellipse(*head), ellipse(*body), palette(lk.genes, lk.role), lk.stage)
    if roles:
        _role_back(layer, roles, pre, f)
    for it in by_slot["back"]:
        _draw_item(layer, it, pre, f)
    b = creature(layer, lk, f, roles)
    for slot in ("neck", "face", "head", "held", "aura"):
        for it in by_slot[slot]:
            _draw_item(layer, it, b, f)
    if roles:
        _role_aura(layer, roles, b, f)
    if lk.dirty:
        it_flies(layer, b, f)
        for x, y in ((b.body[0] - 5, b.body[1] + 2), (b.body[0] + 4, b.body[1] - 1)):
            layer.paint(ellipse(x, y, 1.5, 1), (120, 84, 50))
    if lk.hungry:
        hx, hy, hrx, hry = b.head
        x0, y0 = min(hx + hrx - 1, N - 10), max(0, hy - hry - 9)
        layer.part(rect(x0, y0, x0 + 8, y0 + 6), WHITE)
        layer.paint({(x0 + 1, y0 + 7), (x0 + 1, y0 + 8)}, OUTLINE)
        layer.grid(x0 + 3, y0 + 1, ["..aa", ".aaa", "baa.", "b..."], {"a": (200, 120, 60), "b": (240, 230, 210)})
    layer.fg = by_slot["fg"]
    layer.ghost = lk.ghost
    return layer, b


def draw(cv: Canvas, lk: Look, f: int, mirror: bool = False) -> Body | None:
    """Draw the pet (no background) onto `cv` at its x offset; mirror=True flips it to face left."""
    ox = cv.ox
    layer, b = pet_layer(lk, f, cv.px, ox)
    px = layer.px
    if mirror:
        px = {(N - 1 - x, y): c for (x, y), c in px.items()}
    roles = roles_of(lk)
    under = cv.px
    if "angel" in roles and not lk.ghost and lk.stage:  # soft glow around the silhouette
        ring1 = dilate(px)
        for x, y in ring1 | (dilate(ring1 | set(px)) - set(px)):
            c = under.get((x + ox, y))
            if c and 0 <= x < N:
                under[(x + ox, y)] = mix(c, (255, 250, 214), 0.5 if (x, y) in ring1 else 0.25)
    glitch = "quantum" in roles and not lk.ghost and lk.stage and f % 2 == 0
    ghostly = layer.ghost
    for (x, y), c in px.items():
        if glitch:
            k = (y // 2 + f) % 9
            if k == 0:
                x, c = x + 1, mix(c, (80, 240, 255), 0.3)
            elif k == 5:
                x, c = x - 1, mix(c, (255, 80, 220), 0.3)
        if 0 <= x < N and 0 <= x + ox < cv.w and 0 <= y < cv.h:
            if ghostly:
                bg = under.get((x + ox, y))
                c = mix(bg, c, 0.72) if bg else c
            under[(x + ox, y)] = c
    if lk.ghost:
        grave(cv)
    if layer.fg and b:
        fg = Canvas(N, N)
        fg.base, fg.bx = under, ox
        for it in layer.fg:
            _draw_item(fg, it, b, f)
        for (x, y), c in fg.px.items():
            if 0 <= x < N and 0 <= x + ox < cv.w and 0 <= y < cv.h:
                under[(x + ox, y)] = c
    return b


def frame_canvases(lk: Look, n: int = 4) -> list[Canvas]:
    out = []
    for f in range(n):
        cv = Canvas()
        paint_bg(cv, "cemetery" if lk.ghost else lk.background, f)
        draw(cv, lk, f)
        out.append(cv)
    return out


def frames(lk: Look, n: int = 4) -> list[Image.Image]:
    return [cv.image() for cv in frame_canvases(lk, n)]


def _gif(canvases: list[Canvas], scale: int = SCALE, duration: int = 380) -> bytes:
    """Exact-palette GIF (pixel art has < 256 colours): index at 1:1, then upscale — much faster than RGB quantize."""
    Image = _pil()
    cols = sorted(set().union(*(cv.px.values() for cv in canvases)) | {(0, 0, 0)})
    buf = io.BytesIO()
    if len(cols) > 256:
        fr = [cv.image(scale) for cv in canvases]
        fr[0].save(buf, format="GIF", save_all=True, append_images=fr[1:], duration=duration, loop=0)
        return buf.getvalue()
    idx = {c: i for i, c in enumerate(cols)}
    flat = [v for c in cols for v in c]
    imgs = []
    for cv in canvases:
        data = bytearray([idx[(0, 0, 0)]]) * (cv.w * cv.h)
        for (x, y), c in cv.px.items():
            if 0 <= x < cv.w and 0 <= y < cv.h:
                data[y * cv.w + x] = idx[c]
        im = Image.frombytes("P", (cv.w, cv.h), bytes(data))
        im.putpalette(flat)
        imgs.append(im.resize((cv.w * scale, cv.h * scale), Image.NEAREST))
    imgs[0].save(buf, format="GIF", save_all=True, append_images=imgs[1:], duration=duration, loop=0, optimize=False)
    return buf.getvalue()


def render_gif(lk: Look) -> bytes:
    return _gif(frame_canvases(lk))


def render_png(lk: Look) -> bytes:
    buf = io.BytesIO()
    frames(lk, 1)[0].save(buf, format="PNG")
    return buf.getvalue()


# --- groups --------------------------------------------------------------------------------
BETWEEN = {
    "heart": ([".aa.aa.", "abbabba", "abbbbba", ".abbba.", "..aba..", "...a..."], {"a": OUTLINE, "b": (240, 60, 100)}),
    "broken": ([".aa.aa.", "abb.bba", "abba.ba", ".ab.ba.", "..a.a..", "...a..."], {"a": OUTLINE, "b": (170, 60, 90)}),
    "fight": (["...aa..", "..aba..", ".abba..", "abbbbba", "..abba.", "..aba..", "..aa..."], {"a": OUTLINE, "b": YELLOW}),
    "chat": (["aaaaaaa", "abbbbba", "abcbcba", "abbbbba", "aaaaaaa", ".aa....", "a......"],
             {"a": OUTLINE, "b": WHITE, "c": OUTLINE}),
    "gift": (["..a.a..", "aaaaaaa", "abbcbba", "aaaaaaa", ".abcba.", ".abcba.", ".aaaaa."],
             {"a": OUTLINE, "b": (220, 60, 80), "c": YELLOW}),
    "music": (["...aaa", "...a.a", "...a.a", ".aaa.a", "aaaaaa", ".a.aa."], {"a": OUTLINE}),
}
ROW_STEP = 40  # vertical offset between rows in a zoo (front rows overlap back rows' feet a little)


def _group_canvases(looks: list[Look], background: str, per_row: int, between: str, frames_n: int) -> tuple[list, list]:
    n = max(1, len(looks))
    cols = min(per_row, n)
    rows = math.ceil(n / cols)
    pair = n == 2 and per_row >= 2
    step = 44 if pair else 40
    stagger = step // 2 if rows > 1 else 0
    w = cols * step + 8 + stagger
    h = N + (rows - 1) * ROW_STEP
    out, anchors = [], []
    for f in range(frames_n):
        cv = Canvas(w, h)
        top = Canvas(w, N)
        paint_bg(top, background, f)
        cv.px.update(top.px)
        for y in range(N, h):  # extend the floor/ground downwards
            src = N - 8 + (y - N) % 8
            for x in range(w):
                cv.px[(x, y)] = top.px[(x, src)]
        anchors = []
        for r in range(rows):
            row = looks[r * cols:(r + 1) * cols]
            shift = (cols - len(row)) * step // 2 + (stagger if r % 2 else 0)  # stagger rows, centre a short one
            for c, lk in enumerate(row):
                sub = Canvas(w, N, c * step - 4 + shift + (2 if pair else 0) + (4 if cols == 1 else 0))
                y0 = r * ROW_STEP
                sub.px = {(x, y - y0): col for (x, y), col in cv.px.items() if y0 <= y < y0 + N}
                mirror = c < (len(row) - 1) / 2
                b = draw(sub, lk, f, mirror=mirror)
                for (x, y), col in sub.px.items():
                    cv.px[(x, y + y0)] = col
                hd = b.head if b else (24, 30, 9, 11)
                anchors.append((sub.ox + (N - 1 - hd[0] if mirror else hd[0]), y0 + hd[1] - hd[3], y0 + hd[1], r, c))
        if between in BETWEEN:
            rows_g, colors = BETWEEN[between]
            for a, b2 in zip(anchors, anchors[1:]):
                if a[3] != b2[3]:
                    continue
                x = (a[0] + b2[0]) // 2 - len(rows_g[0]) // 2
                y = min(a[2], b2[2]) - 7 + (f % 2 if between != "fight" else 0)
                cv.grid(x, y + 1, rows_g, colors)
                if between == "fight" and f % 2:
                    cv.paint({(x - 2, y + 2), (x + 8, y + 5), (x - 1, y + 7), (x + 8, y)}, (255, 240, 120))
        out.append(cv)
    return out, anchors


def _labels(img: Image.Image, anchors: list, labels: list[str], scale: int) -> None:
    font = _font(max(12, scale * 2))
    if not font:
        return
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    for (x, _, hy, r, _), text in zip(anchors, labels):
        if not text:
            continue
        cx, y = x * scale, (r * ROW_STEP + N - 3) * scale
        d.text((cx, y), text[:14], font=font, fill=(255, 255, 255), anchor="ms", stroke_width=max(2, scale // 3),
               stroke_fill=OUTLINE)


_FONT_CACHE: dict = {}


def _font(size: int):
    if size not in _FONT_CACHE:
        try:
            from PIL import ImageFont
            _FONT_CACHE[size] = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
        except OSError:
            _FONT_CACHE[size] = None
    return _FONT_CACHE[size]


def render_group(looks: list[Look], background: str = "meadow", per_row: int = 4, between: str = "",
                 labels: list[str] | None = None, gif: bool = False) -> bytes:
    """Several pets in one scene (social events, zoo).

    Pets on the left half face right (mirrored), so two pets face each other. `between` draws a marker between
    neighbours: heart | broken | fight | chat | gift | music. `labels` puts names under pets. gif=True → animated GIF.
    """
    canvases, anchors = _group_canvases(looks, background, per_row, between, 4 if gif else 1)
    if gif and not labels:
        return _gif(canvases)
    imgs = [cv.image() for cv in canvases]
    for im in imgs:
        if labels:
            _labels(im, anchors, labels, SCALE)
    buf = io.BytesIO()
    if gif:
        imgs[0].save(buf, format="GIF", save_all=True, append_images=imgs[1:], duration=380, loop=0)
    else:
        imgs[0].save(buf, format="PNG")
    return buf.getvalue()
