"""Recurring characters (content/cast.py): bonds, states, requirements, old documents, the content that uses them."""
import random

import pytest

from kit_the_cat import engine as E
from kit_the_cat.content import validate
from kit_the_cat.content.cast import BOND_MAX, BOND_MIN, CAST, bond_word
from kit_the_cat.content.dsl import ch, ev, o
from kit_the_cat.content.events import ALL


@pytest.fixture
def pet():
    p = E.new_pet(1, 1, "Тест", "cat", [], random.Random(0))
    p.hatch(E.now(), random.Random(0))
    p.stage, p.years = 3, 30.0
    return p


def test_meeting_a_character_creates_a_record_and_moves_the_bond(pet):
    notes = pet.apply({"cast": {"galya": 2}})
    assert pet.cast["galya"] == dict(b=2, since=30.0, st="here")
    assert any("баба Галя" in n for n in notes)
    pet.apply({"cast": {"galya": -5}})
    assert pet.cast["galya"]["b"] == -3
    assert pet.cast["galya"]["since"] == 30.0   # the first meeting stays


def test_the_bond_stays_on_its_scale(pet):
    pet.apply({"cast": {"galya": 99}})
    assert pet.cast["galya"]["b"] == BOND_MAX
    pet.apply({"cast": {"galya": -99}})
    assert pet.cast["galya"]["b"] == BOND_MIN


def test_an_unknown_character_is_ignored(pet):
    assert pet.apply({"cast": {"nobody": 1}, "cast_state": {"nobody": "away"}}) == []
    assert pet.cast == {}


def test_state_changes_only_for_a_character_the_pet_knows(pet):
    pet.apply({"cast_state": {"galya": "away"}})
    assert pet.cast == {}
    pet.apply({"cast": {"galya": 0}})
    pet.apply({"cast_state": {"galya": "away"}})
    assert pet.cast["galya"]["st"] == "away"
    pet.apply({"cast_state": {"galya": "teleported"}})   # not a state
    assert pet.cast["galya"]["st"] == "away"


def test_cast_requirement_needs_the_character_around_and_the_bond(pet):
    assert not pet.meets({"cast": {"galya": 0}})
    assert pet.meets({"nocast": "galya"}) and pet.meets({"nocast": ["galya", "ostap"]})
    pet.apply({"cast": {"galya": 2}})
    assert pet.meets({"cast": {"galya": 2}}) and not pet.meets({"cast": {"galya": 3}})
    assert pet.meets({"cast": {"galya": (1, 3)}}) and not pet.meets({"cast": {"galya": (-6, 1)}})
    assert not pet.meets({"nocast": "galya"}) and not pet.meets({"nocast": ["ostap", "galya"]})
    pet.apply({"cast_state": {"galya": "away"}})
    assert not pet.meets({"cast": {"galya": 0}})                       # away: not around
    assert pet.meets({"cast_state": {"galya": "away"}})
    assert pet.meets({"cast": {"galya": 2}, "cast_state": {"galya": "away"}})   # …unless the req names that state
    assert not pet.meets({"cast": {"galya": 3}, "cast_state": {"galya": "away"}})
    assert not pet.meets({"cast_state": {"galya": "gone"}})


def test_known_for_counts_the_pets_years(pet):
    pet.apply({"cast": {"galya": 0}})
    assert not pet.meets({"cast_for": {"galya": 5}})
    pet.years += 5
    assert pet.meets({"cast_for": {"galya": 5}}) and not pet.meets({"cast_for": {"galya": 6}})
    assert not pet.meets({"cast_for": {"ostap": 0}})   # never met


def test_old_documents_load_without_a_cast_and_survive_a_round_trip(pet):
    d = pet.to_dict()
    d.pop("cast")
    assert E.Pet.from_dict(d).cast == {}
    pet.apply({"cast": {"galya": 3, "myron": -2}, "cast_state": {"myron": "away"}})
    again = E.Pet.from_dict(pet.to_dict())
    assert again.cast == pet.cast and again.meets({"cast": {"galya": 3}})


