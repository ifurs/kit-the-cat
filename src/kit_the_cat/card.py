"""The life card: a whole life on one picture (PNG), for the end of a pet's story.

    png = card.render_life_card(pet.look(), engine.life_summary(pet, names))

Pure stdlib: the text is a baked bitmap font (cardfont.py), the picture is a pixel-art scene (sprites.py), the PNG is
encoded with zlib. So the Telegram bot and the browser build (Pyodide, no Pillow) draw exactly the same card.
"""
import re
import struct
import zlib

from . import cardfont, sprites
from .sprites_core import Canvas

W, SCALE = 264, 3            # logical width and the zoom of every logical pixel (264 × 3 = 792 px wide)
MARGIN = 12
FW, FH = cardfont.CELL_W, cardfont.CELL_H
COLS = (W - 2 * MARGIN) // FW  # characters per line
MAX_STORY, STORY_LINES = 6, 3  # highlights shown, lines per highlight

BG, BG2 = (22, 20, 40), (30, 27, 54)
INK, DIM, GOLD, RED, PINK = (238, 230, 205), (150, 142, 175), (255, 205, 90), (240, 110, 105), (240, 120, 160)
FRAME = (92, 78, 140)

ICONS = {  # 7×7 pixel pictures: a = the icon's colour, b = a second tone
    "cal": ([".a...a.", "aaaaaaa", "a.....a", "a.b.b.a", "a.....a", "a.b.b.a", "aaaaaaa"], dict(a=(120, 190, 255), b=INK)),
    "dice": (["aaaaaaa", "ab...ba", "a..b..a", "a.....a", "a..b..a", "ab...ba", "aaaaaaa"], dict(a=INK, b=(120, 190, 255))),
    "coin": ([".aaaaa.", "abbbbba", "abb.bba", "abbabba", "abb.bba", "abbbbba", ".aaaaa."], dict(a=GOLD, b=(255, 232, 140))),
    "star": (["...a...", "...a...", "aaaaaaa", ".aaaaa.", "..aaa..", ".aa.aa.", ".a...a."], dict(a=GOLD)),
    "cup": (["aaaaaaa", "a.aaa.a", "a.aaa.a", ".aaaaa.", "..aaa..", "...a...", ".aaaaa."], dict(a=GOLD)),
    "heart": ([".aa.aa.", "aaaaaaa", "aaaaaaa", ".aaaaa.", "..aaa..", "...a...", "......."], dict(a=PINK)),
    "egg": (["..aaa..", ".aaaaa.", ".aaaaa.", "aaaaaaa", "aaaaaaa", ".aaaaa.", "..aaa.."], dict(a=INK)),
    "swords": (["a.....a", ".a...a.", "..a.a..", "...a...", "..a.a..", ".a...a.", "a.....a"], dict(a=(190, 190, 205))),
    "cross": (["...a...", "...a...", ".aaaaa.", "...a...", "...a...", "...a...", "...a..."], dict(a=DIM)),
    "crown": (["a..a..a", "aa.a.aa", "aaaaaaa", "aaaaaaa", ".aaaaa.", ".......", "......."], dict(a=GOLD)),
    "book": ([".aaaaa.", "abbbbba", "abbbbba", "abbbbba", "abbbbba", "aaaaaaa", "......."], dict(a=(190, 140, 90), b=INK)),
    "dot": (["...a...", "..aaa..", ".aaaaa.", "..aaa..", "...a...", ".......", "......."], dict(a=DIM)),
}
EMOJI_ICON = {"📅": "cal", "🎲": "dice", "💰": "coin", "🌟": "star", "🎯": "star", "🏆": "cup", "🫂": "heart", "💍": "heart",
              "🥚": "egg", "🤝": "heart", "⚔": "swords", "💔": "heart", "👑": "crown", "🪦": "cross", "⚰": "cross"}
SAYS = {"№": "N", "₴": "грн", "\u202f": " ", "ʼ": "'", "`": "'", "→": "-", "²": "2", "³": "3"}
NBSP = "\u00a0"  # keeps «5 822 грн» in one piece; drawn as a space


