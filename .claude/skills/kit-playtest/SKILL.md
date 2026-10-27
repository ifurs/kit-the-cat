---
name: kit-playtest
description: Playtest the Kit the Cat sandbox in a browser — start the local server or the Pyodide build, play a pet's life (hatch, care, adventures, neighbours, dates, battles, tournaments), and audit the layout on phone and desktop widths for overlapping/off-screen buttons. Use whenever the user asks to test, try, check or play the game/sandbox, reports a UI bug ("buttons overlap", "на телефоні з'їжджає"), changes sandbox/static/index.html or web/index.html, or before a release.
---

# Playtesting the sandbox

Two front-ends share one API (`sandbox/api.py`): the aiohttp server (`sandbox/static/index.html`) and the
browser build (`web/index.html` + Pyodide). UI changes usually need to land in **both** HTML files.

## Start

Use the built-in browser and `.claude/launch.json`:
- `pet-sandbox` → `uv run kit-the-cat --port 8777` (fast; saves to play.json — the Reset button starts over);
- `web-build` → serves `build/site` on 8778; build it first with `uv run python scripts/deploy_pages.py --dry-run`
  (first load downloads Pyodide, ~10 s);
- live site: https://ifurs.github.io/kit-the-cat/ (after a release).

## Play a life (functional pass)

Drive it like a player, reading the page text rather than screenshots where possible:
1. Create a pet (each species at least once over time), hatch it (fast-forward), feed/play/clean.
2. Answer several adventures; confirm the outcome text, stat changes and sprite changes (items, roles) appear.
3. Add NPC neighbours, fast-forward days: social events, dates, relationship statuses, a wedding/heir if lucky.
4. Spar and run a tournament with an odd number of pets (byes must not stall).
5. Let a pet die (neglect + fast-forward) and take the heir.
6. Reload the page: the state persists.
Watch the console for errors (`read_console_messages`, only errors) and the server log (`preview_logs`).

## Layout audit (phone + desktop)

For each width — `resize_window` preset `mobile` (375×812), then a narrow 320 px custom size, then `desktop` —
reload, open each tab and any popup/menu, and run `scripts/ui_audit.js` through the browser's JavaScript tool
(paste the file content). It returns `{width, overflowX, offscreen, overlaps, smallTargets}`; the goal is
`overflowX: false` and empty lists. Then take one screenshot per tab to catch what code can't (cut text,
ugly wrapping, canvas scaling). Reset the viewport to `desktop` when finished.

Typical fixes (see git history of index.html): `minmax(0,1fr)` grid columns, `min-width:0` on grid children,
`flex-wrap:wrap` on button rows, clamping popup position to the viewport, ≥ 40 px touch targets under
`(pointer: coarse)`.

## Report

What you played (pets, days, features touched), bugs with steps to reproduce and the audit output per width,
screenshots of anything broken, and fixes made (with the before/after audit). Run `uv run pytest -q` after UI
fixes — `tests/test_play_sandbox.py` drives the API.
