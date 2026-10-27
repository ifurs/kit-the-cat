"""All life events, aggregated. Each module exports a list of dsl.Event."""
from .chains import CHAINS
from .daily import DAILY
from .jobs import JOBS_LIFE
from .life import LIFE
from .social import SOCIAL
from .species import SPECIES
from .twists import TWISTS

ALL = LIFE + DAILY + CHAINS + JOBS_LIFE + SPECIES + SOCIAL + TWISTS
