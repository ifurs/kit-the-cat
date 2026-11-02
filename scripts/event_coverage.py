"""Event coverage: which events can actually happen, and why the balance run never sees some of them.

    uv run python scripts/event_coverage.py               # report: unreachable, waiting for their root, rare
    uv run python scripts/event_coverage.py --strict      # exit 1 if any event is truly unreachable (CI gate)
    uv run python scripts/event_coverage.py --sim         # also run the balance simulation and split its «never fired»
    uv run python scripts/event_coverage.py --json out.json

The 40-day balance run (`balance.py`) lives ~25 pets through ~3000 events out of ~750, from one calendar date, without
hiring, so it never fires many events: seasonal and holiday ones, jobs and roles, whole story chains. That says
nothing about the content. This tool answers the real question without dice, in three steps:

1. **Forge.** For every event it builds a pet that meets the event's `req` (and one choice's `req`) on a date that fits
   `season=`/`night=`, and asks the engine itself (`Pet.eligible`). A pet that cannot be forged means contradictory
   or impossible requirements → *unreachable*.
2. **Graph.** Story state has producers: a `flag=` value, a `role`, an `edu`, an item, a job. An event that needs
   a state nobody can produce is *unreachable*; so is a follow-up (`followup=True`) that no outcome schedules with
   `then=`/`step=`, or whose only roots are unreachable themselves. Reachability is a fixed point from the events
   that need no story state.
3. **Weight.** For a forged pet the share of the event among everything the pet could live
   (`Pet.candidates`) says how rare it is when its situation holds → *rare* below RARE_SHARE.

Categories of an event: `reachable` (fine, even if the balance run never saw it), `waiting` (a follow-up whose root
is reachable: it needs its root to fire first), `unreachable` (a content error — the gate fails), plus the
`rare` warning. With `--sim` the balance run's never-fired events are split along these categories.
"""
import argparse
import asyncio
import json
import random
import copy
import sys
from collections import defaultdict, deque
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from kit_the_cat import engine as E
from kit_the_cat.content.economy import JOBS
from kit_the_cat.tz import TZ

RARE_SHARE = 0.0005   # < 0.05% of the pet's pool when the situation holds: about once in 2000 events
STAGE_AGE = {1: (0, 12), 2: (12, 18), 3: (18, 60), 4: (60, 95)}
SEASON_DATE = {"winter": (1, 15), "spring": (4, 15), "summer": (7, 15), "autumn": (10, 15)}
STATE_KEYS = ("flag", "role", "edu", "has", "job")   # story state that something has to produce
YEAR = 2026


# --- calendar -----------------------------------------------------------------------------------

@contextmanager
def clock(month: int, day: int, hour: int):
    """The engine clock stands still at that Kyiv date and hour."""
    ts = datetime(YEAR, month, day, hour, 30, tzinfo=TZ).timestamp()
    old = E.clock
    E.clock = lambda: ts
    try:
        yield ts
    finally:
        E.clock = old


def date_for(req: dict) -> tuple[int, int, int]:
    """A (month, day, hour) when season= and night= of the req hold."""
    v = req.get("season")
    m, d = 6, 10
    if v is not None:
        x = [v] if isinstance(v, (str, int)) else list(v)
        x = x[0]
        if isinstance(x, int):
            m, d = x, 15
        elif x in E.HOLIDAYS:
            (m, d), _ = E.HOLIDAYS[x]
            d += 1
        else:
            m, d = SEASON_DATE[x]
    return m, d, 23 if req.get("night") else 12


# --- forging a pet that meets a req ---------------------------------------------------------------

def _first(v):
    return v if isinstance(v, str) else list(v)[0]


def age_window(req: dict) -> tuple[float, float] | None:
    """The hull of the ages (years) at which the age requirements (stage, phase, years) hold, or None if they exclude
    one another."""
    s = req.get("stage", 1)
    s0, s1 = s if isinstance(s, (tuple, list)) else (s, 4)
    lo, hi = STAGE_AGE[max(s0, 1)][0], STAGE_AGE[min(s1, 4)][1]
    if "years" in req:
        lo, hi = max(lo, req["years"][0]), min(hi, req["years"][1])
    spans = [E.PHASES[p] for p in ([req["phase"]] if isinstance(req.get("phase"), str) else req.get("phase", []))]
    if spans:
        spans = [(max(lo, a), min(hi, b)) for a, b in spans if max(lo, a) < min(hi, b)]
        if not spans:
            return None
        lo, hi = min(a for a, _ in spans), max(b for _, b in spans)
    return None if lo >= hi else (lo, min(hi, 95.0))


