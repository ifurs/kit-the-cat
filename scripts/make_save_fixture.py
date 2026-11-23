"""Write a golden save: pet documents exactly as THIS checkout's engine serializes them, after a deterministic life.

Run it inside a worktree of an old tag to capture what that version stored, then keep the file in tests/fixtures/:

    git worktree add /tmp/kit-old v0.20.0
    (cd /tmp/kit-old && uv run python /path/to/kit-the-cat/scripts/make_save_fixture.py) > tests/fixtures/pet_v0_20.json
    git worktree remove /tmp/kit-old

Uses only the public API that every 0.20+ version has (new_pet, tick, pick_event, start, auto_choice, resolve, care,
fix_partners, mourn, to_dict) and a virtual clock, so the output depends on the version, the seed and the start date.
tests/test_old_saves.py loads every fixture with the current engine.
"""
import argparse
import json
import random
import sys
from datetime import datetime

from kit_the_cat import engine as E
from kit_the_cat.tz import TZ

START = "2026-03-02"
STEP_H = 3  # game passes every 3 real hours


def life(seed: int, steps: int) -> list[dict]:
    now = [datetime.fromisoformat(START).replace(hour=8, tzinfo=TZ).timestamp()]
    E.clock = lambda: now[0]
    rng = random.Random(seed)
    pets: list[E.Pet] = []
    for i, (owner, species, gender) in enumerate([("Аліса", "cat", "f"), ("Богдан", "dog", "m"), ("Віра", "fox", "f")]):
        pets.append(E.new_pet(-100, i + 1, owner, species, list(pets), rng, gender=gender))
    for step in range(steps):
        now[0] += STEP_H * 3600
        for p in pets:
            p.tick(rng=rng)
        E.fix_partners(pets)
        E.mourn(pets)
        for p in pets:
            if not p.alive:
                continue
            if step % 4 == 0:
                E.care(p, rng.choice(["play", "wash", "pat", "heal"]), rng)
            e, other = p.pick_event(pets, rng)
            if e is None:
                continue
            p.start(e, other)
            if step == steps - 1 and p is pets[0]:
                continue  # leave one pending event in the save: hosts resolve it after an upgrade
            idx, _ = p.auto_choice(e, other, rng)
            p.resolve(e, idx, other, rng)
    return [json.loads(json.dumps(p.to_dict(), ensure_ascii=False)) for p in pets]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seed", type=int, default=20)
    ap.add_argument("--steps", type=int, default=120)  # 15 real days: adult pets with jobs, cast, items, journal
    a = ap.parse_args()
    try:
        from importlib.metadata import version
        ver = version("kit-the-cat")
    except Exception:
        ver = "unknown"
    out = {"version": ver, "seed": a.seed, "steps": a.steps, "start": START, "pets": life(a.seed, a.steps)}
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
