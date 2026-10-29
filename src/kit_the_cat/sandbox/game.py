"""Sandbox: the pet game without Telegram. Same engine, content and sprites; plus NPCs.

One sandbox "chat" (SANDBOX) holds your pets (owners 1..9, switch between them to play as different people)
and NPC neighbours (owners ≥ 100) that live on their own. Time is game time: engine.clock = real time + offset.
There is no time button: every action costs hidden life time (engine), and the world moves on by a matching
amount (`_pass`): salaries, NPC lives, holidays by date, world events. Only the egg has a one-time «🐣 Вилупити».
"""
import asyncio
import random
import time
from dataclasses import asdict

from .. import battle as B
from .. import engine as E
from .. import sprites
from ..content.economy import FOOD, JOBS
from ..storage import MemoryStore

SANDBOX = -777
NPC_BASE = 100
HUMANS = {1: "Ти", 2: "Друг", 3: "Сусідка"}
NPC_NAMES = ["Тьотя Валя", "Дядько Толік", "Кума Оксана", "Петрович", "Студент Діма", "Баба Галя", "Айтішник Ігор",
             "Бариста Соня", "Таксист Вітя", "Вчителька Ніна"]


class Sandbox:
    def __init__(self, db: MemoryStore, seed: int | None = None):
        self.db = db
        self.rng = random.Random(seed)
        self.offset = 0.0
        self.lock = asyncio.Lock()
        self.world_feed: list[str] = []
        E.clock = lambda: time.time() + self.offset

    # --- persistence ---------------------------------------------------------------------------
    async def init(self) -> None:
        st = await self.db.pet_chat(SANDBOX)
        self.offset = float(st.get("sandbox_offset", 0.0))
        self.world_feed = st.get("sandbox_feed", [])

    async def _state(self) -> dict:
        return E.chat_state(await self.db.pet_chat(SANDBOX))

    async def _save_state(self, st: dict) -> None:
        st["sandbox_offset"], st["sandbox_feed"] = self.offset, self.world_feed[-30:]
        await self.db.set_pet_chat(SANDBOX, st)

    async def pets(self, tick: bool = True) -> list[E.Pet]:
        pets = [E.Pet.from_dict(d) for d in await self.db.chat_pets(SANDBOX)]
        if tick:
            for p in pets:
                p.tick(rng=self.rng)
        return pets

    async def pet(self, owner: int, tick: bool = True) -> E.Pet | None:
        return next((p for p in await self.pets(tick) if p.owner_id == owner), None)

    async def save(self, *pets: E.Pet | None) -> None:
        pets = [p for p in pets if p]
        await self.db.save_pets([p.to_dict() for p in pets])
        for p in pets:
            p.log = []

    # --- views -----------------------------------------------------------------------------------
    async def view(self, owner: int) -> dict:
        async with self.lock:
            pets = await self.pets()
            await self.save(*pets)
        p = next((x for x in pets if x.owner_id == owner), None)
        names = {x.pid: x.name for x in pets if x.state != "dead"}
        st = await self._state()
        out = dict(owner=owner, owner_name=HUMANS.get(owner, f"Гравець {owner}"), clock=E.kyiv().strftime("%d.%m.%Y %H:%M"),
                   offset_days=round(self.offset / 86400, 2), species=[(s, E.SPECIES_EMOJI.get(s, "🐾"),
                                                                            E.SPECIES_NAME.get(s, s)) for s in sprites.SPECIES],
                   pet=None, players=[], world=None, world_feed=self.world_feed[-8:][::-1])
        for x in sorted(pets, key=lambda x: x.owner_id):
            out["players"].append(dict(owner=x.owner_id, owner_name=x.owner_name, name=x.name, state=x.state,
                                       stage=E.STAGES.get(x.stage, ""), npc=x.owner_id >= NPC_BASE,
                                       emoji=E.SPECIES_EMOJI.get(x.species, "🥚"),
                                       status=(p.status.get(x.pid, "") if p and x is not p else ""),
                                       rel=round(p.rel.get(x.pid, 0)) if p and x is not p else 0))
        w = st.get("world")
        if w and not w.get("closed"):
            out["world"] = dict(id=w["id"], title=E.WORLD[w["key"]]["title"], text=E.WORLD[w["key"]]["text"],
                                button=E.WORLD[w["key"]]["button"], claimed=len(w["claimed"]),
                                n=E.WORLD[w["key"]]["n"], results=w["results"][-5:], mine=owner in w["claimed"])
        if not p:
            return out
        out["pet"] = dict(
            name=p.name, state=p.state, stage=E.STAGES.get(p.stage, ""), card=E.card(p, names),
            stats={k: round(getattr(p, k)) for k in E.STATS}, money=int(p.money), level=p.level,
            age=round(p.age_days, 1), years=int(p.years),
            life=[dict(key=k, icon=v[0], name=v[1], value=round(p.life.get(k, 0)), tier=p.tier_name(k)[2:])
                  for k, v in E.LIFE.items()],
            money_tier=p.tier_name("money"),
            casino=[dict(id=k, name=E.CASINO[k][0], lo=E.CASINO[k][2], hi=min(E.CASINO[k][3], int(p.money)))
                    for k in E.casino_venues(p)],
            role=E.ROLES[p.role]["name"] if p.role in E.ROLES else "", job=JOBS[p.job]["name"] if p.job in JOBS else "",
            traits={E.TRAITS[t]: round(p.traits.get(t, 0), 1) for t in p.top_traits()},
            skills={k: round(p.skills.get(k, 0)) for k in E.SKILLS}, jailed=p.jailed, pending=None,
            genes=sprites.describe(p.genome), dna=sprites.dna_code(p.genome), rarity=sprites.rarity(p.genome)[1],
            gen=p.gen, dynasty=p.dynasty, achievements=p.achievements[-12:], heir=bool(p.heir), look=_look_key(p),
            persona={k: p.persona.get(k, "") for k in ("temper", "dream", "fear")}, emoji=E.SPECIES_EMOJI.get(p.species, "🐾"),
            perk=E.perk_text(p), goal_step=p.goal_step(), dream_done=bool(p.flags.get("dream_done")),
            power={k: round(p.skill(k)) for k in E.SKILLS},
            egg_left=max(0, round((E.EGG_HOURS * E.hour() - (E.now() - p.born)) / 60)) if p.state == "egg" else 0,
            cause=p.cause,
            summary=E.life_summary(p, {x.pid: x.name for x in pets}) if p.state == "dead" else None,
        )
        e = E.EVENTS.get(p.pending.get("id", "")) if p.pending else None
        if e:
            other = next((x for x in pets if x.pid == p.pending.get("other")), None)
            out["pet"]["pending"] = dict(
                id=e.id, text=p.fmt(e.text, other), other=other.name if other else "",
                twist=E.is_twist_event(e), mode=p.pending.get("mode", ""),
                choices=[dict(i=i, label=p.button(e, i, other), chance=p.chance(c)) for i, c in p.options(e, other)])
        rows = await self.db.pet_log(SANDBOX, owner, p.gen, 40)
        out["journal"] = [dict(ts=E.kyiv(r["ts"]).strftime("%d.%m %H:%M"), kind=r["kind"], text=r["text"])
                          for r in rows][::-1]
        return out

    # --- pet lifecycle ---------------------------------------------------------------------------
    async def create(self, owner: int, species: str) -> str:
        if species not in sprites.SPECIES:
            return "Невідомий вид"
        async with self.lock:
            pets = await self.pets()
            old = next((x for x in pets if x.owner_id == owner), None)
            if old and old.state != "dead":
                return "У тебе вже є пет"
            p = E.new_pet(SANDBOX, owner, HUMANS.get(owner, f"Гравець {owner}"), species,
                          [x for x in pets if x.owner_id != owner], self.rng)
            if old:
                p.gen = old.gen + 1
            await self.save(p)
        return "🥚 Яйце знесено! Коли будеш готовий, тисни «🐣 Вилупити»."

    async def hatch(self, owner: int) -> str:
        async with self.lock:
            p = await self.pet(owner)
            if not p or p.state != "egg":
                return "Нема що вилуплювати"
            p.hatch(E.now())
            await self.save(p)
        return f"🐣 Вилупився {p.name}! Характер: {p.persona.get('temper', '')}. Мрія: {p.persona.get('dream', '')}."

    async def _pass(self, years: float) -> None:
        """The world moves on while your pet lives: a few hours for a small thing, up to a day and a half."""
        await self.advance(min(36.0, 3 + 12 * years), auto_me=False)

    async def _timed(self, owner: int, coro):
        """Run an action and let the world move on by the life time it cost the pet (hidden from the player)."""
        p0 = await self.pet(owner, tick=False)
        y0 = p0.years if p0 else 0.0
        out = await coro
        p1 = await self.pet(owner, tick=False)
        if p1 and p1.alive and p1.years > y0:
            await self._pass(p1.years - y0)
        return out

    async def heir(self, owner: int) -> str:
        async with self.lock:
            pets = await self.pets()
            old = next((x for x in pets if x.owner_id == owner), None)
            if not old or old.state != "dead":
                return "Пет ще живий"
            partner = None
            if old.partner and not old.heir:
                po = next((x for x in pets if x.pid == old.partner), None)
                partner = po.genes if po else None
            p = E.new_pet(SANDBOX, owner, old.owner_name, old.species, [x for x in pets if x.owner_id != owner],
                          self.rng, predecessor=old, partner_genes=partner)
            await self.save(p)
        return f"👑 {p.dynasty} продовжується! Покоління {p.gen}. Спадок: {int(p.money)} ₴"

    async def care(self, owner: int, action: str, actor_id: int | None = None) -> str:
        if action not in E.CARE:
            return "Невідома дія"
        actor_id = actor_id or owner
        async with self.lock:
            pets = await self.pets()
            p = next((x for x in pets if x.owner_id == owner), None)
            if not p or not p.alive:
                return "Нема кого доглядати"
            if p.jailed and action != "pat":
                return "⛓ Пет за ґратами"
            left = p.cooldown_left(actor_id, action, E.CARE[action][2])
            if left > 0:
                return "Лікар щойно був. Спробуй трохи згодом." if action == "heal" else "Зарано, дай йому перепочити"
            by_owner = actor_id == owner
            actor = None if by_owner else next((x for x in pets if x.owner_id == actor_id and x.alive), None)
            text, notes = E.care(p, action, self.rng, actor, by_owner, HUMANS.get(actor_id, "Гість"))
            p.mark_cool(actor_id, action)
            await self.save(p, actor)
        return f"{text}\n{' · '.join(notes)}"

    async def feed(self, owner: int, food: str) -> str:
        if food not in FOOD:
            return "Такої їжі нема"
        async with self.lock:
            p = await self.pet(owner)
            if not p or not p.alive:
                return "Нема кого годувати"
            r = E.feed(p, food, self.rng, p)
            if isinstance(r, str):
                return r
            await self.save(p)
        return f"{r[0]}\n{' · '.join(r[1])}"

    async def casino(self, owner: int, venue: str, stake: int) -> str:
        async with self.lock:
            p = await self.pet(owner)
            if not p:
                return "Спершу заведи пета"
            r = E.casino(p, venue, stake, self.rng)
            if isinstance(r, str):
                return r
            await self.save(p)
        return f"{E.CASINO[venue][0]}: {r[0]}\n{' · '.join(r[1])}"

    def foods(self, p_role: str = "") -> list[dict]:
        return [dict(id=k, name=v[0], price=v[1]) for k, v in FOOD.items()
                if not (k in E.ROLE_FOOD and E.ROLE_FOOD[k] != p_role)]

    # --- adventures ------------------------------------------------------------------------------
    async def adventure(self, owner: int, kind: str = "", with_owner: int = 0) -> str:
        """kind '' = any, 'date' / 'fight' = with a chosen pet."""
        async with self.lock:
            pets = await self.pets()
            p = next((x for x in pets if x.owner_id == owner), None)
            if not p or not p.alive:
                return "Пригоди — для живих 🪦"
            if p.pending:
                return "Спершу дорозв'яжи поточну пригоду"
            if kind:
                other = next((x for x in pets if x.owner_id == with_owner and x.alive and x is not p), None)
                if not other:
                    return "Обери живого пета-сусіда"
                e, other = p.pick_event([other], self.rng, kind)
            else:
                e, other = p.pick_event(pets, self.rng)
            if not e:
                return "Сьогодні нічого не трапилось. Навіть дивно."
            p.start(e, other, "manual")
            await self.save(p)
        return "🎲 Пригода!"

    async def choose(self, owner: int, idx: int | None) -> dict:
        async with self.lock:
            pets = await self.pets()
            p = next((x for x in pets if x.owner_id == owner), None)
            if not p or not p.pending:
                return dict(error="Нема активної пригоди")
            e = E.EVENTS.get(p.pending.get("id", ""))
            if not e:
                p.pending = {}
                await self.save(p)
                return dict(error="Пригода зникла")
            other = next((x for x in pets if x.pid == p.pending.get("other")), None)
            if idx is None or idx not in {i for i, _ in p.options(e, other)}:
                idx, _ = p.auto_choice(e, other, self.rng)
            text = p.fmt(e.text, other)
            res = p.resolve(e, idx, other, self.rng)
            await self.save(p, other)
        if not res.died:
            await self._pass(res.time)
        r = asdict(res)
        r.pop("time")  # the player never learns how much of the life a decision took
        r.update(event=text, other=other.name if other else "", name=p.name, cause=p.cause if res.died else "")
        return r

    # --- wardrobe / shop / homes / jobs ----------------------------------------------------------
    async def wardrobe(self, owner: int) -> list[dict]:
        p = await self.pet(owner, tick=False)
        eq = set(p.equipped.values()) if p else set()
        return [dict(i=i, name=E.item_name(it), slot=E.item_slot(it), on=it in eq) for i, it in enumerate(p.items if p else [])]

    async def equip(self, owner: int, i: int) -> str:
        async with self.lock:
            p = await self.pet(owner)
            if not p or i >= len(p.items):
                return "Цієї речі нема"
            it = p.items[i]
            slot = E.item_slot(it)
            if p.equipped.get(slot) == it:
                p.equipped.pop(slot, None)
                msg = f"Знято: {E.item_name(it)}"
            else:
                p.equipped[slot] = it
                msg = f"Одягнено: {E.item_name(it)}"
            await self.save(p)
        return msg

    def stock(self) -> list[dict]:
        day = E.kyiv().strftime("%Y-%m-%d")
        return [dict(i=i, **{k: s[k] for k in ("name", "price", "kind")}) for i, s in enumerate(E.shop_stock(SANDBOX, day))]

    async def buy(self, owner: int, i: int) -> str:
        stock = E.shop_stock(SANDBOX, E.kyiv().strftime("%Y-%m-%d"))
        if i >= len(stock):
            return "Товар скінчився"
        async with self.lock:
            p = await self.pet(owner)
            if not p or not p.alive:
                return "Мертвим знижок нема"
            ok, text = E.buy(p, stock[i], self.rng)
            if ok:
                p.spend("1d", self.rng)  # a trip to the bazaar
                await self.save(p)
        return text

    async def homes(self, owner: int) -> list[dict]:
        p = await self.pet(owner, tick=False)
        return [dict(i=i, name=E.bg_name(h), here=h == p.home) for i, h in enumerate(p.homes)] if p else []

    async def move(self, owner: int, i: int) -> str:
        async with self.lock:
            p = await self.pet(owner)
            if not p or i >= len(p.homes):
                return "Нема такого дому"
            p.home = p.homes[i]
            p.spend("2w", self.rng)  # boxes, movers, a new neighbour with a drill
            await self.save(p)
        return f"🚚 Переїзд: {E.bg_name(p.home)}"

    async def jobs(self, owner: int) -> list[dict]:
        p = await self.pet(owner, tick=False)
        return [dict(id=j, name=JOBS[j]["name"], pay=JOBS[j]["pay"]) for j in E.job_offers(p)] if p else []

    async def apply_job(self, owner: int, jid: str) -> str:
        async with self.lock:
            p = await self.pet(owner)
            if not p or jid not in E.job_offers(p):
                return "Вакансія закрита"
            if p.flags.get("_jobday") == E.game_day():
                return "Сьогодні вже була співбесіда. Спробуй після кількох пригод."
            p.flags["_jobday"] = E.game_day()
            ok, text, notes = E.apply_job(p, jid, self.rng)
            await self.save(p)
        return f"{text}\n{' · '.join(notes)}"

    async def quit_job(self, owner: int) -> str:
        async with self.lock:
            p = await self.pet(owner)
            if not p or not p.job:
                return "Ти й так вільний"
            p.apply({"job": "", "mood": 10, "cha": 1}, None, self.rng)
            await self.save(p)
        return "🚪 Звільнився. Свобода! (і голод)"

    async def rename(self, owner: int, name: str) -> str:
        name = "".join(ch for ch in name if ch.isprintable() and ch not in "<>").strip()[:24]
        if not name:
            return "Порожнє ім'я"
        async with self.lock:
            p = await self.pet(owner)
            if not p:
                return "Нема пета"
            p.name = name
            await self.save(p)
        return f"Тепер це {name}"

    # --- NPCs, world, time -----------------------------------------------------------------------
    async def add_npcs(self, n: int) -> str:
        async with self.lock:
            pets = await self.pets()
            used = {x.owner_id for x in pets}
            added = 0
            for oid in range(NPC_BASE, NPC_BASE + 200):
                if added >= n:
                    break
                if oid in used:
                    continue
                p = E.new_pet(SANDBOX, oid, self.rng.choice(NPC_NAMES), self.rng.choice(sprites.SPECIES), pets, self.rng)
                p.hatch(E.now())
                pets.append(p)
                await self.save(p)
                added += 1
        return f"🏘 Заселилось сусідів: {added}"

    async def world(self, key: str = "") -> str:
        async with self.lock:
            pets = await self.pets()
            st = await self._state()
            key = key if key in E.WORLD else self.rng.choice(sorted(E.WORLD))
            affected = E.world_start(key, pets, self.rng)
            st["world"] = dict(key=key, id=int(E.now()) % 2_000_000_000, claimed=[], results=[], msg=0,
                               until=E.now() + 3600, affected=affected)
            self.world_feed.append(f"{E.kyiv():%d.%m %H:%M} {E.WORLD[key]['title']}")
            # NPCs rush in too
            for p in pets:
                if p.owner_id >= NPC_BASE and p.alive and self.rng.random() < 0.4 and \
                        len(st["world"]["claimed"]) < E.WORLD[key]["n"] - 1:
                    text, notes, _ = E.world_claim(p, key, self.rng)
                    st["world"]["claimed"].append(p.owner_id)
                    st["world"]["results"].append(text)  # world texts already name the pet
            await self.save(*pets)
            await self._save_state(st)
        return E.WORLD[key]["title"]

    async def claim(self, owner: int) -> str:
        async with self.lock:
            st = await self._state()
            w = st.get("world")
            if not w or w.get("closed"):
                return "Подія вже закінчилась"
            if owner in w["claimed"]:
                return "Ти вже там був 🙃"
            p = await self.pet(owner)
            if not p or not p.alive or p.stage < 1:
                return "Потрібен живий пет"
            text, notes, twist = E.world_claim(p, w["key"], self.rng)
            w["claimed"].append(owner)
            w["results"].append(text)
            if len(w["claimed"]) >= E.WORLD[w["key"]]["n"]:
                w["closed"] = True
            await self.save(p)
            await self._save_state(st)
        return f"{'🌀 ' if twist else ''}{text}\n{' '.join(notes)}"

    def _autocare(self, p: E.Pet) -> None:
        """Food, washing and sleep are automatic now; a reasonable owner only takes a sick pet to the doctor."""
        if p.health < 40:
            E.care(p, "heal", self.rng)

    async def advance(self, hours: float, auto_me: bool = True, care_me: bool = False) -> dict:
        """Fast-forward game time hour by hour: ageing, salaries, NPC lives, your pet's auto-decisions, world events."""
        steps = max(1, int(round(hours)))
        summary = dict(hours=steps, events=0, deaths=[], world=[])
        async with self.lock:
            for _ in range(steps):
                self.offset += 3600 / E.SPEED
                pets = await self.pets()
                st = await self._state()
                gd = E.game_day()
                if st.get("gday") != gd:
                    if st.get("gday"):
                        E.chat_daily(pets, self.rng)
                    st["gday"] = gd
                E.mourn(pets)
                t = E.now()
                for p in pets:
                    if not p.alive or p.stage < 1:
                        continue
                    if p.owner_id >= NPC_BASE or care_me:
                        self._autocare(p)
                    if p.owner_id < NPC_BASE and not auto_me:
                        continue  # your pets only live through you
                    if p.pending and t - p.pending.get("ts", t) > E.BUDGET.decide_hours * 3600:
                        e = E.EVENTS.get(p.pending.get("id", ""))
                        other = next((x for x in pets if x.pid == p.pending.get("other")), None)
                        if e:
                            idx, _ = p.auto_choice(e, other, self.rng)
                            p.resolve(e, idx, other, self.rng)
                            summary["events"] += 1
                        p.pending = {}
                        continue
                    if p.pending or (p.next_ev and p.next_ev > t):
                        if not p.next_ev:
                            p.next_ev = t + self.rng.uniform(*E.BUDGET.every) * E.hour()
                        continue
                    if p.owner_id < NPC_BASE and auto_me and steps <= 12:
                        e, other = p.pick_event(pets, self.rng)  # short skips: an adventure waits for you
                        if e:
                            p.start(e, other, "auto")
                        continue
                    if E.live_silently(p, pets, self.rng):
                        summary["events"] += 1
                w = st.get("world")
                if w and E.now() > w.get("until", 0):
                    st["world"] = None
                if not st.get("world") and sum(p.alive for p in pets) >= 3 and self.rng.random() < 1 / 30:
                    key = self.rng.choice(sorted(E.WORLD))
                    affected = E.world_start(key, pets, self.rng)
                    st["world"] = dict(key=key, id=int(t) % 2_000_000_000, claimed=[], results=[], msg=0,
                                       until=t + 3600, affected=affected)
                    self.world_feed.append(f"{E.kyiv():%d.%m %H:%M} {E.WORLD[key]['title']}")
                    summary["world"].append(E.WORLD[key]["title"])
                E.mourn(pets)
                for p in pets:
                    if p.state == "dead" and p.died >= t - 3600:
                        summary["deaths"].append(f"{p.name}: {p.cause}")
                await self.save(*pets)
                await self._save_state(st)
        return summary

    async def reset(self) -> str:
        async with self.lock:
            await self.db.delete_chat(SANDBOX)
            self.offset, self.world_feed = 0.0, []
        return "🧹 Пісочницю очищено"

    # --- battles & tournament -------------------------------------------------------------------
    async def spar(self, owner: int, foe: int, strategy: str) -> dict:
        """Friendly 1-on-1. Non-lethal; rating counts."""
        async with self.lock:
            pets = await self.pets()
            a = next((x for x in pets if x.owner_id == owner), None)
            b = next((x for x in pets if x.owner_id == foe), None)
            if not a or not b or a is b:
                return dict(error="Обери суперника")
            if not B.eligible(a) or not B.eligible(b):
                return dict(error="Битися можуть живі пети від підлітка, не в тюрмі й не в лікарні")
            res = self._battle(a, b, strategy, B.auto_strategy(b, self.rng))
            await self.save(a, b)
        return res

    def _battle(self, a: E.Pet, b: E.Pet, sa: str, sb: str) -> dict:
        fa, fb = B.Fighter.of(a, sa), B.Fighter.of(b, sb)
        chance = B.win_chance(fa, fb)
        r = B.fight(fa, fb, self.rng)
        w, l = (a, b) if r.winner == 0 else (b, a)
        wn, ln = B.aftermath(w, l, self.rng)
        return dict(owners=[a.owner_id, b.owner_id], winner=[a.owner_id, b.owner_id][r.winner], rounds=r.rounds,
                    log=r.log, fighters=r.fighters, text=r.text, chance=round(chance, 3),
                    notes={w.owner_id: wn, l.owner_id: ln})

    async def tour_view(self, owner: int) -> dict:
        st = await self._state()
        t = st.get("tour")
        pets = {p.owner_id: p for p in await self.pets(tick=False)}
        me = pets.get(owner)
        out = dict(tour=None, eligible=sum(B.eligible(p) for p in pets.values()),
                   history=st.get("tour_hist", [])[-5:][::-1], strategies=[(k, *v) for k, v in B.STRATEGIES.items()],
                   my_strategy=(t or {}).get("strategies", {}).get(str(owner), ""),
                   me=dict(elo=me.flags.get("elo", 1000), wins=me.flags.get("wins", 0),
                           losses=me.flags.get("losses", 0), money=int(me.money)) if me else None)
        if not t:
            return out

        def who(o: int) -> dict | None:
            p = pets.get(o)
            if not o or not p:
                return None
            f = B.Fighter.of(p)
            return dict(owner=o, name=p.name, emoji=E.SPECIES_EMOJI.get(p.species, "🐾"), elo=p.flags.get("elo", 1000),
                        power=f.power, npc=o >= NPC_BASE, mine=o == owner)
        rounds = []
        for ri, rnd in enumerate(t["rounds"]):
            ms = []
            for mi, (a, b) in enumerate(rnd):
                key = f"{ri}-{mi}"
                res = t["results"].get(key)
                bets = t["bets"].get(key, {})
                ms.append(dict(key=key, a=who(a), b=who(b), winner=res["winner"] if res else 0,
                               bye=bool(res and res.get("bye")), my_bet=bets.get(str(owner))))
            rounds.append(ms)
        nxt = self._next_match(t)
        cur = None
        if nxt:
            ri, mi = nxt
            a, b = t["rounds"][ri][mi]
            pa, pb = pets.get(a), pets.get(b)
            if pa and pb:
                ch = B.win_chance(B.Fighter.of(pa), B.Fighter.of(pb))
                cur = dict(key=f"{ri}-{mi}", a=who(a), b=who(b), chance=round(ch, 3),
                           odds=[round(0.9 / max(ch, 0.05), 2), round(0.9 / max(1 - ch, 0.05), 2)])
        out["tour"] = dict(id=t["id"], status=t["status"], rounds=rounds, current=cur, champion=t.get("champion"),
                           prize=t["prize"], last=t.get("last"))
        return out

    @staticmethod
    def _next_match(t: dict) -> tuple[int, int] | None:
        for ri, rnd in enumerate(t["rounds"]):
            for mi, (a, b) in enumerate(rnd):
                if f"{ri}-{mi}" not in t["results"]:
                    if ri > 0 and (not a or not b) and not Sandbox._feeders_done(t, ri, mi):
                        return None
                    return ri, mi
        return None

    @staticmethod
    def _feeders_done(t: dict, ri: int, mi: int) -> bool:
        return all(f"{ri - 1}-{2 * mi + k}" in t["results"] for k in (0, 1))

    async def tour_new(self) -> str:
        async with self.lock:
            st = await self._state()
            if st.get("tour") and st["tour"]["status"] == "running":
                return "Турнір уже йде"
            pets = [p for p in await self.pets() if B.eligible(p)]
            if len(pets) < 3:
                return "Потрібно хоча б 3 пети-підлітки й старші (🏘 сусіди дорослішають, поки ти граєш)"
            rounds = B.bracket(pets, self.rng)
            n = sum(1 for r in rounds[0] for o in r if o)
            st["tour"] = dict(id=int(E.now()), status="running", rounds=rounds, results={}, bets={}, strategies={},
                              prize=300 * n, champion=None, last=None)
            self._skip_byes(st["tour"], {p.owner_id: p for p in pets})
            await self._save_state(st)
        return f"🏆 Турнір на {n} бійців! Призовий фонд {300 * n} ₴"

    async def tour_strategy(self, owner: int, strategy: str) -> str:
        if strategy not in B.STRATEGIES:
            return "Невідома тактика"
        async with self.lock:
            st = await self._state()
            if not st.get("tour"):
                return "Турніру нема"
            st["tour"]["strategies"][str(owner)] = strategy
            await self._save_state(st)
        return f"Тактика на турнір: {B.STRATEGIES[strategy][0]}"

    async def tour_bet(self, owner: int, key: str, side: int, amount: int = 50) -> str:
        async with self.lock:
            st = await self._state()
            t = st.get("tour")
            if not t or t["status"] != "running":
                return "Турніру нема"
            nxt = self._next_match(t)
            if not nxt or f"{nxt[0]}-{nxt[1]}" != key:
                return "Ставки приймаються лише на поточний бій"
            pets = await self.pets()
            me = next((x for x in pets if x.owner_id == owner), None)
            ri, mi = nxt
            if not me or not me.alive:
                return "Ставити можна лише гаманцем свого живого пета"
            if owner in t["rounds"][ri][mi]:
                return "На свій бій ставити не можна — це договірняк 🤨"
            if str(owner) in t["bets"].get(key, {}):
                return "Ти вже поставив"
            if me.money < amount:
                return "Не вистачає грошей"
            a, b = t["rounds"][ri][mi]
            fa = B.Fighter.of(next(x for x in pets if x.owner_id == a))
            fb = B.Fighter.of(next(x for x in pets if x.owner_id == b))
            ch = B.win_chance(fa, fb)
            odds = round(0.9 / max(ch if side == 0 else 1 - ch, 0.05), 2)
            me.money -= amount
            t["bets"].setdefault(key, {})[str(owner)] = [side, amount, odds]
            await self.save(me)
            await self._save_state(st)
        return f"🎰 Ставка {amount} ₴ на {[fa.name, fb.name][side]} (×{odds})"

    def _skip_byes(self, t: dict, by: dict) -> None:
        """Resolve byes and walkovers until the next match has two fighters (or the bracket is done),
        so the arena always has a real match to show."""
        while (nxt := self._next_match(t)):
            ri, mi = nxt
            a, b = t["rounds"][ri][mi]
            ok_a, ok_b = bool(by.get(a) and B.eligible(by[a])), bool(by.get(b) and B.eligible(by[b]))
            if ok_a and ok_b:
                return
            win = a if ok_a else b if ok_b else 0
            key = f"{ri}-{mi}"
            t["results"][key] = dict(winner=win, bye=True)
            self._promote(t, ri, mi, win)
            self._refund(t, key, by)

    async def tour_next(self) -> dict:
        """Play the next match (byes and walkovers resolve instantly). Returns the battle or a status."""
        async with self.lock:
            st = await self._state()
            t = st.get("tour")
            if not t or t["status"] != "running":
                return dict(error="Турніру нема")
            pets = await self.pets()
            by = {p.owner_id: p for p in pets}
            while True:
                nxt = self._next_match(t)
                if not nxt:
                    break
                ri, mi = nxt
                key = f"{ri}-{mi}"
                a, b = t["rounds"][ri][mi]
                pa, pb = by.get(a), by.get(b)
                ok_a, ok_b = bool(pa and B.eligible(pa)), bool(pb and B.eligible(pb))
                if not (ok_a and ok_b):  # bye or walkover (pet died / jailed / in hospital)
                    win = a if ok_a else b if ok_b else 0
                    t["results"][key] = dict(winner=win, bye=True)
                    self._promote(t, ri, mi, win)
                    self._refund(t, key, by)
                    continue
                strat = t["strategies"]
                sa = strat.get(str(a)) or B.auto_strategy(pa, self.rng)
                sb = strat.get(str(b)) or B.auto_strategy(pb, self.rng)
                res = self._battle(pa, pb, sa, sb)
                res["key"], res["round"] = key, ri
                t["results"][key] = dict(winner=res["winner"])
                self._promote(t, ri, mi, res["winner"])
                res["bets"] = self._settle(t, key, 0 if res["winner"] == a else 1, by)
                t["last"] = key
                self._skip_byes(t, by)
                if not self._next_match(t):
                    res["champion"] = self._finish(t, by, st)
                await self.save(*pets)
                await self._save_state(st)
                return res
            champ = self._finish(t, by, st) if t["status"] == "running" else t.get("champion")
            await self.save(*pets)
            await self._save_state(st)
            return dict(done=True, champion=champ)

    @staticmethod
    def _promote(t: dict, ri: int, mi: int, win: int) -> None:
        if ri + 1 < len(t["rounds"]):
            t["rounds"][ri + 1][mi // 2][mi % 2] = win

    def _refund(self, t: dict, key: str, by: dict) -> None:
        for o, (side, amount, odds) in t["bets"].get(key, {}).items():
            if by.get(int(o)):
                by[int(o)].money += amount

    def _settle(self, t: dict, key: str, won_side: int, by: dict) -> list[str]:
        lines = []
        for o, (side, amount, odds) in t["bets"].get(key, {}).items():
            p = by.get(int(o))
            if not p:
                continue
            if side == won_side:
                pay = int(amount * odds)
                p.money += pay
                lines.append(f"✅ {p.name}: +{pay} ₴")
            else:
                lines.append(f"❌ {p.name}: −{amount} ₴")
        return lines

    def _finish(self, t: dict, by: dict, st: dict) -> dict | None:
        t["status"] = "done"
        final = t["rounds"][-1][0]
        champ_id = t["results"].get(f"{len(t['rounds']) - 1}-0", {}).get("winner") or final[0] or final[1]
        champ = by.get(champ_id)
        if not champ:
            return None
        second = next((o for o in final if o and o != champ_id), 0)
        champ.apply(dict(money=t["prize"], item="crown@9", mood=30, xp=40, cha=2), None, self.rng)
        champ.ach("Чемпіон турніру")
        champ.flags["titles"] = champ.flags.get("titles", 0) + 1
        champ.note("battle", f"🏆 {champ.name} — ЧЕМПІОН ТУРНІРУ! +{t['prize']} ₴ і золота корона")
        if by.get(second):
            s2 = by[second]
            s2.apply(dict(money=t["prize"] // 3, item="medal@11", xp=20), None, self.rng)
            s2.note("battle", f"🥈 {s2.name} — фіналіст турніру (+{t['prize'] // 3} ₴)")
        t["champion"] = dict(owner=champ_id, name=champ.name, emoji=E.SPECIES_EMOJI.get(champ.species, "🐾"))
        st.setdefault("tour_hist", []).append(f"{E.kyiv():%d.%m} 🏆 {champ.name} (з {len(t['rounds'][0]) * 2} учасників)")
        self.world_feed.append(f"{E.kyiv():%d.%m %H:%M} 🏆 Чемпіон турніру: {champ.name}")
        return t["champion"]

    async def fight_png(self, a: int, b: int) -> bytes | None:
        pets = {p.owner_id: p for p in await self.pets(tick=False)}
        if a not in pets or b not in pets:
            return None
        return await asyncio.to_thread(sprites.render_group, [pets[a].look("club"), pets[b].look("club")], "club", 2,
                                       "fight")

    # --- images ----------------------------------------------------------------------------------
    async def pet_gif(self, owner: int) -> bytes | None:
        p = await self.pet(owner, tick=False)
        return await asyncio.to_thread(sprites.render_gif, p.look()) if p else None

    async def event_png(self, owner: int) -> bytes | None:
        pets = await self.pets(tick=False)
        p = next((x for x in pets if x.owner_id == owner), None)
        e = E.EVENTS.get(p.pending.get("id", "")) if p and p.pending else None
        if not e:
            return None
        bg = e.bg if E.bg_ok(e.bg) else ""
        other = next((x for x in pets if x.pid == p.pending.get("other")), None)
        if other:
            bgx = E.scene(bg or p.home, p.flags)
            st = p.status.get(other.pid, "")
            between = ("heart" if st in ("crush", "partner") else "fight" if st in ("rival", "enemy")
                       else "broken" if st == "ex" else "chat")
            return await asyncio.to_thread(sprites.render_group, [p.look(bgx), other.look(bgx)],
                                           bgx if E.bg_ok(bgx) else "meadow", 2, between)
        return await asyncio.to_thread(sprites.render_png, p.look(bg))

    async def zoo_png(self) -> bytes | None:
        pets = [p for p in await self.pets(tick=False) if p.state != "dead"][:12]
        if not pets:
            return None
        return await asyncio.to_thread(sprites.render_group, [p.look() for p in pets], "meadow", 4, "",
                                       [p.name[:12] for p in pets])


def _look_key(p: E.Pet) -> str:
    """Changes whenever the sprite would change → the UI reloads the GIF only then."""
    return str(abs(hash(repr(p.look()))))