def clean(s: str) -> str:
    """Only what the font can draw: emoji and other symbols go, «№» and «₴» get letters, «17✅ 2❌» is spelled out."""
    s = re.sub(r"(\d+)✅\s*(\d+)❌", r"\1 вдало / \2 невдало", s)
    s = re.sub(r"(?<=\d) (?=\d{3}\b)", NBSP, s)
    out = []
    for ch in s:
        ch = SAYS.get(ch, ch)
        out.append(ch if all(ord(c) in cardfont.GLYPHS or c == NBSP for c in ch) else "")
    return " ".join("".join(out).split(" ")).strip()


def lead_icon(s: str) -> tuple[str, str]:
    """('«📅 12 років»' -> ('cal', '12 років')): a leading emoji becomes a pixel icon, any other symbol a dot."""
    head, _, rest = s.partition(" ")
    if rest and not clean(head) and head:
        return EMOJI_ICON.get(head.rstrip("\ufe0f"), "dot"), rest
    return "", s


def wrap(s: str, cols: int) -> list[str]:
    lines, cur = [], ""
    for word in s.split(" "):
        if not word:
            continue
        while len(word) > cols:  # a very long word breaks at the edge
            head, word = word[:cols - 1] + "-", word[cols - 1:]
            lines.append(cur) if cur else None
            cur = ""
            lines.append(head)
        if not cur:
            cur = word
        elif len(cur) + 1 + len(word) <= cols:
            cur += " " + word
        else:
            lines.append(cur)
            cur = word
    return lines + ([cur] if cur else [])


def fit(s: str, cols: int, max_lines: int) -> list[str]:
    """wrap(), but at most max_lines: the last one loses whole words and ends with «…»."""
    lines = wrap(s, cols)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        while len(lines[-1]) > cols - 1 and " " in lines[-1]:
            lines[-1] = lines[-1].rsplit(" ", 1)[0]
        lines[-1] = lines[-1][:cols - 1].rstrip(" ,.;:-—") + "…"
    return lines


_rows: dict[str, list[int]] = {}


def glyph(ch: str) -> list[int]:
    if ch not in _rows:
        hx = cardfont.GLYPHS.get(ord(ch), "")
        d = (FW + 3) // 4
        _rows[ch] = [int(hx[i * d:(i + 1) * d], 16) for i in range(FH)] if hx else [0] * FH
    return _rows[ch]


