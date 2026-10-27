"""Battle engine: fights end, favourites usually win, no one dies, brackets are well-formed."""
import random

from kit_the_cat import battle as B
from kit_the_cat import engine as E


def _pets(n, rng):
    out = []
    for i in range(n):
        p = E.new_pet(-1, i + 1, f"U{i}", rng.choice(["pig", "cat", "dog", "fox", "horse", "axolotl"]), out, rng)
        p.hatch(E.now())
        p.stage = rng.choice([2, 3, 4])
        for s in p.skills:
            p.skills[s] = rng.randint(5, 70)
        p.xp = rng.randint(0, 2000)
        for t in rng.sample(list(E.TRAITS), 2):
            p.traits[t] = rng.randint(3, 30)
        if rng.random() < 0.3:
            p.role = rng.choice(list(E.ROLES))
        out.append(p)
    return out


def test_fights_end_and_favourites_usually_win():
    rng = random.Random(5)
    pets = _pets(30, rng)
    fav = 0
    for _ in range(600):
        a, b = rng.sample(pets, 2)
        fa, fb = B.Fighter.of(a, rng.choice(list(B.STRATEGIES))), B.Fighter.of(b, rng.choice(list(B.STRATEGIES)))
        ch = B.win_chance(fa, fb)
        r = B.fight(fa, fb, rng)
        assert r.winner in (0, 1) and 1 <= r.rounds <= 25
        assert r.log[0]["text"].startswith("🔔") and r.log[-1]["text"].startswith("🏆")
        assert all("−0" not in e["text"] for e in r.log)
        fav += (r.winner == 0) == (ch >= 0.5)
    assert 0.65 < fav / 600 < 0.92  # favourites win most fights, upsets still happen


def test_aftermath_is_not_lethal():
    rng = random.Random(1)
    a, b = _pets(2, rng)
    b.health = 5
    B.aftermath(a, b, rng)
    assert b.alive and a.flags["wins"] == 1 and b.flags["losses"] == 1
    assert a.flags["elo"] > 1000 > b.flags["elo"]


def test_bracket_shapes():
    rng = random.Random(2)
    for n in (3, 5, 8, 11, 16, 20):
        rounds = B.bracket(_pets(n, rng), rng)
        size = len(rounds[0]) * 2
        assert size & (size - 1) == 0 and size >= min(n, 16)
        entrants = [o for m in rounds[0] for o in m if o]
        assert len(entrants) == min(n, 16) and len(set(entrants)) == len(entrants)
        assert len(rounds[-1]) == 1
        assert not any(m == [0, 0] for m in rounds[0])  # byes only pair a seed with an empty slot
