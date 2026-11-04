# Automated playtest: whole lives, then checks, then (optionally) an LLM read

The first run (2026-11-04, 0.21.0: 40 lives read by 20 Haiku agents, verified by Sonnet; then 2 × 100 lives with the
checks below) found ~14 root causes: alcohol offered to kids, romance across the teen/adult line, school for newborns,
«🔒 потрібно 0 ₴» in debt, «first meetings» with old friends, work events without a job, tails without an age. They are
fixed in 0.22.0; the checks keep them fixed.

## 1. Play lives (no LLM, ~2 min for 100)

```bash
uv run python scripts/playtest_lives.py build/lives 100 8        # OUT_DIR N WORKERS
```
One process per life (the sandbox moves the global clock). Species, gender and the choice strategy (auto = the pet's
character / random / first / last) rotate; 4 NPC neighbours. Each `build/lives/life_XX.md` has, per decision, the
pet's state (age, species, phase, level, money, health, mood, job, role, partner, kids), the event id and text, the
open and 🔒 choices, the choice and the result, and every diary line in between (pay, neighbours, world, tails).

## 2. Deterministic checks

```bash
uv run python scripts/playtest_checks.py build/lives --strict --examples 3
```
`--strict` fails on the exact checks (romance across the line, the debt lock text, «Покликати маму» for grown-ups,
fractional money). The word-based ones (alcohol under 18, school under 3, work words without a job, a «never met» event
with an acquaintance, lifespans over 105) are leads: read the examples. The static side of the same rules is
`scripts/integrity_audit.py --static` (grown-up words under 18 across events and tails, work words, school ages).

## 3. LLM read (optional, for things a regex can't see)

Cheap model per 2 journals (~30k tokens each), then a stronger model verifies every P1/P2 group against the journals
and the source and clusters them by root cause. Expect ~30–40 % precision from the cheap pass: the verification step is
not optional. Brief for the cheap pass (what to flag): age (kids offered alcohol, a job, a mortgage, marriage; grown-ups
sent to school), gender of the pet or the other pet, state contradictions (a spouse with «пара: —», work with «робота:
—»), relationships (an enemy treated as a best friend, «вперше зустрічає» twice), choice ↔ result, time & lifespan,
repetition (3+ times in a life or < 5 years apart), broken text (`{…}`, unresolved `|`, russisms).

Known false positives to tell it about:
- a header change without a diary line explaining it is still not a contradiction unless the diary is missing;
- the species may change (a tail «прокинувся іншим видом», a body swap): events of the new species are right;
- repeats 10+ years apart (social events may repeat twice per life on purpose);
- an amount in the text vs the note differs by < 25 % (the financial-literacy discount);
- fractional life-stat notes («📈+2.2»), builtin ids starting with `_` (`_date`, `_fight`), dark/absurd humour, the war
  context, fantasy roles — all by design;
- an NPC's age may drift a little against the pet's (NPCs pay the time of their own decisions).