class Sheet:
    """A growing page in logical pixels with a cursor (y); pixels are a sparse dict like sprites.Canvas.px."""

    def __init__(self) -> None:
        self.px: dict[tuple[int, int], tuple] = {}
        self.y = MARGIN

    def put(self, x: int, y: int, color: tuple, w: int = 1, h: int = 1) -> None:
        for dy in range(h):
            for dx in range(w):
                self.px[(x + dx, y + dy)] = color

    def text(self, x: int, y: int, s: str, color: tuple, zoom: int = 1, shadow: tuple | None = (12, 10, 24)) -> None:
        for col, off in ([(shadow, 1)] if shadow else []) + [(color, 0)]:
            for i, ch in enumerate(s):
                for r, bits in enumerate(glyph(ch)):
                    for b in range(FW):
                        if bits >> (FW - 1 - b) & 1:
                            self.put(x + (i * FW + b) * zoom + off, y + r * zoom + off, col, zoom, zoom)

    def centered(self, s: str, color: tuple, zoom: int = 1) -> None:
        self.text((W - len(s) * FW * zoom) // 2, self.y, s, color, zoom)
        self.y += FH * zoom + 2

    def icon(self, name: str, x: int, y: int) -> None:
        rows, colors = ICONS[name]
        for dy, line in enumerate(rows):
            for dx, ch in enumerate(line):
                if ch != ".":
                    self.px[(x + dx, y + dy)] = colors[ch]

    def rule(self, color: tuple = FRAME) -> None:
        self.y += 3
        self.put(MARGIN, self.y, color, W - 2 * MARGIN)
        self.y += 5

    def heading(self, s: str) -> None:
        w = len(s) * FW
        x = (W - w) // 2
        self.text(x, self.y, s, GOLD)
        mid = self.y + FH // 2
        self.put(MARGIN, mid, FRAME, x - MARGIN - 4)
        self.put(x + w + 4, mid, FRAME, W - MARGIN - (x + w + 4))
        self.y += FH + 4

    def item(self, s: str, icon: str, color: tuple = INK, max_lines: int = 99) -> None:
        """A paragraph with a pixel icon (or a dot) to the left; the text wraps inside the card."""
        indent = 10
        lines = fit(s, (W - 2 * MARGIN - indent) // FW, max_lines)
        if icon == "bullet":
            self.put(MARGIN + 2, self.y + 5, GOLD, 2, 2)
        elif icon:
            self.icon(icon, MARGIN, self.y + 2)
        for line in lines:
            self.text(MARGIN + indent, self.y, line, color)
            self.y += FH
        self.y += 3


def banner(look: "sprites.Look") -> Canvas:
    """The pet on its scene, as wide as the card."""
    cv = Canvas(W, sprites.N, (W - sprites.N) // 2)
    sprites.paint_bg(cv, "cemetery" if look.ghost else look.background, 0)
    sprites.draw(cv, look, 0)
    return cv


def render_life_card(look: "sprites.Look", summary: dict, footer: str = "kit-the-cat") -> bytes:
    """PNG of a life: portrait, name and title, cause, facts, highlights, family, epitaph.

    `summary` is engine.life_summary(pet, names). `footer` is a line under the card (the bot's name, say)."""
    sh = Sheet()
    top = banner(look)
    sh.px.update({(x, y + 4): c for (x, y), c in top.px.items() if 0 <= x < W and 0 <= y < top.h})
    sh.y = sprites.N + 4 + 8
    name = clean(summary["name"])
    zoom = 2 if len(name) * FW * 2 <= W - 2 * MARGIN else 1
    sh.centered(name, INK, zoom)
    for line in fit(clean(summary["title"]), COLS, 3):
        sh.centered(line, GOLD)
    cause = clean(summary.get("cause", ""))
    if cause:
        sh.y += 2
        lines = fit(cause[:1].upper() + cause[1:], COLS - 2, 3)
        sh.icon("cross", MARGIN, sh.y + 2)
        for line in lines:
            sh.text(MARGIN + 10, sh.y, line, RED)
            sh.y += FH
    sh.rule()
    for fact in summary.get("facts", []):
        icon, text = lead_icon(fact)
        text = clean(text)
        if text:
            sh.item(text, icon or "dot")
    story = [clean(x) for x in summary.get("story", [])]
    story = [x for x in story if x]
    if len(story) > MAX_STORY:  # the first moment stays, then the latest
        story = story[:1] + story[-(MAX_STORY - 1):]
    if story:
        sh.rule()
        sh.heading("НАЙЯСКРАВІШЕ")
        for x in story:
            sh.item(x, "bullet", max_lines=STORY_LINES)
    family = clean(summary.get("family", ""))
    if family:
        sh.rule()
        sh.item(family, "heart")
    epitaph = clean(summary.get("epitaph", ""))
    if epitaph:
        sh.rule()
        for line in fit("«" + epitaph + "»", COLS, 4):
            sh.centered(line, DIM)
    if footer:
        sh.y += 4
        sh.centered(clean(footer), FRAME)
    h = sh.y + MARGIN - 4
    return png(sh.px, W, h, BG, border=True)


def png(px: dict, w: int, h: int, bg: tuple, border: bool = False, scale: int = SCALE) -> bytes:
    """Encode a sparse pixel dict (logical pixels, zoomed `scale` times) as PNG; palette when it fits, else RGB."""
    grid = [[bg] * w for _ in range(h)]
    for (x, y), c in px.items():
        if 0 <= x < w and 0 <= y < h:
            grid[y][x] = c
    if border:  # a two-tone frame over anything that spilled
        for y in range(h):
            for x in range(w):
                m = min(x, y, w - 1 - x, h - 1 - y)
                if m < 3:
                    grid[y][x] = FRAME if m == 1 else BG2
    colors = sorted({c for row in grid for c in row})
    if len(colors) <= 256:
        idx = {c: i for i, c in enumerate(colors)}
        rows = [bytes(idx[c] for c in row) for row in grid]
        kind, bpp, plte = 3, 1, b"".join(bytes(c) for c in colors)
    else:
        rows = [b"".join(bytes(c) for c in row) for row in grid]
        kind, bpp, plte = 2, 3, b""
    raw = bytearray()
    for row in rows:
        zoomed = b"".join(row[i * bpp:(i + 1) * bpp] * scale for i in range(w))
        raw += (b"\x00" + zoomed) * scale

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))
    head = struct.pack(">IIBBBBB", w * scale, h * scale, 8, kind, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", head) + (chunk(b"PLTE", plte) if plte else b"")
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))
