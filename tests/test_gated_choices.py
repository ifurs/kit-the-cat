"""Skills and items open choices (task 08): locked buttons with a reason, the gated content, the soft hint."""
import random
from pathlib import Path

from kit_the_cat import engine as E
from kit_the_cat import sprites
from kit_the_cat.content import economy
from kit_the_cat.content.events import ALL
from kit_the_cat.content.gated import GATED
from test_perks_dreams_health import _pet

ROOT = Path(__file__).resolve().parent.parent
BY_ID = {e.id: e for e in ALL}
GATED_CHOICES = [(eid, c) for eid, cs in GATED.items() for c in cs]


def _adult(money: float = 500, **skills) -> E.Pet:
    p = _pet()
    p.stage, p.money, p.years = 3, money, 30.0
    p.skills = {s: 10 for s in E.SKILLS} | skills
    p.persona = dict(p.persona, temper="", lean="")   # no temperament perk: the numbers below are the skills
    return p


def _event(*choices, req=None) -> E.Event:
    return E.Event(id="t_gate", text="Тест", choices=list(choices), req=req or {})


FREE = E.ch("Просто піти", E.o("Пішов.", mood=1))


# --- locked_why --------------------------------------------------------------------------------------------------
def test_a_skill_lock_says_what_is_needed_and_what_the_pet_has():
    p = _adult(int=31)
    e = _event(FREE, E.ch("Знайти помилку в договорі", E.o("Ого.", fin=3), req=dict(skill={"int": 40})))
    assert [i for i, _ in p.options(e)] == [0]
    assert p.locked_why(e) == [(1, "потрібно 🧠 40 (зараз 31)")]
    p.skills["int"] = 40
    assert [i for i, _ in p.options(e)] == [0, 1] and p.locked_why(e) == []


def test_the_current_value_is_rounded_down_so_that_it_never_equals_the_need():
    p = _adult(int=39.6)
    e = _event(FREE, E.ch("Розум", E.o("Ого.", fin=3), req=dict(skill={"int": 40})))
    assert p.locked_why(e) == [(1, "потрібно 🧠 40 (зараз 39)")]


def test_an_item_lock_names_the_item_and_opens_when_it_is_owned():
    p = _adult()
    e = _event(FREE, E.ch("Дістати шаблю", E.o("Дзінь.", fin=1), req=dict(has="sabre")))
    assert p.locked_why(e) == [(1, f"потрібна річ: {E.item_name('sabre')}")]
    p.items = ["sabre@3"]   # a tinted one counts
    assert [i for i, _ in p.options(e)] == [0, 1] and p.locked_why(e) == []


def test_a_money_lock_keeps_working_both_ways():
    p = _adult(120)
    e = _event(E.ch("Купити авто", E.o("Їде", money=-5000)), FREE, E.ch("Багатий вибір", E.o("Так.", fin=1), req=dict(money=900)))
    assert p.locked(e) == [(0, 4880)]   # the older, money-only form is unchanged
    assert p.locked_why(e) == [(0, "бракує 4880 ₴"), (2, "потрібно 900 ₴ (є 120)")]


def test_several_failing_requirements_are_listed_together():
    p = _adult(int=12)
    e = _event(FREE, E.ch("Двері", E.o("ok", fin=1), req=dict(skill={"int": 40}, has="monocle")))
    assert p.locked_why(e) == [(1, f"потрібно 🧠 40 (зараз 12); потрібна річ: {E.item_name('monocle')}")]


def test_a_hidden_kind_of_requirement_never_shows_up_as_a_lock():
    p = _adult(int=12)
    hidden = [dict(role="vampire"), dict(flag="secret"), dict(cast={"galya": 2}), dict(trait={"toxic": 99}), dict(stage=4),
              dict(goal="mars"), dict(phase="grand"), dict(job="it")]
    for h in hidden:
        e = _event(FREE, E.ch("Закрите", E.o("ok", fin=1), req=dict(h, skill={"int": 40})),
                   E.ch("Закрите 2", E.o("ok", fin=1), req=dict(h, has="sabre")))
        assert p.locked_why(e) == [], h   # the story behind a hidden requirement is not spoilt
        assert [i for i, _ in p.options(e)] == [0]


