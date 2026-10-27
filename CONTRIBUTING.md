# Contributing

Thanks for wanting to make the cat's life worse (in a funny way). Players and writers: ideas are welcome as issues
(«Ідея пригоди» template). Code and content: pull requests.

## Setup

```bash
uv sync --all-extras
uv run kit-the-cat            # sandbox at http://127.0.0.1:8777
```

## What goes where

| You want to… | Read | Touch |
|---|---|---|
| write events | [docs/CONTENT_GUIDE.md](docs/CONTENT_GUIDE.md), [docs/DSL.md](docs/DSL.md) | `src/kit_the_cat/content/*.py` |
| add a DSL effect/requirement | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | `content/dsl.py` (contract + docstring), `engine.py` (`apply`/`meets`), tests |
| draw items, genes, backgrounds | `sprites*.py` docstrings | `sprites.py` / `sprites_gen.py` / `sprites_bg.py`, `scripts/gallery.py` |
| change balance | `scripts/balance.py` targets | `engine.py` constants, content numbers |
| change the sandbox UI | — | `sandbox/static/index.html` and `web/index.html` (keep them in sync) |
| use it in your app | [docs/INTEGRATION.md](docs/INTEGRATION.md) | — |

With Claude Code, the skills in `.claude/skills/` walk through each of these (event writer, sprite artist,
balance, playtest, release).

## Rules

- Core is stdlib-only (Pillow lazy, aiohttp only in the server) — the browser build depends on it.
- User-facing text is Ukrainian without russisms; boundaries in [CONTENT_GUIDE §3](docs/CONTENT_GUIDE.md#3-межі-не-обговорюються)
  are not negotiable (no hate by identity, respectful war content, no real private people).
- Every engine dice roll takes an explicit `random.Random`.
- Pet documents must stay loadable: new fields need defaults; never rename a stored field without a migration in
  `Pet.from_dict`.

## Checks (CI runs all of them)

```bash
uv run ruff check src scripts tests web
uv run pytest -q
uv run python -m kit_the_cat.content.validate
uv run python scripts/gen_dsl_docs.py --check
uv run python scripts/content_stats.py --strict
uv run python scripts/balance.py
```

## Versioning

SemVer on the public API listed in [docs/INTEGRATION.md](docs/INTEGRATION.md):
- **patch** — fixes, new content (events, items, backgrounds), balance tweaks, UI;
- **minor** — new API, new DSL keys, new stored fields (with defaults), new species/roles;
- **major** — removed/renamed API, incompatible pet documents.

Every release: update `CHANGELOG.md`, bump `pyproject.toml`, tag `vX.Y.Z`, deploy Pages, bump hosts' pins.
