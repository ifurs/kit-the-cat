"""Integrity of the stories: do they agree with the pet who lives them, and do they come back too often?

    uv run python scripts/integrity_audit.py                    # static checks + 30 pets for 250 days
    uv run python scripts/integrity_audit.py --static           # only the static part (instant)
    uv run python scripts/integrity_audit.py --pets 60 --days 400 --seed 5 --strict

Static: an event about «the first week at a new job» / «the first salary» must be tied to the job's age (`tenure=`),
a `baby_*` event to a baby's age (`years=`): otherwise a pet meets them decades late.
  Also: a text about the pet's own work (office, boss, colleagues, salary) must need a job, a text about grandchildren
  must need `kids=` — otherwise a pet without a job meets «the boss called» and a childless one «the grandchildren
  came». Those few that are about somebody else (an NPC's boss, a neighbour's grandson) are listed in OTHERS below.
Dynamic (the sandbox with NPC owners, like balance.py): real lives are lived and counted —
  · age: the oldest pet that lived a `baby_*` event; new-job events that came after the first two years of the job;
  · repeats: share of events that a life already had (solo, social, jail, follow-up/story) and the share of events whose
    outcome text is word for word one the same life already read;
  · state: outcomes that contradict the state (hired while employed, the same diploma twice, a baby without a partner…),
    and texts that speak of a job or grandchildren the pet does not have.
--strict exits 1 when a limit below is broken.
"""
import argparse
import asyncio
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import balance as B  # noqa: E402

from kit_the_cat import engine as E  # noqa: E402
from kit_the_cat.grammar import pick  # noqa: E402
from kit_the_cat.sandbox.game import NPC_BASE, Sandbox  # noqa: E402
from kit_the_cat.storage import MemoryStore  # noqa: E402

LIMITS = dict(solo=0.06, social=0.30, jail=0.45, story=0.04, same_text=0.12)   # max share of repeats in a life
BABY_MAX_YEARS = 6
WORK = re.compile(r"офіс|начальник|колег|на роботі|співбесід|зарплат|дедлайн|звільнил|звільнен|випробувальн", re.I)
GRAND = re.compile(r"онук|внук", re.I)
# Reviewed by eye: the words are about somebody else (a character's boss, a ghost's grandsons, the mother's «when will
# there be grandchildren») or the pet takes the job in the same event.
OTHERS = {
    "work": {"qlc_root", "st_job_by_call", "jail_library", "tw_wolf_vet", "tw_evil_twin", "arc_magpie", "dr_flat_1", "o_meet", "ox_bakery", "tw_demon_tax",
             "hol_vyshyvanka_day", "jail_kitchen", "arc_friend_loan", "teen_cook_dinner", "st_garage_meeting"},
    "kids": {"baby_first_birthday", "tw_vamp_garlic", "old_ancestor_ghost", "st_mortgage", "st_startup", "shelter_corridor",
             "g_meet", "ox_bakery", "ox_basket", "o_meet", "sp2_horse_wedding", "hol_halloween_pumpkin", "teen_tutor", "st_border"},
}
NEW_JOB = re.compile(r"новій роботі|перший тиждень на|перша зарплат|першу зарплат|перший робочий|перший день на роботі|"
                     r"випробувальн", re.I)


def category(e) -> str:
    return ("social" if e.social else "jail" if e.id.startswith("jail_") else "story" if e.followup or e.story else "solo")


def texts_of(e) -> list[str]:
    return [pick(e.text, "m", "m")] + [pick(o.text, "m", "m") for c in e.choices for o in c.outs + c.fail]


def guards(e, key: str) -> bool:
    """The event (or a choice that says it) needs the state its text speaks of."""
    reqs = [e.req] + [c.req for c in e.choices]
    return any(key in r for r in reqs) or (key == "job" and any("job" in o.fx for c in e.choices for o in c.outs + c.fail))


def static() -> list[str]:
    bad = []
    for e in E.EVENTS.values():
        text = pick(e.text, "m", "m")
        if not e.social and not e.followup:
            if any(WORK.search(t) for t in texts_of(e)) and not guards(e, "job") and e.id not in OTHERS["work"] \
                    and not e.id.startswith(("jail_", "sp_", "sp2_", "tw_")):
                bad.append(f"{e.id}: speaks of the pet's job, but nothing needs job= (or add it to OTHERS after a look)")
            if any(GRAND.search(t) for t in texts_of(e)) and not guards(e, "kids") and e.id not in OTHERS["kids"]:
                bad.append(f"{e.id}: speaks of grandchildren, but nothing needs kids=")
        if NEW_JOB.search(text) and "job" in e.req and "tenure" not in e.req and not e.followup:
            bad.append(f"{e.id}: about a new job but has no tenure= — it would come decades into the job")
        if e.id.startswith("baby_") and e.req.get("years", (0, 99))[1] > BABY_MAX_YEARS:
            bad.append(f"{e.id}: a baby event without years=(…, ≤{BABY_MAX_YEARS})")
    return bad


def contradictions(e, fx: dict, before: dict) -> list[str]:
    """What the chosen outcome does that the state before it forbids."""
    bad = []
    if fx.get("job") and before["job"] and fx["job"] == before["job"]:
        bad.append("hired into the job it already has")
    if "job" in fx and not fx["job"] and not before["job"]:
        bad.append("fired without a job")
    if fx.get("edu") and fx["edu"] in before["edu"]:
        bad.append("the same diploma twice")
    if fx.get("baby") and not before["partner"] and not e.social:
        bad.append("a baby without a partner")
    if fx.get("status") == "partner" and before["partner"] and not e.social:
        bad.append("a new partner while having one")
    return bad


