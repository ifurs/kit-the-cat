"""Pet life simulation — pure logic, no Telegram.

A Pet is one JSON document per (chat, owner). Time is simulated lazily: tick() advances everything since
the last tick in ≤1 h steps (stats decay, role passives, ageing, daily pay/bills, jail, death). Life events
come from the content/ DSL (content/dsl.py is the contract: every KNOWN_FX / KNOWN_REQ key is implemented
in Pet.apply / Pet.meets). The owner picks a choice; the chat can advise (votes) and bet; if nobody answers
the pet decides by its personality. Everything that happens is journaled into Pet.log (drained by the DB).

The clock is pluggable (engine.clock) so scripts/simulate.py can run 40 days in seconds.
"""
import inspect
import math
import random
import time
from dataclasses import dataclass, field
from datetime import datetime

from .tz import TZ
from . import sprites
from .content import events as event_content
from .content.dsl import years as parse_years
from .content.dsl import KNOWN_REQ, Choice, Event, Out, ch, ev, o
from .content.economy import (BACKGROUND_PRICES, EDUCATION, FOOD, HOME_UPKEEP, JOBS, MYSTERY_BOX, PENSION, POCKET,
                              POTION, PRICES, ROLE_FOOD, WEALTH_TAX, WELFARE)
from .content.persona import DREAMS, EPITAPHS, FEARS, FOODS, NAME_SUFFIX, NAMES, QUIRKS, TEMPERAMENTS

SPEED = 1.0          # >1 = game time runs faster (set from PET_SPEED)
DAY = 86400
clock = time.time    # replaced by the simulator


def now() -> float:
    return clock()


def hour() -> float:
    """Real seconds in one game hour."""
    return 3600 / SPEED


def kyiv(t: float | None = None) -> datetime:
    return datetime.fromtimestamp(now() if t is None else t, TZ)


