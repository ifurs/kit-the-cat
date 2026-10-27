"""Tiny DSL for writing life events.

    ev("found_wallet", "{name} знайшов гаманець…",
       ch("Віднести в поліцію", o("Поліцейський забрав його собі.", love=2, mood=-5), auto="love"),
       ch("Забрати гроші", o("+500 ₴, але совість гризе.", money=500, toxic=1), auto="toxic"),
       ch("Купити лотерейки", o("Джекпот!", money=5000), check=("luck", 70),
          fail=[o("Нічого не виграв.", money=-50)], auto="gambler"),
       req=dict(stage=2))

Effects (o(..., **fx)):
  hunger mood clean health energy      stat deltas (0..100)
  str int cha luck                     skill deltas
  toxic gambler dark party patriot glutton love mystic   trait deltas
  money xp lifespan                    ₴, experience, days of life
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
  season="winter|spring|summer|autumn" | holiday (newyear christmas andriy easter kupala halloween valentine
         independence) | list of those | month numbers (real Kyiv date)
"""
from dataclasses import dataclass, field

# The contract between content (storyline) and engine. Content may only use these keys;
# the engine must implement every one. content/validate.py checks it.
STATS = {"hunger", "mood", "clean", "health", "energy"}
SKILLS = {"str", "int", "cha", "luck"}
TRAITS = {"toxic", "gambler", "dark", "party", "patriot", "glutton", "love", "mystic"}
KNOWN_FX = STATS | SKILLS | TRAITS | {
    "money", "money_mult", "xp", "lifespan", "item", "item_slot", "lose_item", "unequip", "flag", "unflag", "job", "edu",
    "home", "jail", "hospital", "die", "achievement", "free", "gene", "mutate", "species", "role", "reroll_persona",
    "twist", "rel", "status", "other", "baby", "swap_genes",
}
KNOWN_REQ = {
    "stage", "species", "flag", "noflag", "trait", "skill", "money", "debt", "job", "edu", "noedu", "has", "partner",
    "night", "jail", "age", "low", "status", "nostatus", "other_stage", "other_partner", "role", "norole", "other_role",
    "season", "other_stage_max",
}
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


def o(text: str, w: float = 1.0, **fx) -> Out:
    return Out(text, fx, w)


def ch(label: str, *outs: Out, check=None, fail=None, req=None, auto: str = "") -> Choice:
    return Choice(label, list(outs), check, list(fail or []), dict(req or {}), auto)


def ev(id: str, text: str, *choices: Choice, req=None, w: float = 1.0, social: bool = False, bg: str = "",
       once: bool = False, aff: tuple = ()) -> Event:
    return Event(id, text, list(choices), dict(req or {}), w, social, bg, once, tuple(aff))
