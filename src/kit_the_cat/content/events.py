"""All life events, aggregated. Each module exports a list of dsl.Event.

Every module has a default life-time cost for its decisions (a choice's own `time` and the event's `time` win).
"""
from .chains import CHAINS
from .daily import DAILY
from .jobs import JOBS_LIFE
from .life import LIFE
from .social import SOCIAL
from .species import SPECIES
from .status import STATUS
from .twists import TWISTS

DEFAULT_TIME = [(DAILY, "1w"), (LIFE, "1m"), (CHAINS, "3m"), (JOBS_LIFE, "1m"), (SPECIES, "2w"), (SOCIAL, "2w"),
                (TWISTS, "1m"), (STATUS, "1m")]
# big decisions in older modules: per-choice time ("" = default). New content sets `time=` inline instead.
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
}
_by_id = {e.id: e for _events, _ in DEFAULT_TIME for e in _events}
for _id, _times in CHOICE_TIME.items():
    for _c, _t in zip(_by_id[_id].choices, _times):
        _c.time = _c.time or _t
for _events, _t in DEFAULT_TIME:
    for _e in _events:
        _e.time = _e.time or _t

ALL = LIFE + DAILY + CHAINS + JOBS_LIFE + SPECIES + SOCIAL + TWISTS + STATUS
