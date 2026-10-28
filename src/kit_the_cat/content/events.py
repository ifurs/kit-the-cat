"""All life events, aggregated. Each module exports a list of dsl.Event.

FOLLOWUPS links choices of older events to their consequences (content/consequences.py): an earlier choice comes
back years later. New content writes `then=` inline instead.
"""
from .chains import CHAINS
from .consequences import CONSEQUENCES
from .daily import DAILY
from .jobs import JOBS_LIFE
from .life import LIFE
from .social import SOCIAL
from .species import SPECIES
from .status import STATUS
from .twists import TWISTS

ALL = LIFE + DAILY + CHAINS + JOBS_LIFE + SPECIES + SOCIAL + TWISTS + STATUS + CONSEQUENCES
# (event, choice index): (follow-up event, after how much of the pet's life)
FOLLOWUPS = {
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
for (_id, _i), _then in FOLLOWUPS.items():
    for _o in _by_id[_id].choices[_i].outs + _by_id[_id].choices[_i].fail:
        _o.fx.setdefault("then", _then)