def years_for(req: dict) -> float | None:
    """An age in years inside every age requirement (stage, phase, years), or None."""
    w = age_window(req)
    return None if w is None else round(w[0] + (w[1] - w[0]) / 2, 2)


def fit(p: E.Pet, req: dict, *, story: bool = True) -> E.Pet | None:
    """Make `p` meet the requirements it can meet by living on (age, skills, traits, money, life stats, a partner…) and,
    with `story`, the story state too (flags, education, an item, a role, a job). Returns the other pet of a social
    event. The engine stays the judge: the caller asks `eligible`. Needs the clock (see clock())."""
    t = E.now()
    y = years_for(req)
    if y is not None:
        p.years, p.lifespan = y, max(p.lifespan, y + 5)
        p.stage = max([1] + [st for st, yrs in E.STAGE_YEARS.items() if y >= yrs])
        p.hatched = t - max(y * 5, 1) * E.DAY / E.SPEED
    if "age" in req:
        p.hatched = t - max(req["age"][0], 1) * E.DAY / E.SPEED
    for k, v in req.items():
        if k == "flag" and story:
            p.flags.update(v if isinstance(v, dict) else {f: 1 for f in ([v] if isinstance(v, str) else v)})
        elif k == "trait":
            for tr, n in v.items():
                p.traits[tr] = max(p.traits.get(tr, 0), n)
        elif k == "skill":
            for s, n in v.items():
                p.skills[s] = max(p.skills.get(s, 10), n + 15)   # headroom for temperament perks
        elif k == "goal":
            p.persona["goal"] = v
        elif k == "money":
            p.money = max(p.money, v)
        elif k == "debt":
            p.money = -v - 1
        elif k == "job" and (story or v in ("none", "any") or natural("job", _first(v))):
            p.job = "" if v == "none" else "atb" if v == "any" else _first(v)
        elif k == "edu" and story:
            p.edu = [v]
        elif k == "has" and (story or natural("has", v)):
            p.items = [v]
        elif k == "jail":
            p.jail_until = t + 1000 * E.hour() if v else 0
        elif k == "life":
            for s, n in v.items():
                p.life[s] = max(p.life.get(s, 0), n)
        elif k == "tier":
            for s, n in v.items():
                if s == "money":
                    p.money = max(p.money, E.MONEY_TIERS[n][0])
                else:
                    p.life[s] = max(p.life.get(s, 0), E.LIFE_STEPS[n])
        elif k == "tier_max":
            if v.get("money") == 0:
                p.money = -1
        elif k == "low":
            for s, n in v.items():
                setattr(p, s, n / 2)
        elif k == "role" and (story or v == "any" or natural("role", _first(v))):
            p.role = "vampire" if v == "any" else _first(v)
        elif k == "sv" and story:
            p.tale = dict(vars={var: (w[0] if isinstance(w, (tuple, list)) else w) for var, w in v.items()},
                          path=[], fx={}, title="", id="")
    rng = random.Random(0)
    other = None
    if any(k in req for k in ("status", "other_stage", "other_role", "other_stage_max", "other_partner")) or req.get("social"):
        other = E.new_pet(1, 2, "Інший", "dog", [p], rng)
        other.hatch(t, rng)
        other.years = p.years
        o_lo = req.get("other_stage", 1)
        o_lo = o_lo[0] if isinstance(o_lo, (tuple, list)) else o_lo
        other.stage = max(o_lo, p.stage, 1)
        if "other_stage_max" in req:
            other.stage = min(max(o_lo, 1), req["other_stage_max"])
        if "other_role" in req:
            other.role = "vampire" if req["other_role"] == "any" else _first(req["other_role"])
        if "other_partner" in req:
            other.partner = "9:9" if req["other_partner"] else ""
        if "status" in req:
            p.status[other.pid] = _first(req["status"])
    if req.get("partner") and other:
        p.partner = other.pid
    elif req.get("partner"):
        p.partner = "9:9"
    return other


