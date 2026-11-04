"""Regressions from the automated playtest of 40 lives (2026-11-04): debt lock text, the baby guard, romance only within
an age bracket, strangers who already met, tails with an age or a job, the mother in a grown-ups' fight."""
import random

from kit_the_cat import engine as E
from kit_the_cat.content.dsl import ch, ev, o
from test_gated_choices import _adult


def _kid(owner: int, years: float, stage: int) -> E.Pet:
    p = _adult()
    p.owner_id, p.years, p.stage = owner, years, stage
    return p


def test_a_lock_in_debt_names_the_missing_money_not_zero():
    e = ev("x", "t", ch("Купити", o("ок", money=-300)), ch("Піти", o("ок")))
    p = _adult(money=-731)
    why = dict(p.locked_why(e))
    assert why == {0: "бракує 1031 ₴"}, why


def test_a_newborn_lives_only_events_written_for_its_age():
    p = _kid(1, 1.0, 1)
    school = E.EVENTS["sl_meet"]
    assert not p.eligible(school, None) and not E.for_infants(school)
    assert E.for_infants(E.EVENTS["baby_first_word"])
    lived = {p.pick_event([p], random.Random(s), "solo")[0].id for s in range(40)} - {None}
    assert lived and all(E.for_infants(E.EVENTS[i]) for i in lived), lived


def test_romance_stays_within_an_age_bracket():
    teen, grown, kid = _kid(1, 15.0, 2), _kid(2, 40.0, 3), _kid(3, 9.0, 1)
    assert E.same_bracket(teen, _kid(4, 16.0, 2)) and E.same_bracket(grown, _kid(5, 70.0, 4))
    assert not E.same_bracket(teen, grown) and not E.same_bracket(kid, kid)
    for eid in ("_date", "soc_crush", "soc_date", "soc_crush_message"):
        assert eid in E.ROMANCE
        assert not teen.eligible(E.EVENTS[eid], grown, fresh=False) and not grown.eligible(E.EVENTS[eid], teen, fresh=False)
    labels = {c.label for c in E.EVENTS["_date"].choices if teen.meets(c.req, _kid(4, 16.0, 2))}
    assert not {"Зробити пропозицію 💍", "Подумати про дітей 🥚"} & labels


def test_strangers_means_never_met():
    a, b = _kid(1, 30.0, 3), _kid(2, 30.0, 3)
    bench = E.EVENTS["soc_meet_bench"]
    assert a.meets(bench.req, b)
    a.rel[b.pid] = 5   # met once, the score cooled down: status is "" again, but they know each other
    assert a.status.get(b.pid, "") == "" and not a.meets(bench.req, b)


def test_tails_respect_their_age_and_job():
    gated = [t for t in E.TAILS if len(t) > 3]
    assert any("самогон" in t[0] for t in gated) and any("начальника" in t[0] for t in gated)
    kid = _kid(1, 8.0, 1)
    assert not [t for t in gated if "самогон" in t[0] and kid.meets(t[3])]
    assert all("застряг " not in t[0] for t in E.TAILS)   # «{застряг|застрягла}»


def test_mother_comes_only_to_a_kids_fight():
    fight = E.EVENTS["_fight"]
    grown, other = _kid(1, 40.0, 3), _kid(2, 40.0, 3)
    labels = {c.label for i, c in grown.options(fight, other)}
    assert "Покликати маму" not in labels and "Покликати кума" in labels
    kid, kid2 = _kid(3, 9.0, 1), _kid(4, 9.0, 1)
    assert "Покликати маму" in {c.label for i, c in kid.options(fight, kid2)}
