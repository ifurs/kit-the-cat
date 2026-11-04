"""Progress the player can see: income preview == daily payout, chance parts, item skill bonuses, no «ур.»."""
import copy
import random
from pathlib import Path

import pytest

from kit_the_cat import battle as B
from kit_the_cat import engine as E
from kit_the_cat.content import economy
from kit_the_cat.content.dsl import ch, ev, o
from test_perks_dreams_health import _pet

ROOT = Path(__file__).resolve().parent.parent


def _paid(p: E.Pet) -> int:
    """What `_daily` really paid today (income − cost of living − tax), read from the stored last payout."""
    p._daily(random.Random(1))
    day, inc, cost, tax = p.flags["_last_pay"]
    assert day == E.game_day()
    return inc - cost - tax


def _adult(**kw) -> E.Pet:
    p = _pet()
    p.stage, p.money = 3, kw.pop("money", 200)
    for k, v in kw.items():
        setattr(p, k, v)
    return p


def _same(p: E.Pet) -> None:
    pv = E.income_preview(p)
    lo, hi = pv["net"]
    assert lo == hi, "the test needs a fixed pay"
    assert _paid(p) == lo


@pytest.fixture(autouse=True)
def fixed_pay(monkeypatch):
    for j in ("atb", "taxi"):
        monkeypatch.setitem(economy.JOBS[j], "pay_range", (300, 300))


def test_income_preview_matches_the_daily_payout_of_a_job():
    p = _adult(job="atb", job_days=7)
    p.life["blat"] = 40
    pv = E.income_preview(p)
    assert pv["kind"] == "job" and pv["job"] == (int(300 * 1.14 * 1.2),) * 2 and pv["upkeep"] > 0
    _same(p)
    assert p.job_days == 8   # the daily step is the same one that pays


def test_income_preview_tenure_is_capped_at_sixty_percent():
    p = _adult(job="taxi", job_days=90)
    assert E.income_preview(p)["job"] == (480, 480)
    _same(p)


@pytest.mark.parametrize("stage,job,kind", [(3, "", "welfare"), (4, "", "pension"), (1, "", "pocket"), (2, "", "pocket")])
def test_income_preview_without_a_job(stage, job, kind):
    p = _adult(stage=stage, job=job)
    pv = E.income_preview(p)
    assert pv["kind"] == kind and pv["job"][0] == pv["job"][1] > 0
    _same(p)


def test_income_preview_jailed_and_hospital_and_demon():
    jailed = _adult(job="atb")
    jailed.jail_until = E.now() + 3600
    pv = E.income_preview(jailed)
    assert pv["job"] is None and pv["kind"] == ""
    _same(jailed)

    sick = _adult(job="atb")
    sick.hospital_until = E.now() + 3600
    assert E.income_preview(sick)["job"] == (150, 150)   # half of 300
    _same(sick)

    demon = _adult(job="atb", role="demon")
    assert E.income_preview(demon)["job"] == (390, 390)
    _same(demon)
    kid_demon = _adult(stage=1, role="demon")
    assert E.income_preview(kid_demon)["job"] == (int(economy.POCKET * 1.3),) * 2
    _same(kid_demon)


def test_income_preview_extras_and_wealth_tax():
    p = _adult(job="taxi", money=10000)
    p.life.update(fame=50, auth=50, fin=40)
    pv = E.income_preview(p)
    assert dict(pv["extra"]) == {"реклама": 200, "«дах»": 150, "відсотки": int(10000 * 0.004 * 40 / 100)}
    assert pv["tax"] == int((10000 - economy.WEALTH_TAX[0]) * economy.WEALTH_TAX[1])
    _same(p)


def test_income_preview_of_a_range_brackets_the_payout():
    p = _adult(job="blogger", money=100)
    pv = E.income_preview(p)
    assert pv["job"][0] < 0 < pv["job"][1]
    assert pv["net"][0] < _paid(p) <= pv["net"][1]


def test_income_line_reads_like_a_card_line():
    p = _adult(job="atb", job_days=7)
    line = E.income_line(p)
    assert line.startswith("💼 ") and "₴/день, побут −" in line and "≈ +" in line
    assert E.income_line(_adult(job="")).startswith("💶 соцдопомога +")
    assert "💼" in E.card(p, {})


# --- chance ------------------------------------------------------------------------------------------

def _choice(skill="str", diff=30, auto=""):
    return ch("x", o("y"), check=(skill, diff), auto=auto)


@pytest.mark.parametrize("stage,scale", [(1, 0.6), (2, 0.8), (3, 1.0), (4, 1.0)])
@pytest.mark.parametrize("skill,diff", [("str", 30), ("cha", 55), ("luck", 40)])
def test_chance_is_unchanged_for_a_pet_without_items(stage, scale, skill, diff):
    """The documented formula, written out by hand: the refactor into pieces must not move the number."""
    p = _pet(stage=stage)
    p.skills = {"str": 42, "int": 30, "cha": 20, "luck": 50}
    p.xp = 20 * 3 ** 2   # level 4
    p.mood, p.health = 90, 20   # +5 and −10 on every skill
    c = _choice(skill, diff, p.persona["lean"])
    own = lambda s: p.skills[s] + p.perk().get(s, 0) + 5 - 10  # noqa: E731
    v = own(skill) + (own("luck") * 0.15 if skill != "luck" else 0) + (p.level - 1) * 1.5 - diff * scale + E.LEAN_BONUS
    assert p.level == 4
    assert p.chance(c) == pytest.approx(max(0.2, min(0.95, 0.5 + v / 50)), abs=1e-12)
    assert p.chance(c) == p.chance(c, items=False)   # nothing worn: the items change nothing