def new_pet(species: str = "cat") -> E.Pet:
    rng = random.Random(0)
    p = E.new_pet(1, 1, "Тест", species, [], rng)
    p.hatch(E.now(), rng)
    return p


def choice_req(e: E.Event, c) -> dict:
    """The req of the event with one choice's req merged in (the event's wins on a clash)."""
    req = dict(e.req)
    for k, v in (c.req if c else {}).items():
        if isinstance(v, dict) and isinstance(req.get(k), dict) and k in ("flag", "trait", "skill", "life", "tier"):
            req[k] = {**req[k], **v}
        else:
            req.setdefault(k, v)
    return req


def satisfiable(e: E.Event) -> tuple[E.Pet, E.Pet | None, int] | None:
    """A pet that can live `e` now — with `e`'s req and the req of at least one choice — or None."""
    for c in e.choices or [None]:
        req = choice_req(e, c)
        if years_for(req) is None:
            continue
        with clock(*date_for(req)) as t:
            p = new_pet(_first(req["species"]) if "species" in req else "cat")
            other = fit(p, dict(req, social=e.social))
            if p.eligible(e, other, fresh=False):
                return p, other, t
    return None


# --- the graph --------------------------------------------------------------------------------------

def outs(e: E.Event):
    for c in e.choices:
        yield from c.outs + c.fail


def producers(events: dict[str, E.Event]) -> dict:
    """What each kind of story state is given by: {"flag": {(k, v): {event ids}}, "role": {...}, ...}; plus who
    schedules whom ("sched": {follow-up id: {root ids}})."""
    prod: dict = {"flag": defaultdict(set), "role": defaultdict(set), "edu": defaultdict(set), "has": defaultdict(set),
                  "job": defaultdict(set), "sched": defaultdict(set), "status": defaultdict(set)}
    for e in events.values():
        for o in outs(e):
            fx = o.fx
            f = fx.get("flag")
            if isinstance(f, dict):
                for k, v in f.items():
                    prod["flag"][(k, v)].add(e.id)
            elif f:
                for k in ([f] if isinstance(f, str) else f):
                    prod["flag"][(k, 1)].add(e.id)
            for key in ("role", "edu", "job"):
                if fx.get(key):
                    prod[key][fx[key]].add(e.id)
            for it in ([fx["item"]] if isinstance(fx.get("item"), str) else fx.get("item", [])):
                prod["has"][it.split("@")[0]].add(e.id)
            if fx.get("status") and e.social:
                prod["status"][fx["status"]].add(e.id)
            if fx.get("then"):
                prod["sched"][fx["then"][0]].add(e.id)
            st = fx.get("step")
            for i in ([st] if isinstance(st, str) else st or []):
                prod["sched"][i].add(e.id)
    return prod


def natural(kind: str, key) -> bool:
    """State that needs no story: roles that spread by a bite (Engine.chat_daily), items from the bazaar, open jobs
    whose own requirements are natural."""
    if kind == "role":
        return key in ("vampire", "zombie")
    if kind == "has":
        return key in E.PRICES
    if kind == "job":
        j = JOBS.get(key)
        return bool(j and j.get("open") and all(natural(*n) for n in needs(j["req"])))
    return False


def needs(req: dict) -> list[tuple[str, object]]:
    """The story state an event's req asks for, as (kind, key) pairs."""
    out = []
    f = req.get("flag")
    if isinstance(f, dict):
        out += [("flag", (k, v)) for k, v in f.items()]
    elif f:
        out += [("flag", (k, 1)) for k in ([f] if isinstance(f, str) else f)]
    if req.get("role") not in (None, "any"):
        out.append(("role", _first(req["role"])))
    if req.get("edu"):
        out.append(("edu", req["edu"]))
    if req.get("has"):
        out.append(("has", req["has"]))
    j = req.get("job")
    if j not in (None, "none", "any"):
        out.append(("job", _first(j)))
    if "sv" in req:
        out.append(("sv", None))   # story variables: only inside a story
    return out


