"""Tiny DSL for writing life events.

    ev("found_wallet", "{name} знайшов гаманець…",
       ch("Віднести в поліцію", o("Поліцейський забрав його собі.", love=2, mood=-5), auto="love"),
       ch("Забрати гроші", o("+500 ₴, але совість гризе.", money=500, toxic=1), auto="toxic"),
       ch("Купити лотерейки", o("Джекпот!", money=5000), check=("luck", 70),
          fail=[o("Нічого не виграв.", money=-50)], auto="gambler"),
       req=dict(stage=2))

Time: every decision costs some of the pet's life, and the player never sees how much (no time on buttons).
A choice costs `time` if it has one, else `infer_time(choice, base)` — the event's / module's base plus what the
choice does (studying, settling into a job, moving, a serious relationship, a story step, skills learned, money
earned). Give `time=` to the choices whose cost is obvious from the story: «Вступити в КПІ» → "4y", «Купити
хліб» → "1d". An outcome may cost extra: o("Прокинувся через п'ять років…", time="5y"). Jail and hospital eat
life too. Durations: "3d", "2w", "6m", "4y" or a number of years. On top of that the clock ages pets slowly.

Effects (o(..., **fx)):
  hunger mood clean health energy      stat deltas (0..100); hunger/clean/energy are automatic upkeep — use
                                       mood and health in new content
  fame auth blat fin attr              life stats 0..100 with tiers (engine.LIFE): популярність, авторитет, блат,
                                       фінграмотність, привабливість (style and charm, never mocking looks)
  time="5y"                            extra life time this outcome costs (coma, a sentence, cryosleep)
  str int cha luck                     skill deltas
  toxic gambler dark party patriot glutton love mystic   trait deltas
  money xp lifespan                    ₴, experience, years of life
  item="cowboy@6" | ["a", "b"]         give & equip;  item_slot="head" → random item for slot
  lose_item="random" | "id"            take away
  unequip="head" | "all"               take off what is worn in that slot (or everything); items stay owned
  flag={"crime": 2}  unflag="crime"    story flags (quest chains)
  job="it" | job=""                    hire / fire
  edu="kpi"                            diploma
  home="palace"                        move (background)
  jail=48 | hospital=24                hours (outfit + background while there)
  die="cause"                          death
  achievement="…"
  money_mult=0.5                       multiply money (0 = lose everything)
  free=True                            released from jail
  gene={"extra": "fangs"}              set genes directly (sprite changes!)
  mutate=2                             randomly mutate N visible genes
  species="fox"                        transform into another species (keeps colour, swaps parts)
  role="vampire" | role=""             supernatural role (see engine.ROLES) / cure
  reroll_persona=True                  amnesia: new temperament, dream, fear, quirk
  twist=True                           marks the outcome as a plot twist (announced louder)
  then=("fu_kum_returns", "2y")        schedule a follow-up event after that much of the pet's life: earlier
                                       choices come back (the follow-up must be an ev(..., followup=True))
  # social events only:
  rel=+10  status="friend|bestie|rival|enemy|crush|partner|ex"  other={...effects for the other pet}
  baby=True                            the couple gets an heir egg (hybrid genes)
  swap_genes=True                      body swap: the two pets exchange looks

Requirements (req=dict(...)):
  stage=2 | (2, 3)   species="pig"   flag="crime" | flag={"crime": 2}   noflag="crime"
  trait={"toxic": 10}   skill={"int": 30}   money=100   job="it"|"any"|"none"   edu="kpi"   noedu="kpi"
  has="sabre"   partner=True|False   night=True   jail=True (only while jailed)
  status=["crush"] (social: relation with the other pet)   other_stage=2   age=(min_days, max_days)
  debt=500 (money <= -500)   low={"health": 40}   role="vampire" | role="any" | norole=True
  other_role="vampire"   nostatus=[...]   other_partner=False   other_stage_max=2
  life={"fame": 40} (life stat at least)   tier={"fame": 2, "money": 3} (tier at least; money tiers too)
  tier_max={"auth": 0}   years=(18, 60) (age in years)   goal="mayor" (the pet's dream, persona.GOALS)
  phase="young" | ["young", "middle"]   life phase by age: kid 0–12, teen 12–18, young 18–30, middle 30–60, grand 60+
  season="winter|spring|summer|autumn" | holiday (newyear christmas andriy easter kupala halloween valentine
         independence) | list of those | month numbers (real Kyiv date)
"""
from dataclasses import dataclass, field

