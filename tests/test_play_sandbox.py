"""The standalone sandbox (kit-the-cat): a whole life without Telegram, through the HTTP API."""
from urllib.parse import quote

import pytest
import pytest_asyncio
from aiohttp.test_utils import TestClient, TestServer

from kit_the_cat import engine as E
from kit_the_cat.sandbox.server import make_app

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def client(tmp_path):
    old = E.clock
    app = await make_app(str(tmp_path / "play.json"), seed=7)
    async with TestClient(TestServer(app)) as c:
        yield c
    E.clock = old


async def do(c, action, x=None, who=1, **kw):
    r = await c.post(f"/api/do?as={who}", json=dict(action=action, x=x, **kw))
    assert r.status == 200, await r.text()
    return await r.json()


async def ready_for_tournament(c, need: int) -> None:
    """Grow everyone into teens; wait out hospital/jail stays (they depend on the real time of day)."""
    await do(c, "advance", 24 * E.STAGE_YEARS[2] / E.YEARS_PER_DAY[1] + 6, care=True)  # all of childhood
    for _ in range(16):
        if (await (await c.get("/api/tour?as=1")).json())["eligible"] >= need:
            return
        await do(c, "advance", 6, care=True)


async def state(c, who=1):
    r = await c.get(f"/api/state?as={who}")
    assert r.status == 200
    return await r.json()


async def test_page_and_empty_state(client):
    r = await client.get("/")
    assert r.status == 200 and "Пісочниця" in await r.text()
    s = await state(client)
    assert s["pet"] is None and len(s["species"]) == 7


async def test_a_life(client):
    await do(client, "create", "fox")
    assert (await state(client))["pet"]["state"] == "egg"
    await do(client, "advance", 2)
    s = await state(client)
    assert s["pet"]["state"] == "alive"
    gif = await client.get("/img/pet/1.gif")
    assert gif.status == 200 and (await gif.read())[:3] == b"GIF"

    await do(client, "npcs", 3)
    fed = (await do(client, "feed", "crust"))["message"]
    assert "з'їв" in fed or "з'їла" in fed
    await do(client, "care", "play")
    await do(client, "adventure")
    s = await state(client)
    ev = s["pet"]["pending"]
    assert ev and ev["choices"]
    assert (await client.get("/img/event/1.png")).status == 200
    res = (await do(client, "choose", ev["choices"][0]["i"]))["result"]
    assert res["label"] and "error" not in res
    for _ in range(6):  # a story (several decisions in a row) goes on right away
        nxt = (await state(client))["pet"]["pending"]
        if not nxt:
            break
        res = (await do(client, "choose", nxt["choices"][0]["i"]))["result"]
    assert (await state(client))["pet"]["pending"] is None

    await do(client, "world", "meteor")
    s = await state(client)
    assert s["world"] and s["world"]["title"]
    await do(client, "claim")
    lists = await (await client.get("/api/lists?as=1")).json()
    assert lists["stock"] and lists["foods"]
    await do(client, "advance", 24 * 7, care=True)  # a week on autopilot: salaries, NPC lives, ageing
    s = await state(client)
    assert s["offset_days"] >= 7
    assert len(s["journal"]) > 5
    assert (await client.get("/img/zoo.png")).status == 200


async def test_two_humans_can_meet(client):
    await do(client, "create", "cat", who=1)
    await do(client, "create", "dog", who=2)
    await do(client, "advance", 24 * 5, care=True)  # both grow up a bit
    s1 = await state(client, 1)
    if s1["pet"]["pending"]:
        await do(client, "choose", None, who=1)
    await do(client, "advance", 1)
    s1 = await state(client, 1)
    assert s1["pet"]["state"] == "alive", "autopilot care should keep the pet alive"
    if s1["pet"]["pending"]:
        await do(client, "choose", None, who=1)
    msg = (await do(client, "adventure", None, kind="fight", **{"with": 2}))["message"]
    s1 = await state(client, 1)
    assert s1["pet"]["pending"] and s1["pet"]["pending"]["other"], msg


async def test_reset(client):
    await do(client, "create", "pig")
    await do(client, "reset")
    assert (await state(client))["pet"] is None