def story_needs(req: dict) -> list[tuple[str, object]]:
    """…without what comes by itself."""
    return [n for n in needs(req) if not natural(*n)]


def blame(p: E.Pet, req: dict, other: E.Pet | None) -> list[str]:
    return [k for k, v in req.items() if not p.meets({k: v}, other)]


_DICTS = ("flags", "skills", "traits", "life", "persona", "counters", "status", "rel", "genes", "equipped", "cool", "heir",
          "pending")
_LISTS = ("items", "edu", "recent", "story", "achievements", "log", "ancestors", "homes", "posted")


def clone(p: E.Pet) -> E.Pet:
    """A copy of the pet for trying an outcome on (copy.deepcopy is ~30× slower and the walk makes thousands)."""
    q = copy.copy(p)
    for f in _DICTS:
        setattr(q, f, dict(getattr(p, f)))
    for f in _LISTS:
        setattr(q, f, list(getattr(p, f)))
    q.followups = [list(f) for f in p.followups]
    q.tale = copy.deepcopy(p.tale)
    return q


def state_key(p: E.Pet, items: frozenset) -> tuple:
    """The story state of a pet that matters for what can happen next (and nothing else, or states multiply)."""
    return (tuple(sorted((k, v) for k, v in p.flags.items() if not k.startswith(("_", "seen_")))), p.role, p.job,
            tuple(p.edu), tuple(sorted({i.split("@")[0] for i in p.items} & items)),
            tuple(sorted(f[0] for f in p.followups)), p.tale.get("title", ""),
            tuple(sorted(p.tale.get("vars", {}).items())))


STORY_REQ = ("flag", "noflag", "edu", "noedu", "sv", "norole")   # cheap first look: what a state must hold for an event


MAX_STATES = 60000
UNHEALTHY = ("die",)


def closure(events: dict[str, E.Event], forged: dict) -> tuple[dict, dict]:
    """Walk the content like a player who tries every choice and every outcome: from events that need no story state,
    apply each outcome to the pet, let the follow-ups it schedules come due, and see which events the resulting states
    unlock. Age, skills, money and the like are taken as reachable by living on (`fit` lifts them); the story state
    (flags, education, items, role, job) must really come from an outcome. Returns ({event id: reached via}, {id: blame})."""
    reached: dict[str, str] = {}
    why: dict[str, str] = {}
    seen: set = set()
    work: deque = deque()
    chained = [e for e in events.values() if not e.followup and story_needs(e.req)]
    items = frozenset(e.req["has"] for e in events.values() if e.req.get("has"))
    entered: set = set()

    def enter(p: E.Pet, e: E.Event, via: str, other: E.Pet | None = None) -> None:
        """`p` lives `e`: try every option and every outcome, queue the states they lead to."""
        reached.setdefault(e.id, via)
        if (e.id, state_key(p, items)) in entered:
            return
        entered.add((e.id, state_key(p, items)))
        if e.story and (not e.followup or p.tale.get("title") != e.story):
            p.tale = dict(id=e.id, title=e.story, path=[], vars={}, fx={})   # a story begins (Pet.resolve)
        elif not e.story:
            p.tale = {}
        for c in e.choices:
            base = p
            if not p.meets(c.req, other):   # a choice that asks for more (money, skill…): the pet has lived on to have it
                base = clone(p)
                fit(base, c.req, story=False)
                if not base.meets(c.req, other):
                    continue
            for o in c.outs + c.fail:
                if any(k in o.fx for k in UNHEALTHY):
                    continue
                q = clone(base)
                before = q.years
                q.apply(dict(o.fx), (clone(other) if other else None), random.Random(0))
                q.jail_until = q.hospital_until = 0
                q.state = "alive"
                st = o.fx.get("step")
                if st:
                    nxt = q.next_step(st)
                    if nxt:
                        enter(q, nxt, e.id)
                key = state_key(q, items)
                if key in seen or len(seen) > MAX_STATES:
                    continue
                seen.add(key)
                work.append((q, e, before))

    with clock(6, 10, 12):
        for e in events.values():
            if not e.followup and forged.get(e.id) and not story_needs(e.req):
                p, other, _ = forged[e.id]
                enter(p, e, "start")
        while work:
            q, root, before = work.popleft()
            # follow-ups it scheduled come due (the age check: the root's window plus the delay, plus the 15 years they wait)
            for fid, due in list(q.followups):
                f = events.get(fid)
                if not f:
                    continue
                w_root, w_f = age_window(root.req), age_window(f.req)
                delay = due - before
                if w_root and w_f and (w_root[0] + delay > w_f[1] or w_root[1] + delay + 15 < w_f[0]):
                    why.setdefault(fid, f"due at {w_root[0] + delay:.0f}–{w_root[1] + delay:.0f} y after {root.id}, "
                                        f"but the event needs {w_f[0]:.0f}–{w_f[1]:.0f} y")
                    continue
                r = clone(q)
                with clock(*date_for(f.req)):
                    other = fit(r, dict(f.req, social=f.social), story=False)
                    if r.eligible(f, other, fresh=False):
                        enter(r, f, root.id, other)
                    else:
                        why.setdefault(fid, f"scheduled by {root.id}, but not eligible when due: "
                                            + ", ".join(blame(r, f.req, other)))
            # events that need story state: does this state unlock one?
            for e in chained:
                if e.id in reached or not q.meets({k: v for k, v in e.req.items() if k in STORY_REQ}):
                    continue
                r = clone(q)
                with clock(*date_for(e.req)):
                    other = fit(r, dict(e.req, social=e.social), story=False)
                    if r.eligible(e, other, fresh=False):
                        enter(r, e, root.id, other)
    return reached, why