def game_hour(t: float | None = None) -> int:
    t = now() if t is None else t
    if SPEED == 1:
        return kyiv(t).hour
    return int(((t + 3 * 3600) * SPEED % DAY) // 3600)


def is_night(t: float | None = None) -> bool:
    h = game_hour(t)
    return h >= 22 or h < 6


def game_day(t: float | None = None) -> int:
    t = now() if t is None else t
    return int((t + 3 * 3600) * SPEED // DAY)


TRAITS = {
    "toxic": "🤬 токсичність", "gambler": "🎰 азарт", "dark": "💀 темрява", "party": "🌙 тусовки",
    "patriot": "🇺🇦 патріотизм", "glutton": "🍔 ненажерливість", "love": "💖 ніжність", "mystic": "🔮 містика",
}
SKILLS = {"str": "💪", "int": "🧠", "cha": "😎", "luck": "🍀"}
SKILL_NAMES = {"str": "сила", "int": "розум", "cha": "харизма", "luck": "удача"}
STATS = {"hunger": "🍖", "mood": "😊", "clean": "🧼", "health": "❤️", "energy": "⚡"}
STAGES = {0: "🥚 Яйце", 1: "👶 Малюк", 2: "🧒 Підліток", 3: "🧑 Дорослий", 4: "👴 Старий"}
SPECIES_EMOJI = {"pig": "🐷", "cat": "🐱", "dog": "🐶", "fox": "🦊", "horse": "🐴", "axolotl": "🦎", "bird": "🐦"}
SPECIES_NAME = {"pig": "Свинка", "cat": "Котик", "dog": "Песик", "fox": "Лисичка", "horse": "Конячка",
                "axolotl": "Аксолотль", "bird": "Пташка"}
FALLBACK_NAMES = ["Бублик", "Пончик", "Шпротик", "Кексик", "Пиріжок", "Ґудзик", "Мармелад", "Чіпс", "Тефтелька",
                  "Пельмешка", "Галушка", "Сирник", "Кавунчик", "Буряк", "Шкварка"]
EGG_HOURS = 1.0
# life: upkeep is automatic, age is in years (the clock), life stats have tiers
YEARS_PER_DAY = {1: 8.0, 2: 2.6, 3: 2.8, 4: 2.8}     # the clock: a life of ~80 years takes ~30 real days     # passive ageing per game day, by stage
STAGE_YEARS = {2: 12, 3: 18, 4: 60}
LIFESPAN_YEARS = (74, 92)
LIFE = {  # key: (icon, name, tier titles at LIFE_STEPS)
    "fame": ("📈", "популярність", ["Ніхто", "Зірка під'їзду", "Мікроблогер", "Медійна персона", "Зірка Євробачення"]),
    "auth": ("🕶", "авторитет", ["Чистий перед законом", "Хуліган з району", "Решала", "Авторитет", "Хрещений батько"]),
    "blat": ("🤝", "блат", ["Ніхто нікого не знає", "Кум у ЦНАПі", "Свій у міськраді", "Людина зі зв'язками",
                           "Телефонне право"]),
    "fin": ("📊", "фінграмотність", ["Гроші під матрацом", "Знає, що таке відсоток", "Веде таблицю витрат", "Інвестор",
                                    "Фінансовий гуру"]),
    "attr": ("✨", "привабливість", ["Звичайний", "Охайний", "Стильний", "Красунчик району", "Ікона стилю"]),
}
LIFE_STEPS = (0, 20, 45, 70, 90)
# how a lived choice echoes into life stats: personality builds a reputation (positive deltas only)
LIFE_ECHO = {"party": (("fame", 1.0),), "cha": (("fame", 0.5), ("attr", 0.4), ("blat", 0.3)), "toxic": (("auth", 0.8),),
             "dark": (("auth", 0.5),), "str": (("auth", 0.3),), "int": (("fin", 0.8),), "love": (("attr", 0.4),),
             "patriot": (("blat", 0.4),), "gambler": (("fin", -0.3),)}
MONEY_TIERS = [(-1e12, "🕳 У боргах"), (0, "🥫 Бідний студент"), (1000, "🧾 Середній клас"), (5000, "🚗 Мажор"),
               (20000, "🛥 Олігарх")]
UPKEEP = [10, 20, 60, 180, 600]   # ₴/day cost of living by money tier (food, bills, «статус»); adults only
DEBT_HARD = 3000                   # deeper debt hurts health faster
EVENT_ENERGY = 0          # energy is automatic (kept for hosts that still check it); pace adventures with cooldowns
RECENT = 40              # last N events of a pet are not offered again (unless nothing else fits)
REPEAT_DECAY = 0.3       # weight × this per earlier time the pet lived the event: fresh content first
STORY_MAX = 10           # highlights kept for the life summary
TWIST_TAIL = 0.06        # chance of a random mini-twist after any outcome
TWIST_DAILY = 0.04       # chance per pet per game day to queue a twist event
RESURRECT = 0.10         # dead → zombie
ROMANTIC = {"crush", "partner", "ex"}
ROMANCE_MIN_STAGE = {"crush": 2, "partner": 3}  # crushes from teen age, couples and children only for adults
STATUS_NAMES = {"friend": "🤝 друг", "bestie": "💛 найкращий друг", "rival": "😤 суперник", "enemy": "⚔️ ворог",
                "crush": "😳 закоханість", "partner": "💍 партнер", "ex": "💔 колишній"}
# journal kinds worth a place in the chronicle / notices (importance 1..3)
IMPORTANCE = {"died": 3, "twist": 3, "role": 3, "heir": 2, "ach": 2, "love": 2, "jail": 2, "tier": 2, "world": 1, "job": 1,
              "casino": 1,
              "grew": 1, "hatched": 1, "social": 1, "hungry": 1}

# --- supernatural roles -------------------------------------------------------------------------
# genes/items are applied only to the rendered Look (curing restores the pet); if sprites.py draws
# role overlays itself (Look.role), the engine skips its own overrides.
ROLES = {
    "vampire": dict(name="🧛 Вампір", desc="голод майже не мучить, вдень депресує, вночі — король. Кусає ворогів.",
                    genes={"extra": "fangs"}, items=["cape@10"], undead=True,
                    bonus={"cha": 10}, night_bonus={"cha": 10, "str": 10},
                    ach=("Сто років без сонця", 3)),
    "werewolf": dict(name="🐺 Перевертень", desc="сильний, а вночі злий і ще сильніший.",
                     genes={"ears": "dog_pointy", "extra": "fangs"}, items=["scar"],
                     bonus={"str": 5}, night_bonus={"str": 15},
                     ach=("Дитя повні", 2)),
    "zombie": dict(name="🧟 Зомбі", desc="не лікується сам, зате майже не вмирає з голоду й живе довше.",
                   genes={"color": "zombie"}, items=["flies", "plaster"], undead=True,
                   bonus={"str": 10, "cha": -10}, ach=("Живіший за живих", 5)),
    "demon": dict(name="😈 Демон", desc="токсичнішає щодня, але гроші до нього липнуть.",
                  genes={"ears": "devil", "tail": "devil_tail"}, items=["horns", "flames"],
                  bonus={"luck": 12}, ach=("Продав душу вигідно", 0)),
    "angel": dict(name="😇 Ангел", desc="лікує друзів, ніжнішає, приносить удачу в любові.",
                  genes={}, items=["halo", "angel_wings"], bonus={"cha": 10},
                  ach=("Ангел-охоронець", 0)),
    "cyborg": dict(name="🤖 Кіборг", desc="не старіє, розумніший, їсть менше. Боїться відключень світла.",
                   genes={"eyes": "button"}, items=["vr@11"], bonus={"int": 15},
                   ach=("Оновлення прошивки", 3)),
    "alien": dict(name="👽 Іншопланетянин", desc="з ним щодня трапляється щось дивне.",
                  genes={"extra": "antennae", "eyes": "three"}, items=["foil"], bonus={"int": 5},
                  rand_bonus=True, ach=("Контакт встановлено", 3)),
    "quantum": dict(name="⚛️ Квантовий", desc="існує в суперпозиції: 50% пережити будь-яку смерть.",
                    genes={}, items=["sparkles"], bonus={"luck": 8}, ach=("Кіт Шредінгера", 0)),
}
UNDEAD = {r for r, d in ROLES.items() if d.get("undead")}

EVENTS: dict[str, Event] = {e.id: e for e in event_content.ALL}


def is_twist_event(e: Event) -> bool:
    return e.id.startswith("twist_") or any(out.fx.get("twist") for c in e.choices for out in c.outs + c.fail)


TWIST_IDS = {e.id for e in EVENTS.values() if is_twist_event(e)}

# Built-in social scenes: used for /pet_date and /pet_fight when content has nothing fitting,
# and as a low-weight extra in the social pool. Ids start with "_" so they never clash with content.
BUILTIN = [
    ev("_date", "{name} і {other} пішли на побачення в «Пузату хату». Свічки, компот, напруга.",
       ch("Запросити на танець", o("Танцювали до закриття. Між ними іскра! ✨", rel=15, mood=15, love=1,
                                   other=dict(mood=15, love=1)), check=("cha", 30),
          fail=[o("{name} наступив {other} на лапу. Тричі. Незручно.", rel=-3, mood=-10)], auto="party"),
       ch("Освідчитися в коханні", o("{other} почервонів і сказав «так»! 💘", status="crush", rel=20, love=3,
                                     other=dict(love=2, mood=20)), check=("cha", 40),
          fail=[o("«Давай залишимось друзями». Це боляче.", rel=-5, mood=-25, dark=1)],
          req=dict(nostatus=["partner", "crush"]), auto="love"),
       ch("Зробити пропозицію 💍", o("{other} плаче і каже «ТАК»! Весілля року!", status="partner", rel=25,
                                    achievement="Весілля року", mood=30, other=dict(mood=30)), check=("cha", 30),
          fail=[o("{other} сказав, що ще не готовий. Каблучку з'їв офіціант.", rel=-10, mood=-30, money=-300)],
          req=dict(status=["crush"], partner=False, other_partner=False), auto="love"),
       ch("Подумати про дітей 🥚", o("Через кілька днів у гнізді з'явилось яйце. Династія росте!", baby=True, love=3,
                                    mood=20, other=dict(love=3, mood=20)), req=dict(status=["partner"]), auto="love"),
       ch("Втекти через вікно туалету", o("Класика. {other} досі чекає з компотом.", rel=-12, toxic=1), auto="toxic"),
       social=True, bg="love", req=dict(stage=(2, 4), other_stage=2)),
    ev("_fight", "{name} і {other} зустрілися за гаражами. Повітря пахне насінням і бійкою.",
       ch("Битися до кінця", o("{name} переміг! {other} втік, ображено сопучи.", rel=-10, xp=10, str=2, cha=1,
                               other=dict(health=-15, mood=-15)), check=("str", 30),
          fail=[o("{other} надавав {name} по пиці. Принизливо.", rel=-10, health=-15, mood=-15, other=dict(xp=10, str=1))],
          auto="toxic"),
       ch("Кинути капцем", o("Капець влучив точно в лоб {other}. Легендарно.", rel=-8, luck=1, cha=2,
                             other=dict(health=-8)), check=("luck", 25),
          fail=[o("Капець полетів у вікно сусідки. Тепер воюють утрьох.", rel=-5, mood=-10, money=-100)],
          auto="gambler"),
       ch("Помиритися", o("Обнялися. Тепер найкращі вороги.", rel=18, love=1, other=dict(love=1)), check=("cha", 30),
          fail=[o("Простягнув лапу — отримав ляпаса.", rel=-5, mood=-10)], auto="love"),
       ch("Покликати маму", o("Мама прийшла і надавала обом. Справедливо.", rel=5, health=-5, mood=-10,
                              other=dict(health=-5, mood=-10))),
       social=True, bg="kyiv"),
    ev("_hangout", "{name} випадково зустрів {other} біля кіоску з шаурмою.",
       ch("Пригостити шаурмою", o("{other} оцінив. Тепер вони кенти.", rel=10, money=-70, love=1,
                                  other=dict(hunger=40, mood=10))),
       ch("Позичити грошей", o("{other} позичив 200 ₴ «до п'ятниці». П'ятниця не настане.", rel=-3, money=200,
                               other=dict(money=-200)), auto="gambler"),
       ch("Пліткувати про інших", o("Перемили кістки всьому чату. Зблизились.", rel=8, toxic=1, cha=1,
                                    other=dict(toxic=1)), auto="toxic"),
       ch("Зробити вигляд, що не помітив", o("{other} помітив, що ти не помітив.", rel=-5, dark=1), auto="dark"),
       social=True, w=0.5),
]
for _e in BUILTIN:
    EVENTS[_e.id] = _e
DATE_HINTS = ("date", "love", "crush", "kiss", "romance", "flirt", "wedding", "partner", "dating")
FIGHT_HINTS = ("fight", "duel", "beef", "rival", "enemy", "war", "brawl", "battle", "bully")

# --- twist tails: (text, fx, weight) --------------------------------------------------------------
TAILS = [
    ("А потім виявилось, що це все був сон. Але гроші справжні.", dict(money=100), 1),
    ("Раптом подзвонила податкова. Вона все бачила.", dict(money_mult=0.85), 1),
    ("Сусідський кіт усе бачив і тепер шантажує {name}.", dict(money=-60, dark=1), 1),
    ("На шум прибіг журналіст ТСН. {name} — зірка вечірнього випуску!", dict(cha=3, mood=10), 1),
    ("Поруч ударила блискавка. {name} тепер трохи інший…", dict(mutate=1, health=-10), 0.6),
    ("Бабця на лавці прокляла {name} просто так, для профілактики.", dict(luck=-3, mystic=1), 1),
    ("Голуб влучив {name} просто в маківку. Кажуть, на гроші.", dict(money=77, clean=-25), 1),
    ("У кишені знайшовся забутий лотерейний квиток — і він виграшний!", dict(money=300, gambler=1), 0.8),
    ("Над головою закружляла зграя ворон. Погана прикмета.", dict(dark=2, mood=-5), 1),
    ("Вночі {name} вкусив дивний блідий кажан…", dict(role="vampire", twist=True), 0.12),
    ("У повню {name} подряпав дуже волохатий «пес»…", dict(role="werewolf", twist=True), 0.12),
    ("{name} погладив кота Шредінгера. Тепер {name} одночасно є і нема.", dict(role="quantum", twist=True), 0.08),
    ("Посеред ночі {name} забрали на НЛО і повернули… не зовсім таким.", dict(role="alien", twist=True), 0.08),
    ("{name} впав у радіоактивну калюжу за гаражами.", dict(mutate=2, health=-15), 0.4),
    ("Відключили світло. Усе в холодильнику зіпсувалось.", dict(hunger=-20, mood=-5), 1),
    ("На смітнику {name} знайшов цілком нормальну річ!", dict(item_slot="head"), 0.7),
    ("Подзвонила мама й спитала, коли вже онуки.", dict(love=2, mood=-8), 1),
    ("Хтось з чату вночі лайкнув стару фотку {name}. Підозріло.", dict(cha=1, mood=5), 1),
    ("Злива змила весь бруд. Безкоштовний душ!", dict(clean=100), 1),
    ("У новинах сказали, що {food} дарує безсмертя. {name} повірив.", dict(lifespan=5, glutton=1), 0.6),
    ("Чорний кіт перейшов {name} дорогу. Двічі. Туди й назад.", dict(luck=-2), 1),
    ("Ворожка на базарі прошепотіла: «Ти обраний». Тепер {name} у це вірить.", dict(mystic=3, cha=1), 1),
    ("Сусід віддав {name} старий ноутбук «бо все одно гальмує».", dict(item="laptop"), 0.3),
    ("Невідомий доброчинець задонатив {name} 500 ₴.", dict(money=500, love=1), 0.6),
    ("Блогер зняв {name} у тікток. 2 мільйони переглядів!", dict(cha=3, money=200), 0.7),
    ("Таксист-філософ прочитав {name} лекцію про сенс життя.", dict(int=2, mystic=1), 1),
    ("{name} застряг у ліфті на 4 години. Без вайфаю.", dict(mood=-15, dark=1), 1),
    ("На городі {name} викопав козацький скарб!", dict(money=1000, patriot=2, item="sabre"), 0.15),
    ("Кум приніс самогон «на пробу».", dict(party=2, health=-6, mood=10), 1),
    ("Сонце, кава і жодного повідомлення від начальника. Ідеальний день.", dict(mood=20), 1),
    ("З'явився двійник {name}. Хто з них справжній — тепер невідомо.", dict(reroll_persona=True, twist=True), 0.12),
    ("{name} лизнув батарейку. Тепер розуміє фізику.", dict(int=3, health=-8), 0.8),
    ("{name} прокинувся… іншим видом. Лікарі розводять руками.", dict(species="random", twist=True), 0.06),
    ("Священник окропив {name} свяченою водою. Сильно.", dict(role="", clean=30, mood=-5), 0.5),
    ("Зранку на подушці знайшлася пір'їнка. Біла. Світиться.", dict(role="angel", twist=True), 0.06),
    ("{name} підписав якийсь договір дрібним шрифтом. Червоним чорнилом.", dict(role="demon", twist=True, money=666), 0.06),
    ("Сусід-айтішник «трохи поапгрейдив» {name}.", dict(role="cyborg", twist=True), 0.06),
    ("{name} знайшов на дорозі 50 гривень і не віддав. Карма записала.", dict(money=50, toxic=1), 1),
]


class SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def item_slot(item: str) -> str:
    fn = getattr(sprites, "item_slot", None)
    if fn:
        try:
            return fn(item)
        except Exception:
            pass
    if item.startswith("gen:"):
        return item.split(":")[1]
    return sprites._item(item)[1]


def item_name(item: str) -> str:
    try:
        return sprites.item_name(item)
    except Exception:
        return item.split("@")[0]


def bg_base(bg: str) -> str:
    return (bg or "").split("~")[0]


def bg_name(bg: str) -> str:
    fn = getattr(sprites, "bg_name", None)
    if fn:
        try:
            return fn(bg)
        except Exception:
            pass
    v = sprites.BACKGROUNDS.get(bg_base(bg))
    return v[0] if v else bg


def bg_ok(bg: str) -> bool:
    return bool(bg) and bg_base(bg) in sprites.BACKGROUNDS


BG_MODS = getattr(sprites, "BG_MODS", {})
OUTDOOR = getattr(sprites, "OUTDOOR", set())
SEASON_OF_MONTH = {12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring", 5: "spring", 6: "summer",
                   7: "summer", 8: "summer", 9: "autumn", 10: "autumn", 11: "autumn"}
# named windows for req season=...: (month, day) from..to inclusive, may wrap the new year
HOLIDAYS = {"newyear": ((12, 20), (1, 14)), "christmas": ((12, 20), (1, 10)), "andriy": ((12, 8), (12, 16)),
            "easter": ((3, 25), (5, 10)), "kupala": ((6, 20), (7, 10)), "halloween": ((10, 25), (11, 2)),
            "valentine": ((2, 10), (2, 16)), "independence": ((8, 20), (8, 27))}


def in_season(v) -> bool:
    """season req: "winter" | "newyear" | ["spring", "summer"] | (12, 1, 2) month numbers. Real Kyiv date."""
    k = kyiv()
    md = (k.month, k.day)
    for x in ([v] if isinstance(v, (str, int)) else v):
        if isinstance(x, int):
            if k.month == x:
                return True
        elif x in HOLIDAYS:
            a, b = HOLIDAYS[x]
            if (a <= md <= b) if a <= b else (md >= a or md <= b):
                return True
        elif SEASON_OF_MONTH[k.month] == x:
            return True
    return False


def scene(bg: str, flags: dict | None = None) -> str:
    """Add sprite background mods (season, night, temporary world-event mods) when sprites supports them."""
    if not BG_MODS or not bg_ok(bg):
        return bg
    base, mods = bg.split("~")[0], bg.split("~")[1:]
    mod = (flags or {}).get("_mod")
    if mod and mod[1] > now() and mod[0] in BG_MODS:
        mods.append(mod[0])
    if base in OUTDOOR:
        season = SEASON_OF_MONTH[kyiv().month]
        if season in BG_MODS and not any(BG_MODS.get(m, ("", -1))[1] == 0 for m in mods):
            mods.append(season)
        if is_night() and "night" in BG_MODS and not any(BG_MODS.get(m, ("", -1))[1] == 1 for m in mods):
            mods.append("night")
    return "~".join([base] + list(dict.fromkeys(mods)))


_SPRITE_ROLES: bool | None = None


def sprites_draw_roles() -> bool:
    global _SPRITE_ROLES
    if _SPRITE_ROLES is None:
        try:
            _SPRITE_ROLES = hasattr(sprites, "roles_of") or "lk.role" in inspect.getsource(sprites)
        except Exception:
            _SPRITE_ROLES = False
    return _SPRITE_ROLES


LOOK_FIELDS = set(getattr(sprites.Look, "__dataclass_fields__", {}))


@dataclass
class Result:
    text: str
    notes: list
    ok: bool | None = None       # None = no skill check
    crit: str = ""               # "win" / "fail"
    roll: int = 0                # d20
    chance: float | None = None
    twist: bool = False
    rare: bool = False
    tail: str = ""
    tail_notes: list = field(default_factory=list)
    died: bool = False
    label: str = ""


@dataclass
class Pet:
    chat_id: int
    owner_id: int
    owner_name: str = ""
    name: str = ""
    gen: int = 1
    dynasty: str = ""
    ancestors: list = field(default_factory=list)   # "Name (cause)" of previous generations
    genes: dict = field(default_factory=dict)
    state: str = "egg"
    stage: int = 0
    born: float = field(default_factory=now)
    hatched: float = 0.0
    last_tick: float = field(default_factory=now)
    lifespan: float = 82.0                        # years
    years: float = 0.0                            # age in years: the clock + the time decisions cost
    life: dict = field(default_factory=dict)      # fame / auth / blat / fin / attr, 0..100
    hunger: float = 80.0
    mood: float = 80.0
    clean: float = 100.0
    health: float = 100.0
    energy: float = 100.0
    skills: dict = field(default_factory=dict)
    traits: dict = field(default_factory=dict)
    money: float = 100.0
    xp: float = 0.0
    items: list = field(default_factory=list)
    equipped: dict = field(default_factory=dict)
    home: str = "khrushchovka"
    homes: list = field(default_factory=lambda: ["khrushchovka", "meadow"])
    job: str = ""
    job_days: int = 0
    edu: list = field(default_factory=list)
    flags: dict = field(default_factory=dict)
    rel: dict = field(default_factory=dict)       # pid -> -100..100
    status: dict = field(default_factory=dict)    # pid -> friend/bestie/rival/enemy/crush/partner/ex
    partner: str = ""                             # pid
    heir: dict = field(default_factory=dict)      # genes of the egg waiting for the next generation
    children: int = 0
    pending: dict = field(default_factory=dict)
    next_ev: float = 0.0
    recent: list = field(default_factory=list)
    seen: dict = field(default_factory=dict)      # event id -> times lived (this life)
    story: list = field(default_factory=list)     # [ts, kind, text] highlights for the life summary
    followups: list = field(default_factory=list)  # [event id, due at age in years]: consequences of earlier choices
    persona: dict = field(default_factory=dict)
    achievements: list = field(default_factory=list)
    jail_until: float = 0.0
    hospital_until: float = 0.0
    cause: str = ""
    epitaph: str = ""
    died: float = 0.0
    gday: int = 0
    cool: dict = field(default_factory=dict)
    events_done: int = 0
    role: str = ""
    role_since: float = 0.0
    counters: dict = field(default_factory=dict)
    posted: list = field(default_factory=lambda: ["", 0])   # [kyiv day, auto posts that day]
    log: list = field(default_factory=list)                  # [ts, kind, text] — drained into pet_log on save

    # --- persistence -------------------------------------------------------------------------
    def to_dict(self) -> dict:
        """Shallow snapshot for JSON (asdict deep-copies and is ~20× slower)."""
        d = {k: getattr(self, k) for k in FIELDS}
        d.update(_age=round(self.age_days, 2), _level=self.level)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Pet":
        p = cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
        if isinstance(p.partner, int):  # old drafts stored the owner id
            p.partner = ""
        if "years" not in d:  # documents from ≤ 0.2 counted real days; convert to years and seed life stats
            p.years, p.lifespan = days_to_years(p.age_days), max(days_to_years(p.lifespan), 74.0)
            p.life = seed_life(p)
            for k in ("money", *LIFE):
                p.counters.setdefault(f"tier_{k}", p.tier(k))
        return p

    # --- derived -----------------------------------------------------------------------------
    @property
    def pid(self) -> str:
        return f"{self.owner_id}:{self.gen}"

    @property
    def genome(self) -> sprites.Genome:
        return sprites.Genome.from_dict(self.genes)

    @property
    def species(self) -> str:
        return self.genes.get("species", "cat")

    @property
    def alive(self) -> bool:
        return self.state == "alive"

    @property
    def age_days(self) -> float:
        end = self.died or now()
        return max(0.0, (end - self.hatched) * SPEED / DAY) if self.hatched else 0.0

    @property
    def level(self) -> int:
        return 1 + int(math.sqrt(max(0, self.xp) / 20))

    @property
    def jailed(self) -> bool:
        return self.jail_until > now()

    @property
    def in_hospital(self) -> bool:
        return self.hospital_until > now()

    @property
    def rarity(self) -> tuple[int, str]:
        return sprites.rarity(self.genome)

    def tier(self, key: str) -> int:
        if key == "money":
            return max(i for i, (lo, _) in enumerate(MONEY_TIERS) if self.money >= lo)
        v = self.life.get(key, 0)
        return max(i for i, lo in enumerate(LIFE_STEPS) if v >= lo)

    def tier_name(self, key: str, t: int | None = None) -> str:
        t = self.tier(key) if t is None else t
        if key == "money":
            return MONEY_TIERS[t][1]
        return f"{LIFE[key][0]} {LIFE[key][2][t]}"

    def _tiers(self) -> None:
        """Announce new peaks of money and life-stat tiers (journal, story, achievements at the top)."""
        for key in ("money", *LIFE):
            t = self.tier(key)
            best = self.counters.get(f"tier_{key}", 1 if key == "money" else 0)  # hosts set it at birth/migration
            if t > best:
                self.counters[f"tier_{key}"] = t
                self.note("tier", f"{self.tier_name(key)} — {self.name} піднявся на новий рівень!")
                if t == 4:
                    self.ach(MONEY_TIERS[4][1][2:] if key == "money" else LIFE[key][2][4])

    def note(self, kind: str, text: str) -> None:
        self.log.append([int(now()), kind, text[:500]])
        self.log = self.log[-60:]
        if IMPORTANCE.get(kind, 0) >= 2 and kind not in ("died", "heir") and all(x[2] != text[:200] for x in self.story):
            self.story.append([int(now()), kind, text[:200]])
            if len(self.story) > STORY_MAX:  # keep the first moment; drop the oldest of the least important
                low = min(IMPORTANCE.get(k, 0) for _, k, _ in self.story[1:])
                del self.story[next(i for i in range(1, len(self.story)) if IMPORTANCE.get(self.story[i][1], 0) == low)]

    def ach(self, name: str) -> str | None:
        if name in self.achievements:
            return None
        self.achievements.append(name)
        self.note("ach", f"🏆 {self.name}: досягнення «{name}»")
        return f"🏆 {name}"

    def top_traits(self, n: int = 3) -> list[str]:
        return [t for t in sorted(TRAITS, key=lambda t: -self.traits.get(t, 0)) if self.traits.get(t, 0) >= 3][:n]

    def skill(self, s: str) -> float:
        """Effective skill: base + role bonuses (+ night bonuses, alien chaos)."""
        v = self.skills.get(s, 10)
        r = ROLES.get(self.role)
        if r:
            v += r.get("bonus", {}).get(s, 0)
            if is_night():
                v += r.get("night_bonus", {}).get(s, 0)
            if r.get("rand_bonus"):
                v += random.Random(f"{self.pid}:{game_day()}:{s}").randint(-10, 20)
        if self.health < 30:
            v -= 10
        if self.mood > 80:
            v += 5
        return v

    def mood_face(self) -> str:
        if self.state == "dead":
            return "dead"
        night = is_night()
        if self.role == "werewolf" and night:
            return "angry"
        if night and game_hour() < 7 and not self.pending and self.role != "vampire":
            return "sleep"
        if self.health < 35:
            return "sick"
        if self.traits.get("toxic", 0) > 25 and self.mood < 60:
            return "angry"
        if self.mood < 30 or self.hunger < 15:
            return "sad"
        if self.mood > 70 and self.hunger > 40:
            return "happy"
        return "ok"

    def look(self, background: str = "") -> sprites.Look:
        genes = dict(self.genes)
        eq = dict(self.equipped)
        role = ROLES.get(self.role)
        if role and not sprites_draw_roles():
            genes.update({k: v for k, v in role["genes"].items() if v in sprites.GENES.get(k, {})})
            for it in role["items"]:
                if sprites._item(it)[2]:
                    eq[item_slot(it)] = it
        items = list(eq.values())
        bg = background or self.home
        if self.jailed:
            items = [i for i in items if item_slot(i) not in ("outfit",)] + ["prison", "bars"]
            bg = "prison"
        elif self.in_hospital:
            items = [i for i in items if item_slot(i) not in ("outfit", "held")] + ["plaster"]
            bg = "hospital"
        if self.stage == 4 and not any(item_slot(i) == "held" for i in items):
            items.append("cane")
        if self.mood < 15 and self.alive and not any(item_slot(i) == "aura" for i in items):
            items.append("storm")
        kw = dict(genes=sprites.Genome.from_dict(genes), stage=self.stage, mood=self.mood_face(), items=items,
                  background=scene(bg, self.flags) if bg_ok(bg) else "meadow", fat=min(1.0, self.traits.get("glutton", 0) / 40),
                  dirty=self.clean < 25, hungry=self.hunger < 25 and self.alive, ghost=self.state == "dead",
                  egg_cracks=0 if self.state != "egg" else (2 if now() - self.born > EGG_HOURS * hour() * 0.7 else 1),
                  quantum=self.role == "quantum" and self.alive, role=self.role if self.alive else "")
        if self.stage == 0:
            kw["stage"] = 0
        return sprites.Look(**{k: v for k, v in kw.items() if k in LOOK_FIELDS})

    def fmt(self, text: str, other: "Pet | None" = None) -> str:
        p = self.persona
        try:
            return text.format_map(SafeDict(
                name=self.name, owner=self.owner_name, food=p.get("food", "борщ"), dream=p.get("dream", ""),
                fear=p.get("fear", ""), quirk=p.get("quirk", ""), temper=p.get("temper", ""),
                other=other.name if other else "хтось", other_owner=other.owner_name if other else "хтось",
                money=f"{int(self.money)}", role=ROLES.get(self.role, {}).get("name", ""),
            ))
        except (ValueError, IndexError, AttributeError):
            return text

    # --- lifecycle ---------------------------------------------------------------------------
    def hatch(self, t: float) -> None:
        self.state, self.stage, self.hatched, self.last_tick, self.gday = "alive", 1, t, t, game_day(t)
        self.next_ev = t + random.uniform(1, 3) * hour()
        self.note("hatched", f"🐣 Вилупився {self.name} ({SPECIES_NAME.get(self.species, self.species)})!")

    def die(self, cause: str, rng: random.Random | None = None, natural: bool = False) -> bool:
        """Returns True if the pet really died (quantum and zombie twists can cancel it)."""
        rng = rng or random.Random()
        if not self.alive:
            return False
        if self.role == "quantum" and rng.random() < 0.5:
            self.health, self.hunger = max(self.health, 45.0), max(self.hunger, 30.0)
            self.lifespan = max(self.lifespan, self.years + 8)
            self.counters["dodged"] = self.counters.get("dodged", 0) + 1
            self.note("twist", f"⚛️ {self.name} мав загинути ({cause}), але в цьому всесвіті вижив. В іншому — ні.")
            self.ach("Кіт Шредінгера")
            return False
        if not natural and self.role not in UNDEAD and rng.random() < RESURRECT:
            self.set_role("zombie")
            self.health, self.hunger, self.mood = 60.0, 50.0, 40.0
            self.lifespan = max(self.lifespan, self.years + 30)
            self.note("twist", f"🧟 СЮЖЕТНИЙ ПОВОРОТ! {self.name} {cause}… а на третю ніч виліз з могили. Тепер це зомбі.")
            return False
        self.state, self.cause, self.died = "dead", cause, now()
        if natural:
            self.counters["natural"] = 1
        self.epitaph = rng.choice(EPITAPHS)
        self.pending = {}
        self.jail_until = self.hospital_until = 0.0
        self.note("died", f"⚰️ {self.name} {cause}. Прожив {int(self.years)} {plural(int(self.years), 'рік', 'роки', 'років')}, рівень {self.level}.")
        return True

    def set_role(self, role: str) -> str | None:
        if role == self.role or (role and role not in ROLES):
            return None
        old = self.role
        self.role, self.role_since = role, now()
        if role:
            r = ROLES[role]
            if role == "zombie":
                self.lifespan += 25
            if role == "cyborg" and self.stage == 4:
                self.stage = 3
            self.counters[f"role_{role}"] = 1
            self.note("role", f"🌀 {self.name} тепер {r['name']}! ({r['desc']})")
            return f"🌀 {r['name']}"
        self.note("role", f"✨ {self.name} зцілився: більше не {ROLES[old]['name']}")
        return f"✨ вже не {ROLES[old]['name']}"

    def tick(self, t: float | None = None, rng: random.Random | None = None) -> None:
        """Advance time to t in ≤1 game-hour steps. Everything notable lands in self.log."""
        t = now() if t is None else t
        rng = rng or random.Random()
        if self.state == "egg":
            if (t - self.born) / hour() < EGG_HOURS:
                self.last_tick = t
                return
            self.hatch(min(t, self.born + EGG_HOURS * hour()))
        if not self.alive:
            self.last_tick = t
            return
        hours = min(max(0.0, (t - self.last_tick) / hour()), 24 * 14)
        at = t - hours * hour()
        while hours > 1e-6 and self.alive:
            step = min(1.0, hours)
            at += step * hour()
            self._step(step, at, rng)
            hours -= step
        self.last_tick = t

    def _step(self, h: float, at: float, rng: random.Random) -> None:
        role = self.role
        night = is_night(at)
        self.years += YEARS_PER_DAY.get(self.stage, 1.4) * h / 24 * (0.5 if role == "vampire" else 1)
        # upkeep is automatic: fed and washed while there is money; debt shows on the sprite and hurts
        broke = self.money < 0 and self.stage >= 3
        k = min(1.0, 0.2 * h)
        self.hunger += ((25.0 if broke else 85.0) - self.hunger) * k
        self.clean += ((30.0 if broke else 90.0) * (0.6 if role == "zombie" else 1) - self.clean) * k
        self.mood += ((35.0 if broke else 65.0) - self.mood) * min(1.0, 0.03 * h)
        if role == "vampire":
            self.mood = max(0.0, min(100.0, self.mood + (1.0 if night else -0.5) * h))
        elif role == "werewolf" and night:
            self.traits["toxic"] = self.traits.get("toxic", 0) + 0.05 * h
        if self.in_hospital:
            self.health = min(100.0, self.health + 3 * h)
        self.energy = 100.0  # automatic, like food and sleep
        if broke:
            self.health -= (0.8 if self.money < -DEBT_HARD else 0.3) * h * (0.25 if role == "zombie" else 1)
        elif self.mood < 10:
            self.health -= 0.5 * h
        elif role != "zombie":
            self.health = min(100.0, self.health + 1.0 * h * (1.5 if role == "angel" else 1) * (0.5 if self.stage == 4 else 1))
        if self.health <= 0:
            self.die("не витримав боргів і дзвінків колекторів" if broke else "згас від туги й самотності", rng)
            return
        if not self._age_checks(rng):
            return
        if self.jail_until and at >= self.jail_until:
            self.jail_until = 0.0
            self.note("jail", f"🔓 {self.name} вийшов на волю")
        if self.hospital_until and at >= self.hospital_until:
            self.hospital_until = 0.0
        if broke and not self.flags.get("_warned"):
            self.flags["_warned"] = 1
            self.note("hungry", f"🕳 {self.name} у боргах: економить на їжі й митті. Треба заробити!")
        elif not broke:
            self.flags.pop("_warned", None)
        if self.health < 30 and not self.flags.get("_dying"):
            self.flags["_dying"] = 1
            self.note("hungry", f"❗ {self.name} при смерті (здоров'я {self.health:.0f}). Лікування — у ⋯ меню.")
        elif self.health > 50:
            self.flags.pop("_dying", None)
        d = game_day(at)
        if d != self.gday:
            if self.gday:
                self._daily(rng)
            self.gday = d

    def _age_checks(self, rng: random.Random) -> bool:
        """Grow up by years, die of old age. False if the pet died."""
        if self.years >= self.lifespan:
            self.die(rng.choice(["помер від старості у теплому ліжку, як справжній дід",
                                 "заснув і не прокинувся. Тихо, з посмішкою",
                                 "пішов на вічну пенсію, яку нарешті проіндексували"]), rng, natural=True)
            return self.alive
        for st, yrs in STAGE_YEARS.items():
            if self.stage < st and self.years >= yrs and not (st == 4 and self.role == "cyborg"):
                self.stage = st
                for sk in rng.sample(list(SKILLS), 3):
                    self._add(sk, 4)
                self.note("grew", f"{STAGES[st]}: {self.name} подорослішав (навички підросли)")
                if st == 4 and "cane" not in self.items:
                    self.items.append("cane")
        return True

    def _daily(self, rng: random.Random) -> None:
        """Once per game day: money in/out, role passives, achievements, twist roll."""
        inc, why = 0, ""
        if self.job in JOBS and not self.jailed:
            j = JOBS[self.job]
            lo, hi = j.get("pay_range", (j["pay"], j["pay"]))
            inc = int(rng.randint(lo, hi) * (1 + min(self.job_days, 30) * 0.02) * (1 + self.life.get("blat", 0) / 200))
            if self.in_hospital:
                inc //= 2
            why = j["name"]
            self.job_days += 1
            self.xp += 3
            for k, v in j["drift"].items():
                self._add(k, v)
            risk = j.get("risk")
            if risk and rng.random() < risk[1]:
                self.jail_until = now() + 24 * hour()
                self.flags["jailed_times"] = self.flags.get("jailed_times", 0) + 1
                self.note("jail", f"⛓ {self.name} спалився на роботі ({j['name']}) і сів на добу")
            if self.job_days == 30:
                self.ach("Ветеран праці")
        elif self.stage <= 2:
            inc, why = POCKET, "кишенькові від бабусі"
        elif not self.job and not self.jailed:
            inc, why = (PENSION, "пенсія") if self.stage == 4 else (WELFARE, "соцдопомога")
        if self.role == "demon" and inc > 0:
            inc = int(inc * 1.3)
        L, extra = self.life, []
        if not self.jailed and self.tier("fame") >= 2:
            extra.append(("реклама", int(L["fame"] * 4)))
        if not self.jailed and self.tier("auth") >= 2:
            extra.append(("«дах»", int(L["auth"] * 3)))
        if self.money > 0 and L.get("fin", 0) >= 20:
            extra.append(("відсотки", int(self.money * 0.004 * L["fin"] / 100)))
        inc += sum(v for _, v in extra)
        cost = HOME_UPKEEP.get(self.home, int(BACKGROUND_PRICES.get(self.home, 500) * 0.01))
        cost += UPKEEP[self.tier("money")] if self.stage >= 3 else 0
        tax = int(max(0, self.money - WEALTH_TAX[0]) * WEALTH_TAX[1])
        self.money += inc - cost - tax
        self.note("money", f"💰 {why or 'без доходу'}" + "".join(f" + {w}" for w, _ in extra)
                  + f": {inc:+d} ₴, побут −{cost} ₴" + (f", податок −{tax} ₴" if tax else ""))
        self._life_daily(rng)
        # role passives
        role, r = self.role, ROLES.get(self.role)
        if role == "vampire":
            self._add("dark", 0.5)
        elif role == "demon":
            self._add("toxic", 1)
            if self.money >= 5000:
                self.ach("Продав душу вигідно")
        elif role == "angel":
            self._add("love", 0.5)
        elif role == "alien" and rng.random() < 0.5:
            self.counters["weird"] = self.counters.get("weird", 0) + 1
            kind = rng.randrange(4)
            if kind == 0:
                self.apply({"mutate": 1}, None, rng)
                self.note("twist", f"👽 {self.name} прокинувся з новою частиною тіла. Звідки — не каже.")
            elif kind == 1:
                a, b = rng.sample(list(SKILLS), 2)
                self.skills[a], self.skills[b] = self.skills.get(b, 10), self.skills.get(a, 10)
                self.note("life", f"👽 У {self.name} помінялися місцями {SKILL_NAMES[a]} і {SKILL_NAMES[b]}.")
            elif kind == 2:
                t = rng.choice(list(TRAITS))
                self._add(t, 4)
                self.note("life", f"👽 {self.name} всю ніч передавав сигнали в космос. +{TRAITS[t]}")
            else:
                self.money += 250
                self.note("life", f"👽 {self.name} продав вченим пробірку власного слизу. +250 ₴")
        if r and r.get("ach") and r["ach"][1] and (now() - self.role_since) * SPEED / DAY >= r["ach"][1]:
            self.ach(r["ach"][0])
        if self.years >= 85:
            self.ach("Довгожитель")
        if self.events_done >= 50:
            self.ach("Ветеран пригод")
        if self.money < -3000 and not self.flags.get("_collectors"):
            self.flags["_collectors"] = 1
            self.apply({"lose_item": "random", "mood": -20}, None, rng)
            self.note("twist", f"📞 До {self.name} прийшли колектори. Забрали річ і гідність.")
        elif self.money > -1000:
            self.flags.pop("_collectors", None)
        if rng.random() < TWIST_DAILY:
            self.flags["_twist"] = 1

    def _life_daily(self, rng: random.Random) -> None:
        """Life stats fade a little, and high tiers bring their own trouble."""
        L = self.life
        for k, fade, floor in (("fame", 0.4, 10), ("auth", 0.3, 5), ("attr", 0.3, 15)):
            if L.get(k, 0) > floor:
                L[k] = max(floor, L[k] - fade)
        a = L.get("auth", 0)
        if a >= 45 and not self.jailed and rng.random() < (a - 40) / 500:
            self.apply({"jail": 24, "money_mult": 0.85, "auth": 3}, None, rng)
            self.note("jail", f"🚔 Облава! {self.name} взяли разом з усім «районом». Авторитет росте навіть за ґратами.")
        if L.get("blat", 0) >= 70 and rng.random() < 0.02:
            self.apply({"money_mult": 0.7, "blat": -15}, None, rng)
            self.note("twist", f"🕵️ НАБУ зацікавилося, звідки в {self.name} стільки «кумів». Частину статків довелося віддати.")
        if L.get("fame", 0) >= 70 and rng.random() < 0.04:
            self.apply({"mood": -15, "fame": -5}, None, rng)
            self.note("life", f"📰 Скандал! Хтось злив старі пости {self.name}. Хейтери в коментарях, хайп у трендах.")
        if self.tier("money") == 4 and rng.random() < 0.03:
            self.apply({"money_mult": 0.9}, None, rng)
            self.note("life", f"🧾 До {self.name} прийшла податкова «просто поговорити». Розмова коштувала 10% статків.")
        self._tiers()

    # --- effects -----------------------------------------------------------------------------
    def _add(self, key: str, delta: float) -> None:
        if key in STATS:
            setattr(self, key, max(0.0, min(100.0, getattr(self, key) + delta)))
        elif key in SKILLS:
            self.skills[key] = max(0.0, min(100.0, self.skills.get(key, 10) + delta))
        elif key in TRAITS:
            self.traits[key] = max(0.0, min(100.0, self.traits.get(key, 0) + delta))
        elif key in LIFE:
            self.life[key] = max(0.0, min(100.0, self.life.get(key, 0) + delta))

    def give(self, item: str, equip: bool = True) -> str:
        if item not in self.items:
            self.items.append(item)
            if len(self.items) > 60:
                old = next((i for i in self.items if i not in self.equipped.values()), None)
                if old:
                    self.items.remove(old)
        slot = item_slot(item)
        if equip and slot:
            self.equipped[slot] = item
        return item_name(item)

    def random_item(self, slot: str, rng: random.Random) -> str:
        gen = getattr(sprites, "random_item", None)
        if gen and rng.random() < 0.45:
            try:
                it = gen(slot, rng)
                if item_slot(it) == slot or slot not in sprites.SLOTS:
                    return it
            except Exception:
                pass
        pool = [i for i, v in sprites.ITEMS.items() if v[1] == slot and i not in ("prison", "bars", "plaster")]
        if not pool:
            pool = [i for i in PRICES if i in sprites.ITEMS]
        it = rng.choice(pool)
        return it + (f"@{rng.randrange(1, len(sprites.TINTS))}" if rng.random() < 0.5 else "")

    def mutate(self, n: int, rng: random.Random) -> list[str]:
        genes = ["ears", "tail", "face", "eyes", "pattern", "mark", "extra", "color"]
        out = []
        for gene in rng.sample(genes, min(n, len(genes))):
            vals = [v for v in sprites.GENES[gene] if v != self.genes.get(gene)]
            if vals:
                self.genes[gene] = rng.choice(vals)
                out.append(sprites.GENES[gene][self.genes[gene]][0])
        return out

    def transform(self, species: str, rng: random.Random) -> bool:
        if species == "random":
            species = rng.choice([s for s in sprites.SPECIES if s != self.species])
        if species not in sprites.SPECIES or species == self.species:
            return False
        self.genes["species"] = species
        for gene in ("ears", "tail", "face"):
            nat = [k for k, v in sprites.GENES[gene].items() if v[1] == species]
            if nat:
                self.genes[gene] = rng.choice(nat)
        return True

    def apply(self, fx: dict, other: "Pet | None" = None, rng: random.Random | None = None) -> list[str]:
        """Apply DSL effects. Returns short human notes (plain text)."""
        rng = rng or random.Random()
        notes: list[str] = []
        for k, v in fx.items():
            if k in STATS or k in SKILLS or k in TRAITS or k in LIFE:
                if k == "fame" and v > 0:  # charm helps to go viral
                    v = round(v * (1 + self.life.get("attr", 0) / 200), 1)
                self._add(k, v)
                icon = STATS.get(k) or SKILLS.get(k) or (LIFE[k][0] if k in LIFE else TRAITS[k].split()[0])
                notes.append(f"{icon}{'+' if v > 0 else ''}{v:g}")
            elif k == "money":
                if v < 0 and self.life.get("fin", 0) > 0:  # financially literate pets lose less
                    v = round(v * (1 - self.life["fin"] / 300))
                self.money += v
                notes.append(f"{'+' if v > 0 else ''}{v:g} ₴")
            elif k == "then":
                fid, after = v
                if fid in EVENTS and all(f[0] != fid for f in self.followups):
                    self.followups = (self.followups + [[fid, self.years + parse_years(after)]])[-8:]
            elif k == "time":
                y = parse_years(v)
                self.years += y
                notes.append(f"⏳ +{time_label(y)}")
            elif k == "money_mult":
                if self.money > 0:
                    lost = self.money * (1 - v)
                    self.money *= v
                    notes.append(f"💸 {'−' if lost > 0 else '+'}{abs(lost):.0f} ₴" if v != 0 else "💸 втратив усі гроші")
            elif k == "xp":
                self.xp += v
            elif k == "lifespan":
                self.lifespan += v
                notes.append(f"🕯{'+' if v > 0 else ''}{v:g} р. життя")
            elif k == "item":
                for it in ([v] if isinstance(v, str) else v):
                    notes.append(f"🎁 {self.give(it)}")
            elif k == "item_slot":
                notes.append(f"🎁 {self.give(self.random_item(v, rng))}")
            elif k == "lose_item":
                pool = [i for i in self.items if i != "cane"]
                it = (rng.choice(pool) if pool else None) if v == "random" else \
                    next((i for i in self.items if i == v or i.split("@")[0] == v), None)
                if it:
                    self.items.remove(it)
                    self.equipped = {s: i for s, i in self.equipped.items() if i != it}
                    notes.append(f"💨 втратив {item_name(it)}")
            elif k == "unequip":
                if v in ("all", True):
                    self.equipped = {}
                else:
                    self.equipped.pop(v, None)
            elif k == "flag":
                if isinstance(v, dict):
                    self.flags.update(v)
                else:
                    self.flags.update({f: 1 for f in ([v] if isinstance(v, str) else v)})
            elif k == "unflag":
                for f in ([v] if isinstance(v, str) else v):
                    self.flags.pop(f, None)
            elif k == "job":
                if v and v in JOBS:
                    if self.job != v:
                        self.job, self.job_days = v, 0
                        for it in JOBS[v]["items"]:
                            self.give(it)
                        notes.append(f"💼 {JOBS[v]['name']}")
                        self.note("job", f"💼 {self.name} тепер {JOBS[v]['name']}")
                        self.ach("Перша робота")
                elif not v and self.job:
                    notes.append(f"🔥 звільнений: {JOBS.get(self.job, {}).get('name', self.job)}")
                    self.note("job", f"🔥 {self.name} звільнили з роботи")
                    self.job = ""
            elif k == "edu":
                if v not in self.edu:
                    self.edu.append(v)
                    notes.append(f"🎓 {EDUCATION.get(v, v)}")
            elif k == "home":
                if bg_ok(v):
                    if v not in self.homes:
                        self.homes.append(v)
                    self.home = v
                    notes.append(f"🏠 {bg_name(v)}")
            elif k == "jail":
                self.jail_until = max(self.jail_until, now()) + v * hour()
                self.flags["jailed_times"] = self.flags.get("jailed_times", 0) + 1
                notes.append(f"⛓ {v} год. за ґратами")
                self.note("jail", f"⛓ {self.name} сів на {v} год.")
                if self.flags["jailed_times"] >= 3:
                    self.ach("Рецидивіст")
            elif k == "hospital":
                self.hospital_until = max(self.hospital_until, now()) + v * hour()
                notes.append(f"🏥 {v} год. у лікарні")
            elif k == "free":
                if v and self.jail_until:
                    self.jail_until = 0.0
                    notes.append("🔓 на волі")
            elif k == "achievement":
                n = self.ach(v)
                if n:
                    notes.append(n)
            elif k == "die":
                if self.die(v, rng):
                    notes.append("☠️ помер")
                else:
                    notes.append("🌀 …але не до кінця")
            elif k == "gene":
                changed = [g for g, val in v.items() if g in sprites.GENES and val in sprites.GENES[g]
                           or g in ("hue", "sat", "val", "hue2", "sat2", "val2", "iris", "iris2")]
                for g in changed:
                    self.genes[g] = v[g]
                if changed:
                    notes.append("🧬 зовнішність змінилась")
            elif k == "mutate":
                got = self.mutate(int(v), rng)
                if got:
                    notes.append("🧬 мутація: " + ", ".join(got))
            elif k == "species":
                if self.transform(v, rng):
                    notes.append(f"🧬 тепер {SPECIES_NAME.get(self.species, self.species)}")
                    self.note("twist", f"🧬 {self.name} перетворився на {SPECIES_NAME.get(self.species, '')}!")
            elif k == "role":
                n = self.set_role(v)
                if n:
                    notes.append(n)
            elif k == "reroll_persona":
                if v:
                    t, lean = rng.choice(TEMPERAMENTS)
                    self.persona.update(temper=t, lean=lean, dream=rng.choice(DREAMS), fear=rng.choice(FEARS),
                                        quirk=rng.choice(QUIRKS))
                    notes.append(f"🌀 новий характер: {t}")
            elif k == "twist":
                pass  # marker, handled by resolve()
            elif other is None:
                continue  # social-only effects without a partner pet
            elif k == "rel":
                self.set_rel(other, v)
                notes.append(f"{'💞' if v > 0 else '💢'}{'+' if v > 0 else ''}{v:g} стосунки")
            elif k == "status":
                if v in ROMANCE_MIN_STAGE and min(self.stage, other.stage) < ROMANCE_MIN_STAGE[v]:
                    continue  # no romance for kids: relationship points still count, the status doesn't
                self.set_status(other, v)
                notes.append(STATUS_NAMES.get(v, v))
            elif k == "other":
                sub = other.apply(v, self, rng)
                if sub:
                    notes.append(f"{other.name}: " + " ".join(sub))
            elif k == "baby":
                if v and min(self.stage, other.stage) >= ROMANCE_MIN_STAGE["partner"]:
                    try:
                        heir = sprites.breed(self.genome, other.genome, rng).to_dict()
                    except Exception:
                        heir = dict(self.genes)
                    for p in (self, other):
                        p.heir, p.children = heir, p.children + 1
                        p.note("heir", f"🥚 У {self.name} і {other.name} з'явилося яйце-спадкоємець!")
                    notes.append("🥚 яйце-спадкоємець")
                    if self.children >= 3:
                        self.ach("Багатодітний")
            elif k == "swap_genes":
                if v:
                    self.genes, other.genes = other.genes, self.genes
                    notes.append(f"🔄 {self.name} і {other.name} помінялися тілами")
                    for p in (self, other):
                        p.note("twist", f"🔄 {self.name} і {other.name} прокинулися в тілах одне одного!")
        echo: dict[str, float] = {}
        for k, v in fx.items():
            if k in LIFE_ECHO and isinstance(v, (int, float)) and v > 0:
                for stat, m in LIFE_ECHO[k]:
                    echo[stat] = echo.get(stat, 0) + v * m
        if fx.get("jail"):
            echo["auth"] = echo.get("auth", 0) + 4
        for stat, v in echo.items():
            if stat not in fx:
                self._add(stat, v)
                if abs(v) >= 1:
                    notes.append(f"{LIFE[stat][0]}{'+' if v > 0 else ''}{v:.0f}")
        if self.money >= 10000:
            self.ach("Мільйонер (майже)")
        self._tiers()
        return notes

    def set_rel(self, other: "Pet", delta: float) -> None:
        for a, b in ((self, other), (other, self)):
            a.rel[b.pid] = max(-100.0, min(100.0, a.rel.get(b.pid, 0.0) + delta))
            cur = a.status.get(b.pid, "")
            if cur not in ROMANTIC:
                s = a.rel[b.pid]
                new = "bestie" if s >= 70 else "friend" if s >= 30 else "enemy" if s <= -70 else "rival" if s <= -30 else ""
                if new:
                    a.status[b.pid] = new
                else:
                    a.status.pop(b.pid, None)
            if sum(1 for s in a.status.values() if s == "enemy") >= 5:
                a.ach("Скандаліст")
            if a.rel[b.pid] <= -60 and delta < 0 and cur == "partner":
                a.set_status_one(b, "ex")
        if len(self.rel) > 80:   # forget the least important acquaintances
            for k in sorted(self.rel, key=lambda k: abs(self.rel[k]))[:len(self.rel) - 80]:
                self.rel.pop(k, None)
                self.status.pop(k, None)

    def set_status_one(self, b: "Pet", status: str) -> None:
        if status == "partner" and self.partner and self.partner != b.pid:
            # no bigamy: the old partner becomes an ex; their side is updated by fix_partners()
            old = self.partner
            self.status[old] = "ex"
            self.rel[old] = min(self.rel.get(old, 0.0), -40.0)
            self.partner = ""
            self.note("love", f"💔 {self.name} кинув свою пару заради {b.name}. Скандал на весь район!")
            self.traits["toxic"] = self.traits.get("toxic", 0) + 3
        self.status[b.pid] = status
        if status == "partner":
            self.partner = b.pid
            self.note("love", f"💍 {self.name} і {b.name} тепер пара!")
        elif status == "ex" and self.partner == b.pid:
            self.partner = ""
            self.note("love", f"💔 {self.name} і {b.name} розійшлися")
            if sum(1 for s in self.status.values() if s == "ex") >= 3:
                self.ach("Казанова")
        elif status == "crush":
            self.note("love", f"😳 {self.name} закохався в {b.name}")

    def set_status(self, other: "Pet", status: str) -> None:
        self.set_status_one(other, status)
        other.set_status_one(self, status)

    # --- requirements ------------------------------------------------------------------------
    def meets(self, req: dict, other: "Pet | None" = None) -> bool:
        if self.jailed and not req.get("jail"):
            return False
        if not req.keys() <= KNOWN_REQ:  # fail closed on typos / keys from a newer contract
            return False
        for k, v in req.items():
            if k == "stage":
                if isinstance(v, (tuple, list)):
                    if not v[0] <= self.stage <= v[1]:
                        return False
                elif self.stage < v:
                    return False
            elif k == "species" and self.species not in ([v] if isinstance(v, str) else v):
                return False
            elif k == "flag":
                if isinstance(v, str):
                    if not self.flags.get(v):
                        return False
                elif isinstance(v, dict):
                    if any(self.flags.get(f, 0) != n for f, n in v.items()):
                        return False
                elif not all(self.flags.get(f) for f in v):
                    return False
            elif k == "noflag" and any(self.flags.get(f) for f in ([v] if isinstance(v, str) else v)):
                return False
            elif k == "trait" and any(self.traits.get(t, 0) < n for t, n in v.items()):
                return False
            elif k == "skill" and any(self.skill(s) < n for s, n in v.items()):
                return False
            elif k == "money" and self.money < v:
                return False
            elif k == "debt" and self.money > -v:
                return False
            elif k == "job":
                if (v == "any" and not self.job) or (v == "none" and self.job) or \
                        (v not in ("any", "none") and self.job not in ([v] if isinstance(v, str) else v)):
                    return False
            elif k == "edu" and v not in self.edu:
                return False
            elif k == "noedu" and v in self.edu:
                return False
            elif k == "has" and not any(i == v or i.split("@")[0] == v for i in self.items):
                return False
            elif k == "partner" and bool(self.partner) != bool(v):
                return False
            elif k == "night" and is_night() != bool(v):
                return False
            elif k == "jail" and self.jailed != bool(v):
                return False
            elif k == "age" and not v[0] <= self.age_days <= v[1]:
                return False
            elif k == "years" and not v[0] <= self.years <= v[1]:
                return False
            elif k == "life" and any(self.life.get(s, 0) < n for s, n in v.items()):
                return False
            elif k == "tier" and any(self.tier(s) < n for s, n in v.items()):
                return False
            elif k == "tier_max" and any(self.tier(s) > n for s, n in v.items()):
                return False
            elif k == "low" and any(getattr(self, s, 0) > n for s, n in v.items()):
                return False
            elif k == "role":
                if v == "any":
                    if not self.role:
                        return False
                elif self.role not in ([v] if isinstance(v, str) else v):
                    return False
            elif k == "norole":
                if v and self.role and (v is True or self.role in ([v] if isinstance(v, str) else v)):
                    return False
            elif k == "status":
                cur = self.status.get(other.pid, "") if other else None
                if cur not in ([v] if isinstance(v, str) else v):
                    return False
            elif k == "nostatus" and other and self.status.get(other.pid, "") in ([v] if isinstance(v, str) else v):
                return False
            elif k == "other_stage":
                if not other:
                    return False
                if isinstance(v, (tuple, list)):
                    if not v[0] <= other.stage <= v[1]:
                        return False
                elif other.stage < v:
                    return False
            elif k == "season" and not in_season(v):
                return False
            elif k == "other_stage_max" and (not other or other.stage > v):
                return False
            elif k == "other_partner" and other and bool(other.partner) != bool(v):
                return False
            elif k == "other_role":
                if not other:
                    return False
                if v == "any":
                    if not other.role:
                        return False
                elif other.role not in ([v] if isinstance(v, str) else v):
                    return False
        return True

    # --- events ------------------------------------------------------------------------------
    def eligible(self, e: Event, other: "Pet | None", fresh: bool = True) -> bool:
        if e.social != bool(other) or (fresh and e.id in self.recent):
            return False
        if e.once and self.flags.get(f"seen_{e.id}"):
            return False
        return self.meets(e.req, other) and bool(self.options(e, other))

    def pick_event(self, others: list["Pet"], rng: random.Random, kind: str = "") -> tuple[Event | None, "Pet | None"]:
        """kind: "" any, "solo", "social", "twist", "date", "fight". Others = other pets in the chat."""
        if kind in ("", "solo") and self.followups:  # an earlier choice comes back
            self.followups = [f for f in self.followups if f[0] in EVENTS and self.years - f[1] < 15]
            for f in sorted(self.followups, key=lambda f: f[1]):
                e = EVENTS[f[0]]
                if self.years >= f[1] and self.eligible(e, None, fresh=False):
                    self.followups.remove(f)
                    return e, None
        pool = [x for x in others if x.alive and x.pid != self.pid and x.stage >= 1 and not x.jailed]
        twist = kind == "twist" or (not kind and self.flags.get("_twist"))
        other = None
        if kind in ("social", "date", "fight") and pool:
            other = pool[0] if len(pool) == 1 else None
        if other is None and pool and (kind in ("social", "date", "fight") or (not kind and rng.random() < 0.35)):
            weights = [abs(self.rel.get(x.pid, 0)) + 5 + (40 if x.pid == self.partner else 0) for x in pool]
            other = rng.choices(pool, weights)[0]
        if kind == "solo":
            other = None
        cands, ws = [], []
        for e in EVENTS.values():
            if e.followup or (twist and e.id not in TWIST_IDS):
                continue
            if kind == "date" and not (any(h in e.id for h in DATE_HINTS) or "love" in e.aff):
                continue
            if kind == "fight" and not (any(h in e.id for h in FIGHT_HINTS) or "toxic" in e.aff):
                continue
            if not self.eligible(e, other, fresh=False):
                continue
            w = e.w * (1 + sum(self.traits.get(t, 0) for t in e.aff) / 15) * REPEAT_DECAY ** self.seen.get(e.id, 0)
            # personality: situations where the pet can act in character come up more often
            w *= 1 + sum(self.traits.get(c.auto, 0) for c in e.choices if c.auto) / len(e.choices) / 40
            if "flag" in e.req:
                w *= 3.0    # storylines move forward
            elif any(k in e.req for k in ("job", "jail", "role", "season")):
                w *= 1.6    # situations the pet is in right now
            if e.id.startswith("_"):
                w *= 0.4 if not kind else 1
            cands.append(e)
            ws.append(w)
        fresh = [i for i, e in enumerate(cands) if e.id not in self.recent and not (other and e.id in other.recent)]
        if fresh:  # a recent event comes back only when nothing else fits
            cands, ws = [cands[i] for i in fresh], [ws[i] for i in fresh]
        if not cands:
            if kind == "date":
                e = EVENTS["_date"]
            elif kind == "fight":
                e = EVENTS["_fight"]
            elif twist:
                self.flags.pop("_twist", None)
                return self.pick_event(others, rng)
            elif other:
                return self.pick_event(others, rng, "solo")
            else:
                return None, None
            ok = other and self.meets(e.req, other) and self.options(e, other)
            return (e, other) if ok else (None, None)
        if twist:
            self.flags.pop("_twist", None)
        return rng.choices(cands, ws)[0], other

    def options(self, e: Event, other: "Pet | None" = None) -> list[tuple[int, Choice]]:
        out = [(i, c) for i, c in enumerate(e.choices) if self.meets(c.req, other) or (self.jailed and not c.req)]
        if not out and e.choices and self.jailed and e.req.get("jail"):
            out = [(i, c) for i, c in enumerate(e.choices) if self.meets(dict(c.req, jail=True), other)]
        return out

    def chance(self, c: Choice) -> float | None:
        if not c.check:
            return None
        skill, diff = c.check
        luck = self.skill("luck") if skill != "luck" else 0
        scale = {0: 0.6, 1: 0.6, 2: 0.8}.get(self.stage, 1.0)   # content difficulty is written for adults
        v = self.skill(skill) + luck * 0.15 + (self.level - 1) * 1.5 - diff * scale
        return max(0.2, min(0.95, 0.5 + v / 50))

    def start(self, e: Event, other: "Pet | None", mode: str = "auto") -> None:
        """mode: auto (scheduler post), manual (🎲 button), invite (date/fight)."""
        self.pending = dict(id=e.id, other=other.pid if other else "", oid=other.owner_id if other else 0,
                            ts=now(), msg=0, mode=mode, votes={}, bets={})

    def auto_choice(self, e: Event, other: "Pet | None", rng: random.Random,
                    votes: dict | None = None) -> tuple[int, str]:
        """Pick a choice like the pet would. Crowd advice wins 65% of the time. Returns (idx, 'crowd'|'self')."""
        opts = self.options(e, other)
        if not opts:
            return 0, "self"
        allowed = {i for i, _ in opts}
        if votes:
            tally: dict[int, int] = {}
            for v in votes.values():
                if int(v) in allowed:
                    tally[int(v)] = tally.get(int(v), 0) + 1
            if tally and rng.random() < 0.65:
                top = max(tally.values())
                return rng.choice([i for i, n in tally.items() if n == top]), "crowd"
        lean = self.persona.get("lean", "")
        best, best_s = opts[0][0], -1e9
        for i, c in opts:
            s = self.traits.get(c.auto, 0) + (12 if c.auto and c.auto == lean else 0) + rng.random() * 12
            ch_ = self.chance(c)
            if ch_ is not None:
                s += (ch_ - 0.5) * 10
            if s > best_s:
                best, best_s = i, s
        return best, "self"

    def resolve(self, e: Event, idx: int, other: "Pet | None", rng: random.Random) -> Result:
        """Apply a choice: skill check with natural 1/20, weighted outcomes, crits, twist tail, journal."""
        c = e.choices[idx]
        res = Result("", [], label=self.fmt(c.label, other))
        outs = c.outs
        if c.check:
            res.chance = self.chance(c)
            res.roll = rng.randint(1, 20)
            if res.roll == 20:
                res.ok, res.crit = True, "win"
            elif res.roll == 1:
                res.ok, res.crit = False, "fail"
            else:
                res.ok = rng.random() < res.chance
            if not res.ok:
                outs = c.fail or [o("Не вийшло. {name} лише змарнував час і нерви.", mood=-6)]
        weights = [max(0.0, x.w) for x in outs]
        out: Out = rng.choices(outs, weights)[0] if sum(weights) else outs[0]
        res.rare = len(outs) > 1 and out.w / sum(weights) < 0.2
        fx = dict(out.fx)
        if res.crit == "win":
            fx["xp"] = fx.get("xp", 0) + 15
            fx["mood"] = fx.get("mood", 0) + 10
            if fx.get("money", 0) > 0:
                fx["money"] = fx["money"] * 2
        elif res.crit == "fail":
            fx["health"] = fx.get("health", 0) - 10
            fx["mood"] = fx.get("mood", 0) - 10
        res.text = self.fmt(out.text, other)
        res.notes = self.apply(fx, other, rng)
        if self.alive:
            self._age_checks(rng)
        res.twist = bool(fx.get("twist")) or e.id.startswith("twist_")
        self.xp += 4
        self.events_done += 1
        self.lived(e.id)
        if e.once:
            self.flags[f"seen_{e.id}"] = 1
        self.pending = {}
        self.next_ev = now() + rng.uniform(*BUDGET.every) * hour()
        if self.alive and rng.random() < TWIST_TAIL:
            tt, tfx, _ = rng.choices(TAILS, [x[2] for x in TAILS])[0]
            res.tail = self.fmt(tt)
            res.tail_notes = self.apply(tfx, None, rng)
            res.twist = res.twist or bool(tfx.get("twist"))
        res.died = not self.alive
        c = self.counters
        for key, hit in (("ok", res.ok is True), ("fail", res.ok is False), ("twists", res.twist), ("rare", res.rare)):
            if hit:
                c[key] = c.get(key, 0) + 1
        c["money_max"] = max(c.get("money_max", 0), int(self.money))
        kind = "twist" if res.twist else "social" if other else "event"
        line = f"«{res.label}» → {res.text}"
        if other:
            line = f"з {other.name}: " + line
            other.note("social", f"{self.name} і {other.name}: {res.text}")
            other.lived(e.id)
        if res.tail:
            line += f" 🌀 {res.tail}"
        self.note(kind, line)
        return res

    def button(self, e: Event, idx: int, other: "Pet | None" = None) -> str:
        """Choice label for a button (placeholders filled)."""
        return self.fmt(e.choices[idx].label, other)

    def lived(self, eid: str) -> None:
        self.recent = (self.recent + [eid])[-RECENT:]
        self.seen[eid] = self.seen.get(eid, 0) + 1

    # --- care --------------------------------------------------------------------------------
    def cooldown_left(self, actor: int, action: str, hours: float) -> float:
        last = self.cool.get(f"{actor}:{action}", 0)
        return max(0.0, last + hours * hour() - now())

    def mark_cool(self, actor: int, action: str) -> None:
        t = now()
        self.cool = {k: v for k, v in self.cool.items() if t - v < 2 * DAY / SPEED}
        self.cool[f"{actor}:{action}"] = t


FIELDS = tuple(Pet.__dataclass_fields__)


# --- creation ----------------------------------------------------------------------------------

def time_label(y: float) -> str:
    """Short Ukrainian duration for buttons: 3 дн. / 2 тиж. / 6 міс. / 4 р."""
    d = y * 365
    if d < 6.5:
        return f"{max(1, round(d))} дн."
    if d < 28:
        return f"{round(d / 7)} тиж."
    if y < 0.96:
        return f"{max(1, round(y * 12))} міс."
    return f"{round(y)} р." if abs(y - round(y)) < 0.05 else f"{y:.1f} р."


_DAYS_YEARS = [(0, 0), (1.5, 12), (4, 18), (20, 60), (30, 82), (60, 120)]


def days_to_years(d: float) -> float:
    """≤ 0.2 pets aged in real days; map them onto the 0.3 year scale (teen 12, adult 18, elder 60)."""
    for (d0, y0), (d1, y1) in zip(_DAYS_YEARS, _DAYS_YEARS[1:]):
        if d <= d1:
            return y0 + (y1 - y0) * max(0.0, d - d0) / (d1 - d0)
    return 120.0


def seed_life(p: Pet) -> dict:
    """Life stats for a pet that lived before they existed, guessed from what it already is."""
    sk, tr, fl = p.skills, p.traits, p.flags
    c = lambda v: round(max(0.0, min(85.0, v)), 1)  # noqa: E731
    return dict(fame=c(sk.get("cha", 10) * 0.5 + tr.get("party", 0) * 0.3 + len(p.achievements) * 2
                       + (25 if p.job == "blogger" else 0)),
                auth=c(tr.get("toxic", 0) * 0.4 + fl.get("jailed_times", 0) * 12 + (20 if fl.get("crime") else 0)),
                blat=c(sk.get("cha", 10) * 0.3 + (30 if p.job == "deputy" else 10 if p.job else 0)),
                fin=c(sk.get("int", 10) * 0.4 + 8 * len(p.edu)),
                attr=c(15 + sk.get("cha", 10) * 0.3 + tr.get("love", 0) * 0.2 + len(p.equipped) * 2))


def make_name(species: str, taken: set[str], rng: random.Random) -> str:
    pool = NAMES.get(species) or FALLBACK_NAMES
    for _ in range(50):
        n = rng.choice(pool) + rng.choice(NAME_SUFFIX)
        if n not in taken:
            return n
    return rng.choice(pool) + f" №{rng.randint(2, 999)}"


def new_pet(chat_id: int, owner_id: int, owner_name: str, species: str, others: list[Pet],
            rng: random.Random, predecessor: Pet | None = None, partner_genes: dict | None = None) -> Pet:
    """Fresh egg. With a predecessor: heir genes (hybrid if there was a partner), inheritance, dynasty."""
    others_g = [x.genome for x in others if x.genes and x.state != "dead"]
    g = None
    if predecessor:
        a = sprites.Genome.from_dict(predecessor.heir) if predecessor.heir else predecessor.genome
        b = sprites.Genome.from_dict(partner_genes) if partner_genes else a
        try:
            g = sprites.unique_genome(a.species, others_g, rng, min_dist=3.0, parents=(a, b))
        except TypeError:
            g = sprites.breed(a, b, rng, 0.15)
    if g is None:
        if species not in sprites.SPECIES:
            species = rng.choice(sprites.SPECIES)
        g = sprites.unique_genome(species, others_g, rng)
    temper, lean = rng.choice(TEMPERAMENTS)
    p = Pet(chat_id=chat_id, owner_id=owner_id, owner_name=owner_name, genes=g.to_dict(),
            name=make_name(g.species, {x.name for x in others}, rng),
            skills={s: rng.randint(3, 20) for s in SKILLS},
            lifespan=rng.uniform(*LIFESPAN_YEARS),
            life=dict(fame=rng.randint(0, 5), auth=0, blat=rng.randint(0, 5), fin=rng.randint(3, 15),
                      attr=rng.randint(8, 22)),
            persona=dict(temper=temper, lean=lean, dream=rng.choice(DREAMS), fear=rng.choice(FEARS),
                         quirk=rng.choice(QUIRKS), food=rng.choice(FOODS)))
    p.traits = {lean: 3} if lean else {}
    p.born = p.last_tick = now()
    if predecessor:
        p.gen = predecessor.gen + 1
        p.dynasty = predecessor.dynasty or f"Рід {predecessor.name}"
        p.ancestors = (predecessor.ancestors + [f"{predecessor.name} ({predecessor.cause or 'зник'})"])[-12:]
        p.money = 100 + max(0, predecessor.money) * 0.3
        relic = [i for i in predecessor.items if i != "cane"]
        if relic:
            p.items.append(rng.choice(relic))
        for t, v in predecessor.traits.items():
            p.traits[t] = p.traits.get(t, 0) + v * 0.15
        p.homes = list(dict.fromkeys(predecessor.homes + p.homes))
        p.home = predecessor.home
        if p.gen >= 3:
            p.achievements.append("Династія")
    for k in ("money", *LIFE):
        p.counters[f"tier_{k}"] = p.tier(k)
    p.note("born", f"🥚 Знесено яйце: {p.name}" + (f", покоління {p.gen} ({p.dynasty})" if p.gen > 1 else ""))
    return p


def fix_partners(pets: list[Pet]) -> None:
    """Partnership must be mutual. If X still thinks it's with Y but Y moved on, X learns the truth (💔 + drama)."""
    by_pid = {p.pid: p for p in pets}
    for p in pets:
        if not p.alive or not p.partner:
            continue
        q = by_pid.get(p.partner)
        if q is None:  # partner's owner left / used /forget / the pet was replaced by an heir
            p.status[p.partner] = "ex"
            p.partner = ""
            p.note("love", f"💔 {p.name} лишився без пари: друга половинка зникла без сліду.")
            continue
        if q.state == "dead" or q.partner == p.pid:
            continue  # dead partners are handled by mourn()
        p.partner = ""
        p.status[q.pid] = "ex"
        p.rel[q.pid] = min(p.rel.get(q.pid, 0.0), -50.0)
        p.mood = max(0.0, p.mood - 30)
        p.traits["dark"] = p.traits.get("dark", 0) + 2
        rival = by_pid.get(q.partner)
        p.note("love", f"💔 {p.name} дізнався, що {q.name} пішов до {rival.name if rival else 'когось іншого'}. "
                       f"Б'є посуд і слухає Скрябіна.")
        if rival and rival.alive:
            p.rel[rival.pid] = min(p.rel.get(rival.pid, 0.0), -60.0)
            p.status[rival.pid] = "enemy"


def mourn(pets: list[Pet]) -> None:
    """Partners of freshly dead pets become widows; call once per scheduler pass with all chat pets."""
    fix_partners(pets)
    for d in pets:
        if d.state != "dead" or d.flags.get("_mourned"):
            continue
        d.flags["_mourned"] = 1
        for p in pets:
            if not p.alive or p is d:
                continue
            if p.partner == d.pid:
                p.partner = ""
                p.status[d.pid] = "ex"
                p.mood = max(0.0, p.mood - 35)
                p.note("love", f"🖤 {p.name} овдовів: {d.name} пішов на веселку")
            elif p.status.get(d.pid) in ("friend", "bestie"):
                p.mood = max(0.0, p.mood - 10)
                p.note("social", f"😢 {p.name} сумує за другом {d.name}")
            elif p.status.get(d.pid) == "enemy":
                p.mood = min(100.0, p.mood + 10)
                p.note("social", f"😈 {p.name} станцював на могилі ворога {d.name}")


def chat_daily(pets: list[Pet], rng: random.Random) -> list[str]:
    """Once per game day per chat: angels heal friends, vampires bite, zombies infect. Returns notable lines."""
    alive = [p for p in pets if p.alive and p.stage >= 1]
    by_pid = {p.pid: p for p in alive}
    out = []
    for p in alive:
        if p.role == "angel":
            healed = [by_pid[k] for k, s in p.status.items() if s in ("friend", "bestie", "partner") and k in by_pid]
            for f in healed[:5]:
                f._add("health", 15)
                f._add("mood", 5)
                f.note("social", f"😇 Ангел {p.name} підлікував {f.name}")
            if healed:
                p.counters["healed"] = p.counters.get("healed", 0) + len(healed)
                if p.counters["healed"] >= 5:
                    p.ach("Ангел-охоронець")
        elif p.role in ("vampire", "zombie") and len(alive) > 1 and rng.random() < 0.15:
            victims = [x for x in alive if x is not p and x.role not in UNDEAD and x.role != "angel"]
            if not victims:
                continue
            v = min(victims, key=lambda x: p.rel.get(x.pid, 0) + rng.random() * 40)
            v._add("health", -12)
            p.set_rel(v, -8)
            if p.role == "vampire":
                p._add("hunger", 40)
            what = "вкусив" if p.role == "vampire" else "погриз"
            v.note("social", f"🩸 {p.name} вночі {what} {v.name}")
            if rng.random() < 0.15:
                v.set_role(p.role)
                line = f"🌀 {p.name} {what} {v.name}, і тепер {v.name} теж {ROLES[p.role]['name']}!"
                v.note("twist", line)
                out.append(line)
    return out


# --- care actions ------------------------------------------------------------------------------

CARE = {
    "play": ("🎾 Пограти", dict(mood=20, hunger=-5, clean=-8, energy=-10, love=0.5), 1.0),
    "wash": ("🧼 Помити", dict(clean=100, mood=-5), 2.0),
    "pat": ("🤗 Погладити", dict(mood=12, love=1), 0.5),
    "heal": ("💊 Лікувати", dict(health=25, mood=-8), 3.0),
    "kick": ("🦶 Копнути", dict(mood=-20, health=-5, toxic=1, dark=0.5), 1.0),
}
CARE_TEXT = {
    "play": ["{name} ганяв м'ячик і розбив вазу. Щасливий.", "{name} грав у хованки й заснув у шафі.",
             "{name} вивчив новий трюк: вдавати мертвого на команду «податкова».",
             "{name} носився по хаті, як після трьох енергетиків."],
    "wash": ["{name} пережив купання і тепер ображений на весь світ.", "Блискучий {name}! Пахне шампунем «Ромашка».",
             "{name} вилив половину ванни на підлогу. Сусіди знизу вже йдуть."],
    "pat": ["{name} розтанув від щастя.", "{name} підставив пузо. Довіра 100%.", "{name} заплющив очі й муркотів (як умів)."],
    "heal": ["{name} отримав укол і подивився з ненавистю.", "Вітамінки з'їдено. {name} відчуває себе безсмертним.",
             "{name} випив сироп від кашлю і повеселішав підозріло сильно."],
    "kick": ["{name} полетів у кут. Запам'ятав. Назавжди.", "{name} тепер боїться ще й тебе, а не лише {fear}.",
             "{name} мовчки дивиться. Він усе запише в щоденник ненависті."],
}


def care(p: Pet, action: str, rng: random.Random, actor: Pet | None = None, by_owner: bool = True,
         actor_name: str = "") -> tuple[str, list[str]]:
    """Owner or anyone else interacts with the pet. Non-owners change the relationship between the two pets."""
    _, fx, _ = CARE[action]
    fx = dict(fx)
    if action == "wash" and p.species == "cat":
        fx["mood"] = -15
    if action == "wash" and p.species == "axolotl":
        fx["mood"] = 10
    text = p.fmt(rng.choice(CARE_TEXT[action]))
    extra: list[str] = []
    if action == "kick" and p.role == "werewolf" and is_night() and actor:
        actor._add("health", -20)
        text += f" …і перевертень вкусив {actor.name} у відповідь! 🐺"
    if action == "kick" and p.role == "angel" and actor:
        actor._add("luck", -2)
        text += " Небеса це бачили. 🍀−2 кривдникові."
    if action == "heal" and p.role == "zombie":
        fx["health"] = 35
    notes = p.apply(fx, None, rng)
    p.xp += 1
    if not by_owner:
        who = actor_name or "хтось"
        if actor:
            p.set_rel(actor, -10 if action == "kick" else 3)
            if action == "kick":
                actor._add("toxic", 1)
            extra.append(f"{'💢' if action == 'kick' else '💞'} {p.name} ↔ {actor.name}")
        p.note("care", f"{CARE[action][0]} від {who}: {text}")
        if action == "kick":
            p.counters["kicked"] = p.counters.get("kicked", 0) + 1
            if p.counters["kicked"] >= 10:
                p.ach("Груша для биття")
    return text, notes + extra


def feed(p: Pet, food: str, rng: random.Random, payer: Pet | None = None) -> tuple[str, list[str]] | str:
    """payer pays (owner's own pet by default). Returns (text, notes) or an error string."""
    name, price, fx = FOOD[food]
    payer = payer or p
    if price and payer.money < price:
        return f"Не вистачає грошей: {name} коштує {price} ₴, а є {int(payer.money)} ₴."
    payer.money -= price
    fx = dict(fx)
    need = ROLE_FOOD.get(food)
    text = f"{p.name} з'їв: {name}."
    if need and p.role != need:
        fx = dict(mood=-15, health=-5, hunger=5)
        text = f"{p.name} понюхав {name} і знепритомнів від огиди. Це не для нього."
    elif not need and p.role in ("vampire", "zombie"):
        fx["hunger"] = fx.get("hunger", 0) * 0.5
        text += " Без особливого апетиту — йому б чогось… іншого."
    overeat = p.hunger > 90
    notes = p.apply(fx, None, rng)
    if overeat:
        notes += p.apply(dict(health=-5, glutton=1), None, rng)
        text += " Переїв і лежить як тюлень."
    fav = p.persona.get("food", "")
    if fav and fav.split()[0][:4].lower() in name.lower():
        notes += p.apply(dict(mood=10), None, rng)
        text += " Улюблена їжа! 😍"
    if payer is not p:
        p.set_rel(payer, 4)
        notes.append(f"💞 {p.name} ↔ {payer.name}")
        p.note("care", f"🍖 {payer.name} пригостив {p.name}: {name}")
    p.xp += 1
    return text, notes


# --- job centre --------------------------------------------------------------------------------

def job_offers(p: Pet) -> list[str]:
    if p.stage < 2 or p.jailed:
        return []
    out = []
    for jid, j in JOBS.items():
        if not j.get("open") or jid == p.job:
            continue
        if p.stage == 2 and j["pay"] > 160:
            continue
        if p.meets(j["req"]):
            out.append(jid)
    return out


def apply_job(p: Pet, jid: str, rng: random.Random) -> tuple[bool, str, list[str]]:
    j = JOBS[jid]
    diff = 15 + max(j["pay"], sum(j.get("pay_range", (0, 0))) // 2) / 20
    c = max(0.1, min(0.95, 0.5 + (p.skill("cha") * 0.6 + p.skill("int") * 0.4 + p.skill("luck") * 0.2 - diff) / 40))
    roll = rng.random()
    if roll < c:
        notes = p.apply({"job": jid}, None, rng)
        return True, rng.choice([f"Співбесіду пройдено! {p.name} тепер {j['name']}.",
                                 f"HR сказала «ви нам підходите». {p.name} — {j['name']}!"]), notes
    p.mood = max(0.0, p.mood - 8)
    return False, rng.choice([f"«Ми вам передзвонимо». Не передзвонять. (шанс був {c:.0%})",
                              f"Відмовили: «у вас замало досвіду в 3 роки». (шанс був {c:.0%})",
                              f"{p.name} запізнився на співбесіду на годину. (шанс був {c:.0%})"]), ["😊−8"]


# --- shop --------------------------------------------------------------------------------------

def shop_stock(chat_id: int, day: str) -> list[dict]:
    """Daily «Базар»: same stock for the whole chat all day."""
    rng = random.Random(f"bazar:{chat_id}:{day}")
    out = []
    pool = sorted(i for i in PRICES if i in sprites.ITEMS)
    for it in rng.sample(pool, min(8, len(pool))):
        v = rng.randrange(len(sprites.TINTS)) if rng.random() < 0.5 else 0
        mult = 3 if sprites.TINTS[v][1] == "gold" else 1.2 if v else 1
        iid = f"{it}@{v}" if v else it
        out.append(dict(kind="item", id=iid, price=int(PRICES[it] * mult), name=item_name(iid)))
    gen = getattr(sprites, "random_item", None)
    if gen:
        try:
            iid = gen(rng.choice(["head", "face", "neck", "outfit", "held", "aura", "back"]), rng)
            out.append(dict(kind="item", id=iid, price=rng.randint(400, 3000), name="✨ " + item_name(iid)))
        except Exception:
            pass
    homes = sorted(b for b in BACKGROUND_PRICES if BACKGROUND_PRICES[b] > 0 and b in sprites.BACKGROUNDS)
    for bg in rng.sample(homes, min(2, len(homes))):
        out.append(dict(kind="home", id=bg, price=BACKGROUND_PRICES[bg], name=bg_name(bg)))
    out.append(dict(kind="box", id="box", price=MYSTERY_BOX, name="🎁 Кіт у мішку"))
    if rng.random() < 0.35:
        out.append(dict(kind="potion", id="potion", price=POTION, name="🧪 Підозріле зілля"))
    return out


def buy(p: Pet, entry: dict, rng: random.Random) -> tuple[bool, str]:
    price = entry["price"]
    kind = entry["kind"]
    if kind == "home" and entry["id"] in p.homes:
        p.home = entry["id"]
        return True, f"🏠 {p.name} вже має цей дім — переїхали назад."
    if kind == "item" and entry["id"] in p.items:
        return False, "Це вже є в гардеробі."
    if p.money < price:
        return False, f"Не вистачає {int(price - p.money)} ₴. Йди працюй."
    p.money -= price
    if kind == "item":
        n = p.give(entry["id"])
        p.note("life", f"🛒 {p.name} купив {n}")
        return True, f"🛍 Куплено й одягнено: {n}"
    if kind == "home":
        p.apply({"home": entry["id"]}, None, rng)
        p.note("life", f"🏠 {p.name} переїхав: {bg_name(entry['id'])}")
        if entry["id"] == "palace":
            p.ach("Межигір'я — моє")
        return True, f"🔑 Новосілля! {p.name} тепер живе тут: {bg_name(entry['id'])}"
    if kind == "box":
        r = rng.random()
        if r < 0.15:
            p.apply({"mood": -10, "clean": -30}, None, rng)
            return True, "🐈 У мішку був справжній кіт. Він подряпав усіх і втік."
        if r < 0.25:
            p.money += 900
            return True, "💰 У мішку — 900 ₴ і записка «вибач». Хто це був?"
        it = p.random_item(rng.choice(["head", "face", "neck", "outfit", "held", "back", "aura"]), rng)
        return True, f"🎁 У мішку: {p.give(it)}!"
    if kind == "potion":
        r = rng.random()
        if r < 0.55:
            role = rng.choice(sorted(ROLES))
            n = p.set_role(role) or ""
            return True, f"🧪 Буль-буль… {p.name} випив зілля. {n or 'Нічого не змінилось'}!"
        if r < 0.85:
            got = p.mutate(2, rng)
            return True, "🧪 Зілля подіяло дивно. Мутація: " + ", ".join(got)
        p.apply({"health": -40, "mood": -20}, None, rng)
        return True, "🧪 Це був просто денатурат. 🏥"
    return False, "?"


# --- world events ------------------------------------------------------------------------------
# global: effects on every alive pet the moment it happens (role-specific extras), claim: first N clickers.
# 🎰 one venue per wealth tier: (name, money tier, min stake, max stake, background, jackpot ×)
CASINO = {
    "underpass": ("🎰 Автомати в переході", 1, 20, 300, "metro", 10),
    "bukovel": ("🎲 Казино в Буковелі", 2, 300, 5000, "bukovel", 20),
    "private": ("🃏 Закритий покер олігархів", 4, 5000, 50000, "casino", 8),
}


def casino_venues(p: Pet) -> list[str]:
    """Venues open to this pet: adults with money of the venue's tier (or the right «кум» for the private room)."""
    if not p.alive or p.stage < 3 or p.jailed or p.in_hospital:
        return []
    return [k for k, v in CASINO.items() if p.tier("money") >= v[1] or (k == "private" and p.tier("blat") >= 3
                                                                          and p.money >= v[2])]


def casino(p: Pet, venue: str, stake: int, rng: random.Random) -> tuple[str, list[str]] | str:
    """Bet `stake` ₴ at a venue. The house edge is real; luck and fin literacy soften it.
    Returns (text, notes) or an error string."""
    if venue not in casino_venues(p):
        return "Сюди тебе не пустять" if p.alive and p.stage >= 3 else "Казино — тільки для дорослих"
    name, _, lo, hi, _, jackpot = CASINO[venue]
    if not isinstance(stake, int) or isinstance(stake, bool) or not lo <= stake <= min(hi, int(p.money)):
        return f"Ставка від {lo} до {min(hi, max(lo, int(p.money)))} ₴"
    p.counters["casino"] = p.counters.get("casino", 0) + 1
    p._add("gambler", 1)
    fin = p.life.get("fin", 0)
    roll = rng.random()
    win = 0.40 + p.skill("luck") / 500 + (0.05 if p.role == "demon" else 0)
    fx: dict = {}
    if roll < 0.015:
        fx, text = dict(money=stake * jackpot, mood=30), f"ДЖЕКПОТ! Автомат заспівав, люди аплодують — ×{jackpot}!"
        p.ach("Зірвав джекпот")
    elif roll < 0.015 + win:
        fx, text = dict(money=stake, mood=10), rng.choice([
            "{name} поставив на червоне — і червоне не підвело.", "Карта прийшла як по замовленню. Подвоїв ставку.",
            "{name} вийшов у плюс і (неймовірно) вчасно зупинився."])
    else:
        lost = int(stake * (1 - fin / 250))  # financially literate pets stop in time
        fx, text = dict(money=-lost, mood=-10), rng.choice([
            "Казино завжди виграє. Сьогодні — теж.", "{name} «майже відігрався». Тричі.",
            "Дилер співчутливо кивнув і забрав фішки."]) + (" Фінграмотність підказала вчасно встати з-за столу."
                                                          if lost < stake else "")
    special = rng.random()
    if venue == "underpass" and special < 0.06:
        fx.update(jail=12, auth=3)
        text += " А тоді приїхала поліція: автомати виявились нелегальними."
    elif venue == "bukovel" and special < 0.07:
        fx["fame"] = 8
        text += " Хтось зняв це на відео — тепер {name} у трендах."
    elif venue == "private" and special < 0.12:
        fx["blat"] = 10
        text += " За столом сидів заступник міністра. Тепер він «знайомий»."
    raw_money = fx.pop("money")
    p.money += raw_money  # stake rules above already include fin literacy
    notes = [f"{'+' if raw_money > 0 else ''}{raw_money} ₴"]
    notes += p.apply(fx, None, rng)
    p._tiers()
    text = p.fmt(text)
    p.note("casino", f"{name}: {text} ({raw_money:+d} ₴)")
    return text, notes


WORLD = {
    "meteor": dict(title="☄️ Метеорит над чатом!", text="Над районом пролетів метеорит і впав десь за гаражами.",
                   button="🏃 Бігти шукати уламок", n=4, global_fx={},
                   claim=[("знайшов уламок і продав на OLX", dict(money=600), 3),
                          ("надихався космічного пилу", dict(mutate=1, health=-10), 2),
                          ("отримав уламком по голові", dict(health=-30, int=-2), 1),
                          ("торкнувся уламка і почув голоси з космосу", dict(role="alien", twist=True), 0.25)]),
    "blackout": dict(title="🔌 Відключення світла в усьому районі!", text="Укренерго каже: «ненадовго». Усі пети в темряві.",
                     button="🕯 Запалити свічку", n=5, global_fx=dict(mood=-10), role_fx={"cyborg": dict(health=-15)},
                     mod="blackout",
                     claim=[("запалив свічку і розповідав страшилки", dict(mood=15, mystic=2), 3),
                            ("підпалив штори", dict(clean=-30, health=-10), 1),
                            ("знайшов павербанк і став королем під'їзду", dict(cha=3, money=150), 2)]),
    "fair": dict(title="🎪 Ярмарок на площі!", text="Сорочинський ярмарок приїхав у наш чат: каруселі, мед, цигани з картами.",
                 button="🎡 Бігти на ярмарок", n=6, global_fx={},
                 claim=[("виграв у тирі", dict(item_slot="held", mood=10), 3), ("об'ївся медом", dict(hunger=50, glutton=2), 3),
                        ("ворожка обдурила на 200 ₴", dict(money=-200, mystic=1), 2),
                        ("купив кота в мішку — а там гроші", dict(money=500), 1)]),
    "flood": dict(title="🌊 Сусіди зверху затопили весь під'їзд!", text="Вода тече зі стелі. Килим уже не врятувати.",
                  button="🪣 Рятувати майно", n=5, global_fx=dict(clean=-20), mod="rain",
                  claim=[("врятував телевізор і гідність", dict(str=2, mood=10), 3),
                         ("стрибнув у воду і застудився", dict(health=-15), 2),
                         ("виставив сусідам рахунок", dict(money=400, toxic=1), 2)]),
    "eclipse": dict(title="🌑 Сонячне затемнення!", text="Вдень стало темно. Вампіри вийшли на прогулянку.",
                    button="👀 Подивитися без окулярів", n=5, global_fx={}, role_fx={"vampire": dict(mood=30)}, mod="night",
                    claim=[("побачив щось у темряві", dict(mystic=3, luck=-2), 3),
                           ("тимчасово осліп, але подорослішав духовно", dict(int=2, health=-10), 2),
                           ("зустрів у тіні дуже блідого незнайомця…", dict(role="vampire", twist=True), 0.3)]),
    "tax": dict(title="🧾 Податкова перевірка всього району!", text="Кожен, хто має понад 2000 ₴, мусить пояснити звідки.",
                button="🙈 Сховати гроші під матрац", n=6, global_fx={}, rich_fx=dict(money_mult=0.9),
                claim=[("сховав так, що сам не знайшов", dict(money=-200), 2), ("сховав ідеально", dict(gambler=1, money=150), 3),
                       ("спалився і заплатив штраф", dict(money=-500), 1)]),
    "vaccine": dict(title="🩺 Безкоштовна вакцинація у ветклініці!", text="Перші в черзі отримують щеплення і цукерку.",
                    button="💉 Стати в чергу", n=6, global_fx={},
                    claim=[("щеплений і щасливий", dict(health=30), 4), ("вкусив ветеринара", dict(toxic=2, mood=5), 1),
                           ("отримав побічку: третє око", dict(gene={"eyes": "three"}, mystic=2), 0.3)]),
    "drop": dict(title="🪂 Гуманітарка з неба!", text="Над районом розкрився парашут з ящиком. Хто перший — того й тапки.",
                 button="📦 Хапати ящик", n=4, global_fx={},
                 claim=[("схопив консерви", dict(hunger=60), 3), ("схопив щось корисне", dict(item_slot="neck"), 2),
                        ("схопив 300 ₴ у конверті", dict(money=300), 2), ("отримав ящиком по лобі", dict(health=-20), 1)]),
    "moon": dict(title="🌕 Повня над чатом!", text="Собаки виють, перевертні нервують, а всі решта не можуть заснути.",
                 button="🐺 Вити на місяць", n=5, global_fx=dict(energy=-15), role_fx={"werewolf": dict(str=2, toxic=2)},
                 claim=[("вив так гарно, що сусіди заплакали", dict(cha=2, dark=2), 3),
                        ("в кущах щось клацнуло зубами…", dict(role="werewolf", twist=True), 0.3),
                        ("вив до хрипоти", dict(mood=-5, party=1), 2)]),
    "ufo": dict(title="🛸 НЛО зависло над районом!", text="Над хрущовками світиться тарілка. Поліція каже, що це дрон.",
                button="👋 Помахати прибульцям", n=4, global_fx={}, role_fx={"alien": dict(mood=40)},
                claim=[("прибульці помахали у відповідь", dict(mood=20, mystic=2), 3),
                       ("викрадений на 6 годин", dict(hospital=6, int=3), 1),
                       ("повернувся з тарілки зовсім іншим", dict(role="alien", twist=True), 0.35),
                       ("отримав в обмін на борщ технологію", dict(item="vr", int=2), 1)]),
    "atm": dict(title="💸 Банкомат на розі глючить і видає гроші!", text="Банк обіцяє все повернути «найближчим часом».",
                button="🏧 Бігом до банкомата", n=3, global_fx={},
                claim=[("забрав 500 ₴", dict(money=500, gambler=1), 4),
                       ("потрапив на камеру, тепер у розшуку", dict(jail=6, money=300), 1)]),
    "concert": dict(title="🎤 Безкоштовний концерт на площі!", text="Грає гурт, назву якого ніхто не запам'ятав, але всі підспівують.",
                    button="🤘 Під сцену!", n=8, global_fx=dict(mood=5),
                    claim=[("стрибав під сценою до ранку", dict(party=3, mood=20, energy=-20), 4),
                           ("зловив медіатор гітариста", dict(item="guitar", cha=1), 0.5),
                           ("загубився в натовпі", dict(mood=-10), 1)]),
    "bees": dict(title="🐝 Рій бджіл атакує двір!", text="Пасічник з п'ятого поверху «трохи не встежив».",
                 button="🍯 Відібрати мед", n=4, global_fx=dict(mood=-5),
                 claim=[("виніс цілу банку меду", dict(hunger=40, mood=15, str=1), 2),
                        ("покусаний, але гордий", dict(health=-20, str=2), 2),
                        ("став другом бджіл", dict(love=2, mystic=1), 1)]),
}


def world_start(key: str, pets: list[Pet], rng: random.Random) -> list[str]:
    """Apply global effects of a world event to all pets. Returns short summary lines."""
    w = WORLD[key]
    lines = []
    for p in pets:
        if not p.alive or p.stage < 1:
            continue
        fx = dict(w.get("global_fx", {}))
        rfx = w.get("role_fx", {}).get(p.role)
        if rfx:
            fx.update(rfx)
            lines.append(f"{p.name} ({ROLES[p.role]['name']})")
        if w.get("rich_fx") and p.money > 2000:
            fx.update(w["rich_fx"])
        if fx:
            p.apply(fx, None, rng)
        if w.get("mod"):
            p.flags["_mod"] = [w["mod"], now() + 4 * hour()]
        p.note("world", f"{w['title']} {w['text']}")
    return lines


def world_claim(p: Pet, key: str, rng: random.Random) -> tuple[str, list[str], bool]:
    w = WORLD[key]
    text, fx, _ = rng.choices(w["claim"], [c[2] for c in w["claim"]])[0]
    notes = p.apply(fx, None, rng)
    p.note("twist" if fx.get("twist") else "world", f"{w['title']} {p.name} {text}")
    return f"{p.name} {text}", notes, bool(fx.get("twist"))


# --- auto-posting budget / planner -------------------------------------------------------------

@dataclass
class Budget:
    daily: int = 16              # auto posts per chat per day (events + notices + world events)
    gap_min: float = 20          # minutes between auto posts
    decide_hours: float = 3      # owner has this long to answer before the pet decides
    inactive_hours: float = 24   # owner silent this long → "silent life"
    world_per_day: float = 1.0   # expected world events per chat per day
    digest_hour: int = 21        # 📰 Пет-хроніка (Kyiv time)
    quiet: tuple = (0, 8)        # no auto posts during these Kyiv hours
    every: tuple = (5.0, 10.0)   # game hours between life events of one pet
    max_wait: float = 8          # real hours a due pet waits for a post slot before living it silently
    tick_seconds: int = 300


BUDGET = Budget()


def chat_state(d: dict | None) -> dict:
    s = dict(day="", posts=0, last_post=0.0, digest_day="", world=None, last_world=0.0, gday=0)
    s.update(d or {})
    return s


def plan(state: dict, pets: list[Pet], seen: dict[int, float], rng: random.Random, notice_weight: int = 0) -> dict:
    """Decide what this scheduler pass does for one chat. At most ONE auto post per pass.

    Returns dict(action=None|"event"|"notices"|"world", target=Pet|None, expired=[pets], silent=[pets], digest=bool,
    dm=[pets]). `dm` pets get their solo adventure in the owner's DM: outside the group budget and gap, but still
    paced by next_ev and quiet hours.
    """
    t = now()
    k = kyiv(t)
    day = k.strftime("%Y-%m-%d")
    if state["day"] != day:
        state["day"], state["posts"] = day, 0
    b = BUDGET
    quiet = b.quiet[0] <= k.hour < b.quiet[1]
    out = dict(action=None, target=None, expired=[], silent=[], digest=False, dm=[])
    cands = []
    for p in pets:
        if not p.alive or p.stage < 1:
            continue
        if p.pending:
            if t - p.pending.get("ts", t) > b.decide_hours * 3600:
                out["expired"].append(p)
            continue
        if not p.next_ev:
            p.next_ev = t + rng.uniform(*b.every) * hour()
        if p.next_ev > t:
            continue
        inactive = t - seen.get(p.owner_id, 0) > b.inactive_hours * 3600
        if not inactive and p.flags.get("dm") and p.chat_id != p.owner_id:
            if not quiet:
                out["dm"].append(p)  # delivered privately: doesn't use the group's posts/gap
            continue
        (out["silent"] if inactive else cands).append(p)
    can_post = not quiet and state["posts"] < b.daily and t - state["last_post"] >= b.gap_min * 60
    active_ticks = max(1.0, (24 - (b.quiet[1] - b.quiet[0])) * 3600 / b.tick_seconds)
    world = (can_post and not state.get("world") and sum(p.alive for p in pets) >= 3
             and t - state.get("last_world", 0) > 4 * 3600 and rng.random() < b.world_per_day / active_ticks * 3.5)
    if world:
        out["action"] = "world"
    elif can_post and notice_weight >= 3:
        out["action"] = "notices"
    elif can_post and cands:
        def score(p: Pet) -> float:
            waited = (t - p.next_ev) / 3600 + 1
            idle = t - seen.get(p.owner_id, 0)
            act = 2.0 if idle < 3600 else 1.5 if idle < 6 * 3600 else 1.0
            spread = 0.3 ** (p.posted[1] if p.posted[0] == day else 0)
            return waited * act * spread * rng.uniform(0.8, 1.2)
        out["action"], out["target"] = "event", max(cands, key=score)
    for p in cands:
        if p is not out["target"] and (t - p.next_ev) / 3600 > b.max_wait:
            out["silent"].append(p)
    if k.hour >= b.digest_hour and state["digest_day"] != day:
        out["digest"] = True
    if out["action"]:
        state["posts"] += 1
        state["last_post"] = t
        if out["action"] == "world":
            state["last_world"] = t
        if out["target"]:
            tp = out["target"]
            tp.posted = [day, (tp.posted[1] if tp.posted[0] == day else 0) + 1]
    return out


def live_silently(p: Pet, others: list[Pet], rng: random.Random) -> Result | None:
    """An event happens and the pet decides by itself (owner away / no post slot). Journal only."""
    e, other = p.pick_event(others, rng)
    if not e:
        p.next_ev = now() + rng.uniform(*BUDGET.every) * hour()
        return None
    idx, _ = p.auto_choice(e, other, rng)
    return p.resolve(e, idx, other, rng)


# --- presentation (HTML) -----------------------------------------------------------------------

def _esc(s) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def bar(v: float) -> str:
    n = int(round(v / 20))
    return "▰" * n + "▱" * (5 - n)


# life summary titles: (test, title) — first match wins; trait titles are the fallback
LIFE_TITLES = [
    (lambda p, c: p.role in ("vampire", "demon") and c.get("natural"), "Безсмертне зло, яке таки здолала старість"),
    (lambda p, c: c.get("dodged", 0) >= 2, "Кіт Шредінгера: помирав частіше, ніж обідав"),
    (lambda p, c: p.flags.get("jailed_times", 0) >= 2, "Кримінальний авторитет району"),
    (lambda p, c: c.get("money_max", 0) >= 10000, "Місцевий олігарх"),
    (lambda p, c: p.children >= 2, "Засновник династії"),
    (lambda p, c: len(p.achievements) >= 7, "Легенда чату"),
    (lambda p, c: sum(s == "ex" for s in p.status.values()) >= 2, "Серцеїд з розбитим серцем"),
    (lambda p, c: c.get("twists", 0) >= 3, "Магніт для сюжетних поворотів"),
    (lambda p, c: sum(k.startswith("role_") for k in c) >= 2, "Перепробував усі надприродні професії"),
    (lambda p, c: c.get("tier_fame", 0) >= 4, "Зірка Євробачення — і назавжди в серцях фанатів"),
    (lambda p, c: c.get("tier_auth", 0) >= 4, "Хрещений батько району"),
    (lambda p, c: c.get("tier_blat", 0) >= 4, "Людина, якій усі були винні"),
    (lambda p, c: p.years < 30, "Яскраве, але дуже коротке життя"),
    (lambda p, c: c.get("fail", 0) > c.get("ok", 0) + 3, "Невдаха з великим серцем"),
    (lambda p, c: c.get("natural") and p.partner, "Прожив довге життя поруч із коханими"),
]
TRAIT_TITLES = {
    "toxic": "Токсик із принципами", "gambler": "Вічний гравець: ще одна ставка — і точно пощастить",
    "dark": "Темна конячка під'їзду", "party": "Душа кожної вечірки", "patriot": "Патріот свого району",
    "glutton": "Гурман від Бога", "love": "Добра душа, яку любили всі", "mystic": "Містик, що бачив більше за нас",
}


def plural(n: int, one: str, few: str, many: str) -> str:
    """Ukrainian noun form for a count: 1 пригода, 3 пригоди, 5 пригод, 21 пригода, 12 пригод."""
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return one
    return few if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else many


def life_summary(p: Pet, names: dict[str, str] | None = None) -> dict:
    """What a life added up to, for the screen after death (also works for living pets).

    Plain text (hosts escape it): title, facts (short lines), story (highlights in order), family, epitaph.
    names: pid -> pet name for the partner.
    """
    names = names or {}
    c = p.counters
    title = next((t for test, t in LIFE_TITLES if test(p, c)), None)
    if not title:
        top = p.top_traits(1)
        title = TRAIT_TITLES[top[0]] if top else "Тихе звичайне життя — і це теж перемога"
    ok, fail = c.get("ok", 0), c.get("fail", 0)
    yrs = int(p.years)
    facts = [f"📅 {yrs} {plural(yrs, 'рік', 'роки', 'років')} · {STAGES[p.stage]} · рівень {p.level}"
             + (f" · 👑 {p.dynasty}, покоління {p.gen}" if p.gen > 1 and p.dynasty else ""),
             f"🎲 {p.events_done} {plural(p.events_done, 'пригода', 'пригоди', 'пригод')}" + (f" · 🎯 кубик: {ok}✅ {fail}❌" if ok + fail else "")
             + (f" · 🌀 поворотів: {c['twists']}" if c.get("twists") else "")]
    career = [JOBS[p.job]["name"] if p.job in JOBS else "", EDUCATION.get(p.edu[-1], "") if p.edu else ""]
    money = f"💰 найбільше мав {c.get('money_max', int(p.money)):,} ₴".replace(",", " ")
    facts.append(" · ".join(x for x in career + [money] if x))
    roles = [ROLES[k[5:]]["name"] for k in c if k.startswith("role_") and k[5:] in ROLES]
    if roles or p.flags.get("jailed_times"):
        facts.append(" · ".join(roles + ([f"⛓ відсидок: {p.flags['jailed_times']}"] if p.flags.get("jailed_times") else [])))
    peaks = [p.tier_name(k, c[f"tier_{k}"]) for k in LIFE if c.get(f"tier_{k}", 0) >= 2]
    if peaks:
        facts.append("Досяг: " + " · ".join(peaks))
    if p.achievements:
        facts.append(f"🏆 {len(p.achievements)}: " + ", ".join(p.achievements[-4:]))
    st = list(p.status.values())
    family = [f"💍 {names[p.partner]}" if p.partner in names else "",
              f"🥚 дітей: {p.children}" if p.children else "",
              f"🤝 друзів: {sum(s in ('friend', 'bestie') for s in st)}" if any(s in ("friend", "bestie") for s in st) else "",
              f"⚔️ ворогів: {sum(s in ('rival', 'enemy') for s in st)}" if any(s in ("rival", "enemy") for s in st) else "",
              f"💔 колишніх: {st.count('ex')}" if "ex" in st else ""]
    return dict(name=p.name, title=title, cause=p.cause, epitaph=p.epitaph, facts=facts,
                family=" · ".join(x for x in family if x), story=[x for _, _, x in p.story])


def obituary(p: Pet, names: dict[str, str] | None = None, limit: int = 1000, footer: str = "") -> str:
    """life_summary as a Telegram-HTML caption of at most `limit` chars: highlights are dropped (oldest
    first, the very first kept) until it fits, then facts; nothing is cut through a tag."""
    s = life_summary(p, names)
    cause = s["cause"][:1].upper() + s["cause"][1:]
    head = [f"🪦 <b>{_esc(s['name'])}</b> — <i>{_esc(s['title'])}</i>", f"⚰️ {_esc(cause)}"]
    tail = ([_esc(s["family"])] if s["family"] else []) + ([f"<i>«{_esc(s['epitaph'])}»</i>"] if s["epitaph"] else [])
    facts, story = [_esc(x) for x in s["facts"]], [_esc(x) for x in s["story"]]

    def build() -> str:
        body = head + [""] + facts + ([""] + ["📖 Найяскравіше:"] + [f"• {x}" for x in story] if story else []) + tail
        return "\n".join(body + ([footer] if footer else []))

    while len(build()) > limit and len(story) > 1:
        del story[1]
    while len(build()) > limit and story:
        story.pop()
    while len(build()) > limit and len(facts) > 1:
        facts.pop()
    return build()[:limit]


def card(p: Pet, names: dict[str, str]) -> str:
    """Status caption (<1024 chars). names: pid -> pet name for relations."""
    _, tier = p.rarity
    emoji = SPECIES_EMOJI.get(p.species, "🐾")
    if p.state == "egg":
        left = max(0, EGG_HOURS * hour() - (now() - p.born)) / 60
        return (f"🥚 <b>Яйце</b> · {_esc(p.owner_name)}\nЗсередини чути: «{_esc(p.persona.get('temper', ''))}»…\n"
                f"Вилупиться приблизно через {left:.0f} хв. Рідкість: {tier}"
                + (f"\n👑 {_esc(p.dynasty)}, покоління {p.gen}" if p.gen > 1 else ""))
    if p.state == "dead":
        return obituary(p, names, 1020, f"\n🥚 «Нове яйце» — покоління {p.gen + 1}" + (" (є спадкоємець від пари!)" if p.heir else ""))
    lines = [
        f"{emoji} <b>{_esc(p.name)}</b> · {STAGES[p.stage]} · {int(p.years)} р. · ур. {p.level}",
        f"👤 {_esc(p.owner_name)} · {tier}" + (f" · 👑 {_esc(p.dynasty)} ({p.gen})" if p.gen > 1 else ""),
    ]
    if p.role:
        lines.append(f"{ROLES[p.role]['name']} — <i>{ROLES[p.role]['desc']}</i>")
    lines += [
        f"❤️{bar(p.health)} 😊{bar(p.mood)}",
        f"💰 {int(p.money)} ₴ · {p.tier_name('money')}",
        " ".join(f"{LIFE[k][0]}{int(p.life.get(k, 0))}" for k in LIFE)
        + "".join(f" · {p.tier_name(k)}" for k in sorted(LIFE, key=lambda k: -p.life.get(k, 0))[:2] if p.tier(k) >= 1),
        " ".join(f"{SKILLS[s]}{int(p.skills.get(s, 0))}" for s in SKILLS)
        + (" · " + " ".join(TRAITS[t].split()[0] + str(int(p.traits[t])) for t in p.top_traits()) if p.top_traits() else ""),
    ]
    work = [JOBS[p.job]["name"] if p.job in JOBS else "", EDUCATION.get(p.edu[-1], "") if p.edu else "",
            bg_name(p.home)]
    lines.append(" · ".join(x for x in work if x))
    pr = p.persona
    lines.append(f"🎭 {_esc(pr.get('temper'))}, мріє {_esc(pr.get('dream'))}, боїться {_esc(pr.get('fear'))}")
    rels = []
    if p.partner:
        rels.append(f"💍 {_esc(names.get(p.partner, '?'))}")
    crush = [names[k] for k, s in p.status.items() if s == "crush" and k in names]
    if crush:
        rels.append(f"😳 {_esc(crush[0])}")
    fr = [names[k] for k, s in p.status.items() if s in ("friend", "bestie") and k in names]
    en = [names[k] for k, s in p.status.items() if s in ("rival", "enemy") and k in names]
    if fr:
        rels.append("🤝 " + ", ".join(_esc(x) for x in fr[:3]) + (f" +{len(fr) - 3}" if len(fr) > 3 else ""))
    if en:
        rels.append("⚔️ " + ", ".join(_esc(x) for x in en[:2]) + (f" +{len(en) - 2}" if len(en) > 2 else ""))
    if p.children or p.heir:
        rels.append(f"🥚 дітей: {p.children}")
    if rels:
        lines.append(" · ".join(rels))
    if p.achievements:
        lines.append(f"🏆 {len(p.achievements)}: " + ", ".join(_esc(a) for a in p.achievements[-3:]))
    if p.jailed:
        lines.append(f"⛓ За ґратами ще {(p.jail_until - now()) / hour():.0f} год.")
    if p.in_hospital:
        lines.append(f"🏥 У лікарні ще {(p.hospital_until - now()) / hour():.0f} год.")
    if p.pending:
        lines.append("❗ Чекає твого рішення в пригоді!")
    return "\n".join(lines)[:1020]
