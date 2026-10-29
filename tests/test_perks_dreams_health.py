"""Temperament perks in every adventure, dreams as goals with a path to them, health that choices can take away."""
import random

from kit_the_cat import engine as E
from kit_the_cat.content.dsl import ch, ev, o
from kit_the_cat.content.persona import GOALS, PERKS, TEMPERAMENTS


def _pet(temper: str = "конспіролог", goal: str = "sea", stage: int = 3) -> E.Pet:
    lean = dict(TEMPERAMENTS)[temper]
    p = E.Pet(chat_id=-1, owner_id=1, name="Бублик", owner_name="Оля")
    p.state, p.stage, p.hatched, p.last_tick, p.years, p.money = "alive", stage, E.now(), E.now(), 30.0, 500
    p.skills = {s: 20 for s in E.SKILLS}
    p.persona = dict(temper=temper, lean=lean, goal=goal, dream=GOALS[goal], fear="z", food="сало", quirk="q")
    return p


def test_every_temperament_has_a_perk_and_it_counts_in_checks():
    assert {t for t, _ in TEMPERAMENTS} == set(PERKS)
    nerd, jock = _pet("ботан"), _pet("козак")
    assert nerd.skill("int") > jock.skill("int") and jock.skill("str") > nerd.skill("str")
    assert "🧠+10" in E.perk_text(nerd)


def test_choices_in_character_are_marked_easier_and_announced():
    p = _pet("конспіролог")  # leans to mystic
    e = ev("t_perk", "?", ch("Маятник", o("так", mystic=1), check=("luck", 40), auto="mystic"),
           ch("Логіка", o("так"), check=("luck", 40), auto="toxic"))
    assert p.button(e, 0).startswith("🎭 ") and not p.button(e, 1).startswith("🎭")
    assert p.chance(e.choices[0]) > p.chance(e.choices[1])
    res = p.resolve(e, 0, None, random.Random(3))
    assert any("у своїй стихії" in n for n in res.notes)


def test_new_pets_get_a_goal_and_old_ones_migrate():
    p = E.new_pet(-1, 1, "Оля", "cat", [], random.Random(5))
    assert p.persona["goal"] in GOALS and p.persona["dream"] == GOALS[p.persona["goal"]]
    old = _pet().to_dict()
    old["persona"] = {"temper": "ботан", "lean": "", "dream": "з'їсти Місяць", "fear": "z"}
    q = E.Pet.from_dict(old)
    assert q.persona["goal"] in GOALS and q.persona["dream"] == GOALS[q.persona["goal"]]


def test_a_dream_can_be_reached_in_three_steps():
    p, rng = _pet(goal="sea"), random.Random(0)
    p.skills = {s: 100 for s in E.SKILLS}
    p.health = 100
    assert p.eligible(E.EVENTS["dr_sea_1"], None) and not p.eligible(E.EVENTS["dr_mars_1"], None)
    for n in (1, 2, 3):
        e = E.EVENTS[f"dr_sea_{n}"]
        idx = 0 if n != 1 else 1  # hitchhiking needs luck; with luck 100 it works
        p.resolve(e, idx, None, rng)
        if n < 3:
            assert p.goal_step() == n
            p.years += 2
            nxt, _ = p.pick_event([p], rng)
            assert nxt.id == f"dr_sea_{n + 1}"
    assert p.flags.get("dream_done") and E.DONE_ACH in p.achievements
    assert "🌟" in E.goal_text(p) and E.life_summary(p)["title"] == "Той, хто здійснив свою мрію"


def test_a_reckless_choice_at_low_health_kills():
    p = _pet()
    p.health = 20
    e = ev("t_roof", "?", ch("Стрибнути", o("Ой.", health=-40)))
    res = p.resolve(e, 0, None, random.Random(0))
    assert res.died and not p.alive and "Стрибнути" in p.cause


def test_health_recovers_slowly_and_the_doctor_costs_money():
    p = _pet()
    p.health, p.money = 40, 1000
    p.tick(E.now() + 10 * E.hour())
    assert p.health < 50                     # ten hours heal only a few points
    y = p.years
    E.care(p, "heal", random.Random(0))
    assert p.money == 1000 - E.HEAL_PRICE and p.years > y
    p.money = 0
    text, notes = E.care(p, "heal", random.Random(0))
    assert notes == [] and "₴" in text
