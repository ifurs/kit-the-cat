"""All life events, aggregated. Each module exports a list of dsl.Event.

Time (hidden from the player): every module has a base cost; a choice without its own `time` costs
`infer_time(choice, base)` — what the choice does adds to the base, so the choices of one event differ.
CHOICE_TIME hand-tunes common and big older events. GATED (gated.py) adds choices that need a skill or an item. FOLLOWUPS links choices of older events to their consequences (content/consequences.py): an earlier choice comes
back years later. New content writes `then=` inline instead.
"""
from .ages import AGES
from .youth import YOUTH
from .stories import STORIES
from .stories_more import STORIES_MORE
from .stories_tv import STORIES_TV
from .arcs import ARCS_YOUNG
from .arcs_adult import ARCS_ADULT
from .arcs_soul import ARCS_SOUL
from .arcs_week_20261029 import ARCS_WEEK_20261029
from .arcs_week_20261102 import ARCS_WEEK_20261102
from .arena import ARENA
from .cast_home import HOME
from .cast_town import TOWN
from .chains import CHAINS
from .consequences import CONSEQUENCES
from .daily import DAILY
from .dates import DATES
from .dreams import DREAMS_CONTENT
from .dsl import infer_time
from .family import guard as _guard_family
from .gated import GATED
from .health import HEALTH
from .holidays import HOLIDAY_EVENTS
from .jobs import JOBS_LIFE
from .life import LIFE
from .modern import MODERN
from .series import SERIES_CONTENT
from .social import SOCIAL
from .social_more import SOCIAL_MORE
from .species import SPECIES
from .species_more import SPECIES_MORE
from .status import STATUS
from .twists import TWISTS

DEFAULT_TIME = [(DAILY, "3d"), (LIFE, "1m"), (CHAINS, "3m"), (JOBS_LIFE, "1m"), (SPECIES, "1w"), (SPECIES_MORE, "1w"), (SOCIAL, "1w"), (SOCIAL_MORE, "1w"), (DATES, "1w"), (MODERN, "3d"),
                (TWISTS, "1m"), (STATUS, "1m"), (CONSEQUENCES, "2w"), (ARCS_YOUNG, "1m"), (ARCS_ADULT, "1m"),
                (ARCS_SOUL, "1m"), (DREAMS_CONTENT, "3m"), (HEALTH, "1w"),
                (ARCS_WEEK_20261029, "1m"), (ARCS_WEEK_20261102, "1m"), (HOLIDAY_EVENTS, "2d"), (AGES, "1m"), (YOUTH, "1m"), (STORIES, "1d"), (STORIES_MORE, "1d"), (STORIES_TV, "1d"),
                (HOME, "1m"), (TOWN, "1m"), (SERIES_CONTENT, "1m"), (ARENA, "1w")]
ALL = [e for events, _ in DEFAULT_TIME for e in events]
_guard_family(ALL)
CHOICE_TIME = {
    "teen_uni": ["4y", "4y", "6y", "3y", "1y"],
    "baby_kindergarten": ["3y", "3y", "3y"],
    "army_join": ["2y", "1y", ""],
    "space_launch": ["1y", "", ""],
    "space_mars": ["", "2y", "3y"],
    "crime_heist": ["1w", "1m", ""],
    "crime_retire": ["1y", "", "5y", "1y"],
    "jail_escape": ["1m", "3y", "6m"],
    "pol_mayor": ["5y", "", "5y"],
    "pol_president": ["5y", "", ""],
    "pol_nabu": ["3y", "1y", "6m"],
    "band_tour": ["6m", "6m", "2y", ""],
    "adult_vacation": ["2w", "1w", "2w", "1w"],
    "health_surgery": ["1m", "3m", ""],
    # everyday events: walking is slower than squeezing in, a marathon needs months of training…
    "daily_marshrutka": ["1d", "2d", "1d", "1d"],
    "adult_hamster": ["3m", "1w", "2m", "1d"],
    "daily_mushrooms": ["1d", "1d", "2d", "3d"],
    "health_cold": ["1w", "3d", "2w"],
    "adult_therapy": ["1y", "1w", "1d"],
    "adult_gym": ["6m", "3m", "1d"],
    "daily_train": ["1d", "1d", "1d", "1d"],
    "adult_marathon": ["6m", "1d", "1d"],
    "startup_idea": ["1y", "2m", "1w", "1d"],
    "adult_credit": ["1y", "1y", "1d"],
    "blog_start": ["6m", "1d", "1m"],
    "adult_cooking": ["1d", "1d", "1d"],
    "daily_light_back": ["1d", "1d", "1d", "1d"],
    "daily_scam_call": ["1d", "1d", "1d", "1d"],
    "daily_lost_keys": ["1d", "1d", "1d", "1d"],
    "daily_kum_wedding": ["2d", "3d", "2d", "2d", "1d"],
}
# (event, choice index): (follow-up event, after how much of the pet's life)
FOLLOWUPS = {
    ("daily_easter", 0): ("hol_krashanka_final", "1y"),
    ("daily_scam_call", 2): ("fu_scam_return", "6m"), ("daily_scam_call", 1): ("fu_scam_fame", "3m"),
    ("adult_hamster", 1): ("fu_hamster_crash", "1y"), ("daily_pigeon", 0): ("fu_pigeon_ticket", "1m"),
    ("crime_start", 0): ("fu_shukher_past", "8y"), ("crime_start", 2): ("fu_snitch_reward", "6y"),
    ("daily_shelter", 1): ("fu_shelter_kid", "15y"), ("st_cnap_kum", 0): ("fu_kuma_favor", "1y"),
    ("st_cnap_kum", 1): ("fu_cnap_granny", "3y"), ("st_crypto_kum", 0): ("fu_kum_returns", "2y"),
    ("baby_socket", 1): ("fu_socket_engineer", "15y"), ("daily_kum_wedding", 4): ("fu_kum_grudge", "1y"),
    ("daily_kum_wedding", 1): ("fu_kum_godfather", "2y"), ("st_first_video", 0): ("fu_old_video", "5y"),
    ("blog_start", 0): ("fu_old_video", "5y"), ("adult_credit", 0): ("fu_credit_collectors", "1y"),
    ("st_pyramid", 0): ("fu_pyramid_court", "1y"), ("teen_hair", 1): ("fu_oseledets_film", "6y"),
    ("adult_therapy", 0): ("fu_therapy_progress", "1y"), ("daily_lost_keys", 2): ("fu_neighbor_pies", "3m"),
    ("st_charity_stream", 0): ("fu_drone_thanks", "1y"), ("st_startup", 1): ("fu_startup_exit", "3y"),
}
_by_id = {e.id: e for e in ALL}
for _id, _choices in GATED.items():   # gated.py: extra choices for a skilled / equipped pet, after the ones an event has
    _by_id[_id].choices.extend(_choices)
for (_id, _i), _then in FOLLOWUPS.items():
    for _o in _by_id[_id].choices[_i].outs + _by_id[_id].choices[_i].fail:
        _o.fx.setdefault("then", _then)
for _id, _times in CHOICE_TIME.items():
    for _c, _t in zip(_by_id[_id].choices, _times):
        _c.time = _c.time or _t
for _events, _t in DEFAULT_TIME:
    for _e in _events:
        _e.time = _e.time or _t
        for _c in _e.choices:
            _c.time = _c.time or infer_time(_c, _e.time)
