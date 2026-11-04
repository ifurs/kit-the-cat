"""Body swap: the body (genes, so species too) moves, the soul (name, skills, bonds, items) stays; the swap is visible."""
import random

import pytest

from kit_the_cat import battle as B
from kit_the_cat import engine as E
from kit_the_cat.content.dsl import ch, ev, o
from kit_the_cat.sandbox.game import Sandbox
from kit_the_cat.storage import MemoryStore


def _pair(sp_a="pig", sp_b="bird"):
    rng = random.Random(4)
    a = E.new_pet(-1, 1, "A", sp_a, [], rng)
    b = E.new_pet(-1, 2, "B", sp_b, [a], rng)
    for p in (a, b):
        p.hatch(E.now(), rng)
        p.stage = 3
        p.skills = {k: 40 for k in p.skills}
        p.health, p.xp = 80, 500                                 # identical souls: only the bodies differ
    a.items, a.money, a.rel[b.pid] = ["hat"], 123, 7
    return a, b


def test_swap_moves_the_body_and_keeps_the_soul():
    a, b = _pair()
    ga, gb, sa, sb = dict(a.genes), dict(b.genes), a.species, b.species
    assert (sa, sb) == ("pig", "bird")
    before = {k: (v if k not in ("genes", "flags", "log") else None)
              for k, v in {**a.to_dict(), "flags": None}.items()}
    a.apply({"swap_genes": True}, b)
    assert a.genes == gb and b.genes == ga
    assert (a.species, b.species) == (sb, sa)                   # species follows the genes
    assert a.look().genes.species == sb and b.look().genes.species == sa  # drawn as the new body
    after = a.to_dict()
    for k in ("name", "gender", "skills", "money", "items", "rel", "persona", "traits", "owner_id"):
        assert after[k] == before[k], k                         # the soul stays


def test_swap_label_lasts_three_days_and_swapping_back_clears_it():
    a, b = _pair()
    names = {a.pid: a.name, b.pid: b.name}
    assert a.swap_label(names) == ""
    a.apply({"swap_genes": True}, b)
    assert a.swap_with() == b.pid and b.swap_with() == a.pid
    assert a.swap_label(names).startswith("🔄 У тілі ") and b.name.split()[0][:3] in a.swap_label(names)
    assert "🔄 У тілі" in E.card(a, names)
    d0 = a.flags["_swap"][1]
    old = E.clock
    try:
        E.clock = lambda: old() + 86400 * 5 / E.SPEED * 1.0  # five game days later
        assert a.swap_label(names) == "" and "🔄" not in E.card(a, names)
    finally:
        E.clock = old
    assert d0 == E.game_day() + 3
    a.apply({"swap_genes": True}, b)                             # back into their own bodies
    assert (a.species, b.species) == ("pig", "bird") and "_swap" not in a.flags and "_swap" not in b.flags


def test_swapped_pig_fights_like_its_new_body():
    a, b = _pair("pig", "bird")
    fa, fb = B.Fighter.of(a), B.Fighter.of(b)
    assert a.species == "pig" and fa.max_hp > fb.max_hp * 1.2 and fb.dodge > fa.dodge   # pig: HP x1.25; bird: dodge
    a.apply({"swap_genes": True}, b)
    fa2, fb2 = B.Fighter.of(a), B.Fighter.of(b)
    assert fa2.species == "bird" and fb2.species == "pig"
    assert fa2.dodge > fa.dodge + 0.1 and fa2.spd > fa.spd + 3   # bird body: dodge, speed
    assert fa2.max_hp < fa.max_hp * 0.85 and fb2.max_hp > fb.max_hp * 1.15  # the pig HP bonus went with the pig body


SWAP = ev("t_swap", "{name} і {other} чхнули.", ch("Чхнути", o("Обмін!", swap_genes=True)), social=True)


async def _sandbox(monkeypatch):
    monkeypatch.setitem(E.EVENTS, SWAP.id, SWAP)
    old = E.clock
    sb = Sandbox(MemoryStore(), seed=3, epoch=1_800_000_000.0)
    await sb.init()
    await sb.create(1, "pig")
    await sb.create(2, "bird")
    await sb.hatch(1)
    await sb.hatch(2)
    pets = await sb.pets(tick=False)
    for p in pets:
        p.stage = 3
    await sb.save(*pets)
    return sb, old


async def _species(sb):
    return {p.owner_id: (p.species, p.genes) for p in await sb.pets(tick=False)}


@pytest.mark.asyncio
async def test_sandbox_choose_swaps_both_pets_in_storage_and_tells_both_players(monkeypatch):
    sb, old = await _sandbox(monkeypatch)
    try:
        before = await _species(sb)
        a, b = await sb.pets(tick=False)
        a.start(SWAP, b, "manual")
        await sb.save(a)
        r = await sb.choose(1, 0)
        assert "swap" in r and "в тілі" in r["swap"]["text"]
        after = await _species(sb)
        assert after[1] == before[2] and after[2] == before[1]
        v1, v2 = await sb.view(1), await sb.view(2)
        assert v1["pet"]["swap"].startswith("🔄 У тілі ") and v2["pet"]["swap"].startswith("🔄 У тілі ")
        assert v1["pet"]["emoji"] == "🐦" and v2["pet"]["emoji"] == "🐷"
        assert [x["emoji"] for x in v1["players"]] == ["🐦", "🐷"]
        assert any("в тілі" in n for n in v2["pet"]["news"]) and v1["pet"]["news"] == []  # the other player is told
        assert (await sb.view(2))["pet"]["news"] == []                                    # once
    finally:
        E.clock = old


@pytest.mark.asyncio
async def test_sandbox_auto_path_swaps_and_notifies(monkeypatch):
    sb, old = await _sandbox(monkeypatch)
    try:
        before = await _species(sb)
        a, b = await sb.pets(tick=False)
        a.start(SWAP, b, "auto")
        a.pending["ts"] -= (E.BUDGET.decide_hours * 3 + 1) * 3600   # the decision time ran out: the autopilot chooses
        await sb.save(a)
        await sb.advance(1, auto_me=True)
        after = await _species(sb)
        assert after[1][0] == before[2][0] and after[2][0] == before[1][0]
        assert after[1][1] == before[2][1] and after[2][1] == before[1][1]
        v1 = await sb.view(1)
        assert any("в тілі" in n for n in v1["pet"]["news"]) and v1["pet"]["emoji"] == "🐦"
    finally:
        E.clock = old
