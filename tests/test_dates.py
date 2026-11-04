"""Dates: a real pool for every stage of a romance, and a pair does not get the same date twice in a row."""
import random
import re

from kit_the_cat import engine as E
from kit_the_cat.content.dsl import ch, ev, o


def _pet(owner: int, name: str, stage: int = 3, years: float = 25.0) -> E.Pet:
    p = E.Pet(chat_id=1, owner_id=owner, name=name, owner_name="Оля", gender="m" if owner % 2 else "f")
    p.state, p.stage, p.years, p.money, p.hatched = "alive", stage, years, 5000, E.now()
    p.last_tick = E.now()
    p.skills = {s: 20 for s in E.SKILLS}
    return p


def _pair(status: str, stage: int = 3, years: float = 25.0) -> tuple[E.Pet, E.Pet]:
    a, b = _pet(1, "Мурзик", stage, years), _pet(2, "Мурка", stage, years)
    _relate(a, b, status)
    return a, b


def _relate(a: E.Pet, b: E.Pet, status: str) -> None:
    for x, y in ((a, b), (b, a)):
        x.status.pop(y.pid, None)
        x.partner = ""
        if status:
            x.status[y.pid] = status
        if status == "partner":
            x.partner = y.pid


def _pool(a: E.Pet, b: E.Pet) -> list[str]:
    cands, _ = a.candidates(b, "date")
    return [e.id for e in cands]


def test_the_date_flag_is_an_event_attribute():
    e = ev("x", "t", ch("a", o("b")), social=True, date=True)
    assert e.date is True and ev("y", "t", ch("a", o("b"))).date is False
    assert E.is_date_event(e)
    assert E.is_date_event(E.EVENTS["soc_proposal"]) and E.is_date_event(E.EVENTS["soc_date"])  # tagged / by hint
    assert not any(E.is_date_event(E.EVENTS[i]) for i in E.DATE_FALLBACKS)                       # built-ins are not pool


def test_pool_size_by_relationship():
    for label, status, stage, years, need in (
        ("single teens", "", 2, 15.0, 5), ("friend teens", "friend", 2, 15.0, 5),
        ("single adults", "", 3, 25.0, 5), ("bestie adults", "bestie", 3, 40.0, 5),
        ("crush teens", "crush", 2, 15.0, 5), ("crush adults", "crush", 3, 25.0, 5), ("crush grand", "crush", 4, 70.0, 5),
        ("partners", "partner", 3, 35.0, 5), ("exes", "ex", 3, 35.0, 3),
    ):
        a, b = _pair(status, stage, years)
        pool = _pool(a, b)
        assert len(pool) >= need, (label, pool)
        assert not [i for i in pool if i.startswith("_")], (label, pool)


def test_the_proposal_is_a_date_of_a_crush_pair():
    a, b = _pair("crush")
    assert "soc_proposal" in _pool(a, b)


def _date(a: E.Pet, b: E.Pet, rng: random.Random, status: str):
    """One /pet_date: pick, live (the first choice that is open), then put the relationship and the pets back."""
    for x in (a, b):
        x.health, x.money, x.jail_until, x.hospital_until, x.years = 100.0, 5000, 0.0, 0.0, 25.0
        x.recent = []   # the pair memory must work without the 40-event window
    _relate(a, b, status)
    e, other = a.pick_event([b], rng, "date")
    assert e and other is b
    a.resolve(e, a.options(e, b)[0][0], b, rng)
    return e


def test_twenty_dates_in_a_row_do_not_repeat_until_the_pool_is_used_up():
    a, b = _pair("crush")
    rng = random.Random(7)
    n = len(_pool(a, b))
    picks = [_date(a, b, rng, "crush").id for _ in range(20)]
    assert len(set(picks[:n])) == n, picks             # every fitting date once…
    assert not [i for i in picks if i.startswith("_")]  # …and the built-in date never
    assert picks[n] == picks[0] and picks[n + 1] == picks[1]   # then the one had longest ago comes back


def test_a_pair_that_has_had_a_date_gets_a_new_one_even_if_it_is_not_recent():
    a, b = _pair("crush")
    pool = _pool(a, b)
    a.had_date(b, pool[0])
    b.had_date(a, pool[0])
    for seed in range(40):
        e, _ = a.pick_event([b], random.Random(seed), "date")
        assert e.id != pool[0]


def test_the_memory_is_per_pair_and_bounded():
    a, b = _pair("crush")
    c = _pet(3, "Барсик")
    a.had_date(b, "soc_date")
    assert a.dates_had(b) == ["soc_date"] and a.dates_had(c) == []
    for i in range(E.DATE_PAIR_KEEP + 25):
        a.had_date(b, f"x{i}")
    assert len(a.dates_had(b)) == E.DATE_PAIR_KEEP
    for owner in range(10, 10 + E.DATE_PAIRS_KEEP + 15):
        a.had_date(_pet(owner, "Інший"), "soc_date")
    assert len([k for k in a.flags if k.startswith("dt:")]) == E.DATE_PAIRS_KEEP


