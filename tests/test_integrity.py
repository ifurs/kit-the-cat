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
