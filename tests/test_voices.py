"""The pet's inner voice (content/voices.py, Pet.inner_voice): every temperament has one, both genders read well."""
import random

from kit_the_cat import engine as E
from kit_the_cat.content.persona import TEMPERAMENTS
from kit_the_cat.content.voices import VOICES
from kit_the_cat.grammar import template_errors


def pet(temper: str, gender: str = "m") -> E.Pet:
    p = E.new_pet(1, 1, "Оля", "cat", [], random.Random(3), gender=gender)
    p.persona["temper"], p.persona["lean"] = next((t, lean) for t, lean in TEMPERAMENTS if t == temper)
    return p


def test_every_temperament_has_a_voice():
    assert set(VOICES) == {t for t, _ in TEMPERAMENTS}
    for t, lean in TEMPERAMENTS:
        assert len(VOICES[t]["any"]) >= 4, t
        assert len(VOICES[t].get("push", [])) >= (2 if lean else 0), t
        assert set(VOICES[t]) <= {"any", "push"}, t


def test_lines_are_short_clean_and_gender_safe():
    for t, groups in VOICES.items():
        for lines in groups.values():
            assert len(set(lines)) == len(lines), t
            for line in lines:
                assert not template_errors(line), (t, line)
                for g in ("m", "f"):
                    out = pet(t, g).fmt(line)
                    assert "{" not in out and "}" not in out and len(out) <= 90, (t, g, out)


def test_voice_is_stable_and_sometimes_silent():
    p = pet("ботан")
    events = list(E.EVENTS.values())[:300]
    seen = [p.inner_voice(e) for e in events]
    assert seen == [p.inner_voice(e) for e in events]  # the same event shows the same line
    share = sum(1 for s in seen if s) / len(seen)
    assert 0.25 < share < 0.55, share


def test_voice_never_over_a_grave_event():
    grave = [e for e in E.EVENTS.values() if E.is_grave_event(e)]
    assert len(grave) > 50 and {"army_join", "army_trench"} <= {e.id for e in grave}
    assert any("die" in x.fx for e in grave for c in e.choices for x in c.outs + c.fail)
    for t in VOICES:
        p = pet(t)
        assert all(p.inner_voice(e) == "" for e in grave)


def test_voice_leans_towards_the_character_choice():
    p = pet("лінивий")  # leans to «glutton»
    pushes = set(VOICES["лінивий"]["push"])
    with_lean = [e for e in E.EVENTS.values() if any(p.in_character(c) for c in e.choices)]
    assert with_lean
    lines = [p.inner_voice(e) for e in with_lean]
    assert any(s in pushes for s in lines) and any(s in VOICES["лінивий"]["any"] for s in lines)
    others = [e for e in E.EVENTS.values() if not any(p.in_character(c) for c in e.choices)]
    assert not any(p.inner_voice(e) in pushes for e in others)


def test_girl_voice_is_feminine():
    p = pet("вічний студент", "f")
    p.persona["temper"] = "вічний студент"
    out = [p.fmt(s) for s in VOICES["вічний студент"]["any"]]
    assert any("готова" in s for s in out) and not any("готовий" in s for s in out)
