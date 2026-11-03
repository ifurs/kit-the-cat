"""Money is a choice, not an accident: prices lock choices, losses stop at the debt floor, credit is deliberate."""
import random


from kit_the_cat import engine as E
from kit_the_cat.content import economy
from test_perks_dreams_health import _pet


def _adult(money: float) -> E.Pet:
    p = _pet()
    p.stage, p.money = 3, money
    return p


def _event(*choices) -> E.Event:
    return E.Event(id="t_econ", text="Тест", choices=list(choices), req={})


def test_a_choice_whose_every_outcome_loses_money_has_a_price():
    p = _adult(0)
    cheap = E.ch("a", E.o("x", money=-50), E.o("y", money=-300))
    assert p.price(cheap) == 300  # the worst outcome: the pet must be able to pay whichever it rolls
    assert p.price(E.ch("g", E.o("win", money=500), E.o("lose", money=-500))) == 0  # a gamble is no price
    assert p.price(E.ch("f", E.o("free", mood=3))) == 0
    assert p.price(E.ch("c", E.o("loan", credit=-900))) == 0  # a loan is not a price


def test_a_literate_pet_pays_less():
    p = _adult(0)
    p.life["fin"] = 60
    assert p.price(E.ch("a", E.o("x", money=-1000))) == 800


def test_a_broke_pet_does_not_see_what_it_cannot_pay_but_sees_it_locked():
    p = _adult(120)
    e = _event(E.ch("Купити авто", E.o("Їде", money=-5000)), E.ch("Пішки", E.o("Іде", mood=1)),
               E.ch("Шаурма", E.o("Смачно", money=-100)))
    assert [i for i, _ in p.options(e)] == [1, 2]
    assert p.locked(e) == [(0, 4880)]
    p.money = 5000
    assert [i for i, _ in p.options(e)] == [0, 1, 2] and p.locked(e) == []


def test_a_pet_in_debt_still_has_its_free_choices():
    p = _adult(-300)
    e = _event(E.ch("Купити", E.o("ok", money=-10)), E.ch("Ні", E.o("ok", mood=1)))
    assert [i for i, _ in p.options(e)] == [1]


def test_autopilot_never_picks_a_locked_choice():
    e = _event(E.ch("Купити авто", E.o("Їде", money=-5000), auto="party"), E.ch("Пішки", E.o("Іде", mood=1)))
    for seed in range(40):
        p = _adult(10)
        assert p.auto_choice(e, None, random.Random(seed))[0] == 1


def test_a_loss_stops_at_the_debt_floor():
    p = _adult(0)
    p.apply({"money": -99999}, None, random.Random(1))
    assert p.money == E.DEBT_FLOOR
    p.apply({"money": -300}, None, random.Random(1))
    assert p.money == E.DEBT_FLOOR  # already at the floor: nothing more can be taken


def test_a_loss_the_pet_can_pay_is_paid_in_full():
    p = _adult(1000)
    p.apply({"money": -1200}, None, random.Random(1))
    assert p.money == -200


def test_what_could_not_be_taken_hurts_otherwise():
    p = _adult(0)
    p.items = ["cap"]
    mood = p.mood
    notes = p.apply({"money": -5000}, None, random.Random(1))
    assert p.mood < mood and p.items == [] and any("списали" in n for n in notes)


def test_credit_goes_below_the_floor_and_marks_the_pet():
    p = _adult(0)
    p.apply({"credit": -3000}, None, random.Random(1))
    assert p.money == -3000 and p.flags.get("loan")
    p.money = 10
    p._daily(random.Random(1))
    assert not p.flags.get("loan")


def test_credit_is_only_for_loans():
    from kit_the_cat.content.validate import economy_errors
    assert economy_errors() == []


def test_every_event_keeps_a_free_choice_for_a_broke_pet():
    for e in E.EVENTS.values():
        broke = _adult(-400)
        assert any(broke.can_pay(c) and not c.req.get("money") for c in e.choices), e.id


def test_a_dying_pet_is_treated_on_credit_but_a_healthy_one_must_pay():
    p = _adult(20)
    p.health = 10
    text, _ = E.care(p, "heal", random.Random(1))
    assert p.money == 20 - E.HEAL_PRICE and p.flags.get("loan") and p.health > 10
    q = _adult(20)
    q.health = 60
    assert "На лікаря треба" in E.care(q, "heal", random.Random(1))[0] and q.money == 20


def test_welfare_covers_the_cost_of_living():
    p = _adult(0)
    p.job = ""
    day = economy.WELFARE - E.UPKEEP[1] - E.HOME_UPKEEP.get("khrushchovka", 15)
    assert day >= 25
