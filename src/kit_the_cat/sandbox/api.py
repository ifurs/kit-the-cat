"""Transport-free sandbox API: the local web server (server.py) and the in-browser build (web/bridge.py)
both call these, so the game behaves the same over HTTP and inside Pyodide."""
from .game import HUMANS, Sandbox


class UnknownAction(ValueError):
    pass


async def lists(sb: Sandbox, o: int) -> dict:
    p = await sb.pet(o, tick=False)
    return dict(foods=sb.foods(p.role if p else ""), wardrobe=await sb.wardrobe(o), stock=sb.stock(),
                homes=await sb.homes(o), jobs=await sb.jobs(o), humans=HUMANS)


async def dispatch(sb: Sandbox, o: int, b: dict) -> dict:
    """One player action. Returns {message}, {result} (adventure outcome) or {battle}."""
    a = b.get("action", "")
    x = b.get("x")
    if a == "create":
        msg = await sb.create(o, str(x))
    elif a == "heir":
        msg = await sb.heir(o)
    elif a == "care":
        msg = await sb.care(int(b.get("owner") or o), str(x), actor_id=o)
    elif a == "feed":
        msg = await sb.feed(o, str(x))
    elif a == "casino":
        msg = await sb.casino(o, str(x), int(b.get("stake") or 0))
    elif a == "adventure":
        msg = await sb.adventure(o, str(b.get("kind", "")), int(b.get("with") or 0))
    elif a == "choose":
        return dict(result=await sb.choose(o, None if x is None else int(x)))
    elif a == "equip":
        msg = await sb.equip(o, int(x))
    elif a == "buy":
        msg = await sb.buy(o, int(x))
    elif a == "move":
        msg = await sb.move(o, int(x))
    elif a == "job":
        msg = await sb.apply_job(o, str(x))
    elif a == "quit":
        msg = await sb.quit_job(o)
    elif a == "rename":
        msg = await sb.rename(o, str(x))
    elif a == "npcs":
        msg = await sb.add_npcs(max(1, min(int(x or 3), 30)))
    elif a == "world":
        msg = await sb.world(str(x or ""))
    elif a == "claim":
        msg = await sb.claim(o)
    elif a == "advance":
        s = await sb.advance(max(1.0, min(float(x or 1), 24 * 60)), bool(b.get("auto", True)), bool(b.get("care")))
        parts = [f"⏩ +{s['hours']} год. гри", f"подій у сусідів: {s['events']}"]
        parts += [f"🌍 {w}" for w in s["world"]] + [f"⚰️ {d}" for d in s["deaths"]]
        msg = "\n".join(parts)
    elif a == "spar":
        return dict(battle=await sb.spar(o, int(b.get("with") or 0), str(x or "careful")))
    elif a == "t_new":
        msg = await sb.tour_new()
    elif a == "t_strategy":
        msg = await sb.tour_strategy(o, str(x))
    elif a == "t_bet":
        msg = await sb.tour_bet(o, str(b.get("key", "")), int(x or 0), max(10, min(int(b.get("amount") or 50), 5000)))
    elif a == "t_next":
        return dict(battle=await sb.tour_next())
    elif a == "reset":
        msg = await sb.reset()
    else:
        raise UnknownAction(a)
    return dict(message=msg)
