"""Content map: what the 313+ events cover and where it's thin.

    uv run python scripts/content_stats.py            # overview tables
    uv run python scripts/content_stats.py --gaps     # only the weak spots (what to write next)
    uv run python scripts/content_stats.py --strict   # exit 1 on content errors (CI)

Errors: story-chain flag values required somewhere but never set (dead ends), `{other}` outside social events.
Warnings: skill checks whose typical success chance is < 30% for the youngest pet that can see the event
(same formula as Pet.chance, typical skill/level per stage).
"""
import importlib
import sys
from collections import Counter, defaultdict

from kit_the_cat import engine as E
from kit_the_cat.content.dsl import Event
from kit_the_cat.content.economy import JOBS

MODULES = ["life", "daily", "chains", "jobs", "species", "social", "twists", "status", "consequences", "arcs", "arcs_adult", "arcs_soul", "dreams", "health", "arcs_week_20261029", "ages", "youth"]
# typical pet per stage: (skill, luck, level) — skills start 3–20 and grow with stages, jobs and events
TYPICAL = {1: (11, 11, 1), 2: (20, 15, 2), 3: (30, 20, 4), 4: (35, 22, 6)}
MIN_CHANCE = 0.30


def typical_chance(skill: str, diff: int, stage: int) -> float:
    """Pet.chance() for a typical pet of this stage."""
    sk, luck, level = TYPICAL[stage]
    scale = {1: 0.6, 2: 0.8}.get(stage, 1.0)
    v = sk + (luck * 0.15 if skill != "luck" else 0) + (level - 1) * 1.5 - diff * scale
    return max(0.2, min(0.95, 0.5 + v / 50))
GAP = dict(species=4, job=2, role=3, stage=25, trait_auto=60)


def load() -> tuple[list[Event], dict[str, str]]:
    seen: dict[str, Event] = {}
    where: dict[str, str] = {}
    for m in MODULES:
        mod = importlib.import_module(f"kit_the_cat.content.{m}")
        for v in vars(mod).values():
            if isinstance(v, list) and v and isinstance(v[0], Event):
                for e in v:
                    if e.id not in seen:
                        seen[e.id], where[e.id] = e, m
    return list(seen.values()), where


def min_stage(e: Event) -> int:
    s = e.req.get("stage", 1)
    return s[0] if isinstance(s, tuple) else s


def realistic_stage(e: Event) -> int:
    """Youngest stage that can realistically meet the event: jobs, chain flags, marriage, debts and diplomas
    come with adulthood even when the event itself sets no stage; romance statuses start in the teens."""
    r = e.req
    lo = max(min_stage(e), 1)
    if (r.get("job") not in (None, "none")) or any(k in r for k in ("flag", "partner", "debt", "edu")):
        lo = max(lo, 3)
    if set(r.get("status", [])) & {"crush", "partner", "ex"} or r.get("jail"):
        lo = max(lo, 2)
    return lo


def stages(e: Event) -> range:
    s = e.req.get("stage", 1)
    lo, hi = (s if isinstance(s, tuple) else (s, 4))
    return range(max(1, lo), hi + 1)


def outs(e: Event):
    for c in e.choices:
        for o in c.outs + c.fail:
            yield c, o


