"""Golden old saves: pet documents written by released versions must keep loading, living and rendering.

tests/fixtures/pet_v0_*.json were produced by scripts/make_save_fixture.py run inside a worktree of that tag (see its
docstring). Never regenerate an old fixture with the current code: the point is what the OLD engine stored. A failure
here means hosts' saved pets break on upgrade — a major bump per CONTRIBUTING.md, or (better) a fix in Pet.from_dict.
"""
import json
import random
from pathlib import Path

import pytest

from kit_the_cat import card, engine as E, sprites as S

FIXTURES = sorted((Path(__file__).parent / "fixtures").glob("pet_v*.json"))
STEP = 3 * 3600


def test_fixtures_present():
    assert len(FIXTURES) >= 3, "golden saves missing from tests/fixtures/"


@pytest.fixture(params=FIXTURES, ids=lambda p: p.stem)
def save(request, monkeypatch):
    data = json.loads(request.param.read_text(encoding="utf-8"))
    last = max(e[0] for d in data["pets"] for e in d.get("log", []) if isinstance(e, list) and e)
    now = [float(last) + STEP]
    monkeypatch.setattr(E, "clock", lambda: now[0])
    return data, now


def test_old_save_loads_ticks_and_renders(save):
    data, now = save
    pets = [E.Pet.from_dict(d) for d in data["pets"]]
    assert [p.name for p in pets] == [d["name"] for d in data["pets"]]
    assert all(p.alive for p in pets)
    rng = random.Random(1)
    by_pid = {p.pid: p for p in pets}
    for p in pets:  # a pending event stored by the old version is resolved by the new one
        if p.pending and p.pending.get("id") in E.EVENTS:
            e, other = E.EVENTS[p.pending["id"]], by_pid.get(p.pending.get("other", ""))
            idx, _ = p.auto_choice(e, other, rng)
            p.resolve(e, idx, other, rng)
            p.pending = {}
    for _ in range(4):
        now[0] += STEP
        for p in pets:
            p.tick(rng=rng)
        E.fix_partners(pets)
        E.mourn(pets)
        for p in pets:
            if not p.alive:
                continue
            e, other = p.pick_event(pets, rng)
            if e is not None:
                p.start(e, other)
                p.resolve(e, p.auto_choice(e, other, rng)[0], other, rng)
    for p in pets:
        assert E.card(p, {})
        assert E.income_line(p) is not None
        assert card.render_life_card(p.look(), E.life_summary(p, {}))[:4] == b"\x89PNG"
        assert S.frame_canvases(p.look(), 1)
        p.cast_list()
        again = E.Pet.from_dict(json.loads(json.dumps(p.to_dict(), ensure_ascii=False)))
        assert again.to_dict() == p.to_dict()


def test_old_save_renders_images(save):
    pytest.importorskip("PIL")
    data, _ = save
    for d in data["pets"]:
        lk = E.Pet.from_dict(d).look()
        assert S.render_png(lk)[:4] == b"\x89PNG"
        assert S.render_gif(lk)[:3] == b"GIF"
