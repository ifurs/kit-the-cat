"""Stories must agree with the pet who lives them: age, job, repeats."""
import random

from kit_the_cat import engine as E
from test_perks_dreams_health import _pet


def adult(years: float = 30.0) -> E.Pet:
    p = _pet()
    p.stage, p.years = 3, years
    return p


def test_tenure_is_the_time_in_the_current_job():
    p = adult()
    req = dict(tenure=(0, 2))
    assert not p.meets(req)                                   # no job
    p.apply({"job": next(iter(E.JOBS))}, None, random.Random(1))
    assert p.meets(req)
    p.years += 1.9
    assert p.meets(req)
    p.years += 0.2
    assert not p.meets(req)                                   # not new any more
    p.apply({"job": ""}, None, random.Random(1))
    p.years -= 3
    assert not p.meets(req) and "_job_y" not in p.flags       # fired: the clock is gone
    p.job = next(iter(E.JOBS))                                # a document from before 0.18: hired «long ago»
    assert not p.meets(req)


def test_the_first_week_and_the_first_salary_are_about_a_new_job():
    for i in ("st_job", "st_first_salary"):
        assert E.EVENTS[i].req["tenure"][1] <= 2, i


def test_baby_events_are_for_babies():
    """«Перше слово» at ten years old, after the first class, was a real life of a pet."""
    baby = [e for e in E.EVENTS.values() if e.id.startswith("baby_")]
    assert baby and all(e.req.get("years", (0, 99))[1] <= 6 for e in baby), [e.id for e in baby if "years" not in e.req]


def test_an_infant_lives_only_events_written_for_its_age():
    p = _pet()
    p.stage, p.years = 1, 1.0
    other = _pet()
    other.stage, other.years = 3, 30.0
    for who in (None, other):
        cands, _ = p.candidates(who)
        assert cands or who
        assert all(any(k in e.req for k in ("stage", "years", "phase", "age")) for e in cands), \
            [e.id for e in cands if not any(k in e.req for k in ("stage", "years", "phase", "age"))]


def test_an_exhausted_social_pool_gives_a_solo_event_not_a_repeat():
    p, other = adult(), adult()
    other.owner_id = p.owner_id + 1
    p.recent = [e.id for e in E.EVENTS.values() if e.social]   # every social event was lived lately
    for seed in range(80):
        e, who = p.pick_event([p, other], random.Random(seed))
        assert e is None or not e.social, (seed, e.id)


def test_kids_is_the_number_of_children():
    p = adult(70)
    assert not p.meets(dict(kids=1))
    p.children = 1
    assert p.meets(dict(kids=1)) and not p.meets(dict(kids=2))


def test_grandchildren_belong_to_those_who_have_children():
    """«Онуки приїхали на літо» to a pet that never had a child was a real line of a real life."""
    import re
    from kit_the_cat.grammar import pick
    grand = re.compile(r"онук|внук", re.I)
    for i in ("old_grandkids",):
        assert E.EVENTS[i].req["kids"] == 1
    for c in E.EVENTS["old_pension"].choices:
        if grand.search(c.label):
            assert c.req.get("kids") == 1
    # the neutral twin exists for the childless
    assert "old_yard_kids" in E.EVENTS and "kids" not in E.EVENTS["old_yard_kids"].req
    assert not grand.search(pick(E.EVENTS["old_yard_kids"].text, "m", "m"))
    p = adult(70)
    p.stage = 4
    assert not p.meets(E.EVENTS["old_grandkids"].req) and p.meets(E.EVENTS["old_yard_kids"].req)


def test_a_boss_needs_a_job():
    assert E.EVENTS["tw_quantum_double"].req["job"] == "any"
    assert any(c.req.get("job") == "any" for c in E.EVENTS["hl_blood"].choices)


def test_the_new_social_events_fit_the_ages_they_tell_about():
    """Sandboxes for kids, prom for teens, weddings and trips for adults — never the other way round."""
    from kit_the_cat.content.social_more import KIDS, TEENS
    assert KIDS and all(e.req["stage"] == 1 and e.req["other_stage"] == 1 for e in KIDS)
    assert TEENS and all(e.req["stage"] == 2 and e.req["other_stage"] == 2 for e in TEENS)
    for i in ("soc_partner_anniversary", "soc_partner_dinner", "soc_partner_trip", "soc_ex_wedding"):
        assert E.EVENTS[i].req["stage"] == (3, 4), i
