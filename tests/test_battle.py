"""Battle engine: fights end, favourites usually win, no one dies, brackets are well-formed."""
import random

import pytest

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


# --- task 09: a readable fight, one decision, a reason to fight ------------------------------------------------

def _pair(seed):
    rng = random.Random(seed)
    a, b = _pets(2, rng)
    return a, b, rng


def test_paused_fight_plus_resume_equals_one_call():
    paused = 0
    for seed in range(60):
        a, b, rng = _pair(seed)
        one = B.fight(B.Fighter.of(a, "aggressive"), B.Fighter.of(b, "careful"), random.Random(seed + 1000))
        r2 = random.Random(seed + 1000)
        st = B.fight(B.Fighter.of(a, "aggressive"), B.Fighter.of(b, "careful"), r2, stop_at=B.STOP_AT)
        assert isinstance(st, B.FightState)
        paused += st.paused
        two = st.result if st.done else B.resume(st, None, None, r2)
        assert (two.winner, two.rounds, [e["text"] for e in two.log]) == (one.winner, one.rounds, [e["text"] for e in one.log])
        if st.paused:
            assert not st.log[-1]["text"].startswith("🏆")
    assert paused > 30   # most fights have a decision point


def test_the_pause_happens_once_below_half_health():
    for seed in range(20):
        a, b, _ = _pair(seed)
        r = random.Random(seed)
        st = B.fight(B.Fighter.of(a), B.Fighter.of(b), r, stop_at=0.5)
        if st.paused:
            assert st.low in (0, 1) and st.fighters[st.low].hp < st.fighters[st.low].max_hp * 0.5
            assert B.resume(st, "defend", "allin", r).log[-1]["text"].startswith("🏆")
            assert st.done and B.resume(st, "allin", None, r) is st.result   # resuming twice changes nothing


def test_tactics_change_the_numbers_and_say_so():
    a, b, _ = _pair(3)
    f1, f2 = B.Fighter.of(a), B.Fighter.of(b)
    st = B.fight(f1, f2, random.Random(1), stop_at=0.5)
    assert st.paused
    atk, dfn = f1.atk, f1.dfn
    B.resume(st, "allin", None, random.Random(1))
    assert f1.atk == pytest.approx(atk * 1.3) and f1.dfn == pytest.approx(dfn * 0.7)
    assert any(e["k"] == "tactic" and "ва-банк" in e["text"] for e in st.log)


def test_surrender_loses_now_and_keeps_the_health():
    for seed in range(20):
        a, b, rng = _pair(seed)
        st = B.fight(B.Fighter.of(a), B.Fighter.of(b), random.Random(seed), stop_at=0.5)
        if not st.paused:
            continue
        res = B.resume(st, "surrender", "allin", random.Random(seed))
        assert res.winner == 1 and res.surrendered == 0
        assert [e["k"] for e in res.log if e["k"] == "tactic"] == []   # nobody bothers with tactics now
        assert res.log[-2]["k"] == "surrender" and res.log[-1]["text"].startswith("🏆")
        health = a.health
        wn, ln = B.aftermath(b, a, rng, surrender=True)
        assert a.health == health and a.flags["losses"] == 1 and any("без травм" in n for n in ln)
        c, d, rng = _pair(seed)
        hp = d.health
        B.aftermath(c, d, rng)   # a normal defeat costs 8 health
        assert d.health == hp - 8
        # surrendering side b
        a2, b2, _ = _pair(seed)
        st = B.fight(B.Fighter.of(a2), B.Fighter.of(b2), random.Random(seed), stop_at=0.5)
        assert B.resume(st, None, "surrender", random.Random(seed)).winner == 0
        return
    pytest.fail("no paused fight found")


def test_highlights_are_short_and_end_with_the_last_line():
    rng = random.Random(9)
    pets = _pets(12, rng)
    long = 0
    for _ in range(80):
        a, b = rng.sample(pets, 2)
        r = B.fight(B.Fighter.of(a, rng.choice(list(B.STRATEGIES))), B.Fighter.of(b, rng.choice(list(B.STRATEGIES))), rng)
        h = r.highlights
        assert 1 <= len(h) <= B.HIGHLIGHTS and h[-1] is r.log[-1] and h[0] is r.log[0]
        assert [e["i"] for e in h] == sorted(e["i"] for e in h) and all(r.log[e["i"]] is e for e in h)
        assert len(h) >= min(5, len(r.log))
        long += len(r.log) > B.HIGHLIGHTS
    assert long > 40   # the cut really cuts


def test_log_lines_have_kinds():
    rng = random.Random(4)
    kinds = set()
    pets = _pets(10, rng)
    for _ in range(60):
        a, b = rng.sample(pets, 2)
        kinds |= {e["k"] for e in B.fight(B.Fighter.of(a), B.Fighter.of(b), rng).log}
    assert {"crit", "miss", "special"} <= kinds


@pytest.mark.parametrize("elo,name", [(1000, "Новачок"), (1049, "Новачок"), (1050, "Боєць"), (1149, "Боєць"),
                                      (1150, "Гроза району"), (1299, "Гроза району"), (1300, "Легенда арени"), (900, "Новачок")])
def test_rank_boundaries(elo, name):
    p = _pets(1, random.Random(1))[0]
    p.flags["elo"] = elo
    assert B.rank(p) == name
    del p.flags["elo"]
    assert B.rank(p) == "Новачок"


def test_record_line_counts_down_to_the_next_achievement():
    p = _pets(1, random.Random(1))[0]
    p.flags.update(wins=4, losses=1)
    assert B.record(p) == "🥊 4–1 · ще 1 перемога до «Бійцівський клуб»"
    p.flags["wins"] = 15
    assert "ще 5 перемог до «Гроза району»" in B.record(p)
    p.flags["wins"] = 52
    assert B.record(p) == "🥊 52–1" and B.next_goal(p) is None


