"""Integrity of the stories: do they agree with the pet who lives them, and do they come back too often?

    uv run python scripts/integrity_audit.py                    # static checks + 30 pets for 250 days
    uv run python scripts/integrity_audit.py --static           # only the static part (instant)
    uv run python scripts/integrity_audit.py --pets 60 --days 400 --seed 5 --strict

Static: an event about «the first week at a new job» / «the first salary» must be tied to the job's age (`tenure=`),
a `baby_*` event to a baby's age (`years=`): otherwise a pet meets them decades late.
  Also: a text about the pet's own work (office, boss, colleagues, salary) must need a job, a text about grandchildren
  must need `kids=` — otherwise a pet without a job meets «the boss called» and a childless one «the grandchildren
  came». Those few that are about somebody else (an NPC's boss, a neighbour's grandson) are listed in OTHERS below.
  Also: a school scene (lesson, homework, break, test, «до школи»…) in an event that a pet older than SCHOOL_MAX_YEARS can
  get. The age is the event's own gate (stage/phase/years); a follow-up is also closed by its parent's window plus the
  delay plus the grace the engine allows (`followup_grace`). A memory (a classmate in the city council), a kid NPC or the
  pet's own child at school is fine: it is listed in OTHERS["school"] with the reason, after a look.
Dynamic (the sandbox with NPC owners, like balance.py): real lives are lived and counted —
  · family one-offs (`once="dynasty"`: the grandmother's 80th birthday) lived twice by the heirs of one owner;
  · age: the oldest pet that lived a `baby_*` event; new-job events that came after the first two years of the job;
    the oldest pet that lived a school scene (not in OTHERS["school"]); follow-ups that came >3 years after they were due;
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

import event_coverage as C  # noqa: E402
from kit_the_cat import engine as E  # noqa: E402
from kit_the_cat.grammar import pick  # noqa: E402
from kit_the_cat.sandbox.game import NPC_BASE, Sandbox  # noqa: E402
from kit_the_cat.storage import MemoryStore  # noqa: E402

LIMITS = dict(solo=0.06, social=0.30, jail=0.45, story=0.04, same_text=0.12)   # max share of repeats in a life
BABY_MAX_YEARS = 6
SCHOOL_MAX_YEARS = 25    # a present-tense school scene is for a pet at most this old (a student, a young parent)
LATE_YEARS = 3           # a follow-up this many years after it was due is reported
WORK = re.compile(r"офіс|начальник|колег|на роботі|співбесід|зарплат|дедлайн|звільнил|звільнен|випробувальн", re.I)
GRAND = re.compile(r"онук|внук", re.I)
# Reviewed by eye: the words are about somebody else (a character's boss, a ghost's grandsons, the mother's «when will
# there be grandchildren») or the pet takes the job in the same event.
OTHERS = {
    "work": {"qlc_root", "st_job_by_call", "jail_library", "tw_wolf_vet", "tw_evil_twin", "arc_magpie", "dr_flat_1", "o_meet", "ox_bakery", "tw_demon_tax",
             "hol_vyshyvanka_day", "jail_kitchen", "arc_friend_loan", "teen_cook_dinner", "st_garage_meeting"},
    "kids": {"baby_first_birthday", "tw_vamp_garlic", "old_ancestor_ghost", "st_mortgage", "st_startup", "shelter_corridor",
             "g_meet", "ox_bakery", "ox_basket", "o_meet", "sp2_horse_wedding", "hol_halloween_pumpkin", "teen_tutor", "st_border"},
    # Reviewed by eye: why a school word is fine for a grown-up pet.
    "school": {
        "old_reunion": "a class reunion of old pets",
        "army_letter": "schoolchildren write to the defender",
        "sp2_horse_school": "the horse is the riding school's instructor",
        "soc_zombie": "a test paper as a gift item",
        "st_school_friend": "a classmate now in the city council: a memory",
        "fu_oseledets_film": "a memory of the school years",
        "arc_bully_friend": "a memory: «ти заступився за мене в школі»",
        "arc_bully_teacher": "a memory: the teacher invites the grown-up pet to a lesson of courage",
        "arc_bully_video": "a memory of a school video",
        "arc_note_regret": "a classmate met in a minibus years later",
        "arc_olympiad_caught": "the classmate becomes an enemy: a consequence in the teens' own years",
        "arc_note_reunion": "a school reunion",
        "arc_capsule_dream": "the time capsule opened with the classmates",
        "arc_capsule_photo": "the time capsule opened with the classmates",
        "arc_capsule_joke": "the time capsule opened with the classmates",
        "arc_dream_numbers": "a diary of dreams, not a school one",
        "arc_dream_diary": "a diary of dreams, not a school one",
        "arc_telescope": "the pet gives a telescope to a school",
        "arc_telescope_kids": "the pet gave a telescope to a school",
        "hol_pysanka_gift": "a neighbour's girl at a school exhibition",
        "teen_volunteer_fu": "a memory: «Пам'ятаєш сітки, які він плів у шкільній бібліотеці»",
        "qlc_root": "the classmates who «have already made it»: a comparison, not a scene",
        "teen_president_fu": "a classmate remembers the school election",
        "st_dark_2": "a neighbour's child does the homework",
        "st_date_end": "a ticket kept in a diary",
        "middle_parent_chat": "the pet's own child's class chat",
        "fu_solomiya_reunion": "a reunion with the school friend",
        "snitch_revenge": "«Лікарня й урок»: a lesson of life",
        "job_bandit_betrayal": "a henchman nicknamed Шнурок",
        "tw_zombie_cnap": "a lunch break at work",
    },
}
# School words at the start of a word («Шнурок» is not «урок»). The idiom «урок вивчено/засвоєно» is a lesson of life.
SCHOOL = re.compile(
    r"(?<!\w)(?:урок(?!\w*\s+(?:вивчен|засвоєн|засвоїв))|домашк|до школ|у школ|в школ|зі школ|на перерві|шкільн|"
    r"у класі|контрольн|щоденник|диктант|останній дзвоник|останній урок|перший клас|вчителька кличе|класн\w+ керівни|"
    r"чат класу|за партою|у портфелі|пише конспект|однокласни|завуч|директор школи)", re.I)
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


def parents_of() -> dict[str, list[tuple[str, float]]]:
    """follow-up id -> [(the event that schedules it with then=, the delay in years)]."""
    par: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for e in E.EVENTS.values():
        for c in e.choices:
            for o in c.outs + c.fail:
                if "then" in o.fx:
                    fid, after = o.fx["then"]
                    for f in ([fid] if isinstance(fid, str) else fid):
                        par[f].append((e.id, E.parse_years(after)))
    return par


def age_hi(e, par: dict, seen: frozenset = frozenset()) -> float:
    """The oldest age (years) at which the event can be lived: its own gate (stage/phase/years); for a follow-up also its
    parents' oldest age + the delay + the grace the engine allows after it is due."""
    w = C.age_window(e.req)
    hi = w[1] if w else 0.0
    if e.followup and e.id in par and e.id not in seen:
        hi = min(hi, max(age_hi(E.EVENTS[p], par, seen | {e.id}) + d + E.followup_grace(d)
                         for p, d in par[e.id] if p in E.EVENTS))
    return hi


