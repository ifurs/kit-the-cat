"""The standalone sandbox (kit-the-cat): a whole life without Telegram, through the HTTP API."""
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
    await do(c, "advance", 24 * 2, care=True)
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
    assert "з'їв" in (await do(client, "feed", "crust"))["message"]
    await do(client, "care", "play")
    await do(client, "adventure")
    s = await state(client)
    ev = s["pet"]["pending"]
    assert ev and ev["choices"]
    assert (await client.get("/img/event/1.png")).status == 200
    res = (await do(client, "choose", ev["choices"][0]["i"]))["result"]
    assert res["label"] and "error" not in res
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
    b = (await do(client, "spar", "cunning", **{"with": foe}))["battle"]
    assert "error" not in b and b["log"] and b["fighters"][0]["strategy"].startswith("🎭")


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