def test_a_retired_character_is_dropped_on_load(pet):
    d = pet.to_dict()
    d["cast"] = {"galya": dict(b=1, since=1, st="here"), "gone_forever": dict(b=1, since=1, st="here"), "ostap": 5}
    assert set(E.Pet.from_dict(d).cast) == {"galya"}


def test_the_cast_list_is_closest_first_and_gone_last(pet):
    pet.apply({"cast": {"galya": 1, "ostap": 4, "myron": 2, "gavryk": 6}, "cast_state": {"gavryk": "gone"}})
    rows = pet.cast_list()
    assert [r["id"] for r in rows] == ["ostap", "myron", "galya", "gavryk"]
    assert rows[0]["word"] == bond_word(4) and rows[-1]["state"] == "gone"
    assert {"id", "name", "who", "icon", "bond", "word", "state", "years"} <= rows[0].keys()


def test_close_characters_show_in_the_life_summary(pet):
    pet.apply({"cast": {"galya": 4, "myron": 1}})
    facts = E.life_summary(pet)["facts"]
    assert any("баба Галя" in f and "Мирон" not in f for f in facts)


def test_every_character_has_a_name_a_gender_and_an_introduction():
    intros = {cid for e in ALL if "nocast" in e.req for cid in ([e.req["nocast"]] if isinstance(e.req["nocast"], str)
                                                             else e.req["nocast"])}
    for cid, c in CAST.items():
        assert c["name"] and c["who"] and c["icon"] and c["gender"] in ("m", "f"), cid
    assert intros == set(CAST), "every character needs an event that introduces them"


def test_the_validator_catches_a_bad_cast(monkeypatch, capsys):
    bad = [ev("bad_cast", "{name}.", ch("Ок", o("Ок.", cast={"ghost": 1, "galya": 99}, cast_state={"galya": "lost"})),
              req=dict(cast={"galya": 0.5}, cast_state={"galya": "elsewhere"}, nocast="ghost"))]
    monkeypatch.setattr(validate, "ALL", bad)
    errors = validate.cast_errors()
    assert any("unknown character 'ghost'" in e for e in errors)
    assert any("must be whole numbers" in e for e in errors)
    assert sum("unknown cast_state" in e for e in errors) == 2


def test_cast_events_come_more_often_than_plain_ones(pet):
    pet.apply({"cast": {"galya": 0}})
    plain = ev("plain_x", "{name}.", ch("Ок", o("Ок.", mood=1)), req=dict(stage=3))
    cast = ev("cast_x", "{name}.", ch("Ок", o("Ок.", mood=1)), req=dict(stage=3, cast={"galya": 0}))
    old = dict(E.EVENTS)
    E.EVENTS.clear()
    E.EVENTS.update({plain.id: plain, cast.id: cast})
    try:
        cands, ws = pet.candidates(None)
    finally:
        E.EVENTS.clear()
        E.EVENTS.update(old)
    w = dict(zip((e.id for e in cands), ws))
    assert w["cast_x"] == pytest.approx(w["plain_x"] * E.CAST_BOOST)


def test_a_life_with_the_cast_plays_through_and_meets_characters():
    """Run many lives on the engine's own dice: characters get introduced, nothing crashes, bonds stay on the scale."""
    met: set[str] = set()
    for seed in range(12):
        rng = random.Random(seed)
        p = E.new_pet(1, seed, "Тест", "cat", [], rng)
        p.hatch(E.now(), rng)
        for _ in range(160):
            if not p.alive:
                break
            e, other = p.pick_event([], rng, "solo")
            if not e:
                continue
            opts = p.options(e, other)
            if not opts:
                continue
            p.resolve(e, rng.choice(opts)[0], other, rng)
            p.years += 0.3
        for r in p.cast.values():
            assert BOND_MIN <= r["b"] <= BOND_MAX and r["st"] in ("here", "away", "gone")
        met |= set(p.cast)
    assert len(met) >= 4, f"only {sorted(met)} were met in 12 lives"
