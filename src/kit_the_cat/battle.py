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

DUEL = "duel"   # the strategy of a fighter in a duel: no bonus of its own, the moves decide
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


def item_stats(item: str) -> dict:
    """What a worn item gives: {"atk": n, "dfn": n, "skills": {skill: n}} (battle power from ITEM_POWER, a skill
    bonus for adventures from engine.item_skill). A generated item gives +0.5 to both battle stats."""
    a, d = ITEM_POWER.get(item.split("@")[0], (0.5, 0.5) if item.startswith("gen:") else (0, 0))
    return dict(atk=a, dfn=d, skills=E.item_skill(item))


def item_label(item: str) -> str:
    """«🗡️+6 · 🛡️+5 · 💪+3»: battle attack, defence and skill bonuses of an item; "" when it gives nothing."""
    st = item_stats(item)
    parts = [f"{icon}+{v:g}" for icon, v in (("🗡️", st["atk"]), ("🛡️", st["dfn"])) if v]
    parts += [f"{E.SKILLS[k]}+{v}" for k, v in st["skills"].items() if v]
    return " · ".join(parts)


# trait -> (move name, cooldown turns)
SPECIALS = {
    "toxic": ("🤬 Токсичний коментар", 3), "gambler": ("🎰 Ва-банк", 3), "dark": ("💀 Прокляття", 4),
    "party": ("🪩 Дискотека", 4), "patriot": ("🔥 Друге дихання", 3), "glutton": ("🍔 Перекус", 4),
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
SURRENDER_LINES = ["{l} кидає на ринг білий рушник. {w} забирає перемогу без зайвих синців.",
                   "{l} каже «досить» і просить пиріжок. {w} перемагає.",
                   "Бій зупинено: {l} {other:вирішив|вирішила} берегти здоров'я. Перемагає {w}."]


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
    wit: float = 0.0                               # the pet's intellect: how well it reads the opponent in a duel

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
                strategy=strategy if strategy in STRATEGIES or strategy == DUEL else "careful", wit=float(sk("int")),
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
    log: list                    # [{r, side, text, hp, k, i}]; k = "" | crit | miss | special | ult | dot | skip | tactic | surrender
    fighters: list               # [{name, emoji, max_hp, hp, strategy, passive, specials, ultimate, power}]
    text: str = ""
    highlights: list = field(default_factory=list)   # <= HIGHLIGHTS log entries (same shape, with their log index `i`)
    surrendered: int = -1        # side that gave up, or -1


# --- tactics: the one decision of a fight --------------------------------------------------------------------
TACTICS = {
    "allin": ("🔥 Ва-банк", "атака +30%, захист −30%"),
    "defend": ("🛡 В оборону", "захист +40%, атака −20%"),
    "surrender": ("🏳 Здатися", "програти зараз і зберегти здоров'я"),
}
HOLD = "hold"                  # no change: the default
STOP_AT = 0.5                  # the fight pauses when a fighter first drops below this share of health
HIGHLIGHTS = 8


@dataclass
class FightState:
    """A fight paused at `stop_at` (or finished): `resume()` plays the rest. Plain data, nothing is rolled while paused."""
    fighters: list
    log: list
    order: list
    rnd: int = 1                 # round being played
    pos: int = 0                 # index into `order` of the next turn of the round
    max_rounds: int = 25
    stop_at: float = 0.0
    triggered: bool = False      # the pause already happened
    low: int = -1                # side that fell below `stop_at` first
    done: bool = False
    result: "BattleResult | None" = None

    @property
    def paused(self) -> bool:
        return not self.done

    def info(self) -> list:
        return _info(self.fighters)


def auto_strategy(p: "E.Pet", rng: random.Random) -> str:
    """NPC / absent owner: tactic by personality."""
    tt = p.top_traits(1)
    t = tt[0] if tt else ""
    by_trait = {"toxic": "aggressive", "party": "aggressive", "patriot": "aggressive", "gambler": "lucky",
            "mystic": "lucky", "dark": "cunning", "love": "careful", "glutton": "careful"}.get(t)
    return by_trait if by_trait and rng.random() < 0.7 else rng.choice(list(STRATEGIES))


def auto_tactic(f: "Fighter") -> str:
    """The mid-fight tactic of an NPC (or an absent owner), from the strategy `auto_strategy` gave it. Never surrenders."""
    if f.strategy == "aggressive":
        return "allin"
    if f.strategy == "careful":
        return "defend"
    if f.strategy == "lucky":
        return "allin" if f.hp < f.max_hp * 0.4 else HOLD
    return HOLD


def _info(fs: list) -> list:
    return [dict(name=f.name, emoji=E.SPECIES_EMOJI.get(f.species, "🐾"), max_hp=round(f.max_hp),
                 hp=round(max(0, f.hp)), strategy=STRATEGIES.get(f.strategy, ("🥊 Дуель", ""))[0],
                 passive=SPECIES_PASSIVE.get(f.species, ("", ""))[0], specials=[s[1] for s in f.specials],
                 ultimate=f.ultimate, power=f.power) for f in fs]


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


def fight(a: Fighter, b: Fighter, rng: random.Random, max_rounds: int = 25,
          stop_at: float | None = None) -> "BattleResult | FightState":
    """Play a fight. One call returns the BattleResult. With `stop_at` (0.5: when a fighter first drops below half
    of its health) it returns a FightState: paused with `state.paused`, or already finished (`state.result`) when
    nobody dropped that low. `resume(state, tactic_a, tactic_b, rng)` plays the rest, with the same rng."""
    st = FightState([a, b], [], [0, 1], max_rounds=max_rounds, stop_at=stop_at or 0.0)
    _say(st, -1, f"🔔 {a.name} ({STRATEGIES[a.strategy][0]}) проти {inflect(b.name, "gen", b.gender)} ({STRATEGIES[b.strategy][0]})!", "", 0)
    st.order = [0, 1] if a.spd + rng.random() * 3 >= b.spd + rng.random() * 3 else [1, 0]
    _run(st, rng)
    return st if stop_at else st.result


def resume(st: FightState, tactic_a: str | None, tactic_b: str | None, rng: random.Random) -> BattleResult:
    """Finish a paused fight. Tactics: "allin", "defend", "surrender", or None / "hold" for no change."""
    if st.done:
        return st.result
    a, b = st.fighters
    gave_up = 0 if tactic_a == "surrender" else 1 if tactic_b == "surrender" else -1
    for side, (f, t) in enumerate(((a, tactic_a), (b, tactic_b))):
        if gave_up >= 0:
            break
        if t == "allin":
            f.atk, f.dfn = f.atk * 1.3, f.dfn * 0.7
            _say(st, side, f"🔥 {f.name} іде ва-банк: атака +30%, захист −30%", "tactic")
        elif t == "defend":
            f.atk, f.dfn = f.atk * 0.8, f.dfn * 1.4
            _say(st, side, f"🛡 {f.name} стає в оборону: захист +40%, атака −20%", "tactic")
    if gave_up >= 0:
        _say(st, gave_up, f"🏳 {st.fighters[gave_up].name} здається", "surrender")
        _verdict(st, 1 - gave_up, rng, gave_up)
    else:
        _run(st, rng)
    return st.result


def _say(st: FightState, side: int, text: str, kind: str = "", rnd: int | None = None) -> None:
    a, b = st.fighters
    st.log.append(dict(r=st.rnd if rnd is None else rnd, side=side, text=text, k=kind, i=len(st.log),
                       hp=[round(max(0, a.hp)), round(max(0, b.hp))]))


def _run(st: FightState, rng: random.Random) -> None:
    a, b = st.fighters
    fs = st.fighters
    while st.rnd <= st.max_rounds:
        while st.pos < 2:
            i = st.order[st.pos]
            st.pos += 1
            me, foe = fs[i], fs[1 - i]
            if me.hp <= 0 or foe.hp <= 0:
                continue
            say = lambda side, text, kind="": _say(st, side, text, kind)  # noqa: E731
            # start of turn: damage over time, regeneration, timers
            for dot in me.dot:
                me.hp -= dot[0]
                say(i, f"💀 Прокляття гризе {inflect(me.name, "acc", me.gender)}: −{dot[0]:.0f}", "dot")
            me.dot = [(d, t - 1) for d, t in me.dot if t > 1]
            if me.species == "axolotl" and me.hp > 0:
                heal = me.max_hp * 0.03
                me.hp = min(me.max_hp, me.hp + heal)
            if me.weak:
                me.weak -= 1
            for k in list(me.cd):
                me.cd[k] = max(0, me.cd[k] - 1)
            if me.hp <= 0:
                st.pos = 2
                break
            if me.stun:
                me.stun -= 1
                say(i, f"😵 {me.name} пропускає хід", "skip")
                continue
            _act(me, foe, i, rng, say)
            if foe.hp <= 0 and foe.role == "zombie" and not foe.revived:
                foe.revived = True
                foe.hp = foe.max_hp * 0.3
                say(1 - i, f"🧟 {foe.name} встає з мертвих! (ще {foe.hp:.0f})", "special")
            if st.stop_at and not st.triggered and a.hp > 0 and b.hp > 0:
                low = [s for s in (0, 1) if fs[s].hp < fs[s].max_hp * st.stop_at]
                if low:  # the decision point: pause here (nothing is rolled)
                    st.triggered, st.low = True, low[0] if len(low) == 1 else i
                    return
        if a.hp <= 0 or b.hp <= 0:
            return _verdict(st, 0 if b.hp <= 0 else 1, rng)
        st.rnd, st.pos = st.rnd + 1, 0
    st.rnd = st.max_rounds
    _verdict(st, None, rng)


def _verdict(st: FightState, winner: int | None, rng: random.Random, gave_up: int = -1) -> None:
    a, b = st.fighters
    if winner is None:  # judges' decision
        winner = 0 if a.hp / a.max_hp >= b.hp / b.max_hp else 1
        _say(st, -1, "⏱ Час вийшов — рішення суддів за відсотком здоров'я")
    w, l = st.fighters[winner], st.fighters[1 - winner]
    text = pick(rng.choice(SURRENDER_LINES if gave_up >= 0 else WIN_LINES), w.gender, l.gender).format(w=w.name, l=l.name)
    _say(st, winner, f"🏆 {text}")
    st.done = True
    st.result = BattleResult(winner, st.rnd, st.log, _info(st.fighters), text, _highlights(st.log, [a.max_hp, b.max_hp]), gave_up)


def _highlights(log: list, max_hp: list, limit: int = HIGHLIGHTS) -> list:
    """The lines worth reading: the opening, the turning point (the last time the lead changed), crits, specials and
    ultimates (biggest swings first), the finishing blow and the verdict. At most `limit` entries, in order."""
    n = len(log)
    if n <= limit:
        return list(log)
    keep = {0, n - 1, n - 2}   # opening, finishing blow, verdict
    lead, flip = 0, None
    for e in log:
        d = e["hp"][0] / max_hp[0] - e["hp"][1] / max_hp[1]
        now = 1 if d > 0.02 else -1 if d < -0.02 else 0
        if now and lead and now != lead:
            flip = e["i"]
        lead = now or lead
    if flip is not None:
        keep.add(flip)
    swing = lambda i: sum(abs(x - y) for x, y in zip(log[i - 1]["hp"], log[i]["hp"])) if i else 0  # noqa: E731
    rank = {"ult": 3, "surrender": 3, "special": 2, "crit": 1}
    cands = sorted((e["i"] for e in log if e["k"] in rank and e["i"] not in keep), key=lambda i: (-rank[log[i]["k"]], -swing(i), i))
    for i in cands:
        if len(keep) >= limit:
            break
        keep.add(i)
    for i in sorted((e["i"] for e in log if e["i"] not in keep), key=lambda i: (-swing(i), i)):
        if len(keep) >= min(5, limit):  # a quiet fight still gets a few lines
            break
        keep.add(i)
    return [log[i] for i in sorted(keep)]


def _act(me: Fighter, foe: Fighter, i: int, rng: random.Random, say) -> None:
    # ultimate: once per battle, when it matters
    named = lambda side, text: say(side, f"{me.name} → {text}", "special")  # specials always say who did it
    if me.ultimate and not me.ult_used and (me.hp < me.max_hp * 0.5 or rng.random() < 0.15):
        me.ult_used = True
        return _ultimate(me, foe, i, rng, lambda side, text: say(side, f"{me.name} → {text}", "ult"))
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
        return say(i, f"💨 {me.name} {verb}, але {foe.name} ухиляється", "miss")
    foe.hp -= d
    if me.species == "fox":
        me.hp = min(me.max_hp, me.hp + d * 0.1)
    say(i, f"{'💥 КРИТ! ' if tag == 'crit' else ''}{me.name} {verb} → {foe.name} −{d:.0f}", tag)


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


# --- duel: a fight the player plays round by round -------------------------------------------------------------
# Each round both sides pick a move in secret. Strike beats Trick, Trick beats Guard, Guard beats Strike; how much a
# move does comes from the fighter's numbers (skills, level, worn items), so the choice and the build both matter.
MOVES = {
    "strike": ("⚔️ Удар", "сила й зброя; б'є хитрість, програє захисту"),
    "guard": ("🛡 Захист", "блок і контрудар; б'є удар, програє хитрості"),
    "trick": ("🎭 Хитрість", "удача, повз броню; б'є захист, програє удару"),
}
BEATS = {"strike": "trick", "trick": "guard", "guard": "strike"}
SPECIAL, ULT, SURRENDER = "special", "ult", "surrender"
DUEL_ROUNDS = 7
DUEL_HP = 0.58       # a duel is short: fighters enter it with this share of their health pool
TELLS = {
    "strike": ["{name} стискає лапи й дивиться просто в очі", "{name} нахиляється вперед і сопе", "{name} бере розгін"],
    "guard": ["{name} задкує і прикриває ніс", "{name} втягує голову в плечі", "{name} стає боком і чекає"],
    "trick": ["{name} підозріло всміхається й дивиться вбік", "{name} щось ховає за спиною", "{name} насвистує, ніби нічого не задумує"],
    "special": ["{name} щось шепоче собі під ніс", "{name} робить глибокий вдих", "В очах {name_gen} щось блиснуло"],
}


@dataclass
class Duel:
    """A fight in rounds. `duel_round()` plays one; plain data in between, nothing is rolled while it waits."""
    fighters: list
    log: list
    rnd: int = 1
    max_rounds: int = DUEL_ROUNDS
    plan: list = field(default_factory=lambda: [None, None])   # a move already decided for the next round (see duel_tell)
    used: list = field(default_factory=lambda: [[], []])       # what each side has played, in order
    done: bool = False
    result: "BattleResult | None" = None

    def info(self) -> list:
        return _info(self.fighters)


def duel(a: Fighter, b: Fighter, rng: random.Random, max_rounds: int = DUEL_ROUNDS) -> Duel:
    """Start a duel between two fighters built with `Fighter.of(pet, DUEL)`."""
    for f in (a, b):
        f.max_hp = f.hp = f.max_hp * DUEL_HP
    d = Duel([a, b], [], max_rounds=max_rounds)
    _say(d, -1, f"🔔 {a.name} проти {inflect(b.name, "gen", b.gender)}! До {max_rounds} раундів.", "", 0)
    return d


def _ready(f: Fighter) -> tuple | None:
    return next((s for s in f.specials if f.cd.get(s[0], 0) == 0), None)


def _kind(move: str) -> str:
    return move if move in MOVES else "strike"   # a special or an ultimate meets the other move like a strike


def duel_moves(d: Duel, side: int) -> list[dict]:
    """What `side` can play this round: [{key, label, hint, power}]. `power` is the damage to expect if the move wins."""
    me, foe = d.fighters[side], d.fighters[1 - side]
    atk = me.atk * me.buff * (0.8 if me.weak else 1.0)
    hit = max(1.0, atk - foe.dfn * 0.5)
    power = {"strike": hit * 1.15, "guard": hit, "trick": atk * 1.1}
    out = [dict(key=k, label=n, hint=h, power=round(power[k])) for k, (n, h) in MOVES.items()]
    sp = _ready(me)
    if sp:
        out.append(dict(key=SPECIAL, label=sp[1], hint=f"прийом характеру, потім {sp[2]} раунди перерви", power=0))
    if me.ultimate and not me.ult_used:
        out.append(dict(key=ULT, label=me.ultimate, hint="раз на бій", power=0))
    return out


def auto_move(d: Duel, side: int, rng: random.Random) -> str:
    """The move of an NPC (or an absent owner): leans on its best numbers and on what the opponent keeps playing."""
    me = d.fighters[side]
    if me.ultimate and not me.ult_used and (me.hp < me.max_hp * 0.5 or rng.random() < 0.15):
        return ULT
    if _ready(me) and rng.random() < 0.3:
        return SPECIAL
    w = {m["key"]: 1.0 + m["power"] / 40 for m in duel_moves(d, side) if m["key"] in MOVES}
    if me.hp < me.max_hp * 0.3:
        w["guard"] += 0.4
    seen = d.used[1 - side][-3:]
    for m in seen:   # answer the habit: play what beats the move the opponent repeats
        if m in MOVES:
            w[next(k for k, v in BEATS.items() if v == m)] += 1.8 / len(seen)
    return rng.choices(list(w), weights=list(w.values()))[0]


def duel_tell(d: Duel, side: int, rng: random.Random) -> str:
    """Decide the next move of `side` now and say how it looks to the opponent. The sharper the opponent's wit, the
    more often the look is honest (45–80%); otherwise it shows a move the fighter is not going to play."""
    me, foe = d.fighters[side], d.fighters[1 - side]
    move = d.plan[side] = auto_move(d, side, rng)
    shown = SPECIAL if move in (SPECIAL, ULT) else move
    if rng.random() > min(0.8, 0.45 + foe.wit * 0.004):
        shown = rng.choice([k for k in MOVES if k != shown])
    return rng.choice(TELLS[shown]).format(name=me.name, name_gen=inflect(me.name, "gen", me.gender))


def duel_round(d: Duel, move_a: str | None, move_b: str | None, rng: random.Random) -> "BattleResult | None":
    """Play one round. A move is a key of MOVES, "special", "ult" or "surrender"; None = the fighter decides itself
    (the move `duel_tell` announced, if any). Returns the BattleResult when the duel is over, else None."""
    if d.done:
        return d.result
    fs = d.fighters
    moves = []
    for side, m in enumerate((move_a, move_b)):
        m = m or d.plan[side] or auto_move(d, side, rng)
        ok = {x["key"] for x in duel_moves(d, side)} | {SURRENDER}
        moves.append(m if m in ok else "strike")
    d.plan = [None, None]
    for side in (0, 1):
        if moves[side] == SURRENDER:
            _say(d, side, f"🏳 {fs[side].name} здається", "surrender")
            _verdict(d, 1 - side, rng, side)
            return d.result
    say = lambda side, text, kind="": _say(d, side, text, kind)  # noqa: E731
    # start of the round: timers, damage over time, regeneration
    stunned = [False, False]
    for i, me in enumerate(fs):
        for dot in me.dot:
            me.hp -= dot[0]
            say(i, f"💀 Прокляття гризе {inflect(me.name, "acc", me.gender)}: −{dot[0]:.0f}", "dot")
        me.dot = [(x, t - 1) for x, t in me.dot if t > 1]
        if me.species == "axolotl" and me.hp > 0:
            me.hp = min(me.max_hp, me.hp + me.max_hp * 0.03)
        me.weak = max(0, me.weak - 1)
        for k in list(me.cd):
            me.cd[k] = max(0, me.cd[k] - 1)
        if me.stun:
            me.stun -= 1
            stunned[i] = True
    if not _duel_over(d, rng):
        for i in (0, 1):
            d.used[i].append(moves[i])
        label = lambda i: "😵 пропускає раунд" if stunned[i] else _move_label(fs[i], moves[i])  # noqa: E731
        _say(d, -1, f"Раунд {d.rnd}: {fs[0].name} — {label(0)}, {fs[1].name} — {label(1)}", "round")
        first = 0 if fs[0].spd + rng.random() * 3 >= fs[1].spd + rng.random() * 3 else 1
        _exchange(d, moves, stunned, first, rng, say)
        _duel_over(d, rng)
    if not d.done:
        d.rnd += 1
        if d.rnd > d.max_rounds:
            d.rnd = d.max_rounds
            _verdict(d, None, rng)
    return d.result


def _move_label(f: Fighter, move: str) -> str:
    if move == ULT:
        return f.ultimate
    if move == SPECIAL:
        sp = _ready(f)
        return sp[1] if sp else MOVES["strike"][0]
    return MOVES[move][0]


def _duel_over(d: Duel, rng: random.Random) -> bool:
    a, b = d.fighters
    if not d.done and (a.hp <= 0 or b.hp <= 0):
        _verdict(d, 0 if b.hp <= 0 else 1, rng)
    return d.done


def _land(me: Fighter, foe: Fighter, i: int, rng: random.Random, say, mult: float, how: str, pierce: bool = False,
          crit: float = 0.0) -> None:
    """One hit of a duel: `how` is the phrase after the name («б'є першим»)."""
    if me.hp <= 0 or foe.hp <= 0:
        return
    me.crit += crit
    dmg, tag = _dmg(me, foe, rng, mult, pierce=pierce)
    me.crit -= crit
    if tag == "dodge":
        return say(i, f"💨 {me.name} {how}, але {foe.name} ухиляється", "miss")
    foe.hp -= dmg
    if me.species == "fox":
        me.hp = min(me.max_hp, me.hp + dmg * 0.1)
    say(i, f"{'💥 КРИТ! ' if tag == 'crit' else ''}{me.name} {how} → {foe.name} −{dmg:.0f}", tag)
    if foe.hp <= 0 and foe.role == "zombie" and not foe.revived:
        foe.revived = True
        foe.hp = foe.max_hp * 0.3
        say(1 - i, f"🧟 {foe.name} встає з мертвих! (ще {foe.hp:.0f})", "special")


def _exchange(d: Duel, moves: list, stunned: list, first: int, rng: random.Random, say) -> None:
    fs = d.fighters
    verb = lambda f: rng.choice(HITS.get(f.species, ["б'є"]))  # noqa: E731
    # the named moves happen whatever the other side does
    for i in (first, 1 - first):
        me, foe, m = fs[i], fs[1 - i], moves[i]
        if stunned[i] or me.hp <= 0 or foe.hp <= 0:
            continue
        if m == ULT:
            me.ult_used = True
            _ultimate(me, foe, i, rng, lambda side, text, me=me: say(side, f"{me.name} → {text}", "ult"))
        elif m == SPECIAL and (sp := _ready(me)):
            me.cd[sp[0]] = sp[2] + 1
            _special(me, foe, i, sp[0], sp[1], rng, lambda side, text, me=me: say(side, f"{me.name} → {text}", "special"))
    kinds = [_kind(m) for m in moves]
    plain = [moves[i] in MOVES and not stunned[i] for i in (0, 1)]   # still has a move to resolve
    for i in (0, 1):   # a stunned fighter is an open target
        if stunned[i] and plain[1 - i]:
            me, foe = fs[1 - i], fs[i]
            if kinds[1 - i] == "guard":
                heal = me.max_hp * 0.06
                me.hp = min(me.max_hp, me.hp + heal)
                say(1 - i, f"🩹 {me.name} переводить подих: +{heal:.0f}")
            else:
                _land(me, foe, 1 - i, rng, say, 1.15, f"{verb(me)} без опору", pierce=kinds[1 - i] == "trick")
    if stunned[0] or stunned[1]:
        return
    a, b = kinds
    if a == b:
        if a == "strike":
            for i in (first, 1 - first):
                if plain[i]:
                    _land(fs[i], fs[1 - i], i, rng, say, 0.8, f"{verb(fs[i])} в обмін ударами")
        elif a == "guard":
            for i in (0, 1):
                heal = fs[i].max_hp * 0.06
                fs[i].hp = min(fs[i].max_hp, fs[i].hp + heal)
            say(-1, f"🛡 Обоє чекають на удар і переводять подих: +{fs[0].max_hp * 0.06:.0f} і +{fs[1].max_hp * 0.06:.0f}")
        else:
            luck = [fs[i].crit + fs[i].dodge + rng.random() * 0.3 for i in (0, 1)]
            w = 0 if luck[0] >= luck[1] else 1
            say(1 - w, f"🎭 Обоє хитрують, але {fs[w].name} хитрує краще")
            _land(fs[w], fs[1 - w], w, rng, say, 0.9, "обводить суперника", pierce=True)
        return
    w = 0 if BEATS[a] == b else 1
    me, foe, lose = fs[w], fs[1 - w], 1 - w
    if kinds[w] == "strike":      # strike beats trick
        if plain[lose]:
            say(lose, f"🎭 {foe.name} {foe.g('задумав', 'задумала')} хитрість, але не встигає")
        if plain[w]:
            _land(me, foe, w, rng, say, 1.15, f"{verb(me)} на випередження")
    elif kinds[w] == "guard":     # guard beats strike
        if plain[lose]:
            _land(foe, me, lose, rng, say, 0.2, f"{verb(foe)} у блок")
        _land(me, foe, w, rng, say, 1.0, "відповідає контрударом")
    else:                         # trick beats guard
        if plain[lose]:
            say(lose, f"🛡 {foe.name} закривається, але удару нема")
        _land(me, foe, w, rng, say, 1.1, "заходить збоку повз захист", pierce=True, crit=0.15)


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


# --- the arena as a part of life: rank, record, rewards --------------------------------------------------------
RANKS = [(1300, "Легенда арени"), (1150, "Гроза району"), (1050, "Боєць"), (0, "Новачок")]   # by Elo, highest first
ACH_WINS = {5: "Бійцівський клуб", 20: "Гроза району", 50: "Непереможний"}
ARENA_FLAGS = ("arena_vet", "arena_champ")   # set by the engine below; content/arena.py events ask for them
FAME_WIN, FAME_TITLE = 1, 5     # fame (life stat: from tier 2 it pays «реклама» daily) per win / per tournament title


def rank(p: "E.Pet") -> str:
    """Arena rank by Elo: Новачок < 1050 <= Боєць < 1150 <= Гроза району < 1300 <= Легенда арени (shown as «🥊 Боєць»)."""
    elo = float(p.flags.get("elo", 1000))
    return next(name for floor, name in RANKS if elo >= floor)


def _plural(n: int, one: str, few: str, many: str) -> str:
    return one if n % 10 == 1 and n % 100 != 11 else few if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else many


def next_goal(p: "E.Pet") -> tuple[int, str] | None:
    """(wins left, achievement) for the next arena achievement, or None when they are all won."""
    wins = int(p.flags.get("wins", 0))
    return next(((t - wins, name) for t, name in sorted(ACH_WINS.items()) if t > wins), None)


def record(p: "E.Pet") -> str:
    """«🥊 4–1 · ще 1 перемога до «Бійцівський клуб»»."""
    line = f"🥊 {int(p.flags.get('wins', 0))}–{int(p.flags.get('losses', 0))}"
    goal = next_goal(p)
    if goal:
        line += f" · ще {goal[0]} {_plural(goal[0], 'перемога', 'перемоги', 'перемог')} до «{goal[1]}»"
    return line


def _pretty(note: str) -> str:
    """«😊+10» → «😊 +10», «❤️-8» → «❤️ −8» (notes of `apply` are tight)."""
    if " " in note:
        return note
    for i, ch in enumerate(note):
        if ch in "+-" and i and note[i + 1:i + 2].isdigit():
            return f"{note[:i]} {note[i:].replace('-', '−')}"
    return note


def aftermath(win: "E.Pet", lose: "E.Pet", rng: random.Random, surrender: bool = False) -> tuple[list[str], list[str]]:
    """Non-lethal consequences of a battle: rating, XP, mood, strength, fame for the winner; mood and health for the
    loser (a fighter who surrendered keeps the health). Returns the effect notes (winner, loser)."""
    delta = update_elo(win, lose)
    wn = win.apply(dict(mood=10, xp=8, str=0.5, fame=FAME_WIN), None, rng)
    ln = lose.apply(dict(mood=-10, xp=3) if surrender else dict(mood=-10, health=-8, xp=3), None, rng)
    win.note("battle", f"🥊 {win.name} {win.g('переміг', 'перемогла')} {inflect(lose.name, "acc", lose.gender)} (рейтинг +{delta})")
    lose.note("battle", f"🥊 {lose.name} {lose.g('програв', 'програла')} {inflect(win.name, "dat", win.gender)} (рейтинг −{delta})")
    if win.flags["wins"] in ACH_WINS:
        win.ach(ACH_WINS[win.flags["wins"]])
    if win.flags["wins"] >= 5:
        win.flags["arena_vet"] = 1   # opens the events of a known fighter (content/arena.py)
    nbsp = "\u00a0"
    pre = lambda p, d, xp: [f"🏅 Elo {d:+d} ({int(p.flags['elo']):,})".replace("-", "−").replace(",", nbsp), f"⭐ +{xp} XP"]  # noqa: E731
    return (pre(win, delta, 8) + [_pretty(n) for n in wn],
            pre(lose, -delta, 3) + [_pretty(n) for n in ln] + (["🏳 без травм"] if surrender else []))


def crown(champ: "E.Pet", prize: int, rng: random.Random) -> list[str]:
    """A tournament title: the prize, the golden crown, charisma, fame, and the flag that opens the champion's events."""
    notes = champ.apply(dict(money=prize, item="crown@9", mood=30, xp=40, cha=2, fame=FAME_TITLE), None, rng)
    champ.ach("Чемпіон турніру")
    champ.flags["titles"] = champ.flags.get("titles", 0) + 1
    champ.flags["arena_champ"] = 1
    return notes


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
