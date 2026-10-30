"""Pet battles and tournaments — pure logic, reusable by the sandbox and (later) the bot.

A Fighter is built from a Pet snapshot: skills, level, stage, condition (hunger/mood/energy), species passive,
worn items, top traits (special moves) and supernatural role (ultimate). Battles are turn-based and non-lethal:
the loser is knocked out (a little health and mood lost), never killed.

    f1, f2 = Fighter.of(pet_a, "aggressive"), Fighter.of(pet_b, auto_strategy(pet_b, rng))
    res = fight(f1, f2, rng)       # res.winner (0/1), res.log [{r, side, text, hp:[a, b]}]
"""
import math
import random
from dataclasses import dataclass, field

from . import engine as E
from .grammar import inflect, pick

STRATEGIES = {
    "aggressive": ("⚔️ Агресивно", "більше шкоди, менше захисту"),
    "careful": ("🛡 Обережно", "захист і шанс підлікуватися"),
    "cunning": ("🎭 Хитро", "крити й ухиляння"),
    "lucky": ("🍀 На удачу", "шкода від нуля до неба"),
}
SPECIES_PASSIVE = {
    "pig": ("🐷 Товстошкірий", "+25% здоров'я"),
    "cat": ("🐱 Дев'ять життів", "+8% ухилятися"),
    "dog": ("🐶 Вірність до кінця", "+12% крит, коли мало здоров'я"),
    "fox": ("🦊 Хитрість", "+6% крит, краде трохи здоров'я"),
    "horse": ("🐴 Копито", "перший удар +40%"),
    "axolotl": ("🦎 Регенерація", "лікує 3% здоров'я щоходу"),
    "bird": ("🐦 Політ", "+12% ухилятися, атакує першою"),
}
# items that matter in a fight: (attack, defense)
ITEM_POWER = {"sabre": (6, 0), "helmet": (0, 5), "bronik": (0, 7), "cape": (1, 2), "horns": (3, 0),
              "crown": (2, 2), "medal": (1, 1), "eyepatch": (2, 0), "scar": (2, 0), "mustache": (1, 1),
              "wand": (3, 0), "guitar": (2, 0), "chain": (1, 1), "halo": (0, 3), "sunglasses": (1, 0)}
# trait -> (move name, cooldown turns)
SPECIALS = {
    "toxic": ("🤬 Токсичний коментар", 3), "gambler": ("🎰 Ва-банк", 3), "dark": ("💀 Прокляття", 4),
    "party": ("🪩 Дискотека", 4), "patriot": ("🇺🇦 Бойовий гопак", 3), "glutton": ("🍔 Перекус", 4),
    "love": ("🤗 Обійми", 4), "mystic": ("🔮 Таро в бою", 3),
}
ULTIMATES = {
    "vampire": "🧛 Укус у шию", "werewolf": "🐺 Вовчий рик", "demon": "😈 Пекельне полум'я",
    "angel": "😇 Благословення", "cyborg": "🤖 Лазер", "alien": "👽 Викрадення",
}
HITS = {
    "pig": ["таранить п'ятачком", "штовхає боком", "кусає за вухо"],
    "cat": ["дряпає кігтями", "б'є лапою по носі", "кусає за хвіст"],
    "dog": ["кусає за лапу", "налітає з гавкотом", "тягне за вухо"],
    "fox": ["кусає з-за спини", "б'є хвостом", "робить підсічку"],
    "horse": ["б'є копитом", "кусає за гриву", "лягає зверху"],
    "axolotl": ["шльопає плавником", "плює водою", "кусає беззубим ротом"],
    "bird": ["клює в тім'я", "б'є крилом", "пікірує з висоти"],
}
WIN_LINES = ["{w} {переміг|перемогла}! {l} лежить і рахує зірочки.", "Нокаут! {w} — справжн{ій боєць|я бійчиня}.",
             "{l} здається й просить шаурму. {w} перемагає.", "Суддя зупиняє бій: {w} забирає перемогу.",
             "{w} виграє. Глядачі кидають на ринг вареники."]


