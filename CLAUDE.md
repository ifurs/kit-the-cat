# kit-the-cat

Kit the Cat: the pet life-sim of the Ukrainian Telegram bot «Кошеня», as a standalone public package
(`kit_the_cat`). The bot (private repo `koshenyat`) installs it as a dependency; never import bot code here.

## Map
- `engine.py` — Pet (JSON document), years/ageing (decisions cost time), automatic upkeep, life stats with tiers
  (`LIFE`, `MONEY_TIERS`), events, effects, roles, world events, economy, casino, scheduling plan
- `content/` — 360 life events in a tiny DSL (`status.py`: life-stat events); `content/dsl.py` is the contract (KNOWN_FX / KNOWN_REQ) the engine implements
- `grammar.py` — declension of pet names into 7 cases (`decline`, `inflect`; `{name_gen}`…) and the `{він|вона}` gender pairs (`pick`); pure stdlib
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

## Docs and skills
- `docs/CONTENT_GUIDE.md` — how to write events (tone, Ukrainian, boundaries, difficulty/magnitude tables). Read it
  before writing content. `docs/DSL.md` is generated from code (`scripts/gen_dsl_docs.py`) — never edit by hand.
- `docs/ARCHITECTURE.md`, `docs/INTEGRATION.md` (public API, storage contract), `CONTRIBUTING.md` (versioning).
- Skills in `.claude/skills/`: `kit-event-writer`, `kit-sprite-artist`, `kit-balance`, `kit-playtest`,
  `kit-release`. Agent `.claude/agents/content-reviewer.md` reviews language and boundaries.
- Content pipeline: `scripts/content_gate.py` runs every content check; `scripts/ua_lint.py` is the Ukrainian lint
  (strict in CI); the `content-reviewer` agent does the human-level language review.
- Tools: `scripts/case_scan.py` (names in the wrong case), `scripts/gender_scan.py` (masculine words about a pet), `scripts/content_stats.py` (gaps, dead ends, hard checks), `scripts/balance.py` (simulation vs targets),
  `scripts/preview.py` (sprite sheets, `--smoke`), `scripts/ui_audit.js` (layout audit in a browser).
- New DSL key = contract in `dsl.py` + its docstring + `engine.apply/meets` + test + regenerate `docs/DSL.md`.
- Every user-visible change goes into `CHANGELOG.md` → Unreleased.

## Check
uv run ruff check src scripts tests web && uv run pytest -q && uv run python -m kit_the_cat.content.validate
uv run python scripts/gen_dsl_docs.py --check && uv run python scripts/content_stats.py --strict
uv run python scripts/ua_lint.py --strict
uv run python scripts/balance.py && uv run python scripts/preview.py --smoke