def school_words(e) -> list[str]:
    return sorted({m.group(0).lower() for t in texts_of(e) for m in SCHOOL.finditer(t)})


def static() -> list[str]:
    bad = []
    par = parents_of()
    for i in OTHERS["school"]:
        if i not in E.EVENTS:
            bad.append(f"OTHERS['school'] lists an event that does not exist: {i}")
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
        if e.id not in OTHERS["school"] and (words := school_words(e)) and age_hi(e, par) > SCHOOL_MAX_YEARS:
            bad.append(f"{e.id}: a school scene ({', '.join(words)}) for a pet up to {age_hi(e, par):.0f}y — gate it (phase/years), "
                       f"rephrase it as a memory, or add it to OTHERS['school'] with the reason")
        if e.id.startswith(("kid_", "teen_", "soc_kid_", "soc_teen_")) and not e.followup and age_hi(e, par) > SCHOOL_MAX_YEARS:
            bad.append(f"{e.id}: a kid/teen event open to a pet up to {age_hi(e, par):.0f}y (stage=2 alone means «12 and older»)")
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
    stats = dict(events=0, life=defaultdict(list), texts=defaultdict(list), bad=Counter(), baby_age=[], late_job=Counter(), dynasty=Counter(),
                 school_age=[], late_fu=[])
    sb = Sandbox(MemoryStore(), seed, epoch=B.epoch(B.START))
    await sb.init()
    rng = random.Random(seed)
    orig_resolve, orig_apply, orig_care, orig_pick = E.Pet.resolve, E.Pet.apply, Sandbox._autocare, E.Pet.pick_event
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
        if e.once == "dynasty":
            stats["dynasty"][(self.owner_id, e.id)] += 1
        if e.id.startswith("baby_"):
            stats["baby_age"].append((before["years"], e.id))
        if e.id not in OTHERS["school"] and school_words(e):
            stats["school_age"].append((before["years"], e.id))
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

    def pick_event(self, others, r, kind=""):
        queued = {f[0]: f[1] for f in self.followups}
        res = orig_pick(self, others, r, kind)
        if res[0] and res[0].id in queued and self.years - queued[res[0].id] > LATE_YEARS:
            stats["late_fu"].append((self.years - queued[res[0].id], res[0].id))
        return res

    def autocare(self, p):
        orig_care(self, p)
        if p.alive and not p.job and p.stage >= 3 and rng.random() < 0.05:
            offers = E.job_offers(p)
            if offers:
                E.apply_job(p, rng.choice(offers), rng)
    E.Pet.resolve, E.Pet.apply, Sandbox._autocare, E.Pet.pick_event = resolve, apply, autocare, pick_event
    try:
        await sb.add_npcs(pets)
        for _ in range(days):
            await sb.advance(24, auto_me=False, care_me=False)
            for p in await sb.pets(tick=False):
                if p.state == "dead" and p.owner_id >= NPC_BASE:
                    await sb.heir(p.owner_id)
    finally:
        E.Pet.resolve, E.Pet.apply, Sandbox._autocare, E.Pet.pick_event = orig_resolve, orig_apply, orig_care, orig_pick
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
        school = max(st["school_age"], default=(0, ""))
        print(f"  oldest pet at a school scene: {school[0]:.1f}y ({school[1]}), limit {SCHOOL_MAX_YEARS}; "
              f"{len(st['school_age'])} school scenes lived")
        if school[0] > SCHOOL_MAX_YEARS:
            problems.append(f"a school scene at {school[0]:.1f}y: {school[1]}")
        late = Counter(i for _, i in st["late_fu"])
        print(f"  follow-ups lived more than {LATE_YEARS}y after they were due: {len(st['late_fu'])}"
              + (f", the latest {max(st['late_fu'])[0]:.1f}y ({max(st['late_fu'])[1]})" if late else ""))
        again = {k: n for k, n in st["dynasty"].items() if n > 1}
        print(f"  family one-offs lived twice by one dynasty (80th birthday…): {len(again)} of {len(st['dynasty'])}")
        if again:
            problems.append(f"a dynasty lived a family one-off twice: {again}")
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