@dataclass
class Fighter:
    name: str
    owner: int
    species: str
    role: str
    hp: float
    max_hp: float
    atk: float
    dfn: float
    spd: float
    crit: float
    dodge: float
    strategy: str = "careful"
    gender: str = "m"
    specials: list = field(default_factory=list)   # [(trait, name, cooldown)]
    ultimate: str = ""
    elo: float = 1000.0
    cd: dict = field(default_factory=dict)
    dot: list = field(default_factory=list)        # [(dmg, turns)]
    stun: int = 0
    weak: int = 0                                  # turns of -20% attack
    buff: float = 1.0
    revived: bool = False
    ult_used: bool = False
    first_hit: bool = True

    def g(self, masculine: str, feminine: str) -> str:
        return feminine if self.gender == "f" else masculine

    @classmethod
    def of(cls, p: "E.Pet", strategy: str = "careful") -> "Fighter":
        sk = p.skill
        lvl = p.level
        stage_k = {1: 0.6, 2: 0.85, 3: 1.0, 4: 0.9}.get(p.stage, 0.8)
        cond = 0.6 + 0.4 * min(1.0, (p.hunger + p.mood + p.energy) / 210)
        atk_i = dfn_i = 0
        for it in p.equipped.values():
            a, d = ITEM_POWER.get(it.split("@")[0], (0.5, 0.5) if it.startswith("gen:") else (0, 0))
            atk_i, dfn_i = atk_i + a, dfn_i + d
        hp = (70 + sk("str") * 0.5 + lvl * 3 + p.health * 0.3) * (1.25 if p.species == "pig" else 1.0)
        f = cls(name=p.name, owner=p.owner_id, species=p.species, role=p.role, gender=p.gender,
                hp=hp * stage_k, max_hp=hp * stage_k,
                atk=(8 + sk("str") * 0.25 + lvl * 0.8 + atk_i) * stage_k * cond,
                dfn=(3 + sk("int") * 0.1 + dfn_i) * cond,
                spd=5 + sk("luck") * 0.05 + sk("int") * 0.05 + (3 if p.species in ("cat", "fox") else 5 if p.species == "bird" else 0),
                crit=0.05 + sk("luck") * 0.003 + (0.06 if p.species == "fox" else 0),
                dodge=0.04 + sk("luck") * 0.002 + (0.08 if p.species == "cat" else 0.12 if p.species == "bird" else 0) + (0.25 if p.role == "quantum" else 0),
                strategy=strategy if strategy in STRATEGIES else "careful",
                specials=[(t, *SPECIALS[t]) for t in p.top_traits(2)],
                ultimate=ULTIMATES.get(p.role, ""), elo=float(p.flags.get("elo", 1000)))
        if f.strategy == "aggressive":
            f.atk, f.dfn = f.atk * 1.18, f.dfn * 0.75
        elif f.strategy == "careful":
            f.atk, f.dfn = f.atk * 0.97, f.dfn * 1.7
        elif f.strategy == "cunning":
            f.crit, f.dodge = f.crit + 0.08, f.dodge + 0.06
        return f

    @property
    def power(self) -> int:
        """Rough strength for brackets and odds."""
        return int(self.max_hp * 0.4 + self.atk * 3 + self.dfn * 2 + self.spd + (self.crit + self.dodge) * 60
                   + len(self.specials) * 8 + (15 if self.ultimate else 0))


@dataclass
class BattleResult:
    winner: int                  # 0 or 1
    rounds: int
    log: list
    fighters: list               # [{name, max_hp, hp, strategy, passive, specials, ultimate}]
    text: str = ""


def auto_strategy(p: "E.Pet", rng: random.Random) -> str:
    """NPC / absent owner: tactic by personality."""
    tt = p.top_traits(1)
    t = tt[0] if tt else ""
    by_trait = {"toxic": "aggressive", "party": "aggressive", "patriot": "aggressive", "gambler": "lucky",
            "mystic": "lucky", "dark": "cunning", "love": "careful", "glutton": "careful"}.get(t)
    return by_trait if by_trait and rng.random() < 0.7 else rng.choice(list(STRATEGIES))


def _dmg(att: Fighter, de: Fighter, rng: random.Random, mult: float = 1.0, pierce: bool = False,
         sure: bool = False) -> tuple[float, str]:
    """sure = can't be dodged (ultimates, tarot's Tower)."""
    if not sure and de.stun == 0 and rng.random() < de.dodge:
        return 0.0, "dodge"
    k = rng.uniform(0.2, 1.8) if att.strategy == "lucky" else rng.uniform(0.8, 1.2)
    atk = att.atk * att.buff * (0.8 if att.weak else 1.0)
    if att.first_hit and att.species == "horse":
        k *= 1.4
    att.first_hit = False
    crit = att.crit + (0.12 if att.species == "dog" and att.hp < att.max_hp * 0.35 else 0)
    tag = ""
    if rng.random() < crit:
        k *= 1.8
        tag = "crit"
    d = max(1.0, atk * k * mult - (0 if pierce else de.dfn * 0.5))
    return d, tag


