"""Events don't repeat while fresh ones fit; a dead pet gets a life summary that fits a caption."""
import random

from kit_the_cat import engine as E


def _adult(owner: int = 1) -> E.Pet:
    p = E.Pet(chat_id=-1, owner_id=owner, name="Бублик", owner_name="Оля")
    p.state, p.stage, p.hatched = "alive", 3, E.now() - 10 * E.DAY
    p.skills = {s: 30 for s in E.SKILLS}
    p.persona = {"temper": "x", "dream": "y", "fear": "z", "food": "сало", "quirk": "q"}
    return p


def test_solo_events_do_not_repeat_within_the_recent_window():
    p, rng = _adult(), random.Random(3)
    ids = []
    for _ in range(E.RECENT):
        e, _ = p.pick_event([p], rng, "solo")
        p.resolve(e, p.options(e, None)[0][0], None, rng)
        p.state, p.health, p.hunger, p.jail_until, p.hospital_until = "alive", 100.0, 100.0, 0.0, 0.0
        ids.append(e.id)
    assert len(ids) == len(set(ids)), [i for i in ids if ids.count(i) > 1]
    assert sum(p.seen.values()) == E.RECENT


def test_lived_events_lose_weight_but_never_vanish():
    p, rng = _adult(), random.Random(1)
    p.recent = [e.id for e in E.EVENTS.values()]  # everything is "recent": still picks something
    e, _ = p.pick_event([p], rng, "solo")
    assert e is not None


def test_story_keeps_highlights_bounded_and_unique():
    p = _adult()
    p.note("hatched", "🐣 not a highlight")
    for i in range(30):
        p.note("ach", f"🏆 досягнення {i}")
        p.note("twist", "🌀 той самий поворот")
    assert len(p.story) <= E.STORY_MAX
    assert sum(t == "🌀 той самий поворот" for _, _, t in p.story) == 1
    assert p.story[0][2] == "🏆 досягнення 0"  # the first moment stays


def test_obituary_fits_a_caption_and_escapes_names():
    p, b = _adult(), _adult(2)
    p.name, b.name = "<b>Злий</b> & Ко", "Мурка"
    p.partner, p.children = b.pid, 2
    p.counters.update(ok=7, fail=3, twists=4, money_max=12345)
    p.achievements = [f"Досягнення номер {i} з довгою назвою" for i in range(12)]
    for i in range(E.STORY_MAX):
        p.note("twist", f"🌀 {'дуже ' * 20}довгий сюжетний поворот {i}")
    assert p.die("помер від сміху на корпоративі", random.Random(0), natural=True) or p.state == "dead"
    p.state = "dead"
    cap = E.card(p, {b.pid: b.name})
    assert len(cap) <= 1020
    assert "<b>Злий</b>" not in cap and "&lt;b&gt;Злий" in cap
    assert "Засновник династії" in cap or "олігарх" in cap
    s = E.life_summary(p, {b.pid: b.name})
    assert s["title"] and s["story"] and "Мурка" in s["family"]


def test_ukrainian_plural():
    forms = [E.plural(n, "пригода", "пригоди", "пригод") for n in (1, 3, 5, 11, 12, 21, 22, 34, 111, 0)]
    assert forms == ["пригода", "пригоди", "пригод", "пригод", "пригод", "пригода", "пригоди", "пригоди", "пригод", "пригод"]