# The contract between content (storyline) and engine. Content may only use these keys;
# the engine must implement every one. content/validate.py checks it.
STATS = {"hunger", "mood", "clean", "health", "energy"}
LIFE = {"fame", "auth", "blat", "fin", "attr"}
SKILLS = {"str", "int", "cha", "luck"}
TRAITS = {"toxic", "gambler", "dark", "party", "patriot", "glutton", "love", "mystic"}
KNOWN_FX = STATS | SKILLS | TRAITS | LIFE | {"time", "then",
    "money", "money_mult", "xp", "lifespan", "item", "item_slot", "lose_item", "unequip", "flag", "unflag", "job", "edu",
    "home", "jail", "hospital", "die", "achievement", "free", "gene", "mutate", "species", "role", "reroll_persona",
    "twist", "rel", "status", "other", "baby", "swap_genes",
}
KNOWN_REQ = {
    "stage", "species", "flag", "noflag", "trait", "skill", "money", "debt", "job", "edu", "noedu", "has", "partner",
    "night", "jail", "age", "low", "status", "nostatus", "other_stage", "other_partner", "role", "norole", "other_role",
    "season", "other_stage_max", "life", "tier", "tier_max", "years", "goal", "phase",
}
UNITS = {"d": 1 / 365, "w": 7 / 365, "m": 1 / 12, "y": 1.0}


def years(v) -> float:
    """"3d" / "2w" / "6m" / "4y" / number of years → years. Raises ValueError on anything else."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    if isinstance(v, str) and len(v) > 1 and v[-1] in UNITS:
        return float(v[:-1]) * UNITS[v[-1]]
    raise ValueError(f"bad duration {v!r}")


def infer_time(c: "Choice", base) -> float:
    """Years a choice costs: the base plus what it does — studying, a new job, moving, a romance, a story step,
    skills learned and money earned (averaged over its outcomes, so choices of one event differ)."""
    outs = (c.outs + c.fail) or c.outs
    num = lambda v: v if isinstance(v, (int, float)) and not isinstance(v, bool) else 0  # noqa: E731

    def cost(fx: dict) -> float:
        y = 3.0 if fx.get("edu") else 0.0
        y += 1.0 if fx.get("job") else 0.0
        y += 0.5 if fx.get("home") else 0.0
        y += 0.3 if fx.get("flag") else 0.0
        y += 1.0 if fx.get("baby") or fx.get("status") == "partner" else 0.0
        y += 0.15 * max(0.0, sum(num(v) for k, v in fx.items() if k in SKILLS)) / 3
        y += 0.25 * max(0.0, num(fx.get("money", 0))) / 1000
        return y
    return round(years(base) + sum(cost(o.fx) for o in outs) / max(1, len(outs)), 4)


PHASES = {"kid", "teen", "young", "middle", "grand"}   # engine.PHASES has their age ranges
ROLES = {"vampire", "werewolf", "zombie", "demon", "angel", "cyborg", "alien", "quantum"}


@dataclass
class Out:
    text: str
    fx: dict
    w: float = 1.0


@dataclass
class Choice:
    label: str
    outs: list[Out]
    check: tuple[str, int] | None = None
    fail: list[Out] = field(default_factory=list)
    req: dict = field(default_factory=dict)
    auto: str = ""          # trait this choice expresses (used when the pet decides on its own)
    time: str | float = ""  # life time this decision costs, hidden from the player ("" → infer_time)


@dataclass
class Event:
    id: str
    text: str
    choices: list[Choice]
    req: dict = field(default_factory=dict)
    w: float = 1.0
    social: bool = False
    bg: str = ""
    once: bool = False
    aff: tuple = ()         # traits that make this event more likely
    time: str | float = ""  # base cost of its choices ("" → the module's base)
    followup: bool = False  # only comes as a consequence (`then=`), never at random


def o(text: str, w: float = 1.0, **fx) -> Out:
    return Out(text, fx, w)


def ch(label: str, *outs: Out, check=None, fail=None, req=None, auto: str = "", time: str | float = "") -> Choice:
    return Choice(label, list(outs), check, list(fail or []), dict(req or {}), auto, time)


def ev(id: str, text: str, *choices: Choice, req=None, w: float = 1.0, social: bool = False, bg: str = "",
       once: bool = False, aff: tuple = (), time: str | float = "", followup: bool = False) -> Event:
    return Event(id, text, list(choices), dict(req or {}), w, social, bg, once, tuple(aff), time, followup)