def test_at_most_two_locked_buttons_in_event_order():
    p = _adult(int=1, str=1, cha=1, luck=1)
    e = _event(FREE, *[E.ch(f"Закрите {s}", E.o("ok", fin=1), req=dict(skill={s: 90})) for s in E.SKILLS])
    assert [i for i, _ in p.locked_why(e)] == [1, 2] and E.LOCK_MAX == 2


def test_a_jailed_pet_sees_no_locks():
    p = _adult(int=1)
    p.jail_until = E.now() + 3600
    assert p.locked_why(_event(E.ch("Закрите", E.o("ok", fin=1), req=dict(skill={"int": 90})))) == []


def test_the_autopilot_never_picks_a_locked_gated_choice():
    e = _event(FREE, E.ch("Розумний вихід", E.o("ok", fin=9), req=dict(skill={"int": 90}), auto="mystic"))
    for seed in range(30):
        assert _adult().auto_choice(e, None, random.Random(seed))[0] == 0


# --- the soft hint --------------------------------------------------------------------------------------------------
def _locked_event() -> E.Event:
    return _event(FREE, E.ch("Розумний вихід", E.o("ok", fin=1), req=dict(skill={"int": 40})))


def test_the_hint_is_a_third_of_the_time_and_names_the_skill():
    n = 0
    for i in range(300):
        p = _adult(int=30)
        p.owner_id = i
        res = p.resolve(_locked_event(), 0, None, random.Random(i))
        if res.hint:
            n += 1
            assert res.hint == "🔒 З 🧠 40 тут був би ще один варіант"
    assert 70 < n < 130   # 1 in 3


def test_the_hint_names_the_item_and_comes_once_per_game_day():
    e = _event(FREE, E.ch("Шабля", E.o("ok", fin=1), req=dict(has="sabre")))
    hints = []
    for i in range(200):
        p = _adult()
        p.events_done = i
        res = p.resolve(e, 0, None, random.Random(1))
        if res.hint:
            hints.append(res.hint)
            assert p.flags["_lock_hint"] == E.game_day()
            p.events_done += 1
            for k in range(20):   # the same day: never again
                p.events_done = 1000 + k
                assert p.resolve(e, 0, None, random.Random(k)).hint == ""
            break
    assert hints and "річчю «" in hints[0] and hints[0].endswith("тут був би ще один варіант")
    p.flags["_lock_hint"] = E.game_day() - 1   # the next game day it may come again
    for k in range(100, 200):
        p.events_done = k
        if p.resolve(e, 0, None, random.Random(k)).hint:
            break
    else:
        raise AssertionError("no hint on the next game day")


def test_no_hint_without_a_locked_choice_and_no_extra_rng_draw():
    free = _event(FREE, E.ch("Ще", E.o("ok", fin=1)))
    for i in range(40):
        assert _adult().resolve(free, 0, None, random.Random(i)).hint == ""
    a, b = random.Random(7), random.Random(7)
    _adult(int=30).resolve(_locked_event(), 0, None, a)
    _adult(int=50).resolve(_locked_event(), 0, None, b)   # here the choice is open: no hint, same stream
    assert a.random() == b.random()


# --- the content ---------------------------------------------------------------------------------------------
def test_every_gated_choice_belongs_to_an_event_and_comes_after_the_old_ones():
    for eid, cs in GATED.items():
        assert eid in BY_ID, eid
        assert BY_ID[eid].choices[-len(cs):] == cs, f"{eid}: gated choices must be last (indexes of old choices stay put)"
        assert len(BY_ID[eid].choices) > len(cs) and len(BY_ID[eid].choices) <= 6


def test_there_are_enough_gated_choices_for_every_skill():
    skill = [(eid, c) for eid, c in GATED_CHOICES if "skill" in c.req]
    item = [(eid, c) for eid, c in GATED_CHOICES if "has" in c.req]
    assert len(skill) >= 45 and len(item) >= 25
    for s in E.SKILLS:
        assert sum(1 for _, c in skill if s in c.req["skill"]) >= 8, s


def _phases(e: E.Event) -> set[str]:
    """The life phases in which the event's age requirements let it come."""
    age = {k: v for k, v in e.req.items() if k in ("stage", "years", "phase")}
    out = set()
    for ph, (lo, hi) in E.PHASES.items():
        p = _pet()
        p.years = float(min((lo + min(hi, 100)) / 2, 90))
        p.stage = 1 if p.years < 12 else 2 if p.years < 18 else 3 if p.years < 60 else 4
        if p.meets(age):
            out.add(ph)
    return out