async def test_tournament(client):
    await do(client, "create", "horse")
    await do(client, "npcs", 6)
    await ready_for_tournament(client, 3)
    t = await (await client.get("/api/tour?as=1")).json()
    assert t["eligible"] >= 3
    assert "Турнір на" in (await do(client, "t_new"))["message"]
    await do(client, "t_strategy", "aggressive")
    t = await (await client.get("/api/tour?as=1")).json()
    assert t["tour"]["status"] == "running" and t["my_strategy"] == "aggressive"
    battles, champion = 0, None
    for _ in range(40):
        t = await (await client.get("/api/tour?as=1")).json()
        cur = t["tour"]["current"]
        money = (await state(client))["pet"]["money"]
        if cur and 1 not in (cur["a"]["owner"], cur["b"]["owner"]) and not battles and money >= 20:
            msg = (await do(client, "t_bet", 0, key=cur["key"], amount=20))["message"]
            assert "Ставка" in msg, msg
        b = (await do(client, "t_next"))["battle"]
        assert "error" not in b, b
        if b.get("log"):
            battles += 1
            assert b["log"][-1]["text"].startswith("🏆")
            assert b["winner"] in b["owners"]
            img = await client.get(f"/img/fight/{b['owners'][0]}/{b['owners'][1]}.png")
            assert img.status == 200
        if b.get("champion") or b.get("done"):
            champion = b.get("champion")
            break
    assert champion and battles >= 3
    t = await (await client.get("/api/tour?as=1")).json()
    assert t["tour"]["status"] == "done" and t["history"]
    s = await state(client)
    champ_pet_journal = [p for p in s["players"] if p["owner"] == champion["owner"]]
    assert champ_pet_journal and champ_pet_journal[0]["state"] == "alive"  # battles are never lethal


async def test_spar(client):
    await do(client, "create", "pig")
    await do(client, "npcs", 1)
    await ready_for_tournament(client, 2)
    s = await state(client)
    foe = next(p["owner"] for p in s["players"] if p["npc"])
    b = (await do(client, "spar", **{"with": foe}))["battle"]
    assert "error" not in b and b["paused"] and b["duel"] and b["round"] == 1 and b["tell"]
    assert [m["key"] for m in b["moves"]][:3] == ["strike", "guard", "trick"] and all(m["power"] > 0 for m in b["moves"][:3])
    fid, seen = b["fight"], len(b["log"])
    for _ in range(b["rounds"] + 1):   # play it out: every answer carries only the new lines
        b = (await do(client, "spar_move", "strike", fight=fid))["battle"]
        assert "error" not in b and b["from"] == seen and b["log"]
        seen += len(b["log"])
        if not b.get("paused"):
            break
    assert b["winner"] and b["rec"] and b["log"][-1]["text"].startswith("🏆") and b["rounds"] <= 7


@pytest.mark.parametrize("npcs", [2, 4, 6])  # 3, 5, 7 fighters: brackets with byes
async def test_tournament_with_byes_never_stalls(client, npcs):
    await do(client, "create", "cat")
    await do(client, "npcs", npcs)
    await ready_for_tournament(client, npcs + 1)
    assert "Турнір на" in (await do(client, "t_new"))["message"]
    for _ in range(20):
        t = (await (await client.get("/api/tour?as=1")).json())["tour"]
        if t["status"] == "done":
            break
        assert t["current"], "a running tournament must always show the next real match"
        b = (await do(client, "t_next"))["battle"]
        assert "error" not in b
    assert t["status"] == "done" and t["champion"]


async def test_dead_pet_has_life_summary(client):
    await do(client, "create", "pig")
    await do(client, "advance", 2)
    for _ in range(12):  # pets no longer starve: live a whole life on autopilot until old age
        await do(client, "advance", 24 * 7)
        p = (await state(client))["pet"]
        if p["state"] == "dead":
            break
    assert p["state"] == "dead"
    s = p["summary"]
    assert s["title"] and s["cause"] and s["facts"]
    r = await client.get("/img/card/1.png")  # the same life on one picture
    assert r.status == 200 and r.content_type == "image/png"
    assert (await r.read())[:8] == b"\x89PNG\r\n\x1a\n"
    assert (await client.get("/img/card/3.png")).status == 404  # nobody there


