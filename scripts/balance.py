"""Headless balance run: a neighbourhood of pets lives N game days, then the numbers are checked against targets.

    uv run python scripts/balance.py                       # 24 pets, 40 days, seed 1
    uv run python scripts/balance.py --pets 40 --days 60 --neglect 0.25 --seed 7
    uv run python scripts/balance.py --json out.json       # machine-readable report

Uses the real sandbox (engine, content, autopilot owners): `--neglect` is the share of owners who never take a sick
pet to the doctor. Upkeep is automatic, so lives end by old age, debt or events. No Telegram, no network.
Exit code 1 if a target is badly missed.
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

MIN_DEATHS = 10  # death-based shares are "n/a" below this (one unlucky death in a tiny run is noise)
# (low, high): outside → WARN; far outside (×0.5 / ×1.5) → FAIL
TARGETS = {
    "life_years": (65, 95),                  # median age at death, years
    "life_real_days": (22, 42),              # …and how many real days such a life takes
    "early_death_share": (0.0, 0.25),        # died before 40 years (debt, events, sickness)
    "debt_share": (0.0, 0.25),               # living adults in debt at the end
    "tier2_share": (0.35, 1.0),              # lives that reached tier 2 of some life stat (the new content fires)
    "check_success": (0.45, 0.70),           # dice checks: hopeful, not trivial
    "event_coverage": (0.55, 1.0),           # share of content that actually fires in the run
    "money_median": (150, 6000),             # living pets' wallets
    "event_deaths_share": (0.0, 0.15),       # deaths by events (vs debt/age): rare and dramatic
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
                    deaths.append(dict(owner=p.owner_id, age=p.age_days, years=p.years, cause=p.cause,
                                       neglected=p.owner_id in neglected,
                                       tier2=any(p.counters.get(f"tier_{k}", 0) >= 2 for k in E.LIFE),
                                       event=not any(w in p.cause for w in ("борг", "старост", "туг", "сну", "пенсі"))))
            # heirs keep the neighbourhood populated, like real owners pressing "спадкоємець"
            for p in await sb.pets(tick=False):
                if p.state == "dead" and p.owner_id >= NPC_BASE:
                    await sb.heir(p.owner_id)
        final = await sb.pets(tick=False)
    finally:
        E.Pet.resolve, Sandbox._autocare = orig, orig_care

    alive = [p for p in final if p.alive]
    adults = [p for p in alive if p.stage >= 3]
    total_checks = checks["ok"] + checks["fail"]
    if len(deaths) < MIN_DEATHS:  # too few lives ended to judge death-based shares
        deaths_for_stats: list[dict] = []
    else:
        deaths_for_stats = deaths
    m = dict(
        life_years=statistics.median(d["years"] for d in deaths) if deaths else None,
        life_real_days=statistics.median(d["age"] for d in deaths) if deaths else None,
        early_death_share=sum(d["years"] < 40 for d in deaths_for_stats) / len(deaths_for_stats) if deaths_for_stats else None,
        debt_share=sum(p.money < 0 for p in adults) / len(adults) if adults else None,
        tier2_share=sum(d["tier2"] for d in deaths_for_stats) / len(deaths_for_stats) if deaths_for_stats else None,
        check_success=checks["ok"] / total_checks if total_checks else None,
        event_coverage=len(fired) / len(E.EVENTS),
        money_median=statistics.median([p.money for p in alive]) if alive else None,
        event_deaths_share=sum(d["event"] for d in deaths_for_stats) / len(deaths_for_stats) if deaths_for_stats else None,
    )
    return dict(
        params=dict(pets=pets, days=days, neglect=neglect, seed=seed), seconds=round(time.time() - t0, 1),
        metrics=m, events_resolved=sum(fired.values()), deaths=len(deaths),
        causes=Counter(d["cause"] for d in deaths).most_common(8),
        roles=Counter(p.role for p in final if p.role).most_common(),
        jobs=Counter(p.job for p in final if p.job).most_common(8),
        stages=Counter(E.STAGES[p.stage] for p in alive).most_common(),
        tiers={k: Counter(p.tier_name(k, p.counters.get(f"tier_{k}", 0)) for p in final).most_common()
               for k in ("money", *E.LIFE)},
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
        shown = "—" if v is None else (f"{v:.0%}" if k.endswith(("share", "success", "coverage")) else f"{v:.1f}")
        print(f"  {vd:4}  {k:20} {shown:>8}   target {lo:g}–{hi:g}")
    print(f"\ncauses of death: {rep['causes']}\nroles: {rep['roles']}\njobs: {rep['jobs']}\nalive by stage: {rep['stages']}")
    print("peak tiers:\n" + "\n".join(f"  {k}: {v}" for k, v in rep["tiers"].items()))
    print(f"\nnever fired: {rep['never_fired_total']} (first 40): {', '.join(rep['never_fired'])}")
    if a.json:
        with open(a.json, "w") as f:
            json.dump(rep, f, ensure_ascii=False, indent=2, default=str)
    if worst == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