def fight(a: Fighter, b: Fighter, rng: random.Random, max_rounds: int = 25) -> BattleResult:
    fs = [a, b]
    log: list[dict] = []

    def say(side: int, text: str) -> None:
        log.append(dict(r=rnd, side=side, text=text, hp=[round(max(0, a.hp)), round(max(0, b.hp))]))

    rnd = 0
    say(-1, f"🔔 {a.name} ({STRATEGIES[a.strategy][0]}) проти {inflect(b.name, "gen", b.gender)} ({STRATEGIES[b.strategy][0]})!")
    order = [0, 1] if a.spd + rng.random() * 3 >= b.spd + rng.random() * 3 else [1, 0]
    winner = None
    for rnd in range(1, max_rounds + 1):
        for i in order:
            me, foe = fs[i], fs[1 - i]
            if me.hp <= 0 or foe.hp <= 0:
                continue
            # start of turn: damage over time, regeneration, timers
            for dot in me.dot:
                me.hp -= dot[0]
                say(i, f"💀 Прокляття гризе {inflect(me.name, "acc", me.gender)}: −{dot[0]:.0f}")
            me.dot = [(d, t - 1) for d, t in me.dot if t > 1]
            if me.species == "axolotl" and me.hp > 0:
                heal = me.max_hp * 0.03
                me.hp = min(me.max_hp, me.hp + heal)
            if me.weak:
                me.weak -= 1
            for k in list(me.cd):
                me.cd[k] = max(0, me.cd[k] - 1)
            if me.hp <= 0:
                break
            if me.stun:
                me.stun -= 1
                say(i, f"😵 {me.name} пропускає хід")
                continue
            _act(me, foe, i, rng, say)
            if foe.hp <= 0 and foe.role == "zombie" and not foe.revived:
                foe.revived = True
                foe.hp = foe.max_hp * 0.3
                say(1 - i, f"🧟 {foe.name} встає з мертвих! (ще {foe.hp:.0f})")
        if a.hp <= 0 or b.hp <= 0:
            winner = 0 if b.hp <= 0 else 1
            break
    if winner is None:  # judges' decision
        winner = 0 if a.hp / a.max_hp >= b.hp / b.max_hp else 1
        say(-1, "⏱ Час вийшов — рішення суддів за відсотком здоров'я")
    w, l = fs[winner], fs[1 - winner]
    text = pick(rng.choice(WIN_LINES), w.gender, l.gender).format(w=w.name, l=l.name)
    say(winner, f"🏆 {text}")
    info = [dict(name=f.name, max_hp=round(f.max_hp), hp=round(max(0, f.hp)), strategy=STRATEGIES[f.strategy][0],
                 passive=SPECIES_PASSIVE.get(f.species, ("", ""))[0], specials=[s[1] for s in f.specials],
                 ultimate=f.ultimate, power=f.power) for f in fs]
    return BattleResult(winner, rnd, log, info, text)


def _act(me: Fighter, foe: Fighter, i: int, rng: random.Random, say) -> None:
    # ultimate: once per battle, when it matters
    named = lambda side, text: say(side, f"{me.name} → {text}")  # specials always say who did it
    if me.ultimate and not me.ult_used and (me.hp < me.max_hp * 0.5 or rng.random() < 0.15):
        me.ult_used = True
        return _ultimate(me, foe, i, rng, named)
    ready = [s for s in me.specials if me.cd.get(s[0], 0) == 0]
    if me.strategy == "careful" and me.hp < me.max_hp * 0.35 and rng.random() < 0.45:
        heal = me.max_hp * 0.15
        me.hp = min(me.max_hp, me.hp + heal)
        return say(i, f"🩹 {me.name} відступає й зализує рани: +{heal:.0f}")
    if ready and rng.random() < 0.45:
        trait, name, cd = rng.choice(ready)
        me.cd[trait] = cd
        return _special(me, foe, i, trait, name, rng, named)
    d, tag = _dmg(me, foe, rng)
    verb = rng.choice(HITS.get(me.species, ["б'є"]))
    if tag == "dodge":
        return say(i, f"💨 {me.name} {verb}, але {foe.name} ухиляється")
    foe.hp -= d
    if me.species == "fox":
        me.hp = min(me.max_hp, me.hp + d * 0.1)
    say(i, f"{'💥 КРИТ! ' if tag == 'crit' else ''}{me.name} {verb} → {foe.name} −{d:.0f}")