async def test_no_time_button_hatch_once_and_actions_move_time(client):
    page = await (await client.get("/")).text()
    assert "ffBtn" not in page and "⏩ +" not in page and "⏩ Час" not in page   # no time-skip button (⏩ ×2 is the fight speed)
    await do(client, "create", "bird")
    s = await state(client)
    assert s["pet"]["state"] == "egg" and s["pet"]["persona"]["dream"]
    assert "🐣" in (await do(client, "hatch"))["message"]
    assert "Нема" in (await do(client, "hatch"))["message"]           # one time only
    s = await state(client)
    assert s["pet"]["state"] == "alive" and s["pet"]["perk"] and set(s["pet"]["power"]) == set(E.SKILLS)
    clock, years = s["clock"], s["pet"]["years"]
    for _ in range(12):
        await do(client, "adventure")
        r = (await do(client, "choose", None))["result"]
        assert "time" not in r                                          # the cost stays hidden
        if r["died"]:
            break
    s = await state(client)
    assert s["clock"] != clock and s["pet"]["years"] > years            # the world and the pet moved on


async def test_adopt_with_chosen_gender(client):
    assert "стать" in (await do(client, "create", "cat", gender="x"))["message"]
    assert (await state(client))["pet"] is None
    await do(client, "create", "cat", who=1, gender="f")
    await do(client, "create", "dog", who=2, gender="m")
    await do(client, "create", "fox", who=3)  # no choice: a coin flip, still a valid gender
    assert [(await state(client, w))["pet"]["gender"] for w in (1, 2)] == ["f", "m"]
    assert (await state(client, 3))["pet"]["gender"] in ("m", "f")


async def test_pending_event_carries_the_inner_voice(client):
    await do(client, "create", "cat", gender="f")
    await do(client, "hatch")
    await do(client, "advance", 24 * 2, care=True)
    seen = set()
    for _ in range(40):
        await do(client, "adventure")
        pend = (await state(client))["pet"]["pending"]
        if not pend:
            continue
        assert isinstance(pend["voice"], str) and "{" not in pend["voice"]
        seen.add(bool(pend["voice"]))
        await do(client, "choose", None)
    assert seen == {True, False}


async def test_a_duel_belongs_to_the_caller_and_ends_once(client):
    await do(client, "create", "pig")
    await do(client, "npcs", 1)
    await ready_for_tournament(client, 2)
    foe = next(p["owner"] for p in (await state(client))["players"] if p["npc"])
    b = (await do(client, "spar", **{"with": foe}))["battle"]
    assert b["paused"] and "winner" not in b and b["log"] and b["fighters"][0]["emoji"]
    stolen = (await do(client, "spar_move", "surrender", who=2, fight=b["fight"]))["battle"]
    assert "error" in stolen   # somebody else's fight id
    assert "error" in (await do(client, "spar_move", "cheat", fight=b["fight"]))["battle"]   # the id survives a bad move
    r = (await do(client, "spar_move", "surrender", fight=b["fight"]))["battle"]
    assert r["winner"] == foe and r["surrendered"] == 0 and r["from"] == len(b["log"])
    assert r["log"][-1]["text"].startswith("🏆") and r["highlights"][-1]["text"] == r["log"][-1]["text"]
    assert r["rec"]["1"]["line"].startswith("🥊") and r["rec"]["1"]["rank"]
    assert any("без травм" in n for n in r["notes"]["1"])   # JSON object keys are strings
    assert "error" in (await do(client, "spar_move", "strike", fight=b["fight"]))["battle"]   # the fight is over


async def test_my_tournament_match_is_a_duel_and_moves_the_bracket(client):
    await do(client, "create", "pig")
    await do(client, "npcs", 3)
    await ready_for_tournament(client, 4)
    assert "Турнір на" in (await do(client, "t_new"))["message"]
    mine = left = 0
    for _ in range(60):
        t = (await (await client.get("/api/tour?as=1")).json())["tour"]
        if t["status"] != "running":
            break
        cur = t["current"]
        b = (await do(client, "t_next", duel=True))["battle"]
        assert "error" not in b, b
        if not b.get("paused"):
            assert not cur or 1 not in (cur["a"]["owner"], cur["b"]["owner"])   # somebody else's match plays by itself
            continue
        mine += 1
        assert b["duel"] and b["owners"][0] == 1 and b["key"] == cur["key"] and b["moves"] and b["tell"]
        assert "error" in (await do(client, "spar_move", "strike", who=2, fight=b["fight"]))["battle"]
        if mine == 1 and not left:   # walk away from the first one: asking for the match again finishes it, no second try
            left = 1
            again = (await do(client, "t_next", duel=True))["battle"]
            assert not again.get("paused") and again["key"] == b["key"] and again["winner"] in again["owners"]
            assert "error" in (await do(client, "spar_move", "strike", fight=b["fight"]))["battle"]
            continue
        fid = b["fight"]
        while b.get("paused"):
            b = (await do(client, "spar_move", "strike", fight=fid))["battle"]
            assert "error" not in b, b
        assert b["key"] == cur["key"] and b["winner"] in b["owners"] and "bets" in b
        after = (await (await client.get("/api/tour?as=1")).json())["tour"]
        assert next(m for r in after["rounds"] for m in r if m["key"] == cur["key"])["winner"] == b["winner"]
    t = (await (await client.get("/api/tour?as=1")).json())["tour"]
    assert t["status"] == "done" and t["champion"] and mine >= 1