@pytest.mark.parametrize("skill", ["str", "int", "cha", "luck"])
@pytest.mark.parametrize("diff", [10, 50, 80])
@pytest.mark.parametrize("auto", ["", "mystic"])
def test_chance_parts_sum_to_the_pre_clamp_value(skill, diff, auto):
    p = _pet("конспіролог")
    p.equipped = {"held": "sabre", "head": "crown"}
    p.health, p.mood, p.xp = 20, 90, 400
    c = _choice(skill, diff, auto)
    parts = p.chance_parts(c)
    v = (p.chance(c) - 0.5) * 50
    if 0.2 < p.chance(c) < 0.95:
        assert sum(n for _, n in parts) == round(v)
    assert all(isinstance(n, int) and n for _, n in parts)
    names = [name for name, _ in parts]
    assert any("складність" in x for x in names)
    assert p.chance_parts(ch("n", o("y"))) == []


def test_chance_parts_name_the_pieces():
    p = _pet("козак")
    p.equipped = {"held": "sabre"}
    p.health, p.mood = 10, 90
    names = " ".join(n for n, _ in p.chance_parts(_choice("str", 10, p.persona["lean"])))
    for word in ("сила", "темперамент", "речі", "здоров'я", "настрій", "удача", "у своїй стихії", "складність"):
        assert word in names


# --- items -------------------------------------------------------------------------------------------

def test_item_skill_table_points_at_real_items_and_skills():
    from kit_the_cat import sprites
    assert 20 <= len(economy.ITEM_SKILL) <= 40
    for it, bonus in economy.ITEM_SKILL.items():
        assert it in sprites.ITEMS, it
        assert bonus and set(bonus) <= set(E.SKILLS) and all(2 <= v <= 5 for v in bonus.values()), it


def test_item_skill_bonus_counts_only_for_worn_items_and_is_capped():
    p = _pet()
    base = p.skill("str")
    p.items = ["sabre", "bronik", "helmet"]
    assert p.skill("str") == base and p.item_bonus("str") == 0   # in the bag: nothing
    p.equipped = {"held": "sabre"}
    assert p.skill("str") == base + 4 and p.skill("str", items=False) == base
    p.equipped = {"held": "sabre", "outfit": "bronik", "head": "helmet", "face": "scar", "neck": "chain"}
    assert p.item_bonus("str") == economy.ITEM_SKILL_CAP == 8   # 4 + 3 + 2 + 2 capped
    assert p.skill("str") == base + 8
    assert p.item_bonus("int") == 0


def test_generated_items_give_plus_one_from_their_seed():
    it = "gen:head:abc"
    b = E.item_skill(it)
    assert sum(b.values()) == 1 and set(b) <= set(E.SKILLS) and E.item_skill(it) == b
    assert E.item_skill("sabre@3") == {"str": 4} and E.item_skill("nothing") == {}


def test_item_label_shows_battle_and_skill_stats():
    assert B.item_label("sabre") == "🗡️+6 · 💪+4"
    assert B.item_label("helmet") == "🛡️+5 · 💪+2"
    assert B.item_label("cap") == ""


def test_worn_items_lift_the_style_floor():
    p = _pet()
    p.life["attr"] = 15
    p.equipped = {"head": "crown", "held": "guitar", "neck": "chain"}
    for _ in range(40):
        p._life_daily(random.Random(1))
    assert 20 <= p.life["attr"] <= 21 + 1e-9   # 15 + 2 per item, no further
    q = _pet()
    q.life["attr"] = 30
    for _ in range(100):
        q._life_daily(random.Random(1))
    assert q.life["attr"] == 15


def test_a_check_passed_thanks_to_an_item_says_so():
    p = _pet()
    p.skills = {s: 20 for s in E.SKILLS}
    e = ev("t_help", "?", ch("Шабля", o("так"), check=("str", 40)))
    p.equipped = {"held": "sabre"}
    c = e.choices[0]
    chance_with, chance_without = p.chance(c), p.chance(c, items=False)
    assert chance_with > chance_without
    # find a seed whose draw lands between the two chances and whose d20 is neither 1 nor 20
    for seed in range(400):
        q = copy.deepcopy(p)
        res = q.resolve(e, 0, None, random.Random(seed))
        if res.helped:
            assert res.ok and "Шабля" in res.helped and res.helped in res.notes
            assert res.check["skill"] == "str" and res.check["item"] == 4
            break
    else:
        pytest.fail("no seed made the sabre matter")
    nothing = _pet()
    nothing.skills = dict(p.skills)
    assert all(not nothing.resolve(e, 0, None, random.Random(s)).helped for s in range(50))


def test_no_russism_abbreviation_of_level():
    for sub in ("src", "web"):
        for f in (ROOT / sub).rglob("*"):
            if f.suffix in (".py", ".html", ".js") and "content" not in f.parts:
                assert "ур. " not in f.read_text(encoding="utf-8"), f
