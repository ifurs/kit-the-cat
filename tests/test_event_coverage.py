"""scripts/event_coverage.py finds events that can never happen — and lets every real one through."""
import sys
from pathlib import Path

import pytest

from kit_the_cat import engine as E
from kit_the_cat.content.dsl import ch, ev, o

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import event_coverage as C  # noqa: E402


def analyse(monkeypatch, *events):
    monkeypatch.setattr(E, "EVENTS", {e.id: e for e in events})
    return C.analyse()


def plain(id_, **kw):
    return ev(id_, "{name} живе.", ch("Ок", o("Ок.", mood=1)), **kw)


def test_real_content_has_no_unreachable_events():
    assert C.analyse()["unreachable"] == {}


def test_a_chain_is_reachable_through_its_root(monkeypatch):
    root = ev("root", "Старт.", ch("Так", o("Прапорець і наслідок.", flag={"quest": 1}, then=("later", "2y"))), req=dict(stage=3))
    later = plain("later", followup=True, req=dict(stage=3, flag={"quest": 1}))
    gated = plain("gated", req=dict(flag={"quest": 1}))
    rep = analyse(monkeypatch, root, later, gated)
    assert rep["unreachable"] == {}
    assert rep["reachable"] == 3


def test_a_follow_up_nobody_schedules_is_unreachable(monkeypatch):
    rep = analyse(monkeypatch, plain("orphan", followup=True), plain("free"))
    assert list(rep["unreachable"]) == ["orphan"]
    assert "no outcome schedules" in rep["unreachable"]["orphan"]


def test_a_flag_nobody_sets_is_unreachable(monkeypatch):
    rep = analyse(monkeypatch, plain("needs_flag", req=dict(flag={"ghost": 2})),
                  plain("sets_wrong", req=dict(stage=3)),
                  ev("root", "Старт.", ch("Так", o("Не те значення.", flag={"ghost": 1})), req=dict(stage=3)))
    assert list(rep["unreachable"]) == ["needs_flag"]


def test_contradictory_requirements_are_unreachable(monkeypatch):
    rep = analyse(monkeypatch, plain("teen_adult", req=dict(stage=(2, 2), years=(30, 40))),
                  plain("flag_and_not", req=dict(flag="x", noflag="x")),
                  plain("fine", req=dict(stage=(3, 4))))
    assert set(rep["unreachable"]) == {"teen_adult", "flag_and_not"}


def test_a_follow_up_that_dies_before_it_is_due_is_unreachable(monkeypatch):
    # scheduled by a teenager, needed by the elderly: even 15 years of waiting never reach 60
    root = ev("root", "Старт.", ch("Так", o("Колись.", then=("old", "10y"))), req=dict(stage=(2, 2)))
    old = plain("old", followup=True, req=dict(stage=4))
    rep = analyse(monkeypatch, root, old)
    assert list(rep["unreachable"]) == ["old"]
    assert "needs" in rep["unreachable"]["old"]


def test_a_follow_up_its_own_root_makes_ineligible_is_unreachable(monkeypatch):
    root = ev("root", "Старт.", ch("Так", o("Прапорець.", flag="spoiled", then=("later", "1y"))), req=dict(stage=3))
    later = plain("later", followup=True, req=dict(stage=3, noflag="spoiled"))
    rep = analyse(monkeypatch, root, later)
    assert list(rep["unreachable"]) == ["later"]
    assert "not eligible when due" in rep["unreachable"]["later"]


def test_story_steps_with_variables_are_reachable(monkeypatch):
    start = ev("s1", "Крок 1.", ch("Добре", o("Так.", sv={"kind": 2}, step=["s_good", "s_fallback"])),
               ch("Байдуже", o("Ні.", step=["s_good", "s_fallback"])), req=dict(stage=3), story="Казка")
    good = ev("s_good", "Гарний кінець.", ch("Ок", o("Ок.", mood=1)), followup=True, req=dict(sv={"kind": 2}), story="Казка")
    fallback = ev("s_fallback", "Звичайний кінець.", ch("Ок", o("Ок.", mood=1)), followup=True, story="Казка")
    rep = analyse(monkeypatch, start, good, fallback)
    assert rep["unreachable"] == {}
    only_good = ev("s2", "Крок 1.", ch("Добре", o("Так.", sv={"kind": 2}, step=["s_good", "s_fallback"])), req=dict(stage=3),
                   story="Казка")
    assert list(analyse(monkeypatch, only_good, good, fallback)["unreachable"]) == ["s_fallback"]   # no path skips the sv


@pytest.mark.parametrize("req", [dict(status=["partner"]), dict(partner=True)])
def test_a_relationship_nobody_forms_is_unreachable(monkeypatch, req):
    rep = analyse(monkeypatch, ev("couple", "{name} і {other}.", ch("Ок", o("Ок.", mood=1)), social=True, req=req))
    assert list(rep["unreachable"]) == ["couple"]