async def simulate(pets: int, days: int, seed: int) -> dict:
    stats = dict(events=0, life=defaultdict(list), texts=defaultdict(list), bad=Counter(), baby_age=[], late_job=Counter())
    sb = Sandbox(MemoryStore(), seed, epoch=B.epoch(B.START))
    await sb.init()
    rng = random.Random(seed)
    orig_resolve, orig_apply, orig_care = E.Pet.resolve, E.Pet.apply, Sandbox._autocare
    cur: dict = {}

    def apply(self, fx, other=None, r=None):
        if cur.get("pid") == self.pid:
            cur["fx"] = dict(fx)
        return orig_apply(self, fx, other, r)

    def resolve(self, e, idx, other, r):
        before = dict(job=self.job, partner=bool(self.partner), edu=list(self.edu), years=self.years, kids=self.children,
                      since=self.flags.get("_job_y"))
        cur.clear()
        cur.update(pid=self.pid, fx={})
        res = orig_resolve(self, e, idx, other, r)
        key = (self.pid, self.gen)
        stats["events"] += 1
        stats["life"][key].append(e.id)
        stats["texts"][key].append(res.text)
        if e.id.startswith("baby_"):
            stats["baby_age"].append((before["years"], e.id))
        if NEW_JOB.search(pick(e.text, "m", "m")) and before["since"] is not None and before["years"] - before["since"] > 2 \
                and not e.followup:
            stats["late_job"][e.id] += 1
        for what in contradictions(e, cur["fx"], before):
            stats["bad"][(what, e.id)] += 1
        if not e.social and not e.followup:
            said = [pick(e.text, "m", "m"), res.text or ""]
            if not before["job"] and any(WORK.search(t) for t in said) and e.id not in OTHERS["work"] \
                    and "job" not in cur["fx"] and not e.id.startswith(("jail_", "sp_", "sp2_", "tw_")):
                stats["bad"][("speaks of a job the pet does not have", e.id)] += 1
            if not before["kids"] and any(GRAND.search(t) for t in said) and e.id not in OTHERS["kids"]:
                stats["bad"][("speaks of grandchildren the pet does not have", e.id)] += 1
        return res

    def autocare(self, p):
        orig_care(self, p)
        if p.alive and not p.job and p.stage >= 3 and rng.random() < 0.05:
            offers = E.job_offers(p)
            if offers:
                E.apply_job(p, rng.choice(offers), rng)
    E.Pet.resolve, E.Pet.apply, Sandbox._autocare = resolve, apply, autocare
    try:
        await sb.add_npcs(pets)
        for _ in range(days):
            await sb.advance(24, auto_me=False, care_me=False)
            for p in await sb.pets(tick=False):
                if p.state == "dead" and p.owner_id >= NPC_BASE:
                    await sb.heir(p.owner_id)
    finally:
        E.Pet.resolve, E.Pet.apply, Sandbox._autocare = orig_resolve, orig_apply, orig_care
    return stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--static", action="store_true")
    ap.add_argument("--pets", type=int, default=30)
    ap.add_argument("--days", type=int, default=250)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    problems = static()
    print(f"## static: {len(problems) or 'no'} problems")
    print("\n".join("  " + p for p in problems))
    if not a.static:
        st = asyncio.run(simulate(a.pets, a.days, a.seed))
        print(f"\n## dynamic: {st['events']} events in {len(st['life'])} lives")
        tot, rep, same = Counter(), Counter(), 0
        for key, ids in st["life"].items():
            seen, texts = Counter(), set()
            for i, text in zip(ids, st["texts"][key]):
                if i not in E.EVENTS:
                    continue
                c = category(E.EVENTS[i])
                tot[c] += 1
                rep[c] += bool(seen[i])
                same += text in texts
                seen[i] += 1
                texts.add(text)
        shares = {c: rep[c] / max(1, tot[c]) for c in tot}
        shares["same_text"] = same / max(1, sum(tot.values()))
        for c, lim in LIMITS.items():
            ok = shares.get(c, 0) <= lim
            print(f"  repeats {c:9} {shares.get(c, 0):5.0%}  (limit {lim:.0%})  {'OK' if ok else 'TOO MANY'}")
            if not ok:
                problems.append(f"repeats of {c}: {shares[c]:.0%} > {lim:.0%}")
        oldest = max(st["baby_age"], default=(0, ""))
        print(f"  oldest pet at a baby_* event: {oldest[0]:.1f}y ({oldest[1]}), limit {BABY_MAX_YEARS}")
        if oldest[0] > BABY_MAX_YEARS:
            problems.append(f"a baby event at {oldest[0]:.1f}y")
        if st["late_job"]:
            problems.append(f"new-job events long after hiring: {dict(st['late_job'])}")
        print(f"  new-job events after two years in the job: {sum(st['late_job'].values())}")
        kinds = Counter()
        for (what, _), n in st["bad"].items():
            kinds[what] += n
        print("  state contradictions:", dict(kinds) or "none")
        for (what, i), n in st["bad"].most_common(8):
            print(f"    {n:3}x {i}: {what}")
        for (what, i), n in st["bad"].items():
            if what.startswith("speaks"):
                problems.append(f"{i}: {what} ({n}x)")
    raise SystemExit(1 if a.strict and problems else 0)


if __name__ == "__main__":
    main()
