"""The pet's family does not live forever: a mother who calls to dig potatoes is at most a few decades older than her
child, a grandmother who phones with a parcel is a few more. So an event that speaks of the pet's own mother, father or
parents is closed to a pet older than PARENTS_YEARS, and the few about a living grandparent to one older than
GRANDPARENTS_YEARS (`years=` is narrowed when the events are assembled; an event that already has a smaller `years`
keeps it).

Parents are found by their words (мама, тато, батьки…), so new content is covered without remembering to ask; the
words that are about somebody else's mother (a bride's, a neighbour's, «пташина мама», a baby's parents) are listed in
NOT_OURS after a look. Grandparents are the opposite: «бабуся» is as often a granny in the queue as the pet's own, so
the ones who act in the story are listed by hand in GRANDPARENTS.
"""
import re

PARENTS_YEARS = 50
GRANDPARENTS_YEARS = 40

PARENT_WORDS = re.compile(r"(?<![\w'])(?:мам(?:а|и|і|у|о|ою|ин\w*)|тат(?:о|а|ові|ом)|батьк(?!івщ)\w*)(?![\w'])", re.I)
GODFATHER = re.compile(r"хрещен\w+\s+батьк\w*", re.I)

# Reviewed by eye: the mother or the parents are somebody else's.
NOT_OURS = {
    "old_grandkids", "sp_bird_balcony", "sp2_horse_school", "sp2_bird_feeder", "tw_prophecy", "soc_baby", "soc_meet_blackout",
    "arc_recipe_lost", "st_wedding_3", "st_wedding_end_duty", "st_wedding_end", "st_tv_parents", "g_gossip", "ox_bakery",
    "sr_bottle_end_neighbours", "band_gig",
}
# A grandmother or a grandfather of the pet who is alive in the story (phones, feeds, tells, gives).
GRANDPARENTS = {
    "daily_andriy", "daily_grandma_call", "daily_kitten", "teen_hair", "teen_grandma_phone", "health_cold", "kid_dream_seed",
    "kid_village_fu", "dr_sea_1", "zoom_grandma", "zoom_family", "tw_vamp_garlic", "tw_alien_borsch", "tw_cure_vampire",
    "tw_cure_alien", "tw_clinical_death", "arc_grandma_recipe", "arc_recipe_restaurant", "arc_recipe_viral",
    "arc_stairs_dream", "koliada_group", "hol_kutia", "hol_andriy_cherry", "hol_valentine_single", "hol_easter_basket",
    "hol_pysanky", "hol_paska", "hol_kupala_wreath", "hol_vyshyvanka_day", "st_jubilee", "st_jubilee_2", "st_jubilee_3",
    "st_jub_end_star", "st_jub_end_peace", "st_jub_end", "st_date", "sp_pig_truffle",
}


def texts(e) -> list[str]:
    """Everything the event says: the story, the buttons and every outcome."""
    return [e.text] + [c.label for c in e.choices] + [o.text for c in e.choices for o in c.outs + c.fail]


def speaks_of_parents(e) -> bool:
    return any(PARENT_WORDS.search(GODFATHER.sub("", t)) for t in texts(e))


def cap_for(e) -> int | None:
    """The oldest age (years) at which the pet may still meet the event, or None when the family is not in it."""
    if e.id in GRANDPARENTS:
        return GRANDPARENTS_YEARS
    if e.id not in NOT_OURS and speaks_of_parents(e):
        return PARENTS_YEARS
    return None


def guard(events) -> None:
    """Narrow `years=` of the events that speak of the pet's living family. The steps of a story follow one another at
    once and must stay free of requirements, so a step that speaks of family closes the story's first event instead."""
    caps: dict[str, int] = {}
    for e in events:
        cap = cap_for(e)
        if cap is None:
            continue
        if e.story and e.followup:
            caps[e.story] = min(cap, caps.get(e.story, cap))
        else:
            _narrow(e, cap)
    for e in events:
        if e.story in caps and not e.followup:
            _narrow(e, caps[e.story])


INFANT = 3   # engine.INFANT_YEARS: a lower bound below it lets a newborn live the event, so a cap must not add one


def _narrow(e, cap: int) -> None:
    lo, hi = e.req.get("years", (0 if e.id.startswith("baby") else INFANT, 999))
    e.req["years"] = (lo, min(hi, cap))