async def test_an_abandoned_duel_is_fought_out_by_the_pets(client):
    await do(client, "create", "pig")
    await do(client, "npcs", 1)
    await ready_for_tournament(client, 2)
    foe = next(p["owner"] for p in (await state(client))["players"] if p["npc"])
    first = (await do(client, "spar", **{"with": foe}))["battle"]
    second = (await do(client, "spar", **{"with": foe}))["battle"]   # the page was closed and the player starts again
    assert second["paused"] and second["fight"] != first["fight"]
    assert "error" in (await do(client, "spar_move", "strike", fight=first["fight"]))["battle"]
    me = next(p for p in (await state(client))["players"] if p["owner"] == 1)
    assert me   # the first duel was finished and counted without the player


async def test_tournament_title_sets_arena_champ_and_fame():
    import random

    from kit_the_cat.sandbox.game import Sandbox
    from kit_the_cat.storage import MemoryStore
    rng = random.Random(1)
    pets = []
    for o in (1, 2):
        p = E.new_pet(-777, o, f"P{o}", "cat", pets, rng)
        p.hatch(E.now())
        p.life.update(fame=0, attr=0)
        pets.append(p)
    sb = Sandbox(MemoryStore(), seed=1)
    t = dict(status="running", rounds=[[[1, 2]]], results={"0-0": dict(winner=1)}, prize=600, bets={})
    champ = sb._finish(t, {p.owner_id: p for p in pets}, {})
    assert champ["owner"] == 1 and t["status"] == "done"
    assert pets[0].flags["arena_champ"] == 1 and pets[0].life["fame"] == 5 and "arena_champ" not in pets[1].flags


async def _adult(c, who=1):
    await do(c, "create", "cat", who=who)
    await do(c, "hatch", who=who)
    await do(c, "advance", 24 * 30, care=True)


async def _png(c, url):
    r = await c.get(url)
    return r.status, (await r.read())[:4]


async def test_result_screen_keeps_the_picture_of_the_adventure(client):
    await _adult(client)
    assert (await _png(client, "/img/event/1.png"))[0] == 404  # no adventure yet
    await do(client, "adventure")
    assert (await _png(client, "/img/event/1.png")) == (200, b"\x89PNG")
    await do(client, "choose", None)
    for mood in ("", "happy", "sad", "nonsense"):
        assert (await _png(client, f"/img/event/1.png?mood={mood}")) == (200, b"\x89PNG")


async def test_try_on_only_what_is_owned_or_sold_today(client):
    await _adult(client)
    lists = await (await client.get("/api/lists?as=1")).json()
    sold = next(x for x in lists["stock"] if x["kind"] == "item")
    assert (await _png(client, f"/img/tryon/1.png?item={quote(sold['id'])}")) == (200, b"\x89PNG")
    assert (await _png(client, "/img/tryon/1.png?item=gen:head:%21%21"))[0] == 404
    assert (await _png(client, "/img/tryon/1.png?bg=kyiv")) == (200, b"\x89PNG")
    assert (await _png(client, "/img/tryon/1.png?bg=../../etc"))[0] == 200  # an unknown place is just home


async def test_state_shows_quests_achievements_ancestors_and_an_idle_line(client):
    await _adult(client)
    s = (await state(client))["pet"]
    assert s["idle"] and "{" not in s["idle"]
    assert s["ancestors"] == [] and s["ach_total"] >= len(s["achievements"])
    assert all(q["title"] and q["ep"] >= 0 and isinstance(q["end"], str) for q in s["quests"])
    assert all(":" in g and g.isascii() is False for g in s["genes"])
