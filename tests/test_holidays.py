"""Holiday events: the named windows know their dates, and each holiday event really comes up in its own days."""
import random
from datetime import datetime

import pytest

from kit_the_cat import engine as E
from kit_the_cat.content import dsl
from kit_the_cat.content.holidays import HOLIDAY_EVENTS

OWN = [e for e in HOLIDAY_EVENTS if not e.followup]


def _at(monkeypatch, month: int, day: int, hour: int = 14) -> None:
    ts = datetime(2027, month, day, hour, tzinfo=E.TZ).timestamp()
    monkeypatch.setattr(E, "clock", lambda: ts)


def _pet(stage: int = 3, owner: int = 1) -> E.Pet:
    p = E.Pet(chat_id=-1, owner_id=owner, name="Бублик", owner_name="Оля")
    p.state, p.stage, p.hatched, p.last_tick, p.years, p.money = "alive", stage, E.now(), E.now(), 5.0 * stage, 500
    p.skills = {s: 30 for s in E.SKILLS}
    p.persona = {"temper": "x", "dream": "y", "fear": "z", "food": "сало", "quirk": "q"}
    return p


def test_the_contract_lists_every_named_window():
    assert dsl.SEASONS == set(E.HOLIDAYS) | set(E.SEASON_OF_MONTH.values())


@pytest.mark.parametrize("holiday,inside,outside", [
    ("malanka", (1, 13), (1, 20)), ("vyshyvanka", (5, 20), (6, 1)), ("pokrova", (10, 14), (10, 20)),
    ("easter", (4, 12), (7, 1)), ("kupala", (7, 7), (8, 1)), ("independence", (8, 24), (9, 5)),
    ("halloween", (10, 31), (11, 10)), ("valentine", (2, 14), (3, 1)), ("christmas", (1, 7), (1, 20)),
])
def test_a_window_holds_its_date(monkeypatch, holiday, inside, outside):
    _at(monkeypatch, *inside)
    assert E.in_season(holiday)
    _at(monkeypatch, *outside)
    assert not E.in_season(holiday)


def test_every_holiday_event_is_tied_to_a_known_season():
    for e in OWN:
        assert e.req.get("season") in dsl.SEASONS, e.id


@pytest.mark.parametrize("event", OWN, ids=lambda e: e.id)
def test_a_holiday_event_is_eligible_in_its_days_and_not_outside(monkeypatch, event):
    stage = max(event.req["stage"][0], 2) if isinstance(event.req.get("stage"), tuple) else 3
    p = _pet(stage)
    other = _pet(stage, owner=2) if event.social else None
    hour = 1 if event.req.get("night") else 14
    _at(monkeypatch, *E.HOLIDAYS[event.req["season"]][0], hour=hour)
    assert p.eligible(event, other, fresh=False), f"{event.id} is not eligible inside its own window"
    _at(monkeypatch, 9, 15, hour=hour)     # mid-September: no holiday window covers it
    assert not p.eligible(event, other, fresh=False)


@pytest.mark.parametrize("holiday,day", [("christmas", (12, 22)), ("malanka", (1, 13)), ("valentine", (2, 14)),
                                         ("easter", (4, 12)), ("vyshyvanka", (5, 18)), ("independence", (8, 24)),
                                         ("pokrova", (10, 14)), ("halloween", (10, 31))])
def test_holiday_events_are_a_visible_share_of_a_holiday(monkeypatch, holiday, day):
    _at(monkeypatch, *day)
    mine = {e.id for e in OWN if e.req["season"] == holiday}
    rng = random.Random(7)
    hits = sum(1 for _ in range(600) if (pick := _pet(3).pick_event([], rng, "solo")[0]) and pick.id in mine)
    assert hits >= 600 * 0.02, f"{holiday}: only {hits}/600 picks were its events"
