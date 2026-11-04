# Using kit-the-cat in your app

The Telegram bot «Кошеня» is the reference host; the sandbox (`kit_the_cat.sandbox.game.Sandbox`) is a smaller one
worth reading first.

## Install and pin

```bash
uv add "kit-the-cat[images] @ git+https://github.com/ifurs/kit-the-cat@v0.17.0"
```

Always pin a tag. Extras: `images` (Pillow, for GIF/PNG), `sandbox` (aiohttp server).

## Public API

Stable within a minor version (see [CONTRIBUTING.md](../CONTRIBUTING.md#versioning)):

- `engine`: `Pet` (`from_dict`, `to_dict`, `tick`, `pick_event`, `options`, `chance`, `start`, `auto_choice`,
  `resolve`, `look`, `fmt`, `give`, `cooldown_left`, `mark_cool`, `price`, `locked`, `called`), `new_pet`, `EVENTS`, `ROLES`, `WORLD`, `BUDGET`,
  `chat_state`, `plan`, `live_silently`, `care`, `feed`, `buy`, `shop_stock`, `job_offers`, `apply_job`,
  `fix_partners`, `mourn`, `chat_daily`, `world_start`, `world_claim`, `card`, `clock` (patchable), `SPEED`.
  Recurring characters (0.17): `Pet.cast` (a JSON dict inside the pet document, missing in old documents) and
  `Pet.cast_list()` — the people the pet knows (name, icon, bond, `state` here/away/gone) for a card or a keyboard
- `sprites`: `Look`, `render_gif`, `render_png`, `render_group`, `frame_canvases`, `item_name`, `item_slot`
- `card` (0.18): `render_life_card(pet.look(), engine.life_summary(pet, names), footer="")` → PNG bytes, a whole life on one
  picture (portrait, title, cause, facts, highlights, family, epitaph; 792 px wide, taller for a longer life). Pure
  stdlib — no Pillow, so it works in the browser build too. Send it as a document to keep the pixels sharp; as a photo
  Telegram recompresses it (still readable). `engine.life_summary` also works for a living pet (no cause line).
- `content.economy`: `FOOD`, `JOBS`, `EDUCATION`, `ITEM_SKILL`, `ITEM_SKILL_CAP`
- `battle`: `Fighter`, `fight` (+ `stop_at`, `FightState`, `resume`, `auto_tactic`), `win_chance`, `update_elo`, `aftermath`, `crown`, `rank`, `record`, `eligible`, `bracket`, `item_stats`, `item_label`

Progress you can show (0.20):
- `engine.income_preview(pet) -> dict` — what a game day brings, without changing anything:
  `{"job": (lo, hi) | None, "kind": "job"|"pocket"|"pension"|"welfare"|"", "why": str, "extra": [(label, n)],
  "upkeep": n, "tax": n, "net": (lo, hi)}`. `job` is the base income range (a fixed pay gives lo == hi), `extra` the daily
  advertising / «дах» / interest, `net` everything minus cost of living and wealth tax. It uses the same pieces as the
  daily payout, so the two cannot drift apart. `engine.income_line(pet)` is the ready card line:
  «💼 Касир АТБ · ≈ +420 ₴/день, побут −60 ₴» (`engine.card` shows it too).
- `pet.flags["_last_pay"] = [game_day, income, cost, tax]` — the last payout, written by the daily step. Show it once per
  game day: «💰 Зарплата: +432 ₴ · побут −60 ₴ → 💰 {pet.money} ₴» and remember the shown `game_day` in the host.
- `Pet.chance_parts(choice) -> [(label, n)]` — what the success chance adds up from (skill, items, temperament, role,
  health/mood, luck, level, «🎭 у своїй стихії», difficulty); the ints sum to the pre-clamp value `v` of
  `chance = 0.5 + v/50` (clamped to 0.2…0.95). Good for a button tooltip; `chance(choice)` stays the number to show.
  `Pet.chance(choice, items=False)` is the chance without the worn items.
- `Result.check = {skill, value, item, diff, parts}` (a skill check: skill 💪 `value` with `item` bonus against difficulty
  `diff`) and `Result.helped` (non-empty, and repeated in `Result.notes`, when the check passed only thanks to a worn item).
- Items: `ITEM_SKILL = {item: {skill: n}}` is a small bonus (+2…+5) of an item **while it is worn** (`pet.equipped`); a
  generated `gen:` item gives +1. `Pet.skill(s)` includes it (capped at `ITEM_SKILL_CAP` = +8 per skill, see
  `Pet.item_bonus(s)`); `engine.item_skill(item)` is one item's bonus. `battle.item_stats(item)` →
  `{"atk", "dfn", "skills"}` and `battle.item_label(item)` → «🗡️+6 · 💪+3» for a wardrobe or shop row. Every worn item also
  lifts the floor of «стиль» (`attr`) by 2.

## A turn of the game

```python
state = E.chat_state(await store.pet_chat(chat_id))
pets = [E.Pet.from_dict(d) for d in await store.chat_pets(chat_id)]
for p in pets:
    p.tick(rng=rng)                         # decay, ageing, salary, death, role passives
E.fix_partners(pets); E.mourn(pets)
out = E.plan(state, pets, last_seen, rng)   # one auto post per pass, within the chat's daily budget
for p in out["dm"] + ([out["target"]] if out["action"] == "event" else []):
    e, other = p.pick_event(pets, rng)
    p.start(e, other)                       # pending; show p.fmt(e.text, other) + p.options(e, other) as buttons
                                        # (p.locked(e, other) → [(idx, ₴ missing)]: optional greyed-out buttons)
for p in out["silent"]:
    E.live_silently(p, pets, rng)           # owner away: the pet decides alone, journal only
# out["action"] == "world" → E.world_start(...); out["expired"] → resolve with p.auto_choice(...)
await store.set_pet_chat(chat_id, state)
await store.save_pets([p.to_dict() for p in pets])

# later, when the owner presses a button:
res = p.resolve(E.EVENTS[p.pending["id"]], idx, other, rng)
await store.save_pets([p.to_dict()] + ([other.to_dict()] if other else []))
```

Series (serials of episodes years apart): an episode's text already starts with the recap («📺 Раніше: …») when you
format it with `p.fmt(e.text)`; `e.series` is the series id, `engine.SERIES[id]["title"]` its title, `p.series[id]["ep"]` the
episodes lived so far, and `res.series` (`id`, `title`, `ep`, `finale`, `ending`) tells what the choice just closed
(`ending` is filled when a season ends). Hosts that ignore all this still play series correctly.

Text from the engine (`Result`, `p.fmt(...)`) is plain Ukrainian with user-controlled pieces (pet and owner names) substituted. Pet names are declined by `grammar.py` (`p.name_in("gen")`, `grammar.inflect(name, case)`); to put a name into your own
text use these instead of the bare `p.name` after a preposition or as an object. The favourite food (`p.persona["food"]`)
is stored in the accusative; `persona.food_in(food, case)` gives its other forms (`"nom"`, `"gen"`, `"dat"`, `"ins"`,
`"loc"`) from a hand-written table, and a food the table does not know (an old document, your own list) is returned as is.
Pets have a gender (`p.gender`, `"m"` or `"f"`; `new_pet(..., gender=None)` flips a coin, an heir gets a fresh one,
documents without the field load as `"m"`). Texts hold gender pairs («{вилупився|вилупилася}») that `p.fmt` resolves;
for your own words use `p.g("він", "вона")`, `p.role_name()`, `p.role_desc()`, `engine.status_name(status, gender)`,
`engine.species_name(species, gender)` and **`p.ach_name(key)`** — achievements are stored under their masculine key,
show the result of `ach_name`, not the key. `ROLES[k]["name"]`, `STATUS_NAMES` and `SPECIES_NAME` stay the masculine
forms (`name_f` / `desc_f`, `STATUS_NAMES_F`, `SPECIES_NAME_F` hold the feminine). `persona.NAMES[species]` is now
`{"m": [...], "f": [...]}` and `NAME_SUFFIX` a list of `(masculine, feminine)` tails.
**Escape it for your output format** (the bot uses HTML parse mode and escapes everything). Never use player
input as a format template — `Pet.fmt` only formats trusted content templates.
`p.inner_voice(e, other)` (0.14) is one line of the pet's temperament for an event card (`""` most of the time and over
grave events): show it as «🎭 {p.temper_name()}: «…»» under the text.

## Storage contract

Any object with these async methods works (see `storage.MemoryStore`, the bot's SQLite `DB`):

| Method | Meaning |
|---|---|
| `get_pet(chat_id, owner_id) → dict \| None` | current pet of this owner in this chat |
| `chat_pets(chat_id) → list[dict]` | all pets of a chat, dead included |
| `save_pets(docs)` | upsert; move each doc's `log` entries to a log table; record a grave when a pet dies |
| `pet_log(chat_id, owner_id, gen=None, limit=30, kinds=()) → list[dict]` | life story entries |
| `pet_chat(chat_id) → dict` / `set_pet_chat(chat_id, data)` | per-chat state (budget, world event, shop day) |
| `delete_chat(chat_id)` | erase a chat (privacy) |

Privacy: everything is keyed by `chat_id` + `owner_id`; to forget a user, delete their pet docs, log rows and
graves, and remove their id from other pets' `rel`/`status`.

## Telegram notes (from the bot)

- Captions ≤ 1024 chars: event text ≤ 450 is enforced by the validator; keep the rest of the card short.
- Callback data ≤ 64 bytes: put opaque ids (owner id, `gen`, choice index) in buttons and re-check the pending
  event and owner server-side; never trust amounts or ids from a button.
- Rate limits: `BUDGET` caps how many adventures a chat sees per day; DM adventures don't count against it.

## Upgrading

Read [CHANGELOG.md](../CHANGELOG.md), bump the pin, run your test suite and a simulation. Pet documents are
forward-compatible (unknown fields ignored, new fields defaulted).