def social_unsupplied(e: E.Event, prod: dict, reach: set) -> list[str]:
    """Relationship state a social event asks for that no reachable event produces. Friend/bestie/rival/enemy come
    from relationship points by themselves; crush and partner need an outcome with status=; an ex needs a partner."""
    def got(s: str) -> bool:
        if s in ("", "friend", "bestie", "rival", "enemy"):
            return True
        return bool(prod["status"].get(s, set()) & reach) or (s == "ex" and got("partner"))

    miss = []
    st = e.req.get("status")
    if st and not any(got(s) for s in ([st] if isinstance(st, str) else st)):
        miss.append(f"status {st}")
    if e.req.get("partner") and not got("partner"):
        miss.append("a partner")
    role = e.req.get("other_role")
    if role and role != "any" and not natural("role", _first(role)) and not prod["role"].get(_first(role), set()) & reach:
        miss.append(f"other_role {role}")
    return miss


def analyse(events: dict[str, E.Event] | None = None) -> dict:
    events = events or {i: e for i, e in E.EVENTS.items() if not i.startswith("_")}
    prod = producers(events)
    forged = {i: satisfiable(e) for i, e in events.items()}
    reach, link_why = closure(events, forged)
    unreachable: dict[str, str] = {}
    for i, e in events.items():
        miss = social_unsupplied(e, prod, set(reach)) if i in reach else []
        if i in reach and not miss:
            continue
        if miss:
            unreachable[i] = "needs a relationship nothing reachable gives: " + "; ".join(miss)
            continue
        sched = prod["sched"].get(i, set())
        if not forged[i]:
            why = "req cannot be met by any pet (contradictory or impossible): " + json.dumps(e.req, ensure_ascii=False, default=str)
        elif e.followup and not sched:
            why = "follow-up that no outcome schedules (no then=/step= points at it)"
        elif e.followup and not sched & set(reach):
            why = "follow-up whose roots are all unreachable: " + ", ".join(sorted(sched))
        elif i in link_why:
            why = link_why[i]
        else:
            have = [f"{k} {v}" for k, v in story_needs(e.req)
                    if k != "sv" and not prod[k].get(v, set()) & set(reach)]
            why = "needs state nothing reachable gives: " + "; ".join(have or [str(story_needs(e.req))])
        unreachable[i] = why
    # rare: share of the pool for a forged pet
    rare: dict[str, float] = {}
    shares: dict[str, float] = {}
    for i, e in events.items():
        f = forged[i]
        if i not in reach or not f or e.followup:
            continue
        p, other, _ = f
        with clock(*date_for(e.req)):
            cands, ws = p.candidates(other)
            share = ws[cands.index(e)] / sum(ws) if e in cands and sum(ws) else 0.0
        shares[i] = share
        if share < RARE_SHARE:
            rare[i] = round(share, 6)
    waiting = {i: sorted(prod["sched"].get(i, set())) for i, e in events.items() if e.followup and i in reach}
    return dict(total=len(events), reachable=len(reach), unreachable=unreachable, rare=rare, waiting=waiting,
                followups=sum(e.followup for e in events.values()), total_ids=sorted(events), shares=shares, prod_sched=prod["sched"], reached=reach)


