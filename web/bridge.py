"""Browser bridge: what the page's JavaScript calls inside Pyodide.

Same game as `kit-the-cat`: the sandbox API (kit_the_cat.sandbox.api) over an in-memory database that the page
saves to the viewer's browser. Images are returned as raw RGB frames; the page draws them on <canvas>.
"""
import json
from collections import OrderedDict

from kit_the_cat import engine as E
from kit_the_cat import sprites
from kit_the_cat.sandbox import api
from kit_the_cat.sandbox.game import SANDBOX, Sandbox
from kit_the_cat.storage import MemoryStore

DB = MemoryStore()
SB = Sandbox(DB)
_cache: OrderedDict = OrderedDict()


async def boot(saved: str = "") -> bool:
    restored = bool(saved) and DB.load(saved)
    await SB.init()
    return restored


async def call(kind: str, owner: int, body: str = "{}") -> str:
    """kind: state | lists | tour | do. Returns JSON (same shapes as the HTTP sandbox)."""
    owner = owner if owner in (1, 2, 3) else 1
    if kind == "state":
        out = await SB.view(owner)
    elif kind == "lists":
        out = await api.lists(SB, owner)
    elif kind == "tour":
        out = await SB.tour_view(owner)
    elif kind == "do":
        try:
            out = await api.dispatch(SB, owner, json.loads(body or "{}"))
        except api.UnknownAction as e:
            out = dict(message=f"Невідома дія: {e}")
    else:
        out = dict(error=kind)
    return json.dumps(out, ensure_ascii=False)


def dump() -> str:
    return DB.dump()


# --- pixels ------------------------------------------------------------------------------------

def _rgb(cv) -> bytes:
    w, h = cv.w, cv.h
    data = bytearray(w * h * 3)
    for (x, y), c in cv.px.items():
        if 0 <= x < w and 0 <= y < h:
            i = (y * w + x) * 3
            data[i], data[i + 1], data[i + 2] = c[0], c[1], c[2]
    return bytes(data)


def _pack(canvases, labels=None) -> dict:
    return dict(w=canvases[0].w, h=canvases[0].h, frames=[_rgb(cv) for cv in canvases], labels=labels or [])


def _cached(key: str, make):
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key]
    v = make()
    _cache[key] = v
    if len(_cache) > 48:
        _cache.popitem(last=False)
    return v


async def pet_frames(owner: int):
    p = await SB.pet(owner, tick=False)
    if not p:
        return None
    look = p.look()
    return _cached("p" + repr(look), lambda: _pack(sprites.frame_canvases(look, 4)))


async def event_frames(owner: int):
    pets = await SB.pets(tick=False)
    p = next((x for x in pets if x.owner_id == owner), None)
    e = E.EVENTS.get(p.pending.get("id", "")) if p and p.pending else None
    if not e:
        return None
    bg = e.bg if E.bg_ok(e.bg) else ""
    other = next((x for x in pets if x.pid == p.pending.get("other")), None)
    if not other:
        look = p.look(bg)
        return _cached("e" + repr(look), lambda: _pack(sprites.frame_canvases(look, 4)))
    bgx = E.scene(bg or p.home, p.flags)
    st = p.status.get(other.pid, "")
    between = ("heart" if st in ("crush", "partner") else "fight" if st in ("rival", "enemy")
               else "broken" if st == "ex" else "chat")
    looks = [p.look(bgx), other.look(bgx)]
    return _group(looks, bgx if E.bg_ok(bgx) else "meadow", 2, between)


async def fight_frames(a: int, b: int):
    pets = {p.owner_id: p for p in await SB.pets(tick=False)}
    if a not in pets or b not in pets:
        return None
    return _group([pets[a].look("club"), pets[b].look("club")], "club", 2, "fight")


async def zoo_frames():
    pets = [p for p in await SB.pets(tick=False) if p.state != "dead"][:12]
    if not pets:
        return None
    return _group([p.look() for p in pets], "meadow", 4, "", [p.name[:14] for p in pets])


def _group(looks, bg: str, per_row: int, between: str, names=None):
    def make():
        canvases, anchors = sprites._group_canvases(looks, bg, per_row, between, 4)
        labels = []
        if names:
            for (x, _top, _cy, r, _c), name in zip(anchors, names):
                labels.append([name, x, r * sprites.ROW_STEP + sprites.N - 2])
        return _pack(canvases, labels)
    return _cached("g" + repr((looks, bg, per_row, between, names)), make)


def sandbox_chat() -> int:
    return SANDBOX