def test_the_fallback_date_has_variants_and_is_only_for_pairs_with_nothing():
    reqs = {repr(E.EVENTS[i].req) for i in E.DATE_FALLBACKS}
    assert len(reqs) == 1 and len({E.EVENTS[i].text for i in E.DATE_FALLBACKS}) == 3
    a, b = _pair("enemy", 2, 15.0)    # enemies have no date in the pool
    assert not _pool(a, b)
    seen = {a.pick_event([b], random.Random(s), "date")[0].id for s in range(60)}
    assert seen == set(E.DATE_FALLBACKS)
    kid, grown = _pet(1, "Малюк", 1, 6.0), _pet(2, "Дорослий")
    assert kid.pick_event([grown], random.Random(1), "date") == (None, None)   # no romance for kids
    a, b = _pair("", 2, 15.0)
    assert not [e for e in E.EVENTS.values() if e.id in E.DATE_FALLBACKS[1:] and e in a.candidates(b, "")[0]]


NEW = [e for e in E.EVENTS.values() if e.id.startswith("dt_")]
ALCOHOL = re.compile(r"пив[оа]|вино|шампан|горілк|коньяк|віскі|алкогол|п'ян|похміл", re.I)


def _texts(e) -> str:
    return " ".join([e.text] + [c.label for c in e.choices] + [x.text for c in e.choices for x in c.outs + c.fail])


def test_new_dates_are_marked_social_and_gated_by_age():
    assert len(NEW) >= 30
    for e in NEW:
        assert e.social and e.date and not e.followup, e.id
        req = e.req
        phases = req.get("phase", [])
        phases = [phases] if isinstance(phases, str) else phases
        stage = req.get("stage", 0)
        stage = stage[0] if isinstance(stage, (tuple, list)) else stage
        assert "kid" not in phases and (phases or stage >= 2), f"{e.id}: a kid could get this date"
        lo = req.get("other_stage", 0)
        lo = lo[0] if isinstance(lo, (tuple, list)) else lo
        assert lo >= 2, f"{e.id}: the other pet could be a kid"
        if req["status"] in (["partner"],):
            assert (phases and "teen" not in phases) or stage >= 3, f"{e.id}: a couple must be grown-up"


def test_teen_dates_are_innocent():
    teen = [e for e in NEW if e.req.get("phase") == "teen"]
    assert len(teen) == 9
    for e in teen:
        assert e.req["other_stage"] == (2, 2), e.id   # a teen's date is a teen
        assert not ALCOHOL.search(_texts(e)), e.id
        for c in e.choices:
            for x in c.outs + c.fail:
                assert x.fx.get("party", 0) <= 1, (e.id, c.label)
                assert x.fx.get("status") in (None, "crush"), (e.id, c.label)   # no couples before 18
                assert not x.fx.get("baby") and not x.fx.get("swap_genes"), e.id


def test_new_date_pools_by_status_and_phase():
    def count(status, phase):
        return sum(1 for e in NEW if set(e.req["status"]) == set(status) and e.req.get("phase") in phase)
    friends = ["", "friend", "bestie"]
    assert count(friends, ["teen"]) == 5 and count(friends, [["young", "middle"]]) == 5
    assert count(["crush"], ["teen"]) == 4
    assert count(["crush"], [["young", "middle"], ["young", "middle", "grand"], "grand"]) == 7
    assert count(["partner"], [["young", "middle", "grand"], ["young", "middle"], ["middle", "grand"]]) == 6
    assert count(["ex"], [["young", "middle", "grand"]]) == 3


def test_new_dates_fit_a_caption_and_follow_ups_exist():
    for e in NEW:
        assert len(e.text) <= 450 and all(len(c.label) <= 40 for c in e.choices), e.id
    thens = {x.fx["then"][0] for e in NEW for c in e.choices for x in c.outs + c.fail if "then" in x.fx}
    assert thens == {"fu_dt_valentine_card", "fu_dt_tiles", "fu_dt_ficus"}
    for i in thens:
        f = E.EVENTS[i]
        assert f.followup and not f.social and ("phase" in f.req or "stage" in f.req), i


def test_a_follow_up_of_a_date_comes_back_alone():
    a, b = _pair("partner")
    e = E.EVENTS["dt_p_ficus"]
    rng = random.Random(3)
    a.resolve(e, 0, b, rng)
    assert [f[0] for f in a.followups] == ["fu_dt_ficus"]
    a.years += 1.5
    got, other = a.pick_event([b], rng, "solo")
    assert got and got.id == "fu_dt_ficus" and other is None