def analyse(events: list[Event], where: dict[str, str]) -> dict:
    a: dict = defaultdict(Counter)
    errors: list[str] = []
    warnings: list[str] = []
    flags_set: set[tuple[str, int]] = set()
    flags_req: dict[tuple[str, int], list[str]] = defaultdict(list)
    for e in events:
        a["module"][where[e.id]] += 1
        a["kind"]["social" if e.social else "solo"] += 1
        for s in stages(e):
            a["stage"][s] += 1
        for key, bucket in (("species", "species"), ("role", "role"), ("job", "job"), ("season", "season")):
            v = e.req.get(key)
            if v:
                for x in (v if isinstance(v, (list, tuple)) else [v]):
                    a[bucket][str(x)] += 1
        if any(o.fx.get("twist") for _, o in outs(e)):
            a["kind"]["twist"] += 1
        req_flag = e.req.get("flag")
        if isinstance(req_flag, dict):
            for k, v in req_flag.items():
                flags_req[(k, v)].append(e.id)
        texts = [e.text] + [c.label for c in e.choices] + [o.text for _, o in outs(e)]
        if not e.social and any("{other" in t for t in texts):
            errors.append(f"{e.id}: uses {{other}} but is not a social event")
        for c in e.choices:
            a["choices"]["total"] += 1
            a["auto"][c.auto or "—"] += 1
            if c.check:
                skill, diff = c.check
                a["check_skill"][skill] += 1
                lo = realistic_stage(e)
                p = typical_chance(skill, diff, lo)
                if p < MIN_CHANCE:
                    warnings.append(f"{e.id}/«{c.label}»: {skill} {diff} → ~{p:.0%} for a typical {E.STAGES[lo]}")
        for _, o in outs(e):
            f = o.fx.get("flag")
            if isinstance(f, dict):
                flags_set.update(f.items())
            for k in o.fx:
                a["effect"][k] += 1
            if o.w < 0.35:
                a["kind"]["rare outcomes"] += 1
            if o.fx.get("die"):
                a["kind"]["deadly outcomes"] += 1
    for (k, v), ids in sorted(flags_req.items()):
        if (k, v) not in flags_set:
            errors.append(f"flag {k}={v} is required by {', '.join(ids)} but no outcome sets it (dead end)")
    a["errors"], a["warnings"] = errors, warnings
    return a


def show(title: str, c: Counter, limit: int = 40) -> None:
    print(f"\n## {title}")
    for k, n in c.most_common(limit):
        print(f"  {n:4}  {k}")


def gaps(a: dict) -> list[str]:
    out = []
    for sp in sorted(E.SPECIES_NAME):
        if a["species"][sp] < GAP["species"]:
            out.append(f"species {sp}: {a['species'][sp]} events (want ≥ {GAP['species']})")
    for j in JOBS:
        if a["job"][j] < GAP["job"]:
            out.append(f"job {j}: {a['job'][j]} events (want ≥ {GAP['job']})")
    for r in E.ROLES:
        if a["role"][r] < GAP["role"]:
            out.append(f"role {r}: {a['role'][r]} events (want ≥ {GAP['role']})")
    for s in range(1, 5):
        if a["stage"][s] < GAP["stage"]:
            out.append(f"stage {s} ({E.STAGES[s]}): {a['stage'][s]} events available (want ≥ {GAP['stage']})")
    total = a["choices"]["total"]
    for t in E.TRAITS:
        if a["auto"][t] < total * GAP["trait_auto"] / 100 / len(E.TRAITS):
            out.append(f"personality {t}: only {a['auto'][t]} choices express it — pets with this lean rarely act in character")
    return out


def main() -> None:
    events, where = load()
    a = analyse(events, where)
    if "--gaps" not in sys.argv:
        print(f"# Content: {len(events)} events, {a['choices']['total']} choices")
        show("By module", a["module"])
        show("By kind", a["kind"])
        show("Available at stage", Counter({f"{s} {E.STAGES[s]}": n for s, n in sorted(a["stage"].items())}))
        show("Species-specific", a["species"])
        show("Job events", a["job"])
        show("Role events", a["role"])
        show("Seasonal", a["season"])
        show("Choice personality (auto=)", a["auto"])
        show("Skill checks", a["check_skill"])
        show("Most used effects", a["effect"], 20)
    g = gaps(a)
    print("\n## Gaps (what to write next)")
    print("\n".join(f"  - {x}" for x in g) or "  none")
    print("\n## Warnings (hard checks for young pets)")
    print("\n".join(f"  - {x}" for x in a["warnings"]) or "  none")
    print("\n## Errors")
    print("\n".join(f"  - {x}" for x in a["errors"]) or "  none")
    if "--strict" in sys.argv and a["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