def _special(me: Fighter, foe: Fighter, i: int, trait: str, name: str, rng: random.Random, say) -> None:
    if trait == "toxic":
        d, tag = _dmg(me, foe, rng, 0.5)
        if tag == "dodge":
            return say(i, f"{name}: {foe.name} навіть не слухає")
        foe.hp -= d
        foe.weak = 2
        say(i, f"{name}: «{rng.choice(['ти граєш як бот', 'твоя мама — пилосос', 'лох, просто лох'])}». "
               f"{foe.name} −{d:.0f} і {foe.g('засмучений', 'засмучена')} (−20% атаки)")
    elif trait == "gambler":
        if rng.random() < 0.5:
            d, tag = _dmg(me, foe, rng, 2.5)
            if tag == "dodge":
                return say(i, f"{name}: ставка зіграла, але {foe.name} {foe.g('ухилився', 'ухилилася')}")
            foe.hp -= d
            say(i, f"{name} — ДЖЕКПОТ! {foe.name} −{d:.0f}")
        else:
            d = me.max_hp * 0.12
            me.hp -= d
            say(i, f"{name} — казино завжди виграє. {me.name} −{d:.0f}")
    elif trait == "dark":
        foe.dot.append((max(3.0, me.atk * 0.35), 3))
        say(i, f"{name}: на {inflect(foe.name, "acc", foe.gender)} падає тінь (шкода 3 ходи)")
    elif trait == "party":
        if rng.random() < 0.6:
            foe.stun = 1
            say(i, f"{name}: {foe.name} {foe.g('не втримався', 'не втрималася')} й танцює замість бою")
        else:
            say(i, f"{name}: {foe.name} не любить техно. Не подіяло")
    elif trait == "patriot":
        d, tag = _dmg(me, foe, rng, 1.4)
        me.buff = min(1.6, me.buff + 0.15)
        if tag == "dodge":
            return say(i, f"{name}! {foe.name} {foe.g('ухилився', 'ухилилася')}, але {me.name} надихається (+15% атаки)")
        foe.hp -= d
        say(i, f"{name}! {foe.name} −{d:.0f}, {me.name} надихається (+15% атаки)")
    elif trait == "glutton":
        heal = me.max_hp * 0.25
        me.hp = min(me.max_hp, me.hp + heal)
        say(i, f"{name}: {me.name} дістає бутерброд посеред бою. +{heal:.0f}")
    elif trait == "love":
        if rng.random() > 0.7:
            return say(i, f"{name}: {foe.name} {foe.g('вивернувся', 'вивернулася')} з обіймів")
        foe.stun = 1
        me.hp = min(me.max_hp, me.hp + 5)
        foe.hp = min(foe.max_hp, foe.hp + 5)
        say(i, f"{name}: {foe.name} {foe.g('розчулився', 'розчулилася')} й {foe.g('забув', 'забула')}, що треба битися")
    elif trait == "mystic":
        card = rng.choice(["sun", "tower", "death", "fool"])
        if card == "sun":
            heal = me.max_hp * 0.2
            me.hp = min(me.max_hp, me.hp + heal)
            say(i, f"{name}: Сонце! {me.name} +{heal:.0f}")
        elif card == "tower":
            d, _ = _dmg(me, foe, rng, 2.0, pierce=True, sure=True)
            foe.hp -= d
            say(i, f"{name}: Вежа! На {inflect(foe.name, "acc", foe.gender)} падає цегла. −{d:.0f}")
        elif card == "death":
            foe.dot.append((max(4.0, me.atk * 0.5), 2))
            say(i, f"{name}: Смерть! {foe.name} відчуває холод (шкода 2 ходи)")
        else:
            me.stun = 1
            say(i, f"{name}: Блазень. {me.name} {me.g('заплутався', 'заплуталася')} у власних картах")