def test_a_win_pays_in_fame_and_notes_say_what_the_fight_gave():
    rng = random.Random(2)
    a, b = _pets(2, rng)
    a.life["fame"] = b.life["fame"] = 0
    a.life["attr"] = 0
    wn, ln = B.aftermath(a, b, rng)
    assert a.life["fame"] == B.FAME_WIN and b.life["fame"] == 0
    assert wn[0].startswith("🏅 Elo +") and "⭐ +8 XP" in wn and any(n.startswith("💪") for n in wn) and any(n.startswith("😊 +10") for n in wn)
    assert ln[0].startswith("🏅 Elo −") and any(n.startswith("❤️ −8") for n in ln) and any(n.startswith("😊 −10") for n in ln)


def test_five_wins_make_a_known_fighter_and_a_title_makes_a_champion():
    rng = random.Random(3)
    a, b = _pets(2, rng)
    for _ in range(5):
        B.aftermath(a, b, rng)
    assert a.flags["arena_vet"] == 1 and "Бійцівський клуб" in a.achievements
    a.life["fame"], a.life["attr"] = 0, 0
    B.crown(a, 900, rng)
    assert a.flags["arena_champ"] == 1 and a.flags["titles"] == 1 and a.life["fame"] == B.FAME_TITLE
    assert any(i.startswith("crown") for i in a.items)


# --- duel: a fight in rounds ------------------------------------------------------------------------------------

def _duel(seed):
    a, b, rng = _pair(seed)
    return B.duel(B.Fighter.of(a, B.DUEL), B.Fighter.of(b, B.DUEL), rng), rng


def test_a_duel_ends_within_its_rounds_whatever_is_played():
    for seed in range(40):
        d, rng = _duel(seed)
        while not d.done:
            assert [m["key"] for m in B.duel_moves(d, 0)][:3] == list(B.MOVES)
            B.duel_round(d, rng.choice([None, "strike", "guard", "trick", "special", "ult", "nonsense"]), None, rng)
        r = d.result
        assert r.winner in (0, 1) and 1 <= r.rounds <= B.DUEL_ROUNDS and r.log[-1]["text"].startswith("🏆")
        assert sum(e["k"] == "round" for e in r.log) <= B.DUEL_ROUNDS and len(r.highlights) <= B.HIGHLIGHTS
        assert B.duel_round(d, "strike", "strike", rng) is r   # a finished duel stays finished


def test_duel_triangle_strike_beats_trick_beats_guard_beats_strike():
    def hurt(ma, mb):   # health each side lost over many first rounds
        lost = [0.0, 0.0]
        for seed in range(60):
            d, rng = _duel(seed)
            for f in d.fighters:   # plain fighters: no dodge, no specials, no ultimate
                f.dodge, f.specials, f.ultimate = 0.0, [], ""
            hp = [f.hp for f in d.fighters]
            B.duel_round(d, ma, mb, rng)
            lost = [lost[i] + hp[i] - d.fighters[i].hp for i in (0, 1)]
        return lost
    for win, lose in B.BEATS.items():
        a, b = hurt(win, lose)
        assert a < b * 0.5, (win, lose, a, b)   # the winner of the exchange is hurt far less
    a, b = hurt("guard", "guard")
    assert a <= 0 and b <= 0   # two blocks: nobody is hit, both catch their breath


def test_duel_gear_and_skills_show_in_the_moves():
    a, b, _ = _pair(4)
    bare = {m["key"]: m["power"] for m in B.duel_moves(B.duel(B.Fighter.of(a, B.DUEL), B.Fighter.of(b, B.DUEL), random.Random(1)), 0)}
    a.equipped["held"] = "sabre"
    armed = {m["key"]: m["power"] for m in B.duel_moves(B.duel(B.Fighter.of(a, B.DUEL), B.Fighter.of(b, B.DUEL), random.Random(1)), 0)}
    assert all(armed[k] > bare[k] for k in B.MOVES)
    b.equipped["outfit"] = "bronik"   # armour blunts a strike and a counter, a trick goes past it
    vs_armour = {m["key"]: m["power"] for m in B.duel_moves(B.duel(B.Fighter.of(a, B.DUEL), B.Fighter.of(b, B.DUEL), random.Random(1)), 0)}
    assert vs_armour["strike"] < armed["strike"] and vs_armour["trick"] == armed["trick"]


def test_duel_tell_is_the_plan_more_often_for_a_sharp_reader():
    def honest(wit):
        hits = 0
        for seed in range(300):
            d, rng = _duel(seed % 20)
            d.fighters[0].wit = wit
            for f in d.fighters:
                f.specials, f.ultimate = [], ""
            text = B.duel_tell(d, 1, random.Random(seed))
            shown = next(k for k, v in B.TELLS.items() if any(text.startswith(t.split("{")[0]) and text.endswith(t.split("}")[-1]) for t in v))
            hits += shown == d.plan[1]
        return hits / 300
    assert honest(90) > honest(0) + 0.2
    d, rng = _duel(1)
    B.duel_tell(d, 1, rng)
    plan = d.plan[1]
    B.duel_round(d, "guard", None, rng)
    assert d.used[1] == [plan]   # the announced move is the one that is played


def test_surrender_in_a_duel_loses_now():
    d, rng = _duel(2)
    r = B.duel_round(d, "surrender", None, rng)
    assert r.winner == 1 and r.surrendered == 0 and r.log[-2]["k"] == "surrender"
