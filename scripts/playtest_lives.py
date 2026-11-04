"""Play N whole pet lives through the sandbox (no LLM) and write one readable journal per life (docs/PLAYTEST.md).

    uv run python scripts/playtest_lives.py build/lives 100 8      # OUT_DIR [N=40] [WORKERS=8], ~2 min for 100
    uv run python scripts/playtest_checks.py build/lives --strict  # then the deterministic checks

Each life: own process (the sandbox moves the global game clock), own seed, species/gender/strategy rotate.
The journal has, per decision: the pet's state, the event (id + text), the open and 🔒 choices, the choice, the result,
and every journal line the pet got since the previous decision (daily life, neighbours, world).
"""
import asyncio
import random
import sys
from multiprocessing import Pool
from pathlib import Path

STRATS = ["auto", "random", "first", "last"]   # auto = the pet decides by its character
MAX_STEPS = 260


def run(i: int, out: str) -> str:
    from kit_the_cat import engine as E
    from kit_the_cat import sprites
    from kit_the_cat.sandbox.game import Sandbox
    from kit_the_cat.storage import MemoryStore

    species = sorted(sprites.SPECIES)[i % len(sprites.SPECIES)]
    gender = "mf"[(i // len(sprites.SPECIES)) % 2] if i % 3 else "mf"[i % 2]
    strat = STRATS[i % len(STRATS)]
    rng = random.Random(1000 + i)

    async def life() -> list[str]:
        store = MemoryStore()
        sb = Sandbox(store, seed=1000 + i)
        last = [0]

        def diary() -> list[str]:  # the sandbox moves p.log into the store on every save: read it from there
            rows = [r for r in store.logs if r["owner_id"] == 1 and r["id"] > last[0]]
            if rows:
                last[0] = rows[-1]["id"]
            return [f"  · [{r['kind']}] {r['text']}" for r in rows]
        await sb.init()
        await sb.create(1, species, gender)
        await sb.advance(3, auto_me=False, care_me=True)
        if (await sb.pet(1)).state == "egg":
            await sb.hatch(1)
        await sb.add_npcs(4)
        p = await sb.pet(1)
        lines = [f"# Життя {i:02d}: {p.name} ({species}, {'дівчинка' if p.gender == 'f' else 'хлопчик'}), "
                 f"стратегія вибору: {strat}",
                 f"Характер: {p.temper_name()} · мрія: {p.dream_text()} · боїться: {p.persona.get('fear', '')}", ""]
        diary()
        names = {}
        for step in range(1, MAX_STEPS + 1):
            p = await sb.pet(1)
            if not p or not p.alive:
                break
            pets = await sb.pets(tick=False)
            names = {x.pid: x.name for x in pets}
            lines += diary()
            if not p.pending:
                await sb.adventure(1)
                p = await sb.pet(1)
                if not p.pending:
                    await sb.advance(6, auto_me=False, care_me=True)
                    continue
            e = E.EVENTS.get(p.pending.get("id", ""))
            other = next((x for x in pets if x.pid == p.pending.get("other")), None)
            opts = [i2 for i2, _ in p.options(e, other)]
            partner = names.get(p.partner, "") if p.partner else ""
            lines.append("")
            lines.append(f"## Крок {step} · {int(p.years)} р. · {E.SPECIES_EMOJI.get(p.species, '')}{p.species} · {E.phase_name(p.phase(), p.gender)} · рів. {p.level} · "
                         f"💰{int(p.money)} · ❤️{int(p.health)} 😊{int(p.mood)} · робота: {p.job_name() if p.job else '—'}"
                         f" · роль: {p.role_name() if p.role else '—'} · пара: {partner or '—'} · дітей: {p.children}"
                         + (" · ⛓ у в'язниці" if p.jailed else ""))
            lines.append(f"ПОДІЯ [{e.id}]" + (f" з {other.name} ({'дівчинка' if other.gender == 'f' else 'хлопчик'}, "
                                             f"{int(other.years)} р., статус: {p.status.get(other.pid, '—')})" if other else "")
                         + f": {p.fmt(e.text, other)}")
            lines.append("ВАРІАНТИ: " + " | ".join(p.fmt(e.choices[k].label, other) for k in opts)
                         + "".join(f" | 🔒 {p.fmt(e.choices[k].label, other)} ({why})" for k, why in p.locked_why(e, other)))
            idx = (None if strat == "auto" else rng.choice(opts) if strat == "random"
                   else opts[0] if strat == "first" else opts[-1])
            res = await sb.choose(1, idx)
            if res.get("error"):
                lines.append(f"ПОМИЛКА: {res['error']}")
                break
            verdict = "" if res.get("ok") is None else (" ✅" if res["ok"] else " ❌")
            lines.append(f"ВИБІР: {res.get('label', '')}{verdict}")
            lines.append(f"РЕЗУЛЬТАТ: {res.get('text', '')}" + (f" · {' · '.join(res['notes'])}" if res.get("notes") else ""))
            if res.get("tail"):
                lines.append(f"ХВІСТ: {res['tail']}")
            await sb.advance(4, auto_me=False, care_me=True)
        p = await sb.pet(1)
        lines += diary()
        lines += ["", f"КІНЕЦЬ: стан {p.state}, {int(p.years)} р." + (f", причина: {p.cause}" if p.state == "dead" else "")]
        return lines

    lines = asyncio.run(life())
    path = Path(out) / f"life_{i:02d}.md"
    path.write_text("\n".join(lines) + "\n")
    return f"{path.name}: {len(lines)} lines, {lines[-1]}"


if __name__ == "__main__":
    out = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    w = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    Path(out).mkdir(parents=True, exist_ok=True)
    with Pool(w) as pool:
        for line in pool.starmap(run, [(i, out) for i in range(n)]):
            print(line)
