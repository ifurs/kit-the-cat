"""0.3 life model: automatic upkeep, years as the price of decisions, life stats with tiers, casino, migration."""
import random

import pytest

from kit_the_cat import engine as E
from kit_the_cat.content import dsl
from kit_the_cat.content.dsl import ch, ev, o


def _adult(money: float = 500) -> E.Pet:
    p = E.Pet(chat_id=-1, owner_id=1, name="Бублик", owner_name="Оля")
    p.state, p.stage, p.hatched, p.last_tick, p.years, p.money = "alive", 3, E.now(), E.now(), 30.0, money
    p.skills = {s: 30 for s in E.SKILLS}
    p.persona = {"temper": "x", "dream": "y", "fear": "z", "food": "сало", "quirk": "q"}
    return p


@pytest.mark.parametrize("v,years", [("3d", 3 / 365), ("2w", 14 / 365), ("6m", 0.5), ("4y", 4.0), (1.5, 1.5)])
def test_durations(v, years):
    assert dsl.years(v) == pytest.approx(years)


@pytest.mark.parametrize("bad", ["", "5", "3x", "y", True, None])
def test_bad_durations_raise(bad):
    with pytest.raises(ValueError):
        dsl.years(bad)


def test_time_labels():
    assert [E.time_label(dsl.years(x)) for x in ("1d", "3d", "2w", "6m", "4y", "18m")] == \
        ["1 дн.", "3 дн.", "2 тиж.", "6 міс.", "4 р.", "1.5 р."]


def test_an_outcome_that_skips_years_can_end_a_life():
    p = _adult()
    p.years, p.lifespan = 79.0, 80.0
    p.resolve(ev("t_cryo", "?", ch("Кріосон", o("Розморозили", time="2y"))), 0, None, random.Random(0))
    assert p.state == "dead" and p.counters.get("natural")


def test_no_starving_without_care_but_debt_hurts():
    rich, broke = _adult(5000), _adult(-5000)
    for p in (rich, broke):
        p.hunger = p.clean = 10.0
        p._step(1.0, E.now(), random.Random(0))
        for _ in range(47):
            p._step(1.0, E.now(), random.Random(0))
    assert rich.alive and rich.health == 100 and rich.hunger > 70 and rich.clean > 70
    assert broke.health < 70 and broke.hunger < 40 and broke.look().hungry


def test_life_tiers_unlock_events_and_are_announced():
    p = _adult()
    req = dict(tier={"fame": 2})
    assert not p.meets(req)
    p.apply({"fame": 50})
    assert p.tier("fame") == 2 and p.meets(req) and p.tier_name("fame") == "📈 Мікроблогер"
    assert any("Мікроблогер" in t for _, k, t in p.log if k == "tier")
    p.apply({"fame": 60})
    assert "Зірка Євробачення" in p.achievements
    assert p.meets(dict(tier_max={"auth": 0}, life={"fame": 90}, years=(18, 60)))
    assert not p.meets(dict(tier={"money": 3}))


def test_personality_echoes_into_life_stats():
    p = _adult()
    p.apply({"party": 4, "toxic": 2, "int": 3})
    assert p.life["fame"] == pytest.approx(4) and p.life["auth"] == pytest.approx(1.6) and p.life["fin"] == pytest.approx(2.4)
    p.apply({"party": 4, "fame": 1})  # explicit life effect wins over the echo
    assert p.life["fame"] == pytest.approx(5)


def test_fin_literacy_softens_losses():
    a, b = _adult(1000), _adult(1000)
    b.life["fin"] = 90
    a.apply({"money": -300})
    b.apply({"money": -300})
    assert a.money == 700 and b.money == 790


def test_casino_rules():
    rng = random.Random(3)
    kid = _adult(1000)
    kid.stage = 2
    assert isinstance(E.casino(kid, "underpass", 50, rng), str)
    p = _adult(1000)
    assert E.casino_venues(p) == ["underpass", "bukovel"]
    for bad in (5, 10**9, -50, "100", True):
        assert isinstance(E.casino(p, "underpass", bad, rng), str)
    assert isinstance(E.casino(p, "private", 5000, rng), str)
    text, notes = E.casino(p, "underpass", 100, rng)
    assert text and p.counters["casino"] == 1


def test_old_documents_migrate_to_years_and_life_stats():
    d = _adult().to_dict()
    for k in ("years", "life"):
        d.pop(k)
    d["hatched"] = E.now() - 10 * E.DAY / E.SPEED  # 10 real days old (adult) in the 0.2 model
    d["lifespan"], d["skills"]["cha"], d["job"] = 30.0, 60, "blogger"
    p = E.Pet.from_dict(d)
    assert 18 < p.years < 60 and p.lifespan >= 74
    assert p.life["fame"] >= 45 and set(p.life) == set(E.LIFE)
    assert not any(k == "tier" for _, k, _ in p.log)  # no fake "new tier" announcements for migrated pets
