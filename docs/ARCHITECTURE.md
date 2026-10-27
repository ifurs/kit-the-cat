# Architecture

Kit the Cat is a pure-Python life simulation. The core (`engine`, `content`, `sprites*`, `battle`, `storage`, `tz`)
uses only the standard library, so the same code runs in a Telegram bot, a local aiohttp sandbox and the browser
(Pyodide). Hosts own I/O: persistence, delivery, buttons, schedules.

```
                ┌──────────────── host (bot / sandbox / browser) ─────────────────┐
                │  storage (dicts)   scheduler (engine.plan)   UI (buttons, cards) │
                └──────┬──────────────────────┬──────────────────────┬────────────┘
                       │ Pet.from_dict/to_dict│ tick/pick/resolve     │ look() → sprites
   content/*.py ──► engine.EVENTS ──► engine.Pet ──────────────────► sprites.render_gif/png
   (DSL, dsl.py contract)               │  apply(fx) / meets(req)        frame_canvases (browser)
                                        └──► battle.Fighter / fight / bracket / Elo
```

## Modules

| Module | Responsibility |
|---|---|
| `engine.py` | `Pet` dataclass (a JSON document); ageing and decay in `tick()`; event choice (`pick_event`, weights by traits/`aff`, cooldowns, `once`); `resolve()` → `Result` (text, effects, twists); effects `apply()` and requirements `meets()` — the only implementation of the DSL; roles, world events, economy (`care`, `feed`, `buy`, jobs); `plan()` decides what a chat sees next within `BUDGET` |
| `content/dsl.py` | `ev/ch/o` builders and the contract: `KNOWN_FX`, `KNOWN_REQ`, `ROLES`. The docstring is the human reference (rendered into `docs/DSL.md`) |
| `content/{life,daily,chains,jobs,species,social,twists}.py` | 313 events, aggregated in `content/events.py` (`ALL`) |
| `content/economy.py` | `FOOD`, `JOBS`, `EDUCATION`, prices |
| `content/persona.py` | temperaments, dreams, fears, quirks (names/text for `{dream}` etc.) |
| `content/validate.py` | contract check: unknown keys, label/text lengths, duplicate ids |
| `sprites_core.py` | 48×48 `Canvas`, shape primitives (`ellipse`, `poly`, `rect`), colour helpers, `Body` geometry |
| `sprites.py` | `Genome` (genes → visible parts), `unique_genome` (min distance 4 within a chat), `breed`, species drawing, roles, fixed `ITEMS` (`it_*` draw functions), tints, eggs, graves, GIF/PNG, group scenes |
| `sprites_gen.py` | generated items `gen:<slot>:<code>` — kinds × colours × patterns × ornaments, with Ukrainian names in correct grammatical gender |
| `sprites_bg.py` | backgrounds and modifiers (`farm~winter~snow`) |
| `battle.py` | `Fighter` from a pet (species passives, trait specials, role ultimates), `fight`, `win_chance`, `update_elo`, `bracket` |
| `storage.py` | `MemoryStore` — reference implementation of the storage contract ([INTEGRATION.md](INTEGRATION.md)) |
| `tz.py` | Kyiv time zone (zoneinfo, or a built-in rule where tzdata is missing) |
| `sandbox/` | `Sandbox` game service over a store (NPC neighbours, autopilot care, tournaments), `api.dispatch` (HTTP-free), `server.py` (aiohttp), `static/index.html` |
| `web/` | browser build: `bridge.py` exposes `api.dispatch` to JS; `index.html` draws canvases; saves to localStorage |

## Data model

A pet is one dict (`Pet.to_dict()`): identity (`chat_id`, `owner_id`, `gen`), genome, stats/skills/traits, `flags`
(story chains; keys starting with `_` are engine-internal), relations (`rel`, `status` by pet id), items/equipment,
job/education/home, role, pending event, cooldowns, and a short `log` of new entries that the store moves out on save.
Unknown fields are ignored on load and missing ones get defaults, so documents survive upgrades.

## Time

Real time (`engine.clock`, patchable in tests) × `engine.SPEED` = game time. Pets decay per game hour (`DECAY`),
grow by days since hatching (`STAGE_AGE`), and die of neglect in ~3 days or of old age at ~24–36 days. Night and
seasons use the real Kyiv date.

## Randomness

Every engine call that rolls dice takes an explicit `random.Random`. Hosts pass their own (seeded in tests,
`scripts/balance.py`, and the sandbox), which makes runs reproducible.

## Invariants (tests guard them)

- Content uses only contract keys; the engine implements every contract key (`tests/test_dsl_contract.py`).
- Unknown requirement → event unavailable (fail closed).
- Partners are mutual and monogamous (`fix_partners`); romance respects `ROMANCE_MIN_STAGE`.
- No two pets in a chat look alike (`unique_genome`, `scripts/uniqueness.py`).
- The core imports with `python -I -S` (no third-party modules) — CI builds the browser tree and imports it.
