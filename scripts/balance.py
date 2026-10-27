"""Headless balance run: a neighbourhood of pets lives N game days, then the numbers are checked against targets.

    uv run python scripts/balance.py                       # 24 pets, 40 days, seed 1
    uv run python scripts/balance.py --pets 40 --days 60 --neglect 0.25 --seed 7
    uv run python scripts/balance.py --json out.json       # machine-readable report

Uses the real sandbox (engine, content, autopilot owners): `--neglect` is the share of owners who never care
(their pets show how fast neglect kills). No Telegram, no network. Exit code 1 if a target is badly missed.
"""
import argparse
import asyncio
import json
import random
import statistics
import time
from collections import Counter

from kit_the_cat import engine as E
from kit_the_cat.sandbox.game import NPC_BASE, Sandbox
from kit_the_cat.storage import MemoryStore

# (low, high): outside → WARN; far outside (×0.5 / ×1.5) → FAIL
TARGETS = {
    "neglect_death_days": (2.0, 5.0),        # forgotten pets die in ~3 days: harsh but fair
    "cared_alive_share": (0.75, 1.0),        # cared pets mostly survive the run (old age comes ~24–36 days)
    "check_success": (0.45, 0.70),           # dice checks: hopeful, not trivial
    "event_coverage": (0.55, 1.0),           # share of content that actually fires in the run
    "money_median": (150, 6000),             # living pets' wallets
    "event_deaths_share": (0.0, 0.15),       # deaths by events (vs hunger/dirt/age): rare and dramatic
}


async def run(pets: int, days: float, neglect: float, seed: int) -> dict:
    rng = random.Random(seed)
    store = MemoryStore()
    sb = Sandbox(store, seed)
    await sb.init()
    fired: Counter = Counter()
    checks = Counter()
    orig = E.Pet.resolve

    def resolve(self, e, idx, other, r):
        res = orig(self, e, idx, other, r)
        fired[e.id] += 1
        if res.ok is not None:
            checks["ok" if res.ok else "fail"] += 1
        return res

    E.Pet.resolve = resolve
    neglected = set()
    orig_care = Sandbox._autocare

    def autocare(self, p):
        if p.owner_id not in neglected:
            orig_care(self, p)

    Sandbox._autocare = autocare
    try:
        await sb.add_npcs(pets)
        owners = [p.owner_id for p in await sb.pets(tick=False)]
        neglected.update(rng.sample(owners, round(len(owners) * neglect)))
        t0 = time.time()
        deaths: list[dict] = []
        seen_dead: set[str] = set()
        for _ in range(int(days)):
            await sb.advance(24, auto_me=False, care_me=False)
            for p in await sb.pets(tick=False):
                if p.state == "dead" and p.pid not in seen_dead:
                    seen_dead.add(p.pid)
                    deaths.append(dict(owner=p.owner_id, age=p.age_days, cause=p.cause, neglected=p.owner_id in neglected,
                                       event=not any(w in p.cause for w in ("голод", "бруд", "старост", "туг", "сну", "пенсі"))))
            # heirs keep the neighbourhood populated, like real owners pressing "спадкоємець"
            for p in await sb.pets(tick=False):
                if p.state == "dead" and p.owner_id >= NPC_BASE:
                    await sb.heir(p.owner_id)
        final = await sb.pets(tick=False)
    finally:
        E.Pet.resolve, Sandbox._autocare = orig, orig_care

    alive = [p for p in final if p.alive]
    cared = [p for p in final if p.owner_id not in neglected]
    neglect_deaths = [d["age"] for d in deaths if d["neglected"]]
    total_checks = checks["ok"] + checks["fail"]
    m = dict(
        neglect_death_days=statistics.median(neglect_deaths) if neglect_deaths else None,
        cared_alive_share=sum(p.alive for p in cared) / len(cared) if cared else None,
        check_success=checks["ok"] / total_checks if total_checks else None,
        event_coverage=len(fired) / len(E.EVENTS),
        money_median=statistics.median([p.money for p in alive]) if alive else None,
        event_deaths_share=sum(d["event"] for d in deaths) / len(deaths) if deaths else 0.0,
    )
    return dict(
        params=dict(pets=pets, days=days, neglect=neglect, seed=seed), seconds=round(time.time() - t0, 1),
        metrics=m, events_resolved=sum(fired.values()), deaths=len(deaths),
        causes=Counter(d["cause"] for d in deaths).most_common(8),
        roles=Counter(p.role for p in final if p.role).most_common(),
        jobs=Counter(p.job for p in final if p.job).most_common(8),
        stages=Counter(E.STAGES[p.stage] for p in alive).most_common(),
        never_fired=sorted(set(E.EVENTS) - set(fired))[:40], never_fired_total=len(set(E.EVENTS) - set(fired)),
        top_events=fired.most_common(10),
    )


def verdict(name: str, v) -> str:
    if v is None:
        return "n/a"
    lo, hi = TARGETS[name]
    if lo <= v <= hi:
        return "OK"
    return "FAIL" if v < lo * 0.5 or v > hi * 1.5 else "WARN"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pets", type=int, default=24)
    ap.add_argument("--days", type=float, default=40)
    ap.add_argument("--neglect", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--json", help="also write the report as JSON")
    a = ap.parse_args()
    rep = asyncio.run(run(a.pets, a.days, a.neglect, a.seed))
    print(f"# Balance: {a.pets} pets × {a.days:g} days (neglect {a.neglect:.0%}, seed {a.seed}) in {rep['seconds']} s")
    print(f"events resolved: {rep['events_resolved']} · deaths: {rep['deaths']}\n")
    worst = "OK"
    for k, v in rep["metrics"].items():
        vd = verdict(k, v)
        worst = "FAIL" if vd == "FAIL" else ("WARN" if vd == "WARN" and worst == "OK" else worst)
        lo, hi = TARGETS[k]
        shown = "—" if v is None else (f"{v:.0%}" if isinstance(v, float) and v <= 1 and k != "neglect_death_days" else f"{v:.1f}")
        print(f"  {vd:4}  {k:20} {shown:>8}   target {lo:g}–{hi:g}")
    print(f"\ncauses of death: {rep['causes']}\nroles: {rep['roles']}\njobs: {rep['jobs']}\nalive by stage: {rep['stages']}")
    print(f"\nnever fired: {rep['never_fired_total']} (first 40): {', '.join(rep['never_fired'])}")
    if a.json:
        with open(a.json, "w") as f:
            json.dump(rep, f, ensure_ascii=False, indent=2, default=str)
    if worst == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
