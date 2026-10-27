# kit-the-cat

Kit the Cat: the pet life-sim of the Ukrainian Telegram bot «Кошеня», as a standalone public package
(`kit_the_cat`). The bot (private repo `koshenyat`) installs it as a dependency; never import bot code here.

## Map
- `engine.py` — Pet (JSON document), time/ageing, events, effects, roles, world events, economy, scheduling plan
- `content/` — 313 life events in a tiny DSL; `content/dsl.py` is the contract (KNOWN_FX / KNOWN_REQ) the engine implements
- `sprites*.py` — procedural pixel art: genome, species, roles, items (fixed + generated), backgrounds, groups
- `battle.py` — fighters, battles, tournaments (brackets, Elo)
- `storage.py` — MemoryStore (in-memory, JSON dump/load); hosts may provide their own with the same methods
- `sandbox/` — Sandbox game service, HTTP-free `api.py`, aiohttp `server.py` (`kit-the-cat`), static UI
- `web/` — browser build (Pyodide): `bridge.py` + `index.html`; `scripts/build_web.py`, `scripts/deploy_pages.py`

## Rules
- Core stays dependency-free: stdlib only. Pillow is optional (`images` extra) and imported lazily; aiohttp only in
  `sandbox/server.py`. CI checks the browser bundle imports with `python -I -S`.
- Time zone: `tz.TZ` (zoneinfo, falls back to a built-in Europe/Kyiv rule — Pyodide has no tzdata).
- User-facing text: Ukrainian, no russisms; dark humour OK, no hate by identity; romance only teen+ (couples adult).
- Content uses only dsl.KNOWN_FX / KNOWN_REQ; run `uv run python -m kit_the_cat.content.validate`.
- Public API used by the bot: `engine` (Pet, new_pet, EVENTS, ROLES, WORLD, BUDGET, plan, care, feed, buy, …),
  `sprites` (Look, render_gif, render_png, render_group, frame_canvases), `content.economy` (FOOD, JOBS),
  `battle`. Changing these is a breaking change → bump the version, tag, update the bot's pin.

## Check
uv run ruff check src scripts tests web && uv run pytest -q && uv run python -m kit_the_cat.content.validate