def test_every_life_phase_has_gated_choices():
    for ph in E.PHASES:
        n = sum(1 for eid, _ in GATED_CHOICES if ph in _phases(BY_ID[eid]))
        assert n >= 5, f"{ph}: only {n}"
    # not only «any adult» events: each phase has some that belong to it alone
    only = {ph: sum(1 for eid, _ in GATED_CHOICES if _phases(BY_ID[eid]) == {ph}) for ph in E.PHASES}
    assert only["kid"] >= 5 and only["teen"] >= 5 and only["grand"] >= 3, only


def test_gated_requirements_are_known_and_use_real_buyable_items():
    for eid, c in GATED_CHOICES:
        assert set(c.req) <= {"skill", "has"}, (eid, c.label)
        assert ("skill" in c.req) != ("has" in c.req), (eid, c.label)   # one key: a skill or an item
        for s, n in c.req.get("skill", {}).items():
            assert s in E.SKILLS and 15 <= n <= 60, (eid, c.label)
        if "has" in c.req:
            item = c.req["has"]
            assert item in sprites.ITEMS, f"{eid}: unknown item {item}"
            assert item in economy.PRICES, f"{eid}: {item} cannot be bought"


def test_a_gated_choice_is_a_reward_not_a_cost_and_not_a_dice_roll():
    for eid, c in GATED_CHOICES:
        assert not c.check and not c.fail, (eid, c.label)
        assert c.auto, (eid, c.label)
        for out in c.outs:
            assert out.fx.get("money", 0) >= 0 and not out.fx.get("die"), (eid, c.label)
            assert out.fx.get("money", 0) <= 300, (eid, c.label)   # a reward, not a jackpot


def test_a_gated_choice_text_names_its_item_or_has_a_skill_word():
    names = {"sabre": "шабл", "guitar": "гітар", "helmet": "каск|касці", "cape": "плащ", "clown": "клоун", "cowboy": "ковбой",
             "mic": "мікрофон", "nerd": "окуляр", "sunglasses": "окуляр", "flowers": "квіт|букет", "apron": "фартух",
             "laptop": "ноутбук", "book": "книж", "monocle": "монокль", "headphones": "навушник", "suit": "костюм",
             "vyshyvanka": "вишиванк", "chef": "ковпак", "cards": "карти", "wizard": "капелюс", "hoodie": "худі",
             "cane": "ціп", "mustache": "вус", "foil": "фольг", "tracksuit": "спортивк|спортивц"}
    import re
    for eid, c in GATED_CHOICES:
        if "has" in c.req:
            text = (c.label + " " + c.outs[0].text).lower()
            assert re.search(names[c.req["has"]], text), f"{eid}: the text does not name {c.req['has']}"


def test_gated_events_still_have_a_free_choice_and_load():
    for eid in GATED:
        e = BY_ID[eid]
        assert any(not c.req.get("money") and not c.req.get("skill") and not c.req.get("has") for c in e.choices), eid
        assert e is E.EVENTS[eid]


def test_both_uis_draw_the_reason_under_a_locked_button():
    for page in ("web/index.html", "src/kit_the_cat/sandbox/static/index.html"):
        html = (ROOT / page).read_text(encoding="utf-8")
        assert "c.why" in html and "c.need" not in html and "r.hint" in html, page


def test_the_sandbox_view_carries_the_reason_and_the_result_the_hint():
    import asyncio

    from kit_the_cat.sandbox.game import Sandbox
    from kit_the_cat.storage import MemoryStore

    async def go():
        sb = Sandbox(MemoryStore(), 1)
        await sb.init()
        await sb.create(1, "fox", "f")
        await sb.hatch(1)
        p = await sb.pet(1, tick=False)
        p.stage, p.years, p.skills = 3, 30.0, {s: 10 for s in E.SKILLS}
        p.persona = dict(p.persona, temper="", lean="")
        e = BY_ID["adult_credit"]
        p.start(e, None, "manual")
        await sb.save(p)
        v = (await sb.view(1))["pet"]["pending"]
        assert [c["i"] for c in v["choices"]] == [0, 1, 2]
        lk = v["locked"]
        assert len(lk) == 1 and lk[0]["i"] == 3 and lk[0]["why"] == "потрібно 🧠 44 (зараз 10)" and lk[0]["label"]
        return await sb.choose(1, 2)
    res = asyncio.run(go())
    assert "hint" in res and isinstance(res["hint"], str)
