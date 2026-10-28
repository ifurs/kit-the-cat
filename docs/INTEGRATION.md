# Using kit-the-cat in your app

The Telegram bot «Кошеня» is the reference host; the sandbox (`kit_the_cat.sandbox.game.Sandbox`) is a smaller one
worth reading first.

## Install and pin

```bash
uv add "kit-the-cat[images] @ git+https://github.com/ifurs/kit-the-cat@v0.4.0"
```

Always pin a tag. Extras: `images` (Pillow, for GIF/PNG), `sandbox` (aiohttp server).

## Public API

Stable within a minor version (see [CONTRIBUTING.md](../CONTRIBUTING.md#versioning)):

- `engine`: `Pet` (`from_dict`, `to_dict`, `tick`, `pick_event`, `options`, `chance`, `start`, `auto_choice`,
  `resolve`, `look`, `fmt`, `give`, `cooldown_left`, `mark_cool`), `new_pet`, `EVENTS`, `ROLES`, `WORLD`, `BUDGET`,
  `chat_state`, `plan`, `live_silently`, `care`, `feed`, `buy`, `shop_stock`, `job_offers`, `apply_job`,
  `fix_partners`, `mourn`, `chat_daily`, `world_start`, `world_claim`, `card`, `clock` (patchable), `SPEED`
- `sprites`: `Look`, `render_gif`, `render_png`, `render_group`, `frame_canvases`, `item_name`, `item_slot`
- `content.economy`: `FOOD`, `JOBS`, `EDUCATION`
- `battle`: `Fighter`, `fight`, `win_chance`, `update_elo`, `aftermath`, `eligible`, `bracket`

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
for p in out["silent"]:
    E.live_silently(p, pets, rng)           # owner away: the pet decides alone, journal only
# out["action"] == "world" → E.world_start(...); out["expired"] → resolve with p.auto_choice(...)
await store.set_pet_chat(chat_id, state)
await store.save_pets([p.to_dict() for p in pets])

# later, when the owner presses a button:
res = p.resolve(E.EVENTS[p.pending["id"]], idx, other, rng)
await store.save_pets([p.to_dict()] + ([other.to_dict()] if other else []))
```

Text from the engine (`Result`, `p.fmt(...)`) is plain Ukrainian with user-controlled pieces (pet and owner names) substituted.
**Escape it for your output format** (the bot uses HTML parse mode and escapes everything). Never use player
input as a format template — `Pet.fmt` only formats trusted content templates.

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