def _ultimate(me: Fighter, foe: Fighter, i: int, rng: random.Random, say) -> None:
    u, r = me.ultimate, me.role
    if r == "vampire":
        d, _ = _dmg(me, foe, rng, 1.5, sure=True)
        foe.hp -= d
        me.hp = min(me.max_hp, me.hp + d)
        say(i, f"{u}! {foe.name} −{d:.0f}, {me.name} +{d:.0f}")
    elif r == "werewolf":
        me.buff = min(2.0, me.buff + (0.6 if E.is_night() else 0.4))
        say(i, f"{u}! {me.name} звіріє (+{'60' if E.is_night() else '40'}% атаки)")
    elif r == "demon":
        d, _ = _dmg(me, foe, rng, 2.0, sure=True)
        foe.hp -= d
        foe.dot.append((max(3.0, me.atk * 0.3), 2))
        say(i, f"{u}! {foe.name} −{d:.0f} і горить")
    elif r == "angel":
        heal = me.max_hp * 0.4
        me.hp = min(me.max_hp, me.hp + heal)
        say(i, f"{u}: з неба сяйво. {me.name} +{heal:.0f}")
    elif r == "cyborg":
        d, _ = _dmg(me, foe, rng, 2.2, pierce=True, sure=True)
        foe.hp -= d
        say(i, f"{u}: пряме влучання крізь будь-який захист. {foe.name} −{d:.0f}")
    elif r == "alien":
        foe.stun = 2
        say(i, f"{u}: {foe.name} на два ходи зник у тарілці")


def win_chance(a: Fighter, b: Fighter) -> float:
    """Elo blended with power: used for odds and bracket seeding."""
    elo = 1 / (1 + 10 ** ((b.elo - a.elo) / 400))
    pw = 1 / (1 + math.exp(-(a.power - b.power) / 25))
    return max(0.05, min(0.95, 0.5 * elo + 0.5 * pw))


def update_elo(win: "E.Pet", lose: "E.Pet", k: float = 32) -> int:
    ra, rb = float(win.flags.get("elo", 1000)), float(lose.flags.get("elo", 1000))
    ea = 1 / (1 + 10 ** ((rb - ra) / 400))
    delta = round(k * (1 - ea))
    win.flags["elo"], lose.flags["elo"] = round(ra + delta), round(rb - delta)
    win.flags["wins"] = win.flags.get("wins", 0) + 1
    lose.flags["losses"] = lose.flags.get("losses", 0) + 1
    return delta


def aftermath(win: "E.Pet", lose: "E.Pet", rng: random.Random) -> tuple[list[str], list[str]]:
    """Non-lethal consequences of a battle. Returns effect notes (winner, loser)."""
    delta = update_elo(win, lose)
    wn = win.apply(dict(mood=10, xp=8, str=0.5), None, rng)
    ln = lose.apply(dict(mood=-10, health=-8, xp=3), None, rng)
    win.note("battle", f"🥊 {win.name} {win.g('переміг', 'перемогла')} {inflect(lose.name, "acc", lose.gender)} (рейтинг +{delta})")
    lose.note("battle", f"🥊 {lose.name} {lose.g('програв', 'програла')} {inflect(win.name, "dat", win.gender)} (рейтинг −{delta})")
    if win.flags["wins"] in (5, 20, 50):
        win.ach({5: "Бійцівський клуб", 20: "Гроза району", 50: "Непереможний"}[win.flags["wins"]])
    return wn + [f"🏅 +{delta}"], ln + [f"🏅 −{delta}"]


def eligible(p: "E.Pet") -> bool:
    return p.alive and p.stage >= 2 and not p.jailed and not p.in_hospital


def bracket(pets: list["E.Pet"], rng: random.Random, size_cap: int = 16) -> list[list[list[int]]]:
    """Single elimination. Returns rounds → matches → [owner_a, owner_b] (0 = bye/empty). Top seeds get byes."""
    seeds = sorted(pets, key=lambda p: (-p.flags.get("elo", 1000), -Fighter.of(p).power, rng.random()))[:size_cap]
    n = 1
    while n < len(seeds):
        n *= 2
    order = [0]
    while len(order) < n:  # standard seeding: 1 v n, 2 v n-1, ... spread across the bracket
        m = len(order) * 2
        order = [x for s in order for x in (s, m - 1 - s)]
    slots = [seeds[s].owner_id if s < len(seeds) else 0 for s in order]
    rounds = [[[slots[i], slots[i + 1]] for i in range(0, n, 2)]]
    while len(rounds[-1]) > 1:
        rounds.append([[0, 0] for _ in range(len(rounds[-1]) // 2)])
    return rounds
