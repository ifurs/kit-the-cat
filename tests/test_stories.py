"""Multi-step stories (step=, sv=, story=): the next step comes at once, scores pick the ending, the ending lists
every decision; every path of every story ends within 6 steps without errors."""
import random

from kit_the_cat import engine as E
from kit_the_cat.content.events import ALL
from test_perks_dreams_health import _pet

ROOTS = [e for e in ALL if e.story and not e.followup]


def _play(p: E.Pet, path: list[int], rng: random.Random) -> list[E.Result]:
    """Play the pending story choosing path[i] at step i (wrapping); returns the results."""
    out = []
    while p.pending and len(out) < 10:
        e = E.EVENTS[p.pending["id"]]
        idx = path[len(out) % len(path)] % len(e.choices)
        out.append(p.resolve(e, idx, None, rng))
    return out


def test_story_steps_come_at_once_and_the_ending_lists_every_decision():
    p, rng = _pet(), random.Random(1)
    p.health = 100
    p.start(E.EVENTS["st_alarm"], None, "manual")
    p.pending["at"] = 42
    r1 = p.resolve(E.EVENTS["st_alarm"], 0, None, rng)          # → metro
    assert r1.next == "st_alarm_metro" and p.pending["id"] == "st_alarm_metro" and p.pending["at"] == 42
    assert r1.story == {"title": "Ніч тривоги", "step": 2} and not r1.tail
    p.resolve(E.EVENTS["st_alarm_metro"], 0, None, rng)         # share water: kind +2
    r3 = p.resolve(E.EVENTS["st_alarm_morning"], 0, None, rng)  # help with the glass: kind +2 → the kind ending
    assert r3.next == "st_alarm_end_kind"
    end = p.resolve(E.EVENTS["st_alarm_end_kind"], 0, None, rng)
    assert not end.next and not p.pending and not p.tale
    assert end.story["title"] == "Ніч тривоги" and len(end.story["steps"]) == 4
    assert end.story["steps"][0] == "Бігти в метро" and any("❤" in n or "😊" in n for n in end.story["notes"])


def test_scores_pick_the_ending_and_the_fallback_catches_the_rest():
    p, rng = _pet(), random.Random(2)
    p.start(E.EVENTS["st_alarm"], None, "manual")
    rs = _play(p, [2, 2, 2, 0], rng)                            # sleep, scroll the news, walk: risk 3
    assert [r.next for r in rs[:3]] == ["st_alarm_hall", "st_alarm_morning", "st_alarm_end_tired"]
    p.start(E.EVENTS["st_alarm"], None, "manual")
    rs = _play(p, [1, 1, 1, 0], rng)                            # hall, "I'm ok", coffee: kind 1, risk 0
    assert rs[2].next == "st_alarm_end"


def test_every_path_of_every_story_ends_within_six_steps():
    assert len(ROOTS) >= 8
    for root in ROOTS:
        for seed in range(30):
            rng = random.Random(seed)
            p = _pet()
            p.health, p.money = 100, 5000
            p.start(root, None, "manual")
            rs = _play(p, [rng.randrange(4) for _ in range(6)], rng)
            assert rs and not p.pending and not p.tale, root.id
            assert len(rs) <= 6 and rs[-1].story.get("steps"), root.id
            assert all(r.next for r in rs[:-1]), root.id


def test_a_plain_event_or_death_clears_a_broken_story():
    p, rng = _pet(), random.Random(3)
    p.start(E.EVENTS["st_cnap"], None, "manual")
    p.resolve(E.EVENTS["st_cnap"], 0, None, rng)
    assert p.tale and p.pending["id"] == "st_cnap_2"
    p.resolve(E.EVENTS["kid_puddle"], 0, None, rng)             # something else got resolved instead
    assert not p.tale
    p.start(E.EVENTS["st_cnap"], None, "manual")
    p.resolve(E.EVENTS["st_cnap"], 0, None, rng)
    p.die("тест", rng)
    assert not p.tale and not p.pending


def test_a_story_survives_growing_up_in_the_middle_of_a_step():
    p, rng = _pet(stage=2), random.Random(4)
    p.years = 17.999                                            # a teen on a first date turns 18 during the step
    p.start(E.EVENTS["st_date"], None, "manual")
    r = p.resolve(E.EVENTS["st_date"], 0, None, rng)
    assert r.next == "st_date_2" and p.tale and p.pending["id"] == "st_date_2"
