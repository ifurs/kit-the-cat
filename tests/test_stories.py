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


# --- «Холостяк / Холостячка» -------------------------------------------------------------------------------------

def _girl() -> E.Pet:
    p = _pet()
    p.name, p.gender = "Мурка", "f"
    return p


def _tv_run(p: E.Pet, root: str, seed: int) -> list[E.Result]:
    rng = random.Random(seed)
    p.health, p.money, p.years = 100, 5000, 22
    p.start(E.EVENTS[root], None, "manual")
    return _play(p, [rng.randrange(4) for _ in range(6)], rng)


def test_story_titles_are_gendered_like_any_text():
    assert E.EVENTS["st_tv"].story == "{Холостяк|Холостячка}"
    for p, want in ((_pet(), "Холостяк"), (_girl(), "Холостячка")):
        rs = _tv_run(p, "st_tv", 1)
        assert rs[-1].story["title"] == want and all(r.story["title"] == want for r in rs if r.next)
    p = _girl()
    p.health = 100
    p.start(E.EVENTS["st_lift"], None, "manual")
    rs = _play(p, [0], random.Random(3))
    assert rs[-1].story["title"] == "Застрягла у ліфті" and "{" not in rs[-1].story["title"]


def test_the_tv_story_plays_for_a_boy_and_a_girl_and_every_ending_is_reachable():
    ends = set()
    for make in (_pet, _girl):
        for root in ("st_tv", "st_tv_scout"):
            for seed in range(120):
                p = make()
                rs = _tv_run(p, root, seed)
                assert 2 <= len(rs) <= 6 and not p.pending and not p.tale
                steps = rs[-1].story["steps"]
                assert len(steps) == len(rs) and all("{" not in s and "|" not in s for s in steps)
                ends.add(rs[-2].next)
    assert ends == {"st_tv_end_secret", "st_tv_end_love", "st_tv_end_scandal", "st_tv_end_star", "st_tv_end",
                    "st_tv_end_no"}


def test_a_girls_season_has_male_contestants_and_a_boys_season_female_ones():
    boy, girl = _pet(), _girl()
    t_boy = boy.fmt(E.EVENTS["st_tv_limo"].text)
    t_girl = girl.fmt(E.EVENTS["st_tv_limo"].text)
    assert "Оксана з Полтави" in t_boy and "Тарас" not in t_boy
    assert "Тарас з Полтави" in t_girl and "Оксана" not in t_girl
    assert "Холостячка" in girl.fmt(E.EVENTS["st_tv"].text) and "«Холостяк»" in boy.fmt(E.EVENTS["st_tv"].text)
    assert boy.fmt(E.EVENTS["blog_viral"].choices[2].label) == "Піти на «Холостяка»"
    assert girl.fmt(E.EVENTS["blog_viral"].choices[2].label) == "Піти на «Холостячку»"


def test_blog_viral_casts_the_pet_and_the_story_can_then_fire():
    p, rng = _girl(), random.Random(5)
    p.years, p.health, p.stage = 24, 100, 3
    assert not p.meets(E.EVENTS["st_tv"].req)
    p.flags["blog"] = 1
    p.start(E.EVENTS["blog_viral"], None, "manual")
    res = p.resolve(E.EVENTS["blog_viral"], 2, None, rng)
    assert p.flags["tv_cast"] == 1 and not res.next
    assert p.meets(E.EVENTS["st_tv"].req) and p.phase() == "young"
    _tv_run(p, "st_tv", 9)
    assert "tv_cast" not in p.flags or not p.flags["tv_cast"]
    assert not p.meets(E.EVENTS["st_tv"].req) or p.flags.get("seen_st_tv")


def test_the_secret_ending_needs_the_quiet_rose_and_a_warm_heart():
    p, rng = _pet(), random.Random(1)
    p.health, p.years = 100, 24
    p.start(E.EVENTS["st_tv"], None, "manual")
    ids = [p.resolve(E.EVENTS["st_tv"], 0, None, rng).next]                     # honest contract: heart 1
    ids.append(p.resolve(E.EVENTS["st_tv_limo"], 2, None, rng).next)           # the quiet rose: heart 2
    ids.append(p.resolve(E.EVENTS["st_tv_date"], 0, None, rng).next)           # keep the peace: heart 3
    ids.append(p.resolve(E.EVENTS["st_tv_scandal"], 1, None, rng).next)        # silence: heart 4, drama 1
    ids.append(p.resolve(E.EVENTS["st_tv_parents"], 0, None, rng).next)        # Zhytomyr: heart 6
    assert ids[-1] == "st_tv_end_secret"
    end = p.resolve(E.EVENTS["st_tv_end_secret"], 0, None, rng)
    assert "Остання троянда" in p.achievements and end.story["steps"][0] == "Підписати чесно"