def categorize(rep: dict, fired: dict) -> dict:
    """Split the balance run's never-fired events along the categories above."""
    never = [i for i in E.EVENTS if not i.startswith("_") and i not in fired]
    out: dict[str, list[str]] = defaultdict(list)
    for i in never:
        e = E.EVENTS[i]
        if i in rep["unreachable"]:
            out["unreachable"].append(i)
        elif e.followup:
            roots = rep["prod_sched"].get(i, set())
            out["follow-up, root fired but not it" if roots & set(fired) else "follow-up waiting for its root"].append(i)
        elif i in rep["rare"]:
            out["rare (tiny weight in its own situation)"].append(i)
        elif e.req.get("season"):
            out["seasonal (the run starts on one date)"].append(i)
        elif story_needs(e.req) or any(k in e.req for k in ("job", "role", "status", "partner", "tier", "goal", "debt")):
            out["needs a job / role / story flag / relationship the run rarely gets"].append(i)
        else:
            out["plain: never drawn in this run (large pool)"].append(i)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="exit 1 when an event is unreachable")
    ap.add_argument("--sim", action="store_true", help="run the balance simulation and split its never-fired list")
    ap.add_argument("--union", type=int, metavar="N", help="with --sim: N runs from dates spread over the year (and "
                    "different seeds); an event counts as seen if any of them fired it")
    ap.add_argument("--json", help="write the report as JSON")
    ap.add_argument("--list", action="store_true", help="list every event of each category")
    a = ap.parse_args()
    rep = analyse()
    print(f"# Coverage: {rep['total']} events ({rep['followups']} follow-ups), {rep['reachable']} reachable")
    print(f"unreachable: {len(rep['unreachable'])} · waiting follow-ups: {len(rep['waiting'])} · rare (< {RARE_SHARE:.2%}): {len(rep['rare'])}")
    for i, why in sorted(rep["unreachable"].items()):
        print(f"  ✗ {i}: {why}")
    for i, s in sorted(rep["rare"].items()):
        print(f"  ~ {i}: {s:.3%} of its pool")
    if a.list:
        low = sorted(rep["shares"].items(), key=lambda kv: kv[1])[:8]
        print("rarest in their own situation: " + ", ".join(f"{i} {s:.2%}" for i, s in low))
    cat = {}
    if a.sim:
        sys.path.insert(0, str(Path(__file__).parent))
        import balance
        runs = a.union or 1
        fired: dict = {}
        for n in range(runs):
            start = balance.START if runs == 1 else f"{YEAR}-{n * 12 // runs + 1:02d}-{(n * 7) % 27 + 1:02d}"
            sim = asyncio.run(balance.run(24, 40, 0.2, 1 + n, start, jobs=True))
            for k, v in sim["fired"].items():
                fired[k] = fired.get(k, 0) + v
            print(f"  run {n + 1}/{runs} from {start}: {len(sim['fired'])} events", flush=True)
        sim = dict(fired=fired, never_fired_total=sum(1 for i in rep["total_ids"] if i not in fired))
        cat = categorize(rep, fired)
        print(f"\n## Balance {'run' if runs == 1 else f'runs ({runs} dates)'}: {sim['never_fired_total']} never fired (of {rep['total']})")
        for k, v in sorted(cat.items(), key=lambda kv: -len(kv[1])):
            print(f"  {len(v):4}  {k}" + (f": {', '.join(sorted(v))}" if a.list or k == "unreachable" else ""))
    if a.json:
        Path(a.json).write_text(json.dumps(dict(
            total=rep["total"], reachable=rep["reachable"], unreachable=rep["unreachable"], rare=rep["rare"],
            waiting=rep["waiting"], never_fired=cat), ensure_ascii=False, indent=2))
    if a.strict and rep["unreachable"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
