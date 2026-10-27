---
name: kit-balance
description: Measure and tune game balance of Kit the Cat — survival and death rates, neglect timing, money and salaries, skill-check success, event coverage, roles and jobs distribution, via the headless simulation scripts/balance.py and content_stats.py. Use whenever the user says the game is too hard/easy, pets die too fast/never die, money is broken, an event never shows up, a check is impossible, or asks to "simulate", "rebalance", "перевір баланс", tune numbers, or after any change to engine constants or many events.
---

# Balancing Kit the Cat

Balance is decided by numbers from simulations, not by feel. Measure first, change one thing, measure again.

## 1. Baseline

```bash
uv run python scripts/balance.py --pets 24 --days 40 --seed 1 --json <scratchpad>/before.json
uv run python scripts/balance.py --pets 24 --days 40 --seed 2      # a second seed: is it noise?
uv run python scripts/content_stats.py --gaps
```

`balance.py` runs the real sandbox: NPC owners on autopilot care, a `--neglect` share that never cares, heirs after
deaths. It prints each target as OK / WARN / FAIL (FAIL = exit 1):

| Metric | Target | Meaning |
|---|---|---|
| neglect_death_days | 2–5 | forgotten pet dies in ~3 days — harsh but fair |
| cared_alive_share | 75–100 % | cared pets mostly survive (old age ~24–36 days) |
| check_success | 45–70 % | dice checks hopeful, not trivial |
| event_coverage | ≥ 55 % | content actually fires in a 40-day run |
| money_median | 150–6000 ₴ | wallets of living pets |
| event_deaths_share | ≤ 15 % | deaths by events are rare and dramatic |

Plus: causes of death, roles, jobs, stage mix, never-fired events. Several seeds and `--days 60` before believing
a small difference; `--pets 60` for rare things (roles, chains).

## 2. Diagnose

- Never-fired events: check their `req=` (impossible combos, flag never set → `content_stats.py --strict`),
  weight `w=`, `season=` (real date!), `once=`. Chains and job events need adult pets with jobs — longer runs.
- Check success too low/high: `content_stats.py` warnings list the hardest checks; the formula is in
  `engine.Pet.chance` (and mirrored by `typical_chance()` in `scripts/content_stats.py` — keep them in sync).
- Deaths/neglect: `engine.DECAY`, `STARVE`, `EVENT_ENERGY`, lifespan in `new_pet`.
- Money: salaries in `content/economy.py` `JOBS`, shop prices, event `money=` outcomes (`content_stats.py` shows
  most used effects).
- Rare drama: `TWIST_TAIL`, `TWIST_DAILY`, `RESURRECT`, role chances in twist events.

## 3. Change and re-measure

Change the smallest lever (one constant or a handful of events), re-run the same seeds, compare with
`before.json`. Keep the old numbers in your report. If a target itself is wrong for the design (the user wants
a crueller game), change the target in `TARGETS` explicitly and say so.

Engine constant changes affect live pets in the bot — mention it; content number changes only affect new events.

## 4. Done

```bash
uv run pytest -q && uv run python scripts/content_stats.py --strict && uv run python scripts/balance.py
```

Report a before/after table of the metrics, what changed and why, and add a CHANGELOG line (Unreleased → Changed).
