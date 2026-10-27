"""Local web sandbox for the pet game:  uv run kit-the-cat  → http://127.0.0.1:8777

No Telegram, no tokens. The game is saved to a JSON file (play.json) after every action.
Binds to localhost only: this is a test tool, not a public server.
"""
import argparse
import logging
from pathlib import Path

from aiohttp import web

from ..storage import MemoryStore
from . import api
from .game import HUMANS, Sandbox

STATIC = Path(__file__).parent / "static"
log = logging.getLogger("kit_the_cat.sandbox")


def _owner(req: web.Request) -> int:
    try:
        o = int(req.query.get("as", "1"))
    except ValueError:
        o = 1
    return o if o in HUMANS else 1


async def _body(req: web.Request) -> dict:
    try:
        return await req.json()
    except Exception:
        return {}


def routes(sb: Sandbox, save=lambda: None) -> web.RouteTableDef:
    r = web.RouteTableDef()

    @r.get("/")
    async def index(req):
        return web.FileResponse(STATIC / "index.html")

    @r.get("/api/state")
    async def state(req):
        return web.json_response(await sb.view(_owner(req)))

    @r.get("/api/lists")
    async def lists(req):
        return web.json_response(await api.lists(sb, _owner(req)))

    @r.post("/api/do")
    async def do(req):
        try:
            out = await api.dispatch(sb, _owner(req), await _body(req))
            save()
            return web.json_response(out)
        except api.UnknownAction:
            raise web.HTTPBadRequest(text="unknown action")

    @r.get("/api/tour")
    async def tour(req):
        return web.json_response(await sb.tour_view(_owner(req)))

    @r.get("/img/fight/{a}/{b}.png")
    async def fight_png(req):
        data = await sb.fight_png(int(req.match_info["a"]), int(req.match_info["b"]))
        if not data:
            raise web.HTTPNotFound()
        return web.Response(body=data, content_type="image/png", headers={"Cache-Control": "no-store"})

    @r.get("/img/pet/{owner}.gif")
    async def pet_gif(req):
        data = await sb.pet_gif(int(req.match_info["owner"]))
        if not data:
            raise web.HTTPNotFound()
        return web.Response(body=data, content_type="image/gif", headers={"Cache-Control": "no-store"})

    @r.get("/img/event/{owner}.png")
    async def event_png(req):
        data = await sb.event_png(int(req.match_info["owner"]))
        if not data:
            raise web.HTTPNotFound()
        return web.Response(body=data, content_type="image/png", headers={"Cache-Control": "no-store"})

    @r.get("/img/zoo.png")
    async def zoo(req):
        data = await sb.zoo_png()
        if not data:
            raise web.HTTPNotFound()
        return web.Response(body=data, content_type="image/png", headers={"Cache-Control": "no-store"})

    return r


async def make_app(save_path: str | None = "play.json", seed: int | None = None) -> web.Application:
    """save_path=None keeps the game in memory only (tests)."""
    store = MemoryStore()
    path = Path(save_path) if save_path else None
    if path and path.exists():
        store.load(path.read_text())
    sb = Sandbox(store, seed)
    await sb.init()

    def save() -> None:
        if path:
            tmp = path.with_suffix(".tmp")
            tmp.write_text(store.dump())
            tmp.replace(path)  # atomic: a crash mid-write never corrupts the save

    app = web.Application()
    app.add_routes(routes(sb, save))
    return app


def main() -> None:
    ap = argparse.ArgumentParser(description="Кошеня: пісочниця тамагочі без Telegram")
    ap.add_argument("--port", type=int, default=8777)
    ap.add_argument("--save", default="play.json", help="save file (JSON)")
    ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    print(f"🐾 Пісочниця: http://127.0.0.1:{a.port}")
    web.run_app(make_app(a.save, a.seed), host="127.0.0.1", port=a.port, print=None)


if __name__ == "__main__":
    main()
