"""Decisions have weight: inferred per-choice time, follow-ups that bring earlier choices back, personality."""
import random

from kit_the_cat import engine as E
from kit_the_cat.content import dsl
from kit_the_cat.content.events import ALL, FOLLOWUPS


def _adult() -> E.Pet:
    p = E.Pet(chat_id=-1, owner_id=1, name="Бублик", owner_name="Оля")
    p.state, p.stage, p.hatched, p.last_tick, p.years, p.money = "alive", 3, E.now(), E.now(), 30.0, 500
    p.skills = {s: 30 for s in E.SKILLS}
    p.persona = {"temper": "x", "dream": "y", "fear": "z", "food": "сало", "quirk": "q"}
    return p


def test_decisions_cost_no_time_but_story_skips_do():
    p, rng = _adult(), random.Random(0)
    p.resolve(E.EVENTS["teen_uni"], 0, None, rng)
    assert p.years == 30.0 and p.button(E.EVENTS["teen_uni"], 0) == "КПІ"
    p.resolve(E.EVENTS["st_coma"], 0, None, random.Random(0))  # waiting out a coma: the story skips years
    assert p.years > 30.0


def test_followups_are_never_random_and_always_scheduled():
    p, rng = _adult(), random.Random(0)
    fu = {e.id for e in ALL if e.followup}
    assert fu and {v[0] for v in FOLLOWUPS.values()} <= fu
    for _ in range(300):
        e, _ = p.pick_event([p], rng, "solo")
        assert e is None or e.id not in fu


def test_an_earlier_choice_comes_back():
    p, rng = _adult(), random.Random(1)
    e = E.EVENTS["daily_pigeon"]
    p.resolve(e, 0, None, rng)  # bought a lottery ticket → fu_pigeon_ticket in a month
    assert [f[0] for f in p.followups] == ["fu_pigeon_ticket"]
    p.years += dsl.years("1m")
    e2, other = p.pick_event([p], rng)
    assert e2.id == "fu_pigeon_ticket" and other is None and not p.followups


def test_followups_wait_until_due_and_expire():
    p, rng = _adult(), random.Random(2)
    p.followups = [["fu_pigeon_ticket", p.years + 5]]
    e, _ = p.pick_event([p], rng, "solo")
    assert e.id != "fu_pigeon_ticket" and p.followups
    p.years += 25  # overdue by 20 years: the moment has passed
    e, _ = p.pick_event([p], rng, "solo")
    assert not p.followups


def test_personality_makes_in_character_events_likelier():
    calm, glutton = _adult(), _adult()
    glutton.traits["glutton"] = 60
    rng_a, rng_b = random.Random(5), random.Random(5)
    food = lambda e: e and any(c.auto == "glutton" for c in e.choices)  # noqa: E731
    a = sum(bool(food(calm.pick_event([calm], rng_a, "solo")[0])) for _ in range(400))
    b = sum(bool(food(glutton.pick_event([glutton], rng_b, "solo")[0])) for _ in range(400))
    assert b > a * 1.2
